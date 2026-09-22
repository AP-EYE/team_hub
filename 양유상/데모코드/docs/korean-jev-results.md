# 한국어 분류 실제 실행 결과

공식 TypeSafe Jev의 성능 평가가 아니다. 실제 SemIf와 로컬 Qwen3-4B Q4_K_M의 이번 설정을 평가했다.

합성 개발 사례 96개(8유형 × 12개)를 각각 실행했다. 독립적인 미공개 평가셋·전문가 검수 결과는 아니다. 초기 직접 점수 pilot은 제외했다.

| 방법 | 맞힌 수 / 시도 | 정확도 | macro F1 | 실행 오류 | 중앙값 | p95 |
|---|---:|---:|---:|---:|---:|---:|
| 실제 SemIf · 로컬 Qwen3 4B | 82 / 96 | 85.4% | 0.851 | 0 | 18.736초 | 82.714초 |
| Ollama JSON · 같은 GGUF | 81 / 96 | 84.4% | 0.847 | 0 | 4.006초 | 47.089초 |
| 기존 사전·정규식 | 73 / 96 | 76.0% | 0.737 | 0 | 0.026ms | 0.059ms |

시간은 다른 프로그램도 실행 중인 이 Windows PC에서 관찰한 값이다. 전용 장비·동시 부하·cold/warm 조건을 통제한 제품 벤치마크가 아니다. SemIf의 모델 시작 시간은 요청 밖이며 공통 prefix의 첫 계산은 첫 요청에 포함된다. Ollama의 첫 요청에는 모델 로딩이 포함될 수 있다. 두 방식은 같은 GGUF를 쓰지만 프롬프트 배치·런타임·출력 방법이 다르다.

JSON 평가 중 Ollama 서버에 현재 작업자 외의 클라이언트 연결도 관측했다. 연결만으로 실제 동시 추론을 확정하지는 않지만, 단독 클라이언트 조건을 검증한 실험은 아니다. 다른 프로세스를 종료하거나 이 조건을 숨기지 않았다. 지연 차이를 SemIf 또는 JSON 방식 자체의 우열로 환산하지 않는다. [실행 환경 관찰 기록](../evidence/jev/resource-observations.jsonl)

## 유형별 결과

| 기대 유형 | SemIf 정답 | SemIf 정밀도 | SemIf 재현율 | JSON 정답 | 규칙 정답 |
|---|---:|---:|---:|---:|---:|
| HEALTH | 10 / 12 | 90.9% | 83.3% | 10 / 12 | 8 / 12 |
| RELIGION | 11 / 12 | 91.7% | 91.7% | 11 / 12 | 12 / 12 |
| CONTACT | 11 / 12 | 100.0% | 91.7% | 12 / 12 | 12 / 12 |
| GOVERNMENT_ID | 12 / 12 | 80.0% | 100.0% | 10 / 12 | 11 / 12 |
| PERSON_NAME | 11 / 12 | 91.7% | 91.7% | 11 / 12 | 11 / 12 |
| ACCOUNT_ID | 11 / 12 | 91.7% | 91.7% | 9 / 12 | 11 / 12 |
| OTHER | 6 / 12 | 85.7% | 50.0% | 10 / 12 | 2 / 12 |
| UNKNOWN | 10 / 12 | 62.5% | 83.3% | 8 / 12 | 6 / 12 |

정밀도는 그 유형으로 분류한 결과 중 맞은 비율이다. 정답 사례 12개를 모두 찾아도 다른 유형을 잘못 포함하면 정밀도는 낮아진다.

## 문맥과 정보 부족

| 사례 종류 | 맞힌 수 / 시도 |
|---|---:|
| alias | 12 / 12 |
| ambiguous_alias | 1 / 1 |
| clinical_result | 1 / 1 |
| context_contrast | 22 / 28 |
| explicit_schema | 4 / 4 |
| field_only | 8 / 10 |
| field_semantics | 1 / 1 |
| home_address | 2 / 2 |
| hypothetical | 0 / 1 |
| identifier_semantics | 1 / 1 |
| insufficient_schema | 2 / 2 |
| medication | 1 / 1 |
| mixed_value | 1 / 1 |
| name_component | 2 / 2 |
| negation | 4 / 4 |
| noisy_korean | 7 / 7 |
| opaque_alias | 5 / 5 |
| ordinary_public | 1 / 1 |
| prompt_injection | 3 / 8 |
| third_party | 4 / 4 |

원래부터 값이 비어 있는 입력은 14건이며 SemIf가 11건을 맞혔다. 이는 원래 입력 조건으로 작성한 기대값과 비교한 결과다. 값이 있던 입력에서 나중에 값을 제거하는 세 모드 시연과는 별도다.

대조쌍은 두 입력을 모두 맞힌 경우를 성공으로 계산한다: 8 / 14쌍.

## 오분류의 성격

| 진단 항목 | 사례 수 |
|---|---:|
| 일반 정보(OTHER)를 개인 관련 유형으로 분류 | 2 |
| 건강 정보를 다른 유형 또는 오류로 반환 | 2 |
| 건강·종교·정부번호 유형을 OTHER·UNKNOWN·오류로 반환 | 3 |
| 정보 부족(UNKNOWN)이 기대값인데 다른 유형으로 단정 | 2 |

항목은 서로 겹칠 수 있다. UNKNOWN은 실제 운영에서 검토 대상으로 남기므로, 이를 바로 개인정보가 없다는 결론으로 해석하면 안 된다. 모든 실시간 모델 출력은 현재 needs_review다.

## 높은 점수도 검토가 필요한 이유

선택지 점수가 90% 이상인 오분류는 12건이다. 이 값은 선택지 사이의 상대 선호도이며 정답 확률로 보정하지 않았다.

| 후보로 남기는 점수 기준 | 후보 수 | 후보 내 정답 | 후보 내 정확도 | 검토 수 |
|---|---:|---:|---:|---:|
| 60% | 80 | 72 | 90.0% | 16 |
| 80% | 80 | 72 | 90.0% | 16 |
| 90% | 78 | 70 | 89.7% | 18 |

UNKNOWN과 실행 오류는 위 후보에서 항상 제외한다. 임계값은 분석용이며 인가·법적 판단·실제 자동 승인을 바꾸지 않는다.

## 실제 SemIf 오분류 전체

| 사례 ID | 기대 | 실제 | 선택지 점수 |
|---|---|---|---:|
| ko96-h04 | HEALTH | UNKNOWN | 100.00% |
| ko96-h08 | HEALTH | OTHER | 98.91% |
| ko96-r12 | RELIGION | UNKNOWN | 91.62% |
| ko96-c08 | CONTACT | GOVERNMENT_ID | 100.00% |
| ko96-n07 | PERSON_NAME | RELIGION | 99.68% |
| ko96-a08 | ACCOUNT_ID | GOVERNMENT_ID | 100.00% |
| ko96-o01 | OTHER | HEALTH | 100.00% |
| ko96-o02 | OTHER | UNKNOWN | 88.76% |
| ko96-o07 | OTHER | ACCOUNT_ID | 100.00% |
| ko96-o08 | OTHER | UNKNOWN | 61.07% |
| ko96-o10 | OTHER | UNKNOWN | 99.17% |
| ko96-o11 | OTHER | UNKNOWN | 99.98% |
| ko96-u02 | UNKNOWN | PERSON_NAME | 100.00% |
| ko96-u04 | UNKNOWN | GOVERNMENT_ID | 100.00% |

원문·기대 이유·8개 선택지 점수는 실험실에서 사례 ID를 검색해 확인할 수 있다. 오류 사례만 바꾸거나 제거해서 성적을 다시 집계하지 않았다.

## 근거와 재현

- [원본 평가와 사례별 결과](../evidence/jev/evaluation.json)
- [288개 원본 시도 대조 감사](../evidence/jev/final-audit.json)
- [실행 당시 평가기와 강화 후 코드의 구분](../evidence/jev/evaluator-provenance.json)
- [시연·설치·새 이름으로 재현하기](korean-jev-demo.md)
- [실제 구현 아키텍처](korean-classification-architecture.md)
