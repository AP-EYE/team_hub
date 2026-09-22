param([switch]$KeepModels)
$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$pidFile = Join-Path $taskRoot '.runtime\processes.json'
if (Test-Path -LiteralPath $pidFile) {
    foreach ($owned in (Get-Content -LiteralPath $pidFile -Raw | ConvertFrom-Json)) {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $($owned.pid)" -ErrorAction SilentlyContinue
        if ($proc -and $proc.CommandLine.Contains($owned.module)) {
            $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $($owned.pid)" -ErrorAction SilentlyContinue
            foreach ($child in $children) {
                if ($child.CommandLine.Contains($owned.module)) { Stop-Process -Id $child.ProcessId -ErrorAction SilentlyContinue }
            }
            Stop-Process -Id $owned.pid -ErrorAction SilentlyContinue
        }
    }
}
Set-Location -LiteralPath $taskRoot
docker compose stop
if (-not $KeepModels) {
    & (Join-Path $taskRoot 'stop-model.ps1')
    & (Join-Path $taskRoot 'stop-jev.ps1')
}
Write-Output 'Demo services stopped. Database volume, model weights and evidence retained.'
