"""Run frozen KO96 inputs against the local worker; persist every attempt.

One process at a time. Existing attempts are preserved and skipped, including
errors: this evaluator does not silently retry failures or select the best run.
The raw files contain the actual response and request metadata. Gold labels and
reasons are never included in an HTTP request to the model worker.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import uuid

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.engine import rule_baseline
from ml_jev.engine import COMMIT, CONTRACT_HASH
from ml_jev.metrics import LABELS, method_metrics

BASE_EVIDENCE = ROOT / 'evidence' / 'jev'
EVIDENCE = BASE_EVIDENCE
METHODS = ('semif', 'json', 'rules')
WORKER_URL = 'http://127.0.0.1:8814'
ADAPTER_VERSION = 'korean-cached-contract-v2'
SEMIF_BACKEND = 'semif_phase1.llamacpp_backend.SerialPrefixScorer.score'
# Capture process-start source identity once. Hashing the file at a later method
# boundary could misidentify already imported code after an on-disk edit.
STARTUP_EVALUATOR_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
STARTUP_METRICS_SHA256 = hashlib.sha256(Path(__file__).with_name('metrics.py').read_bytes()).hexdigest()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_run_name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', value):
        raise ValueError('Run name must be 1-64 ASCII letters, digits, hyphens or underscores and start with a letter or digit.')
    if value.upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}:
        raise ValueError('Run name is a reserved Windows device name.')
    return value


def output_directory(run_name=None):
    if run_name is None:
        return BASE_EVIDENCE
    name = validate_run_name(run_name)
    canonical = BASE_EVIDENCE.resolve()
    namespace = canonical / 'reproductions'
    target = (namespace / name).resolve()
    # Checking the unresolved namespace prevents a pre-existing directory link
    # from redirecting reproduction writes outside the named evidence subtree.
    if target.parent != namespace:
        raise ValueError('Resolved reproduction path escapes the permitted evidence/jev/reproductions directory.')
    return target


def frozen_adapter():
    adapter = json.loads((BASE_EVIDENCE / 'cached-adapter-frozen.json').read_text(encoding='utf-8-sig'))
    if adapter.get('adapter_version') != ADAPTER_VERSION:
        raise ValueError('Cached adapter version differs from the required v2 experiment; evaluation refused.')
    if sha(ROOT / 'ml_jev' / 'engine.py') != adapter.get('engine_sha256'):
        raise ValueError('Model adapter source differs from its frozen SHA-256; evaluation refused.')
    return adapter


def require_semif_identity(response):
    if response.get('adapter_version') != ADAPTER_VERSION:
        raise ValueError('SemIf response belongs to a different adapter; direct pilot and cached v2 must remain separate.')
    if response.get('backend') != SEMIF_BACKEND or response.get('source') != 'actual_semif_llamacpp':
        raise ValueError('SemIf response did not use the pinned upstream SerialPrefixScorer backend.')
    if response.get('semif_commit') != COMMIT:
        raise ValueError('SemIf response upstream commit differs from the pinned version.')
    if not isinstance(response.get('cache_hit'), bool):
        raise ValueError('SemIf response omitted the actual cache-hit state.')


def frozen_dataset():
    frozen_adapter()
    freeze = json.loads((BASE_EVIDENCE / 'dataset-frozen.json').read_text(encoding='utf-8-sig'))
    source = ROOT / 'ml_jev' / 'cases.jsonl'
    if sha(source) != freeze['sha256']:
        raise ValueError('Dataset differs from the pre-inference frozen SHA-256; evaluation refused.')
    if CONTRACT_HASH != freeze['contract_sha256']:
        raise ValueError('Model label contract differs from frozen SHA-256; evaluation refused.')
    cases = [json.loads(line) for line in source.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    if len(cases) != freeze['count'] or len({row['id'] for row in cases}) != len(cases):
        raise ValueError('Frozen dataset count or unique IDs do not match.')
    if any(row['expected'] not in LABELS for row in cases):
        raise ValueError('Unknown gold label in frozen dataset.')
    return freeze, cases


def atomic_json(path, value):
    temporary = path.with_name(f'.{path.name}.{uuid.uuid4().hex}.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    try:
        for attempt in range(5):
            try:
                os.replace(temporary, path)
                return
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(.1)
    finally:
        if temporary.exists():
            temporary.unlink()


def load_progress(freeze, cases):
    adapter = frozen_adapter()
    path = EVIDENCE / 'evaluation.json'
    rows = {case['id']: {'id': case['id'], 'expected': case['expected'], 'slice': case['slice'],
                         'pair_id': case.get('pair_id'), 'methods': {}} for case in cases}
    runs = []
    if path.exists():
        previous = json.loads(path.read_text(encoding='utf-8-sig'))
        if previous['dataset']['sha256'] != freeze['sha256'] or previous.get('contract_sha256') != CONTRACT_HASH:
            raise ValueError('Existing evaluation uses a different dataset or contract; preserve it as another version first.')
        for previous_row in previous.get('rows', []):
            if previous_row['id'] not in rows or previous_row['expected'] != rows[previous_row['id']]['expected']:
                raise ValueError('Existing evaluation row does not match frozen case.')
            rows[previous_row['id']]['methods'] = previous_row.get('methods', {})
        runs = previous.get('runs', [])
    # Restore an append-and-fsync raw result if a process ended before its next
    # atomic snapshot. This preserves the attempt rather than re-running it.
    raw_semif = {}
    for raw_path in sorted(EVIDENCE.glob('run-*-rows.jsonl')):
        for line in raw_path.read_text(encoding='utf-8').splitlines():
            try:
                saved = json.loads(line)
            except json.JSONDecodeError:
                # A partial line has no complete evidence result to import.
                continue
            if saved.get('dataset_sha256') != freeze['sha256'] or saved.get('contract_sha256') != CONTRACT_HASH:
                continue
            case_id, method = saved.get('id'), saved.get('method')
            if method == 'semif':
                if saved['result'].get('execution_status') != 'failed':
                    original = saved.get('worker_response')
                    if not isinstance(original, dict):
                        raise ValueError('Saved SemIf result has no raw worker response to verify adapter identity.')
                    require_semif_identity(original)
                    if original.get('label') != saved['result'].get('label') or original.get('prompt_sha256') != saved['result'].get('prompt_sha256'):
                        raise ValueError('Saved SemIf summary does not agree with its raw worker response.')
                    proof = {key: original.get(key) for key in ('adapter_version', 'backend', 'cache_hit', 'semif_commit', 'source')}
                    if case_id in raw_semif and raw_semif[case_id]['result'] != saved['result']:
                        raise ValueError('Conflicting saved SemIf attempts require a separate experiment; no best-result selection.')
                    raw_semif[case_id] = {'result': saved['result'], 'identity': proof}
                elif saved.get('adapter_version') != ADAPTER_VERSION or saved.get('engine_sha256') != adapter['engine_sha256']:
                    raise ValueError('Failed legacy SemIf attempt lacks frozen adapter identity; keep it in its original experiment.')
                else:
                    raw_semif[case_id] = {'result': saved['result'], 'identity': {
                        'adapter_version': ADAPTER_VERSION, 'engine_sha256': adapter['engine_sha256']}}
            if case_id in rows and method in METHODS and method not in rows[case_id]['methods']:
                rows[case_id]['methods'][method] = saved['result']
    # Older cached-v2 snapshots omitted identity fields even though their full
    # raw responses retained them. Verify against raw evidence, then enrich only
    # the in-memory view. Never edit a saved raw result to manufacture identity.
    for case_id, row in rows.items():
        result = row['methods'].get('semif')
        if result is None:
            continue
        proof = raw_semif.get(case_id)
        if proof:
            original_result = proof['result']
            for key in ('label', 'score', 'prompt_sha256', 'correct'):
                if result.get(key) != original_result.get(key):
                    raise ValueError('Existing SemIf progress conflicts with the preserved raw prediction.')
            row['methods']['semif'] = {**result, **proof['identity']}
        else:
            # A successful aggregate without its raw response is not sufficient
            # evidence to resume the cached-v2 benchmark.
            raise ValueError('Existing SemIf progress has no matching raw cached-v2 evidence.')
    return rows, runs


def snapshot(freeze, cases, rows, runs, active_method=None):
    # Expose pending rows as absent methods, never as fabricated incorrect calls.
    ordered = [rows[case['id']] for case in cases]
    methods = {method: method_metrics(ordered, method, len(cases)) for method in METHODS}
    status = 'completed' if all(x['count'] == len(cases) for x in methods.values()) else 'running'
    value = {'status': status, 'updated_at': utc_now(), 'active_method': active_method,
             'output_directory': str(EVIDENCE.relative_to(ROOT)).replace('\\', '/'),
             'ui_default_result_replaced': False if EVIDENCE != BASE_EVIDENCE else None,
             'dataset': {'count': len(cases), 'sha256': freeze['sha256'], 'scope': freeze['scope'],
                         'name': 'KO96 authored Korean technical-type development set'},
             'contract_sha256': CONTRACT_HASH, 'adapter_version': ADAPTER_VERSION,
             'engine_sha256': frozen_adapter()['engine_sha256'], 'methods': methods, 'rows': ordered, 'runs': runs,
             'method_notes': {
                 'semif': 'Actual pinned upstream SemIf SerialPrefixScorer on local GGUF, adapter korean-cached-contract-v2. The fixed contract moved into shared state and varying untrusted input into the question; this changes prompt arrangement as well as reusing prefix computation. Separate direct-pilot results are not combined. Scores are uncalibrated option-relative preferences.',
                 'json': 'Local Ollama constrained JSON output on the same GGUF model and frozen label contract; runtimes differ.',
                 'rules': 'Unmodified ml.engine.rule_baseline dictionary/regex comparator; no model inference.',
                 'failed_output': 'A completed request attempt with an error counts as incorrect; UNKNOWN is never used as a substitute for an error.',
                 'partial_denominator': 'Accuracy uses attempted rows, count. Not-yet-run rows are absent from each method and excluded until attempted.',
                 'retries': 'Existing attempts, including failures, are not rerun or replaced automatically.'}}
    atomic_json(EVIDENCE / 'evaluation.json', value)
    return value


def normalized_result(response, expected, method, wall_ms):
    frozen_adapter()
    label = response.get('label')
    if label not in LABELS:
        raise ValueError('Worker returned an invalid label.')
    if response.get('contract_sha256') != CONTRACT_HASH:
        raise ValueError('Worker response contract does not match frozen contract.')
    if response.get('external_inference') is not False:
        raise ValueError('Worker did not confirm local-only inference.')
    if method == 'semif':
        require_semif_identity(response)
    score = response.get('score')
    if method == 'semif' and (not isinstance(score, (int, float)) or isinstance(score, bool)
                              or not math.isfinite(score) or not 0 <= score <= 1):
        raise ValueError('Invalid SemIf option score.')
    latency = response.get('latency_ms')
    if not isinstance(latency, (int, float)) or not math.isfinite(latency) or latency < 0:
        raise ValueError('Worker did not return a valid measured latency.')
    return {'label': label, 'score': score, 'probabilities': response.get('probabilities', {}),
            'allowed_token_mass': response.get('allowed_token_mass'), 'latency_ms': latency,
            'wall_latency_ms': round(wall_ms, 3), 'status': response.get('status', 'needs_review'),
            'execution_status': 'completed', 'correct': label == expected,
            'source': response.get('source'), 'generated_tokens': response.get('generated_tokens'),
            'prompt_sha256': response.get('prompt_sha256'), 'contract_sha256': response.get('contract_sha256'),
            'cache_hit': response.get('cache_hit'), 'adapter_version': response.get('adapter_version'),
            'backend': response.get('backend'), 'semif_commit': response.get('semif_commit')}


def evaluate(args):
    global EVIDENCE
    EVIDENCE = output_directory(getattr(args, 'run_name', None))
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    print(json.dumps({'output_directory': str(EVIDENCE),
                      'result_file': str(EVIDENCE / 'evaluation.json'),
                      'reproduction': EVIDENCE != BASE_EVIDENCE,
                      'ui_default_result_replaced': False if EVIDENCE != BASE_EVIDENCE else None}, ensure_ascii=False), flush=True)
    lock_path = EVIDENCE / '.evaluation.lock'
    try:
        lock_handle = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError:
        raise SystemExit('Another evaluation lock exists. Inspect its PID and preserve raw evidence before removing a stale lock.')
    try:
        os.write(lock_handle, json.dumps({'pid': os.getpid(), 'started_at': utc_now()}).encode())
        os.close(lock_handle)
        freeze, cases = frozen_dataset()
        rows, runs = load_progress(freeze, cases)
        selected = METHODS if args.method == 'all' else (args.method,)
        if args.limit is not None and args.limit < 1:
            raise ValueError('--limit must be positive.')
        with httpx.Client(timeout=args.timeout, trust_env=False) as client:
            for method in selected:
                # Recheck files at each method boundary before issuing inference.
                checked_freeze, _ = frozen_dataset()
                if checked_freeze != freeze:
                    raise ValueError('Freeze manifest changed during evaluation.')
                pending = [case for case in cases if method not in rows[case['id']]['methods']]
                if args.limit:
                    pending = pending[:args.limit]
                if not pending:
                    print(json.dumps({'method': method, 'status': 'already_attempted', 'count': len(cases)}, ensure_ascii=False), flush=True)
                    continue
                health = None
                if method != 'rules':
                    response = client.get(WORKER_URL + '/health')
                    response.raise_for_status()
                    health = response.json()
                    if health.get('external_inference') is not False or health.get('busy'):
                        raise ValueError('Local worker is not ready for a sequential evaluation.')
                stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
                raw_path = EVIDENCE / f'run-{stamp}-{method}-rows.jsonl'
                run = {'id': stamp + '-' + method, 'method': method, 'started_at': utc_now(),
                       'run_name': getattr(args, 'run_name', None),
                       'status': 'running', 'planned_attempts': len(pending), 'attempted': 0,
                       'raw_file': str(raw_path.relative_to(ROOT)).replace('\\', '/'),
                       'dataset_sha256': freeze['sha256'], 'contract_sha256': CONTRACT_HASH,
                       'adapter_version': ADAPTER_VERSION, 'engine_sha256': frozen_adapter()['engine_sha256'],
                       'worker_health': health, 'timeout_seconds': args.timeout,
                       'rule_source_sha256': sha(ROOT / 'ml' / 'engine.py'),
                       'evaluator_sha256': STARTUP_EVALUATOR_SHA256, 'metrics_sha256': STARTUP_METRICS_SHA256,
                       'source_hash_scope': 'Source files captured once when this evaluator process imported its modules.'}
                runs.append(run)
                snapshot(freeze, cases, rows, runs, method)
                with raw_path.open('x', encoding='utf-8', newline='\n') as raw:
                    for index, case in enumerate(pending, 1):
                        started = time.perf_counter()
                        submitted = {key: case[key] for key in ('text', 'field_path', 'description')}
                        full_response = None
                        http_status = None
                        try:
                            if method == 'rules':
                                label = rule_baseline(**submitted)
                                elapsed = (time.perf_counter() - started) * 1000
                                result = {'label': label, 'correct': label == case['expected'],
                                          'status': 'completed', 'execution_status': 'completed',
                                          'latency_ms': round(elapsed, 6), 'source': 'ml.engine.rule_baseline'}
                            else:
                                response = client.post(WORKER_URL + '/classify', json={'method': method, **submitted})
                                http_status = response.status_code
                                full_response = response.json()
                                response.raise_for_status()
                                result = normalized_result(full_response, case['expected'], method, (time.perf_counter() - started) * 1000)
                        except Exception as error:
                            result = {'label': None, 'score': None, 'probabilities': {}, 'allowed_token_mass': None,
                                      'status': 'failed', 'execution_status': 'failed', 'correct': False,
                                      'latency_ms': round((time.perf_counter() - started) * 1000, 3),
                                      'error_type': type(error).__name__, 'error': str(error)[:500]}
                        raw_record = {'id': case['id'], 'method': method, 'timestamp': utc_now(),
                                      'dataset_sha256': freeze['sha256'], 'contract_sha256': CONTRACT_HASH,
                                      'adapter_version': ADAPTER_VERSION, 'engine_sha256': frozen_adapter()['engine_sha256'],
                                      'submitted': submitted, 'expected': case['expected'], 'slice': case['slice'],
                                      'result': result, 'http_status': http_status, 'worker_response': full_response}
                        raw.write(json.dumps(raw_record, ensure_ascii=False, allow_nan=False) + '\n')
                        raw.flush()
                        os.fsync(raw.fileno())
                        rows[case['id']]['methods'][method] = result
                        run['attempted'] = index
                        run['last_case_id'] = case['id']
                        current = snapshot(freeze, cases, rows, runs, method)
                        if index % 4 == 0 or index == len(pending) or result['execution_status'] == 'failed':
                            m = current['methods'][method]
                            print(json.dumps({'method': method, 'attempted': m['count'], 'total': len(cases),
                                              'correct': m['correct'], 'failed': m['failed'],
                                              'last_id': case['id'], 'last_label': result['label'],
                                              'last_latency_ms': result.get('latency_ms')}, ensure_ascii=False), flush=True)
                        # Do not hammer a locked worker or a stalled service after
                        # an error. The recorded error remains in the denominator.
                        if result['execution_status'] == 'failed' and not args.continue_on_error:
                            run['status'] = 'stopped_after_error'
                            run['finished_at'] = utc_now()
                            snapshot(freeze, cases, rows, runs, None)
                            raise RuntimeError(f'Evaluation stopped after recorded failure on {case["id"]}. Inspect raw evidence; no automatic retry.')
                run['status'] = 'completed'
                run['finished_at'] = utc_now()
                snapshot(freeze, cases, rows, runs, None)
        final = snapshot(freeze, cases, rows, runs, None)
        print(json.dumps({'status': final['status'], 'result_file': str(EVIDENCE / 'evaluation.json'),
                          'methods': {key: {field: value[field] for field in ('status', 'count', 'correct', 'accuracy', 'macro_f1')} for key, value in final['methods'].items()}}, ensure_ascii=False), flush=True)
    finally:
        lock_path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--method', choices=(*METHODS, 'all'), default='all')
    parser.add_argument('--run-name', type=validate_run_name,
                        help='Run/resume independent results in evidence/jev/reproductions/NAME; preserve packaged benchmark and UI default. Simple ASCII name only.')
    parser.add_argument('--limit', type=int, help='Attempt at most this many previously unattempted cases per selected method; remaining cases stay unrun.')
    parser.add_argument('--timeout', type=float, default=240, help='Per-worker-request timeout in seconds; default 240.')
    parser.add_argument('--continue-on-error', action='store_true', help='Explicitly continue after recording a failed call; never retries that case.')
    evaluate(parser.parse_args())


if __name__ == '__main__':
    main()
