"""Bundle authored source/docs/evidence, excluding virtualenvs, weights and runtime state."""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT.parent / 'api-privacy-gateway-demo-source.zip'
EXCLUDED = {'__pycache__', '.pytest_cache', 'models', '.git', '.runtime'}
EXCLUDED_FILES = {'.evaluation.lock'}
FOLDERS = ['gateway', 'static', 'scripts', 'tests', 'docs', 'ml', 'ml_alternative', 'ml_jev', 'evidence']


def source_files():
    files = [p for p in ROOT.iterdir() if p.is_file() and (p.suffix in ('.txt', '.yaml', '.ps1', '.md') or p.name == '.gitignore')]
    for folder in FOLDERS:
        base = ROOT / folder
        if base.exists():
            files += [p for p in base.rglob('*') if p.is_file()
                      and not any(part in EXCLUDED for part in p.relative_to(base).parts)
                      and p.name not in EXCLUDED_FILES and p.suffix not in ('.log', '.pid', '.pyc', '.lock')]
    # Ship the pinned MIT source, not its Git history, generated package metadata,
    # dependencies, benchmark assets or model weights.
    vendor = ROOT / '.vendor/SemIf'
    files += [vendor / name for name in ('LICENSE', 'README.md', 'pyproject.toml') if (vendor / name).is_file()]
    package = vendor / 'src/semif_phase1'
    if package.exists():
        files += [p for p in package.rglob('*.py') if '__pycache__' not in p.parts]
    # This host-specific config is recreated by prepare_tokenizer on the new PC.
    return sorted(set(files) - {ROOT / 'ml_jev/local-runtime.json'})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', default=TARGET.name, help='ZIP basename placed next to the project')
    args = parser.parse_args()
    if Path(args.name).name != args.name or '/' in args.name or '\\' in args.name or not args.name.endswith('.zip'):
        parser.error('--name must be a ZIP basename without directory components')
    target = ROOT.parent / args.name
    files = source_files()
    with ZipFile(target, 'w', ZIP_DEFLATED) as bundle:
        for path in sorted(files):
            bundle.write(path, 'api-privacy-gateway-demo/' + path.relative_to(ROOT).as_posix())
    with ZipFile(target) as bundle:
        if bundle.testzip() is not None:
            raise RuntimeError('Bundle integrity test failed')
        names = bundle.namelist()
        if any('/.venv' in name or '/models/' in name or '/.runtime/' in name or '/.git/' in name
               or name.endswith('.lock') or '.egg-info/' in name for name in names):
            raise RuntimeError('Unexpected dependency/runtime content in bundle')
        if 'api-privacy-gateway-demo/ml_jev/local-runtime.json' in names:
            raise RuntimeError('Host-specific Jev runtime config must be regenerated')
    print(json.dumps({"archive": str(target), "files": len(files), "bytes": target.stat().st_size, "sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "zip_integrity": "PASS"}))


if __name__ == '__main__':
    main()
