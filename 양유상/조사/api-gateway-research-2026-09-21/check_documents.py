from pathlib import Path
import re
import json
import hashlib
import importlib.util

root = Path(__file__).resolve().parent
errors = []
results = []
yaml_available = importlib.util.find_spec('yaml') is not None
if yaml_available:
    import yaml

for p in sorted(root.glob('*.md')):
    text = p.read_text(encoding='utf-8')
    if text.count('```') % 2:
        errors.append(f'{p.name}: unbalanced code fences')
    if '\ufffd' in text:
        errors.append(f'{p.name}: replacement character')
    if re.search(r'turn\d+(?:search|view)\d+|\ue200|\ue201', text):
        errors.append(f'{p.name}: raw web citation token')
    for label, target in re.findall(r'\[([^\]]+)\]\(([^)]+)\)', text):
        if not target.startswith(('https://', 'http://', '#')):
            dest = p.parent / target.split('#')[0]
            if not dest.exists():
                errors.append(f'{p.name}: missing local link {target}')
    for language, body in re.findall(r'```([^\n]*)\n(.*?)\n```', text, re.S):
        if language == 'json':
            try:
                json.loads(body)
            except Exception as exc:
                errors.append(f'{p.name}: invalid JSON: {exc}')
        if language == 'yaml' and yaml_available:
            try:
                yaml.safe_load(body)
            except Exception as exc:
                errors.append(f'{p.name}: invalid YAML: {exc}')
    results.append({'file': p.name, 'bytes': p.stat().st_size, 'lines': len(text.splitlines()), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})

manifest = json.loads((root / 'evidence/attachments/manifest.json').read_text(encoding='utf-8'))
for item in manifest:
    if hashlib.sha256(Path(item['source']).read_bytes()).hexdigest() != item['sha256']:
        errors.append(f'Original attachment changed: {item["id"]}')

report = {'documents': results, 'yaml_parser_available': yaml_available, 'errors': errors, 'original_attachments_unchanged': not any('Original' in e for e in errors), 'scope': 'Local document consistency only; no product runtime or performance test; Mermaid not rendered.'}
(root / 'evidence/document-checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
raise SystemExit(bool(errors))
