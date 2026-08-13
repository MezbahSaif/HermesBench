# run_gepa.py
# Case 4A driver – reflective optimizer (GEPA) on a single PC.
# Usage:
#   python run_gepa.py --config case4/config_case4.yaml --run-id case4_gepa_run
import argparse
import os
import sys
from pathlib import Path

# Per the folder layout HermesBench/Case4_Ornith/case4/ — two levels up from case4/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml
import dspy
from dspy.lm import LM

from case4.hermes_task_module import HermesTaskModule, hermes_metric


def load_examples_from_csv(csv_path, task_id_field="task_id"):
    """Read a CSV with a task_id column and return a list of dspy.Example."""
    examples = []
    with open(csv_path, newline="") as f:
        header = f.readline()  # skip header
        for line in f:
            tid = line.strip()
            if not tid:
                continue
            # Build a minimal example; the optimizer only needs the id
            # and will call the module forward(task_id, pristine_files)
            example = dspy.Example()
            example.task_id = tid
            example.pristine_files = f"datasets/variants/tasks/{tid}"
            examples.append(example)
    return examples


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    # Load config
    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    # ------------------------------------------------------------------
    # Config paths (case4: block per plan §6)
    # ------------------------------------------------------------------
    case4_cfg = cfg.get("case4", {})
    student_model_cfg = case4_cfg.get("student_model", {})
    reflection_model_cfg = case4_cfg.get("reflection_model", {})
    dataset_cfg = case4_cfg.get("dataset", {})
    train_csv = dataset_cfg.get("train_csv", "datasets/case4_train.csv")
    val_csv = dataset_cfg.get("val_csv", "datasets/case4_val.csv")

    # ------------------------------------------------------------------
    # Configure DSPy LMs (local LM Studio) – student model for GEPA
    # Real DSPy LM signature: dspy.LM(model="openai/<model_name>", api_base=..., api_key=...)
    # CRITICAL: student_lm MUST be used to wire the model into HermesInterface
    # ------------------------------------------------------------------
    student_lm = dspy.LM(
        model=f"openai/{student_model_cfg.get('model_name', 'ornith-1.0-9b')}",
        api_base=student_model_cfg.get("base_url", "http://127.0.0.1:1234/v1"),
        api_key=student_model_cfg.get("api_key", "sk-lm-studio"),
    )

    # Reflection model (used by GEPA for self‑critique)
    reflection_lm = None
    if reflection_model_cfg:
        reflection_lm = dspy.LM(
            model=f"openai/{reflection_model_cfg.get('model_name', 'ornith-1.0-9b')}",
            api_base=reflection_model_cfg.get("base_url", "http://127.0.0.1:1234/v1"),
            api_key=reflection_model_cfg.get("api_key", "sk-lm-studio"),
        )

    # ------------------------------------------------------------------
    # Load the frozen splits
    # ------------------------------------------------------------------
    trainset = load_examples_from_csv(train_csv)
    valset = load_examples_from_csv(val_csv) if Path(val_csv).exists() else []

    # ------------------------------------------------------------------
    # Build the DSPy module – now with dspy.Predict so GEPA has predictors to mutate
    # ------------------------------------------------------------------
    repo_root = Path(__file__).resolve().parent.parent
    hermes_exe = repo_root / "hermes.exe" if (repo_root / "hermes.exe").exists() else Path(
        os.path.expandvars("${LOCALAPPDATA}/hermes/hermes-agent/venv/Scripts/hermes.exe")
    )
    hermes_home = repo_root / "datasets" / "variants" / "tasks"

    base_prompt_template = case4_cfg.get("base_prompt_template",
        "You are Hermes. Solve the following coding task:\nTask ID: {task_id}\nInstruction: {prompt}")

    # Pass student_lm and reflection_lm to HermesTaskModule
    module = HermesTaskModule(base_prompt_template=base_prompt_template,
                              hermes_exe=hermes_exe,
                              hermes_home=hermes_home,
                              student_lm=student_lm,
                              reflection_lm=reflection_lm)

    # ------------------------------------------------------------------
    # Construct GEPA optimizer per REAL DSPy API:
    #   GEPA enforces exactly ONE budget param: auto OR max_metric_calls (not both).
    #   Crate: dspy.GEPA(metric=..., auto="light")  then  .compile(student=module, trainset=trainset, valset=valset)
    # ------------------------------------------------------------------
    gepa_cfg = case4_cfg.get("gepa", {})
    # Use EXACTLY ONE budget strategy:
    #   Option A: auto="light" ( GEPA chooses n=6 rollouts internally)
    #   Option B: max_metric_calls=100 (explicit budget, no auto)
    # Do NOT pass both — DSPy will raise at construction.
    # Here we use auto="light" as the plan intends, which handles its own rollout count.
    use_auto = gepa_cfg.get("auto", "light")
    # Remove max_metric_calls from the constructor when using auto
    gepa_kwargs = dict(
        metric=hermes_metric,
        auto=use_auto,
        reflection_lm=reflection_lm,
    )
    # If the user explicitly set max_metric_calls, we could use that instead,
    # but the plan's config uses auto="light". For safety, we just use auto.
    # If you want explicit budget, set auto=None and pass max_metric_calls alone.

    try:
        # Build GEPA – constructor takes metric, auto, reflection_lm (NOT module/trainset/valset)
        gepa_optim = dspy.GEPA(**gepa_kwargs)
        # Compile the optimizer – this is where reflective updates happen
        # .compile(student=module, trainset=trainset, valset=valset) returns the optimized program
        optimized_program = gepa_optim.compile(
            student=module,
            trainset=trainset,
            valset=valset,
        )
        # Retrieve the best prompt
        best_prompt = optimized_program.task_prompt
        with open(f"{args.run_id}_best_prompt.txt", "w") as f:
            f.write(best_prompt)

        print(f"GEPA finished. Best prompt saved to {args.run_id}_best_prompt.txt")
        print(f"GEPA auto={use_auto}, reflection_lm={'present' if reflection_lm else 'absent'}")

    except Exception as e:
        print(f"GEPA error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()