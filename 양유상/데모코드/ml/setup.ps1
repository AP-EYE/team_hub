$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
uv venv .venv-model --python 3.12
if ($LASTEXITCODE -ne 0) { throw 'venv creation failed' }
uv pip install --python .venv-model/Scripts/python.exe torch==2.14.0 --index-url https://download.pytorch.org/whl/cpu
if ($LASTEXITCODE -ne 0) { throw 'CPU PyTorch installation failed' }
uv pip install --python .venv-model/Scripts/python.exe -r requirements-model.txt
if ($LASTEXITCODE -ne 0) { throw 'Model dependency installation failed' }
& .venv-model/Scripts/python.exe -m ml.download_model
if ($LASTEXITCODE -ne 0) { throw 'Pinned model download failed' }
