param(
    [string]$OutputDir = (Join-Path $PSScriptRoot 'rendered\audio')
)

$ErrorActionPreference = 'Stop'
$sceneFile = Join-Path $PSScriptRoot 'scenes.json'
$scenes = Get-Content -LiteralPath $sceneFile -Raw -Encoding UTF8 | ConvertFrom-Json
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voices = @($synth.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo })
$voice = $voices | Where-Object { $_.Culture.Name -eq 'ko-KR' } | Select-Object -First 1
if (-not $voice) { throw 'Windows에 ko-KR 음성이 설치되어 있지 않습니다.' }
$synth.SelectVoice($voice.Name)
$synth.Rate = -1
$synth.Volume = 100

$manifest = [System.Collections.Generic.List[object]]::new()
try {
    foreach ($scene in $scenes) {
        $path = Join-Path $OutputDir ($scene.id + '.wav')
        $synth.SetOutputToWaveFile($path)
        $synth.Speak([string]$scene.narration)
        $synth.SetOutputToNull()
        $reader = [System.IO.BinaryReader]::new([System.IO.File]::OpenRead($path))
        try {
            $reader.BaseStream.Position = 24
            $sampleRate = $reader.ReadInt32()
            $reader.BaseStream.Position = 28
            $byteRate = $reader.ReadInt32()
            $reader.BaseStream.Position = 42
            $dataBytes = $reader.ReadInt32()
        }
        finally { $reader.Dispose() }
        $duration = [Math]::Round(($dataBytes / $byteRate), 3)
        $manifest.Add([pscustomobject]@{
            id = $scene.id
            file = [System.IO.Path]::GetFileName($path)
            sample_rate = $sampleRate
            duration_seconds = $duration
            caption = $scene.caption
            narration = $scene.narration
        })
        Write-Output ("{0}: {1:N1}초" -f $scene.id, $duration)
    }
}
finally { $synth.Dispose() }

$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $OutputDir 'audio-manifest.json') -Encoding UTF8
