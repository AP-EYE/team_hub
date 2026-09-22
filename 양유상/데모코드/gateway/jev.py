"""HTTP surface for the Korean SemIf lab, isolated from authorization and logs."""
import json
from pathlib import Path
from typing import Literal
import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field
from ml_jev.engine import LABELS, COMMIT

ROOT = Path(__file__).resolve().parents[1]
WORKER = 'http://127.0.0.1:8814'
router = APIRouter()


@router.get('/privacy-lab')
def lab():
    return FileResponse(ROOT / 'static/jev-lab.html')


@router.get('/api/jev/state')
async def state():
    try:
        async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
            response = await client.get(WORKER + '/health')
            response.raise_for_status()
            runtime = response.json()
    except httpx.HTTPError:
        runtime = {'status': 'unavailable', 'model': 'Qwen3-4B Q4_K_M', 'semif_commit': COMMIT, 'external_inference': False}
    cases = [json.loads(line) for line in (ROOT / 'ml_jev/cases.jsonl').read_text(encoding='utf-8').splitlines() if line]
    evaluation_path = ROOT / 'evidence/jev/evaluation.json'
    evaluation = json.loads(evaluation_path.read_text(encoding='utf-8')) if evaluation_path.exists() else None
    return {'runtime': runtime, 'labels': LABELS, 'cases': cases, 'evaluation': evaluation}


class Classification(BaseModel):
    text: str = Field(default='', max_length=2500)
    field_path: str = Field(default='', max_length=200)
    description: str = Field(default='', max_length=500)
    input_mode: Literal['full', 'schema_only', 'value_only'] = 'full'
    method: Literal['semif', 'json'] = 'semif'


@router.post('/api/jev/classify')
async def classify(body: Classification):
    try:
        async with httpx.AsyncClient(timeout=240, trust_env=False) as client:
            response = await client.post(WORKER + '/classify', json=body.model_dump())
        if response.status_code == 409:
            raise HTTPException(409, '로컬 모델이 다른 입력을 처리 중입니다. 완료 후 실행해 주세요.')
        if response.status_code == 400:
            raise HTTPException(400, response.json().get('error', 'Invalid classifier input'))
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as error:
        raise HTTPException(503, f'Local SemIf worker unavailable: {type(error).__name__}')


@router.get('/api/jev/report')
def report():
    path = ROOT / 'docs/korean-jev-demo.md'
    if not path.exists():
        raise HTTPException(409, '실측 보고서를 작성 중입니다.')
    return PlainTextResponse(path.read_text(encoding='utf-8'), media_type='text/markdown',
        headers={'Content-Disposition': 'attachment; filename="korean-semif-demo.md"'})
