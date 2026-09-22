r"""Independent HTTP acceptance evaluator. Uses only synthetic localhost fixtures.

Run after the demo is started:
  .venv\Scripts\python.exe tests\evaluate_demo.py
Expected labels are deliberately written here, not imported from the policy oracle.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


EXPECTED_VULNERABLE = {
    "owner": "allowed", "bola_profile": "confirmed", "bola_consult": "confirmed",
    "public": "allowed", "bopla": "confirmed", "bfla": "confirmed", "admin": "allowed",
    "shared": "allowed", "unshared": "blocked", "unknown": "needs_review",
    "tenant": "confirmed", "beta_owner": "allowed", "anonymous": "blocked",
    "general_info": "allowed", "order": "allowed", "general_consult": "allowed",
}
EXPECTED_FIXED = {
    **EXPECTED_VULNERABLE,
    "bola_profile": "blocked", "bola_consult": "blocked", "bopla": "allowed",
    "bfla": "blocked", "tenant": "blocked",
}
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class Evaluator:
    def __init__(self, base: str):
        parsed = urlsplit(base)
        if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("This evaluator only targets the local synthetic demo.")
        self.base = base.rstrip("/")
        self.results = []
        self.unit_tests = {"status": "NOT_RUN"}

    def request(self, path, payload=None, method=None, headers=None):
        data = None if payload is None else json.dumps(payload).encode()
        req = Request(self.base + path, data=data, method=method,
                      headers={"Content-Type": "application/json", **(headers or {})})
        try:
            response = urlopen(req, timeout=90)
        except HTTPError as error:
            response = error
        body = response.read().decode("utf-8")
        try:
            value = json.loads(body)
        except json.JSONDecodeError:
            value = body
        return response.status, value

    def check(self, case_id, description, condition, observed=None):
        result = {"id": case_id, "description": description,
                  "status": "PASS" if condition else "FAIL"}
        if observed is not None:
            result["observed"] = observed
        self.results.append(result)
        print(f"{result['status']:4} {case_id}: {description}")

    def run(self):
        status, initial = self.request("/api/state")
        self.check("HTTP-STATE", "state API is available", status == 200)
        if status != 200 or not isinstance(initial, dict):
            return
        initial_runs = {r["id"] if "id" in r else r["run_id"] for r in initial.get("runs", [])}
        snapshots = {}
        for mode, expected in (("vulnerable", EXPECTED_VULNERABLE), ("fixed", EXPECTED_FIXED)):
            status, execution = self.request("/api/demo/run", {"mode": mode})
            self.check(f"RUN-{mode}", "scenario execution completes", status == 200)
            if status != 200:
                continue
            status, state = self.request("/api/state")
            self.check(f"STATE-{mode}", "post-run state is available", status == 200)
            snapshots[mode] = state
            run_id = execution.get("run_id") or execution.get("id")
            if not run_id and isinstance(execution.get("run"), dict):
                run_id = execution["run"].get("id") or execution["run"].get("run_id")
            findings = [f for f in state.get("findings", []) if not run_id or f.get("run_id") == run_id]
            actual = {f.get("scenario_id"): f.get("verdict") for f in findings}
            self.check(f"COVERAGE-{mode}", "all 16 independent scenarios are recorded",
                       set(actual) == set(expected), {"expected": sorted(expected), "actual": sorted(str(x) for x in actual)})
            for scenario, verdict in expected.items():
                self.check(f"AUTH-{mode}-{scenario}", f"{scenario} has the specified policy outcome",
                           actual.get(scenario) == verdict,
                           {"expected": verdict, "actual": actual.get(scenario)})

            event_ids = {str(e.get("id") or e.get("event_id")) for e in state.get("events", [])}
            confirmed = [f for f in findings if f.get("verdict") == "confirmed"]
            self.check(f"EVIDENCE-{mode}", "confirmed findings reference observed events",
                       all(f.get("evidence_ids") and all(str(eid) in event_ids for eid in f["evidence_ids"]) for f in confirmed),
                       {"confirmed_count": len(confirmed)})
            case_events = {e.get("case_id"): e for e in state.get("events", [])}
            if mode == "vulnerable":
                observed = case_events.get("bola_profile", {})
                self.check("LOG-ACTOR-SUBJECT", "requester Bob and subject Alice remain distinct",
                           observed.get("actor_id") == "U200" and observed.get("subjects") == ["alpha:U100"])
                links = state.get("links", [])
                self.check("LINK-REAL-OBSERVATIONS", "same attacker observes profile and consultation for one subject",
                           any(link.get("actor") == "bob" and link.get("tenant") == "alpha" and link.get("subject_id") == "U100"
                               and "person.phone" in link.get("fields", []) and "consultation.reason" in link.get("fields", []) for link in links))
                self.check("LINK-TENANT-ISOLATION", "same identifier in beta is not merged into alpha",
                           all(not any(str(path).startswith("tenants/beta/") for path in link.get("endpoints", []))
                               for link in links if link.get("tenant") == "alpha"))
                self.check("LINK-EXPOSURE-COUNT", "three distinct tenant-scoped subjects are observed across confirmed responses",
                           state.get("summary", {}).get("subjects") == 3, state.get("summary", {}).get("subjects"))
            else:
                self.check("FIXED-NO-LINKS", "fixed authorization leaves no confirmed exposure joins", state.get("links") == [])
            self.check(f"LOG-INTEGRITY-{mode}", "all stored event payload checksums match",
                       bool(state.get("events")) and all(e.get("integrity_ok") is True for e in state.get("events", [])))
            serial = json.dumps(state, ensure_ascii=False)
            self.check(f"SECRET-{mode}", "fixture bearer tokens are absent from state",
                       all(token not in serial for token in
                           ("demo-alice", "demo-bob", "demo-admin", "demo-mallory")))

        if "vulnerable" in snapshots and "fixed" in snapshots:
            before = snapshots["vulnerable"]
            after = snapshots["fixed"]
            old_runs = initial_runs | {str(r.get("id") or r.get("run_id")) for r in before.get("runs", [])}
            # The UI intentionally returns only recent history. Check persisted rows,
            # not pagination visibility, to determine whether old evidence survived.
            from gateway import store
            with store.connect() as connection:
                stored_runs = {row["id"] for row in connection.execute("SELECT id FROM runs WHERE id = ANY(%s)", (list(old_runs),)).fetchall()}
                before_ids = [e["id"] for e in before.get("events", [])]
                stored_events = connection.execute("SELECT id, sha256 FROM events WHERE id = ANY(%s)", (before_ids,)).fetchall()
            self.check("LOG-APPEND-RUNS", "new run preserves old run identities in PostgreSQL", old_runs == stored_runs)
            preserved_hashes = {row["id"]: row["sha256"] for row in stored_events}
            self.check("LOG-PRESERVED-EVENTS", "prior run event identities and payload hashes persist in PostgreSQL",
                       all(preserved_hashes.get(e["id"]) == e.get("sha256") for e in before.get("events", [])))
            old_events = {str(e.get("id") or e.get("event_id")) for e in before.get("events", [])}
            new_events = {str(e.get("id") or e.get("event_id")) for e in after.get("events", [])}
            self.check("LOG-APPEND-EVENTS", "database event count accumulates across runs",
                       after.get("summary", {}).get("total_events", 0) >= before.get("summary", {}).get("total_events", 0) + 16)
            self.check("LOG-NEW-EVENTS", "second run creates separate new observations", len(new_events - old_events) >= 16)

        status, _ = self.request("/proxy/fixed/profile/private/U100", headers={"Authorization": "Bearer unknown-synthetic-test-token"})
        self.check("HTTP-UNKNOWN-TOKEN", "unknown credentials cannot access private data", status == 401)
        status, _ = self.request("/proxy/vulnerable/profile/private/U100", method="POST", payload={"marker": "no-write"})
        self.check("HTTP-NO-WRITES", "gateway refuses state-changing methods", status == 405)
        status, _ = self.request("/proxy/not-a-mode/profile/private/U100", headers={"Authorization": "Bearer demo-alice"})
        self.check("HTTP-UNKNOWN-MODE", "gateway rejects an unsupported upstream mode", status in {400, 404, 422})

        # Canary is deliberately synthetic and safe. It must not appear in persisted state/report.
        marker = "synthetic-secret-canary-do-not-log-8759"
        self.request("/proxy/fixed/profile/public/U100?access_token=" + marker,
                     headers={"Authorization": "Bearer " + marker, "Cookie": "session=" + marker})
        _, final_state = self.request("/api/state")
        report_status, report = self.request("/api/report")
        self.check("HTTP-REPORT", "report API returns an export", report_status == 200)
        combined = json.dumps([final_state, report], ensure_ascii=False)
        self.check("SECRET-QUERY-HEADERS", "raw query/header/cookie canary is not retained or exported", marker not in combined)

        stream = io.StringIO()
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_semantics.py")
        unit = unittest.TextTestRunner(stream=stream, verbosity=1).run(suite)
        self.unit_tests = {"status": "PASS" if unit.wasSuccessful() else "FAIL", "tests_run": unit.testsRun,
                           "failures": len(unit.failures), "errors": len(unit.errors), "skipped": len(unit.skipped),
                           "output": stream.getvalue()}
        self.check("SEMANTIC-UNIT-SUITE", "independent semantic edge cases all pass", unit.wasSuccessful(),
                   {"tests_run": unit.testsRun, "failures": len(unit.failures), "errors": len(unit.errors)})

    def save(self, output):
        passed = sum(r["status"] == "PASS" for r in self.results)
        document = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "scope": "Local synthetic fixture integration; independent expected outcomes, not production certification",
            "target": self.base,
            "status": "PASS" if self.results and passed == len(self.results) else "FAIL",
            "total": len(self.results), "passed": passed, "failed": len(self.results) - passed,
            "cases": self.results,
            "unit_tests": self.unit_tests,
            "source_sha256": {str(file.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(file.read_bytes()).hexdigest()
                              for folder in (ROOT / "gateway", ROOT / "tests") for file in folder.glob("*.py")},
            "limitations": [
                "Expected authorization policies are synthetic and explicitly supplied.",
                "A passing fixture does not demonstrate universal field mapping or legal identifiability.",
                "Local model accuracy/latency are evaluated in separate model evidence.",
                "Gateway full production hardening and performance are outside this acceptance run.",
            ],
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        return document


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8810")
    parser.add_argument("--output", type=Path, default=ROOT / "evidence" / "integration-tests.json")
    args = parser.parse_args()
    evaluator = Evaluator(args.base)
    started = time.perf_counter()
    try:
        evaluator.run()
    except Exception as exc:
        evaluator.check("EVALUATOR-ERROR", "evaluator completes without a transport or schema error", False,
                        {"type": type(exc).__name__, "message": str(exc)})
    report = evaluator.save(args.output)
    print(json.dumps({"status": report["status"], "passed": report["passed"], "total": report["total"],
                      "elapsed_seconds": round(time.perf_counter() - started, 3), "evidence": str(args.output)}, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
