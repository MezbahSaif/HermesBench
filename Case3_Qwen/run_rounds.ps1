# Case 3 (case3_run replica) - run all 5 rounds (10 tasks/round: 3 Repeat + 5 Variant + 2 New).
# Requirements: LM Studio running with qwen/qwen3.5-9b on 127.0.0.1:1234.
# Round 1 starts fresh; rounds 2-5 resume. Results land in Case3_Qwen\runs\case3_run\.
$ErrorActionPreference = "Stop"
$Py = Join-Path $PSScriptRoot "..\..\.venv\Scripts\python.exe"
Set-Location -LiteralPath $PSScriptRoot

if (-not (Test-Path $Py)) { throw "venv python not found: $Py" }

& $Py benchmark\run_benchmark.py --config config\config.yaml --dataset datasets\variants\tier_round_1.csv --round 1 --arm both --run-id case3_run --limit 10
if ($LASTEXITCODE -ne 0) { throw "round 1 failed (exit $LASTEXITCODE)" }

foreach ($r in 2..5) {
    & $Py benchmark\run_benchmark.py --config config\config.yaml --dataset datasets\variants\tier_round_$r.csv --round $r --arm both --run-id case3_run --limit 10 --resume
    if ($LASTEXITCODE -ne 0) { throw "round $r failed (exit $LASTEXITCODE)" }
}

Write-Host "Case 3 complete. Metrics: Case3_Qwen\runs\case3_run\metrics.csv (expect 100 rows)"