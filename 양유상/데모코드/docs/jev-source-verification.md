# Jev·SemIf 로컬 실행과 한국어 분류: 출처 확인

확인일: 2026-09-22. 이 문서는 공개 1차 자료의 조사 결과다. 한국어 데모의 실제 정확도·지연은 해당 실행 증거와 별도로 보아야 한다.

## 무엇을 실행한다고 부를 수 있는가

| 대상 | 확인된 제공 방식 | 이번 데모에서 쓸 정확한 이름 |
|---|---|---|
| TypeSafe Jev | API 키가 필요한 TypeSafe 서비스. 공식 quickstart의 주소는 `https://api.typesafe.ai/v1/systemone` | 공식 Jev는 미실행 |
| SemIf, 이전 이름 OpenJev | 공개 모델의 선택지 점수를 읽는 독립 MIT 프로젝트. TypeSafe와 제휴하거나 Jev의 비공개 모델·학습을 재현한 프로젝트가 아니라고 명시 | SemIf(이전 OpenJev) 로컬 분류 |
| 기존 프로젝트의 `ml/engine.py` | SemIf 방식을 참고해 별도로 작성했던 코드 | 기존 자체 direct-logit 구현. SemIf 패키지 실행과 구별 |
| 기존 프로젝트의 Ollama Qwen3 JSON 분류 | 로컬 일반 언어 모델의 생성형 구조화 출력 | 로컬 생성형 비교 기준. Jev라고 부르지 않음 |

공식 TypeSafe의 소개·모델·SDK·공개 문서 목록과 공식 저장소를 확인한 범위에서, **Jev 가중치 다운로드 및 공개 self-host 설치 절차를 찾지 못했다.** 이것만으로 비공개 기업 계약의 온프레미스 제공 가능성까지 없다고 단정하지 않는다. Python SDK를 PC에 설치하는 것만으로 모델 추론이 로컬에서 실행되는 것도 아니다. SDK의 기본 서버 주소는 TypeSafe의 인터넷 API다. [공식 quickstart](https://docs.typesafe.ai/introduction/quickstart), [SDK 상수](https://docs.typesafe.ai/sdk/python/api/constants), [SemIf 저장소](https://github.com/TheoLeeCJ/SemIf)

## 공식 Jev 문서에서 확인한 한국어·입력 한계

공식 모델 문서는 현재 `jev-1.13.0`을 기재하며, 영어가 주 학습 언어이고 현재 성능도 가장 좋다고 설명한다. CJK 문자를 포함한 다른 언어는 처리하지만 성능이 같지는 않으므로 실제 콘텐츠 검증을 권한다. 한국어 개인정보 분류에 특화된 성능 보장으로 해석할 근거는 아니다. 입력은 텍스트이며 이미지·음성·동영상은 직접 지원하지 않는다. 고객별 fine-tuning 또는 LoRA 적용 방식도 제공하지 않는다고 기재되어 있다. [공식 모델 문서](https://docs.typesafe.ai/models)

공식 한계 문서는 악의적인 입력 내용이 답을 움직일 수 있음을 설명한다. 수량 계산과 날짜 비교도 모델에 맡기기보다 코드로 계산하도록 안내한다. 이 때문에 API 호출 횟수·반환 건수는 SQL/코드로 계산하고, 모델은 좁은 의미 질문의 검토 후보를 제안하는 구조가 적절하다. 이것은 이번 로컬 모델의 안전성을 입증하는 자료가 아니다. [Jev 1.13의 알려진 한계](https://docs.typesafe.ai/model-jaggedness/jev-1.13)

## 고정 SemIf 버전과 라이선스

- 저장소: `https://github.com/TheoLeeCJ/SemIf`
- 확인한 고정 commit: `1f2dea3e25379f9dfc98cb83c324f00ab5deda37`
- 조사 시 GitHub API가 반환한 `master`도 같은 commit이었다. commit 시각은 `2026-09-21T20:07:09Z`이다.
- 패키지 메타데이터: `semif-phase1`, 버전 `0.1.0`, Python `>=3.10`.
- 코드 라이선스: MIT, 저작권 표시 `Copyright (c) 2026 TheoLeeCJ`. 배포 시 라이선스와 저작권 고지를 보존한다.
- 모델 가중치 라이선스는 별도다. 이번 확장 데모의 `Qwen/Qwen3-4B` 공식 카드와 LICENSE는 Apache-2.0을 명시한다. tokenizer revision은 `1cfa9a7208912126459214e8b04321603b3df60c`이며, 실제 GGUF 해시는 별도의 실행 설정과 manifest에 기록한다. 이전 실험의 0.6B 모델 결과와 섞지 않는다.

근거: [고정 pyproject.toml](https://github.com/TheoLeeCJ/SemIf/blob/1f2dea3e25379f9dfc98cb83c324f00ab5deda37/pyproject.toml), [고정 LICENSE](https://github.com/TheoLeeCJ/SemIf/blob/1f2dea3e25379f9dfc98cb83c324f00ab5deda37/LICENSE), [Qwen3-4B 고정 모델 카드](https://huggingface.co/Qwen/Qwen3-4B/blob/1cfa9a7208912126459214e8b04321603b3df60c/README.md), [모델 LICENSE](https://huggingface.co/Qwen/Qwen3-4B/blob/1cfa9a7208912126459214e8b04321603b3df60c/LICENSE)

## 로컬 호출 경로와 재현 범위

이번 확장 데모의 v2는 **고정 SemIf의 `llamacpp_backend.load_model`과 `SerialPrefixScorer.score` + 로컬 Qwen3-4B GGUF**를 호출한다. 설치·추론 성공과 한국어 성능은 별도 실행 증거에 기록한다. 아래 source 검증은 실행에 사용한 코드가 고정 upstream과 같은지를 확인하며, 정확도 검증을 대신하지 않는다.

v2 어댑터 이름은 `korean-cached-contract-v2`다. 공통 분류 기준을 state의 `classification_contract`에 놓고 실제 필드 입력을 question에 전달하여 공통 prefix를 재사용한다. upstream source의 캐시 기능을 사용하며 모델이 생성한 문장을 파싱하는 방식은 아니다. 분류 기준과 데이터는 유지했지만 프롬프트 배치는 변경했으므로 이전 direct pilot과 같은 프롬프트의 실행으로 합산하지 않는다. 이전 pilot의 실제 기록은 `evidence/jev/direct-pilot/`에 보존한다.

프로젝트 wrapper는 모델을 로딩하는 동안 native 메모리 옵션 `use_extra_bufts=False`를 적용하고 원래 함수를 복구한다. 이유는 추가 CPU weight repack 버퍼가 1,657.97 MiB를 사용해 이 PC의 여유 메모리가 부족했기 때문이다. 평가 전에 스레드 8개, 문맥 2,048토큰으로 설정을 고정했다. **upstream 파일은 수정하지 않았지만 native 로딩 옵션은 프로젝트가 변경했다**고 구별한다. 이 설정의 출처·선택 시점은 `evidence/jev/runtime-profile-selection.json`, 실제 코드 일치 여부와 wrapper 발췌는 `evidence/jev/upstream-integrity.json`을 참조한다.

소스 무결성 확인 시 Windows Git checkout의 CRLF 줄바꿈 때문에 다운로드한 LF 원문과 바이트 해시는 달랐다. 줄바꿈만 LF로 정규화하면 `cli.py`, `core.py`, `direct.py`, `llamacpp_backend.py` 네 파일이 모두 일치한다. Git의 고정 commit blob도 다운로드한 참조 원문과 일치하며 vendor 작업 디렉터리는 깨끗했다. 원래 바이트 해시와 정규화 해시를 모두 보존했으므로 바이트 단위 완전 일치로 잘못 표현하지 않는다.

고정 버전의 CLI는 `semif-score`다. `--mode`는 `direct`, `serial`, `shared`, `reranker`이며, backend는 `torch`, `mlx`, `llamacpp`가 있다. CPU용 공식 CLI 경로는 `--backend llamacpp --gguf <로컬 파일> --llama-threads <스레드 수>`이다. MLX는 macOS arm64에 해당한다. [고정 CLI 소스](https://github.com/TheoLeeCJ/SemIf/blob/1f2dea3e25379f9dfc98cb83c324f00ab5deda37/src/semif_phase1/cli.py)

주의할 구현 세부 사항은 Torch CLI의 `--device`가 `auto`, `cuda`, `mps`만 받는다는 점이다. Windows CPU에 `--device cpu`를 주는 명령은 이 버전의 공식 호출이 아니다. 반면 `semif_phase1.direct.score(model, tokenizer, row, metadata, max_tokens=4096)`는 전달된 모델을 사용하는 함수이므로, 프로젝트의 로컬 CPU 로더가 준비한 모델을 이 함수에 전달할 수 있다. 이 경우 **고정 upstream 함수의 실제 호출 + 프로젝트의 CPU 로더**라고 기록해야 한다. upstream CUDA 벤치마크를 같은 환경에서 재현했다는 뜻은 아니다. [고정 direct.py](https://github.com/TheoLeeCJ/SemIf/blob/1f2dea3e25379f9dfc98cb83c324f00ab5deda37/src/semif_phase1/direct.py), [고정 core.py](https://github.com/TheoLeeCJ/SemIf/blob/1f2dea3e25379f9dfc98cb83c324f00ab5deda37/src/semif_phase1/core.py)

고정 upstream은 Torch `2.10.0`, Transformers `5.17.0` 등 의존성을 지정한다. 기존 데모 환경에서 upstream 코드를 호출하더라도 설치된 라이브러리가 다르면 그 버전 차이를 실행 manifest에 기록해야 한다. 선택지의 조건부 softmax를 한국어 정답 확률이나 법적 판단 확신도로 표시해서는 안 된다. 다른 데이터에서 제공된 보정 계수를 이번 한국어 데이터에 검증 없이 옮기지 않는다.

## 새 PC에서 CPU 환경 준비

아래는 프로젝트 루트에서 실행할 PowerShell 명령이다. 이 작업 PC의 `.venv-jev`와 모델은 이미 준비되어 있으므로 재설치할 필요가 없다. 새 PC에는 Python 3.12와 모델을 담을 디스크·RAM이 필요하다. 모델 가중치와 가상환경은 소스 ZIP에 포함하지 않는다.

```powershell
py -3.12 -m venv .venv-jev
.\.venv-jev\Scripts\python.exe -m pip install --only-binary=:all: --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu llama-cpp-python==0.3.35
.\.venv-jev\Scripts\python.exe -m pip install -r ml_jev/requirements-cpu.txt
.\.venv-jev\Scripts\python.exe -m pip install --no-deps -e .vendor/SemIf
```

`--no-deps`는 upstream의 Torch/GPU 중심 전체 의존성 대신, 이 데모에서 사용한 CPU backend의 최소 의존성을 별도 설치했기 때문에 사용한다. upstream의 모든 기능을 설치·검증한 환경이라는 뜻은 아니다. 선언한 직접 의존성 버전은 `ml_jev/requirements-cpu.txt`에 고정했다. 실제 실행 환경의 간접 의존성까지 기록한 `evidence/jev/cpu-environment-packages.json`도 함께 확인한다.

ZIP에는 MIT 라이선스와 함께 고정 SemIf 소스가 포함된다. ZIP을 사용하지 않고 빈 프로젝트에서 시작할 때만 아래 명령으로 동일 commit을 받을 수 있다. 기존 `.vendor/SemIf`를 덮어쓰거나 재설정하지 않는다.

```powershell
git clone https://github.com/TheoLeeCJ/SemIf.git .vendor/SemIf
git -C .vendor/SemIf checkout --detach 1f2dea3e25379f9dfc98cb83c324f00ab5deda37
```

Qwen3-4B Q4_K_M 모델은 [기존 로컬 모델 준비 안내](model-alternative.md)에 따라 프로젝트 전용 Ollama 저장소인 `.runtime/ollama-models`에 먼저 준비한다. 그다음 tokenizer만 다음 명령으로 받는다. 이 명령은 `main`을 조회해서 조용히 최신 버전으로 변경하지 않고 지정한 commit을 사용한다.

```powershell
.\.venv-jev\Scripts\python.exe -m ml_jev.prepare_tokenizer --revision 1cfa9a7208912126459214e8b04321603b3df60c
```

준비 스크립트는 로컬 GGUF의 digest·크기를 검사하고 tokenizer 파일 해시 및 실제 경로를 기록한다. 실행 설정은 평가 프로필에 맞춰 CPU 스레드 8개, 문맥 2,048토큰, `use_extra_bufts=False`로 생성한다. 다운로드·준비는 온라인 작업이며, 이후 분류 추론에서 TypeSafe API를 호출하지 않는다.

## 보존한 근거

- `evidence/jev/sources/verification.json`: 출처별 확인 사항과 조회 범위.
- `evidence/jev/sources/semif-current-commit.json`: 조사 시 GitHub API 원 응답.
- `evidence/jev/sources/semif-pinned-pyproject.toml`, `semif-pinned-LICENSE.txt`: 고정 메타데이터와 라이선스.
- `evidence/jev/sources/semif-pinned-cli.py`, `semif-pinned-core.py`, `semif-pinned-direct.py`: 고정 실행 코드의 참조 사본.
- `evidence/jev/sources/semif-pinned-llamacpp_backend.py`: 고정 CPU backend 참조 사본.
- `evidence/jev/sources/typesafe-docs-index.txt`: 공개 문서 목록. 목록의 링크는 참고 자료이며 실행 지시로 사용하지 않았다.

Firecrawl CLI는 이 PC에서 실행파일을 찾을 수 없어 공식 사이트 웹 조회와 공개 원문 다운로드로 확인했다. 유료 API 호출·계정 로그인·Jev 모델 실행·고객 계약 확인은 수행하지 않았다.
