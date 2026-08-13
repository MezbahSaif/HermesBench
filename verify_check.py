#!/usr/bin/env python
import py_compile, os, sys, hashlib, pathlib, re

files = [
    r'G:\HermesBench\Case4_Ornith\case4\_\_init__.py',
    r'G:\HermesBench\Case4_Ornith\case4\dataset_case4.py',
    r'G:\HermesBench\Case4_Ornith\case4\hermes_task_module.py',
    r'G:\HermesBench\Case4_Ornith\case4\run_gepa.py',
    r'G:\HermesBench\Case4_Ornith\case4\run_mipro.py',
    r'G:\HermesBench\Case4_Ornith\case4\replay_eval.py',
    r'G:\HermesBench\Case4_Ornith\config\config_case4.yaml',
]

print("FILE BY FILE COMPILATION CHECK")
print()

all_ok = True
for f in files:
    try:
        if f.endswith('.yaml'):
            import yaml
            with open(f) as fh:
                yaml.safe_load(fh)
        else:
            py_compile.compile(f, doraise=True)
        print("  OK:", os.path.basename(f))
    except Exception as e:
        print("  ERROR:", os.path.basename(f), "-", str(e)[:50])
        all_ok = False

print()
print("SPLIT HASH VERIFICATION")
print()
repo = pathlib.Path(r'G:\HermesBench\datasets')
for name in ['case4_train.csv', 'case4_val.csv', 'case4_test.csv']:
    p = repo / name
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    print("  " + name + ":", h)

print()
print("Manifest hashes:")
manifest_path = repo / 'SPLIT_MANIFEST.md'
manifest_text = open(manifest_path).read()
for name in ['case4_train.csv', 'case4_val.csv', 'case4_test.csv']:
    m = re.search(r'\*\*' + name + r'\*\*: `([^`]+)`', manifest_text)
    if m:
        manifest_hash = m.group(1)
        actual = hashlib.sha256(open(repo / name, 'rb').read()).hexdigest()
        match = 'MATCH' if actual == manifest_hash else 'MISMATCH'
        print("  " + name + ": manifest=" + manifest_hash[:16] + "... actual=" + actual[:16] + "... " + match)

# Check disjointness
print()
print("Disjointness check:")
task_sets = {}
for name in ['case4_train.csv', 'case4_val.csv', 'case4_test.csv']:
    import csv
    tasks = set()
    with open(repo / name) as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            if row and row[0]:
                tasks.add(row[0])
    task_sets[name] = tasks

is_disjoint = True
names = ['case4_train.csv', 'case4_val.csv', 'case4_test.csv']
for i in range(3):
    for j in range(i+1, 3):
        overlap = task_sets[names[i]] & task_sets[names[j]]
        if overlap:
            print("  OVERLAP between " + names[i] + " and " + names[j] + ": " + str(len(overlap)) + " tasks")
            is_disjoint = False
if is_disjoint:
    print("  All splits are disjoint")

print()
print("Overall compile:", "ALL OK" if all_ok else "SOME ERRORS")