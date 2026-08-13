# hermes_task_module.py
import sys
import importlib
from pathlib import Path
import dspy

_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

_hermes_interface = None
try:
    _hermes_interface = importlib.import_module("benchmark.hermes_interface")
except ImportError:
    _hermes_interface = None

if _hermes_interface is not None:
    HermesInterface = getattr(_hermes_interface, "HermesInterface")
    _restore_workspace = getattr(_hermes_interface, "restore_workspace", None)
    if _restore_workspace is None:
        def restore_workspace(task):
            return True
    else:
        restore_workspace = _restore_workspace
else:
    class HermesInterface:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("benchmark.hermes_interface is unavailable")

    def restore_workspace(task):
        return True

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
        # Declare a predictor so DSPy optimizers have a target to mutate
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
        task = Task(task_id, workdir=Path(pristine_files).parent, category="", prompt="", 
                    check_type="", expected="", threshold=0.0, rubric="")

        restored = restore_workspace(task)
        if not restored:
            return dspy.Prediction(score=None, score_detail="restore-failed", diff="N/A")

        workdir = Path(pristine_files).parent
        prompt_text = ""
        for possible in ["problem.json", "task.json", "prompt.json",
                         "problem.txt", "task.txt", "prompt.txt",
                         "problem.md", "task.md", "prompt.md"]:
            p = workdir / possible
            if p.is_file():
                try:
                    prompt_text = p.read_text(encoding="utf-8")[:500]
                    break
                except Exception:
                    continue
        if not prompt_text.strip():
            prompt_text = "Implement a solution for the given coding task."

        # Safe variable substitution
        rendered_prompt = self.task_prompt.replace("{task_id}", task_id).replace("{prompt}", prompt_text)

        # Ensure Hermes ALWAYS runs using the student LM
        model_str = self.student_lm.model if self.student_lm is not None else ""

        iface: HermesInterface = HermesInterface(
            {"hermes": {"executable": str(self.hermes_exe),
                        "real_home": str(self.hermes_home),
                        "model": model_str,
                        "provider": "",
                        "extra_args": []},
             "benchmark": {"pass_threshold": 0.7}},
            self.hermes_home,
            Path("datasets") / "variants" / "tasks" / task_id
        )

        try:
            if not hasattr(iface, 'run_task'):
                return dspy.Prediction(score=None, score_detail="hermes-interface-missing-run_task", diff="N/A")
            run_task_method = getattr(iface, 'run_task')
            result = run_task_method(rendered_prompt)
        except Exception as exc:
            return dspy.Prediction(score=None, score_detail=f"hermes-execution-error: {exc}", diff="N/A")

        try:
            score, detail = grade(task, result.response, judge=None)
        except Exception as exc:
            score, detail = None, f"grader-error:{type(exc).__name__}"

        passed = bool(score is not None and score >= task.threshold) if score is not None else False

        return dspy.Prediction(
            score=score,
            score_detail=detail if detail else ("passed" if passed else "failed"),
            diff=f"task_{task.task_id}_score_{score}_passed_{passed}"
        )


def hermes_metric(gold, pred, trace=None):
    return {"score": pred.score, "feedback": pred.score_detail}