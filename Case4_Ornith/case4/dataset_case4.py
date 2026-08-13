# dataset_case4.py
# Builds and freezes the train/val/test split for Case 4.
# Uses the same 34-task pool as build_case3_dataset.py (repo root).
# Random seed 4 (config) ensures reproducible split on both PCs.
# Outputs (relative to the HermesBench repo root):
#   datasets/case4_train.csv, case4_val.csv, case4_test.csv
#   datasets/SPLIT_MANIFEST.md with SHA-256 hashes of the CSVs.
# 
# The script asserts that every task ID in the three CSVs exists in the real
# 34-task pool, so fabricated names (e.g. "refactor_logs") can never appear.
# It also asserts cross-split disjointness (plan §4).
# 
import hashlib, json, pathlib, random, sys
from pathlib import Path

# ---- Resolve the real pool location (one directory up from this package) ----
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent  # .../HermesBench
POOL_ROOT = REPO_ROOT / "datasets" / "variants" / "tasks"   # 34 task dirs

if not POOL_ROOT.is_dir():
    raise FileNotFoundError(
        f"Task pool not found at {POOL_ROOT}. "
        "Place the HermesBench repo checkout so that "
        "`datasets/variants/tasks/` exists."
    )

REAL_TASK_IDS = sorted(p.name for p in POOL_ROOT.iterdir() if p.is_dir())
if len(REAL_TASK_IDS) != 34:
    raise ValueError(
        f"Expected 34 task directories in the pool, found {len(REAL_TASK_IDS)}. "
        "Check that the real repo is checked out and the pool is intact."
    )

# ---- Reproducible split ----
random.seed(4)
real_copy = REAL_TASK_IDS.copy()
random.shuffle(real_copy)

train_cnt = int(0.40 * len(real_copy))
val_cnt = int(0.20 * len(real_copy))
test_cnt = len(real_copy) - train_cnt - val_cnt

train_ids = real_copy[:train_cnt]
val_ids   = real_copy[train_cnt:train_cnt + val_cnt]
test_ids  = real_copy[train_cnt + val_cnt:]

# ---- Sanity: every ID must exist in the real pool ----
for name, ids in [("train", train_ids), ("val", val_ids), ("test", test_ids)]:
    for tid in ids:
        if tid not in REAL_TASK_IDS:
            raise ValueError(
                f"Task ID '{tid}' in {name} split does not exist in the real 34-task pool. "
                "Regenerate the split with the real repo checked out."
            )

# ---- Cross-split disjointness assertions (plan §4) ----
train_set = set(train_ids)
val_set    = set(val_ids)
test_set   = set(test_ids)
assert not (train_set & val_set), f"train/val overlap: {train_set & val_set}"
assert not (train_set & test_set), f"train/test overlap: {train_set & test_set}"
assert not (val_set & test_set), f"val/test overlap: {val_set & test_set}"

SPLIT = {
    "train": train_ids,
    "val":    val_ids,
    "test":   test_ids,
}

OUT = REPO_ROOT / "datasets"   # the repo's datasets folder, shared by all cases

for name, ids in SPLIT.items():
    csv_path = OUT / f"case4_{name}.csv"
    with open(csv_path, "w", newline="") as f:
        f.write("task_id\n")
        for tid in ids:
            f.write(tid + "\n")

# Manifest
manifest = {}
for name, csv_name in [("train", "case4_train.csv"), ("val", "case4_val.csv"), ("test", "case4_test.csv")]:
    p = OUT / csv_name
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    manifest[csv_name] = h

manifest_path = OUT / "SPLIT_MANIFEST.md"
with open(manifest_path, "w") as f:
    f.write("# Case 4 split manifest\n\n")
    for name, h in manifest.items():
        f.write(f"- **{name}**: `{h}`\n")

print("Case 4 split generated and verified against real pool.")
PYEOF