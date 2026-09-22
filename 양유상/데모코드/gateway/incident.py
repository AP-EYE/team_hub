"""Limited retrospective investigation: immutable log reads, never API replay."""
from collections import defaultdict
from datetime import datetime, timezone
import json
import re
from . import store
from .privacy import inspect_payload


# These are known fixture route contracts, not guessed arbitrary-ID replacement.
ROUTES = [
    (r'profile/(private|public|leaky)/([^/]+)', lambda m: f'profile/{m[1]}/{{member_id}}'),
    (r'(consultations|orders|ambiguous)/([^/]+)', lambda m: f'{m[1]}/{{member_id}}'),
    (r'tenants/([^/]+)/profile/([^/]+)', lambda m: 'tenants/{tenant_id}/profile/{member_id}'),
]


def endpoint_key(path):
    for pattern, render in ROUTES:
        match = re.fullmatch(pattern, path)
        if match:
            return render(match)
    return path


def instant(value):
    if value is None or value == '':
        return None
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError('Time filters require a timezone, for example +09:00 or Z')
    return parsed.astimezone(timezone.utc)


def json_date(value):
    return value.isoformat() if isinstance(value, datetime) else value


def requested_target(path):
    if endpoint_key(path) == path:
        return None
    tenant = path.split('/')[1] if path.startswith('tenants/') else 'alpha'
    return f"{tenant}:synthetic-member-v1:{path.split('/')[-1]}"


def subject_keys(body):
    if not isinstance(body, dict):
        return set()
    rows = body.get('records', [body])
    if not isinstance(rows, list):
        return set()
    result = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        identifier = row.get('member_id') or row.get('customer_no')
        if row.get('tenant_id') and identifier:
            result.add((str(row['tenant_id']), 'synthetic-member-v1', str(identifier)))
    return result


def observed_fields(body, key):
    """A derived observation must also exist in the preserved response structure."""
    rows = body.get('records', [body]) if isinstance(body, dict) else []
    fields = set()
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        identifier = row.get('member_id') or row.get('customer_no')
        if (str(row.get('tenant_id')), 'synthetic-member-v1', str(identifier)) == key:
            fields.update(item['canonical'] for item in inspect_payload(row) if item.get('canonical'))
    return fields


def analyze_records(run, events, findings, observations, models, actor='bob', start=None, end=None, capture='full'):
    if capture not in ('full', 'metadata_only'):
        raise ValueError('capture must be full or metadata_only')
    if not isinstance(actor, str) or not actor or len(actor) > 100:
        raise ValueError('actor must be a nonempty account name or all')
    start_at, end_at = instant(start), instant(end)
    if start_at and end_at and start_at > end_at:
        raise ValueError('start must be at or before end')
    full = capture == 'full'
    selected = []
    for row in events:
        if row.get('run_id', row['payload'].get('run_id')) != run['id']:
            continue
        payload, created = row['payload'], instant(row['created_at'])
        if actor != 'all' and payload.get('actor') != actor:
            continue
        if start_at and created < start_at or end_at and created > end_at:
            continue
        selected.append(row)
    selected.sort(key=lambda row: (instant(row['created_at']), row['id']))
    find_by_event, obs_by_event = defaultdict(list), defaultdict(list)
    if full:
        for row in findings:
            payload = row['payload']
            if row.get('run_id', payload.get('run_id')) != run['id']:
                continue
            for event_id in payload.get('evidence_ids', []):
                find_by_event[event_id].append(payload)
        for row in observations:
            if row.get('run_id') == run['id']:
                obs_by_event[row['event_id']].append(row)
    api, people, timeline = {}, {}, []
    confirmed_ids, corrupt_ids, missing_body, valid_ids = set(), [], [], set()
    for row in selected:
        event, event_id = row['payload'], row['id']
        valid = store.checksum(event) == row.get('sha256') if full else None
        status = event.get('status_code')
        success = isinstance(status, int) and 200 <= status < 300
        denied = status in (401, 403)
        body_available = full and 'response_redacted' in event and event['response_redacted'] is not None
        if full and not valid:
            corrupt_ids.append(event_id)
        if full and not body_available:
            missing_body.append(event_id)
        if valid:
            valid_ids.add(event_id)
        policy = event.get('policy', {}) if full and valid else {}
        supported = [f for f in find_by_event[event_id] if f.get('actor') == event.get('actor')]
        verdicts = {f.get('verdict') for f in supported} if valid and body_available else set()
        keys = subject_keys(event['response_redacted']) if valid and body_available and success else set()
        confirmed = (bool(keys) and policy.get('state') == 'approved'
                     and policy.get('expected') in ('deny', 'allow_fields') and verdicts == {'confirmed'})
        verdict = ('confirmed' if confirmed else next(iter(verdicts)) if len(verdicts) == 1 and 'confirmed' not in verdicts else 'needs_review') if full else None
        if confirmed:
            confirmed_ids.add(event_id)
        fields, event_subjects = set(), set()
        if valid and keys:
            for tenant, namespace, subject_id in keys:
                key = f'{tenant}:{namespace}:{subject_id}'
                event_subjects.add(key)
                person = people.setdefault(key, {'subject_key': key, 'tenant': tenant, 'namespace': namespace,
                    'subject_id': subject_id, 'fields': set(), 'confirmed_fields': set(), 'endpoints': set(), 'event_ids': set(), 'confirmed_event_ids': set(), 'actors': set()})
                person['endpoints'].add(event.get('path', ''))
                person['event_ids'].add(event_id)
                person['actors'].add(event.get('actor', 'unknown'))
                if confirmed:
                    person['confirmed_event_ids'].add(event_id)
                present = observed_fields(event['response_redacted'], (tenant, namespace, subject_id))
                for ob in obs_by_event[event_id]:
                    if (ob.get('tenant'), ob.get('namespace'), ob.get('subject_id')) == (tenant, namespace, subject_id) and ob.get('actor') == event.get('actor') and ob.get('canonical') in present:
                        person['fields'].add(ob['canonical'])
                        if confirmed:
                            person['confirmed_fields'].add(ob['canonical'])
                        fields.add(ob['canonical'])
        endpoint = endpoint_key(event.get('path', ''))
        group = api.setdefault((event.get('method', 'UNKNOWN'), endpoint), {'method': event.get('method', 'UNKNOWN'), 'endpoint': endpoint,
            'requests': 0, 'http_success': 0, 'denied': 0, 'other': 0, 'confirmed_policy_requests': 0 if full else None,
            'evidence_ids': [], 'paths': set(), 'requested_targets': set(), 'returned_subject_keys': set(), 'fields': set()})
        group['requests'] += 1
        group['http_success'] += int(success)
        group['denied'] += int(denied)
        group['other'] += int(not success and not denied)
        if full:
            group['confirmed_policy_requests'] += int(confirmed)
        group['evidence_ids'].append(event_id)
        group['paths'].add(event.get('path', ''))
        target = requested_target(event.get('path', ''))
        if target:
            group['requested_targets'].add(target)
        group['returned_subject_keys'].update(event_subjects)
        group['fields'].update(fields)
        timeline.append({'event_id': event_id, 'created_at': json_date(row['created_at']), 'actor': event.get('actor'),
            'actor_tenant': event.get('actor_tenant'), 'method': event.get('method'), 'path': event.get('path'),
            'status_code': status, 'verdict': verdict, 'integrity_ok': valid,
            'response_redacted': event.get('response_redacted') if valid and body_available else None,
            'fields': sorted(fields), 'response_evidence_available': bool(valid and body_available),
            'requested_target': target, 'returned_subject_keys': sorted(event_subjects)})
    def serialize_sets(item):
        return {key: sorted(value) if isinstance(value, set) else value for key, value in item.items()}
    api_calls = [serialize_sets(api[key]) for key in sorted(api)]
    subjects = [serialize_sets(people[key]) for key in sorted(people)]
    summary = {'logged_requests': len(selected), 'api_count': len(api_calls),
        'http_success': sum(a['http_success'] for a in api_calls), 'denied': sum(a['denied'] for a in api_calls),
        'other': sum(a['other'] for a in api_calls), 'confirmed_policy_requests': len(confirmed_ids) if full else None,
        'returned_subjects': len(subjects) if full else None,
        'confirmed_exposure_subjects': sum(bool(s['confirmed_event_ids']) for s in subjects) if full else None}
    coverage_notes = [
        '로그 완전성을 보증하는 독립 자료가 없어 누락률과 전체 호출 횟수는 알 수 없습니다.',
        '반복 호출도 별도 로그 1건으로 셉니다. HTTP 2xx 횟수는 개인정보 조회 인원과 다릅니다.',
        '정규화 경로는 이 데모의 명시된 경로 계약에 한정하며 요청 대상과 실제 반환 대상을 구분합니다.',
        '쿼리 값과 본문 원문은 보존하지 않아 페이지·검색 조건·전체 DB 조회 범위를 복원할 수 없습니다.',
    ]
    if not full:
        coverage_notes.append('응답 본문·저장 판정·필드 관측·AI 결과를 제외한 비교 모드입니다. 원본 로그를 삭제하지 않습니다.')
    if actor == 'all':
        coverage_notes.append('전체 계정 비교는 여러 계정의 관측을 합친 통계입니다. 단일 행위자의 결합 가능성으로 해석할 수 없습니다.')
    if corrupt_ids:
        coverage_notes.append('해시 불일치 이벤트는 메타데이터 기록으로만 표시하고 내용·노출 확인 집계에서 제외했습니다.')
    if missing_body:
        coverage_notes.append('응답 자료가 누락된 이벤트는 반환 정보주체를 확인할 수 없습니다. 알려진 수는 나머지 로그에서 관측한 최소 범위입니다.')
    conclusions = [
        f"선택한 기록에서 {actor}의 요청 {len(selected)}건, API 유형 {len(api_calls)}개를 확인했습니다.",
        f"HTTP 2xx {summary['http_success']}건, 401/403 {summary['denied']}건, 그 밖의 응답 {summary['other']}건입니다.",
    ]
    if full:
        conclusions.append(f"검증 가능한 응답에서 중복 제거 정보주체 {summary['returned_subjects']}개를 관측했고, 저장된 정책 위반 근거가 있는 응답은 {summary['confirmed_policy_requests']}건입니다.")
        conclusions.append(f"그 비인가 응답에서 확인된 정보주체는 {summary['confirmed_exposure_subjects']}개입니다. 실제 전체 피해자 수의 추정치가 아닙니다.")
    else:
        conclusions.append('요청 횟수와 경로·상태는 집계할 수 있으나 실제 반환 항목·조회 인원·노출 확인은 알 수 없습니다.')
    return {'source': 'stored_postgresql_records_only', 'network_replay': False,
        'run': {**run, 'created_at': json_date(run.get('created_at'))}, 'actor': actor,
        'analysis_mode': 'stored_capture' if full else 'metadata_only_simulation',
        'window': {'start': json_date(start_at), 'end': json_date(end_at), 'first_observed': timeline[0]['created_at'] if timeline else None, 'last_observed': timeline[-1]['created_at'] if timeline else None},
        'summary': summary, 'api_calls': api_calls, 'subjects': subjects, 'timeline': timeline,
        'coverage': {'completeness': 'unknown', 'response_evidence_available': full and any(t['response_evidence_available'] for t in timeline),
            'corrupt_event_ids': corrupt_ids, 'missing_response_event_ids': missing_body, 'notes': coverage_notes},
        'conclusions': conclusions, 'stored_model_candidates': [{'event_id': row['event_id'], **row['payload']} for row in models if full and row['event_id'] in valid_ids and row['event_id'] in {t['event_id'] for t in timeline if t['response_evidence_available']}],
        'limitations': ['게이트웨이에 남은 기록의 범위만 조사합니다. 누락 로그·우회 접근·삭제된 데이터는 복원하지 못합니다.',
            '여기서 말하는 계정은 로그의 인증 주체입니다. 계정 탈취 여부나 실제 행위자의 신원을 확정하지 않습니다.',
            '등록 당시 정책·관측 자료를 사용하며 새 진단 트래픽이나 외부 API 요청을 생성하지 않습니다.',
            'SHA-256은 우발적 변경 확인용이며 관리자에 의한 동시 변조를 막는 서명이 아닙니다.',
            '분석은 저장 기록의 집계와 템플릿입니다. 저장된 AI 후보는 보조 근거이며 새 추론을 실행하지 않습니다.',
            '법률적 유출 판정·신고 의무·전체 피해 규모를 자동 확정하지 않습니다.']}


def list_runs():
    with store.connect() as conn:
        conn.execute('SET TRANSACTION READ ONLY')
        rows = conn.execute('''SELECT r.*, count(e.id) AS event_count,
            array_remove(array_agg(DISTINCT e.payload->>'actor'),NULL) AS actors
            FROM runs r LEFT JOIN events e ON e.run_id=r.id
            GROUP BY r.id ORDER BY (r.id LIKE 'incident-%%') DESC, r.created_at DESC LIMIT 200''').fetchall()
    return {'runs': [{**row, 'created_at': row['created_at'].isoformat()} for row in rows]}


def analyze(run_id, actor='bob', start=None, end=None, capture='full'):
    with store.connect() as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        run = conn.execute('SELECT * FROM runs WHERE id=%s', (run_id,)).fetchone()
        if not run:
            raise LookupError('Stored run not found')
        events = conn.execute('SELECT * FROM events WHERE run_id=%s ORDER BY id', (run_id,)).fetchall()
        findings = conn.execute('SELECT * FROM findings WHERE run_id=%s', (run_id,)).fetchall() if capture == 'full' else []
        observations = conn.execute('SELECT * FROM observations WHERE run_id=%s', (run_id,)).fetchall() if capture == 'full' else []
        models = conn.execute('SELECT m.* FROM model_results m JOIN events e ON e.id=m.event_id WHERE e.run_id=%s ORDER BY m.id', (run_id,)).fetchall() if capture == 'full' else []
    return analyze_records(run, events, findings, observations, models, actor, start, end, capture)


def markdown(report):
    def cell(value):
        return str(value).replace('|', '\\|').replace('\n', ' ')
    lines = ['# 남은 요청·응답 로그 기반 사후 분석', '',
        f"- 실행: {report['run']['id']}", f"- 대상 계정: {report['actor']}",
        f"- 분석 방식: {report['analysis_mode']}", '- 분석 중 API 재호출: 없음',
        '- 모든 기록은 로컬 합성 시나리오에서 생성됐습니다.', '']
    lines.extend('- ' + text for text in report['conclusions'])
    lines += ['', '## 접근 API와 호출 횟수', '', '| API | 로그 호출 | HTTP 2xx | 401/403 | 기타 | 정책 위반 근거 | 증거 ID |', '|---|---:|---:|---:|---:|---:|---|']
    for row in report['api_calls']:
        confirmed = row['confirmed_policy_requests'] if row['confirmed_policy_requests'] is not None else '알 수 없음'
        lines.append(f"| {cell(row['method'] + ' ' + row['endpoint'])} | {row['requests']} | {row['http_success']} | {row['denied']} | {row['other']} | {confirmed} | {row['evidence_ids']} |")
    lines += ['', '## 응답에서 관측한 정보주체', '', '| 테넌트·회원 체계·ID | 전체 관측 항목 | 비인가 응답 관측 항목 | 증거 ID | 비인가 응답 증거 ID |', '|---|---|---|---|---|']
    for row in report['subjects']:
        lines.append(f"| {cell(row['subject_key'])} | {cell(', '.join(row['fields']))} | {cell(', '.join(row['confirmed_fields']))} | {row['event_ids']} | {row['confirmed_event_ids']} |")
    if report['summary']['returned_subjects'] is None:
        lines.append('\n응답 증거를 사용하지 않는 비교 모드로 조회 인원·반환 항목은 알 수 없습니다.')
    lines += ['', '## 타임라인', '', '| 로그 | 시각 | 계정 | 요청 경로 | 상태 | 저장 판정 |', '|---|---|---|---|---:|---|']
    for row in report['timeline']:
        lines.append(f"| {row['event_id']} | {cell(row['created_at'])} | {cell(row['actor'])} | {cell(row['path'])} | {row['status_code']} | {row['verdict'] or '알 수 없음'} |")
    lines += ['', '## 기록 범위와 알 수 없는 사항', ''] + ['- ' + value for value in report['coverage']['notes'] + report['limitations']]
    lines += ['', '## 저장된 AI 후보', '', '분석 시 새 추론을 수행하지 않았습니다.', '```json', json.dumps(report['stored_model_candidates'], ensure_ascii=False, indent=2), '```']
    return '\n'.join(lines)
