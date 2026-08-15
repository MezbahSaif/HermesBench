"""Ad-hoc verification for bug_fix_scheduling_wrong_compare fix."""
import sys, os

sys.path.insert(0, "G:/HermesBench/datasets/variants/tasks/bug_fix_scheduling_wrong_compare/work")
from main import Shift, is_overlap, merge_shifts, total_hours as th

errs = []
# 1. touching intervals overlap (<= semantics)
if not is_overlap(Shift("A",9,10), Shift("B",10,11)): errs.append("touching not overlap")
# 2. merge all-touching into one shift [9..12]
m = merge_shifts([Shift("A",9,10), Shift("B",10,11), Shift("C",11,12)])
if len(m) != 1 or m[0].start != 9 or m[0].end != 12: errs.append(f"merge [9-12] got {m}")
# 3. non-touching stay separate + total_hours=4
m2 = merge_shifts([Shift("A",8,10), Shift("B",15,17)])
if len(m2) != 2 or th(m2) != 4: errs.append(f"non-touching expected [2,4] got {len(m2)},{th(m2)}")
# 4. overlapping merge
m3 = merge_shifts([Shift("A",8,10), Shift("B",9,11)])
if len(m3) != 1 or m3[0].start != 8 or m3[0].end != 11: errs.append(f"overlap got {m3}")
# 5. empty input
if merge_shifts([]) != []: errs.append("empty not handled")

pristine = open("G:/HermesBench/datasets/variants/tasks/bug_fix_scheduling_wrong_compare/pristine/main.py").read()
work = open("G:/HermesBench/datasets/variants/tasks/bug_fix_scheduling_wrong_compare/work/main.py").read()
if pristine != work: errs.append("file mismatch with pristine")

print("AD-HOC VERIFY:" if not errs else "FAILS:")
for e in errs: print(f"  {e}")
if not errs:
    print("\nALL CHECKS PASSED")
else:
    print(f"\n{len(errs)} error(s)")
