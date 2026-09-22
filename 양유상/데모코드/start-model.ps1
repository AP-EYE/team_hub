param([ValidateSet('ollama','direct')][string]$Backend='ollama')
$ErrorActionPreference='Stop'
$taskRoot=$PSScriptRoot
$runtimeDir=Join-Path $taskRoot '.runtime'
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
if ($Backend -eq 'ollama') {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $taskRoot 'ml_alternative\start-ollama.ps1')
    if ($LASTEXITCODE -ne 0) { throw 'Isolated Ollama startup failed' }
    $taskPython=Join-Path $taskRoot '.venv\Scripts\python.exe'
    $module='ml_alternative.worker'
    $port=8813
    $env:OLLAMA_HOST='http://127.0.0.1:11437'
    $env:DEMO_CLASSIFIER_MODEL='qwen3:4b-q4_K_M'
} else {
    $taskPython=Join-Path $taskRoot '.venv-model\Scripts\python.exe'
    $module='ml.worker'
    $port=8812
}
if (-not (Test-Path -LiteralPath $taskPython -PathType Leaf)) { throw "Model dependencies are missing; see docs/model-evaluation.md or docs/model-alternative.md" }
$occupied=Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if ($occupied) {
    $process=Get-CimInstance Win32_Process -Filter "ProcessId = $($occupied[0].OwningProcess)"
    if (-not $process.CommandLine.Contains($module)) { throw "Port $port belongs to another process; refusing to reuse it" }
} else {
    $process=Start-Process -FilePath $taskPython -ArgumentList @('-m',$module,'--port',"$port") -WorkingDirectory $taskRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimeDir "$Backend-model.out.log") -RedirectStandardError (Join-Path $runtimeDir "$Backend-model.err.log") -PassThru
}
$registeredPid = if ($process.Id) { $process.Id } else { $process.ProcessId }
@{backend=$Backend;pid=$registeredPid;module=$module;port=$port} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtimeDir "$Backend-model-process.json") -Encoding utf8
$ready=$false
for ($attempt=0; $attempt -lt 60; $attempt++) {
    try {
        $health=Invoke-RestMethod -Uri "http://127.0.0.1:$port/health" -TimeoutSec 3
        if ($health.status -eq 'ready') { $ready=$true;break }
    } catch { Start-Sleep -Milliseconds 500 }
}
if (-not $ready) { throw 'Model worker not ready; inspect its log and model installation' }
@{backend=$Backend;selection_scope='Research candidate only; outputs require review';model=$health.model} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtimeDir 'model-selection.json') -Encoding utf8
Write-Output "Local model ready: $($health.model) ($Backend). Gateway default updated."
