"""Exercise the gateway's local AI forms without changing demo observations."""
from datetime import datetime, timezone
import json
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    with httpx.Client(base_url='http://127.0.0.1:8810', timeout=120, trust_env=False) as client:
        before = client.get('/api/state').json()
        checks = []
        for field, description, expected in [
            ('customer_no', '응답에 포함된 정보주체의 회원 식별자', 'data_subject.id'),
            ('mobile_no', '회원의 휴대전화번호', 'person.phone'),
        ]:
            response = client.post('/api/mapping/suggest', json={'field_path': field, 'description': description})
            result = response.json()
            checks.append({'case': field, 'status_code': response.status_code, 'expected': expected, 'result': result,
                           'pass': response.status_code == 200 and result.get('canonical_field') == expected and result.get('approved') is False and result.get('approval_status') == 'candidate_requires_review'})
        response = client.post('/api/model/classify', json={'text': 'fictional-member@example.test', 'field_path': 'email', 'description': '합성 회원 연락용 이메일', 'backend': 'ollama'})
        result = response.json()
        checks.append({'case': 'explicit_backend_classify', 'status_code': response.status_code, 'expected': 'CONTACT', 'result': result,
                       'pass': response.status_code == 200 and result.get('label') == 'CONTACT' and result.get('status') == 'needs_review' and result.get('confidence') is None})
        after = client.get('/api/state').json()
        checks.append({'case': 'no_automatic_approval_or_observation_mutation', 'pass': before['mappings'] == after['mappings'] and before['findings'] == after['findings'] and before['events'] == after['events']})
    report = {'created_at': datetime.now(timezone.utc).isoformat(), 'scope': 'Gateway forwarding smoke; synthetic examples, not accuracy benchmark', 'passed': sum(row['pass'] for row in checks), 'count': len(checks), 'checks': checks}
    (ROOT / 'evidence/final-api-smoke.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    if report['passed'] != report['count']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
