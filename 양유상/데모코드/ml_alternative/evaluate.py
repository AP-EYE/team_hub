"""Run independent smoke examples then the existing fixed 24-item evaluation."""
import argparse
import hashlib
import json
import math
import statistics
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import httpx

from ml.engine import rule_baseline
from .engine import MODEL, PROMPT_SHA256, SCHEMA, SYSTEM, classify, endpoint

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/model-alternative"
SMOKE = [
    {"id": "smoke-contact-en", "text": "person@example.invalid", "field_path": "email", "description": "A fictional person's email address", "gold": "CONTACT"},
    {"id": "smoke-health-ko", "text": "어제부터 가상 인물의 무릎에 통증이 있습니다.", "field_path": "patient_note", "description": "가상 환자의 증상 기록", "gold": "HEALTH"},
    {"id": "smoke-account-en", "text": "SYNTHETIC-7781", "field_path": "account_id", "description": "Internal account identifier", "gold": "ACCOUNT_ID"},
    {"id": "smoke-unknown-en", "text": "", "field_path": "x", "description": "", "gold": "UNKNOWN"},
]


def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def metrics(rows):
    labels = SCHEMA["properties"]["label"]["enum"]
    per_class = {}
    for label in labels:
        tp = sum(r.get("prediction") == label and r["gold"] == label for r in rows)
        fp = sum(r.get("prediction") == label and r["gold"] != label for r in rows)
        fn = sum(r.get("prediction") != label and r["gold"] == label for r in rows)
        precision = tp/(tp+fp) if tp+fp else 0
        recall = tp/(tp+fn) if tp+fn else 0
        per_class[label] = {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": 2*precision*recall/(precision+recall) if precision+recall else 0}
    times = sorted(r["latency_ms"] for r in rows if "latency_ms" in r)
    return {
        "count": len(rows), "correct": sum(r.get("prediction") == r["gold"] for r in rows),
        "accuracy": sum(r.get("prediction") == r["gold"] for r in rows)/len(rows),
        "baseline_correct": sum(r.get("baseline") == r["gold"] for r in rows),
        "baseline_accuracy": sum(r.get("baseline") == r["gold"] for r in rows)/len(rows),
        "macro_f1": statistics.mean(v["f1"] for v in per_class.values()),
        "per_class": per_class,
        "prediction_counts": dict(Counter(r.get("prediction", "ERROR") for r in rows)),
        "errors": sum("error" in r for r in rows),
        "median_latency_ms": statistics.median(times) if times else None,
        "p95_latency_ms": times[max(0, math.ceil(len(times)*.95)-1)] if times else None,
        "p95_definition": "sorted nearest-rank ceil(0.95*n), no cold/warm filtering",
    }


def run(rows, name, model=MODEL):
    records = []
    path = OUT / (name + ".jsonl")
    # Unique experiment names protect earlier results against accidental overwrite.
    with path.open("x", encoding="utf-8") as handle:
        for row in rows:
            record = {"id": row["id"], "gold": row["gold"], "slice": row.get("slice", "smoke"),
                      "baseline": rule_baseline(row["text"], row.get("field_path", ""), row.get("description", ""))}
            start = time.perf_counter()
            try:
                result = classify(row["text"], row.get("field_path", ""), row.get("description", ""), model=model)
                record.update(prediction=result["label"], **result)
            except Exception as exc:
                record.update(error=f"{type(exc).__name__}: {exc}", latency_ms=round((time.perf_counter()-start)*1000,2))
            records.append(record)
            handle.write(json.dumps(record, ensure_ascii=False)+"\n")
            handle.flush()
            print(json.dumps({"id": record["id"], "gold": record["gold"], "prediction": record.get("prediction"), "error": record.get("error"), "latency_ms": record.get("latency_ms")}, ensure_ascii=False), flush=True)
    summary = metrics(records)
    save(name + "-metrics.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--smoke-only", action="store_true")
    parser.add_argument("--model", choices=["qwen3:1.7b-q4_K_M", "qwen3:4b-q4_K_M"], default=MODEL)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    tags = httpx.get(endpoint()+"/api/tags", trust_env=False, timeout=10).json()
    version = httpx.get(endpoint()+"/api/version", trust_env=False, timeout=10).json()
    save(args.name+"-provenance.json", {
        "run_time_utc": datetime.now(timezone.utc).isoformat(), "endpoint": endpoint(),
        "model": args.model, "version": version,
        "model_metadata": [x for x in tags.get("models",[]) if x["name"]==args.model],
        "prompt_sha256": PROMPT_SHA256, "prompt": SYSTEM, "schema": SCHEMA,
        "fixture_sha256": hashlib.sha256((ROOT/"ml/fixtures.jsonl").read_bytes()).hexdigest(),
        "frozen_prompt_origin": "Only class definitions from ml.engine.LABELS; no fixture examples/gold in prompt",
        "model_network": "HTTP loopback; no cloud inference; preexisting official-digest local weights",
        "sources": ["https://ollama.com/library/qwen3:1.7b", "https://docs.ollama.com/capabilities/structured-outputs", "https://docs.ollama.com/capabilities/thinking"],
    })
    smoke = run(SMOKE, args.name+"-smoke", args.model)
    print("SMOKE", json.dumps(smoke, ensure_ascii=False), flush=True)
    if not args.smoke_only and smoke["errors"] == 0:
        rows = [json.loads(line) for line in (ROOT/"ml/fixtures.jsonl").read_text(encoding="utf-8-sig").splitlines() if line.strip()]
        summary = run(rows, args.name+"-fixtures", args.model)
        print("FIXTURES", json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
