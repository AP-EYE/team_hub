"""Live contract smoke; separate from evaluation accuracy measurements."""
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    checks = []
    with httpx.Client(base_url="http://127.0.0.1:8813", timeout=180, trust_env=False) as client:
        health = client.get("/health")
        checks.append({"name": "health", "status_code": health.status_code, "body": health.json(), "pass": health.status_code==200 and health.json()["model"]=="qwen3:4b-q4_K_M"})
        for route, payload, key, expected in [
            ("/classify", {"text": "demo@example.invalid", "field_path": "email", "description": "Fictional contact email"}, "label", "CONTACT"),
            ("/normalize", {"field_path": "customer_no", "description": "Identifier of the data subject described by the response"}, "canonical_field", "data_subject.id"),
        ]:
            response = client.post(route, json=payload)
            result = response.json()
            passed = response.status_code==200 and result[key]==expected and result["confidence"] is None and result["status"]=="needs_review" and result["source"]=="live_local_ollama"
            if route=="/normalize":
                passed = passed and result["approved"] is False
            checks.append({"name": route, "status_code": response.status_code, "body": result, "pass": passed})
        bad = client.post("/classify", json={"text": 12})
        checks.append({"name": "reject_nonstring", "status_code": bad.status_code, "pass": bad.status_code==400})
    output = {"run_time_utc": datetime.now(timezone.utc).isoformat(), "checks": checks, "passed": sum(c["pass"] for c in checks), "count": len(checks)}
    (ROOT/"evidence/model-alternative/worker-contract.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": output["passed"], "count": output["count"]}))
    if output["passed"] != output["count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
