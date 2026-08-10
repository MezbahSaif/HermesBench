"""Offline self-tests: graders, statistics, graphs (no Hermes, no LM Studio)."""
import shutil
import sys
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from benchmark.graders import grade, extract_code_blocks, _EPILOGUE
from benchmark.task_loader import load_tasks, Task as BenchTask
from analysis import statistics as st
from analysis.graphs import plot_all

failures = []
def check(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)

# --- task loading ---------------------------------------------------------
tasks = load_tasks(ROOT / "datasets" / "benchmark.csv")
check("16 tasks loaded", len(tasks) == 16)

by_id = {t.task_id: t for t in tasks}

# --- deterministic graders (judge=None) -----------------------------------
r = by_id["prog_bubble_sort"]
score, detail = grade(r,
    "```python\ndef bubble_sort(arr):\n    arr = list(arr)\n    for i in range(len(arr)):\n"
    "        for j in range(len(arr)-1-i):\n            if arr[j] > arr[j+1]:\n"
    "                arr[j], arr[j+1] = arr[j+1], arr[j]\n    return arr\n```",
    None)
check(f"bubble_sort score==1 (got {score}, {detail})", score == 1.0)

score, detail = grade(r, "```python\ndef bubble_sort(arr):\n    return sorted(arr)\n```", None)
check(f"bubble_sort sorted-alias score==1 (got {score})", score == 1.0)

score, detail = grade(r, "```python\ndef bubble_sort(arr):\n    return arr\n```", None)
check(f"bubble_sort partial credit 0.4<0.7 (got {score}, {detail})",
      score is not None and 0.0 < score < 0.7)

score, detail = grade(r, "I have no idea how to write bubble sort.", None)
check(f"bubble_sort no-code score==0 (got {score}, {detail})", score == 0.0)

r = by_id["prog_fizzbuzz"]
score, detail = grade(r,
    "```python\ndef fizzbuzz(n):\n"
    "    out = []\n"
    "    for i in range(1, n+1):\n"
    "        if i % 15 == 0: out.append('FizzBuzz')\n"
    "        elif i % 3 == 0: out.append('Fizz')\n"
    "        elif i % 5 == 0: out.append('Buzz')\n"
    "        else: out.append(str(i))\n"
    "    return out\n```", None)
check(f"fizzbuzz score==1 (got {score}, {detail})", score == 1.0)

r = by_id["prog_debug_syntax"]
# Fix the intentionally-broken fixture, as the agent would (in a TEMP copy,
# never the real dataset workdir):
dbg_tmp = Path(tempfile.mkdtemp(prefix="selftest_dbg_"))
dbg_tmp.joinpath("broken.py").write_text(
    "def main_task(x):\n    result = x * x\n    return result\n",
    encoding="utf-8",
)
dbg_task = BenchTask(task_id="prog_debug_syntax", category=r.category,
                     prompt=r.prompt, check_type=r.check_type,
                     expected=r.expected, threshold=r.threshold,
                     rubric=r.rubric, workdir=dbg_tmp, family=r.family)
score, detail = grade(dbg_task, "I fixed it.", None)
check(f"debug_syntax via file==1 (got {score}, {detail})", score == 1.0)

r = by_id["reason_logic"]
score, detail = grade(r, "4", None)
check(f"logic regex score==1 (got {score})", score == 1.0)
score, detail = grade(r, "Bob is 8", None)
check(f"logic regex wrong==0 (got {score})", score == 0.0)

r = by_id["reason_error_hunt"]
score, detail = grade(r, "The answer is line 6.", None)
check(f"error_hunt contains==1 (got {score})", score == 1.0)

# --- file checkers --------------------------------------------------------
r = by_id["term_organize"]
# Simulate the agent's edit in a TEMP copy, never the real dataset workdir:
org_tmp = Path(tempfile.mkdtemp(prefix="selftest_org_"))
org_tmp.joinpath("README.md").write_text(
    "data.csv 52\nnotes.txt 40\nREADME.md 44\nscript.py 31\n", encoding="utf-8"
)
org_task = BenchTask(task_id="term_organize", category=r.category,
                     prompt=r.prompt, check_type=r.check_type,
                     expected=r.expected, threshold=r.threshold,
                     rubric=r.rubric, workdir=org_tmp, family=r.family)
score, detail = grade(org_task, "done", None)
check(f"organize file_contains==1 (got {score}, {detail})", score == 1.0)

# --- llm_judge without judge ----------------------------------------------
r = by_id["res_summarize_paper"]
score, detail = grade(r, "summary text", None)
check(f"judge None->score None (got {score}, {detail})", score is None and detail == "judge_unavailable")

# --- v2 checkers (SE dataset: file_contains multi-line, "+", banned,
#     test_suite, command_check) --------------------------------------------


def make_task(check_type, expected, banned=None, files=None):
    tmp = tempfile.mkdtemp(prefix="selftest_")
    workdir = Path(tmp)
    for rel, content in (files or []):
        t = workdir / rel
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_text(content, encoding="utf-8")
    return BenchTask(task_id="t", category="c", prompt="p",
                     check_type=check_type, expected=expected,
                     threshold=0.7, rubric="", workdir=workdir,
                     banned=banned or [])


t = make_task("file_contains", "app.py|FastAPI(\napp.py|HTTPException\nrequirements.txt|fastapi\n",
              files=[("app.py", "from fastapi import FastAPI, HTTPException\napp = FastAPI()\n"),
                     ("requirements.txt", "fastapi\n")])
score, detail = grade(t, "", None)
check(f"file_contains multi-line all==1 (got {score}, {detail})", score == 1.0)

t = make_task("file_contains", "app.py|FastAPI(\napp.py|HTTPException\n",
              files=[("app.py", "from fastapi import FastAPI\napp = FastAPI()\n")])
score, _ = grade(t, "", None)
check(f"file_contains multi-line partial==0.5 (got {score})", score == 0.5)

t = make_task("contains+regex", "hello")
score, detail = grade(t, "say hello!", None)
check(f"combined '+' both pass==1 (got {score}, {detail})", score == 1.0)
score, _ = grade(t, "goodbye", None)
check(f"combined '+' both fail==0 (got {score})", score == 0.0)

t = make_task("file_code_exec", "mod.py\ncheck(\"x\", mod.X == 1)\n",
              banned=["global "], files=[("mod.py", "global _g\nX = 1\n")])
score, detail = grade(t, "", None)
check(f"banned pattern -> 0 (got {score}, {detail})", score == 0.0)

t = make_task("file_code_exec", "mod.py\ncheck(\"x\", mod.X == 1)\n",
              banned=["global "], files=[("mod.py", "X = 1\n")])
score, _ = grade(t, "", None)
check(f"clean module with banned -> 1 (got {score})", score == 1.0)

good_mod = "def add(a, b):\n    return a + b\n"
buggy_mod = "def add(a, b):\n    return a - b\n"
suite = ("def test_add():\n    assert mod.add(2, 3) == 5\n\n"
         "def test_zero():\n    assert mod.add(0, 0) == 0\n")
t = make_task("test_suite", "GOOD_MODULE=good.py\nBUGGY_MODULE=buggy.py\n",
              files=[("good.py", good_mod), ("buggy.py", buggy_mod)])
score, detail = grade(t, f"```python\n{suite}\n```", None)
check(f"test_suite catches bug==1 (got {score}, {detail})", score == 1.0)
score, _ = grade(t, "```python\ndef test_nothing():\n    pass\n```", None)
check(f"test_suite weak tests==0 (got {score})", score == 0.0)

tool = ("import sys\n"
        "n = int(sys.argv[sys.argv.index('--n') + 1])\n"
        "for i in range(1, n + 1):\n    print(i)\n")
t = make_task("command_check", "CMD:python tool.py --n 3\n1\n2\n3\n",
              files=[("tool.py", tool)])
score, detail = grade(t, "", None)
check(f"command_check exact==1 (got {score}, {detail})", score == 1.0)
t = make_task("command_check", "CMD:python tool.py --n 3\n1\n2\n3\n",
              files=[("tool.py", "print('nope')\n")])
score, _ = grade(t, "", None)
check(f"command_check wrong==0 (got {score})", score == 0.0)

# --- regression tests from the code review ----------------------------------
# 1) CSV round-trip: literal \n escapes + CRLF must decode (bug: broke every
#    multi-line expected in generated datasets)
from benchmark.task_loader import _unescape
check("unescape \\n + CRLF", _unescape("a\\nb\r\nc") == "a\nb\nc")
kt = [k for k in load_tasks(ROOT / "datasets" / "variants" / "round_1_se.csv")
      if k.task_id == "implement_knapsack"][0]
check("CSV task expected decodes to real newlines",
      kt.expected.startswith("solution.py\ncheck("))

# 2) empty expected must not auto-pass contains/regex
t = make_task("contains", "")
score, detail = grade(t, "anything", None)
check(f"empty expected contains==0 (got {score}, {detail})", score == 0.0)
t = make_task("regex", "")
score, _ = grade(t, "anything", None)
check(f"empty expected regex==0 (got {score})", score == 0.0)

# 3) test_suite honors banned patterns
t = make_task("test_suite", "GOOD_MODULE=good.py\nBUGGY_MODULE=buggy.py\n",
              banned=["global "],
              files=[("good.py", good_mod), ("buggy.py", buggy_mod)])
score, detail = grade(t, f"```python\nglobal _x\n{suite}\n```", None)
check(f"test_suite banned==0 (got {score}, {detail})", score == 0.0)

# 4) file_contains with a directory glob (previously crashed the benchmark)
t = make_task("file_contains", "sub/*|needle", files=[("sub/x.txt", "needle")])
score, _ = grade(t, "", None)
check(f"file_contains subdir glob==1 (got {score})", score == 1.0)
t = make_task("file_contains", "sub|needle", files=[("sub/x.txt", "needle")])
score, detail = grade(t, "", None)
check(f"file_contains dir-match safe==0 (got {score}, {detail})", score == 0.0)

# 5) command_check with quoted args (shlex)
t = make_task("command_check",
              'CMD:python echo.py --msg "hello world"\nhello world\n',
              files=[("echo.py", "import sys\nprint(sys.argv[sys.argv.index('--msg') + 1])\n")])
score, detail = grade(t, "", None)
check(f"command_check quoted args==1 (got {score}, {detail})", score == 1.0)

# 6) judge score extraction accepts quoted values
from benchmark.graders import _extract_score
check("extract quoted score",
      _extract_score('{"score": "0.8"}') == 0.8
      and _extract_score('score: 0.4') == 0.4)

# 7) final-round comparison includes success_rate and drops NaN rows
from analysis.statistics import compare_arms, welch_ttest
sdf = pd.DataFrame([
    {"run_id": "r", "round": rd, "arm": ar, "task_id": f"t{ti}", "family": f"f{ti % 2}",
     "category": "c", "passed": p, "score": sc, "duration_s": 1.0,
     "api_calls": 1, "tool_call_log_events": 0, "error_log_events": 0,
     "retry_log_events": 0, "reflection_log_events": 0,
     "human_interventions": 0, "after_skill_files": 0, "after_memory_bytes": 0}
    for rd in range(1, 6)
    for ar in ("treatment", "control")
    for ti, (p, sc) in enumerate(
        ([(False, 0.2), (True, 0.8), (True, 0.9), (True, 1.0), (True, 0.95)] if ar == "treatment" else
         [(False, 0.3), (False, 0.3), (True, 0.6), (False, 0.4), (True, 0.7)])
    )
])
cmp = compare_arms(sdf)
has_sr = any(r["metric"] == "success_rate" and " vs " in r["arm"]
             for _, r in cmp.iterrows())
check("final-round success_rate comparison present", has_sr)
w = welch_ttest([1.0, float("nan"), 0.5], [0.0, 0.2])
check("welch drops NaN (p finite)", w["p"] == w["p"] and w["p"] != 1.0)

# 8) treatment-first ordering: mean diff = treatment - control
trow = cmp[(cmp["metric"] == "success_rate") & (cmp["arm"].str.contains(" vs "))].iloc[0]
check("treatment-first ordering", "treatment" in trow["arm"].split(" vs ")[0])

# --- SE task generator: every variant must self-validate (offline) --------
import datasets.generate_tasks as gen
all_variants = gen._all_variants(sorted(gen.FAMILIES))
valid, bad = 0, []
for v in all_variants:
    ok_v, msg = gen._validate_variant(v)
    if ok_v:
        valid += 1
    else:
        bad.append(f"{v['name']}: {msg}")
check(f"generator: {valid}/{len(all_variants)} variants validated (bad={bad[:2]})",
      valid == len(all_variants) and not bad)

with tempfile.TemporaryDirectory(prefix="selftest_gen_") as tmp:
    gen.generate(1, 2, 99, sorted(gen.FAMILIES), Path(tmp))
    csvs = list(Path(tmp).glob("round_1_se.csv"))
    check("generator emits round CSV", len(csvs) == 1)
    if csvs:
        v2_tasks = load_tasks(csvs[0])
        check("generated CSV loads through loader", len(v2_tasks) >= 7)
        check("generated tasks carry family", all(hasattr(x, "family") and x.family for x in v2_tasks))
        check("generated CSV has no banned col issues",
              all(isinstance(x.banned, list) for x in v2_tasks))

# --- statistics -----------------------------------------------------------
x = [0.4, 0.5, 0.6, 0.65, 0.7]
tau, p = st.mann_kendall(x)
check(f"MK increasing tau>0 (tau={tau:.3f}, p={p:.4f})", tau > 0 and p < 0.2)
tau0, p0 = st.mann_kendall(list(reversed(x)))
check(f"MK decreasing tau<0 (tau={tau0:.3f})", tau0 < 0)
tr = st.linear_trend(x)
check(f"OLS slope>0 (slope={tr['slope']:.4f}, p={tr['p']:.4f})", tr["slope"] > 0 and tr["p"] < 0.05)
w = st.welch_ttest([0.7, 0.8, 0.75, 0.85], [0.4, 0.5, 0.45, 0.55])
check(f"Welch t p<0.05 (p={w['p']:.4f}, d={w['d']:.3f})", w["p"] < 0.05)

# --- synthetic metrics DataFrame + report + graphs ------------------------
import numpy as np
rng = np.random.default_rng(7)
rows = []
for arm, trend in (("treatment", 0.06), ("control", 0.005)):
    for round_no in range(1, 6):
        for t in tasks:
            base = 0.35 + trend * round_no
            score = max(0.0, min(1.0, base + rng.normal(0, 0.12)))
            rows.append({
                "run_id": "synth", "round": round_no, "arm": arm,
                "task_id": t.task_id, "category": t.category,
                "status": "ok", "passed": score >= 0.7, "score": score,
                "duration_s": rng.normal(120, 20), "api_calls": rng.poisson(6),
                "tool_call_log_events": rng.poisson(4),
                "error_log_events": rng.poisson(2),
                "retry_log_events": rng.poisson(1),
                "reflection_log_events": rng.poisson(1),
                "human_interventions": 0,
                "after_skill_files": 0 if arm == "control" else round_no * 2,
                "after_memory_bytes": 0 if arm == "control" else round_no * 500,
            })
# force a few failures so recovery_rate is computable
rows[0]["passed"] = False; rows[0]["score"] = 0.2   # treatment R1 fails
rows[16]["passed"] = False; rows[16]["score"] = 0.2  # control R1 fails
df = pd.DataFrame(rows)
rep = st.compare_arms(df)
sig_treatment = rep[(rep["arm"] == "treatment") & (rep["metric"] == "success_rate")]["trend_significant"].iloc[0]
sig_control = rep[(rep["arm"] == "control") & (rep["metric"] == "success_rate")]["trend_significant"].iloc[0]
check(f"synthetic: treatment trend significant (got {sig_treatment})", sig_treatment)
check(f"synthetic: control trend not significant (got {sig_control})", not sig_control)
rec = st.recovery_rate_series(df, "treatment")
check(f"recovery series present (got {len(rec)} rows)", len(rec) == 5)
check(f"some recovery happened (recovered={rec['recovered'].sum()})",
      rec["recovered"].sum() >= 1)
print(rep[["metric", "arm", "tau", "trend_p", "trend_significant"]].to_string(index=False))

pngs = plot_all(df, ROOT / "analysis" / "plots" / "_selftest")
check(f"graphs saved ({len(pngs)} pngs)", len(pngs) >= 8)

# --- workspace isolation (pristine snapshot + restore) ---------------------
from benchmark.benchmark_runner import restore_workspace, snapshot_pristine

iso = Path(tempfile.mkdtemp(prefix="selftest_iso_"))
iso.joinpath("work", "sub").mkdir(parents=True)
iso.joinpath("work", "a.txt").write_text("v1", encoding="utf-8")
iso.joinpath("work", "sub", "b.txt").write_text("v2", encoding="utf-8")
iso_task = BenchTask(task_id="iso", category="se_easy", prompt="p",
                     check_type="file_contains", expected="v1", threshold=0.5,
                     rubric="", workdir=iso / "work", family="bug_fix")
check("snapshot_pristine creates pristine", snapshot_pristine(iso_task))
# agent edits the workdir...
iso_task.workdir.joinpath("a.txt").write_text("TAMPERED", encoding="utf-8")
iso_task.workdir.joinpath("evil_new.txt").write_text("x", encoding="utf-8")
check("restore_workspace restores", restore_workspace(iso_task))
check("restore wiped tampering",
      iso_task.workdir.joinpath("a.txt").read_text(encoding="utf-8") == "v1"
      and not iso_task.workdir.joinpath("evil_new.txt").exists()
      and iso_task.workdir.joinpath("sub", "b.txt").read_text(encoding="utf-8") == "v2")
check("restore_workspace no-op without pristine",
      not restore_workspace(BenchTask(task_id="nope", category="se_easy",
                                      prompt="p", check_type="file_contains",
                                      expected="x", threshold=0.5, rubric="",
                                      workdir=Path(tempfile.mkdtemp()), family="bug_fix")))
# every variant task in the real dataset has a pristine snapshot
vt = load_tasks(ROOT / "datasets" / "variants" / "round_1_se.csv")
missing = [t.task_id for t in vt if not t.workdir.parent.joinpath("pristine").is_dir()]
check(f"all variant tasks have pristine (missing={missing})", not missing)
# every v1 task in the real dataset has a workdir + pristine snapshot
v1 = load_tasks(ROOT / "datasets" / "benchmark.csv")
missing_work = [t.task_id for t in v1 if not t.workdir.is_dir()]
missing_pristine = [t.task_id for t in v1
                    if not t.workdir.parent.joinpath("pristine").is_dir()]
check(f"all v1 tasks have workdir (missing={missing_work})", not missing_work)
check(f"all v1 tasks have pristine (missing={missing_pristine})", not missing_pristine)
shutil.rmtree(iso)

# --- metrics engine (csv + xlsx + plots + verdict) --------------------------
from analysis.metrics_engine import (generate_outputs, build_summary,
                                     build_recovery, verdict)

engine_dir = Path(tempfile.mkdtemp(prefix="selftest_engine_"))
res = generate_outputs(df, engine_dir, quiet=True)
check("engine writes metrics.csv", Path(res["metrics_csv"]).exists())
check("engine writes results.xlsx", res["xlsx"] is not None
      and Path(res["xlsx"]).exists())
check(f"engine writes plots ({len(res['plots'])})", len(res["plots"]) >= 8)
with pd.ExcelFile(res["xlsx"]) as xf:
    sheets = xf.sheet_names
check(f"xlsx has 8 sheets (got {sheets})",
      sheets == ["metrics", "summary", "improvement", "gain", "families",
                 "regression", "trends", "recovery"])
trends = pd.read_excel(res["xlsx"], sheet_name="trends")
check("trends sheet has tau/p columns",
      {"tau", "trend_p", "trend_significant"} <= set(trends.columns))
rec = build_recovery(df)
check("recovery sheet covers both arms",
      set(rec.columns) >= {"treatment_recovery_rate",
                           "control_recovery_rate"})
v = verdict(df)
check("verdict: treatment improving", v["per_metric"]["success_rate"].get("treatment") is True)
check("verdict: control not improving", v["per_metric"]["success_rate"].get("control") is False)
check("verdict: claim supported on success_rate",
      "success_rate" in v["supported_metrics"])
summ = build_summary(df)
check("summary table rows = rounds x arms",
      len(summ) == len(df["round"].unique()) * len(df["arm"].unique()))
shutil.rmtree(engine_dir)

# --- resumed runs must accumulate rows across invocations ------------------
# Regression test: _flush_metrics overwrites metrics.csv, so a resumed round
# must re-load the existing rows (with numeric dtypes) or rounds 1..N-1 are
# silently erased. Exercises BenchmarkRunner.__init__ + _flush_metrics only.
from benchmark.config_loader import load_config
from benchmark.benchmark_runner import BenchmarkRunner, METRIC_COLUMNS

resume_dir = Path(tempfile.mkdtemp(prefix="selftest_resume_"))
old = [dict(zip(METRIC_COLUMNS, [None] * len(METRIC_COLUMNS)))]
old[0].update(run_id="rt", round=1, arm="treatment",
              task_id="bug_fix_text_offbyone", family="bug_fix",
              category="se_medium", status="ok", passed=True, score=0.75,
              threshold=0.7, duration_s=123.4, response_chars=100,
              api_calls=5, human_interventions=0,
              completed_at="2026-08-05T10:00:00")
pd.DataFrame(old).to_csv(resume_dir / "metrics.csv", index=False)
rcfg = load_config(ROOT / "config" / "config.yaml")
r = BenchmarkRunner(rcfg, resume_dir, "rt", ["treatment"], 5,
                    resume=True, dry_run=True, round_no=2)
acc = r._flush_metrics()
check("resume loads existing rows", len(acc) == 1)
check("resume keeps numeric dtypes", acc["score"].dtype.kind in "fiu")
new = dict(acc.iloc[0].to_dict())
new["round"] = 2
new["score"] = 1.0
r.rows.append(new)
acc2 = r._flush_metrics()
check("resume appends without erasing", len(acc2) == 2
      and set(acc2["round"]) == {1, 2})
shutil.rmtree(resume_dir)

print()
if failures:
    print(f"{len(failures)} FAILURES: {failures}")
    sys.exit(1)
print("ALL OFFLINE SELF-TESTS PASSED")
