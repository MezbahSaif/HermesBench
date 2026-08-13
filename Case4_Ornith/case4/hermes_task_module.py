# hermes_task_module.py
import sys
import traceback
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
from benchmark.infrastructure_recovery import restore_workspace
from benchmark.graders import grade
from benchmark.task_loader import Task


class HermesTaskSignature(dspy.Signature):
    """Solve the following coding task."""
    task_id: str = dspy.InputField(desc="The unique ID of the task")
    problem_text: str = dspy.InputField(desc="The problem statement")
    result_summary: str = dspy.OutputField(desc="Free-text summary of execution")


class HermesTaskModule(dspy.Module):
    def __init__(self, base_prompt_template: str, hermes_exe: Path, hermes_home: Path,
                 student_lm=None, reflection_lm=None):
        super().__init__()
        self.predict = dspy.Predict(HermesTaskSignature)
        if self.predict.signature is not None and hasattr(self.predict.signature, 'with_instructions'):
            self.predict.signature = self.predict.signature.with_instructions(base_prompt_template)
        elif self.predict.signature is not None:
            self.base_prompt_template = base_prompt_template
        
        self.hermes_exe = hermes_exe
        self.hermes_home = hermes_home
        self.student_lm = student_lm
        self.reflection_lm = reflection_lm

    @property
    def task_prompt(self):
        if self.predict.signature is not None:
            return getattr(self.predict.signature, 'instructions', "")
        return ""

    def forward(self, task_id: str, pristine_files: str):
        workdir_path = Path(pristine_files)
        
        try:
            task = Task(task_id, workdir=workdir_path)
            if hasattr(task, 'threshold'):
                task.threshold = 0.7
        except TypeError:
            task = Task(task_id, category="", prompt="", check_type="", expected="", threshold=0.7, rubric="", workdir=workdir_path)
        except Exception as exc:
            print(f"[HERMES] Task creation failed for {task_id}: {exc}")
            traceback.print_exc()
            return dspy.Prediction(score=None, score_detail=f"task-creation-error: {exc}", diff="N/A")

        try:
            restored = restore_workspace(task)
        except Exception as exc:
            print(f"[HERMES] restore_workspace failed for {task_id}: {exc}")
            traceback.print_exc()
            return dspy.Prediction(score=None, score_detail=f"restore-error: {exc}", diff="N/A")

        if not restored:
            print(f"[HERMES] restore_workspace returned False for {task_id}")
            return dspy.Prediction(score=None, score_detail="restore-failed", diff="N/A")

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
                            "real_home": str(self.hermes_home),
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


def hermes_metric(gold, pred, trace=None, pred_name=None, pred_trace=None):
    score = pred.score if pred.score is not None else 0.0
    return float(score)