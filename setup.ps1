param([string]$PythonExecutable)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if ((-not $PythonExecutable) -and (Get-Command uv -ErrorAction SilentlyContinue)) {
    uv sync --frozen --group dev
} else {
    if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
        if ($PythonExecutable) {
            & $PythonExecutable -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)'
            if ($LASTEXITCODE -ne 0) { throw 'The selected interpreter must be Python 3.12.' }
            & $PythonExecutable -m venv .venv
        } else {
            py -3.12 -m venv .venv
        }
        if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 environment creation failed. Install Python 3.12 or pass -PythonExecutable with its full executable path.' }
    }
    & '.\.venv\Scripts\python.exe' -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)'
    if ($LASTEXITCODE -ne 0) { throw 'The existing .venv must use Python 3.12.' }
    & '.\.venv\Scripts\python.exe' -m ensurepip
    if ($LASTEXITCODE -ne 0) { throw 'pip bootstrap failed.' }
    & '.\.venv\Scripts\python.exe' -m pip install -r requirements.lock.txt
}
if ($LASTEXITCODE -ne 0) { throw 'Dependency setup failed.' }
Write-Output 'Setup complete. Start Ollama, then run .\start.ps1 -Seed.'
