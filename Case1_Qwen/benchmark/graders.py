"""Task grading.

Deterministic checkers (contains / regex / file_exists / file_contains /
code_exec / file_code_exec / test_suite / command_check) plus an
LLM-as-a-judge checker that talks to the LM Studio OpenAI-compatible
endpoint.

A task may combine several check types with "+" (score = mean of the
sub-scores), e.g. "file_contains+file_code_exec".

Optional `banned` column: semicolon-separated substrings; if any appears in
the code under test (extracted code / edited file / written tests), the
task scores 0 — used to forbid shortcuts and anti-patterns.

code_exec / file_code_exec run the model's code in a throwaway temp dir with
a hard timeout. The expected test code uses a small helper:

    check("name", boolean_expression)

Score = passed checks / total checks (continuous 0..1, enables trend stats).
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import requests

_CODE_FENCE_RE = re.compile(
    r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE
)
_CHECK_RE = re.compile(r"^(PASS|FAIL)\s+(.+)$", re.MULTILINE)

_PRELUDE = (
    "_results = []\n"
    "def check(name, cond):\n"
    "    _results.append((name, bool(cond)))\n"
)
_EPILOGUE = (
    "\ndef _run_checks():\n"
    "    for name, ok in _results:\n"
    "        print(('PASS' if ok else 'FAIL') + ' ' + name)\n"
    "_run_checks()\n"
)

_CHECKERS = {
    "contains", "regex", "file_exists", "file_contains", "code_exec",
    "file_code_exec", "llm_judge", "test_suite", "command_check",
}


class LLMJudge:
    """LLM-as-a-judge client for the LM Studio OpenAI-compatible API."""

    def __init__(self, base_url: str, model: str, api_key: str = "lm-studio",
                 timeout_s: float = 180.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_s = timeout_s

    def available(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/models", timeout=5)
            return r.status_code == 200
        except requests.RequestException:
            return False

    def grade(self, prompt: str, rubric: str, response: str) -> Optional[float]:
        system = (
            "You are a rigorous evaluation judge. Score the AI response below "
            "against the rubric. Output ONLY a JSON object of the form "
            '{"score": <float between 0 and 1>, "reason": "<one sentence>"}.'
        )
        user = (
            f"TASK PROMPT:\n{prompt}\n\n"
            f"RUBRIC (score against this):\n{rubric}\n\n"
            f"AI RESPONSE:\n{response[:20000]}\n\n"
            "JSON score:"
        )
        try:
            r = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.0,
                    "max_tokens": 256,
                },
                timeout=self.timeout_s,
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
            return _extract_score(content)
        except (requests.RequestException, KeyError, IndexError, ValueError):
            return None


def _extract_score(content: str) -> Optional[float]:
    m = re.search(r'\{\s*"score"\s*:\s*"?([0-9]*\.?[0-9]+)"?', content)
    if m:
        return max(0.0, min(1.0, float(m.group(1))))
    m = re.search(r"score[:\s]*\"?([0-9]*\.?[0-9]+)\"?", content, re.IGNORECASE)
    if m:
        return max(0.0, min(1.0, float(m.group(1))))
    return None


def extract_code_blocks(response: str) -> str:
    blocks = _CODE_FENCE_RE.findall(response)
    if blocks:
        return "\n".join(b.strip() for b in blocks)
    # No fences: if the whole response looks like code, use it.
    if response.strip() and not re.search(r"\s{2,}[A-Za-z]", response):
        return response.strip()
    return ""


def grade(task, response: str, judge: Optional[LLMJudge]) -> tuple[float | None, str]:
    """Return (score, detail). score None means grading was unavailable."""
    sub_checks = [c for c in task.check_type.split("+") if c.strip()]
    if not sub_checks:
        return None, f"unknown:{task.check_type}"
    scores = []
    details = []
    for ct in sub_checks:
        score, detail = _grade_single(task, ct.strip(), response, judge)
        if score is None:
            return None, detail
        scores.append(score)
        details.append(detail)
    score = sum(scores) / len(scores)
    return score, "+".join(details)


def _grade_single(task, ct: str, response: str,
                  judge: Optional[LLMJudge]) -> tuple[float, str]:
    if ct == "contains":
        if not task.expected.strip():
            return 0.0, "contains:empty-expected"
        return (1.0 if task.expected.lower() in response.lower() else 0.0), "contains"
    if ct == "regex":
        if not task.expected.strip():
            return 0.0, "regex:empty-expected"
        try:
            ok = re.search(task.expected, response, re.IGNORECASE) is not None
        except re.error as exc:
            return 0.0, f"regex:bad-pattern:{exc}"
        return (1.0 if ok else 0.0), "regex"
    if ct == "file_exists":
        try:
            hits = list(task.workdir.glob(task.expected))
        except (OSError, re.error) as exc:
            return 0.0, f"file_exists:{type(exc).__name__}"
        return (1.0 if hits else 0.0), f"file_exists:{len(hits)}"
    if ct == "file_contains":
        return _grade_file_contains(task)
    if ct == "code_exec":
        code = extract_code_blocks(response)
        if getattr(task, "banned", None) and _banned_in(code, task.banned):
            return 0.0, "code_exec:banned"
        return _run_code_tests(code, "", task.expected, task.workdir)
    if ct == "file_code_exec":
        lines = [l for l in task.expected.splitlines() if l.strip()]
        if not lines:
            return 0.0, "file_code_exec:no-test"
        file_rel, tests = lines[0], "\n".join(lines[1:])
        module_path = task.workdir / file_rel
        if getattr(task, "banned", None):
            try:
                banned_hit = module_path.exists() and _banned_in(
                    module_path.read_text(encoding="utf-8", errors="ignore"),
                    task.banned,
                )
            except OSError as exc:
                return 0.0, f"file_code_exec:read-error:{type(exc).__name__}"
            if banned_hit:
                return 0.0, "file_code_exec:banned"
        return _run_code_tests("", file_rel, tests, task.workdir)
    if ct == "test_suite":
        return _grade_test_suite(task, response)
    if ct == "command_check":
        return _grade_command(task)
    if ct == "llm_judge":
        if judge is None or not judge.available():
            return None, "judge_unavailable"
        score = judge.grade(task.prompt, task.rubric, response)
        if score is None:
            return None, "judge_failed"
        return score, "llm_judge"
    return None, f"unknown:{ct}"


def _banned_in(code: str, banned: list[str]) -> bool:
    lowered = code.lower()
    return any(b.lower() in lowered for b in banned)


def _grade_file_contains(task) -> tuple[float, str]:
    """Partial credit over lines: each 'glob|needle' line scores 1/n."""
    lines = [l for l in task.expected.splitlines() if l.strip()]
    if not lines:
        return 0.0, "file_contains:no-expectation"
    hits = 0
    matched_files = []
    for line in lines:
        glob_pat, _, needle = line.partition("|")
        found = False
        try:
            matches = task.workdir.glob(glob_pat.strip())
            for hit in matches:
                if hit.is_file() and needle.strip().lower() in hit.read_text(
                    encoding="utf-8", errors="ignore"
                ).lower():
                    found = True
                    matched_files.append(f"{hit.name}~{needle.strip()}")
                    break
        except (OSError, re.error) as exc:
            return 0.0, f"file_contains:{type(exc).__name__}"
        if found:
            hits += 1
    score = hits / len(lines)
    detail = f"file_contains:{hits}/{len(lines)}"
    if matched_files:
        detail += ":" + ",".join(matched_files)
    return score, detail


def _grade_test_suite(task, response: str) -> tuple[float, str]:
    """The model writes unit tests; they must pass on the GOOD module and
    fail on the BUGGY one.

    Expected format:
        GOOD_MODULE=rel/path/to/good.py
        BUGGY_MODULE=rel/path/to/buggy.py

    The model's tests are extracted from code fences. They are expected to
    be pytest-style: functions named test_* containing plain asserts, using
    `import mod` to reach the module under test. Every test_* function must
    pass against GOOD_MODULE and at least one must fail against BUGGY_MODULE.
    """
    expected = {}
    for line in task.expected.splitlines():
        line = line.strip()
        if "=" in line:
            key, _, val = line.partition("=")
            expected[key.strip()] = val.strip()
    good_rel = expected.get("GOOD_MODULE", "")
    buggy_rel = expected.get("BUGGY_MODULE", "")
    if not good_rel or not buggy_rel:
        return 0.0, "test_suite:bad-config"
    tests = extract_code_blocks(response)
    if not tests:
        return 0.0, "test_suite:no-tests"
    if getattr(task, "banned", None) and _banned_in(tests, task.banned):
        return 0.0, "test_suite:banned"
    good_detail = _run_testsuite_in_subprocess(good_rel, tests, task.workdir)
    buggy_detail = _run_testsuite_in_subprocess(buggy_rel, tests, task.workdir)
    if good_detail is None or buggy_detail is None:
        return 0.0, "test_suite:runner-failed"
    good_pass, good_total = good_detail
    buggy_pass, buggy_total = buggy_detail
    if good_total == 0:
        return 0.0, "test_suite:no-tests-found"
    passes_on_good = good_pass == good_total
    catches_bug = buggy_pass < buggy_total
    if passes_on_good and catches_bug:
        return 1.0, f"test_suite:good_ok/buggy_caught"
    return 0.0, (
        f"test_suite:good={good_pass}/{good_total},buggy={buggy_pass}/{buggy_total}"
        " (want good all-pass, buggy any-fail)"
    )


def _run_testsuite_in_subprocess(module_rel: str, tests_src: str,
                                 workdir: Path) -> tuple[int, int] | None:
    """Run pytest-style test functions against one module file.

    Returns (passed, total) or None if the runner itself failed.
    """
    module_path = (workdir / module_rel).resolve()
    if not module_path.exists():
        return None
    runner = (
        "import importlib.util, sys as _sys\n"
        "import pathlib as _p\n"
        "_path = " + json.dumps(str(module_path)) + "\n"
        "_spec = importlib.util.spec_from_file_location('mod', _path)\n"
        "_m = importlib.util.module_from_spec(_spec)\n"
        "_sys.modules['mod'] = _m\n"
        "_spec.loader.exec_module(_m)\n"
        "mod = _m\n"
        + tests_src
        + "\n"
        "_tests = [(k, v) for k, v in globals().items()\n"
        "           if k.startswith('test_') and callable(v)]\n"
        "_passed = 0\n"
        "for _name, _fn in _tests:\n"
        "    try:\n"
        "        _fn()\n"
        "        _passed += 1\n"
        "        print('PASS ' + _name)\n"
        "    except BaseException as e:\n"
        "        print('FAIL ' + _name)\n"
        "print('SUMMARY %d/%d' % (_passed, len(_tests)))\n"
    )
    with tempfile.TemporaryDirectory(prefix="hermesbench_") as tmp:
        script = Path(tmp) / "run_testsuite.py"
        script.write_text(runner, encoding="utf-8")
        try:
            proc = subprocess.run(
                [sys_executable(), str(script)],
                cwd=str(workdir) if workdir.exists() else tmp,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=90,
            )
        except (subprocess.TimeoutExpired, OSError):
            return None
    m = re.search(r"SUMMARY (\d+)/(\d+)", proc.stdout)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def _grade_command(task) -> tuple[float, str]:
    """Run a command in the task workdir and compare expected stdout lines.

    Expected format:
        CMD:python cli.py --input data.csv
        line1 expected
        line2 expected
    Score = matched expected lines / total expected lines.
    """
    lines = [l for l in task.expected.splitlines() if l.strip()]
    if not lines or not lines[0].startswith("CMD:"):
        return 0.0, "command_check:bad-config"
    cmd = lines[0][4:].strip()
    want = [l.strip() for l in lines[1:]]
    if not want:
        return 0.0, "command_check:no-expectation"
    try:
        import shlex
        parts = shlex.split(cmd)
    except ValueError as exc:
        return 0.0, f"command_check:bad-cmd:{exc}"
    if parts and parts[0].lower() == "python":
        parts[0] = sys_executable()
    try:
        proc = subprocess.run(
            parts,
            cwd=str(task.workdir) if task.workdir.exists() else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return 0.0, f"command_check:{type(exc).__name__}"
    got = [l.strip() for l in proc.stdout.splitlines() if l.strip()]
    matched = sum(1 for w in want if w in got)
    return matched / len(want), f"command_check:{matched}/{len(want)}"


def _run_code_tests(model_code: str, module_file: str, tests: str,
                    workdir: Path) -> tuple[float, str]:
    """Sandboxed execution of model code + test code (hard timeout)."""
    module_loader = ""
    if module_file:
        module_loader = (
            "import importlib.util, pathlib as _p, sys as _sys\n"
            "_spec = importlib.util.spec_from_file_location(\n"
            "    'user_mod', _p.Path.cwd() / "
            + json.dumps(str(module_file))
            + ")\n"
            "mod = importlib.util.module_from_spec(_spec)\n"
            "_sys.modules['user_mod'] = mod\n"
            "_spec.loader.exec_module(mod)\n"
        )
    source = "\n".join(
        [
            _PRELUDE,
            module_loader,
            model_code,
            tests,
            _EPILOGUE,
        ]
    )
    if not model_code and not module_file:
        return 0.0, "code_exec:no-code"
    with tempfile.TemporaryDirectory(prefix="hermesbench_") as tmp:
        script = Path(tmp) / "run_tests.py"
        script.write_text(source, encoding="utf-8")
        try:
            proc = subprocess.run(
                [sys_executable(), str(script)],
                cwd=str(workdir) if workdir.exists() else tmp,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            return 0.0, "code_exec:timeout"
        except OSError as exc:
            return 0.0, f"code_exec:oserror:{exc}"
    out = proc.stdout + "\n" + proc.stderr
    checks = _CHECK_RE.findall(out)
    if not checks:
        return 0.0, f"code_exec:no-checks::error:{out[:300]}"
    passed = sum(1 for status, _ in checks if status == "PASS")
    return passed / len(checks), f"code_exec:{passed}/{len(checks)}"


def sys_executable() -> str:
    import sys
    return sys.executable
