$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv-model/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Run the model setup instructions in docs/model-evaluation.md first.' }
Set-Location -LiteralPath $projectRoot
& $pythonPath -m ml.worker --port 8812
