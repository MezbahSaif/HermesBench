# Case 1 (other_run replica) - run all 5 rounds.
# Requirements: LM Studio running with qwen/qwen3.5-9b on 127.0.0.1:1234.
# Round 1 starts fresh; rounds 2-5 resume (retryable rows are replaced in place).
# Results land in Case1_Qwen\runs\case1_run\.
$ErrorActionPreference = "Stop"
$Py = Join-Path $PSScriptRoot "..\..\.venv\Scripts\python.exe"
Set-Location -LiteralPath $PSScriptRoot

if (-not (Test-Path $Py)) { throw "venv python not found: $Py" }

& $Py benchmark\run_benchmark.py --config config\config.yaml --dataset datasets\variants\round_1.csv --round 1 --arm both --run-id case1_run --limit 8
if ($LASTEXITCODE -ne 0) { throw "round 1 failed (exit $LASTEXITCODE)" }

foreach ($r in 2..5) {
    & $Py benchmark\run_benchmark.py --config config\config.yaml --dataset datasets\variants\round_$r.csv --round $r --arm both --run-id case1_run --limit 8 --resume
    if ($LASTEXITCODE -ne 0) { throw "round $r failed (exit $LASTEXITCODE)" }
}

Write-Host "Case 1 complete. Metrics: Case1_Qwen\runs\case1_run\metrics.csv (expect 80 rows)"