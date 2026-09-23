"""Mux the recorded browser video with the synchronized Korean narration."""

from __future__ import annotations

import subprocess
from pathlib import Path

import imageio_ffmpeg


ROOT = Path(__file__).resolve().parent
VIDEO = ROOT / "rendered" / "video" / "AP-EYE-kickoff-demo.webm"
AUDIO = ROOT / "rendered" / "audio" / "narration.wav"
OUTPUT = ROOT / "rendered" / "video" / "AP-EYE-kickoff-demo.mp4"


def main() -> None:
    for source in (VIDEO, AUDIO):
        if not source.is_file():
            raise SystemExit(f"Missing input file: {source}")
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(VIDEO),
        "-i",
        str(AUDIO),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "22",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(OUTPUT),
    ]
    subprocess.run(command, check=True)
    print(f"Created {OUTPUT} ({OUTPUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
