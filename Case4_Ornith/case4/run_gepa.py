# run_gepa.py
import argparse
import os
import sys
from pathlib import Path
import yaml
import dspy

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from case4.hermes_task_module import HermesTaskModule, hermes_metric

def load_examples_from_csv(csv_path):
    examples = []
    with open(csv_path, newline="") as f:
        f.readline()
        for line in f:
            tid = line.strip()
            if not tid: continue
            example = dspy.Example(task_id=tid, pristine_files=f"datasets/variants/tasks/{tid}").with_inputs('task_id', 'pristine_files')
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
    student_cfg = case4_cfg.get("student_model", {})
    reflection_cfg = case4_cfg.get("reflection_model", {})
    dataset_cfg = case4_cfg.get("dataset", {})

    student_lm = dspy.LM(
        model=f"openai/{student_cfg.get('model_name', 'ornith-1.0-9b')}",
        api_base=student_cfg.get("base_url", "http://127.0.0.1:1234/v1"),
        api_key=student_cfg.get("api_key", "sk-lm-studio"),
    )

    # CRITICAL: Configure DSPy global LM
    dspy.configure(lm=student_lm)

    reflection_lm = None
    if reflection_cfg:
        reflection_lm = dspy.LM(
            model=f"openai/{reflection_cfg.get('model_name', 'ornith-1.0-9b')}",
            api_base=reflection_cfg.get("base_url", "http://127.0.0.1:1234/v1"),
            api_key=reflection_cfg.get("api_key", "sk-lm-studio"),
        )

    trainset = load_examples_from_csv(dataset_cfg.get("train_csv"))
    val_csv = dataset_cfg.get("val_csv")
    valset = load_examples_from_csv(val_csv) if Path(val_csv).exists() else []

    repo_root = Path(__file__).resolve().parent.parent
    hermes_exe = repo_root / "hermes.exe" if (repo_root / "hermes.exe").exists() else Path(os.path.expandvars("${LOCALAPPDATA}/hermes/hermes-agent/venv/Scripts/hermes.exe"))
    
    module = HermesTaskModule(
        base_prompt_template=case4_cfg.get("base_prompt_template", ""),
        hermes_exe=hermes_exe,
        hermes_home=repo_root / "datasets" / "variants" / "tasks",
        student_lm=student_lm,
        reflection_lm=reflection_lm
    )

    gepa_cfg = case4_cfg.get("gepa", {})
    use_auto = gepa_cfg.get("auto", "light")
    
    try:
        gepa_optim = dspy.GEPA(metric=hermes_metric, auto=use_auto, reflection_lm=reflection_lm)
        optimized_program = gepa_optim.compile(student=module, trainset=trainset, valset=valset)
        
        best_prompt = optimized_program.task_prompt
        with open(f"{args.run_id}_best_prompt.txt", "w") as f:
            f.write(best_prompt)
        print(f"GEPA finished. Best prompt saved to {args.run_id}_best_prompt.txt")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()