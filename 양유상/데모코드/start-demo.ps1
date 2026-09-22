param([switch]$SkipInstall, [switch]$WithModel, [switch]$WithJev)
$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
Set-Location -LiteralPath $taskRoot
$runtimeDir = Join-Path $taskRoot '.runtime'
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    uv venv .venv --python 3.12
    if ($LASTEXITCODE -ne 0) { throw 'Python environment creation failed' }
}
if (-not $SkipInstall) {
    uv pip install --python .venv\Scripts\python.exe -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency install failed' }
}
docker compose up -d --wait --wait-timeout 300
if ($LASTEXITCODE -ne 0) { throw 'Demo PostgreSQL startup failed' }
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
$owned = @()
foreach ($service in @(@{name='mock';module='gateway.mock_api:app';port=8811}, @{name='gateway';module='gateway.app:app';port=8810})) {
    $occupied = Get-NetTCPConnection -LocalPort $service.port -State Listen -ErrorAction SilentlyContinue
    if ($occupied) {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $($occupied[0].OwningProcess)"
        if (-not $proc.CommandLine.Contains($service.module)) { throw "Port $($service.port) belongs to another process; refusing to reuse it" }
        $owned += @{name=$service.name;pid=$proc.ProcessId;module=$service.module}
        continue
    }
    $started = Start-Process -FilePath $taskPython -ArgumentList @('-m','uvicorn',$service.module,'--host','127.0.0.1','--port',"$($service.port)",'--no-access-log') -WorkingDirectory $taskRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimeDir "$($service.name).out.log") -RedirectStandardError (Join-Path $runtimeDir "$($service.name).err.log") -PassThru
    $owned += @{name=$service.name;pid=$started.Id;module=$service.module}
}
$owned | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtimeDir 'processes.json') -Encoding utf8
$healthy = $false
for ($attempt=0; $attempt -lt 30; $attempt++) {
    try {
        $check = Invoke-RestMethod -Uri 'http://127.0.0.1:8810/health' -TimeoutSec 2
        if ($check.status -eq 'ok') { $healthy=$true; break }
    } catch { Start-Sleep -Milliseconds 500 }
}
if (-not $healthy) { throw 'Gateway health check failed; inspect .runtime logs' }
if ($WithModel) { & (Join-Path $taskRoot 'start-model.ps1') -Backend ollama }
if ($WithJev) { & (Join-Path $taskRoot 'start-jev.ps1') }
Write-Output 'Demo ready: http://127.0.0.1:8810'
Write-Output 'Only synthetic local endpoints are tested. Use -WithModel or start-model.ps1 for the measured 4B local research candidate.'
