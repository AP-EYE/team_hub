"""Copy already-present public runtime/weights into this demo; preserve source files."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    result = hashlib.sha256()
    with path.open('rb') as file:
        while data := file.read(8 * 1024 * 1024):
            result.update(data)
    return result.hexdigest()


def main():
    config_path = ROOT / 'ml_alternative/local-runtime.json'
    config = json.loads(config_path.read_text(encoding='utf-8-sig'))
    source_runtime = Path(config['ollama_executable']).parent
    source_models = Path(config['model_directory'])
    runtime = ROOT / '.runtime/ollama-runtime'
    models = ROOT / '.runtime/ollama-models'
    if source_runtime.resolve() != runtime.resolve():
        shutil.copytree(source_runtime, runtime, dirs_exist_ok=True)
    records = []
    for tag in ('1.7b-q4_K_M', '4b-q4_K_M'):
        relative = Path('manifests/registry.ollama.ai/library/qwen3') / tag
        original = source_models / relative
        manifest = json.loads(original.read_text(encoding='utf-8-sig'))
        destination = models / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if original.resolve() != destination.resolve():
            shutil.copy2(original, destination)
        for layer in [manifest['config'], *manifest['layers']]:
            digest = layer['digest'].split(':')[1]
            src = source_models / 'blobs' / ('sha256-' + digest)
            dst = models / 'blobs' / src.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.resolve() != dst.resolve() and not dst.exists():
                shutil.copy2(src, dst)
            if dst.stat().st_size != layer['size'] or sha(dst) != digest:
                raise RuntimeError('Copied model blob does not match its content digest')
        records.append({"model": 'qwen3:' + tag, "manifest_sha256": sha(destination), "blob_digest_verified": True})
    config.update(ollama_executable=str(runtime / 'ollama.exe'), model_directory=str(models), note='Project-local copy of public runtime and evaluated model blobs. Original runtime/service/model files were preserved. Weights excluded from source ZIP.')
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
    evidence = {"runtime_exe_sha256": sha(runtime / 'ollama.exe'), "models": records, "original_files_modified": False, "location": str(ROOT / '.runtime')}
    (ROOT / 'evidence/model-alternative/project-local-runtime.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    print(json.dumps(evidence))


if __name__ == '__main__':
    main()
