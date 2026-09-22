param([ValidateSet('vulnerable','fixed')][string]$Mode='vulnerable')
$ErrorActionPreference='Stop'
$result = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8810/api/demo/run' -ContentType 'application/json' -Body (@{mode=$Mode} | ConvertTo-Json)
$evidenceDir = Join-Path $PSScriptRoot 'evidence\runs'
New-Item -ItemType Directory -Path $evidenceDir -Force | Out-Null
$state = Invoke-RestMethod -Uri 'http://127.0.0.1:8810/api/state'
$state | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath (Join-Path $evidenceDir "$($result.run_id)-$Mode.json") -Encoding utf8
Invoke-WebRequest -Uri 'http://127.0.0.1:8810/api/report' -OutFile (Join-Path $evidenceDir "$($result.run_id)-$Mode.md")
$result
$state.summary
