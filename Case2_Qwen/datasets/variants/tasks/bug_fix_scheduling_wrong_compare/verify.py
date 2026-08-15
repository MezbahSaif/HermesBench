"""Ad-hoc verification: fixed work/main.py should match pristine/main.py."""
import sys, os

# Add work directory to path so we can import the module
WORK_DIR = os.path.join('work')
sys.path.insert(0, WORK_DIR)

from main import Shift, is_overlap, merge_shifts, total_hours as th

errors = []

# 1. is_overlap: touching intervals should be overlapping (<= semantics)
if is_overlap(Shift('A', 9, 10), Shift('B', 10, 11)) != True:
    errors.append('FAIL: touching shifts not detected as overlapping')

if is_overlap(Shift('A', 8, 10), Shift('B', 10, 12)) != True:
    errors.append('FAIL: truly overlapping shifts not detected')

# 2. merge_shifts: with <= overlap detection, touching should merge into one
shifts = [Shift('A', 9, 10), Shift('B', 10, 11), Shift('C', 11, 12)]
merged = merge_shifts(shifts)
if len(merged) != 1 or merged[0].start != 9 or merged[0].end != 12:
    errors.append(f'FAIL: expected 1 merged shift [9,12], got {merged}')

# 3. Non-touching shifts stay separate
shifts2 = [Shift('A', 8, 10), Shift('B', 15, 17)]
merged2 = merge_shifts(shifts2)
if len(merged2) != 2 or th(merged2) != 4:
    errors.append(f'FAIL: non-touching shifts should stay separate')

# 4. Truly overlapping merges correctly
shifts3 = [Shift('A', 8, 10), Shift('B', 9, 11)]
merged3 = merge_shifts(shifts3)
if len(merged3) != 1 or merged3[0].start != 8 or merged3[0].end != 11:
    errors.append(f'FAIL: overlapping merge failed')

# 5. Empty input
try:
    assert merge_shifts([]) == []
except AssertionError as e:
    errors.append(f'FAIL: empty input {e}')

if errors:
    print('FAILED:')
    for err in errors:
        print(err)
else:
    # 6. Verify file matches pristine exactly (content + whitespace)
    PRISTINE_PATH = os.path.join('pristine', 'main.py')
    work_path = os.path.join(WORK_DIR, 'main.py')
    
    with open(PRISTINE_PATH) as f:
        pristine_text = f.read()
    
    with open(work_path) as f:
        work_text = f.read()
    
    if pristine_text == work_text:
        print('PASS: work/main.py matches pristine/main.py exactly')
    else:
        errors.append('FAIL: file content differs from pristine')

if errors:
    print(f'\n{len(errors)} error(s) found.')
else:
    print('\nALL CHECKS PASSED')
