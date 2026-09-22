from pathlib import Path
from html.parser import HTMLParser
import argparse
import hashlib
import json
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'evidence' / 'attachments'
OUT.mkdir(parents=True, exist_ok=True)

parser_args = argparse.ArgumentParser(description='Extract the supplied HTML/PDF source materials.')
parser_args.add_argument(
    '--source-dir',
    type=Path,
    default=ROOT.parent / 'source-materials',
    help='Directory containing the three supplied source files (default: ../source-materials)',
)
SOURCE = parser_args.parse_args().source_dir.resolve()

class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.parts = []
        self.links = []
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip += 1
        if tag in ('p', 'div', 'section', 'tr', 'li', 'br', 'h1', 'h2', 'h3', 'h4'):
            self.parts.append('\n')
        if tag == 'a':
            self.links.extend(v for k, v in attrs if k == 'href')
    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.skip:
            self.skip -= 1
        if tag in ('p', 'div', 'section', 'tr', 'li', 'h1', 'h2', 'h3', 'h4'):
            self.parts.append('\n')
        if tag in ('td', 'th'):
            self.parts.append(' | ')
    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

names = [
    ('proposal', 'BOLABFLA 자동 탐지와 개인정보보호법 기반 노출 영향도 산정.html'),
    ('briefing', '게이트웨이 브리핑.html'),
    ('slides', 'API 인가 취약점 진단 및 개인정보 노출 영향도 산정.pdf'),
]
manifest = []
for key, name in names:
    path = SOURCE / name
    raw = path.read_bytes()
    record = {'id': key, 'source': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    if path.suffix == '.pdf':
        reader = PdfReader(path)
        record['pages'] = len(reader.pages)
        text = '\n\n'.join(f'## PAGE {i+1}\n{page.extract_text()}' for i, page in enumerate(reader.pages))
    else:
        parser = TextParser()
        parser.feed(raw.decode('utf-8-sig'))
        text = '\n'.join(line.strip() for line in ''.join(parser.parts).splitlines() if line.strip())
        record['links'] = parser.links
    (OUT / f'{key}.txt').write_text(text, encoding='utf-8')
    record['text_chars'] = len(text)
    manifest.append(record)
    print(json.dumps(record, ensure_ascii=False))
(OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
