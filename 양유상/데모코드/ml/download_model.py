"""Fetch a pinned public model. No API inference, credentials, or user data."""
import hashlib
import json
from pathlib import Path
from huggingface_hub import snapshot_download

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence/model"
versions = json.loads((EVIDENCE / "upstream-versions.json").read_text(encoding="utf-8-sig"))
target = ROOT / "ml/models/Qwen3-0.6B"
snapshot_download(versions["model_id"], revision=versions["model_revision"], local_dir=target,
                  allow_patterns=["*.json", "*.safetensors", "*.txt", "*.jinja", "LICENSE", "README.md"])
files = []
for path in sorted(target.iterdir()):
    if path.is_file():
        h = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
                h.update(chunk)
        files.append({"file": path.name, "bytes": path.stat().st_size, "sha256": h.hexdigest()})
manifest = {**versions, "source": "https://huggingface.co/Qwen/Qwen3-0.6B", "local_path": str(target), "files": files,
            "upstream_method": "https://github.com/TheoLeeCJ/SemIf", "affiliation": "Independent demo; neither Jev nor SemIf runtime", "inference": "local CPU, direct option logits"}
(EVIDENCE / "model-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"downloaded": str(target), "files": len(files), "bytes": sum(x["bytes"] for x in files)}, ensure_ascii=False))
