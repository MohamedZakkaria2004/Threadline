param([switch]$Seed, [switch]$Test)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Run setup.ps1 first.' }
if ($Test) { & $pythonPath -m pytest -q; exit $LASTEXITCODE }
if ($Seed) { & $pythonPath -m scripts.seed; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }
& $pythonPath -m app
exit $LASTEXITCODE
