# run_gepa.py
import argparse
import json
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
case4_dir = repo_root / "case4"
if not case4_dir.is_dir():
    case4_dir = repo_root / "Case4_Ornith"
if str(case4_dir) not in sys.path:
    sys.path.insert(0, str(case4_dir))

from case4.hermes_task_module import HermesTaskModule, hermes_metric, LMStudioLM
from benchmark.config_loader import detect_hermes

def load_examples_from_csv(csv_path):
    examples = []
    with open(csv_path, newline="") as f:
        f.readline()
        for line in f:
            tid = line.strip()
            if not tid: continue
            pristine = str(repo_root / "datasets" / "variants" / "tasks" / tid / "work")
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
    reflection_cfg = case4_cfg.get("reflection_model", {})
    dataset_cfg = case4_cfg.get("dataset", {})

    student_lm = LMStudioLM(
        model=f"openai/{student_cfg.get('model_name', 'ornith-1.0-9b')}",
        api_base=student_cfg.get("base_url", "http://127.0.0.1:1234/v1"),
        api_key=student_cfg.get("api_key", "sk-lm-studio"),
    )

    dspy.configure(lm=student_lm)

    reflection_lm = None
    if reflection_cfg:
        reflection_lm = LMStudioLM(
            model=f"openai/{reflection_cfg.get('model_name', 'ornith-1.0-9b')}",
            api_base=reflection_cfg.get("base_url", "http://127.0.0.1:1234/v1"),
            api_key=reflection_cfg.get("api_key", "sk-lm-studio"),
        )

    train_csv = repo_root / dataset_cfg.get("train_csv", "datasets/case4_train.csv")
    val_csv = repo_root / dataset_cfg.get("val_csv", "datasets/case4_val.csv")
    
    # Slice trainset to 4 tasks for fast local optimization
    full_trainset = load_examples_from_csv(train_csv)
    trainset = full_trainset[:4]
    
    valset = load_examples_from_csv(val_csv)[:2] if Path(val_csv).exists() else []
    print(f"[run_gepa] Optimizing over {len(trainset)} training tasks and {len(valset)} validation tasks")

    meta_path = repo_root / "datasets" / "case4_tasks.json"
    task_meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    print(f"[run_gepa] loaded metadata for {len(task_meta)} tasks")

    detected = detect_hermes()
    if detected:
        hermes_exe = Path(detected[0])
        hermes_real_home = Path(detected[1])
        print(f"[run_gepa] hermes exe: {hermes_exe}")
        print(f"[run_gepa] hermes real home: {hermes_real_home}")
    else:
        hermes_exe = repo_root / "hermes.exe" if (repo_root / "hermes.exe").exists() else Path(sys.executable).parent / "hermes.exe"
        hermes_real_home = repo_root
    
    module = HermesTaskModule(
        base_prompt_template=case4_cfg.get("base_prompt_template", ""),
        hermes_exe=hermes_exe,
        hermes_home=repo_root / "datasets" / "variants" / "tasks",
        hermes_real_home=hermes_real_home,
        student_lm=student_lm,
        reflection_lm=reflection_lm,
        task_meta=task_meta
    )

    gepa_cfg = case4_cfg.get("gepa", {})
    
    try:
        max_calls = gepa_cfg.get("max_metric_calls")
        log_dir = str(repo_root / "runs" / args.run_id / "gepa")
        gepa_optim = dspy.GEPA(metric=hermes_metric,
                               auto=None if max_calls else gepa_cfg.get("auto", "light"),
                               reflection_lm=reflection_lm,
                               max_metric_calls=int(max_calls) if max_calls else None,
                               num_threads=int(gepa_cfg.get("num_threads", 1)),
                               log_dir=log_dir,
                               track_stats=True)
        print(f"[run_gepa] GEPA num_threads={gepa_optim.num_threads}")
        print(f"[run_gepa] checkpoints -> {log_dir} (rerun this same command to resume from the last checkpoint)")
        optimized_program = gepa_optim.compile(student=module, trainset=trainset, valset=valset)
        
        best_prompt = optimized_program.task_prompt
        with open(f"{args.run_id}_best_prompt.txt", "w") as f:
            f.write(str(best_prompt))
        print(f"GEPA finished. Best prompt saved to {args.run_id}_best_prompt.txt")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()