param(
    [string]$OllamaExecutable = $env:DEMO_OLLAMA_EXECUTABLE,
    [string]$ModelDirectory = $env:DEMO_OLLAMA_MODEL_DIRECTORY,
    [int]$Port = 11437
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$evidenceDirectory = Join-Path $projectRoot 'evidence\model-alternative'
New-Item -ItemType Directory -Path $evidenceDirectory -Force | Out-Null
try {
    $existing = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/version" -TimeoutSec 2
    Write-Output "Existing Ollama at 127.0.0.1:$Port ($($existing.version)); no changes made."
    exit 0
} catch { }
$localConfigurationPath = Join-Path $PSScriptRoot 'local-runtime.json'
if (Test-Path -LiteralPath $localConfigurationPath) {
    $localConfiguration = Get-Content -LiteralPath $localConfigurationPath -Raw | ConvertFrom-Json
    if (-not $OllamaExecutable -and (Test-Path -LiteralPath $localConfiguration.ollama_executable -PathType Leaf)) {
        $OllamaExecutable = $localConfiguration.ollama_executable
    }
    if (-not $ModelDirectory -and (Test-Path -LiteralPath $localConfiguration.model_directory -PathType Container)) {
        $ModelDirectory = $localConfiguration.model_directory
    }
}
if (-not $OllamaExecutable) {
    $OllamaExecutable = (Get-Command ollama -ErrorAction Stop).Source
}
if (-not (Test-Path -LiteralPath $OllamaExecutable -PathType Leaf)) {
    throw "Ollama executable does not exist: $OllamaExecutable"
}
$env:OLLAMA_HOST = "127.0.0.1:$Port"
if ($ModelDirectory) {
    if (-not (Test-Path -LiteralPath $ModelDirectory -PathType Container)) {
        throw "Existing model directory does not exist: $ModelDirectory"
    }
    $env:OLLAMA_MODELS = $ModelDirectory
}
$env:OLLAMA_NO_CLOUD = 'true'
$env:OLLAMA_NOPRUNE = 'true'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$env:OLLAMA_NUM_PARALLEL = '1'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$process = Start-Process -FilePath $OllamaExecutable -ArgumentList 'serve' -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $evidenceDirectory "ollama-$stamp.stdout.log") -RedirectStandardError (Join-Path $evidenceDirectory "ollama-$stamp.stderr.log")
$process.Id | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'ollama.pid')
Write-Output "Started isolated Ollama PID $($process.Id) on 127.0.0.1:$Port. Existing Ollama services are unchanged."
