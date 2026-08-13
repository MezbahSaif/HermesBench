# dataset_case4.py
# Builds and freezes the train/val/test split for Case 4.

import hashlib, random
from pathlib import Path

def get_repo_root():
    current = Path(__file__).resolve()
    # Walk up to find the HermesBench root which contains datasets/variants/tasks/
    for p in [current] + list(current.parents):
        if (p / "datasets" / "variants" / "tasks").is_dir():
            return p
    return current.parent.parent

REPO_ROOT = get_repo_root()
POOL_ROOT = REPO_ROOT / "datasets" / "variants" / "tasks"

if not POOL_ROOT.is_dir():
    raise FileNotFoundError(
        f"Task pool not found at {POOL_ROOT}. "
        "Place the HermesBench repo checkout so that `datasets/variants/tasks/` exists."
    )

REAL_TASK_IDS = sorted(p.name for p in POOL_ROOT.iterdir() if p.is_dir())
if len(REAL_TASK_IDS) != 34:
    raise ValueError(f"Expected 34 task directories, found {len(REAL_TASK_IDS)}.")

# Reproducible split
random.seed(4)
real_copy = REAL_TASK_IDS.copy()
random.shuffle(real_copy)

train_cnt = int(0.40 * len(real_copy))
val_cnt = int(0.20 * len(real_copy))
test_cnt = len(real_copy) - train_cnt - val_cnt

train_ids = real_copy[:train_cnt]
val_ids   = real_copy[train_cnt:train_cnt + val_cnt]
test_ids  = real_copy[train_cnt + val_cnt:]

# Sanity: every ID must exist
for name, ids in [("train", train_ids), ("val", val_ids), ("test", test_ids)]:
    for tid in ids:
        if tid not in REAL_TASK_IDS:
            raise ValueError(f"Task ID '{tid}' in {name} split does not exist.")

# Cross-split disjointness assertions
train_set = set(train_ids)
val_set    = set(val_ids)
test_set   = set(test_ids)
assert not (train_set & val_set), f"train/val overlap: {train_set & val_set}"
assert not (train_set & test_set), f"train/test overlap: {train_set & test_set}"
assert not (val_set & test_set), f"val/test overlap: {val_set & test_set}"

SPLIT = {"train": train_ids, "val": val_ids, "test": test_ids}
OUT = REPO_ROOT / "datasets"

OUT.mkdir(parents=True, exist_ok=True)
for name, ids in SPLIT.items():
    csv_path = OUT / f"case4_{name}.csv"
    with open(csv_path, "w", newline="") as f:
        f.write("task_id\n")
        for tid in ids:
            f.write(tid + "\n")

# Manifest
manifest = {}
for csv_name in ["case4_train.csv", "case4_val.csv", "case4_test.csv"]:
    p = OUT / csv_name
    manifest[csv_name] = hashlib.sha256(p.read_bytes()).hexdigest()

manifest_path = OUT / "SPLIT_MANIFEST.md"
with open(manifest_path, "w") as f:
    f.write("# Case 4 split manifest\n\n")
    for csv_name, h in manifest.items():
        f.write(f"- **{csv_name}**: `{h}`\n")

print("Case 4 split generated and verified against real pool.")