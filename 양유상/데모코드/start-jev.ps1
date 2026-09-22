param()
$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
Set-Location -LiteralPath $taskRoot
$taskRuntime = Join-Path $taskRoot '.runtime'
$taskPython = Join-Path $taskRoot '.venv-jev\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Run the setup procedure in docs/korean-jev-demo.md first.' }
& (Join-Path $taskRoot 'ml_alternative\start-ollama.ps1')
$listener = Get-NetTCPConnection -LocalPort 8814 -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    $existing = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener[0].OwningProcess)"
    if ($existing.CommandLine -notlike '*-m ml_jev.worker*') { throw '8814 belongs to another process' }
    Invoke-RestMethod 'http://127.0.0.1:8814/health' | Select-Object status,model,backend
    return
}
$started = Start-Process -FilePath $taskPython -ArgumentList @('-X','utf8','-m','ml_jev.worker','--port','8814') -WorkingDirectory $taskRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskRuntime 'jev-worker.out.log') -RedirectStandardError (Join-Path $taskRuntime 'jev-worker.err.log') -PassThru
@{pid=$started.Id;module='ml_jev.worker';port=8814} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskRuntime 'jev-process.json') -Encoding utf8
Write-Output 'Starting actual SemIf CPU worker on localhost:8814. Inspect .runtime/jev-worker.out.log for ready state.'
