"""Three predeclared information-ablation demos; separate from KO96 accuracy."""
from datetime import datetime, timezone
import json
from pathlib import Path
import httpx

from .engine import input_state

ROOT = Path(__file__).resolve().parents[1]
INPUT = {'field_path': 'document.id', 'description': '가상 회원의 여권번호를 저장하는 필드',
         'text': 'SYNTHETIC-ID-TOKEN'}
EXPECTED = {'full': 'GOVERNMENT_ID', 'schema_only': 'GOVERNMENT_ID', 'value_only': 'UNKNOWN'}


def main():
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    destination = ROOT / 'evidence/jev' / f'input-modes-{stamp}.jsonl'
    with destination.open('x', encoding='utf-8') as output, httpx.Client(timeout=240, trust_env=False) as client:
        for mode, expected in EXPECTED.items():
            submitted = {**INPUT, 'input_mode': mode, 'method': 'semif'}
            response = client.post('http://127.0.0.1:8810/api/jev/classify', json=submitted)
            record = {'at': datetime.now(timezone.utc).isoformat(), 'input_mode': mode,
                      'submitted_to_loopback_gateway': submitted,
                      'model_input_after_mode_filter': input_state(**INPUT, input_mode=mode),
                      'expected_for_this_separate_demo': expected, 'http_status': response.status_code,
                      'response': response.json()}
            record['matches_expected'] = response.is_success and record['response'].get('label') == expected
            output.write(json.dumps(record, ensure_ascii=False) + '\n')
            output.flush()
            print(json.dumps({'mode': mode, 'http_status': response.status_code,
                              'expected': expected, 'label': record['response'].get('label'),
                              'matches_expected': record['matches_expected'],
                              'latency_ms': record['response'].get('latency_ms')}, ensure_ascii=False), flush=True)
            response.raise_for_status()
    print(str(destination), flush=True)


if __name__ == '__main__':
    main()
