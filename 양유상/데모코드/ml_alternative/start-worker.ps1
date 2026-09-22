param([int]$Port = 8813, [string]$OllamaUrl = 'http://127.0.0.1:11437')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$env:OLLAMA_HOST = $OllamaUrl
Set-Location -LiteralPath $projectRoot
& $python -m ml_alternative.worker --port $Port
