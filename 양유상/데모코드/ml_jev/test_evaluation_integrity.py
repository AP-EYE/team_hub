"""Local fabricated structures only: no model loads and no HTTP requests."""
import hashlib
import json

import pytest

from ml_jev import evaluate


@pytest.fixture
def isolated_evidence(tmp_path, monkeypatch):
    (tmp_path / 'ml_jev').mkdir()
    (tmp_path / 'evidence' / 'jev').mkdir(parents=True)
    engine = tmp_path / 'ml_jev' / 'engine.py'
    engine.write_text('# Synthetic frozen adapter source\n', encoding='utf-8')
    evidence = tmp_path / 'evidence' / 'jev'
    adapter = {'adapter_version': evaluate.ADAPTER_VERSION,
               'engine_sha256': hashlib.sha256(engine.read_bytes()).hexdigest()}
    (evidence / 'cached-adapter-frozen.json').write_text(json.dumps(adapter), encoding='utf-8')
    monkeypatch.setattr(evaluate, 'ROOT', tmp_path)
    monkeypatch.setattr(evaluate, 'EVIDENCE', evidence)
    monkeypatch.setattr(evaluate, 'BASE_EVIDENCE', evidence)
    return tmp_path, evidence, adapter


def response():
    return {'label': 'HEALTH', 'score': .8, 'probabilities': {'HEALTH': .8, 'OTHER': .2},
            'allowed_token_mass': .5, 'latency_ms': 123, 'external_inference': False,
            'contract_sha256': evaluate.CONTRACT_HASH, 'adapter_version': evaluate.ADAPTER_VERSION,
            'backend': evaluate.SEMIF_BACKEND, 'source': 'actual_semif_llamacpp',
            'semif_commit': evaluate.COMMIT, 'cache_hit': True, 'prompt_sha256': 'synthetic-prompt',
            'status': 'needs_review'}


def test_frozen_adapter_refuses_source_or_version_change(isolated_evidence):
    root, evidence, adapter = isolated_evidence
    assert evaluate.frozen_adapter()['engine_sha256'] == adapter['engine_sha256']
    (root / 'ml_jev' / 'engine.py').write_text('# Changed source\n', encoding='utf-8')
    with pytest.raises(ValueError, match='source differs'):
        evaluate.frozen_adapter()
    adapter['adapter_version'] = 'direct-pilot'
    (evidence / 'cached-adapter-frozen.json').write_text(json.dumps(adapter), encoding='utf-8')
    with pytest.raises(ValueError, match='version differs'):
        evaluate.frozen_adapter()


@pytest.mark.parametrize('field,value,message', [
    ('adapter_version', 'direct-pilot', 'different adapter'),
    ('backend', 'semif_phase1.llamacpp_backend.score', 'SerialPrefixScorer'),
    ('semif_commit', 'another-commit', 'upstream commit'),
    ('cache_hit', None, 'cache-hit'),
    ('source', 'independent_reimplementation', 'SerialPrefixScorer'),
])
def test_normalized_response_rejects_wrong_execution_identity(isolated_evidence, field, value, message):
    actual = response()
    actual[field] = value
    with pytest.raises(ValueError, match=message):
        evaluate.normalized_result(actual, 'HEALTH', 'semif', 150)


def test_normalized_response_retains_real_cache_and_adapter_fields(isolated_evidence):
    result = evaluate.normalized_result(response(), 'HEALTH', 'semif', 150)
    assert result['cache_hit'] is True
    assert result['adapter_version'] == evaluate.ADAPTER_VERSION
    assert result['backend'] == evaluate.SEMIF_BACKEND
    assert result['semif_commit'] == evaluate.COMMIT
    assert result['correct'] is True


def save_legacy_progress(evidence, original):
    # Simulates the first v2 evaluator, whose aggregate omitted identity fields
    # but whose immutable raw record retained the complete worker response.
    compact = {'label': 'HEALTH', 'score': .8, 'prompt_sha256': 'synthetic-prompt',
               'correct': True, 'execution_status': 'completed'}
    freeze = {'sha256': 'synthetic-dataset-sha'}
    case = {'id': 'h1', 'expected': 'HEALTH', 'slice': 'synthetic'}
    aggregate = {'dataset': freeze, 'contract_sha256': evaluate.CONTRACT_HASH,
                 'rows': [{**case, 'methods': {'semif': compact}}]}
    raw = {'id': 'h1', 'method': 'semif', 'dataset_sha256': freeze['sha256'],
           'contract_sha256': evaluate.CONTRACT_HASH, 'result': compact, 'worker_response': original}
    (evidence / 'evaluation.json').write_text(json.dumps(aggregate), encoding='utf-8')
    raw_path = evidence / 'run-synthetic-semif-rows.jsonl'
    raw_path.write_text(json.dumps(raw) + '\n', encoding='utf-8')
    return freeze, [case], raw_path


def test_old_v2_progress_is_verified_against_raw_without_editing_evidence(isolated_evidence):
    _, evidence, _ = isolated_evidence
    freeze, cases, raw_path = save_legacy_progress(evidence, response())
    before = raw_path.read_bytes()
    rows, _ = evaluate.load_progress(freeze, cases)
    assert rows['h1']['methods']['semif']['adapter_version'] == evaluate.ADAPTER_VERSION
    assert rows['h1']['methods']['semif']['cache_hit'] is True
    assert raw_path.read_bytes() == before


def test_direct_pilot_cannot_be_restored_into_cached_progress(isolated_evidence):
    _, evidence, _ = isolated_evidence
    original = response()
    original.pop('adapter_version')
    original['backend'] = 'semif_phase1.llamacpp_backend.score'
    freeze, cases, _ = save_legacy_progress(evidence, original)
    with pytest.raises(ValueError, match='different adapter'):
        evaluate.load_progress(freeze, cases)


def test_aggregate_without_raw_proof_is_not_accepted(isolated_evidence):
    _, evidence, _ = isolated_evidence
    freeze, cases, raw_path = save_legacy_progress(evidence, response())
    raw_path.unlink()
    with pytest.raises(ValueError, match='no matching raw'):
        evaluate.load_progress(freeze, cases)


def test_failed_pilot_without_adapter_identity_is_not_imported(isolated_evidence):
    _, evidence, _ = isolated_evidence
    freeze, cases, raw_path = save_legacy_progress(evidence, response())
    raw = json.loads(raw_path.read_text(encoding='utf-8'))
    raw['result'] = {'label': None, 'score': None, 'correct': False, 'execution_status': 'failed'}
    raw['worker_response'] = None
    raw_path.write_text(json.dumps(raw) + '\n', encoding='utf-8')
    with pytest.raises(ValueError, match='Failed legacy SemIf attempt lacks frozen adapter identity'):
        evaluate.load_progress(freeze, cases)


@pytest.mark.parametrize('name', ['', '..', '../replay', 'a/b', 'a\\b', '/tmp/replay', 'C:\\temp\\replay', 'a b', 'a.', 'CON', 'nul', 'COM1', 'LPT9', 'a' * 65])
def test_reproduction_name_rejects_unsafe_or_reserved_paths(name):
    with pytest.raises(ValueError):
        evaluate.validate_run_name(name)


def test_reproduction_path_is_bounded_and_does_not_create_files(isolated_evidence):
    _, evidence, _ = isolated_evidence
    assert evaluate.output_directory() == evidence
    assert evaluate.output_directory('replay-01') == evidence / 'reproductions' / 'replay-01'
    assert evaluate.output_directory('replay_02') == evidence / 'reproductions' / 'replay_02'
    assert not (evidence / 'reproductions').exists()


def test_reproduction_rejects_resolved_directory_redirection(isolated_evidence, monkeypatch):
    root, evidence, _ = isolated_evidence
    path_type = type(evidence)
    original_resolve = path_type.resolve
    redirected = evidence / 'reproductions' / 'replay'

    def resolve(path, *args, **kwargs):
        if path == redirected:
            return root / 'outside-evidence' / 'replay'
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(path_type, 'resolve', resolve)
    with pytest.raises(ValueError, match='escapes the permitted'):
        evaluate.output_directory('replay')


def test_fresh_named_progress_ignores_packaged_results_and_uses_base_freeze(isolated_evidence, monkeypatch):
    _, evidence, _ = isolated_evidence
    freeze, cases, raw_path = save_legacy_progress(evidence, response())
    original = raw_path.read_bytes()
    named = evaluate.output_directory('replay')
    monkeypatch.setattr(evaluate, 'EVIDENCE', named)
    rows, runs = evaluate.load_progress(freeze, cases)
    assert rows['h1']['methods'] == {} and runs == []
    assert evaluate.frozen_adapter()['adapter_version'] == evaluate.ADAPTER_VERSION
    assert not named.exists()
    assert raw_path.read_bytes() == original


def test_same_named_progress_resumes_only_its_own_results(isolated_evidence, monkeypatch):
    _, evidence, _ = isolated_evidence
    named = evaluate.output_directory('replay')
    named.mkdir(parents=True)
    freeze, cases, raw_path = save_legacy_progress(named, response())
    before = raw_path.read_bytes()
    monkeypatch.setattr(evaluate, 'EVIDENCE', named)
    rows, runs = evaluate.load_progress(freeze, cases)
    assert rows['h1']['methods']['semif']['correct'] is True
    assert rows['h1']['methods']['semif']['adapter_version'] == evaluate.ADAPTER_VERSION
    assert raw_path.read_bytes() == before
    assert not (evidence / 'evaluation.json').exists()
