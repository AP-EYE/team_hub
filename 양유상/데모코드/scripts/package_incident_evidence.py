"""Record the final incident demo's measured results and source fingerprints."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8-sig'))


def main():
    offline = read('evidence/incident-offline-proof.json')
    tests = read('evidence/incident-tests.json')
    ui = read('evidence/incident-ui/ui-validation.json')
    restore = read('evidence/incident-offline-process.json')
    files = []
    for folder in ('gateway', 'static', 'tests', 'scripts', 'docs'):
        files += [p for p in (ROOT / folder).rglob('*') if p.is_file() and p.suffix in ('.py', '.js', '.css', '.html', '.md', '.ps1')]
    files += [ROOT / 'README.md', ROOT / 'requirements.txt', ROOT / 'compose.yaml']
    manifest = {'created_at': datetime.now(timezone.utc).isoformat(), 'run_id': offline['run_id'],
        'basis': 'Stored synthetic requests, observed offline analysis, independent tests and screenshots.',
        'source_sha256': {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)},
        'evidence_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in
            ('evidence/incident-tests.json', 'evidence/incident-offline-proof.json', 'evidence/incident-ui/ui-validation.json', 'evidence/incident-offline-process.json')},
        'full_summary': offline['full_summary'], 'metadata_summary': offline['metadata_summary'],
        'offline_checks': {'passed': offline['passed'], 'total': offline['total']},
        'ui_checks': {'passed': sum(check['passed'] for check in ui['checks']), 'total': len(ui['checks'])},
        'restored_synthetic_api': restore.get('restored'),
        'prior_evidence': 'Earlier 16-scenario authorization results and source ZIP remain historical evidence; not rerun as 60 new checks.'}
    (ROOT / 'evidence/incident-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'run_id': manifest['run_id'], 'source_files': len(files), 'full_summary': manifest['full_summary'], 'offline_checks': manifest['offline_checks'], 'ui_checks': manifest['ui_checks'], 'restored': manifest['restored_synthetic_api']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
