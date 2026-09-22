"""Single-client local smoke measurement, not a production capacity test."""
import json
import math
import platform
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]


def measure(client, url, n=30):
    values = []
    for i in range(n + 3):
        started = time.perf_counter()
        response = client.get(url, headers={"Authorization": "Bearer demo-alice"})
        response.raise_for_status()
        if response.json().get('member_id') != 'U100':
            raise AssertionError('Unexpected benchmark response')
        elapsed = (time.perf_counter() - started) * 1000
        if i >= 3:
            values.append(round(elapsed, 3))
    ordered = sorted(values)
    return {"requests": n, "warmup": 3, "concurrency": 1, "p50_ms": round(statistics.median(values), 3), "p95_ms": ordered[math.ceil(n*.95)-1], "max_ms": max(values), "rows_ms": values}


if __name__ == '__main__':
    with httpx.Client(timeout=30, trust_env=False) as client:
        direct = measure(client, 'http://127.0.0.1:8811/fixed/profile/private/U100')
        proxy = measure(client, 'http://127.0.0.1:8810/proxy/fixed/profile/private/U100')
    result = {"status": "MEASURED", "created_at": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(), "direct": direct, "gateway_with_postgres_logging": proxy, "p50_difference_ms": round(proxy['p50_ms']-direct['p50_ms'], 3), "limitations": ["단일 클라이언트·작은 JSON·30회·로컬 Docker", "LLM 추론은 별도 비동기 작업이며 이 요청 경로에는 없음", "TLS/동시부하/장애복구/운영 SLA 검증 아님", "별도 모델 초기화 등 이 PC의 다른 작업 영향을 받을 수 있음"]}
    path = ROOT / 'evidence' / 'latency-smoke.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in result.items() if key not in ('direct', 'gateway_with_postgres_logging')}, ensure_ascii=False))
    print('direct p50/p95:', direct['p50_ms'], direct['p95_ms'])
    print('gateway p50/p95:', proxy['p50_ms'], proxy['p95_ms'])
