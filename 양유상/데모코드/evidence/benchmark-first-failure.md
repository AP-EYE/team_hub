# 첫 연속 요청 시험에서 발견한 실패

2026-09-22 로컬 단일 클라이언트 지연 측정을 수행하던 중, 프록시의 run 종료 상태 저장 단계에서 PostgreSQL 새 연결이 5초 안에 수립되지 않아 HTTP 500이 한 번 발생했다. 이 실행은 성공 성능 수치로 보고하지 않는다.

- 실패 위치: gateway/store.py connect() -> psycopg.connect(connect_timeout=5)
- 호출 경로: GET /proxy/fixed/profile/private/U100 -> store.finish_run
- 당시에는 매 저장·조회마다 새 TCP/DB 연결을 만들었다.
- 같은 PC에서 로컬 모델 평가와 Docker가 실행 중이었다. 시스템 부하 영향과 새 연결 비용을 분리해 원인을 확정한 것은 아니다.
- 조치: min1/max4 연결 풀을 도입해 반복 연결 수립을 제거하고, 연결/풀 실패를 명시적인 503으로 처리했다. 로컬 모델 작업도 한 번에 하나씩 제출해 대기 중 추론 요청의 타임아웃을 줄였다.
- 변경 후 성공 여부와 지연 수치는 latency-smoke.json 및 최종 integration-tests.json을 확인한다.
