"""Publish a traceable research-candidate summary without replacing raw runs."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/"evidence/model-alternative"


def read(name):
    path = OUT/name
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    candidates = []
    for prefix, model in [("qwen3-1p7b", "qwen3:1.7b-q4_K_M"), ("qwen3-4b", "qwen3:4b-q4_K_M")]:
        filename = prefix+"-isolated-v1-fixtures-metrics.json"
        metrics = read(filename)
        normalization = read(prefix+"-normalize-v1-metrics.json")
        if metrics["count"] != 24 or normalization["count"] != 8:
            raise ValueError("Cannot select a model from incomplete evaluations")
        candidates.append((metrics["accuracy"], normalization["accuracy"], prefix, model, filename, metrics, normalization))
    _, _, prefix, model, filename, metrics, normalization = max(candidates, key=lambda x:(x[0], x[1]))
    scope = "Authored synthetic development fixtures only; models selected on this same set. Not an independent held-out estimate, legal correctness, or production certification."
    shared = {
        "model": model, "model_id": model, "backend": "ollama_cpu_structured_generation",
        "status": "completed", "selection": "best_of_two_local_generative_research_candidates_on_authored_set",
        "source": "live_local_ollama", "external_inference": False,
        "created_at": datetime.now(timezone.utc).isoformat(), "production_ready": False,
        "scope": scope, "confidence_is_calibrated": False, "automatic_approval": False,
    }
    summary = {**shared, **metrics, "source_file": filename, "source_sha256": hashlib.sha256((OUT/filename).read_bytes()).hexdigest(),
               "beats_frozen_rule_baseline_on_authored_set": metrics["accuracy"]>metrics["baseline_accuracy"],
               "model_is_not": "Not TypeSafe Jev or SemIf; general Qwen3 generation with a JSON schema",
               "candidate_comparison": [{"model": c[3], "classification_accuracy": c[5]["accuracy"], "normalization_accuracy": c[6]["accuracy"]} for c in candidates]}
    alias_filename = prefix+"-normalize-v1-metrics.json"
    alias_summary = {**shared, **normalization, "source_file": alias_filename, "source_sha256": hashlib.sha256((OUT/alias_filename).read_bytes()).hexdigest()}
    for name, value in [("evaluation-summary.json", summary), ("normalize-summary.json", alias_summary)]:
        (OUT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"selected_model": model, "classification_correct": metrics["correct"], "classification_total": metrics["count"], "normalization_correct": normalization["correct"], "normalization_total": normalization["count"], "baseline_correct": metrics["baseline_correct"], "production_ready": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
