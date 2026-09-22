import asyncio
from contextlib import asynccontextmanager
import json
from pathlib import Path
from time import perf_counter
from uuid import uuid4
from typing import Literal
import httpx
import psycopg
from psycopg_pool import PoolTimeout
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field
from . import store, incident
from .jev import router as jev_router
from .domain import TOKENS, SCENARIOS, actor_from_header, policy_for
from .privacy import MAPPINGS, inspect_payload, redact, observations, decide, records

ROOT = Path(__file__).resolve().parents[1]
MODEL_URLS = {'direct': 'http://127.0.0.1:8812', 'ollama': 'http://127.0.0.1:8813'}
BACKGROUND = set()
RUN_LOCK = asyncio.Lock()
MODEL_LOCK = asyncio.Semaphore(1)


def default_backend():
    try:
        selected = json.loads((ROOT / '.runtime' / 'model-selection.json').read_text(encoding='utf-8-sig')).get('backend')
        return selected if selected in MODEL_URLS else 'direct'
    except (OSError, ValueError):
        return 'direct'


@asynccontextmanager
async def lifespan(app):
    store.init()
    app.state.http = httpx.AsyncClient(timeout=15, trust_env=False)
    yield
    for task in BACKGROUND:
        task.cancel()
    await app.state.http.aclose()
    store.close()


app = FastAPI(title='API 노출 분석 실험실', lifespan=lifespan)
app.include_router(jev_router)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver'])
(ROOT / 'static').mkdir(exist_ok=True)
app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')


@app.exception_handler(psycopg.Error)
@app.exception_handler(PoolTimeout)
async def database_failure(request, exc):
    return JSONResponse({"detail": "Logging database unavailable; request evidence was not confirmed saved."}, status_code=503)


@app.get('/')
def index():
    file = ROOT / 'static' / 'index.html'
    return FileResponse(file) if file.exists() else PlainTextResponse('Dashboard is being prepared. See /docs.')


@app.get('/health')
def health():
    with store.connect() as conn:
        database = conn.execute('SELECT version() AS version').fetchone()['version']
    return {"status": "ok", "database": database.split(' on ')[0], "synthetic": True}


async def model_event(event_id, raw, path):
    text = raw.get('consult_reason') or raw.get('text') if isinstance(raw, dict) else None
    if not text:
        return
    field = 'consult_reason' if 'consult_reason' in raw else 'text'
    body = {"text": text, "field_path": field, "description": '특정 개인의 상담 기록' if field == 'consult_reason' else '공개 일반 건강 안내문'}
    backend = default_backend()
    try:
        async with MODEL_LOCK:
            async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
                response = await client.post(MODEL_URLS[backend] + '/classify', json=body)
                response.raise_for_status()
                result = response.json()
    except Exception as error:
        result = {"status": "unavailable", "model": "local-worker", "error_type": type(error).__name__, "label": None}
    store.save_model(event_id, {"field_path": field, "endpoint": path, "backend": backend, "input_scope": "실제 로컬 합성 응답값 / 외부 전송 없음", "result": result, "decision_role": "분류 후보만 생성; 인가 판정·법적 확정·자동 차단에 사용하지 않음"})


async def forward(mode, path, authorization, run_id, case_id='manual', title='수동 로컬 조회', query_keys=None):
    if mode not in ('vulnerable', 'fixed'):
        raise HTTPException(400, 'mode must be vulnerable or fixed')
    if not path or '..' in path or '://' in path or path.startswith('/'):
        raise HTTPException(400, 'invalid fixture path')
    actor = actor_from_header(authorization)
    start = perf_counter()
    try:
        upstream = await app.state.http.get(f'http://127.0.0.1:8811/{mode}/{path}', headers={'authorization': authorization} if authorization else {})
    except httpx.HTTPError:
        raise HTTPException(502, 'local fixture API unavailable')
    duration = round((perf_counter() - start) * 1000, 3)
    try:
        body = upstream.json()
    except ValueError:
        body = {"error": "non_json_response"}
    policy = policy_for(path, actor, body)
    verdict, category, reason, exposed_fields = decide(policy, upstream.status_code, body)
    response_records = records(body)
    # A resource mismatch is not enough to confirm an authorization failure.
    # This fixture has an explicit path-to-object contract; violations of the
    # contract are separated from tested permission failures.
    if verdict == 'confirmed' and category == 'BOLA' and response_records:
        target = path.split('/')[-1]
        tenant = path.split('/')[1] if path.startswith('tenants/') else 'alpha'
        if path.startswith(('profile/', 'consultations/', 'orders/', 'tenants/')) and not any((r.get('member_id') or r.get('customer_no')) == target and r.get('tenant_id') == tenant for r in response_records):
            verdict, reason = 'needs_review', '요청 대상과 반환 객체의 대응이 불명확하여 추가 확인 필요'
    privacy = inspect_payload(body)
    people = sorted({f"{r['tenant_id']}:{r.get('member_id') or r.get('customer_no') or r.get('owner_id')}" for r in response_records})
    subject = ', '.join(people) if people else 'unknown'
    score = 0
    factors = []
    if verdict == 'confirmed':
        score = {'BOLA': 65, 'BFLA': 75, 'BOPLA': 55}.get(category, 40)
        factors.append(f'{category} 기준 {score}')
        if any(p['label'] == 'SENSITIVE_CANDIDATE' for p in privacy):
            score += 20
            factors.append('민감정보 후보 +20')
        elif any(p['label'] in {'PHONE', 'ADDRESS', 'NAME', 'EMAIL'} for p in privacy):
            score += 10
            factors.append('일반 개인정보 +10')
        score = min(score, 100)
    event = {"run_id": run_id, "case_id": case_id, "mode": mode, "actor": actor['name'] if actor else 'anonymous', "actor_id": actor['id'] if actor else None, "actor_tenant": actor['tenant'] if actor else None, "subject": subject, "subjects": people, "tenant": sorted({r['tenant_id'] for r in response_records}), "method": "GET", "path": path, "status_code": upstream.status_code, "request_redacted": {"method": "GET", "path": path, "query_keys_only": query_keys or [], "headers": {"authorization": "[REMOVED]"} if authorization else {}}, "response_redacted": redact(body), "privacy": privacy, "duration_ms": duration, "policy": policy, "synthetic": True, "response_capture": "구조·분류·연결 식별자 보존, 일반/민감 값 마스킹; 원문 전체 포렌식 복원 불가"}
    finding = {"run_id": run_id, "case_id": case_id, "scenario_id": case_id, "title": title, "verdict": verdict, "category": category, "reason": reason, "actor": event['actor'], "subject": subject, "endpoint": path, "status_code": upstream.status_code, "fields": exposed_fields, "score": score, "score_basis": factors, "score_notice": "팀의 설명 가능한 실험용 우선순위; 법정 점수·법 위반 확정 아님", "mode": mode}
    event_id, finding_id = store.save(event, finding, observations(body))
    if path.startswith('consultations/') or path == 'info/health':
        task = asyncio.create_task(model_event(event_id, body, path))
        BACKGROUND.add(task)
        task.add_done_callback(BACKGROUND.discard)
    return body, upstream.status_code, event_id, finding_id


@app.get('/proxy/{mode}/{path:path}')
async def proxy(mode: str, path: str, request: Request):
    run_id = 'manual-' + uuid4().hex[:12]
    store.new_run(run_id, mode)
    try:
        body, status, event_id, _ = await forward(mode, path, request.headers.get('authorization', ''), run_id, query_keys=list(request.query_params.keys()))
        store.finish_run(run_id)
    except Exception:
        store.finish_run(run_id, 'failed')
        raise
    return JSONResponse(body, status_code=status, headers={'X-Demo-Event-Id': str(event_id), 'X-Demo-Run-Id': run_id, 'Cache-Control': 'no-store'})


class RunBody(BaseModel):
    mode: str = 'vulnerable'


@app.post('/api/demo/run')
async def run_demo(body: RunBody):
    if body.mode not in ('vulnerable', 'fixed'):
        raise HTTPException(400, 'unknown mode')
    if RUN_LOCK.locked():
        raise HTTPException(409, 'demo run already in progress')
    async with RUN_LOCK:
        run_id = uuid4().hex[:16]
        store.new_run(run_id, body.mode)
        try:
            for case in SCENARIOS:
                token = 'Bearer demo-' + case['actor'] if case['actor'] != 'anonymous' else ''
                await forward(body.mode, case['path'], token, run_id, case['id'], case['title'])
            store.finish_run(run_id)
        except Exception:
            store.finish_run(run_id, 'failed')
            raise
        return {"run_id": run_id, "mode": body.mode, "cases": len(SCENARIOS), "status": "completed", "model_analysis": "비동기 로컬 분석; 결과는 /api/state에서 확인"}


async def model_health(backend=None):
    try:
        result = await app.state.http.get(MODEL_URLS[backend or default_backend()] + '/health', timeout=0.6)
        result.raise_for_status()
        return result.json()
    except Exception:
        return {"status": "unavailable", "note": "로컬 모델 작업자 미실행. 규칙 결과를 AI 실행으로 표시하지 않음."}


def read_artifact(path):
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return None


@app.get('/api/state')
async def get_state():
    state = store.state()
    model = await model_health()
    model['selected_backend'] = default_backend()
    healths = await asyncio.gather(*(model_health(name) for name in MODEL_URLS))
    model['backends'] = {name: status for name, status in zip(MODEL_URLS, healths)}
    model['event_results'] = state.pop('model_results')
    model['pending_jobs'] = len(BACKGROUND)
    model['evidence_files'] = sorted(p.name for p in (ROOT / 'evidence' / 'model').glob('*.json')) if (ROOT / 'evidence' / 'model').exists() else []
    model['benchmarks'] = {p.stem: read_artifact(p) for p in (ROOT / 'evidence' / 'model').glob('*summary.json')} if (ROOT / 'evidence' / 'model').exists() else {}
    model['alternative_benchmarks'] = {p.stem: read_artifact(p) for p in (ROOT / 'evidence' / 'model-alternative').glob('*summary*.json')} if (ROOT / 'evidence' / 'model-alternative').exists() else {}
    evaluation = read_artifact(ROOT / 'evidence' / 'integration-tests.json') or {"status": "NOT_RUN"}
    confirmed = sum(f['verdict'] == 'confirmed' for f in state['findings'])
    state.update(meta={"title": "API 노출 분석 실험실", "version": "0.1.0", "database": "PostgreSQL 17 / local Docker", "scope": "합성 REST/JSON API · localhost 전용 · 사전 진단 + 기록 범위 내 조사", "model_status": model.get('status', 'unknown'), "score_notice": "법정 점수가 아닌 실험용 수정 우선순위"}, summary={"events": len(state['events']), "total_events": state['total_events'], "findings": len(state['findings']), "confirmed": confirmed, "review": sum(f['verdict'] == 'needs_review' for f in state['findings']), "subjects": state['subjects'], "allowed": sum(f['verdict'] == 'allowed' for f in state['findings']), "blocked": sum(f['verdict'] == 'blocked' for f in state['findings'])}, mappings=MAPPINGS, model=model, evaluation=evaluation)
    return state


@app.get('/api/incidents/runs')
def incident_runs():
    return incident.list_runs()


def incident_result(run_id, actor, start, end, capture):
    try:
        return incident.analyze(run_id, actor, start, end, capture)
    except LookupError as error:
        raise HTTPException(404, str(error))
    except ValueError as error:
        raise HTTPException(400, str(error))


@app.get('/api/incidents/analyze')
def analyze_incident(run_id: str, actor: str = 'bob', start: str | None = None, end: str | None = None, capture: str = 'full'):
    return incident_result(run_id, actor, start, end, capture)


@app.get('/api/incidents/report')
def export_incident(run_id: str, actor: str = 'bob', start: str | None = None, end: str | None = None, capture: str = 'full'):
    report = incident_result(run_id, actor, start, end, capture)
    return PlainTextResponse(incident.markdown(report), media_type='text/markdown', headers={'Content-Disposition': 'attachment; filename="incident-report.md"'})


@app.post('/api/incidents/demo/prepare')
async def prepare_incident_logs():
    if RUN_LOCK.locked():
        raise HTTPException(409, 'demo run already in progress')
    # Capture is deliberately separate from investigation. Each entry is a real
    # synthetic GET; calls are logged individually, including retries and errors.
    calls = [
        ('bob', 'profile/private/U100'), ('bob', 'profile/private/U100'),
        ('bob', 'profile/private/U200'), ('bob', 'profile/private/U999'),
        ('bob', 'consultations/U100'), ('bob', 'consultations/U100'),
        ('bob', 'profile/public/U100'), ('bob', 'documents/private'),
        ('bob', 'admin/export'), ('bob', 'admin/export'),
        ('bob', 'tenants/beta/profile/U100'), ('bob', 'ambiguous/U100'),
        ('bob', 'info/health'), ('admin', 'admin/export'),
    ]
    async with RUN_LOCK:
        run_id = 'incident-' + uuid4().hex[:12]
        store.new_run(run_id, 'vulnerable')
        try:
            for index, (actor, path) in enumerate(calls, 1):
                await forward('vulnerable', path, 'Bearer demo-' + actor, run_id,
                              f'incident_{index:02d}', f'합성 사고 기록 {index}: {path}')
            store.finish_run(run_id)
        except Exception:
            store.finish_run(run_id, 'failed')
            raise
    return {'run_id': run_id, 'status': 'completed', 'cases': len(calls),
            'note': '합성 API에 GET을 보내 사고 기록을 준비했습니다. 이후 분석은 저장된 DB만 읽습니다.'}


class ClassifyBody(BaseModel):
    text: str = Field(max_length=4000)
    field_path: str = Field(default='', max_length=200)
    description: str = Field(default='', max_length=500)
    backend: Literal['direct', 'ollama'] | None = None


@app.post('/api/model/classify')
async def classify(body: ClassifyBody):
    try:
        result = await app.state.http.post(MODEL_URLS[body.backend or default_backend()] + '/classify', json=body.model_dump(exclude={'backend'}), timeout=120)
        result.raise_for_status()
        return result.json()
    except httpx.HTTPError as error:
        raise HTTPException(503, f'local model unavailable: {type(error).__name__}')


class MappingBody(BaseModel):
    field_path: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=500)
    backend: Literal['direct', 'ollama'] | None = None


@app.post('/api/mapping/suggest')
async def mapping_suggest(body: MappingBody):
    try:
        response = await app.state.http.post(MODEL_URLS[body.backend or default_backend()] + '/normalize', json=body.model_dump(exclude={'backend'}), timeout=120)
        response.raise_for_status()
        result = response.json()
        result['approval_status'] = 'candidate_requires_review'
        result['notice'] = '로컬 모델의 매핑 후보입니다. 승인된 규칙이나 DB 연결 키를 자동 변경하지 않습니다.'
        return result
    except httpx.HTTPError as error:
        raise HTTPException(503, f'local mapping model unavailable: {type(error).__name__}')


@app.get('/api/report')
async def report():
    state = await get_state()
    mode = state['runs'][0]['mode'] if state['runs'] else 'none'
    text = ['# API 개인정보 노출 분석 데모 실행 보고서', '', '모든 데이터는 합성 자료이며 실제 침해사고 결과가 아닙니다.', '', f"- 최신 실행: {state['runs'][0]['id'] if state['runs'] else 'none'} ({mode})", f"- 관측 요청: {state['summary']['events']}", f"- 정책 위반 확인: {state['summary']['confirmed']}", f"- 정책 미확정 검토: {state['summary']['review']}", f"- 비인가 응답에서 관측한 중복 제거 정보주체: {state['summary']['subjects']}", '- 범위: 현재 실행에서 기록된 응답. 전체 유출 규모 또는 법 위반 확정이 아닙니다.', '- 원문 개인정보 값은 마스킹되어 원문 전체의 사후 복원은 지원하지 않습니다.', '', '| 사례 | 판정 | 유형 | 점수 | 증거 이벤트 |', '|---|---|---|---:|---|']
    for f in state['findings']:
        text.append(f"| {f['title']} | {f['verdict']} | {f['category']} | {f['score']} | {f['evidence_ids']} |")
    text += ['', '## 결합 분석', '', '같은 요청자가 같은 실행에서 받은 비인가 응답만 tenant + namespace + subject_id로 결합합니다. 필드 조합만으로 법적 식별 가능성을 확정하지 않습니다.', '', '```json', json.dumps(state['links'], ensure_ascii=False, indent=2), '```', '', '## 로컬 모델', '', '모델 분류는 후보이며 인가 정책 판정에는 사용하지 않습니다.', '', '```json', json.dumps(state['model'], ensure_ascii=False, indent=2), '```', '', '## 무결성', '', '이벤트 SHA-256은 우발적 변경 탐지용입니다. DB 관리자가 값과 해시를 함께 수정하는 위협에 대한 서명/외부 증거 보존은 구현하지 않았습니다.', '', '## 남은 범위', '', '운영 인증/권한, TLS, 성능·부하 검증, 독립 한국어 평가셋, 정책 온보딩, 로그 보존·접근 통제, 실제 게이트웨이 플러그인, 원문 증거 보존 설계가 필요합니다.']
    return PlainTextResponse('\n'.join(text), media_type='text/markdown', headers={'Content-Disposition': 'attachment; filename="demo-report.md"'})
