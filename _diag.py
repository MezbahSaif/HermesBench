import subprocess, os, json, sys, time
from pathlib import Path
import pandas as pd

df = pd.read_csv("datasets/variants/round_1_se.csv", dtype=str)
r = df[df.task_id == "bug_fix_text_offbyone"].iloc[0]
prompt = r["prompt"]
workdir = Path("datasets/variants/tasks/bug_fix_text_offbyone/work")
print("prompt len", len(prompt))
home = Path("runs/thesis_run/homes/treatment_home")
cmd = [r"G:\Hermes\hermes-agent\venv\Scripts\hermes.exe", "-z", prompt,
       "--usage-file", "G:/HermesBench/_diag_usage.json"]
env = os.environ.copy()
env["HERMES_HOME"] = str(home)
env["PYTHONIOENCODING"] = "utf-8"
t0 = time.time()
try:
    p = subprocess.run(cmd, cwd=str(workdir), env=env,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=180)
    print("exited in %.1fs code=%s" % (time.time() - t0, p.returncode))
    print("STDOUT tail:", (p.stdout or "")[-1200:])
    print("STDERR tail:", (p.stderr or "")[-400:])
except subprocess.TimeoutExpired as e:
    print("TIMEOUT at 180s (%.1fs elapsed)" % (time.time() - t0))
    print("STDOUT tail:", (e.stdout or "")[-1200:] if e.stdout else "")
    print("STDERR tail:", (e.stderr or "")[-400:] if e.stderr else "")
print("usage exists?", Path("G:/HermesBench/_diag_usage.json").exists())