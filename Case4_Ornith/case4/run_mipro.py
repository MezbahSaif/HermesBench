# run_mipro.py
# Case 4B driver – non‑reflective optimizer (MIPROv2) on a single PC.
import argparse
import os
import sys
from pathlib import Path

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

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    case4_cfg = cfg.get("case4", {})
    student_model_cfg = case4_cfg.get("student_model", {})
    reflection_model_cfg = case4_cfg.get("reflection_model", {})
    dataset_cfg = case4_cfg.get("dataset", {})
    train_csv = dataset_cfg.get("train_csv", "datasets/case4_train.csv")
    val_csv = dataset_cfg.get("val_csv", "datasets/case4_val.csv")

    # Student LM
    student_lm = dspy.LM(
        model=f"openai/{student_model_cfg.get('model_name', 'ornith-1.0-9b')}",
        api_base=student_model_cfg.get("base_url", "http://127.0.0.1:1234/v1"),
        api_key=student_model_cfg.get("api_key", "sk-lm-studio"),
    )

    # Reflection LM (MIPROv2 also uses a reflection model for scoring candidates)
    reflection_lm = None
    if reflection_model_cfg:
        reflection_lm = dspy.LM(
            model=f"openai/{reflection_model_cfg.get('model_name', 'ornith-1.0-9b')}",
            api_base=reflection_model_cfg.get("base_url", "http://127.0.0.1:1234/v1"),
            api_key=reflection_model_cfg.get("api_key", "sk-lm-studio"),
        )

    trainset = load_examples_from_csv(train_csv)
    valset = load_examples_from_csv(val_csv) if Path(val_csv).exists() else []

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
                              student_lm=student_lm,          # NEW
                              reflection_lm=reflection_lm)      # NEW

    mipro_cfg = case4_cfg.get("mipro", {})
    max_metric_calls = mipro_cfg.get("max_metric_calls", 150)  # real MIPROv2 param

    # MIPROv2 API (real DSPy):
    #   optimizer = dspy.MIPROv2(metric=..., auto="light", num_candidates=6, max_metric_calls=150, ...)
    #   optimized_program = optimizer.compile(student=module, trainset=trainset, valset=valset)
    try:
        mipro_optim = dspy.MIPROv2(
            metric=hermes_metric,
            auto=mipro_cfg.get("auto", "light"),
            num_candidates=mipro_cfg.get("num_candidates", 6),
            max_metric_calls=max_metric_calls,
        )
        optimized_program = mipro_optim.compile(
            student=module,
            trainset=trainset,
            valset=valset,
        )

        best_prompt = optimized_program.task_prompt
        with open(f"{args.run_id}_best_prompt.txt", "w") as f:
            f.write(best_prompt)

        print(f"MIPROv2 finished. Best prompt saved to {args.run_id}_best_prompt.txt")
        print(f"MIPROv2 max_metric_calls={max_metric_calls}, auto={mipro_cfg.get('auto')}, "
              f"num_candidates={mipro_cfg.get('num_candidates')}")

    except Exception as e:
        print(f"MIPROv2 error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()