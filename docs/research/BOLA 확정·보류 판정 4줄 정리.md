---
date: 2026-09-30
type: research-hypothesis
project: CCIT-2
tags: [research-hypothesis, bola, ccit]
ai-first: true
source_notion: https://app.notion.com/p/3ea93f3d109680138a25feb148812f0c
---

## For future Claude

노션 문서 허브 페이지 "권한표 없이 테스트 객체로 BOLA 확정·보류 판정"(2026-09-30 06:21 UTC 기준)을 조재현 교수 안내 4줄 형식으로 압축한 노트다.
4줄은 가설 1문장, 필요한 이유, 직접 선행논문, 기존 연구와 다른 점이다.
팀 단톡방과 노션 공용 목록에 옮기기 위한 초안이며 근거 원문은 노션 페이지를 따른다.
관련: [2026-09-29 멘토링 피드백](../../review/2026-09-29%20%EB%A9%98%ED%86%A0%EB%A7%81%20%ED%94%BC%EB%93%9C%EB%B0%B1.md)

2026-10-02 검토: 최신 범위·판정표·비교 설계는 [BOLA 판정 연구 구체화](BOLA%20%ED%8C%90%EC%A0%95%20%EC%97%B0%EA%B5%AC%20%EA%B5%AC%EC%B2%B4%ED%99%94.md), 교수님 질문에 직접 대응하는 사례표는 [선행연구 직접 비교 - 객체별 권한 판단](%EC%84%A0%ED%96%89%EC%97%B0%EA%B5%AC%20%EC%A7%81%EC%A0%91%20%EB%B9%84%EA%B5%90%20-%20%EA%B0%9D%EC%B2%B4%EB%B3%84%20%EA%B6%8C%ED%95%9C%20%ED%8C%90%EB%8B%A8.md)의 10/2 보강을 따른다.

---

# BOLA 확정·보류 판정 4줄 정리

## 1. 가설 1문장

공개·비공개·공유 테스트 객체의 설정 근거를 쓰면 관찰 기반 판정보다 공개·공유 오탐을 줄이면서 실제 읽기 위반 탐지를 유지하고, 전체 객체 권한표 입력보다 준비 비용을 줄일 수 있다는 가설이다. 세 효과 모두 검증해야 한다.

- 비교 대상: 접근 성공 규칙, 반환 객체 일치 기준선, 두 계정의 URL·내용을 비교하는 BACScan식 공개 필터. 엔드포인트 단위 필터라는 표현은 철회한다.
- 수치 근거: 기준선 오탐률 44%는 실측(2026-10-01)이다. "재현율 유지"는 BOLA를 주입한 취약 버전에서 검증할 목표이고 아직 측정하지 않았다.
- 주의: 테스트 객체는 정답을 우리가 지정하므로 그 객체 위의 오탐 0은 당연한 결과다. 그래서 주장의 무게는 "오탐 0"이 아니라 "재현율을 잃지 않는다"와 "입력 비용이 작다"에 둔다.

## 해결 가능성: crAPI 확인 (2026-10-01)

- 확인 대상: 로컬 클론 `D:\SJH_Data\SecurityLab\crAPI` (커밋 b5fc307, 2026-09-09), `openapi-spec/crapi-openapi-spec.json` 엔드포인트 44개와 서비스 소스.
- 소스 전체에 visibility, is_public, is_private, shared_with 같은 객체별 공개 설정 필드가 없다(grep 0건).
- 공개 여부가 객체가 아니라 엔드포인트 종류로 고정돼 있다.
  - 공개: 커뮤니티 게시글 (`GET /community/api/v2/community/posts/{postId}`, `/posts/recent`)
  - 비공개(주인만): 차량 위치, 주문, 프로필 영상
  - 역할 공유: 정비 리포트 (차주 + 배정된 정비사, `workshop/crapi/mechanic/views.py`)
- 결론: crAPI에서는 같은 엔드포인트 안에 공개 객체와 비공개 객체를 섞어 만들 수 없다. 우리 차이점(엔드포인트 단위를 넘어 객체 단위로 구분)을 crAPI만으로는 검증할 수 없다.
- 쓸 수 있는 범위: 엔드포인트 단위 기준선(BACScan식)과 역할 공유(정비 리포트) 사례.
- 다음 확인: 객체별 공개 설정이 있는 오픈소스 앱 4종의 공식 API 문서를 확인했다(2026-10-01).

| 앱 | 같은 엔드포인트에서 객체별 상태 | 공유 | 근거 |
|---|---|---|---|
| Gitea | `GET /repos/{owner}/{repo}` 응답에 `private`(boolean), 생성 시 `CreateRepoOption.private` | 협업자 `PUT /repos/{owner}/{repo}/collaborators/{collaborator}`, permission read/write/admin | https://gitea.com/swagger.v1.json (1.27.0+dev) |
| WordPress | `/wp/v2/posts/<id>`의 `status` = publish, future, draft, pending, private. `password`로 보호 | 특정 사용자 공유 없음(역할 기반) | https://developer.wordpress.org/rest-api/reference/posts/ |
| Mastodon | `visibility` = public, unlisted, private, direct. `GET /api/v1/statuses/:id`는 비공개면 404 "Status does not exist or is private" | direct는 멘션한 사용자만 | https://docs.joinmastodon.org/methods/statuses/ |
| Nextcloud | OCS 공유 API `shareType` 0 사용자, 1 그룹, 3 공개 링크 등. permissions 1 read ~ 31 all | 사용자·그룹 공유 | https://docs.nextcloud.com/server/latest/developer_manual/client_apis/OCS/ocs-share-api.html |

- 판단: Gitea가 1순위다. 같은 엔드포인트에 공개·비공개·공유(협업자 read) 세 상태를 모두 만들 수 있고, 응답에 `private` 필드가 있다(단 하위 객체인 이슈에는 없음, 아래 예비 실험). 배포도 도커 컨테이너 하나로 된다(배포 난이도는 추정, 미실행).
- 2순위는 WordPress(공개·비공개·비밀번호, 공유 없음)다. Mastodon은 상태 종류는 가장 풍부하지만 서비스 구성이 무거울 것으로 보인다(추정). Nextcloud는 파일 본문이 WebDAV 경로라 JSON 객체 API 실험과 결이 다르다.
- Gitea 예비 실험 (2026-10-01, gitea 28.0.0 도커, 로컬 localhost:3300)
  - 스크립트: `3_연구/data/gitea_bola_probe.py`, 결과: `3_연구/data/gitea_bola_probe_result.txt`
  - 계정 A(alice, 주인), B(bob, 권한 없음), C(carol, shared 저장소 read 협업자), 비로그인. 저장소 pub(공개), priv(비공개), shared(비공개+C 공유)와 각 이슈 1번.
  - 단순 규칙("타인이 200이면 위반")은 18건 중 8건을 오탐했다. 공개 저장소·이슈 조회 6건과 C의 공유 조회 2건이다.
  - 비공개 객체는 B·C·비로그인 모두 404였다. Gitea는 인가가 정상 구현돼 실제 위반은 0건이다.
  - 저장소 응답에는 `private` 필드가 있지만 이슈 응답에는 없다(None). 이슈는 부모 저장소의 공개 상태를 따른다. 응답 필드만으로 미표시 객체를 판정하는 6절 방식은 하위 객체에서 막히고, 부모 객체 관계를 알아야 한다.
- 설계상 주의: 이 앱들은 인가가 정상 구현돼 있을 가능성이 높다. 오탐률은 그대로 잴 수 있지만, 재현율을 재려면 권한 검사를 일부러 뺀 취약 버전(패치로 BOLA 주입)이 필요하다.

## 2. 왜 필요한지

기존 판정은 "타인 객체 접근 = 위반"으로 단순화해서 공개 조회와 공유받은 조회를 위반으로 오탐한다.
이를 피하려면 ZAP처럼 객체마다 누가 접근해도 되는지 적은 권한표 전체가 필요하고, OpenAPI 표준에는 객체 수준 권한을 적는 자리도 없다.
BOLA는 실제로 흔하고 국내 사고 원인도 권한 검증 누락이다(강남언니 2026-09-08 21만 9,665건, 레쥬메나인 2026-09-15).

## 3. 가장 직접적인 선행논문

1. Sahin, Zhang, Arcuri, *Enhancing REST API Fuzzing with Access Policy Violation Checks and Injection Attacks*, arXiv 2604.00702, 2026-04
   - "단순하게 규정하면 오탐 결함이 많이 생길 뿐"이라고 직접 지적한다(3.3절).
   - 그러나 접근 정책은 퍼징 중 관찰한 401/403 응답으로 동적 추론한다(3절).
2. Atlidakis, Godefroid, Polishchuk, *Checking Security Properties of Cloud Service REST APIs*, ICST 2020
   - 다른 토큰으로 마지막 유효 요청을 재실행해 성공하면 위반으로 보고한다(3.B절).
   - 단순 규칙의 대표 사례다.
3. Liu et al., *BACScan*, CCS 2025 (PDF: `3_연구/papers/BACScan_CCS25.pdf`)
   - 공격자와 피해자 모두 접근할 수 있는 페이지를 공개로 보고 제외한다(3.3절: "filtering out public pages that are accessible to both attackers and victims").
   - 조재현 교수 예시 가설(공개 정책을 고려한 판정)에 가장 가까운 기존 방식이다.
   - (2026-10-01 정정) 공개 판단은 "엔드포인트 단위"가 아니라 "두 세션 탐색에서 URL과 내용이 같은 페이지"다(§4 RBAC 탐지, 2차 확인). 한계는 공개 여부를 탐색 도달로 추정한다는 점, 공유·로그인 공개 범주와 보류가 없다는 점이다. 상세는 [BOLA 구체화 - 교수님 절차](BOLA%20%EA%B5%AC%EC%B2%B4%ED%99%94%20-%20%EA%B5%90%EC%88%98%EB%8B%98%20%EC%A0%88%EC%B0%A8.md).

## 4. 기존 연구와 다른 점 1문장

기존 연구의 공개 필터와 다중 계정 검사를 출발점으로, 허용 객체의 관찰 누락과 금지 객체의 누출 조건에서 테스트 객체 설정 근거가 판정을 얼마나 개선하는지, 그 대가로 얼마의 준비 비용과 판정 범위 제한이 생기는지를 비교한다.

## 범위 (본체와 확장)

- 본체: 테스트 객체 판정까지. 공개·비공개·공유 상태를 지정한 테스트 객체에 대해 위반을 확정하고 오탐률·재현율·입력 비용을 잰다.
- 확장(이번 연구 밖): 노션 6절의 미표시 객체 판정. 응답의 공개 필드로 테스트 객체가 아닌 객체까지 판정하는 부분이다.
- 확장으로 뺀 이유
  1. 조재현 교수 조언: 해결할 수 있는 문제 하나만 본체로 둔다.
  2. 적용 범위가 좁다: 공개 필드가 있는 명세는 대형 클라우드 제외 9.5%다(자체 조사).
  3. 하위 객체에서 막힌다: Gitea 이슈 응답에는 `private` 필드가 없고 부모 저장소 상태를 따른다(예비 실험).

---

## 보충 근거 (코멘트 답변용)

- 정책 의도를 표준으로 못 얻는다: *OpenAPI Specification Extended Security Scheme*, arXiv 2212.06606, 2022.
- 권한표 전체 입력이 필요하다: OWASP ZAP Access Control Testing 공식 문서.
- 목록 API에 의존하고, 목록이 없으면 테스트 대상이 거의 안 나온다: *AuthProbe*, arXiv 2607.20574, 2026-07, VIII절.
- 트래픽 방식은 앱마다 재조정이 필요하고 평가 데이터가 실제 환경과 다르다: arXiv 2607.16754, 2026-07, 6.2절.
- 공개 페이지 구분이 엔드포인트 단위다: *BACScan*, CCS 2025, 3.3절. 같은 엔드포인트에 공개와 비공개 객체가 섞이면 구분되지 않는다.
- 문제의 빈도: *Broken Object Level Authorization in the Wild*, arXiv 2605.25865, 2026-05, 5.10절. 직접 객체 참조가 원래 36.9%, 가중 37.5%로 가장 큰 유형이다.

## 자체 조사: 응답에 권한 단서 필드가 있는 API 비율 (2026-09-29 기준)

- 대상: APIs.guru 등록 OpenAPI 명세 2,529개 중 2,521개 다운로드, GET 응답이 있는 2,034개.
- 기준: 응답 필드 이름이 visibility, public, private, is_public, is_private, privacy, shared_with, collaborators, acl, access_control 등과 정확히 일치하면 후보로 센다.
- 결과: 전체 2,034개 중 133개(6.5%). Azure, Google, AWS, Microsoft 명세를 뺀 1,003개 중 95개(9.5%).
- 후보 95개 중 30개를 문서로 확인한 결과는 해당 17, 무관 5, 보류 8이다.
- 필드 하나만으로는 판정하지 않는다. 비공개 필드와 공유 대상 목록이 둘 다 보이고 목록에 B가 없을 때만 위반을 확정하고 나머지는 보류한다.
- 결론: 미표시 객체를 확정할 수 있는 API는 9.5%보다 적다. 그래서 "모든 API에서 된다"가 아니라 확정 범위와 보류율을 함께 측정한다.

## 참고 문헌 (PDF 경로와 URL)

PDF는 모두 `D:\SJH_Data\PersonalVault\01_Projects\API-인가-취약점-진단\3_연구\papers\` 아래에 있다.

| 논문 | PDF 파일 | URL |
|---|---|---|
| Sahin et al., 2604.00702 (3번 선행논문 1) | EvoMaster-Security_2604.00702.pdf | https://arxiv.org/abs/2604.00702 |
| Atlidakis et al., ICST 2020 (3번 선행논문 2) | ICST2020_REST-API-security-rules.pdf | URL 미확인, PDF만 있음 |
| OpenAPI Specification Extended Security Scheme, 2212.06606 | 없음 | https://arxiv.org/abs/2212.06606 |
| AuthProbe, 2607.20574 | AuthProbe_2607.20574.pdf | https://arxiv.org/abs/2607.20574 |
| Non-Intrusive Traffic Analysis Framework, 2607.16754 | TrafficAuthzRisk_2607.16754.pdf | https://arxiv.org/abs/2607.16754 |
| BACScan, CCS 2025 | BACScan_CCS25.pdf | URL 미확인, PDF만 있음 |
| BOLA in the Wild, 2605.25865 | BOLA-Taxonomy_2605.25865.pdf | https://arxiv.org/abs/2605.25865 |
| OWASP ZAP Access Control Testing | 없음 | URL 미확인 |

## 용어 (짧게)

- 테스트 계정: A는 주인, B는 권한 없는 사용자, C는 공유받은 사용자.
- 확정: 금지 근거가 있고 금지된 계정이 실제로 데이터를 받았을 때 위반으로 단정하는 것.
- 판정 보류: 근거가 부족해 위반과 정상 어느 쪽도 결론 내리지 않는 판정.
- 확정 범위: 전체 검사 대상 중 결론을 낸 비율.
- 오탐률: 정상 접근(공개 조회, 공유받은 조회)을 위반으로 잘못 판정한 비율.
- 보류율: 전체 검사 대상 중 판정 보류로 남긴 비율.
