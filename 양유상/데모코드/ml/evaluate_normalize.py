import hashlib
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from ml.engine import LocalClassifier
from ml.normalize import normalize

ROOT = Path(__file__).resolve().parents[1]


def run(engine=None):
    engine = engine or LocalClassifier()
    fixture = ROOT / "ml/normalize-fixtures.jsonl"
    rows = []
    for line in fixture.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        result = normalize(engine, case["field_path"], case["description"])
        rows.append({**case, "result": result, "correct": result["canonical_field"] == case["gold"]})
        print(json.dumps({"id": case["id"], "gold": case["gold"], "prediction": result["canonical_field"], "latency_ms": result["latency_ms"]}), flush=True)
    evidence = ROOT / "evidence/model"
    (evidence / "normalize-rows.jsonl").write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
    summary = {"n": len(rows), "accuracy": sum(row["correct"] for row in rows) / len(rows),
               "errors": [row["id"] for row in rows if not row["correct"]],
               "median_latency_ms": statistics.median(row["result"]["latency_ms"] for row in rows),
               "created_at": datetime.now(timezone.utc).isoformat(), "model_revision": engine.revision,
               "fixture_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
               "normalize_sha256": hashlib.sha256((ROOT / "ml/normalize.py").read_bytes()).hexdigest(),
               "scope": "8 authored synthetic schema-only alias cases; no independent test set, not production accuracy; all proposals need review"}
    (evidence / "normalize-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    run()
