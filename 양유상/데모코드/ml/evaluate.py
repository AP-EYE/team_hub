"""Reproducible, authored synthetic fixture comparison, not production benchmark."""
import argparse
import hashlib
import json
import platform
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from ml.engine import LocalClassifier, LABELS, rule_baseline

ROOT = Path(__file__).resolve().parents[1]


def metrics(rows, prediction):
    labels = sorted({row["gold"] for row in rows})
    per_label = {}
    for label in labels:
        tp = sum(row["gold"] == label and row[prediction] == label for row in rows)
        fp = sum(row["gold"] != label and row[prediction] == label for row in rows)
        fn = sum(row["gold"] == label and row[prediction] != label for row in rows)
        precision = tp / (tp + fp) if tp + fp else 0
        recall = tp / (tp + fn) if tp + fn else 0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
        per_label[label] = {"support": tp + fn, "precision": precision, "recall": recall, "f1": f1}
    return {"n": len(rows), "accuracy": sum(row["gold"] == row[prediction] for row in rows) / len(rows),
            "macro_f1": statistics.mean(x["f1"] for x in per_label.values()),
            "balanced_accuracy": statistics.mean(x["recall"] for x in per_label.values()), "per_label": per_label,
            "errors": [row["id"] for row in rows if row["gold"] != row[prediction]]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--name", default="evaluation")
    args = parser.parse_args()
    fixture = ROOT / "ml/fixtures.jsonl"
    cases = [json.loads(line) for line in fixture.read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.limit:
        cases = cases[:args.limit]
    model = LocalClassifier()
    output = ROOT / "evidence/model" / f"{args.name}-rows.jsonl"
    rows = []
    with output.open("w", encoding="utf-8") as result_file:
        for case in cases:
            result = model.classify(case["text"], case["field_path"], case["description"])
            row = {**case, "baseline_prediction": rule_baseline(case["text"], case["field_path"], case["description"]),
                   "model_prediction": result["label"], "model_result": result}
            rows.append(row)
            result_file.write(json.dumps(row, ensure_ascii=False) + "\n")
            result_file.flush()
            print(json.dumps({"id": case["id"], "gold": case["gold"], "baseline": row["baseline_prediction"], "model": result["label"], "latency_ms": result["latency_ms"]}), flush=True)
    latencies = sorted(row["model_result"]["latency_ms"] for row in rows)
    summary = {"status": "completed", "created_at": datetime.now(timezone.utc).isoformat(), "model_id": "Qwen/Qwen3-0.6B",
               "model_revision": model.revision, "runtime": {"python": sys.version, "platform": platform.platform(), "torch": model.torch.__version__, "device": "cpu", "threads": model.torch.get_num_threads()},
               "fixture_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
               "engine_sha256": hashlib.sha256((ROOT / "ml/engine.py").read_bytes()).hexdigest(),
               "model_load_seconds": model.load_seconds, "model": metrics(rows, "model_prediction"),
               "baseline": metrics(rows, "baseline_prediction"), "slices": {name: {"model": metrics([row for row in rows if row["slice"] == name], "model_prediction"), "baseline": metrics([row for row in rows if row["slice"] == name], "baseline_prediction")} for name in sorted({row["slice"] for row in rows})},
               "latency_ms": {"median": statistics.median(latencies), "p95_nearest_rank": latencies[max(0, int(__import__('math').ceil(.95 * len(latencies))) - 1)], "min": min(latencies), "max": max(latencies)},
               "scope": "24 authored synthetic Korean fixtures; no independent test set, no training, no calibration, not legal correctness or production reliability", "confidence_is_calibrated": False}
    (ROOT / "evidence/model" / f"{args.name}-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"summary": args.name, "model_accuracy": summary["model"]["accuracy"], "baseline_accuracy": summary["baseline"]["accuracy"], "latency_ms": summary["latency_ms"]}), flush=True)
    if not args.limit:
        from ml.evaluate_normalize import run
        run(model)


if __name__ == "__main__":
    main()
