"""Measure model labels on stored live demo responses, preserving errors."""
import json
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {'bola_consult': 'HEALTH', 'general_info': 'OTHER', 'general_consult': 'OTHER'}


def main():
    response = httpx.get('http://127.0.0.1:8810/api/state', timeout=30, trust_env=False)
    response.raise_for_status()
    state = response.json()
    model_by_event = {r['event_id']: r['result'] for r in state['model']['event_results']}
    rows = []
    for event in state['events']:
        if event['case_id'] not in EXPECTED or event['status_code'] != 200:
            continue
        result = model_by_event.get(event['id'], {})
        rows.append({"event_id": event['id'], "case_id": event['case_id'], "path": event['path'], "expected": EXPECTED[event['case_id']], "actual": result.get('label'), "correct": result.get('label') == EXPECTED[event['case_id']], "source": result.get('source'), "model": result.get('model'), "latency_ms": result.get('latency_ms'), "candidate_only": result.get('status') == 'needs_review'})
    complete = len(rows) == 3 and all(r['actual'] for r in rows)
    correct = sum(r['correct'] for r in rows)
    report = {"status": 'MEASURED' if complete else 'INCOMPLETE', "run_id": state['runs'][0]['id'], "count": len(rows), "correct": correct, "classification_errors": [r['case_id'] for r in rows if not r['correct']], "rows": rows, "scope": "동일 데모의 실제 응답 3건과 API 맥락. 24건 작성자 평가와 별도로 측정하며 독립 통계 평가라고 주장하지 않음.", "interpretation": "오답도 원본 유지. 인가 판단에는 사용하지 않아 공개 안내를 취약점으로 만들지 않음."}
    (ROOT / 'evidence/live-classification-validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
