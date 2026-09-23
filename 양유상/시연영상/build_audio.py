"""Join generated Korean narration WAVs and emit a caption timeline."""

from __future__ import annotations

import json
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parent
AUDIO = ROOT / "rendered" / "audio"
MANIFEST = AUDIO / "audio-manifest.json"
PAUSE_SECONDS = 0.55


def timestamp(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02}.{milliseconds:03}"


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    recording_manifest_path = ROOT / "rendered" / "video" / "recording-manifest.json"
    recording_starts: dict[str, float] = {}
    if recording_manifest_path.exists():
        recording = json.loads(recording_manifest_path.read_text(encoding="utf-8-sig"))
        recording_starts = {
            item["id"]: float(item["start_seconds"])
            for item in recording.get("scene_starts", [])
        }
    first = wave.open(str(AUDIO / manifest[0]["file"]), "rb")
    params = first.getparams()
    first.close()
    if params.nchannels != 1 or params.sampwidth != 2:
        raise SystemExit("Narration must be mono 16-bit PCM WAV.")

    output = AUDIO / "narration.wav"
    vtt: list[str] = ["WEBVTT", ""]
    timeline: list[dict[str, object]] = []
    position = 0.0
    with wave.open(str(output), "wb") as writer:
        writer.setparams(params)
        for index, item in enumerate(manifest):
            source = wave.open(str(AUDIO / item["file"]), "rb")
            if source.getparams()[:3] != params[:3]:
                raise SystemExit(f"Audio format mismatch in {item['file']}")
            duration = source.getnframes() / params.framerate
            writer.writeframes(source.readframes(source.getnframes()))
            source.close()
            start = recording_starts.get(item["id"], position)
            end = start + duration
            if index + 1 < len(manifest):
                next_item = manifest[index + 1]
                if next_item["id"] in recording_starts:
                    pause = max(0.0, recording_starts[next_item["id"]] - end)
                else:
                    pause = PAUSE_SECONDS
            else:
                pause = PAUSE_SECONDS if not recording_starts else 0.0
            vtt.extend([
                f"{timestamp(start)} --> {timestamp(end)}",
                item["caption"],
                "",
            ])
            timeline.append({
                "id": item["id"],
                "start_seconds": round(start, 3),
                "speech_seconds": round(duration, 3),
                "pause_seconds": round(pause, 3),
                "scene_seconds": round(duration + pause, 3),
                "caption": item["caption"],
                "narration": item["narration"],
            })
            silence_frames = round(params.framerate * pause)
            writer.writeframes(b"\x00\x00" * silence_frames)
            position = end + pause

    (ROOT / "captions.vtt").write_text("\n".join(vtt), encoding="utf-8")
    (AUDIO / "timeline.json").write_text(
        json.dumps({"duration_seconds": round(position, 3), "scenes": timeline}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"audio": str(output), "duration_seconds": round(position, 3), "scenes": len(timeline)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
