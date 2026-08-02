# =============================================================================
# HermesBench — environment verifier for the teammate machine
# Run once after cloning:
#   powershell -ExecutionPolicy Bypass -File .\verify_setup.ps1
# Creates the venv + installs requirements on first run (takes a few
# minutes), then checks: Python, venv, config, Hermes install, LM Studio
# server, dataset files, task fixtures (catches files dropped by git/zip),
# and finally runs the benchmark's own --dry-run.
# The project toolchain (venv + base python) is kept on the project drive;
# components resolved from the C: drive are flagged as WARN.
# =============================================================================
param([switch]$SkipSetup)

$ErrorActionPreference = "Continue"
$root = $PSScriptRoot
Set-Location $root
$results = New-Object System.Collections.Generic.List[string]

function Report([string]$kind, [string]$msg) {
    $color = switch ($kind) { "OK" { "Green" } "WARN" { "Yellow" } "FAIL" { "Red" } default { "Gray" } }
    Write-Host ("[{0}] {1}" -f $kind, $msg) -ForegroundColor $color
    $script:results.Add($kind)
}

Write-Host ("=" * 70)
Write-Host "HermesBench environment verification"
Write-Host "Project: $root"
Write-Host ("=" * 70)

# ---- 1. Python ------------------------------------------------------------
$pyCmd = $null
foreach ($candidate in @("py -3.13", "py", "python")) {
    $cmd, $arg = $candidate.Split(" ", 2)
    try {
        $v = & $cmd $arg --version 2>&1
        if ($LASTEXITCODE -eq 0 -and "$v" -match "Python 3\.1[1-9]") { $pyCmd = $candidate; break }
    } catch { }
}
$pyParts = @()
if ($pyCmd) { $pyParts = @($pyCmd -split " ", 2) }
if ($pyCmd) {
    $pyVer = if ($pyParts.Count -gt 1) { & $pyParts[0] $pyParts[1] --version 2>&1 } else { & $pyParts[0] --version 2>&1 }
    Report "OK" "Python found: $($pyVer -join ' ')"
} else {
    Report "FAIL" "Python 3.11+ not found. Install from https://python.org (tick 'Add to PATH')."
    exit 1
}

# ---- 2. venv + requirements ------------------------------------------------
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    if ($SkipSetup) { Report "FAIL" ".venv missing (run without -SkipSetup to create it)"; exit 1 }
    Write-Host "[...] creating .venv (one time, ~1 min)..."
    if ($pyParts.Count -gt 1) { & $pyParts[0] $pyParts[1] -m venv (Join-Path $root ".venv") }
    else { & $pyParts[0] -m venv (Join-Path $root ".venv") }
    if (-not (Test-Path $venvPy)) { Report "FAIL" "venv creation failed"; exit 1 }
    Report "OK" ".venv created"
    Write-Host "[...] installing requirements (one time, ~2-5 min)..."
    & $venvPy -m pip install -r (Join-Path $root "requirements.txt")
    if ($LASTEXITCODE -ne 0) { Report "FAIL" "pip install failed"; exit 1 }
} else {
    Report "OK" ".venv exists"
}
foreach ($mod in @("pandas", "scipy", "streamlit", "yaml", "matplotlib", "openpyxl")) {
    & $venvPy -c "import $mod" 2>$null
    if ($LASTEXITCODE -ne 0) {
        if ($SkipSetup) { Report "FAIL" "package '$mod' missing (run without -SkipSetup to install)"; exit 1 }
        Write-Host "[...] installing missing package: $mod ..."
        & $venvPy -m pip install -r (Join-Path $root "requirements.txt")
        break
    }
}
Report "OK" "requirements installed"

# ---- 2b. venv base python must not live on the C: drive --------------------
$venvCfg = Get-Content (Join-Path $root ".venv\pyvenv.cfg") -ErrorAction SilentlyContinue
$venvHome = ($venvCfg | Where-Object { $_ -match "^home\s*=" }) -replace "^home\s*=\s*", ""
if ($venvHome -and $venvHome -match "^C:\\") {
    Report "WARN" ".venv base python is on C: ($venvHome) - delete .venv and re-run so it is rebuilt from a python on the project drive"
} elseif ($venvHome) {
    Report "OK" ".venv base python on $($venvHome.Substring(0, 2)): $venvHome"
}

# ---- 3. config file --------------------------------------------------------
if (Test-Path (Join-Path $root "config\config.yaml")) { Report "OK" "config\config.yaml found" }
else { Report "FAIL" "config\config.yaml missing"; exit 1 }

# ---- 4. Hermes install (resolved through the benchmark's own config loader) -
$hermesResolve = @'
import sys
sys.path.insert(0, sys.argv[1])
from pathlib import Path
from benchmark.config_loader import load_config
c = load_config(Path(sys.argv[1]) / 'config' / 'config.yaml')
h = c.get('hermes', {})
print(h.get('executable', ''))
'@
$hermesExe = ""
try {
    $hermesOut = @(& $venvPy -c $hermesResolve $root |
        Where-Object { $_.Trim() -and $_ -notmatch "^\[config\]" })
    if ($hermesOut.Count -gt 0) { $hermesExe = $hermesOut[0].Trim() }
} catch { }
if ($hermesExe -and (Test-Path $hermesExe)) {
    Report "OK" "Hermes found: $hermesExe"
    if ($hermesExe -match "^C:\\") { Report "WARN" "Hermes executable is on the C: drive ($hermesExe) - works, but the toolchain is not fully on the project drive" }
} else {
    $hermesOnPath = Get-Command hermes -ErrorAction SilentlyContinue
    if ($hermesOnPath) { Report "OK" "Hermes found on PATH: $($hermesOnPath.Source)" }
    else {
        Report "FAIL" "Hermes Agent not found. Install it (its exe should land under %LOCALAPPDATA%\hermes\), then re-run."
        exit 1
    }
}

# ---- 5. LM Studio server (needed for REAL runs, not for dry-run) -----------
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:1234/v1/models" -TimeoutSec 5 -UseBasicParsing
    if ($r.StatusCode -eq 200) { Report "OK" "LM Studio server reachable on 127.0.0.1:1234" }
    else { Report "WARN" "LM Studio server returned HTTP $($r.StatusCode)" }
} catch {
    Report "WARN" "LM Studio server NOT reachable on 127.0.0.1:1234 - start LM Studio + server before real runs"
}

# ---- 6. experiment dataset files ------------------------------------------
$missingCsv = @()
for ($r = 1; $r -le 5; $r++) {
    if (-not (Test-Path (Join-Path $root "datasets\variants\round_${r}_se.csv"))) { $missingCsv += "round_${r}_se.csv" }
}
if ($missingCsv.Count -eq 0) { Report "OK" "All 5 round CSVs present" }
else { Report "FAIL" "Missing round CSVs: $($missingCsv -join ', ')" }

# ---- 7. task fixtures (work/ + pristine/) ----------------------------------
$badFixtures = @()
$variants = Get-ChildItem (Join-Path $root "datasets\variants\tasks") -Directory -ErrorAction SilentlyContinue
if (-not $variants) { Report "FAIL" "datasets\variants\tasks\ is empty - fixtures were dropped in transfer"; exit 1 }
foreach ($v in $variants) {
    $work = @(Get-ChildItem (Join-Path $v.FullName "work") -Recurse -File -ErrorAction SilentlyContinue)
    $pris = @(Get-ChildItem (Join-Path $v.FullName "pristine") -Recurse -File -ErrorAction SilentlyContinue)
    if ($work.Count -eq 0 -or $pris.Count -eq 0) { $badFixtures += $v.Name }
}
if ($badFixtures.Count -eq 0) { Report "OK" "All $($variants.Count) variant fixtures present (work + pristine, with files)" }
else { Report "FAIL" "Fixtures incomplete for: $($badFixtures -join ', ') - re-copy the project (empty dirs/files were dropped)" }

# ---- 8. v1 dataset note (not part of the experiment) -----------------------
$v1Missing = @()
Get-ChildItem (Join-Path $root "datasets\tasks") -Directory -ErrorAction SilentlyContinue | ForEach-Object {
    if (-not (Test-Path (Join-Path $_.FullName "work"))) { $v1Missing += $_.Name }
}
if ($v1Missing.Count -gt 0) {
    Report "WARN" "v1 dataset: $($v1Missing.Count) work dirs missing (git drops empty dirs). Not needed for the experiment - only if you ever run the default dataset."
}

# ---- 9. benchmark's own dry-run --------------------------------------------
Write-Host ""
Write-Host "[...] running the benchmark's own --dry-run (round 1 dataset)..."
& $venvPy (Join-Path $root "benchmark\run_benchmark.py") --dataset "datasets\variants\round_1_se.csv" --dry-run
if ($LASTEXITCODE -ne 0) { Report "FAIL" "--dry-run exited with code $LASTEXITCODE" }
else { Report "OK" "--dry-run passed" }

# ---- 10. summary -----------------------------------------------------------
Write-Host ""
Write-Host ("=" * 70)
$fails = @($results | Where-Object { $_ -eq "FAIL" }).Count
$warns = @($results | Where-Object { $_ -eq "WARN" }).Count
if ($fails -eq 0) {
    Write-Host "RESULT: PASS ($fails failures, $warns warnings)" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next: start LM Studio + model server, then run round 1:"
    Write-Host "  .\.venv\Scripts\python benchmark\run_benchmark.py --dataset datasets\variants\round_1_se.csv --round 1 --arm both --run-id thesis_run"
    exit 0
} else {
    Write-Host "RESULT: FAIL - $fails failing check(s) above, $warns warnings" -ForegroundColor Red
    exit 1
}
