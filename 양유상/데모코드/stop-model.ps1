[CmdletBinding(SupportsShouldProcess=$true)]
param()
$ErrorActionPreference='Stop'
$taskRoot=$PSScriptRoot
foreach ($backend in @('direct','ollama')) {
    $record=Join-Path $taskRoot ".runtime\$backend-model-process.json"
    if (-not (Test-Path -LiteralPath $record)) { continue }
    $owned=Get-Content -LiteralPath $record -Raw | ConvertFrom-Json
    $process=Get-CimInstance Win32_Process -Filter "ProcessId = $($owned.pid)" -ErrorAction SilentlyContinue
    if ($process -and $process.CommandLine.Contains($owned.module)) {
        $children=Get-CimInstance Win32_Process -Filter "ParentProcessId = $($owned.pid)" -ErrorAction SilentlyContinue
        foreach ($child in $children) {
            if ($child.CommandLine.Contains($owned.module) -and $PSCmdlet.ShouldProcess("PID $($child.ProcessId)",$owned.module)) { Stop-Process -Id $child.ProcessId -ErrorAction SilentlyContinue }
        }
        if ($PSCmdlet.ShouldProcess("PID $($owned.pid)",$owned.module)) { Stop-Process -Id $owned.pid -ErrorAction SilentlyContinue }
    }
}
$ollamaPidFile=Join-Path $taskRoot 'ml_alternative\ollama.pid'
if (Test-Path -LiteralPath $ollamaPidFile) {
    $ownedOllamaPid=[int](Get-Content -LiteralPath $ollamaPidFile -Raw).Trim()
    $listener=Get-NetTCPConnection -LocalPort 11437 -State Listen -ErrorAction SilentlyContinue
    $process=Get-CimInstance Win32_Process -Filter "ProcessId = $ownedOllamaPid" -ErrorAction SilentlyContinue
    if ($listener -and $listener[0].OwningProcess -eq $ownedOllamaPid -and $process.CommandLine -match 'ollama.*serve') {
        if ($PSCmdlet.ShouldProcess("PID $ownedOllamaPid on port 11437",'Stop this demo isolated Ollama')) { Stop-Process -Id $ownedOllamaPid }
    }
}
Write-Output 'Only registered demo model workers and the owned port-11437 server were considered. Model files retained.'
