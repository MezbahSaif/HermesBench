# hermes_task_module.py
import shutil
import sys
import traceback
import uuid
from pathlib import Path
import dspy

def get_repo_root():
    current = Path(__file__).resolve()
    for p in [current] + list(current.parents):
        if (p / "datasets" / "variants" / "tasks").is_dir():
            return p
    return current.parent.parent

_repo_root = get_repo_root()
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from benchmark.hermes_interface import HermesInterface
from benchmark.graders import grade
from benchmark.task_loader import Task
from benchmark.infrastructure_recovery import restore_workspace


class LMStudioLM(dspy.LM):
    """dspy's JSONAdapter sends response_format={"type": "json_object"},
    which this LM Studio build rejects (only "json_schema"/"text" allowed).
    Removing response_format from supported_params makes the adapters skip it
    and issue plain text calls; the model's JSON text output is parsed from
    the raw response instead."""
    @property
    def supported_params(self) -> set:
        return super().supported_params - {"response_format"}


class HermesTaskSignature(dspy.Signature):
    """Solve the following coding task."""
    task_id: str = dspy.InputField(desc="The unique ID of the task")
    problem_text: str = dspy.InputField(desc="The problem statement")
    result_summary: str = dspy.OutputField(desc="Free-text summary of execution")


class HermesTaskModule(dspy.Module):
    def __init__(self, base_prompt_template: str, hermes_exe: Path, hermes_home: Path,
                 hermes_real_home: Path = None, student_lm=None, reflection_lm=None,
                 task_meta: dict = None):
        super().__init__()
        self.predict = dspy.Predict(HermesTaskSignature)
        if self.predict.signature is not None and hasattr(self.predict.signature, 'with_instructions'):
            self.predict.signature = self.predict.signature.with_instructions(base_prompt_template)
        elif self.predict.signature is not None:
            self.base_prompt_template = base_prompt_template
        
        self.hermes_exe = hermes_exe
        self.hermes_home = hermes_home
        self.hermes_real_home = Path(hermes_real_home) if hermes_real_home else hermes_home
        self.student_lm = student_lm
        self.reflection_lm = reflection_lm
        self.task_meta = task_meta or {}

    @property
    def task_prompt(self):
        sig = getattr(self.predict, 'extended_signature', getattr(self.predict, 'signature', None))
        return getattr(sig, 'instructions', "") if sig is not None else ""

    def forward(self, task_id: str, pristine_files: str):
        print(f"\n[GEPA LOG] Starting evaluation on Task: {task_id}", flush=True)
        pristine_dir = Path(pristine_files)
        workdir_path = pristine_dir.parent / f"{pristine_dir.name}__{uuid.uuid4().hex[:8]}"

        if not pristine_dir.is_dir():
            try:
                dummy_task = Task(task_id, category="", prompt="", check_type="", expected="",
                                  threshold=0.7, rubric="", workdir=pristine_dir)
                restore_workspace(dummy_task)
            except Exception as exc:
                print(f"[HERMES] Could not restore pristine workspace for {task_id}: {exc}")

        try:
            shutil.copytree(pristine_dir, workdir_path)
        except Exception as exc:
            print(f"[HERMES] workspace copy failed for {task_id}: {exc}")
            traceback.print_exc()
            shutil.rmtree(workdir_path, ignore_errors=True)
            return dspy.Prediction(score=None, score_detail=f"workspace-copy-error: {exc}", diff="N/A")

        try:
            try:
                md = self.task_meta.get(task_id)
                if md:
                    task = Task(task_id=task_id,
                                category=md.get("category", ""),
                                prompt="",
                                check_type=md.get("check_type", ""),
                                expected=md.get("expected", ""),
                                threshold=float(md.get("threshold", 0.7) or 0.7),
                                rubric=md.get("rubric", ""),
                                workdir=workdir_path,
                                family=md.get("family", ""),
                                banned=list(md.get("banned", [])))
                else:
                    task = Task(task_id, category="", prompt="", check_type="", expected="",
                                threshold=0.7, rubric="", workdir=workdir_path)
            except Exception as exc:
                print(f"[HERMES] Task creation failed for {task_id}: {exc}")
                traceback.print_exc()
                return dspy.Prediction(score=None, score_detail=f"task-creation-error: {exc}", diff="N/A")

            prompt_text = ""
            for possible in ["problem.json", "task.json", "prompt.json",
                             "problem.txt", "task.txt", "prompt.txt",
                             "problem.md", "task.md", "prompt.md"]:
                p = workdir_path / possible
                if p.is_file():
                    try:
                        prompt_text = p.read_text(encoding="utf-8")[:500]
                        break
                    except Exception:
                        continue
            if not prompt_text.strip():
                prompt_text = "Implement a solution for the given coding task."

            # Call self.predict FIRST so GEPA can intercept and track the prediction
            pred = self.predict(task_id=task_id, problem_text=prompt_text)

            # Now read the (possibly GEPA-mutated) instructions
            rendered_prompt = self.task_prompt.replace("{task_id}", task_id).replace("{prompt}", prompt_text)

            model_str = self.student_lm.model if self.student_lm is not None else ""

            try:
                iface = HermesInterface(
                    {"hermes": {"executable": str(self.hermes_exe),
                                "real_home": str(self.hermes_real_home),
                                "model": model_str,
                                "provider": "",
                                "extra_args": []},
                     "benchmark": {"pass_threshold": 0.7}},
                self.hermes_home,
                self.hermes_home / task_id / "work"
                )
            except Exception as exc:
                print(f"[HERMES] HermesInterface creation failed for {task_id}: {exc}")
                traceback.print_exc()
                return dspy.Prediction(score=None, score_detail=f"iface-creation-error: {exc}", diff="N/A")

            try:
                iface.seed_home()
            except Exception as exc:
                print(f"[HERMES] seed_home failed for {task_id}: {exc}")
                traceback.print_exc()
                return dspy.Prediction(score=None, score_detail=f"seed-home-error: {exc}", diff="N/A")

            task.prompt = rendered_prompt
            usage_path = self.hermes_home / task_id / "usage.json"
            usage_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                result = iface.run_task(task, usage_path)
            except Exception as exc:
                print(f"[HERMES] iface.run_task failed for {task_id}: {exc}")
                traceback.print_exc()
                return dspy.Prediction(score=None, score_detail=f"hermes-execution-error: {exc}", diff="N/A")

            try:
                score, detail = grade(task, result.response, judge=None)
            except Exception as exc:
                print(f"[HERMES] grade() failed for {task_id}: {exc}")
                score, detail = None, f"grader-error:{type(exc).__name__}"

            passed = bool(score is not None and score >= task.threshold) if score is not None else False

            return dspy.Prediction(
                score=score,
                score_detail=detail if detail else ("passed" if passed else "failed"),
                diff=f"task_{task.task_id}_score_{score}_passed_{passed}"
            )
        finally:
            shutil.rmtree(workdir_path, ignore_errors=True)


class ScoreWithFeedback:
    """Metric result that satisfies BOTH dspy 3.3 GEPA and MIPROv2.

    GEPA's feedback pipeline does `hasattr(o, "feedback")` and then indexes
    `o["score"]` / `o["feedback"]` (gepa_utils.py feedback_fn), while dspy's
    parallelizer does `sum(vals)` over raw metric outputs and GEPA's
    evaluate() extracts `s["score"] if hasattr(s, "score") else s`.

    A plain dict crashes the parallelizer (`int + dict`); a plain float loses
    the execution feedback. This object supports attribute access, subscript
    access, and numeric coercion so both optimizers see a float score while
    the reflection gets the real `score_detail` feedback text.
    """
    def __init__(self, score, feedback):
        self.score = float(score)
        self.feedback = str(feedback)

    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __radd__(self, other):
        return other + self.score

    def __add__(self, other):
        return self.score + other

    def __float__(self):
        return self.score

    def __gt__(self, other):
        return self.score > other

    def __lt__(self, other):
        return self.score < other

    def __ge__(self, other):
        return self.score >= other

    def __le__(self, other):
        return self.score <= other

    def __eq__(self, other):
        return self.score == other

    def __ne__(self, other):
        return self.score != other

    def __repr__(self):
        return f"ScoreWithFeedback(score={self.score}, feedback={self.feedback!r})"


def hermes_metric(gold, pred, trace=None, pred_name=None, pred_trace=None):
    score = float(pred.score) if (pred is not None and getattr(pred, "score", None) is not None) else 0.0
    feedback = getattr(pred, "score_detail", "no-detail-provided")
    return ScoreWithFeedback(score=score, feedback=str(feedback))