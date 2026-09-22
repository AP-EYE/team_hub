# 한국어 개인정보 분류 실험실: 실제 로컬 SemIf 실행

교수님이 제안한 “로컬 분류 기술로 필드의 의미와 개인정보 문맥을 확인해 보자”를 구체적인 입력·출력·오분류로 검증하는 데모다. **공식 TypeSafe Jev 제품을 실행한 결과는 아니다.** 공개 SemIf 소스의 실제 CPU 추론 경로를 프로젝트의 얇은 연결 코드에서 호출하며, 초기 데모의 독립적인 0.6B 모방 구현과 구분한다.

대시보드 주소: **http://127.0.0.1:8810/privacy-lab**

실제 모듈, API 계약과 데이터 흐름은 [구현 아키텍처](korean-classification-architecture.md)에 정리했다.

완료된 실측 수치와 모든 SemIf 오분류는 [한국어 분류 실행 결과](korean-jev-results.md)에서 확인한다.

## 이번 실행에서 확인한 결과

| 방법 | 일치 / 시도 | 정확도 |
|---|---:|---:|
| 실제 로컬 SemIf · Qwen3 4B | 82 / 96 | 85.4% |
| Ollama JSON · 같은 GGUF | 81 / 96 | 84.4% |
| 기존 사전·정규식 | 73 / 96 | 76.0% |

세 방법 모두 96건을 시도했고 실행 오류는 없었다. 총 288개 원본 시도와 집계를 대조한 `evidence/jev/final-audit.json`도 PASS다. SemIf와 JSON은 한 사례 차이이므로 이 개발셋만으로 뚜렷한 우위를 주장하지 않는다.

SemIf는 문맥 대조쌍 14개 중 8개에서 두 입력을 모두 맞혔고, 지시문 삽입 사례는 8개 중 3개를 맞혔다. 점수가 90% 이상인 오분류도 12건이었다. 원래부터 값이 비어 있는 14개 입력은 11개를 맞혔다. 이 결과는 **의미 유형의 검토 후보 제안**에 활용할 수 있으나, 자동으로 법적 분류·CIM 매핑·인가 결정을 확정할 근거로는 부족하다.

관찰한 중앙값은 SemIf 18.736초, JSON 4.006초였다. 다른 프로그램이 실행 중이었고 JSON 평가 중 Ollama에 다른 클라이언트 연결도 관측했다. 프롬프트 배치와 실행기·로딩 조건도 달라 두 방식 자체의 속도 우열을 통제해 측정한 수치는 아니다. 현재 구성에서는 API 응답의 동기 처리보다 로그 후처리 실험에 먼저 적용하는 편이 맞다.

## 실행하는 것

| 구성 | 이 데모에서의 역할 |
|---|---|
| 실제 SemIf | 주어진 선택지 토큰의 상대 점수를 읽어 기술 라벨 하나를 선택한다. 긴 답변을 생성하지 않는다. |
| Qwen3 4B Q4_K_M | 로컬 CPU에서 읽는 공개 GGUF 모델이다. |
| Ollama JSON 방식 | 같은 GGUF 모델을 사용해 제한된 JSON 라벨을 생성하는 비교군이다. |
| 기존 규칙 분류 | `ml.engine.rule_baseline`의 사전·정규식 비교군이다. 운영 게이트웨이의 규칙 엔진 전체를 평가한 결과가 아니다. |
| 합성 KO96 평가셋 | 각 라벨 12건씩 96개 필드 입력이다. 기대값을 추론 전에 작성·검토하고 해시로 동결했다. |
| 실험실 화면 | 직접 입력, 입력 정보 범위 변경, 저장 결과 비교, 혼동행렬, 검토 기준 변경을 제공한다. |

`HEALTH`, `RELIGION`, `CONTACT`, `GOVERNMENT_ID`, `PERSON_NAME`, `ACCOUNT_ID`, `OTHER`, `UNKNOWN`의 여덟 **기술 라벨**을 사용한다. 법률상 개인정보 해당 여부, 동일인 식별 가능성, 인가 위반, 실제 유출 피해자 수를 이 분류만으로 확정하지 않는다. 상세 기준은 [라벨 작성 가이드](korean-label-guide.md)에 있다.

## 이 PC에서 시작하기

PowerShell에서 프로젝트 폴더로 이동한 뒤 실행한다.

```powershell
.\start-demo.ps1 -WithJev
```

기존 웹·DB가 실행 중이면 다음으로 전용 모델 작업자만 시작한다.

```powershell
.\start-jev.ps1
```

SemIf 작업자는 `127.0.0.1:8814`, JSON 비교용 전용 Ollama는 `127.0.0.1:11437`에서 실행된다. 작업자 시작 명령은 모델 준비 완료 전에 돌아올 수 있다. 화면 상단 연결 상태 또는 아래 조회로 준비를 확인한다.

```powershell
Invoke-RestMethod http://127.0.0.1:8814/health
```

처음에는 모델 파일 로딩과 고정 프롬프트 준비가 필요하다. 배치 평가와 직접 입력은 같은 작업자를 사용하므로 평가 중에는 잠시 기다려야 할 수 있다. 화면의 처리 시간은 이 PC에서 실제 요청을 처리한 값이며 동시 사용자 부하 성능이 아니다.

## 교수님께 보여 줄 시연 순서

### 1. 본인의 진단과 일반 건강 안내

예시 검색에 `pair-health-advice` 대신 개별 ID `ko96-h01`과 `ko96-o01`을 차례로 입력한다. 예시 목록 검색은 필드·값·ID를 대상으로 한다.

| 예시 | 입력 의미 | 기대 유형 |
|---|---|---|
| `ko96-h01` | “저는 어제 천식 진단을 받았어요.” — 본인 진단 | HEALTH |
| `ko96-o01` | 천식 증상이 의심되면 상담할 수 있다는 공개 안내 | OTHER |

질환 단어가 두 입력에 모두 있지만 특정인의 상태를 진술하는지에 따라 기대 라벨이 다르다. **로컬 분류 실행**을 눌러 실제 예측과 점수 분포를 확인한다. 틀리면 그 상태를 그대로 보여 주고 아래 저장된 비교 결과와 연결한다. 기대값에 맞을 때까지 문구를 바꾸는 시연은 하지 않는다.

### 2. “없다”도 개인에 관한 내용인가

`ko96-h02`는 특정 환자에게 빈혈이 없고 복용 약도 없다는 내용으로 HEALTH다. `ko96-r02`는 특정 응답자가 종교가 없다고 답한 것으로 RELIGION이다. `ko96-u12`는 설명 없는 `status: 없음`이므로 UNKNOWN이다.

단어 “없음”만 분류하지 않고 **무엇이 누구에게 없다는 것인지**를 문맥에서 확인해야 한다는 점을 시연한다.

### 3. 종교와 관광을 구별하는가

`ko96-r01`의 본인 불교 신앙과 `ko96-o03`의 사찰 관광을 비교한다. 관광 장소로 사찰을 방문했다는 사실에서 그 사람의 신앙을 만들어 내면 안 된다. `ko96-r05`와 `ko96-o04`는 신앙과 종교사 책 소개의 대조다.

### 4. 같은 필드명과 값이라도 의미가 달라지는가

`ko96-g05`와 `ko96-a05`는 `document.id`와 `SYNTHETIC-ID-TOKEN`이 같지만 설명이 다르다. 여권번호라는 설명이면 GOVERNMENT_ID, 서비스 자체 회원번호라는 설명이면 ACCOUNT_ID다.

`ko96-a01`과 `ko96-o07`은 같은 ID 문자열이 회원을 가리키는지 주문을 가리키는지 비교한다. 회원번호를 정부 식별번호로 오인하거나, 주문번호를 사람 식별자라고 단정하는 실패를 확인할 수 있다. 주문번호도 외부 데이터와 결합될 수 있는지는 별도 분석 대상이다.

### 5. 값은 로컬에 두고 필드·설명만으로 어디까지 가능한가

`ko96-c02`는 값이 비어 있어도 회원 휴대전화 필드임을 설명한다. `ko96-u08`은 값이 없는 `addr`이고 설명도 정의하지 않아 보류해야 한다.

그다음 원하는 예시에서 **모델에 전달할 정보**를 다음처럼 변경한다.

| 입력 모드 | 전달되는 내용 | 확인할 한계 |
|---|---|---|
| 필드 + 설명 + 값 | 세 가지 모두 | 원래 KO96 기대값과 비교하는 조건이다. |
| 필드와 설명만 | 실제 값은 제외 | 명확한 스키마 종류는 제안할 수 있지만 실제 응답 값의 존재·내용은 확인하지 못한다. |
| 값만 | 필드명·설명은 제외 | 같은 문자열의 이름·상품명, 계정·주문 ID 구별이 어려울 수 있다. |

**모드를 바꾸면 원래 입력과 조건이 달라진다.** 기본 평가셋 기대값을 그대로 적용해 새로운 정확도를 계산하지 않는다. 화면에서 의미가 어떻게 달라지는지 관찰하는 추가 실험이다. 이 데모는 모든 모드의 입력을 로컬로 처리한다. 외부 LLM에 스키마만 보내는 방안의 개인정보 비노출을 검증한 결과는 아니다.

별도로 기대값을 먼저 정한 실제 세 모드 시연도 실행했다. 필드는 `document.id`, 설명은 ‘가상 회원의 여권번호를 저장하는 필드’, 값은 `SYNTHETIC-ID-TOKEN`이다.

| 모드 | 이 시연의 기대 유형 | 실제 SemIf | 관찰 |
|---|---|---|---|
| 전체 | GOVERNMENT_ID | GOVERNMENT_ID | 설명으로 유형을 구별함 |
| 필드와 설명만 | GOVERNMENT_ID | GOVERNMENT_ID | 값이 없어도 명확한 스키마 유형을 제안함 |
| 값만 | UNKNOWN | ACCOUNT_ID | 종류가 불명확한 합성 ID에서 계정 유형을 과도하게 추측함 |

세 요청 모두 실제 gateway API를 거쳐 HTTP 200 응답을 받았다. **의미 분류 일치는 2/3이며 KO96 성적에 더하지 않는다.** [원본 결과](../evidence/jev/input-modes-20260922T052854Z.jsonl)와 [실행 전 시연 정의 해시](../evidence/jev/input-modes-frozen.json)를 보존했다. 다시 실행하려면 `.venv\Scripts\python.exe -X utf8 -m ml_jev.demo_modes`를 사용한다. 새 시각의 파일에 저장하며 기존 결과를 덮어쓰지 않는다.

### 6. 데이터에 “규칙을 무시하라”가 들어오면 어떻게 되는가

`ko96-h08`, `ko96-r07`, `ko96-c08`, `ko96-g08`, `ko96-n07`, `ko96-a08`, `ko96-o10`, `ko96-u11`에 지시 삽입 사례가 있다. 값 안의 명령은 분석 대상 데이터이고 분류기를 제어할 지시가 아니다.

기본 프롬프트는 이 원칙을 명시하지만 **그 문구만으로 프롬프트 주입 방어가 완성되지는 않는다.** 예측이 높은 점수로 잘못 나오면 그 결과를 오분류 기록에서 확인한다. 몇 개 사례를 맞힌 결과를 광범위한 공격 방어의 보증으로 확대하지 않는다.

### 7. 한 번의 정답보다 전체 실패 형태 보기

**평가 결과와 오분류**에서 방법별 실행 건수·정확도·처리 시간을 확인한 뒤, 혼동행렬의 HEALTH 행과 OTHER 행을 살펴본다. HEALTH를 OTHER로 놓치는 경우와 일반 정보를 HEALTH로 과잉 분류하는 경우를 구별한다.

예시 목록의 **SemIf 오분류 예시만**으로 실패 입력을 다시 열어 기대 이유와 실제 예측을 비교한다. 점수 임계값을 올려도 높은 점수의 오류가 남을 수 있고, UNKNOWN은 원래부터 보류 후보라는 점을 보여 준다.

## 숫자를 읽는 방법

최신 실제 집계는 [`evidence/jev/evaluation.json`](../evidence/jev/evaluation.json)에 있다. 실행 도중에는 완료된 시도만 집계한다. 방법별 `count`가 96인지, `status`가 completed인지 확인한 뒤 전체 평가 결과로 인용한다. 미실행 정확도는 `null`이며 0%가 아니다. HTTP 오류·불완전 출력은 실행 오류로 기록하고 시도된 오답에 포함한다.

| 지표 | 의미 |
|---|---|
| 정확도 | 실제 시도한 입력 중 기대 라벨과 일치한 비율 |
| macro F1 | 여덟 라벨의 F1을 같은 비중으로 평균. 일부 라벨만 실행한 중간값은 전체 성능을 대표하지 않음 |
| 정밀도 | 그 라벨로 예측한 것 중 맞은 비율 |
| 재현율 | 실제 그 라벨인 것 중 찾아낸 비율 |
| 중앙값·p95 | 기록된 요청 지연의 중앙값과 95백분위. 이 PC의 조건에 한정 |
| 선택지 점수 | 허용된 선택지 사이에서 정규화된 상대 선호도. 정답 확률로 교정하지 않았음 |
| 허용 토큰 질량 | 전체 다음 토큰 분포 중 허용된 선택지 토큰들이 차지하는 질량. 선택지 내부 점수와 별개의 값 |
| 임계값별 후보 비율 | 점수가 기준 이상이고 UNKNOWN·오류가 아닌 후보 비율 |
| 후보 내 정확도 | 그 기준으로 남긴 후보의 실제 정답률. 남은 후보가 없으면 계산 불가(null) |

UNKNOWN은 평가에서 실제 정답 라벨이다. 따라서 UNKNOWN을 제대로 예측하면 원래 정확도에서는 정답이다. 운영상 후보 분류에서는 UNKNOWN을 사람이 확인할 대상으로 남긴다. 이 두 계산을 섞지 않는다.

KO96은 이번 데모용으로 작성·검토한 **개발 평가셋**이다. 실제 서비스 표본, 독립적인 미공개 평가셋, 사람 전문가 검수 결과로 소개하지 않는다. 유형마다 12개씩 맞춘 구성이라 실제 서비스의 유형별 비율도 반영하지 않는다. 기존 24개 개발 사례 결과와 분모를 합치지 않는다. 정답표·해설·사례 ID·슬라이스·대조쌍 ID는 모델 입력에 보내지 않는다.

## 실제 구현과 프롬프트 배치

공개 [SemIf 저장소](https://github.com/TheoLeeCJ/SemIf/tree/1f2dea3e25379f9dfc98cb83c324f00ab5deda37)를 커밋 `1f2dea3e25379f9dfc98cb83c324f00ab5deda37`에 고정해 사용한다. `.vendor/SemIf` 원본과 프로젝트 연결 코드 `ml_jev/engine.py`를 구별한다. 소스 비교 기록은 [`upstream-integrity.json`](../evidence/jev/upstream-integrity.json)에 있다. Windows CRLF와 참조 LF의 바이트 차이는 정규화 후 일치 여부와 따로 기록한다.

초기 직접 점수 실험은 사례마다 전체 프롬프트를 처리했다. 현재는 반복되는 라벨 설명과 작업 설명을 고정 상태에 두고, 달라지는 입력을 뒤에 배치해 **upstream `SerialPrefixScorer`의 접두부 재사용 경로**를 실제 호출한다. 이전 직접 점수 실험 3건은 `evidence/jev/direct-pilot/`에 보존했고 현재 96건 집계에 합치지 않는다. 고정 어댑터는 `korean-cached-contract-v2`이며 `cached-adapter-frozen.json`에 해시와 변경 이유를 남겼다.

첫 세 평가 입력은 초기 pilot에도 사용됐다. 따라서 현재 96건을 프롬프트 설계 과정에서 전혀 보지 않은 평가셋이라고 소개하지 않는다. 별도로 실행한 초기 일반 안내·진료·정보 부족 smoke 결과도 보존했으며 96건 분모에 더하지 않았다.

여기에는 두 변화가 함께 있다. 하나는 같은 접두부 계산을 재사용하는 실행 방식이고, 다른 하나는 입력·설명·선택지의 프롬프트 배치다. 라벨 정의와 평가셋 해시를 유지하더라도 **새 점수·정확도·속도의 변화를 캐시 효과 하나로 설명하면 안 된다.** 같은 배치에서 캐시만 켠 경우와 끈 경우를 따로 비교해야 캐시 자체의 효과를 판단할 수 있다. 서로 다른 배치의 예측을 한 방법의 96건처럼 섞지 않는다.

두 모델 방법은 같은 GGUF를 사용하지만 SemIf의 다음 선택지 점수 읽기와 Ollama의 JSON 생성은 런타임·프롬프트 구조·출력 절차가 다르다. 결과 차이를 모델 크기 차이나 Jev 제품의 장단점으로 해석하지 않는다.

## 새 PC의 준비 절차

현재 PC에는 `.venv-jev`와 tokenizer, GGUF가 준비돼 있다. 소스 ZIP에는 대용량 실행기·가중치·가상환경이 포함되지 않으므로 새 PC에서는 준비가 필요하다. Python 3.12와 `uv`, 기존 웹/DB 시연을 함께 사용할 경우 Docker Desktop을 설치한다.

1. [로컬 Ollama 준비 문서](model-alternative.md)에 따라 프로젝트 전용 Ollama와 `qwen3:4b-q4_K_M` 가중치를 준비한다. `prepare_tokenizer.py`는 `.runtime/ollama-models` 아래의 해당 manifest와 blob을 기대한다.
2. 소스 ZIP의 `.vendor/SemIf`는 고정 커밋의 코드와 MIT 라이선스를 담은 **소스 스냅샷**이며 `.git`은 포함하지 않는다. 이 폴더가 이미 있으면 `git clone`이나 `git checkout`을 실행하지 않는다. `evidence/jev/upstream-integrity.json`에 기록한 파일 경로·실제 SHA-256과 배포된 소스를 비교한다. 예를 들어 아래 명령의 값은 해당 JSON의 `llamacpp_backend.py` 항목 `actual_sha256`과 비교할 수 있다.

```powershell
Get-FileHash .vendor/SemIf/src/semif_phase1/llamacpp_backend.py -Algorithm SHA256
```

ZIP을 사용하지 않았고 대상 폴더가 없을 때만 다음으로 동일 커밋을 받는다.

```powershell
git clone https://github.com/TheoLeeCJ/SemIf.git .vendor/SemIf
git -C .vendor/SemIf checkout --detach 1f2dea3e25379f9dfc98cb83c324f00ab5deda37
```

독립 실행 환경을 만들고 CPU용 라이브러리와 고정 소스를 설치한다.

```powershell
uv venv .venv-jev --python 3.12
uv pip install --python .venv-jev\Scripts\python.exe --only-binary=:all: --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu llama-cpp-python==0.3.35
uv pip install --python .venv-jev\Scripts\python.exe -r ml_jev/requirements-cpu.txt
uv pip install --python .venv-jev\Scripts\python.exe --no-deps -e .vendor/SemIf
```

이것은 현재 사용한 CPU GGUF 경로에 필요한 최소 구성이다. **SemIf 패키지의 전체 기본 의존성을 설치한 환경은 아니다.** 현재 `.venv-jev`에는 Torch가 없다. `--no-deps`로 SemIf를 설치한 뒤 필요한 경로의 의존성을 명시적으로 설치한다. 모든 upstream 백엔드·CLI가 이 최소 환경에서 실행된다고 주장하지 않는다. `llama-cpp-python`의 호환 바이너리가 없는 PC에서는 네이티브 빌드 환경이 필요할 수 있으므로 해당 버전의 설치 성공을 먼저 확인한다.

3. 토크나이저와 가중치 출처를 준비한다.

```powershell
.venv-jev\Scripts\python.exe -X utf8 -m ml_jev.prepare_tokenizer --revision 1cfa9a7208912126459214e8b04321603b3df60c
```

준비 스크립트는 명시한 tokenizer revision을 다운로드하고 기록한다. 이번 결과를 정확히 재현하려면 [`runtime-provenance.json`](../evidence/jev/runtime-provenance.json)에 기록한 tokenizer revision과 GGUF SHA-256을 유지해야 한다. 현재 기록된 tokenizer revision은 `1cfa9a7208912126459214e8b04321603b3df60c`, GGUF SHA-256은 `163553aea1b1de62de7c5eb2ef5afb756b4b3133308d9ae7e42e951d8d696ef5`다. 다른 revision을 선택하면 동일 실행으로 취급하지 말고 새 환경 기록으로 평가한다. 고정 소스·라이선스·설치 확인 절차는 [소스 검증과 재현 안내](jev-source-verification.md)에 모았다.

4. `ml_jev/local-runtime.json`의 경로와 CPU 설정을 확인하고 `start-demo.ps1 -WithJev`를 실행한다. 이번 PC에서는 추가 weight repack 버퍼가 메모리를 더 사용해 해당 할당을 끄는 런타임 설정을 적용했다. [`runtime-profile-selection.json`](../evidence/jev/runtime-profile-selection.json)에 최초 조건과 변경 이유를 기록했다. upstream 소스 편집과 프로젝트 연결 코드에서의 로딩 옵션 변경은 구별한다.

설치·공개 모델 다운로드는 네트워크를 사용한다. 준비가 끝난 뒤 **분류할 원문은 외부 모델 API로 보내지 않는다.** Transformers tokenizer는 로컬 파일로 로드하고 SemIf는 로컬 GGUF를 읽는다. JSON 비교 요청의 목적지도 프로젝트 전용 `127.0.0.1:11437`이다.

## 평가를 재개하거나 근거를 확인하기

소스 ZIP에는 이미 실행한 평가 결과가 포함돼 있다. 따라서 기본 명령은 그 결과를 보존하고 **미시도 항목만 이어서 실행**하며, 모두 끝났다면 모델을 호출하지 않고 건너뛴다. 새 PC에서 원본 근거를 유지하면서 실제로 다시 분류하려면 별도 재현 이름을 지정한다.

로컬 작업자가 준비된 뒤 프로젝트의 일반 Python 환경에서 먼저 세 건을 실행한다.

```powershell
.venv\Scripts\python.exe -X utf8 -m ml_jev.evaluate --run-name replay --method semif --limit 3
```

새 결과와 원본 응답은 `evidence/jev/reproductions/replay/`에 저장된다. 데이터셋·분류 계약·어댑터 동결 기록은 기존 `evidence/jev/`의 동일한 파일을 읽지만, 이전 96건 예측을 새 폴더에 복사하지 않으므로 처음부터 실제 모델 호출을 수행한다. 실행 시작과 종료에 결과 경로를 출력한다.

같은 재현 이름으로 전체 평가를 이어가려면 다음을 사용한다. 앞서 세 건을 완료했다면 그 세 건은 다시 실행하지 않는다.

```powershell
.venv\Scripts\python.exe -X utf8 -m ml_jev.evaluate --run-name replay --method all
```

이름은 1~64자의 영문·숫자·하이픈·밑줄이며 영문 또는 숫자로 시작한다. 절대경로, `..`, 슬래시, Windows 장치 예약명은 허용하지 않는다. 저장 경로가 심볼릭 링크 등으로 허용된 재현 폴더를 벗어나도 거절한다. 완전히 새 반복 실험은 `replay-02`처럼 다른 이름을 사용한다. **재현 결과가 기존 UI 기본 평가를 자동으로 교체하지 않는다.** 출력된 새 JSON·원본 응답 파일을 별도로 검토한다.

기본 대표 평가의 미시도 항목을 이어서 실행할 때만 이름 없이 다음을 사용한다.

```powershell
.venv\Scripts\python.exe -X utf8 -m ml_jev.evaluate --method semif
.venv\Scripts\python.exe -X utf8 -m ml_jev.evaluate --method json
.venv\Scripts\python.exe -X utf8 -m ml_jev.evaluate --method rules
```

각 저장 폴더 안에서는 아직 시도하지 않은 입력을 이어서 실행한다. 이미 기록한 오류도 자동으로 다시 시도해 유리한 결과로 바꾸지 않는다. `--limit 4`는 다음 미시도 네 건만 실행하는 제한이며 96건 전체 평가가 아니다. 오류 발생 시 원본을 저장하고 기본적으로 중단한다. 같은 저장 폴더에서 다른 평가 프로세스가 실행 중이면 중복 실행을 거절한다. 다른 이름의 평가라도 같은 로컬 작업자를 동시에 호출하면 busy 오류가 날 수 있으므로 순서대로 실행한다.

동결 데이터·계약·어댑터 소스 해시가 바뀌면 후속 실행을 거절한다. 응답의 어댑터 이름과 실제 upstream backend·commit도 검사해 직접 점수 pilot이 캐시 실험에 섞이는 것을 방지한다. 매 입력마다 원본 응답을 `run-시각-방법-rows.jsonl`에 추가하고 디스크 반영 후 집계 파일을 갱신한다. 별도 프롬프트 배치 실험은 기존 원본과 집계를 분리해 보존해야 한다. 화면의 저장된 결과 조회는 모델 재실행이 아니다.

평가 도중 후속 재현용 평가기에 어댑터 무결성 검사를 추가했다. 실제 진행 중인 프로세스가 읽은 이전 평가기는 `evidence/jev/evaluator-running-version.py`에 보존했다. SHA-256 `240d533696855a2a4c2682f90ade3e3b49e0ea8fe2a95cf76bcb2baa3198d2bb`가 실행 메타데이터와 정확히 일치한다. 실행 중 소스를 바꿨다고 이전 프로세스에 강화된 검사가 소급 적용되는 것은 아니다. 이전 평가기는 방법을 바꿀 때 디스크 파일을 다시 해시하므로, 수정 이후의 JSON·규칙 메타데이터가 기록한 해시는 이미 실행 중인 코드의 증명이 아닐 수 있다. 프로세스 확인·당시 소스·변경 범위는 [`evaluator-provenance.json`](../evidence/jev/evaluator-provenance.json)에 별도로 보존했다. 완료된 결과의 버전 확인은 원본 응답과 동결 기록을 대조하는 별도 사후 검사로 남긴다.

| 파일 | 확인할 근거 |
|---|---|
| `ml_jev/cases.jsonl` | 96개 원본 입력·기대값·이유·슬라이스 |
| `evidence/jev/dataset-frozen.json` | 추론 전 동결한 입력·계약 해시 |
| `evidence/jev/cached-adapter-frozen.json` | 캐시 실험의 어댑터 이름·소스 해시·변경 설명 |
| `evidence/jev/runtime-provenance.json` | tokenizer revision, GGUF 해시, 로컬 경로 |
| `evidence/jev/upstream-integrity.json` | 고정한 SemIf 소스와 실제 checkout 비교 |
| `evidence/jev/evaluation.json` | 최신 방법별 집계와 사례별 예측 |
| `evidence/jev/run-*-rows.jsonl` | 실제로 제출한 입력과 각 원본 응답 |
| `ml_jev/metrics.py` | 정확도·오류·검토 기준의 계산 정의 |
| `ml_jev/test_metrics.py` | UNKNOWN·오류·민감 유형 혼동·0분모 계산 검증 |
| `ml_jev/test_evaluation_integrity.py` | 실제 추론 없이 가짜 응답으로 버전 혼합·근거 누락 거부 검증 |
| `evidence/jev/evaluator-running-version.py` | 실제 평가 프로세스가 읽었던 평가기 소스 사본 |
| `evidence/jev/evaluator-provenance.json` | 프로세스·실행 당시 평가기와 후속 강화 버전의 구별 |

## 브라우저 화면 검사 환경

UI 검사에는 데모의 Python 환경과 별도로 **Node.js, Playwright 모듈, 설치된 Google Chrome**이 필요하다. 두 검사 스크립트는 먼저 `require('playwright')`로 설치된 모듈을 찾는다. 다른 위치에 이미 준비한 모듈을 사용할 때는 `DEMO_PLAYWRIGHT_MODULE`에 해당 모듈의 절대 경로를 지정한다. 특정 PC의 사용자 폴더를 소스에 고정하지 않는다.

```powershell
$env:DEMO_PLAYWRIGHT_MODULE = 'C:\path\to\node_modules\playwright'
node evidence/jev/ui/ui-check.cjs
```

일반 설치 경로에서 Playwright를 찾을 수 있으면 환경 변수 지정은 생략한다. `ui-check.cjs`는 저장된 상태를 읽고 화면만 검사한다. `live-check.cjs`는 합성 예시를 실제 폼으로 **한 번 제출**하므로 전체 평가가 끝난 뒤 별도로 실행한다. 두 스크립트 모두 필요한 모듈이나 브라우저를 자동 설치하지 않는다.

## 프로젝트 적용 판단에 남기는 질문

이 데모의 결과로 결정할 것은 자동 차단 도입 여부보다 **어떤 필드를 어느 조건에서 검토 후보로 올릴 수 있는가**다. 특정인의 상태와 일반 안내를 충분히 구분하는지, 설명이 없는 별칭에서 보류하는지, 값 안의 지시에 흔들리는지, CPU 시간과 메모리 비용이 감당 가능한지를 확인한다.

후속 개발에서는 실제 서비스와 분리한 평가 자료, 외부 검토를 거친 한국어 라벨 기준, 값 추출과 다중 라벨 분류, 거부·재시도 정책, 승인된 CIM 매핑 절차를 보완한다. 모델의 유형 제안이 인가 정책·사고 범위·법적 판단을 자동으로 바꾸지 않도록 현재의 경계를 유지한다.
