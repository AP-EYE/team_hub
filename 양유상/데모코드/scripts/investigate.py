"""Reconstruct an observed exposure from previously stored records, without replay."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gateway import store

ROOT = Path(__file__).resolve().parents[1]


def investigate(run_id=None, actor='bob'):
    with store.connect() as conn:
        if run_id:
            run = conn.execute('SELECT * FROM runs WHERE id=%s', (run_id,)).fetchone()
        else:
            run = conn.execute("SELECT * FROM runs WHERE mode='vulnerable' AND status='completed' AND id NOT LIKE 'manual-%%' ORDER BY created_at DESC LIMIT 1").fetchone()
        if not run:
            raise ValueError('No stored completed vulnerable run found')
        findings = conn.execute("SELECT id,payload FROM findings WHERE run_id=%s AND payload->>'actor'=%s AND payload->>'verdict'='confirmed' ORDER BY id", (run['id'], actor)).fetchall()
        event_ids = sorted({i for row in findings for i in row['payload']['evidence_ids']})
        events = conn.execute('SELECT id,created_at,payload,sha256 FROM events WHERE id=ANY(%s) ORDER BY id', (event_ids,)).fetchall()
        subjects = conn.execute('''SELECT tenant,namespace,subject_id,array_agg(DISTINCT canonical ORDER BY canonical) AS fields,array_agg(DISTINCT path ORDER BY path) AS endpoints,array_agg(DISTINCT event_id ORDER BY event_id) AS event_ids FROM observations WHERE run_id=%s AND actor=%s AND confirmed=true GROUP BY tenant,namespace,subject_id ORDER BY tenant,subject_id''', (run['id'], actor)).fetchall()
        model = conn.execute('SELECT id,event_id,payload FROM model_results WHERE event_id=ANY(%s) ORDER BY id', (event_ids,)).fetchall()
    return {"source": "stored_postgresql_records_only", "network_replay": False, "run": {**run, "created_at": run['created_at'].isoformat()}, "actor": actor, "confirmed_responses": len(events), "observed_subjects": len(subjects), "subjects": subjects, "events": [{"id": r['id'], "created_at": r['created_at'].isoformat(), **r['payload'], "integrity_ok": store.checksum(r['payload']) == r['sha256']} for r in events], "findings": [{"id": r['id'], **r['payload']} for r in findings], "stored_model_candidates": [{"event_id": r['event_id'], **r['payload']} for r in model], "limitations": ["지정한 실행·요청자가 받은 관측 응답만 분석", "현재 로그에 없는 요청·우회 접근·이전 사고는 복원하지 못함", "마스킹한 값의 원문 복원 불가", "기록의 hash는 서명/외부원본 보존을 대체하지 않음", "AI 분류는 기술적 후보이며 법적 식별·침해 여부 확정 아님", "이 보고서는 SQL 집계와 템플릿이며 LLM이 작성했다고 주장하지 않음"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run')
    parser.add_argument('--actor', default='bob', choices=['alice', 'bob', 'admin', 'mallory', 'anonymous'])
    args = parser.parse_args()
    report = investigate(args.run, args.actor)
    out = ROOT / 'evidence' / 'investigations'
    out.mkdir(parents=True, exist_ok=True)
    filename = report['run']['id'] + '-' + args.actor
    (out / (filename + '.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# 저장 로그 기반 노출 범위 조사', '', f"- 실행: {report['run']['id']}", f"- 대상 요청자: {args.actor}", f"- 확인된 비인가 응답: {report['confirmed_responses']}건", f"- 관측 정보주체: {report['observed_subjects']}명(테넌트/회원 체계 포함 중복 제거)", '- 재전송 없이 기존 PostgreSQL 기록만 읽었습니다.', '', '| 정보주체 | 함께 관측된 항목 | 엔드포인트 | 증거 ID |', '|---|---|---|---|']
    for subject in report['subjects']:
        lines.append(f"| {subject['tenant']}:{subject['subject_id']} | {', '.join(subject['fields'])} | {', '.join(subject['endpoints'])} | {subject['event_ids']} |")
    lines += ['', '## 저장된 AI 분류 후보', '', '```json', json.dumps(report['stored_model_candidates'], ensure_ascii=False, indent=2), '```', '', '## 한계', ''] + ['- ' + note for note in report['limitations']]
    (out / (filename + '.md')).write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({"source": report['source'], "network_replay": False, "responses": report['confirmed_responses'], "subjects": report['observed_subjects'], "report": str(out / (filename + '.md'))}, ensure_ascii=False))
    store.close()


if __name__ == '__main__':
    main()
