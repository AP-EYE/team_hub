"""Evaluate the frozen mapping prompt on the existing eight synthetic rows."""
import argparse
import hashlib
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

from .normalize import SYSTEM, SCHEMA, PROMPT_SHA256, normalize
from .engine import MODEL

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/"evidence/model-alternative"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default=datetime.now(timezone.utc).strftime("normalize-%Y%m%dT%H%M%SZ"))
    parser.add_argument("--model", choices=["qwen3:1.7b-q4_K_M", "qwen3:4b-q4_K_M"], default=MODEL)
    args = parser.parse_args()
    rows = [json.loads(line) for line in (ROOT/"ml/normalize-fixtures.jsonl").read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    results = []
    with (OUT/(args.name+".jsonl")).open("x", encoding="utf-8") as handle:
        for row in rows:
            record = {"id": row["id"], "gold": row["gold"]}
            try:
                result = normalize(row["field_path"], row.get("description", ""), model=args.model)
                record.update(prediction=result["canonical_field"], **result)
            except Exception as exc:
                record["error"] = f"{type(exc).__name__}: {exc}"
            handle.write(json.dumps(record, ensure_ascii=False)+"\n")
            handle.flush()
            results.append(record)
            print(json.dumps({k:record.get(k) for k in ("id", "gold", "prediction", "latency_ms", "error")}, ensure_ascii=False), flush=True)
    summary = {
        "run_time_utc": datetime.now(timezone.utc).isoformat(),
        "model": args.model,
        "count": len(results), "correct": sum(r.get("prediction")==r["gold"] for r in results),
        "accuracy": sum(r.get("prediction")==r["gold"] for r in results)/len(results),
        "errors": sum("error" in r for r in results),
        "median_latency_ms": statistics.median(r["latency_ms"] for r in results if "latency_ms" in r),
        "prompt": SYSTEM, "prompt_sha256": PROMPT_SHA256, "schema": SCHEMA,
        "fixture_sha256": hashlib.sha256((ROOT/"ml/normalize-fixtures.jsonl").read_bytes()).hexdigest(),
        "limitations": "Eight fixed synthetic examples, development comparison only; no holdout/generalization claim; definition-only prompt, no gold labels in inference inputs",
    }
    (OUT/(args.name+"-metrics.json")).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("SUMMARY", json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
