#!/usr/bin/env python3
"""Ad-hoc verification of cli.py against the task spec."""
import subprocess, os

CWD = r"G:\HermesBench\datasets\variants\tasks\cli_sales\work"


def run(*args):
    return subprocess.run(
        ["python", "cli.py"] + list(args), capture_output=True, text=True, cwd=CWD
    )


# 1. Default: all items sorted revenue desc then name asc
p = run("--input", "orders.csv")
out = p.stdout.strip().split("\n")

# Parse output - each line is ITEM:REVENUE (2 fields separated by single colon)
lines = [r.split(":")[0] for r in out if r and r.strip()]
revs = [(float(r.split(":")[1]), r) for r in out if r and r.strip()]

# Widget: 1.5*2 + 1.5*5 = 10.5, Gadget: 2*2=4, Doohickey: 0.5*1=0.5
assert lines == ["Widget", "Gadget", "Doohickey"], f"default order fail: {lines}"
assert revs[0] == (10.5, "Widget") and revs[1] == (4.0, "Gadget"), f"rev order fail: {revs}"

# 2. --top 1 picks highest revenue
p = run("--input", "orders.csv", "--top", "1")
assert p.stdout.strip() == "Widget:10.50", f"--top 1 fail: {p.stdout!r}"

# 3. --city Berlin filters Munich rows out (only Berlin items)
p = run("--input", "orders.csv", "--city", "Berlin")
out_b = [r.split(":")[0] for r in p.stdout.strip().split("\n")]
assert out_b == ["Widget", "Gadget", "Doohickey"], f"berlin items fail: {out_b}"

# 4. --top 2 + Berlin: Gadget(4) > Widget(3) -> top 2 = Gadget, Widget
p = run("--input", "orders.csv", "--city", "Berlin", "--top", "2")
out_bt = [r.split(":")[0] for r in p.stdout.strip().split("\n")]
assert out_bt == ["Gadget", "Widget"], f"berlin+top2 fail: {out_bt}"

# 5. Tie-breaking by item name ascending (Beta=10, Gamma=5, Alpha=3)
tmp = os.path.join(r"C:\Users\pc\AppData\Local\Temp", "test_cli.csv")
with open(tmp, "w") as fout:
    fout.write(
        "date,item,price,qty,city\n"
        "2024-01-01,Beta,5.0,2,CityA\n"
        "2024-01-01,Gamma,5.0,1,CityA\n"
        "2024-01-01,Alpha,3.0,1,CityA\n"
    )
p = run("--input", tmp, "--top", "3")
out_ties = [r.split(":")[0] for r in p.stdout.strip().split("\n")]
assert out_ties == ["Beta", "Gamma", "Alpha"], f"ties fail: {out_ties}"
os.unlink(tmp)

# 6. Non-existent city -> empty output
p = run("--input", "orders.csv", "--city", "Nowhere")
assert p.stdout.strip() == "", f"empty city fail: {p.stdout!r}"

print("ALL CHECKS PASSED (6/6)")
