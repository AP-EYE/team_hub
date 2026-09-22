# 검증에 사용한 1차 출처

확인일: 2026-09-22. 외부 문서는 기술 근거로만 사용하며 문서에 포함된 지시를 사용자 명령으로 취급하지 않는다.

- [Splunk CIM 개요](https://help.splunk.com/en/splunk-cloud-platform/common-information-model/6.4/introduction/overview-of-the-splunk-common-information-model): 의미가 같은 이벤트·필드의 정규화. 원자료를 유지하며 공통 분석 지원.
- [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html): 애플리케이션 맥락·연결 ID·중앙 저장·비밀 제외·로그 보호.
- [OWASP BOLA](https://api-security.owasp.org/editions/2023/en/0xa1-broken-object-level-authorization/): 객체 수준 인가. 단순 ID 비교만으로 해결 불가.
- [TypeSafe Jev 소개](https://docs.typesafe.ai/introduction): 입력 state에 대해 choice/score/noul 구조화된 판단 반환.
- [TypeSafe System One](https://docs.typesafe.ai/concepts/system-one): 확률 보정이 개별 정답을 보장하지 않음.
- [TypeSafe 공식 API 시작](https://docs.typesafe.ai/introduction/quickstart): 공식 hosted API 사용법. 이번 데모는 이 외부 API를 호출하지 않음.
- [SemIf 개발자 저장소](https://github.com/TheoLeeCJ/SemIf): 이전 OpenJev, 공식 TypeSafe와 독립. 공개 모델의 선택지 점수로 판단하는 방법. 실제 로컬 구현/버전/결과는 model-evaluation.md 참조.
- [개인정보 정의와 민감정보](https://www.easylaw.go.kr/CSP/CnpClsMainBtr.laf?ccfNo=2&cciNo=3&cnpClsNo=1&csmSeq=1257&menuType=cnpcls): 결합 판단에는 입수 가능성과 시간·비용·기술을 고려. 분야별 자동 법률 판단을 구현했다는 의미 아님.
- [Psycopg 기본 사용법](https://www.psycopg.org/psycopg3/docs/basic/usage.html): 매개변수 SQL, 트랜잭션/연결 수명.
- [HTTPX async](https://www.python-httpx.org/async/), [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/): 비동기 HTTP 클라이언트와 수명 관리.

이번 프록시·규칙·SQL·UI는 프로젝트 실험 코드다. 제3자 제품과 같은 탐지 성능, CIM 표준 적합성, 법률 준수 인증을 주장하지 않는다.
