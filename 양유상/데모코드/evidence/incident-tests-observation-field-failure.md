# 사후 분석 독립 검사에서 발견한 필드 근거 오류

- 실행: `python -m unittest discover -s tests -p test_incidents.py -v`
- 최초 관측: 26개 중 25개 통과, 1개 실패.
- 실패 검사: `test_observation_field_absent_from_body_is_not_reported_as_returned`
- 조건: 저장된 마스킹 응답에는 `member_id`, `name`만 존재하지만, 파생 관측 행에 `canonical=consultation.reason`을 삽입.
- 기대: 실제 응답에 없는 상담 항목은 반환 필드 집계에서 제외.
- 실제: `api_calls.fields`가 `['consultation.reason', 'data_subject.id', 'person.name']`을 반환.

```text
AssertionError: 'consultation.reason' unexpectedly found in
['consultation.reason', 'data_subject.id', 'person.name']
Ran 26 tests in 0.007s
FAILED (failures=1)
```

수정 방향은 마스킹 응답에 실제로 존재하는 필드와 승인된 필드 매핑을 함께 확인하는 것이다. 이 문서는 최초 실패를 보존하며 최종 수정 검증은 `incident-tests.json`을 참조한다.

별도로 최초 23개 검사 중 1개는 테스트 기대값을 수정했다. 본문의 실제 U100과 파생 관측 행의 가짜 U999가 충돌할 때, 본문에 직접 남은 U100까지 버리고 0명을 기대했던 테스트였다. 본문의 U100은 유지하고 가짜 U999와 그 파생 필드를 제외하는 것이 타당하므로 해당 검사만 바로잡았다. 이는 제품 수정과 구분된다.
