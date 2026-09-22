"""Independent stored-log analysis tests; no API replay, database, or model calls."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gateway.incident import analyze_records, endpoint_key


RUN_ID = "independent-incident-unit-run"
NAMESPACE = "synthetic-member-v1"
BASE_TIME = datetime(2026, 9, 22, 0, 0, tzinfo=timezone.utc)
RUN = {"id": RUN_ID, "created_at": BASE_TIME, "mode": "incident_fixture", "status": "completed"}


def digest(payload):
    # Intentionally independent from store.checksum to test the serialization contract.
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def fixture(event_id=1, actor="bob", tenant="alpha", subject="U100", path="profile/private/U100",
            status=200, verdict="confirmed", policy_state="approved", expected="deny", body="default"):
    if body == "default":
        body = {"tenant_id": tenant, "member_id": subject, "name": "[REDACTED:NAME]"}
    payload = {
        "run_id": RUN_ID, "case_id": f"independent-{event_id}", "actor": actor,
        "actor_id": "U200" if actor == "bob" else "A001", "actor_tenant": "alpha",
        "method": "GET", "path": path, "status_code": status, "synthetic": True,
        "request_redacted": {"method": "GET", "path": path, "query_keys_only": []},
        "response_redacted": body,
        "policy": {"state": policy_state, "expected": expected, "version": "independent-test-v1",
                   "reason": "Independent approved fixture contract", "category": "BOLA"},
        "privacy": [{"path": "member_id", "canonical": "data_subject.id", "label": "SERVICE_ID"},
                    {"path": "name", "canonical": "person.name", "label": "NAME"}],
        "subjects": [f"{tenant}:{subject}"],
    }
    event = {"id": event_id, "run_id": RUN_ID, "created_at": BASE_TIME + timedelta(minutes=event_id),
             "payload": payload, "sha256": digest(payload)}
    finding = {"id": event_id, "run_id": RUN_ID,
               "payload": {"run_id": RUN_ID, "evidence_ids": [event_id], "actor": actor,
                           "verdict": verdict, "category": "BOLA", "reason": "Independent stored finding"}}
    observations = [{"id": event_id * 10 + index, "event_id": event_id, "run_id": RUN_ID,
                     "actor": actor, "tenant": tenant, "namespace": NAMESPACE,
                     "subject_id": subject, "canonical": canonical, "path": path,
                     "confirmed": verdict == "confirmed"}
                    for index, canonical in enumerate(("data_subject.id", "person.name"))]
    return event, finding, observations


def report(*cases, models=None, **filters):
    return analyze_records(RUN, [case[0] for case in cases], [case[1] for case in cases],
                           [ob for case in cases for ob in case[2]], models or [], **filters)


class IncidentEvidenceTests(unittest.TestCase):
    def test_retry_is_another_request_but_not_another_person(self):
        result = report(fixture(1), fixture(2), fixture(3))
        self.assertEqual(result["summary"]["logged_requests"], 3)
        self.assertEqual(result["summary"]["confirmed_policy_requests"], 3)
        self.assertEqual(result["summary"]["returned_subjects"], 1)
        self.assertEqual(result["summary"]["confirmed_exposure_subjects"], 1)
        self.assertEqual(result["summary"]["api_count"], 1)

    def test_same_number_in_two_tenants_is_two_people(self):
        result = report(fixture(1), fixture(2, tenant="beta", path="tenants/beta/profile/U100"))
        self.assertEqual(result["summary"]["returned_subjects"], 2)
        self.assertEqual(result["summary"]["confirmed_exposure_subjects"], 2)

    def test_export_multiple_records_count_distinct_subjects(self):
        case = fixture(1, path="admin/export", body={"records": [
            {"tenant_id": "alpha", "member_id": "U100", "name": "[REDACTED:NAME]"},
            {"tenant_id": "alpha", "member_id": "U200", "name": "[REDACTED:NAME]"}]})
        second = copy.deepcopy(case[2])
        for ob in second:
            ob["subject_id"] = "U200"
        case[2].extend(second)
        result = report(case)
        self.assertEqual(result["summary"]["logged_requests"], 1)
        self.assertEqual(result["summary"]["returned_subjects"], 2)

    def test_denial_error_and_success_are_separate_request_counts(self):
        result = report(fixture(1), fixture(2, status=403, body={"detail": "denied"}, verdict="blocked"),
                        fixture(3, status=404, body={"detail": "not found"}, verdict="needs_review"),
                        fixture(4, status=500, body={"detail": "service error"}, verdict="needs_review"),
                        fixture(5, status=401, body={}, verdict="blocked"))
        summary = result["summary"]
        self.assertEqual((summary["http_success"], summary["denied"], summary["other"]), (1, 2, 2))
        self.assertEqual(summary["confirmed_policy_requests"], 1)
        self.assertEqual(summary["returned_subjects"], 1)

    def test_empty_200_does_not_prove_a_person_was_returned(self):
        for empty in ({}, [], {"records": []}, {"error": "not available"}):
            with self.subTest(body=empty):
                result = report(fixture(body=empty))
                self.assertEqual(result["summary"]["http_success"], 1)
                self.assertEqual(result["summary"]["returned_subjects"], 0)
                self.assertEqual(result["summary"]["confirmed_policy_requests"], 0)

    def test_absent_response_cannot_use_subject_hints_as_body_evidence(self):
        case = fixture()
        case[0]["payload"].pop("response_redacted")
        case[0]["sha256"] = digest(case[0]["payload"])
        result = report(case)
        self.assertEqual(result["summary"]["returned_subjects"], 0)
        self.assertEqual(result["summary"]["confirmed_policy_requests"], 0)

    def test_forged_observation_subject_not_in_response_is_excluded(self):
        case = fixture()
        for ob in case[2]:
            ob["subject_id"] = "U999"
        result = report(case)
        # The actual masked body independently proves U100, even when the derived
        # observation rows claim a different person. Preserve that body evidence.
        self.assertEqual(result["summary"]["returned_subjects"], 1)
        self.assertIn("U100", json.dumps(result.get("subjects", [])))
        self.assertNotIn("U999", json.dumps(result.get("subjects", [])))
        self.assertFalse(result["api_calls"][0]["fields"])

    def test_observation_field_absent_from_body_is_not_reported_as_returned(self):
        case = fixture()
        case[2].append({**case[2][0], "canonical": "consultation.reason"})
        result = report(case)
        self.assertNotIn("consultation.reason", result["api_calls"][0]["fields"])

    def test_unknown_policy_cannot_confirm_despite_finding_claim(self):
        result = report(fixture(policy_state="unknown", expected="review", verdict="confirmed"))
        self.assertEqual(result["summary"]["confirmed_policy_requests"], 0)
        self.assertEqual(result["summary"]["confirmed_exposure_subjects"], 0)
        self.assertEqual(result["summary"]["returned_subjects"], 1)

    def test_no_matching_finding_is_not_a_confirmed_policy_violation(self):
        case = fixture()
        case[1]["payload"]["evidence_ids"] = [999]
        result = report(case)
        self.assertEqual(result["summary"]["returned_subjects"], 1)
        self.assertEqual(result["summary"]["confirmed_policy_requests"], 0)

    def test_review_finding_is_not_promoted_from_response_identity(self):
        result = report(fixture(verdict="needs_review"))
        self.assertEqual(result["summary"]["confirmed_policy_requests"], 0)
        self.assertEqual(result["summary"]["confirmed_exposure_subjects"], 0)

    def test_public_other_person_stays_allowed(self):
        case = fixture(path="profile/public/U100", expected="allow_fields", verdict="allowed")
        result = report(case)
        self.assertEqual(result["summary"]["returned_subjects"], 1)
        self.assertEqual(result["summary"]["confirmed_policy_requests"], 0)
        self.assertEqual(result["summary"]["confirmed_exposure_subjects"], 0)

    def test_payload_tamper_excludes_response_and_confirmation_facts(self):
        case = fixture()
        case[0]["payload"]["response_redacted"]["member_id"] = "U999"
        result = report(case)
        self.assertEqual(result["summary"]["logged_requests"], 1)
        self.assertEqual(result["summary"]["confirmed_policy_requests"], 0)
        self.assertEqual(result["summary"]["returned_subjects"], 0)
        self.assertEqual(result["summary"]["confirmed_exposure_subjects"], 0)
        self.assertEqual(result["api_calls"][0]["fields"], [])
        self.assertEqual(result["coverage"]["corrupt_event_ids"], [1])
        self.assertFalse(result["timeline"][0]["integrity_ok"])

    def test_duplicate_observations_do_not_inflate_people(self):
        case = fixture()
        case[2].extend(copy.deepcopy(case[2]) * 3)
        result = report(case)
        self.assertEqual(result["summary"]["returned_subjects"], 1)
        self.assertEqual(result["summary"]["confirmed_exposure_subjects"], 1)

    def test_legitimate_only_field_is_not_attributed_to_confirmed_exposure(self):
        exposed = fixture(1)
        allowed = fixture(2, verdict="allowed", expected="allow", body={
            "tenant_id": "alpha", "member_id": "U100", "phone": "[REDACTED:PHONE]"})
        allowed[2][1]["canonical"] = "person.phone"
        result = report(exposed, allowed)
        person = result["subjects"][0]
        self.assertIn("person.phone", person["fields"])
        self.assertNotIn("person.phone", person["confirmed_fields"])
        self.assertIn("person.name", person["confirmed_fields"])

    def test_models_cannot_change_authorization_or_confirmed_count(self):
        case = fixture(verdict="allowed", expected="allow")
        baseline = report(case)
        result = report(case, models=[{"id": 1, "event_id": 1, "payload": {
            "label": "HEALTH", "verdict": "confirmed", "approved": True,
            "reason": "Untrusted synthetic AI claim"}}])
        self.assertEqual(baseline["summary"]["confirmed_policy_requests"], result["summary"]["confirmed_policy_requests"])
        self.assertEqual(result["summary"]["confirmed_policy_requests"], 0)

    def test_metadata_only_does_not_claim_zero_while_response_is_unavailable(self):
        result = report(fixture(), models=[{"id": 1, "event_id": 1, "payload": {"label": "HEALTH"}}], capture="metadata_only")
        summary = result["summary"]
        self.assertEqual(summary["logged_requests"], 1)
        self.assertEqual(summary["http_success"], 1)
        self.assertIsNone(summary["returned_subjects"])
        self.assertIsNone(summary["confirmed_exposure_subjects"])
        self.assertIsNone(summary["confirmed_policy_requests"])
        for api in result["api_calls"]:
            self.assertFalse(api.get("returned_subject_keys"))
            self.assertFalse(api.get("fields"))
        self.assertFalse(result["subjects"])
        self.assertFalse(result["stored_model_candidates"])
        for event in result["timeline"]:
            self.assertIsNone(event["response_redacted"])
            self.assertIsNone(event["verdict"])

    def test_tampered_or_unselected_event_models_do_not_become_evidence(self):
        case = fixture()
        case[0]["sha256"] = "0" * 64
        models = [{"id": 1, "event_id": 1, "payload": {"label": "HEALTH"}},
                  {"id": 2, "event_id": 999, "payload": {"label": "HEALTH"}}]
        result = report(case, models=models)
        self.assertEqual(result["stored_model_candidates"], [])

    def test_analysis_does_not_mutate_input_records(self):
        case = fixture()
        original = copy.deepcopy(case)
        report(case)
        self.assertEqual(case, original)


class IncidentSelectionTests(unittest.TestCase):
    def test_actor_selection_excludes_other_callers(self):
        result = report(fixture(1), fixture(2, actor="admin", subject="U999"), actor="bob")
        self.assertEqual(result["summary"]["logged_requests"], 1)
        self.assertEqual(result["summary"]["returned_subjects"], 1)

    def test_all_actor_view_is_explicit_and_retains_both_callers(self):
        result = report(fixture(1), fixture(2, actor="admin", subject="U999"), actor="all")
        self.assertEqual(result["summary"]["logged_requests"], 2)
        self.assertEqual(result["summary"]["returned_subjects"], 2)
        self.assertEqual({row["actor"] for row in result["timeline"]}, {"bob", "admin"})

    def test_other_run_records_are_not_mixed_in(self):
        other = fixture(2, subject="U999")
        other[0]["run_id"] = "other-run"
        result = report(fixture(1), other)
        self.assertEqual(result["summary"]["logged_requests"], 1)
        self.assertEqual(result["summary"]["returned_subjects"], 1)

    def test_no_matching_actor_is_zero_logs_with_no_invented_person(self):
        result = report(fixture(), actor="not-in-this-run")
        self.assertEqual(result["summary"]["logged_requests"], 0)
        self.assertEqual(result["summary"]["returned_subjects"], 0)

    def test_time_range_includes_both_endpoints_and_excludes_outside(self):
        result = report(fixture(1), fixture(2), fixture(3), fixture(4),
                        start="2026-09-22T00:02:00+00:00", end="2026-09-22T00:03:00+00:00")
        self.assertEqual(result["summary"]["logged_requests"], 2)

    def test_equivalent_non_utc_timezone_filters_match(self):
        utc = report(fixture(1), fixture(2), start="2026-09-22T00:02:00Z")
        kst = report(fixture(1), fixture(2), start="2026-09-22T09:02:00+09:00")
        self.assertEqual(utc["summary"]["logged_requests"], 1)
        self.assertEqual(utc["summary"], kst["summary"])

    def test_invalid_time_and_capture_filters_are_rejected(self):
        for filters in ({"start": "2026-09-22T00:01:00"}, {"end": "not-a-date"},
                        {"start": "2026-09-22T00:03:00Z", "end": "2026-09-22T00:01:00Z"},
                        {"capture": "invented-full-capture"}, {"actor": ""}, {"actor": None}, {"actor": "x" * 101}):
            with self.subTest(filters=filters), self.assertRaises(ValueError):
                report(fixture(), **filters)

    def test_only_registered_dynamic_paths_share_an_endpoint(self):
        self.assertEqual(endpoint_key("profile/private/U100"), endpoint_key("profile/private/U999"))
        self.assertNotEqual(endpoint_key("unknown/2025"), endpoint_key("unknown/2026"))
        self.assertNotEqual(endpoint_key("api/v1"), endpoint_key("api/v2"))

    def test_requested_nonexistent_id_does_not_inflate_returned_people(self):
        result = report(fixture(1), fixture(2, subject="U999", path="profile/private/U999",
                                             status=404, body={"detail": "not found"}, verdict="needs_review"))
        self.assertEqual(result["summary"]["logged_requests"], 2)
        self.assertEqual(result["summary"]["returned_subjects"], 1)
        self.assertEqual(result["summary"]["api_count"], 1)
        self.assertIn("U999", json.dumps(result["api_calls"][0]["requested_targets"]))
        self.assertNotIn("U999", json.dumps(result["api_calls"][0]["returned_subject_keys"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
