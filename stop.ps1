$ErrorActionPreference = 'Stop'
$port = if ($env:COPILOT_PORT) { [int]$env:COPILOT_PORT } else { 8765 }
$pidFile = Join-Path $PSScriptRoot 'artifacts\server.pid'
if (-not (Test-Path -LiteralPath $pidFile)) { throw 'No Atlas process record found. Stop its terminal with Ctrl+C.' }
$recordedPid = [int](Get-Content -LiteralPath $pidFile)
$connections = Get-NetTCPConnection -LocalAddress '127.0.0.1' -LocalPort $port -State Listen -ErrorAction SilentlyContinue
foreach ($connection in $connections) {
    $serverProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $($connection.OwningProcess)"
    if ($serverProcess.ProcessId -eq $recordedPid -and $serverProcess.CommandLine -match '(?:^|\s)-m\s+app(?:\s|$)') {
        Stop-Process -Id $serverProcess.ProcessId
        Write-Output "Stopped local Atlas server on port $port."
    } else {
        throw "Port $port belongs to a different process; it was not stopped."
    }
}
