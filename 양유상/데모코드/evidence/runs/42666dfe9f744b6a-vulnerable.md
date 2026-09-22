# API 개인정보 노출 분석 데모 실행 보고서

모든 데이터는 합성 자료이며 실제 침해사고 결과가 아닙니다.

- 최신 실행: 42666dfe9f744b6a (vulnerable)
- 관측 요청: 16
- 정책 위반 확인: 5
- 정책 미확정 검토: 1
- 비인가 응답에서 관측한 중복 제거 정보주체: 3
- 범위: 현재 실행에서 기록된 응답. 전체 유출 규모 또는 법 위반 확정이 아닙니다.
- 원문 개인정보 값은 마스킹되어 원문 전체의 사후 복원은 지원하지 않습니다.

| 사례 | 판정 | 유형 | 점수 | 증거 이벤트 |
|---|---|---|---:|---|
| 소유자의 비공개 프로필 조회 | allowed | NONE | 0 | [79] |
| 타인의 비공개 프로필 조회 | confirmed | BOLA | 75 | [80] |
| 타인의 상담 내용 조회 | confirmed | BOLA | 85 | [81] |
| 타인의 공개 프로필 정상 조회 | allowed | NONE | 0 | [82] |
| 공개 프로필의 비공개 필드 과다 반환 | confirmed | BOPLA | 65 | [83] |
| 일반 회원의 관리자 기능 호출 | confirmed | BFLA | 85 | [84] |
| 관리자의 허용된 내보내기 | allowed | NONE | 0 | [85] |
| 명시적으로 공유된 문서 조회 | allowed | NONE | 0 | [86] |
| 공유되지 않은 문서 차단 | blocked | BOLA | 0 | [87] |
| 정책 없는 엔드포인트 검토 보류 | needs_review | UNKNOWN | 0 | [88] |
| 다른 테넌트의 동일 회원번호 조회 | confirmed | BOLA | 75 | [89] |
| beta 소유자의 동일 번호 정상 조회 | allowed | NONE | 0 | [90] |
| 인증 없는 비공개 조회 차단 | blocked | BOLA | 0 | [91] |
| 건강 키워드가 있는 일반 안내문 | allowed | NONE | 0 | [92] |
| 소유자의 주문·별칭 필드 조회 | allowed | NONE | 0 | [93] |
| 건강정보가 아닌 본인 상담 조회 | allowed | NONE | 0 | [94] |

## 결합 분석

같은 요청자가 같은 실행에서 받은 비인가 응답만 tenant + namespace + subject_id로 결합합니다. 필드 조합만으로 법적 식별 가능성을 확정하지 않습니다.

```json
[
  {
    "actor": "bob",
    "tenant": "alpha",
    "namespace": "synthetic-member-v1",
    "subject_id": "U100",
    "fields": [
      "consultation.reason",
      "data_subject.id",
      "person.address",
      "person.email",
      "person.name",
      "person.phone"
    ],
    "endpoints": [
      "admin/export",
      "consultations/U100",
      "profile/leaky/U100",
      "profile/private/U100"
    ],
    "event_ids": [
      80,
      81,
      83,
      84
    ],
    "endpoint_count": 4,
    "subject_key": "alpha:synthetic-member-v1:U100",
    "member_ids": [
      "U100"
    ],
    "attacker_observed": true,
    "reason": "동일 실행·요청자·테넌트·회원 체계에서 비인가 응답에 실제 포함된 정보만 연결. 실명 재식별의 법적 확정 아님."
  }
]
```

## 로컬 모델

모델 분류는 후보이며 인가 정책 판정에는 사용하지 않습니다.

```json
{
  "status": "ready",
  "model": "Qwen/Qwen3-0.6B",
  "revision": "c1899de289a04d12100db370d81485cdf75e47ca",
  "backend": "cpu_direct_logits",
  "external_inference": false,
  "calibrated": false,
  "event_results": [],
  "pending_jobs": 3,
  "evidence_files": [
    "development-diagnostics.json",
    "evaluation-summary.json",
    "model-manifest.json",
    "normalize-summary.json",
    "smoke-summary.json",
    "upstream-versions.json"
  ],
  "benchmarks": {}
}
```

## 무결성

이벤트 SHA-256은 우발적 변경 탐지용입니다. DB 관리자가 값과 해시를 함께 수정하는 위협에 대한 서명/외부 증거 보존은 구현하지 않았습니다.

## 남은 범위

운영 인증/권한, TLS, 성능·부하 검증, 독립 한국어 평가셋, 정책 온보딩, 로그 보존·접근 통제, 실제 게이트웨이 플러그인, 원문 증거 보존 설계가 필요합니다.