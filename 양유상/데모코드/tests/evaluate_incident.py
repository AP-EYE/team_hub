"""Read-only HTTP/DB acceptance checks against a prepared synthetic incident run.

The caller prepares the scene and may stop the mock backend separately. This
evaluator never generates API traffic, starts/stops a service, or writes to DB.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import socket
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def snapshot(run_id):
    from gateway import store

    with store.connect() as connection:
        tables = {
            "runs": connection.execute("SELECT * FROM runs WHERE id=%s ORDER BY id", (run_id,)).fetchall(),
            "events": connection.execute("SELECT * FROM events WHERE run_id=%s ORDER BY id", (run_id,)).fetchall(),
            "findings": connection.execute("SELECT * FROM findings WHERE run_id=%s ORDER BY id", (run_id,)).fetchall(),
            "observations": connection.execute("SELECT * FROM observations WHERE run_id=%s ORDER BY id", (run_id,)).fetchall(),
            "model_results": connection.execute("SELECT m.* FROM model_results m JOIN events e ON m.event_id=e.id WHERE e.run_id=%s ORDER BY m.id", (run_id,)).fetchall(),
        }
        counts = {table: connection.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]
                  for table in ("runs", "events", "findings", "observations", "model_results")}
    return tables, counts


def summary_snapshot(tables, counts):
    return {"table_rows": {name: len(rows) for name, rows in tables.items()},
            "table_sha256": {name: hashlib.sha256(canonical(rows).encode()).hexdigest() for name, rows in tables.items()},
            "global_row_counts": counts}


class Evaluator:
    def __init__(self, base, run_id, backend_offline=False):
        if urlsplit(base).hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("This evaluator only targets the localhost synthetic demo.")
        self.base = base.rstrip("/")
        self.run_id = run_id
        self.backend_offline = backend_offline
        self.results = []
        self.requests = []
        self.unit_tests = {"status": "NOT_RUN"}
        self.db_snapshots = {}

    def request(self, route, **query):
        path = route + ("?" + urlencode(query) if query else "")
        request = Request(self.base + path, method="GET")
        try:
            response = urlopen(request, timeout=30)
        except HTTPError as error:
            response = error
        raw = response.read().decode("utf-8")
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            value = raw
        self.requests.append({"method": "GET", "path": path, "status_code": response.status})
        return response.status, value

    def check(self, case_id, description, condition, observed=None):
        record = {"id": case_id, "description": description, "status": "PASS" if condition else "FAIL"}
        if observed is not None:
            record["observed"] = observed
        self.results.append(record)
        print(f"{record['status']:4} {case_id}: {description}")

    def run(self):
        before, counts_before = snapshot(self.run_id)
        self.db_snapshots["before"] = summary_snapshot(before, counts_before)
        self.check("FIXTURE-EXISTS", "prepared synthetic run has exactly 14 original request records",
                   len(before["runs"]) == 1 and len(before["events"]) == 14,
                   {"runs": len(before["runs"]), "events": len(before["events"])})
        if not before["runs"]:
            return

        if self.backend_offline:
            reachable = False
            try:
                with socket.create_connection(("127.0.0.1", 8811), timeout=2):
                    reachable = True
            except OSError:
                pass
            self.check("MOCK-BACKEND-OFFLINE", "mock backend port 8811 is unavailable during analysis", not reachable)

        status, run_list = self.request("/api/incidents/runs")
        self.check("LIST-HISTORY", "incident history includes selected persisted run",
                   status == 200 and self.run_id in canonical(run_list))
        status, full = self.request("/api/incidents/analyze", run_id=self.run_id, actor="bob", capture="full")
        self.check("ANALYZE-HTTP", "stored-log analysis responds successfully", status == 200)
        if not isinstance(full, dict) or "summary" not in full:
            return
        expected = {"logged_requests": 13, "api_count": 8, "http_success": 11, "denied": 1, "other": 1,
                    "confirmed_policy_requests": 7, "returned_subjects": 3, "confirmed_exposure_subjects": 3}
        for key, number in expected.items():
            self.check("SUMMARY-" + key, "Bob incident " + key + " matches independent expected outcome",
                       full["summary"].get(key) == number,
                       {"expected": number, "actual": full["summary"].get(key)})
        private = [api for api in full.get("api_calls", []) if "profile/private/U999" in api.get("paths", [])]
        self.check("API-RETRIES-AND-404", "registered private API groups retries, self lookup, and missing target",
                   len(private) == 1 and private[0].get("requests") == 4 and private[0].get("other") == 1,
                   private)
        self.check("ATTEMPT-IS-NOT-RETURN", "missing U999 is an attempted target and absent from returned subjects",
                   len(private) == 1 and "U999" in canonical(private[0].get("requested_targets"))
                   and "U999" not in canonical(private[0].get("returned_subject_keys")))
        returned = {key for api in full.get("api_calls", []) for key in api.get("returned_subject_keys", [])}
        self.check("CROSS-TENANT-IDENTITY", "alpha and beta member U100 retain separate namespace-qualified identities",
                   len(returned) == 3 and any("alpha" in key and "U100" in key for key in returned)
                   and any("beta" in key and "U100" in key for key in returned), sorted(returned))

        bob_rows = [row for row in before["events"] if row["payload"].get("actor") == "bob"]
        earliest = min(row["created_at"] for row in bob_rows)
        expected_at_time = sum(row["created_at"] == earliest for row in bob_rows)
        status, bounded = self.request("/api/incidents/analyze", run_id=self.run_id, actor="bob", capture="full",
                                       start=earliest.isoformat(), end=earliest.isoformat())
        self.check("TIME-INCLUSIVE", "same start/end timestamp includes precisely matching stored calls",
                   status == 200 and bounded.get("summary", {}).get("logged_requests") == expected_at_time)

        status, admin = self.request("/api/incidents/analyze", run_id=self.run_id, actor="admin", capture="full")
        self.check("ACTOR-SEPARATION", "administrator's one permitted export is separate and unconfirmed",
                   status == 200 and admin.get("summary", {}).get("logged_requests") == 1
                   and admin.get("summary", {}).get("confirmed_policy_requests") == 0)
        status, empty = self.request("/api/incidents/analyze", run_id=self.run_id, actor="absent-actor", capture="full")
        self.check("EMPTY-SELECTION", "no caller match returns zero observed logs without invented exposure",
                   status == 200 and empty.get("summary", {}).get("logged_requests") == 0
                   and empty.get("summary", {}).get("returned_subjects") == 0)

        status, metadata = self.request("/api/incidents/analyze", run_id=self.run_id, actor="bob", capture="metadata_only")
        metadata_summary = metadata.get("summary", {}) if isinstance(metadata, dict) else {}
        self.check("METADATA-REQUEST-COUNTS", "metadata-only view retains request and status observations",
                   status == 200 and all(metadata_summary.get(key) == expected[key]
                                        for key in ("logged_requests", "api_count", "http_success", "denied", "other")))
        self.check("METADATA-UNKNOWN-NOT-ZERO", "missing response evidence returns null subject and confirmed counts",
                   all(key in metadata_summary and metadata_summary[key] is None
                       for key in ("returned_subjects", "confirmed_exposure_subjects", "confirmed_policy_requests")))
        self.check("METADATA-NO-RESPONSE-FACTS", "metadata-only endpoint groups omit subject and field evidence",
                   all(not api.get("returned_subject_keys") and not api.get("fields") for api in metadata.get("api_calls", [])))

        status, markdown = self.request("/api/incidents/report", run_id=self.run_id, actor="bob", capture="full")
        self.check("MARKDOWN-EXPORT", "read-only Markdown export names its run and caller",
                   status == 200 and isinstance(markdown, str) and self.run_id in markdown and "bob" in markdown)
        for case_id, filters in (("BAD-CAPTURE", {"capture": "all-data-invented"}),
                                 ("NAIVE-TIME", {"start": "2026-09-22T00:00:00"}),
                                 ("BAD-TIME", {"start": "invalid"}),
                                 ("REVERSED-TIME", {"start": "2026-09-23T00:00:00Z", "end": "2026-09-22T00:00:00Z"})):
            status, _ = self.request("/api/incidents/analyze", run_id=self.run_id, actor="bob", **filters)
            self.check(case_id, "invalid analysis filters are rejected", status in {400, 422}, {"status_code": status})
        status, _ = self.request("/api/incidents/analyze", run_id="incident-run-that-does-not-exist", actor="bob")
        self.check("UNKNOWN-RUN", "unknown run reports not found", status == 404)

        stream = io.StringIO()
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_incidents.py")
        unit = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        self.unit_tests = {"status": "PASS" if unit.wasSuccessful() else "FAIL", "tests_run": unit.testsRun,
                           "failures": len(unit.failures), "errors": len(unit.errors), "skipped": len(unit.skipped),
                           "output": stream.getvalue()}
        self.check("INCIDENT-UNIT-SUITE", "independent evidence, filtering, and normalization edge cases pass",
                   unit.wasSuccessful(), {key: self.unit_tests[key] for key in ("tests_run", "failures", "errors")})
        after, counts_after = snapshot(self.run_id)
        self.db_snapshots["after"] = summary_snapshot(after, counts_after)
        for table in before:
            self.check("READONLY-" + table, f"GET analysis/export preserves every original {table} row",
                       canonical(before[table]) == canonical(after[table]))
        self.check("READONLY-GLOBAL-COUNTS", "analysis creates no run, event, finding, observation, or model result",
                   counts_before == counts_after, {"before": counts_before, "after": counts_after})
        self.check("NO-REPLAY-ROUTES", "evaluator called only read-only incident GET endpoints",
                   all(row["method"] == "GET" and row["path"].startswith("/api/incidents/") for row in self.requests))

    def save(self, output):
        passed = sum(row["status"] == "PASS" for row in self.results)
        document = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "scope": "Synthetic saved-log incident analysis, distinct from predicting total breach scope or production certification",
            "run_id": self.run_id, "target": self.base, "backend_offline_requested": self.backend_offline,
            "status": "PASS" if self.results and passed == len(self.results) else "FAIL",
            "total": len(self.results), "passed": passed, "failed": len(self.results) - passed,
            "cases": self.results, "unit_tests": self.unit_tests,
            "database_snapshots": self.db_snapshots, "http_requests": self.requests,
            "source_sha256": {str(path.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
                              for path in (ROOT / "gateway" / "incident.py", Path(__file__), ROOT / "tests" / "test_incidents.py")},
            "limitations": [
                "Only observed saved synthetic logs are analyzed; missing or bypassed traffic is unknown.",
                "Stored response checksums detect changes relative to a stored digest, not tamper-proof signatures.",
                "Explicitly supplied authorization policies determine confirmation, never a classifier label.",
                "Unit suite is included as one acceptance check; its count must not be added to acceptance totals.",
            ],
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        return document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8810")
    parser.add_argument("--run-id", required=True, help="An existing prepared 14-event incident scene; never created by this evaluator.")
    parser.add_argument("--backend-offline", action="store_true", help="Verify mock API port 8811 was stopped by the caller.")
    parser.add_argument("--output", type=Path, default=ROOT / "evidence" / "incident-tests.json")
    arguments = parser.parse_args()
    evaluator = Evaluator(arguments.base, arguments.run_id, arguments.backend_offline)
    try:
        evaluator.run()
    except Exception as error:
        evaluator.check("EVALUATOR-ERROR", "evaluator completes without unhandled infrastructure error", False,
                        {"type": type(error).__name__, "message": str(error)})
    result = evaluator.save(arguments.output)
    print(f"{result['status']}: {result['passed']}/{result['total']} checks; {arguments.output}")
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
