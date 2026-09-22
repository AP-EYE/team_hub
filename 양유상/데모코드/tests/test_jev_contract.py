"""Input and HTTP contracts only: no database, worker, model or network calls.

Mocked score payloads are transport fixtures, never model-quality evidence.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import subprocess
import sys

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gateway.app import app
from gateway import jev
from ml_jev.engine import input_state


# Keep a real in-process ASGI client before patching the worker HTTP client.
ASGI_CLIENT = httpx.AsyncClient


def request_json(payload):
    async def run():
        async with ASGI_CLIENT(transport=httpx.ASGITransport(app=app), base_url='http://127.0.0.1:8810') as client:
            return await client.post('/api/jev/classify', json=payload)
    return asyncio.run(run())


@pytest.mark.parametrize(('mode', 'expected'), [
    ('full', {'field_path': 'member.memo', 'description': '가상 회원의 메모', 'value': '가상 값'}),
    ('schema_only', {'field_path': 'member.memo', 'description': '가상 회원의 메모', 'value': ''}),
    ('value_only', {'field_path': '', 'description': '', 'value': '가상 값'}),
])
def test_input_mode_preserves_only_declared_context(mode, expected):
    assert input_state('가상 값', 'member.memo', '가상 회원의 메모', mode) == expected


def test_unicode_input_at_limits_is_not_truncated():
    result = input_state('가' * 2500, '필' * 200, '설' * 500)
    assert (len(result['value']), len(result['field_path']), len(result['description'])) == (2500, 200, 500)


@pytest.mark.parametrize('values', [
    ('가' * 2501, '', ''), ('', '필' * 201, ''), ('', '', '설' * 501),
])
def test_input_over_limits_rejected_even_if_hidden_by_mode(values):
    with pytest.raises(ValueError, match='not silently truncated'):
        input_state(*values, input_mode='schema_only')


@pytest.mark.parametrize('values', [(None, '', ''), ('', 12, ''), ('', '', ['description'])])
def test_non_string_inputs_rejected(values):
    with pytest.raises(ValueError, match='strings'):
        input_state(*values)


def test_unknown_input_mode_rejected():
    with pytest.raises(ValueError, match='Unknown input mode'):
        input_state('가상 값', input_mode='infer_everything')


@pytest.mark.parametrize('payload', [
    {'method': 'official_jev'},
    {'input_mode': 'ignore_limits'},
    {'text': '가' * 2501},
    {'field_path': '필' * 201},
    {'description': '설' * 501},
    {'text': {'nested': 'not a string'}},
    ['not', 'an', 'object'],
])
def test_api_invalid_inputs_never_call_local_model(monkeypatch, payload):
    def forbidden_client(*args, **kwargs):
        pytest.fail('Invalid request reached the local model client')
    monkeypatch.setattr(jev.httpx, 'AsyncClient', forbidden_client)
    assert request_json(payload).status_code == 422


def install_worker_response(monkeypatch, status=200, payload=None, error=None):
    calls = []
    class WorkerClient:
        def __init__(self, **kwargs):
            calls.append({'client': kwargs})
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        async def post(self, url, **kwargs):
            calls.append({'url': url, **kwargs})
            if error:
                raise error
            return httpx.Response(status, json=payload, request=httpx.Request('POST', url))
    monkeypatch.setattr(jev.httpx, 'AsyncClient', WorkerClient)
    return calls


def test_busy_is_409_with_no_fake_classification(monkeypatch):
    calls = install_worker_response(monkeypatch, 409, {'error': 'local_model_busy'})
    response = request_json({'text': '가상 입력'})
    assert response.status_code == 409
    assert 'label' not in response.json()
    assert len(calls) == 2


def test_worker_rejects_input_as_400(monkeypatch):
    install_worker_response(monkeypatch, 400, {'error': 'Input exceeds token context; not truncated'})
    response = request_json({'text': '가상 입력'})
    assert response.status_code == 400
    assert response.json()['detail'] == 'Input exceeds token context; not truncated'


@pytest.mark.parametrize('error', [httpx.ConnectError('Worker unavailable'), httpx.ReadTimeout('Timed out')])
def test_network_failure_is_503_not_a_rule_fallback(monkeypatch, error):
    install_worker_response(monkeypatch, error=error)
    response = request_json({'text': '가상 입력'})
    assert response.status_code == 503
    assert 'label' not in response.json()
    assert type(error).__name__ in response.json()['detail']


def test_upstream_server_error_is_503(monkeypatch):
    install_worker_response(monkeypatch, 500, {'error': 'scoring_failed'})
    response = request_json({'text': '가상 입력'})
    assert response.status_code == 503
    assert 'label' not in response.json()


def test_success_returns_worker_scores_without_rewriting(monkeypatch):
    # These deliberately arbitrary numbers test round-trip integrity only.
    fixture = {'label': 'UNKNOWN', 'score': 0.413, 'probabilities': {'UNKNOWN': 0.413, 'OTHER': 0.587},
               'allowed_token_mass': 0.129, 'raw': {'option_logits': [-1.5, -1.2]},
               'status': 'needs_review', 'score_is_calibrated': False,
               'external_inference': False, 'source': 'mock_contract_fixture',
               'backend': 'semif_phase1.llamacpp_backend.SerialPrefixScorer.score',
               'adapter_version': 'korean-cached-contract-v2', 'cache_hit': True}
    calls = install_worker_response(monkeypatch, 200, fixture)
    payload = {'text': '가상 입력', 'field_path': 'memo', 'description': '시험용',
               'input_mode': 'schema_only', 'method': 'semif'}
    response = request_json(payload)
    assert response.status_code == 200
    assert response.json() == fixture
    assert calls[0]['client']['trust_env'] is False
    assert calls[1]['url'] == 'http://127.0.0.1:8814/classify'
    assert calls[1]['json'] == payload


def test_json_comparator_has_no_fabricated_option_probabilities(monkeypatch):
    fixture = {'label': 'CONTACT', 'score': None, 'probabilities': {}, 'generated_tokens': 8,
               'source': 'mock_json_fixture', 'status': 'needs_review'}
    calls = install_worker_response(monkeypatch, 200, fixture)
    response = request_json({'text': '가상 연락처', 'method': 'json'})
    assert response.json() == fixture
    assert calls[1]['json']['method'] == 'json'


def test_gateway_import_does_not_load_model_dependencies():
    code = ('import json, sys; import gateway.jev; import ml_jev.engine; '
            'print(json.dumps({"prefix":sys.prefix,"loaded":'
            '[x for x in ("torch","transformers","llama_cpp","semif_phase1") if x in sys.modules]}))')
    result = subprocess.run([str(ROOT / '.venv/Scripts/python.exe'), '-X', 'utf8', '-c', code],
                            cwd=ROOT, text=True, capture_output=True, check=True)
    data = json.loads(result.stdout)
    assert Path(data['prefix']).resolve() == (ROOT / '.venv').resolve()
    assert data['loaded'] == []


def test_jev_backend_import_does_not_require_torch():
    code = ('import json, sys; import semif_phase1.llamacpp_backend; '
            'print(json.dumps({"prefix":sys.prefix,"torch_imported":"torch" in sys.modules}))')
    result = subprocess.run([str(ROOT / '.venv-jev/Scripts/python.exe'), '-X', 'utf8', '-c', code],
                            cwd=ROOT, text=True, capture_output=True, check=True)
    data = json.loads(result.stdout)
    assert Path(data['prefix']).resolve() == (ROOT / '.venv-jev').resolve()
    assert data['torch_imported'] is False
