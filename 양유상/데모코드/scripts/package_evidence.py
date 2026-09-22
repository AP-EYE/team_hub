"""Export the observed run and source/runtime fingerprints without touching originals."""
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import subprocess
import httpx

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    with httpx.Client(timeout=30, trust_env=False) as client:
        response = client.get('http://127.0.0.1:8810/api/state')
        response.raise_for_status()
        state = response.json()
        report = client.get('http://127.0.0.1:8810/api/report')
        report.raise_for_status()
    latest = state['runs'][0]
    out = ROOT / 'evidence' / 'runs'
    out.mkdir(parents=True, exist_ok=True)
    name = f"{latest['id']}-{latest['mode']}-final"
    (out / f'{name}.json').write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    (out / f'{name}.md').write_text(report.text, encoding='utf-8')
    source = {}
    for folder in ('gateway', 'static', 'scripts', 'tests', 'ml', 'ml_alternative'):
        for path in (ROOT / folder).glob('*'):
            if path.is_file() and path.suffix in ('.py', '.js', '.css', '.html', '.ps1', '.jsonl'):
                source[str(path.relative_to(ROOT)).replace('\\', '/')] = digest(path)
    for path in ROOT.glob('*'):
        if path.is_file() and path.suffix in ('.txt', '.yaml', '.ps1', '.md'):
            source[path.name] = digest(path)
    try:
        image = subprocess.check_output(['docker', 'image', 'inspect', 'postgres:17-alpine', '--format', '{{.Id}}'], text=True, timeout=10).strip()
    except Exception as error:
        image = 'unavailable:' + type(error).__name__
    manifest = {"created_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(), "python": platform.python_version(), "packages": {p: version(p) for p in ('fastapi', 'httpx', 'uvicorn', 'psycopg', 'psycopg-pool')}, "postgres_image_id": image, "run_id": latest['id'], "pending_model_jobs_at_export": state['model']['pending_jobs'], "source_sha256": source, "evidence_scope": "합성 로컬 실행과 해당 소스의 연결. 원본 증거 서명이나 운영 인증 아님."}
    (ROOT / 'evidence' / 'runtime-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({"run_id": latest['id'], "summary": state['summary'], "pending_model_jobs": state['model']['pending_jobs'], "export": str(out / f'{name}.md')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
