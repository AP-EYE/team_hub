# 로컬 의미 분류 데모와 평가

## 현재 구현

공식 Jev API는 호출하지 않았다. SemIf(이전 OpenJev)는 TypeSafe와 무관한 독립 프로젝트다. 본 데모는 SemIf의 **선택지 토큰 logits를 한 번의 forward pass로 읽는 방식**을 참고하여 별도로 작성한 CPU 구현이다. SemIf 패키지를 실행한 결과나 Jev를 복제한 모델이라고 부르지 않는다.

- 모델: 공개 `Qwen/Qwen3-0.6B`, 고정 revision은 `evidence/model/upstream-versions.json`.
- 추론: Windows CPU, PyTorch/Transformers. 추론 시 `local_files_only=True`, `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`.
- 최초 모델 다운로드만 Hugging Face 공개 저장소에 접속한다. 외부 추론 API, 결제 API, 실제 개인정보를 사용하지 않는다.
- 응답: 8개 기술적 유형 중 하나와 선택지 조건부 점수. 이 점수는 보정된 정확도나 법적 확신도가 아니다.
- `status=needs_review`: 결과는 사람이 확인할 후보이며 인가 정책 변경, 차단, 법률 판단, CIM 매핑 승인에 직접 사용하지 않는다.
- 데이터 크기 초과 시 조용히 잘라서 판단하지 않고 오류를 반환한다.

## 실행

프로젝트 루트에서 PowerShell:

```powershell
./ml/setup.ps1
.venv-model/Scripts/python.exe -m ml.evaluate --limit 4 --name smoke
.venv-model/Scripts/python.exe -m ml.evaluate --name evaluation
.venv-model/Scripts/python.exe -m ml.diagnose
.venv-model/Scripts/python.exe -m ml.worker --port 8812
```

이미 설치와 다운로드가 완료된 이 작업 PC에서는 `setup.ps1`을 다시 실행할 필요가 없다. 실행 중인 worker 상태는 `http://127.0.0.1:8812/health`로 확인한다.

분류 API:

```http
POST http://127.0.0.1:8812/classify
Content-Type: application/json

{"text":"지난달 당뇨 진단을 받았습니다.","field_path":"memo","description":"가상 회원 상담 내용"}
```

서버는 loopback에만 바인딩하고, 요청 본문을 로그에 기록하지 않는다. `ml.adapter.classify()`는 표준 라이브러리 HTTP 클라이언트만 사용하며 worker가 없으면 `status=unavailable`을 반환한다. 규칙 결과를 모델 결과로 대체하지 않는다.

`POST /normalize`에 `{"field_path":"customer_no","description":"응답 정보주체인 회원 식별자"}`를 보내면 `canonical_field`, `probabilities`, `approved:false`를 반환한다. 선택지는 `data_subject.id`, `person.phone`, `person.address`, `resource.order.id`, `unknown`이다. 프로젝트용 의미 스키마이며 Splunk CIM 공식 필드를 그대로 구현했다는 뜻은 아니다. 모델 제안을 승인된 매핑 레지스트리에 자동 반영하지 않는다.

## 고정 평가 설계

`ml/fixtures.jsonl`에 사람이 작성한 합성 한국어 24개를 고정했다. 정답, 근거, slice가 각 행에 있다. 단순 정규식/키워드 기준과 모델이 동일한 입력을 받아 비교된다. 학습이나 파인튜닝은 하지 않았다.

- 개인 건강 상태와 일반 건강 조언을 구별한다.
- 무종교·질환 부재 등 부정 표현도 해당 개인에 대한 정보임을 평가한다.
- 종교 관광지 언급만으로 신앙을 단정하지 않는지 평가한다.
- 서비스 회원 UUID와 주민등록·여권 등 법정 고유식별정보 유형을 구별한다.
- 설명 없는 `id`는 UNKNOWN, 주문 `id`와 회원 `id`는 서로 다르게 분류한다.
- 값 없이 스키마만으로 가능한 유형 분류와, 자유 메모의 실제 값이 있어야 가능한 분류를 구별한다.
- 입력 안의 프롬프트 주입을 따라 일반 정보로 오분류하지 않는지 한 사례를 시험한다.

실제 개인정보나 유효한 신분증 번호는 없다. 신분증 관련 사례는 필드 **의미**를 분류하며 번호 진위나 체크섬 검증 성능을 의미하지 않는다. 예시 이름·식별자는 모두 합성이다. 이러한 작은 작성자 평가셋은 실제 서비스 정확도를 입증하지 않는다. 별도 블라인드 평가셋, 두 명 이상 라벨링, 분포가 다른 API와 더 큰 모델 검증이 필요하다.

`ml/normalize-fixtures.jsonl`의 별도 8건은 필드명과 설명만으로 CIM 매핑을 제안하는 실험이다. `id`의 모호함과 요청자 ID/정보주체 ID 차이를 포함한다. 전체 평가 명령이 동일 모델 인스턴스로 이 8건까지 실행한다.

## 결과 및 해석

2026-09-22 실제 실행 결과:

| 실행 | 정답 수 | 정확도 | 추가 지표 |
|---|---:|---:|---|
| 초기 분류 smoke | 0 / 4 | 0% | 실행 자체는 완료, 의미 정확도는 실패 |
| 고정 24건 단순 규칙 | 19 / 24 | 79.17% | macro F1 0.7370 |
| 고정 24건 로컬 모델 | 3 / 24 | 12.50% | macro F1 0.0278; 전부 OTHER 예측 |
| 별도 8건 AI 필드 매핑 | 2 / 8 | 25.00% | 전부 unknown 제안 |
| 짧은 영어/한국어 개발 진단 | 2 / 4 | 50% | 전체 평가와 독립 성능 지표로 합치지 않음 |

24건 분류 추론 지연 중간값은 **7.052초**, p95는 **16.825초**였다. 매핑 8건 중간값은 **6.501초**다. 고정 선택지로 결과를 받는 기술적 연결은 동작했지만, 이 모델과 현재 프롬프트는 자동 분류 및 자동 필드 매핑 기준에 **불합격**이다. 규칙 비교기도 일반 건강 조언, 관광 장소, 부정 설명의 계정 ID 등에 오답이 있어 최종 판정기로 쓰지 않는다.

토큰 읽기 오류 가능성도 확인했다. 진단 5건에서 선택지 토큰의 round-trip 및 프롬프트 뒤 토큰화 경계 검사가 모두 통과했다. 원래 건강 사례의 제약 없는 상위 토큰도 `G`(OTHER) 0.5499, `H`(UNKNOWN) 0.2742, `A`(HEALTH) 0.1731로 나왔다. 따라서 최소한 이 사례에서는 출력 접두사를 잘못 읽은 것이 아니라 모델이 실제로 오답을 선호했다. 더 짧은 2선택지 질문에서도 회원 ID를 전화번호로, 일반 조언을 개인 건강 정보로 오분류했다. 프롬프트/모델/런타임을 완전히 분리한 원인 규명이 완료됐다는 뜻은 아니다.

프롬프트 주입 사례에서 오답 OTHER에 대한 조건부 점수가 0.9821이었다. 높은 모델 점수를 자동 승인 근거로 쓸 수 없다는 구체적 실패 증거다. 이 평가셋의 오답을 보고 점수를 올리기 위해 정답표를 규칙에 추가하거나 프롬프트를 수정하지 않았다.

실측 결과는 `evidence/model/evaluation-summary.json`, 행별 예측·지연·확률·프롬프트 해시는 `evidence/model/evaluation-rows.jsonl`에 저장된다. 모델 로딩 시간은 행별 추론 지연과 분리된다. 가장 첫 추론은 캐시 준비 영향을 포함하며 GPU를 사용하지 않는다.

여기서 `model_load_seconds`는 tokenizer/가중치 로딩 시간이고 Python/torch/transformers import 시간은 포함하지 않는다. 이 Windows 환경에서 최초 라이브러리 import가 수분 걸린 사실을 관측했다. 지연값은 여러 개발 서비스가 동작한 PC에서의 단일 측정이며 통제된 처리량 벤치마크로 해석하지 않는다. 정답 수와 지연은 실행 증거 파일의 실제 값만 사용한다.

`ml/diagnose.py`는 고정 평가와 분리된 개발 진단이다. 원래 8분류 프롬프트와 짧은 영어/한국어 2선택지 질문의 결과를 비교하고, 선택지 토큰 round-trip/프롬프트 경계 및 제약 없는 상위 5토큰을 저장한다. 첫 4건 오답을 보고 시작한 진단이므로 독립 검증셋이라고 부르지 않는다. 기존 smoke와 본 평가 오답을 유지한다.

모델 점수는 8개 선택지 사이의 조건부 softmax다. 높은 점수로 틀릴 수 있으므로 문서나 UI에서 “정답 확률”로 표시해서는 안 된다. 법률상 개인정보 해당 여부와 결합 특정성의 최종 판단도 이 분류 정확도 지표의 범위 밖이다.

## 프로젝트 착수 판단

로그 기록과 결정적 인가 검사, 사람이 승인한 CIM 매핑은 모델 성능과 독립적으로 개발할 수 있다. 이 모델은 비동기 후보 제안용 실험 모듈이다. 로컬 분류가 규칙보다 우수한지는 실제 결과를 보고 판단하며, 데모를 성공으로 보이게 하려고 오답을 숨기거나 모델 이름을 바꾸지 않는다.

**개발 착수 가능 / AI 자동 적용 보류**가 이번 결과다. 첫 개발 주기에는 (1) 별도 블라인드 한국어 데이터와 다중 검토자 정답, (2) 작업을 좁힌 이진 분류, (3) 같은 데이터에서 더 큰 로컬 모델 및 양자화 런타임 비교, (4) 오탐·미탐·기권률·지연을 포함한 사전 합격 기준을 준비하는 것이 좋다. 모델 결과가 없어도 로그, 승인된 정규화, 인가 검증, 결정적 식별자 기반 결합은 계속 동작해야 한다.

## 1차 자료

- [TypeSafe Jev 소개](https://docs.typesafe.ai/introduction): 공식 hosted 서비스의 구조화된 판단 인터페이스.
- [SemIf 공식 저장소](https://github.com/TheoLeeCJ/SemIf): 독립 구현, 모델·하드웨어·측정 범위 및 조건부 확률의 한계.
- [고정 SemIf 방법론 문서](https://github.com/TheoLeeCJ/SemIf/blob/1f2dea3e25379f9dfc98cb83c324f00ab5deda37/docs/METHOD.md): direct option scoring 방법 참고. 로컬 스냅샷은 `evidence/model/semif-method.md`.
- [Qwen3-0.6B 공식 모델 카드](https://huggingface.co/Qwen/Qwen3-0.6B): 모델 가중치와 라이선스. 실제 다운로드 파일 해시는 `evidence/model/model-manifest.json`.

조사일: 2026-09-22. 모델·방법의 공개 성능 수치는 본 PC에서 측정한 값과 혼합하지 않는다.
