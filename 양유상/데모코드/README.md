# API 노출 분석 실험실

교수님 피드백의 **요청·응답 로깅 → CIM 개념의 필드 정규화 → 로컬 AI 분류 → DB 결합 → 인가 판정·조사 지원**을 실제 연결한 합성 데이터 데모입니다.

이 폴더는 4인 프로젝트 착수를 위한 기술 검증 코드입니다. 모든 테스트는 이 PC 안의 합성 서버만 대상으로 합니다. 공식 TypeSafe Jev는 실행하지 않았습니다. 한국어 분류 실험실은 공개 오픈소스 **SemIf(구 OpenJev)**의 선택지 점수 방식과 같은 Qwen3 4B GGUF를 사용합니다.

## 바로 실행

PowerShell에서 이 폴더로 이동한 뒤:

```powershell
.\start-demo.ps1 -WithJev
```

브라우저: **http://127.0.0.1:8810/privacy-lab**

기존 게이트웨이·로그·사후 조사 화면까지 보려면 `-WithModel`을 추가하거나 `-WithJev` 없이 `start-demo.ps1`를 사용하세요. 새 PC의 Python·Docker·모델 준비는 [한국어 SemIf 시연·설치 안내](docs/korean-jev-demo.md)와 [대안 모델 설치·평가](docs/model-alternative.md)를 읽으세요. 모델 가중치와 가상환경은 저장소에 포함하지 않았습니다.

## 데모 구성

- `gateway/`: FastAPI 게이트웨이, 합성 업무 API, 인가·로깅·조사 라우터
- `ml_jev/`: 한국어 8개 라벨 분류 계약, SemIf·JSON·규칙 평가기, 입력 모드 비교
- `static/jev-lab.*`: 96개 사례, 분류 폼, 점수·오류·혼동행렬·저장 결과 UI
- `evidence/`: 실제 실행 결과, 해시, 테스트 XML/JSON, 화면 검사와 브라우저 호출 증거
- `docs/`: 교수 피드백 대응, 아키텍처, 조사 데모, 모델 평가, 착수 계획
- `.vendor/SemIf/`: 실행에 사용한 SemIf 소스 일부와 라이선스

## 핵심 문서

- [데모 해석·상세 설명](../데모-해석-상세.md)
- [교수 피드백 대응표](docs/professor-feedback.md)
- [통합 실행 결과와 착수 판단](docs/demo-results.md)
- [남은 로그 기반 사후 조사](docs/incident-demo.md)
- [한국어 분류 시연·설치·평가 해석](docs/korean-jev-demo.md)
- [한국어 96건 라벨 기준](docs/korean-label-guide.md)
- [한국어 분류 아키텍처](docs/korean-classification-architecture.md)
- [96건 상세 측정 결과](docs/korean-jev-results.md)
- [1차 출처 목록](docs/sources.md)

원래 조사 문서는 [`../조사/api-gateway-research-2026-09-21/`](../조사/api-gateway-research-2026-09-21/)에 보존되어 있습니다. 이번 실행 구현과 이전 제안 문서의 기술 선택은 구분합니다.

## 검증 결과의 범위

96개 합성 개발 사례에서 SemIf 선택지 점수 방식은 82/96(85.4%), 같은 GGUF의 제약 JSON 방식은 81/96(84.4%), 사전·정규식 기준선은 73/96(76.0%)였습니다. 이 결과는 공식 TypeSafe Jev의 성능이 아니며, 합성 개발셋·단일 PC·로컬 Qwen3 4B에 한정됩니다. 점수는 교정된 정답 확률이 아니고, 모든 AI 결과는 검토 후보입니다. 개인정보보호법 분류나 인가 허용·차단을 모델 단독으로 결정하지 않습니다.

코드·계약·무결성 테스트 103개, 저장 결과 UI 검사 56개, 실제 모델 호출을 포함한 브라우저 검사 31개가 이 작업 시점에 통과했습니다. 전체 수치와 실패 사례는 `evidence/jev/`와 관련 문서에서 확인하세요.
