# hermes_task_module.py
# DSPy / Hermes bridge for Case 4.
# - Uses dspy.Predict so GEPA/MIPROv2 can mutate the task prompt
# - Calls the real HermesInterface/restore/grade functions
# - The only mutable field the optimizers touch is ``self.task_prompt``
#   inside the Predict signature.

import sys
from pathlib import Path
import dspy

# Ensure the HermesBench repo is on the Python path so we import the real
# helpers regardless of where this package is executed from.
_repo_root = Path(__file__).resolve().parent.parent.parent  # .../HermesBench
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from benchmark.hermes_interface import HermesInterface, restore_workspace
from benchmark.graders import grade
from benchmark.task_loader import Task


class HermesTaskSignature(dspy.Signature):
    """Editable task instruction Hermes receives before solving a coding task."""
    task_prompt: str = dspy.InputField(desc="The instruction text GEPA/MIPRO evolves")
    task_id: str = dspy.InputField()
    pristine_files: str = dspy.InputField(desc="Path or serialized snapshot of the workdir")
    result_summary: str = dspy.OutputField(desc="Free‑text summary of what the agent did")


class HermesTaskModule(dspy.Module):
    def __init__(self, base_prompt_template: str, hermes_exe: Path, hermes_home: Path,
                 student_lm=None, reflection_lm=None):
        super().__init__()
        # Build a dspy.Predict whose single configurable field is the prompt.
        # GEPA/MIPRO will rewrite .signature.instructions (the task_prompt).
        self.predict = dspy.Predict(HermesTaskSignature)
        self.task_prompt = base_prompt_template  # initial value; optimizers will mutate it
        self.hermes_exe = hermes_exe
        self.hermes_home = hermes_home
        self.student_lm = student_lm
        self.reflection_lm = reflection_lm

    def forward(self, task_id: str, pristine_files: str):
        """Execute one task through Hermes and return a dspy.Prediction.

        1. Build a Task object from the task_id.
        2. Restore pristine → work (real restore_workspace).
        3. Render the current task_prompt (the optimizer‑mutated string)
           against the task’s own problem file, then pass it to Hermes.
        4. Invoke hermes.exe via HermesInterface (real subprocess driver).
        5. Grade the response via the real grader.
        6. Return dspy.Prediction(score=..., score_detail=..., diff=...)
        """
        # 1. Build a Task object from the task_id
        task = Task(task_id, workdir=Path(pristine_files).parent)

        # 2. Restore pristine -> work (real function from HermesBench)
        restored = restore_workspace(task)
        if not restored:
            return dspy.Prediction(
                score=None,
                score_detail="restore-failed: workdir could not be restored",
                diff="N/A"
            )

        # 3. Render the prompt from the work directory’s problem file.
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

        # Format the optimizer‑mutated prompt with {task_id} and {prompt}
        rendered_prompt = self.task_prompt.format(task_id=task_id, prompt=prompt_text)

        # 4. Invoke hermes.exe using HermesInterface
        #    Build the config dict – wire student_lm/reflection_lm if given.
        model_str = ""
        provider_str = ""
        if self.student_lm is not None:
            model_str = self.student_lm.model or ""
        if self.reflection_lm is not None:
            # Use reflection_lm for GEPA; fall back to student_lm
            model_str = (self.reflection_lm.model or self.student_lm.model or "") if self.student_lm else ""

        iface = HermesInterface(
            {"hermes": {"executable": str(self.hermes_exe),
                        "real_home": str(self.hermes_home),
                        "model": model_str,
                        "provider": provider_str,
                        "extra_args": []},
             "benchmark": {"pass_threshold": 0.7}},
            self.hermes_home,
            Path("datasets") / "variants" / "tasks" / task_id
        )

        try:
            result = iface.run_task(rendered_prompt)
        except Exception as exc:
            return dspy.Prediction(
                score=None,
                score_detail=f"hermes-execution-error: {exc}",
                diff="N/A"
            )

        # 5. Grade the response via the real grader
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
    """Return feedback text (not just a float) for GEPA.

    The planner/optimizer uses the ``feedback`` string to guide reflective
    updates.  We reuse the ``score_detail`` values already produced by the
    grader (``file_code_exec:banned``, ``test_suite:runner-failed``, etc.).
    """
    return {"score": pred.score, "feedback": pred.score_detail}