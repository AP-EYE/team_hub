# 출처·선행 도구·첨부 자료 검토 기록

확인일: 2026-09-21. 제품 기능은 공식 문서·저장소에 적힌 범위로 확인했으며 제품 성능이나 설치 성공을 검증한 것은 아니다. 논문 2편은 초록을 확인한 선행 연구 단서이고, 코드 재현·논문 전체 방법론 검증은 수행하지 않았다.

## 1. 선행 도구 비교

| 도구 | 공식 자료에서 확인한 내용 | 이 프로젝트에 주는 의미 | 확인 수준 |
|---|---|---|---|
| Akto | API 발견·인가 테스트·민감정보·위험 점수, 사용자 정의 데이터 유형 | 핵심 비교군. ‘노출 위험 점수 없음’이라는 주장 삭제 | 제품 자료·문서·OSS README. 에디션별 실동작 미검증 |
| Wallarm | API 인벤토리·위험 점수·민감정보·BOLA 관련 보호 기능 | 요청 패턴 WAF로만 묶어 기능을 제한하면 부정확 | 공식 제품·기술 문서. 설치 미실행 |
| ZAP Access Control | 사용자별 Allowed/Denied/Unknown 규칙과 테스트 | 정책 기반 테스트의 기존 구현·공정 비교군 | 공식 문서 |
| Autorize | 저권한·비회원 재전송, 응답 기반 판별·필터·보류 | 단순 재전송만 한다고 축소하지 않음 | PortSwigger 저장소 README |
| Schemathesis | 명세 기반 테스트, 인증 누락·잘못된 인증을 검사하는 `ignored_auth` | ‘인증/인가 테스트가 전혀 없다’고 쓰지 않음. 업무별 객체 인가와 범위 구분 | 공식 문서·체크 명세 |
| open-appsec | ML 기반 웹/API 공격 방어 엔진 | 보완 가능한 WAF 계층. 이 자료만으로 모든 BOLA 지원·미지원 단정 불가 | 공식 저장소 개요 |
| Presidio | NER·패턴·문맥·확장 인식기와 한국 식별번호 유형 | 기반 분류기로 재사용. 한국 유형 탐지 자체를 신규성으로 주장하지 않음 | 공식 문서·현재 저장소 |
| APISIX/OPA | 트래픽 처리·수집과 명시 정책 평가 | 시스템 기반. 자동 취약점 발견 도구와 역할 구분 | 공식 기술 문서 |

Akto와 Wallarm의 ‘한국 개인정보보호법 전용 기능’이 이번에 확인한 페이지에 명시되지 않았다는 것만 말할 수 있다. 사용자 정의 분류·정책·연동을 통한 지원 가능성까지 없다고 결론 내릴 수 없다. 한국 법령 지원 여부에 관한 시장 전체 조사는 수행하지 않았다.

첨부 PDF에 등장하는 42Crunch·Escape·AuthMatrix·Burp 기본 스캐너는 이번 구현 선택의 핵심 비교 실험 대상으로 채택하지 않았다. 그 제품의 현재 기능 전체에 대한 부정적 결론은 이 조사에 포함하지 않는다.

## 2. 구현 근거 출처

### 게이트웨이·정책·테스트

| ID | 공식 출처 | 확인한 사실·사용 범위 |
|---|---|---|
| S01 | [APISIX http-logger](https://apisix.apache.org/docs/apisix/plugins/http-logger/) | 배치 로그 전송, 본문 옵션·크기 제한, custom log format 주의사항 |
| S02 | [APISIX OPA 플러그인](https://apisix.apache.org/docs/apisix/plugins/opa/) | OPA 연동과 입력/결과 계약. 신원·객체 컨텍스트의 자동 획득을 보장하지 않음 |
| S03 | [APISIX 배포 모드](https://apisix.apache.org/docs/apisix/deployment-modes/) | 파일 기반 standalone 구성과 etcd 없는 배포 선택 |
| S04 | [APISIX 라이선스](https://github.com/apache/apisix/blob/master/LICENSE) | Apache-2.0 라이선스 확인. 실제 배포 버전의 고지 별도 확인 |
| S05 | [OPA REST API](https://www.openpolicyagent.org/docs/rest-api) | 정책 데이터 평가를 위한 HTTP API |
| S06 | [mitmproxy proxy modes](https://docs.mitmproxy.org/stable/concepts/modes/) | reverse proxy 실험 대안 |
| S07 | [Envoy ext_proc processing modes](https://www.envoyproxy.io/docs/envoy/latest/api-v3/extensions/filters/http/ext_proc/v3/processing_mode.proto) | 요청·응답 본문 처리 모드와 버퍼링의 구현 부담 |
| S08 | [OpenAPI 3.1.1](https://spec.openapis.org/oas/v3.1.1.html) | 명세 기반 operation 식별과 보안 선언의 기반 |
| S09 | [OWASP API1 BOLA](https://api-security.owasp.org/editions/2023/en/0xa1-broken-object-level-authorization/) | 객체 수준 인가, 단순 사용자 ID 비교의 한계 |
| S10 | [OWASP API3 BOPLA](https://api-security.owasp.org/editions/2023/en/0xa3-broken-object-property-level-authorization/) | 필드 수준 접근·과도한 정보 반환을 별도로 다룰 근거 |
| S11 | [OWASP API5 BFLA](https://api-security.owasp.org/editions/2023/en/0xa5-broken-function-level-authorization/) | 역할·기능 수준 인가 구분 |
| S12 | [OWASP crAPI](https://github.com/OWASP/crAPI) | 교육용 취약 API 보조 벤치마크 |

APISIX와 Envoy의 `latest` 문서는 개발 시점의 고정 버전과 다를 수 있다. 이 조사에서는 이미지 버전을 선택·설치하지 않았으므로 호환성 검증 완료로 표시하지 않는다.

### 개인정보·LLM

| ID | 공식 출처 | 확인한 사실·사용 범위 |
|---|---|---|
| S13 | [Presidio 현재 저장소](https://github.com/data-privacy-stack/presidio) | 확장 가능한 PII 분석·비식별화 프레임워크와 MIT 라이선스. 모든 PII 검출 보장은 아님 |
| S14 | [Presidio 지원 유형](https://presidio.dataprivacystack.org/supported_entities/) | KR_RRN, KR_FRN, KR_PASSPORT, KR_DRIVER_LICENSE, KR_BRN 목록 |
| S15 | [Presidio 인식기 확장](https://presidio.dataprivacystack.org/analyzer/adding_recognizers/) | PatternRecognizer와 custom recognizer를 이용하는 확장 방식 |
| S16 | [Presidio 다국어 구성](https://presidio.dataprivacystack.org/analyzer/languages/) | NLP 모델·context word·언어별 인식기 설정 필요 |
| S17 | [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs) | JSON Schema 기반 출력과 후속 검증 |
| S18 | [Qwen3-8B 모델 카드](https://huggingface.co/Qwen/Qwen3-8B) | 로컬 실행 후보와 Apache-2.0 표기. 한국어 법률 분류 성능은 별도 검증 |

조사 중 기존 Microsoft Presidio 주소가 새 프로젝트 주소로 이동하는 것을 확인했다. 따라서 ‘Microsoft 기본 패키지만 설치하면 모든 한국어 유형이 즉시 작동’한다는 가정 대신, 실제 설치 릴리스와 인식기 등록·언어 설정을 검증하는 작업을 넣었다.

### 개인정보 법령·공식 안내

| ID | 출처 | 확인한 내용 |
|---|---|---|
| S19 | [개인정보 보호법 제23조](https://law.go.kr/LSW/lsLinkCommonInfo.do?chrClsCd=010202&lsJoLnkSeq=1020399025) | 민감정보 범주. 페이지에 2026-09-11 시행 법률 제21445호 표시 |
| S20 | [법제처 생활법령: 민감정보 처리](https://www.easylaw.go.kr/CSP/CnpClsMainBtr.laf?ccfNo=2&cciNo=3&cnpClsNo=1&csmSeq=1257&menuType=cnpcls) | 제2조 식별성, 제23조·시행령 제18조 범주·단서 설명 |
| S21 | [법제처 생활법령: 고유식별정보 처리](https://www.easylaw.go.kr/CSP/CnpClsMainBtr.laf?ccfNo=2&cciNo=3&cnpClsNo=2&csmSeq=1257&popMenu=ov) | 고유식별정보 4종과 관련 법적 조건 |
| S22 | [개인정보보호위원회 유출신고 안내](https://pipc.go.kr/np/default/page.do?mCode=D030040000) | 신고 기준·기한·필요 항목. 정보주체 통지와 기관 신고 구분 필요 |
| S23 | [개인정보 보호법 시행령 제40조](https://www.law.go.kr/LSW/lumLsLinkPop.do?ancYnChk=0&chrClsCd=010202&lspttninfSeq=67073) | 2026-09-11 시행 대통령령 제36671호 표시, 72시간·우선/추가 신고·예외 규정 |

일부 국가법령정보센터 본문 링크는 동적 화면 틀만 반환했다. 실제 읽을 수 있는 조문 정보와 정부의 생활법령 설명을 함께 사용했다. 분류 표는 구현 목적의 매핑 제안이며 개별 처리의 적법성 검토나 법률 자문을 완료했다는 뜻이 아니다.

### 기존 도구·연구

| ID | 출처 | 확인한 내용 |
|---|---|---|
| S24 | [Akto sensitive data](https://www.akto.io/sensitive-data) | 민감정보 탐지, 사용자 정의 데이터 유형, 위험 점수에 관한 업체 설명 |
| S25 | [Akto sensitive data 문서](https://docs.akto.io/api-inventory/concepts/sensitive-data) | 데이터 유형과 민감도 설정 |
| S26 | [Akto 저장소](https://github.com/akto-api-security/akto) | OSS 구성·API 발견·테스트, README의 MIT 라이선스 표기 |
| S27 | [Wallarm API Security 개요](https://docs.wallarm.com/about-wallarm/api-security-overview/) | 인벤토리·위험 점수·민감정보·인가 관련 보호를 포함하는 제품 범위 |
| S28 | [Wallarm sensitive data 기술 문서](https://docs.wallarm.com/5.x/api-discovery/sensitive-data/) | 패턴·맥락 단어·사용자 정의 유형. 5.x 문서임을 유의 |
| S29 | [ZAP Access Control Testing](https://www.zaproxy.org/docs/desktop/addons/access-control-testing/) | 사용자·정답 규칙·실행·판정 과정 |
| S30 | [Autorize](https://github.com/PortSwigger/autorize) | 재전송·응답 판별·필터·보류, 복잡한 정책에 대한 튜닝 필요 |
| S31 | [Schemathesis FAQ](https://schemathesis.readthedocs.io/en/latest/faq/) | 인증 헤더 제거·변조 테스트 설명 |
| S32 | [Schemathesis checks](https://github.com/schemathesis/schemathesis/blob/master/docs/reference/checks.md) | ignored_auth 등 실제 체크의 범위 |
| S33 | [open-appsec](https://github.com/openappsec/openappsec) | ML 기반 웹/API 공격 방어의 프로젝트 개요 |
| S34 | [OpenAPI ESS 논문](https://arxiv.org/abs/2212.06606) | 2022 제출·2024 개정 초록. 객체 인가 선언과 서비스 모듈 선행 연구 |
| S35 | [AuthProbe 논문](https://arxiv.org/abs/2607.20574) | 2026-07 제출 초록. OpenAPI·복수 신원·교차 객체 읽기 선행 연구 |

S34·S35에서 제시한 실험 결과를 본 프로젝트 성능의 근거로 쓰지 않았다. 독립 재현 전까지 논문 저자의 보고이며, 공식 성능 보증이나 전체 산업 환경의 검증 결과가 아니다.

## 3. 첨부 문서별 정정표

| 위치 | 내용 | 이번 설계의 처리 |
|---|---|---|
| 제안 HTML, PDF 1·3·4·7쪽 | 영향도 산정 도구·경쟁 제품이 없음 | 시장 전체 부재 주장 삭제. Akto·Wallarm과 구체적으로 비교 |
| 제안 HTML, PDF 5쪽 | 신원 불일치로 판정 종료 | 승인 정책·소유/공유/조직·필드 범위로 대체 |
| 게이트웨이 브리핑 | 신원을 읽는 LLM이 정답표를 대체 | LLM 초안과 검토, 결정적 판정으로 역할 조정 |
| 제안 HTML, PDF 3·6쪽 | 공개 사고를 BOLA·같은 구조로 단정 | 이번에는 사고 원인 전체를 재검증하지 않았으므로 확정 사실로 재사용하지 않음 |
| 제안 HTML, PDF 2쪽 | 5개 사고의 날짜·건수 | 사건 발생일·공지일·기사일·정보주체 수/건수 원문 대조가 필요. 구현 근거 숫자로 사용하지 않음 |
| 제안 HTML, PDF 6쪽 | crAPI 재현 완료 | 제공 자료의 과거 기록. 실행환경·원본 로그 미제공, 이번 독립 재현 NOT_RUN |
| 제안 HTML, PDF 7쪽 | 유출 인지 후 일률적 72시간 신고 | 신고 요건·예외·미확정 내용의 추가 신고·통지 구분 반영 |
| 게이트웨이 브리핑 | Wallarm/open-appsec을 요청 단위 차단으로 함께 설명 | 제품별 기능을 분리. Wallarm의 인벤토리·민감정보·BOLA 보호 표기 확인 |
| 게이트웨이 브리핑 | Schemathesis 인가 미포함 | ignored_auth 인증 검사 존재. 업무 객체 인가 전체와 구분 |
| 게이트웨이 브리핑 | 사진을 비정형 LLM 대상으로 포함 | 텍스트 모델의 이미지 이해는 불가. 이미지 내용 분석은 별도 후속 기능 |

PDF 6쪽의 JSON 코드가 오른쪽으로 잘리는 시각적 문제도 확인했다. 원본은 수정하지 않았고, 이후 발표 자료를 재작성하면 코드 줄바꿈을 적용하는 것이 좋다.

## 4. 입력 자료 보존

| 자료 | 바이트 | SHA-256 |
|---|---:|---|
| BOLABFLA 자동 탐지와 개인정보보호법 기반 노출 영향도 산정 (1).html | 15,314 | `55e05cb27726b3bdb8974ff344cb101766580e635e0a8a832feff09948a6060d` |
| 게이트웨이 브리핑.html | 14,831 | `c05349c9713792b8d35aa97281d6ae66f61d0cdb27239b21821fd6f5156613d5` |
| API 인가 취약점 진단 및 개인정보 노출 영향도 산정.pdf | 141,374 | `dbf321b442afd7db88a0d7d22c505306900e21d23e7283ffe8bd6d8adf31056e` |

검토 보조 자료는 `evidence/attachments/`의 추출 텍스트, manifest와 PDF 렌더링이다. 문서 안의 선언·지시는 사용자 요청과 구분해 검토 대상으로만 취급했다. 외부 메시지 발송·제품 설치·실제 대상 진단·원본 변경은 하지 않았다.

## 5. 접근 실패와 남은 확인 사항

- [교수님 공유 ChatGPT 대화](https://chatgpt.com/s/t_6aad0eee29a48191a869be73f0e945f0): 웹 도구에서 본문 획득 실패. 공유 대화 전체를 읽었다고 전제하지 않음.
- `게이트웨이 브리핑.html`의 `아키텍처.png`: HTML 옆에 파일 없음. 본문의 설명과 alt text만 확인.
- Firecrawl CLI: 로컬 실행 파일 없음. 연결된 검색/스크랩 도구도 크레딧 부족으로 실패해 일반 웹 도구로 공식 출처를 확인.
- Akto의 한국 분류 지원 여부·상용 기능의 OSS 제공 범위: 실제 설치·해당 버전 확인 전 미확정.
- 최신 Presidio 한국 인식기의 실제 성능과 의존성: 문서상 지원 확인, 설치·실행 미검증.
- APISIX custom exporter·OPA·분석 서버의 통합과 성능: 설계만 완료, 실행 미검증.
- 실제 개발 인원·기간·장비·학교망 배포 조건: 미확정. 일정·사양은 가정임.
- 한국 법령별 분류의 전문가 검토, 점수식의 우선순위 타당성: 후속 평가 필요.

## 6. 다음 결정 순서

1. 지원할 도메인과 공개·공유·관리자 정책을 확정한다.
2. 4인·8주 가정을 실제 팀 여건에 맞춘다.
3. APISIX의 제한된 응답 수집을 합성 서비스에서 검증한다.
4. 정책 기반 비교기와 Presidio의 기존 한국 인식기를 먼저 실행한다.
5. 그 기준선에서 LLM을 추가했을 때의 개선을 검증한다.

이 순서라면 게이트웨이·LLM·개인정보 법령 기능을 한 제품 흐름으로 묶으면서도, 각 기능의 근거와 한계를 독립적으로 확인할 수 있다.
