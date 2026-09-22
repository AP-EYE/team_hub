"""Download only the pinned reference tokenizer; reuse existing local GGUF weights."""
import argparse
import hashlib
import json
from pathlib import Path
from huggingface_hub import snapshot_download

ROOT = Path(__file__).resolve().parents[1]
MODEL = 'Qwen/Qwen3-4B'
PINNED_REVISION = '1cfa9a7208912126459214e8b04321603b3df60c'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', default=PINNED_REVISION, help='Explicit Hugging Face tokenizer revision; defaults to the evaluated commit')
    args = parser.parse_args()
    revision = args.revision
    folder = ROOT / '.runtime/jev-tokenizer/Qwen3-4B'
    snapshot_download(MODEL, revision=revision, local_dir=folder,
        allow_patterns=['tokenizer*', 'vocab.json', 'merges.txt', 'config.json', 'generation_config.json', 'LICENSE', 'README.md', 'chat_template*'])
    manifest_path = ROOT / '.runtime/ollama-models/manifests/registry.ollama.ai/library/qwen3/4b-q4_K_M'
    manifest = json.loads(manifest_path.read_text())
    layer = next(row for row in manifest['layers'] if row['mediaType'] == 'application/vnd.ollama.image.model')
    model_file = ROOT / '.runtime/ollama-models/blobs' / layer['digest'].replace(':', '-')
    with model_file.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    assert digest == layer['digest'].split(':')[1] and model_file.stat().st_size == layer['size']
    config = {'model_id': MODEL, 'tokenizer_revision': revision, 'tokenizer_directory': str(folder),
        'gguf': str(model_file), 'gguf_sha256': digest, 'gguf_bytes': model_file.stat().st_size,
        'semif_commit': '1f2dea3e25379f9dfc98cb83c324f00ab5deda37', 'threads': 8, 'max_tokens': 2048,
        'use_extra_bufts': False}
    out = ROOT / 'evidence/jev'
    out.mkdir(parents=True, exist_ok=True)
    (ROOT / 'ml_jev/local-runtime.json').write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
    evidence = {**config, 'tokenizer_files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file()}}
    (out / 'runtime-provenance.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'model': MODEL, 'revision': revision, 'gguf_sha256': digest, 'tokenizer_files': len(evidence['tokenizer_files'])}))


if __name__ == '__main__':
    main()
