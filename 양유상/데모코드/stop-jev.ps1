param([switch]$WhatIf)
$ErrorActionPreference = 'Stop'
$path = Join-Path $PSScriptRoot '.runtime\jev-process.json'
if (-not (Test-Path -LiteralPath $path)) { return }
$record = Get-Content -LiteralPath $path | ConvertFrom-Json
$listener = Get-NetTCPConnection -LocalPort 8814 -State Listen -ErrorAction SilentlyContinue
$candidates = @(Get-CimInstance Win32_Process | Where-Object {($_.ProcessId -eq $record.pid -or $_.ParentProcessId -eq $record.pid) -and $_.CommandLine -like '*-m ml_jev.worker*'})
foreach ($process in $candidates) {
    if ($WhatIf) { Write-Output "Would stop SemIf worker PID $($process.ProcessId)" }
    else { Stop-Process -Id $process.ProcessId -ErrorAction SilentlyContinue }
}
