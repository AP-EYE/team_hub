"""Audit completed local predictions and write a factual Korean results report."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from .evaluate import frozen_dataset, load_progress, snapshot, METHODS
from .metrics import method_metrics

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evidence/jev'
NAMES = {'semif': '실제 SemIf · 로컬 Qwen3 4B', 'json': 'Ollama JSON · 같은 GGUF', 'rules': '기존 사전·정규식'}


def duration(value):
    return f'{value:.3f}ms' if value < 1000 else f'{value / 1000:.3f}초'


def main():
    if (EVIDENCE / '.evaluation.lock').exists():
        raise RuntimeError('Do not finalize an active evaluation')
    freeze, cases = frozen_dataset()
    previous_bytes = (EVIDENCE / 'evaluation.json').read_bytes()
    previous = json.loads(previous_bytes)
    rows, runs = load_progress(freeze, cases)
    for method in METHODS:
        measured = method_metrics(list(rows.values()), method, len(cases))
        if measured['count'] != len(cases):
            raise RuntimeError(f'{method} has not attempted the complete frozen dataset')
        if measured != previous['methods'][method]:
            raise RuntimeError('Recomputed metrics disagree with preserved aggregate')
    raw_rows = [json.loads(line) for path in sorted(EVIDENCE.glob('run-*-rows.jsonl'))
                for line in path.read_text(encoding='utf-8').splitlines() if line]
    runtime = json.loads((EVIDENCE / 'runtime-provenance.json').read_text(encoding='utf-8'))
    manifest_path = ROOT / '.runtime/ollama-models/manifests/registry.ollama.ai/library/qwen3/4b-q4_K_M'
    manifest = json.loads(manifest_path.read_text())
    layer = next(item for item in manifest['layers'] if item['mediaType'] == 'application/vnd.ollama.image.model')
    if layer['digest'] != 'sha256:' + runtime['gguf_sha256']:
        raise RuntimeError('Ollama model mapping differs from the pinned GGUF')
    ollama_identity = json.loads((EVIDENCE / 'ollama-model-identity.json').read_text(encoding='utf-8'))
    if not ollama_identity['matches_jev_gguf'] or runtime['gguf_sha256'] not in ollama_identity['modelfile_blob_hashes']:
        raise RuntimeError('Observed Ollama server identity does not match the pinned GGUF')
    identities = Counter((row['method'], row['id']) for row in raw_rows)
    if len(identities) != len(cases) * len(METHODS) or any(n != 1 for n in identities.values()):
        raise RuntimeError('Duplicate or missing raw attempts')
    for row in raw_rows:
        expected_case = next(case for case in cases if case['id'] == row['id'])
        if row['dataset_sha256'] != freeze['sha256']:
            raise RuntimeError('Raw dataset mismatch')
        if row['submitted'] != {key: expected_case[key] for key in ('text', 'field_path', 'description')}:
            raise RuntimeError('Recorded model input differs from frozen case or contains gold metadata')
        if row['result']['correct'] != (row['result'].get('label') == expected_case['expected']):
            raise RuntimeError('Raw correctness mismatch')
        if row['method'] != 'rules' and row['result'].get('execution_status') == 'completed':
            response = row['worker_response']
            if response.get('external_inference') is not False:
                raise RuntimeError('Local inference provenance missing')
            if row['method'] == 'semif':
                if response['raw']['model']['gguf']['sha256'] != runtime['gguf_sha256']:
                    raise RuntimeError('Actual loaded SemIf GGUF differs from pinned model')
                if len(response['probabilities']) != 8 or abs(sum(response['probabilities'].values()) - 1) > 1e-6:
                    raise RuntimeError('Invalid normalized option distribution')
                if response['generated_tokens'] != 0:
                    raise RuntimeError('Unexpected generated tokens in SemIf')
    # Enrich identity fields from verified raw results; predictions and metrics
    # must remain identical. The evaluator preserves every original JSONL.
    data = snapshot(freeze, cases, rows, runs)
    audit = {'status': 'PASS', 'at': datetime.now(timezone.utc).isoformat(),
             'raw_attempts': len(raw_rows), 'cases_per_method': len(cases),
             'metrics_recomputed_unchanged': True, 'raw_predictions_unchanged': True,
             'prior_aggregate_sha256': hashlib.sha256(previous_bytes).hexdigest(),
             'aggregate_sha256': hashlib.sha256((EVIDENCE / 'evaluation.json').read_bytes()).hexdigest(),
             'dataset_sha256': freeze['sha256'],
             'gguf_sha256': runtime['gguf_sha256'],
             'same_gguf_basis': 'Computed SemIf loaded-model hashes in raw replies, observed loopback Ollama /api/show model identity, and local manifest mapping checked at finalization.',
             'scorer_identity': 'Verified actual upstream SerialPrefixScorer, cached v2 only',
             'loaded_evaluator_provenance': 'evaluator-provenance.json',
             'interpretation': 'Authored development set; not a heldout estimate of Korean PII accuracy.'}
    (EVIDENCE / 'final-audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    output = ['# 한국어 분류 실제 실행 결과', '',
              '공식 TypeSafe Jev의 성능 평가가 아니다. 실제 SemIf와 로컬 Qwen3-4B Q4_K_M의 이번 설정을 평가했다.', '',
              '합성 개발 사례 96개(8유형 × 12개)를 각각 실행했다. 독립적인 미공개 평가셋·전문가 검수 결과는 아니다. 초기 직접 점수 pilot은 제외했다.', '',
              '| 방법 | 맞힌 수 / 시도 | 정확도 | macro F1 | 실행 오류 | 중앙값 | p95 |',
              '|---|---:|---:|---:|---:|---:|---:|']
    for method, name in NAMES.items():
        m = data['methods'][method]
        output.append(f"| {name} | {m['correct']} / {m['count']} | {m['accuracy']:.1%} | {m['macro_f1']:.3f} | {m['failed']} | {duration(m['latency_ms']['median'])} | {duration(m['latency_ms']['p95'])} |")
    output += ['', '시간은 다른 프로그램도 실행 중인 이 Windows PC에서 관찰한 값이다. 전용 장비·동시 부하·cold/warm 조건을 통제한 제품 벤치마크가 아니다. SemIf의 모델 시작 시간은 요청 밖이며 공통 prefix의 첫 계산은 첫 요청에 포함된다. Ollama의 첫 요청에는 모델 로딩이 포함될 수 있다. 두 방식은 같은 GGUF를 쓰지만 프롬프트 배치·런타임·출력 방법이 다르다.', '',
               'JSON 평가 중 Ollama 서버에 현재 작업자 외의 클라이언트 연결도 관측했다. 연결만으로 실제 동시 추론을 확정하지는 않지만, 단독 클라이언트 조건을 검증한 실험은 아니다. 다른 프로세스를 종료하거나 이 조건을 숨기지 않았다. 지연 차이를 SemIf 또는 JSON 방식 자체의 우열로 환산하지 않는다. [실행 환경 관찰 기록](../evidence/jev/resource-observations.jsonl)', '',
               '## 유형별 결과', '', '| 기대 유형 | SemIf 정답 | SemIf 정밀도 | SemIf 재현율 | JSON 정답 | 규칙 정답 |', '|---|---:|---:|---:|---:|---:|']
    per_label = {item['label']: item for item in data['methods']['semif']['per_label']}
    for label in data['methods']['semif']['confusion_matrix']:
        values = [data['methods'][method]['confusion_matrix'][label][label] for method in METHODS]
        quality = per_label[label]
        output.append(f"| {label} | {values[0]} / 12 | {quality['precision']:.1%} | {quality['recall']:.1%} | {values[1]} / 12 | {values[2]} / 12 |")
    output += ['', '정밀도는 그 유형으로 분류한 결과 중 맞은 비율이다. 정답 사례 12개를 모두 찾아도 다른 유형을 잘못 포함하면 정밀도는 낮아진다.']
    m = data['methods']['semif']
    output += ['', '## 문맥과 정보 부족', '', '| 사례 종류 | 맞힌 수 / 시도 |', '|---|---:|']
    for group in m['slices']:
        output.append(f"| {group['slice']} | {group['correct']} / {group['count']} |")
    empty_cases = [case for case in cases if not case['text'].strip()]
    empty_correct = sum(rows[case['id']]['methods']['semif']['correct'] for case in empty_cases)
    output += ['', f"원래부터 값이 비어 있는 입력은 {len(empty_cases)}건이며 SemIf가 {empty_correct}건을 맞혔다. 이는 원래 입력 조건으로 작성한 기대값과 비교한 결과다. 값이 있던 입력에서 나중에 값을 제거하는 세 모드 시연과는 별도다."]
    output += ['', f"대조쌍은 두 입력을 모두 맞힌 경우를 성공으로 계산한다: {m['contrast_pairs']['both_correct']} / {m['contrast_pairs']['evaluated_pairs']}쌍.", '',
               '## 오분류의 성격', '', '| 진단 항목 | 사례 수 |', '|---|---:|',
               f"| 일반 정보(OTHER)를 개인 관련 유형으로 분류 | {len(m['diagnostics']['personal_type_false_alarms_on_other'])} |",
               f"| 건강 정보를 다른 유형 또는 오류로 반환 | {len(m['diagnostics']['health_misses'])} |",
               f"| 건강·종교·정부번호 유형을 OTHER·UNKNOWN·오류로 반환 | {len(m['diagnostics']['sensitive_underflags'])} |",
               f"| 정보 부족(UNKNOWN)이 기대값인데 다른 유형으로 단정 | {len(m['diagnostics']['unsupported_assertions_on_unknown'])} |", '',
               '항목은 서로 겹칠 수 있다. UNKNOWN은 실제 운영에서 검토 대상으로 남기므로, 이를 바로 개인정보가 없다는 결론으로 해석하면 안 된다. 모든 실시간 모델 출력은 현재 needs_review다.', '',
               '## 높은 점수도 검토가 필요한 이유', '',
               f"선택지 점수가 90% 이상인 오분류는 {len(m['high_confidence_errors'])}건이다. 이 값은 선택지 사이의 상대 선호도이며 정답 확률로 보정하지 않았다.", '',
               '| 후보로 남기는 점수 기준 | 후보 수 | 후보 내 정답 | 후보 내 정확도 | 검토 수 |', '|---|---:|---:|---:|---:|']
    for threshold in m['thresholds']:
        accuracy = f"{threshold['selective_accuracy']:.1%}" if threshold['selective_accuracy'] is not None else '계산 불가'
        output.append(f"| {threshold['threshold']:.0%} | {threshold['accepted']} | {threshold['correct']} | {accuracy} | {threshold['review']} |")
    output += ['', 'UNKNOWN과 실행 오류는 위 후보에서 항상 제외한다. 임계값은 분석용이며 인가·법적 판단·실제 자동 승인을 바꾸지 않는다.', '',
               '## 실제 SemIf 오분류 전체', '', '| 사례 ID | 기대 | 실제 | 선택지 점수 |', '|---|---|---|---:|']
    for case in cases:
        r = rows[case['id']]['methods']['semif']
        if not r['correct']:
            score = f"{r['score']:.2%}" if isinstance(r.get('score'), (int, float)) else '없음'
            output.append(f"| {case['id']} | {case['expected']} | {r.get('label') or '실행 오류'} | {score} |")
    output += ['', '원문·기대 이유·8개 선택지 점수는 실험실에서 사례 ID를 검색해 확인할 수 있다. 오류 사례만 바꾸거나 제거해서 성적을 다시 집계하지 않았다.', '',
               '## 근거와 재현', '',
               '- [원본 평가와 사례별 결과](../evidence/jev/evaluation.json)',
               '- [288개 원본 시도 대조 감사](../evidence/jev/final-audit.json)',
               '- [실행 당시 평가기와 강화 후 코드의 구분](../evidence/jev/evaluator-provenance.json)',
               '- [시연·설치·새 이름으로 재현하기](korean-jev-demo.md)',
               '- [실제 구현 아키텍처](korean-classification-architecture.md)', '']
    (ROOT / 'docs/korean-jev-results.md').write_text('\n'.join(output), encoding='utf-8')
    print(json.dumps({'audit': audit, 'methods': {method: {k: data['methods'][method][k] for k in ('count', 'correct', 'failed', 'accuracy')} for method in METHODS}}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
