"""Write briefing results solely from persisted measurements."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8-sig'))


def main():
    integration = read('evidence/integration-tests.json')
    direct = read('evidence/model/evaluation-summary.json')
    alias = read('evidence/model/normalize-summary.json')
    latency = read('evidence/latency-smoke.json')
    alternative_alias = read('evidence/model-alternative/normalize-summary.json') if (ROOT / 'evidence/model-alternative/normalize-summary.json').exists() else None
    live = read('evidence/live-classification-validation.json') if (ROOT / 'evidence/live-classification-validation.json').exists() else None
    forms = read('evidence/final-api-smoke.json') if (ROOT / 'evidence/final-api-smoke.json').exists() else None
    ui = read('evidence/ui/ui-validation.json') if (ROOT / 'evidence/ui/ui-validation.json').exists() else None
    ui_note = f"브라우저 화면 검사 {sum(check['passed'] for check in ui['checks'])}/{len(ui['checks'])} 통과. 데스크톱·390px 모바일의 5개 탭, 모델 선택기, 실제 측정값, 증거 연결을 확인했다. 근거: evidence/ui/ui-validation.json 및 같은 폴더의 화면 캡처." if ui else '브라우저 화면 검사는 아직 기록되지 않았다.'
    forms_note = f"별도 게이트웨이 폼 입력 검사는 {forms['passed']}/{forms['count']} 통과했다. 회원 식별자라고 설명한 customer_no를 unknown으로 보류한 1건을 evidence/final-api-smoke.json에 보존했다. 모든 요청은 실제 로컬 모델에 전달되었으며 승인된 매핑·인가 판정·관측 로그는 변경되지 않았다. 이 추가 입력 검사는 위의 60개 기능 검사와 구분한다." if forms else '게이트웨이 폼 입력 검사는 아직 기록되지 않았다.'
    live_note = f"실제 게이트웨이 응답의 추가 확인은 {live['correct']}/{live['count']}건 일치했다. 오류 사례: {', '.join(live['classification_errors']) or '없음'}. 고정 24건의 점수를 실제 입력 전반에 일반화하면 안 된다." if live else '실제 응답별 결과는 대시보드의 모델 후보와 증거 ID를 확인한다.'
    alias_note = f"선택한 대안 모델의 필드 통일 제안은 {alternative_alias['correct']}/{alternative_alias['count']}건 일치했다. 필드 설명이 없는 mobile_no를 unknown으로 보류한 사례는 오답으로 보존했다." if alternative_alias else '대안 모델 매핑 결과는 별도 평가 파일을 확인한다.'
    rows = [f"| 분류 비교용 키워드 규칙 | {round(direct['baseline']['accuracy']*direct['baseline']['n'])}/{direct['baseline']['n']} | {direct['baseline']['accuracy']*100:.2f}% | 측정하지 않음 |", f"| Qwen3-0.6B 선택지 점수 | {round(direct['model']['accuracy']*direct['model']['n'])}/{direct['model']['n']} | {direct['model']['accuracy']*100:.2f}% | {direct['latency_ms']['median']/1000:.3f}초 |"]
    for path in sorted((ROOT / 'evidence/model-alternative').glob('*fixtures-metrics.json')):
        result = json.loads(path.read_text(encoding='utf-8-sig'))
        if result.get('count') == 24:
            rows.append(f"| {path.stem.replace('-fixtures-metrics','')} JSON 생성 | {result['correct']}/{result['count']} | {result['accuracy']*100:.2f}% | {result['median_latency_ms']/1000:.3f}초 |")
    text = f'''# 실행 결과와 프로젝트 착수 판단

검증일: 2026-09-22. 실서비스가 아닌 이 PC의 합성 API·가상 계정·합성 개인정보를 대상으로 실제 실행했다.

## 판단

**4인 프로젝트 착수를 위한 통합 PoC는 실행 가능하다.** 로그·정책·정규화·결합·보고서를 연결하는 구조는 동작한다. AI 품질은 모델 선택에 따라 크게 달라지며, 자동 적용을 약속하기 전에 독립 평가와 검토 절차를 확보해야 한다. 이 데모는 제품 완성이나 범용 API 탐지 정확도를 인증하지 않는다.

## 교수 피드백에 대한 실제 증거

| 질문 | 확인한 결과 | 증거 |
|---|---|---|
| 요청·응답을 별도 로깅할 수 있는가? | PostgreSQL에 실행·응답·판정·필드 관측·모델 후보를 저장 | gateway/store.py, evidence/integration-tests.json |
| 이후 사고 조사에 활용 가능한가? | 이전 실행의 Bob 응답 5건·관측 정보주체 3명을 재전송 없이 집계 | evidence/investigations/42666dfe9f744b6a-bob.json |
| 이름이 다른 필드를 통일할 수 있는가? | 승인된 회원/연락처/주소 매핑 12개를 적용하고 AI 후보를 별도로 시험 | gateway/privacy.py, evidence/model/normalize-summary.json, 대안 모델 결과 |
| 로컬 분류 모델이 작동하는가? | 외부 추론 API 없이 실제 모델 실행. 작은 모델의 심각한 오분류를 확인하고 대안 비교 | evidence/model/, evidence/model-alternative/ |
| DB에서 정보가 결합되는가? | 같은 실행·요청자·테넌트·회원 체계에서 노출된 필드만 SQL로 연결 | gateway/store.py, 통합 평가 |

## 인가·저장 검증

- 통합 검사: **{integration['passed']}/{integration['total']} {integration['status']}**.
- 별도 의미론 단위 테스트: **{integration['unit_tests']['tests_run']}개 통과**. 통합 검사 안에도 이 단위 테스트 묶음의 성공 여부가 포함되므로 두 수를 단순 합산하지 않는다.
- 취약 모드 16개: 위반 확인 5, 정상 8, 차단 2, 검토 1.
- 수정 모드 16개: 위반 확인 0, 정상 9, 차단 6, 검토 1.
- BOLA 3, BFLA 1, BOPLA 1이 취약 모드에서 확인됐다. 동일한 16개 사례를 수정 모드에서 재실행했다.
- 공개 프로필·공유 문서·관리자 정상 접근에서 경보하지 않았다.
- 신원 불일치 또는 빈 HTTP 200만으로 확정하지 않고, 요청 객체와 실제 반환 자료의 대응을 확인했다.
- alpha:U100과 beta:U100을 분리하고, 서로 다른 요청자가 받은 데이터를 섞지 않았다.
- 토큰/쿠키/쿼리 값이 저장·보고서에 남지 않는지, DB 장애 시 증거 저장 성공을 주장하지 않는지 확인했다.

이 비율은 미리 검토한 정책과 합성 사례의 기능 검사다. 공개/공유 API 전체에서 오탐 0%, 어떤 서비스에서든 탐지율 100%라는 의미가 아니다.

{ui_note}

## AI 비교

| 방법 | 정답 | 정확도 | 중앙 처리 시간 |
|---|---:|---:|---:|
{chr(10).join(rows)}

- 기준선과 모델은 동일한 작성자 합성 한국어 24건을 사용했다. 별도 블라인드 평가셋이 아니다.
- 0.6B 방식은 공식 Jev나 SemIf 실행 결과가 아니라 공개 모델의 선택지 점수를 읽는 독립 구현이다. 분류는 모두 OTHER, 8건 CIM 매핑은 {round(alias['accuracy']*alias['n'])}/{alias['n']}이며 모두 unknown으로 나왔다. **이 설정의 자동 적용은 부적합**하다.
- 대안은 로컬 Ollama의 JSON 생성 방식이며 Jev의 속도·보정·구조를 재현했다고 주장하지 않는다. 모델 크기·양자화·런타임·출력 방식이 함께 달라져 어느 한 요소의 효과만 분리한 실험은 아니다.
- 예측을 보고 평가 정답을 바꾸거나 오답을 제외하지 않았다. 실제 실패·중단된 실행은 별도 파일로 보존했다.
- 규칙은 분류 비교용 `ml.engine.rule_baseline`이며 gateway/privacy.py의 운영 경로 규칙과 같은 평가를 수행한 것으로 읽으면 안 된다.
- 학습·파인튜닝은 수행하지 않았다. 정형 필드와 문맥 필드를 분리하고 큰 모델을 비교하는 단계가 먼저 필요하다.
- 모델 결과와 CIM 제안은 모두 후보이며 자동 인가 판단·차단·매핑 승인에 사용하지 않는다.
- {alias_note}
- {live_note}
- {forms_note}
- 4B 고정 평가의 건강 스키마 및 프롬프트 주입이 포함된 상담 문장 실패를 보존했다. 프롬프트 주입에 안전한 분류기라고 주장하지 않는다.

## 지연 측정과 발견한 실패

- 작은 JSON, 단일 클라이언트, 워밍업 3회 후 30회 측정.
- 직접 업무 API: 중앙값 {latency['direct']['p50_ms']:.3f}ms, p95 {latency['direct']['p95_ms']:.3f}ms.
- 프록시+PostgreSQL 기록: 중앙값 {latency['gateway_with_postgres_logging']['p50_ms']:.3f}ms, p95 {latency['gateway_with_postgres_logging']['p95_ms']:.3f}ms.
- LLM은 별도 비동기 경로에 있으며 위 수치에 모델 추론을 포함하지 않는다. TLS·동시 부하·운영 SLA 측정은 아니다.
- 첫 연속 요청 시험에서 DB 새 연결 시간 초과가 발생했다. 연결 풀을 도입한 뒤 30회가 성공했다. evidence/benchmark-first-failure.md에 실패를 남겼다.
- 회귀 중 Windows 연결 중단 1건은 원인이 확정되지 않았다. 서버 상태 확인 후 코드 변경 없이 한 차례 재실행해 통과했고, 실패 원본은 evidence/integration-pool-first-failure.json에 보존했다.

## 착수 전에 합의할 사항

1. 핵심 성과를 **검토된 정책에 따른 인가 검증 + 관측 응답의 개인정보 항목 연결**로 정한다.
2. AI는 개인정보/필드 의미의 검토 지원으로 시작한다. 독립 한국어 평가를 통과한 범위만 점진적으로 자동화한다.
3. 개인정보 원문 보존 목적·권한·암호화·보존 기간을 먼저 정한다. 지금처럼 마스킹하면 과거 원문 전체를 다시 분석할 수 없다.
4. 실제 서비스 담당자가 승인한 권한과 데이터 관계를 입력받는다. 정규화된 필드명만으로 권한이나 동일인을 추측하지 않는다.
5. 다음 개발에서는 기존 게이트웨이 addon, 내구성 있는 작업 큐, 관리 화면 인증, 대시보드 접근 통제, 부하와 장애 시험을 추가한다.

팀별 역할과 제안 일정은 kickoff-plan.md를 따른다. 브리핑에서는 성공 수치와 AI 실패 수치를 함께 보여주는 것이 이 데모의 정확한 설명이다.
'''
    (ROOT / 'docs/demo-results.md').write_text(text, encoding='utf-8')
    print('Wrote docs/demo-results.md from measured evidence')


if __name__ == '__main__':
    main()
