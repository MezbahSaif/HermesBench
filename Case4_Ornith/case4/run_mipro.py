# run_mipro.py
import argparse
import sys
from pathlib import Path
import yaml
import dspy

def get_repo_root():
    current = Path(__file__).resolve()
    for p in [current] + list(current.parents):
        if (p / "benchmark").is_dir() and (p / "datasets").is_dir():
            return p
    return current.parent.parent

repo_root = get_repo_root()
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from case4.hermes_task_module import HermesTaskModule, hermes_metric

def load_examples_from_csv(csv_path):
    examples = []
    with open(csv_path, newline="") as f:
        f.readline()
        for line in f:
            tid = line.strip()
            if not tid: continue
            pristine = str(repo_root / "datasets" / "variants" / "tasks" / tid)
            example = dspy.Example(task_id=tid, pristine_files=pristine).with_inputs('task_id', 'pristine_files')
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
    dataset_cfg = case4_cfg.get("dataset", {})

    student_lm = dspy.LM(
        model=f"openai/{student_cfg.get('model_name', 'ornith-1.0-9b')}",
        api_base=student_cfg.get("base_url", "http://127.0.0.1:1234/v1"),
        api_key=student_cfg.get("api_key", "sk-lm-studio"),
    )

    dspy.configure(lm=student_lm)

    train_csv = repo_root / dataset_cfg.get("train_csv", "datasets/case4_train.csv")
    val_csv = repo_root / dataset_cfg.get("val_csv", "datasets/case4_val.csv")
    
    trainset = load_examples_from_csv(train_csv)
    valset = load_examples_from_csv(val_csv) if Path(val_csv).exists() else []

    hermes_exe = repo_root / "hermes.exe" if (repo_root / "hermes.exe").exists() else Path(sys.executable).parent / "hermes.exe"
    
    module = HermesTaskModule(
        base_prompt_template=case4_cfg.get("base_prompt_template", ""),
        hermes_exe=hermes_exe,
        hermes_home=repo_root / "datasets" / "variants" / "tasks",
        student_lm=student_lm
    )

    mipro_cfg = case4_cfg.get("mipro", {})
    try:
        mipro_optim = dspy.MIPROv2(
            metric=hermes_metric,
            auto=mipro_cfg.get("auto", "light"),
            num_candidates=mipro_cfg.get("num_candidates", 6)
        )
        optimized_program = mipro_optim.compile(student=module, trainset=trainset, valset=valset)
        
        best_prompt = optimized_program.task_prompt
        with open(f"{args.run_id}_best_prompt.txt", "w") as f:
            f.write(str(best_prompt))
        print(f"MIPROv2 finished. Best prompt saved to {args.run_id}_best_prompt.txt")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()