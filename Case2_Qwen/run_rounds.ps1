# Case 2 (tier_run replica) - run all 5 rounds (6 tasks/round: 2 Repeat + 3 Variant + 1 New).
# Requirements: LM Studio running with qwen/qwen3.5-9b on 127.0.0.1:1234.
# Round 1 starts fresh; rounds 2-5 resume. Results land in Case2_Qwen\runs\case2_run\.
$ErrorActionPreference = "Stop"
$Py = Join-Path $PSScriptRoot "..\..\.venv\Scripts\python.exe"
Set-Location -LiteralPath $PSScriptRoot

if (-not (Test-Path $Py)) { throw "venv python not found: $Py" }

& $Py benchmark\run_benchmark.py --config config\config.yaml --dataset datasets\variants\tier_round_1.csv --round 1 --arm both --run-id case2_run --limit 6
if ($LASTEXITCODE -ne 0) { throw "round 1 failed (exit $LASTEXITCODE)" }

foreach ($r in 2..5) {
    & $Py benchmark\run_benchmark.py --config config\config.yaml --dataset datasets\variants\tier_round_$r.csv --round $r --arm both --run-id case2_run --limit 6 --resume
    if ($LASTEXITCODE -ne 0) { throw "round $r failed (exit $LASTEXITCODE)" }
}

Write-Host "Case 2 complete. Metrics: Case2_Qwen\runs\case2_run\metrics.csv (expect 60 rows)"