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
import sys
import time
import uuid

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.engine import rule_baseline
from ml_jev.engine import CONTRACT_HASH
from ml_jev.metrics import LABELS, method_metrics

EVIDENCE = ROOT / 'evidence' / 'jev'
METHODS = ('semif', 'json', 'rules')
WORKER_URL = 'http://127.0.0.1:8814'


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen_dataset():
    freeze = json.loads((EVIDENCE / 'dataset-frozen.json').read_text(encoding='utf-8-sig'))
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
            if case_id in rows and method in METHODS and method not in rows[case_id]['methods']:
                rows[case_id]['methods'][method] = saved['result']
    return rows, runs


def snapshot(freeze, cases, rows, runs, active_method=None):
    # Expose pending rows as absent methods, never as fabricated incorrect calls.
    ordered = [rows[case['id']] for case in cases]
    methods = {method: method_metrics(ordered, method, len(cases)) for method in METHODS}
    status = 'completed' if all(x['count'] == len(cases) for x in methods.values()) else 'running'
    value = {'status': status, 'updated_at': utc_now(), 'active_method': active_method,
             'dataset': {'count': len(cases), 'sha256': freeze['sha256'], 'scope': freeze['scope'],
                         'name': 'KO96 authored Korean technical-type development set'},
             'contract_sha256': CONTRACT_HASH, 'methods': methods, 'rows': ordered, 'runs': runs,
             'method_notes': {
                 'semif': 'Actual pinned upstream SemIf direct candidate-token scoring on local GGUF; scores are uncalibrated option-relative preferences.',
                 'json': 'Local Ollama constrained JSON output on the same GGUF model and frozen label contract; runtimes differ.',
                 'rules': 'Unmodified ml.engine.rule_baseline dictionary/regex comparator; no model inference.',
                 'failed_output': 'A completed request attempt with an error counts as incorrect; UNKNOWN is never used as a substitute for an error.',
                 'partial_denominator': 'Accuracy uses attempted rows, count. Not-yet-run rows are absent from each method and excluded until attempted.',
                 'retries': 'Existing attempts, including failures, are not rerun or replaced automatically.'}}
    atomic_json(EVIDENCE / 'evaluation.json', value)
    return value


def normalized_result(response, expected, method, wall_ms):
    label = response.get('label')
    if label not in LABELS:
        raise ValueError('Worker returned an invalid label.')
    if response.get('contract_sha256') != CONTRACT_HASH:
        raise ValueError('Worker response contract does not match frozen contract.')
    if response.get('external_inference') is not False:
        raise ValueError('Worker did not confirm local-only inference.')
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
            'prompt_sha256': response.get('prompt_sha256'), 'contract_sha256': response.get('contract_sha256')}


def evaluate(args):
    EVIDENCE.mkdir(parents=True, exist_ok=True)
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
                       'status': 'running', 'planned_attempts': len(pending), 'attempted': 0,
                       'raw_file': str(raw_path.relative_to(ROOT)).replace('\\', '/'),
                       'dataset_sha256': freeze['sha256'], 'contract_sha256': CONTRACT_HASH,
                       'worker_health': health, 'timeout_seconds': args.timeout,
                       'rule_source_sha256': sha(ROOT / 'ml' / 'engine.py'),
                       'evaluator_sha256': sha(Path(__file__)), 'metrics_sha256': sha(Path(__file__).with_name('metrics.py'))}
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
        print(json.dumps({'status': final['status'], 'methods': {key: {field: value[field] for field in ('status', 'count', 'correct', 'accuracy', 'macro_f1')} for key, value in final['methods'].items()}}, ensure_ascii=False), flush=True)
    finally:
        lock_path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--method', choices=(*METHODS, 'all'), default='all')
    parser.add_argument('--limit', type=int, help='Attempt at most this many previously unattempted cases per selected method; remaining cases stay unrun.')
    parser.add_argument('--timeout', type=float, default=240, help='Per-worker-request timeout in seconds; default 240.')
    parser.add_argument('--continue-on-error', action='store_true', help='Explicitly continue after recording a failed call; never retries that case.')
    evaluate(parser.parse_args())


if __name__ == '__main__':
    main()
