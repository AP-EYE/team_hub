"""Technical and simple semantic smoke, separate from the frozen KO96 dataset."""
import json
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    {'id': 'dev-health', 'text': '저는 알레르기 진단을 받았고 약을 복용합니다.', 'field_path': 'clinical.note', 'description': '가상 개인의 진료 기록', 'expected': 'HEALTH'},
    {'id': 'dev-general', 'text': '규칙적인 산책은 건강에 도움이 될 수 있습니다.', 'field_path': 'article.body', 'description': '특정 개인을 다루지 않는 공개 일반 안내', 'expected': 'OTHER'},
    {'id': 'dev-unknown', 'text': '', 'field_path': 'x', 'description': '', 'expected': 'UNKNOWN'},
]


def main():
    rows = []
    with httpx.Client(timeout=180, trust_env=False) as client:
        for case in CASES:
            response = client.post('http://127.0.0.1:8814/classify', json={**{k: case[k] for k in ('text', 'field_path', 'description')}, 'method': 'semif'})
            response.raise_for_status()
            result = response.json()
            rows.append({'case': case, 'result': result, 'correct': result['label'] == case['expected']})
            (ROOT / 'evidence/jev/smoke-additional.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps({'id': case['id'], 'label': result['label'], 'correct': rows[-1]['correct'], 'latency_ms': result['latency_ms']}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
