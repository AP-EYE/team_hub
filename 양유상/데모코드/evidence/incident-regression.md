# 사후 분석 추가 후 기존 의미 검사 회귀 결과

2026-09-22 이 작업에서 실제 실행한 명령:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

실제 종료 코드: 0

```text
.............................................         [100%]
45 passed, 19 subtests passed in 1.40s
```

45개는 기존 의미 검사 17개와 새 사후 분석 검사 28개의 합계다. 19개 subtest를 별도 독립 테스트로 더하지 않는다. 실제 HTTP/DB 사후 분석 검사는 incident-tests.json, 업무 API 중지 상태의 조회 증거는 incident-offline-proof.json을 참고한다. 기존 인가 HTTP 60개 검사를 이번 변경에서 다시 실행한 것으로 표시하지 않는다.
