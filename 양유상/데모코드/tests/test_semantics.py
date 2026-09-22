"""Adversarial semantic checks, independent from fixture policy generation."""
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gateway.privacy import classify_field, decide, observations, redact


class PrivacySemanticsTests(unittest.TestCase):
    def test_service_uuid_is_not_statutory_unique_identifying_information(self):
        classification = classify_field("member_id", "2d556ae1-e756-4f4c-98a7-96f757b7e5c0")
        self.assertEqual(classification["label"], "SERVICE_ID")
        self.assertNotIn("제24조", classification["legal_category"])
        self.assertNotIn("고유식별정보", classification["legal_category"])

    def test_order_and_appointment_ids_are_not_person_identifiers(self):
        for key in ("order_id", "appointment_id"):
            with self.subTest(key=key):
                item = classify_field(key, "U100")
                self.assertNotEqual(item["label"], "SERVICE_ID")
                self.assertNotEqual(item.get("canonical"), "data_subject.id")

    def test_general_consultation_is_not_health_sensitive(self):
        item = classify_field("consult_reason", "주차장 운영 시간을 알고 싶습니다.")
        self.assertNotEqual(item["label"], "SENSITIVE_CANDIDATE")

    def test_personal_treatment_is_sensitive_candidate(self):
        item = classify_field("consult_reason", "우울증 진단을 받고 약을 복용 중입니다.")
        self.assertEqual(item["label"], "SENSITIVE_CANDIDATE")
        self.assertIn("후보", item["legal_category"])

    def test_nested_secrets_are_removed_case_insensitively(self):
        marker = "synthetic-do-not-retain-491"
        payload = {"record": [{"Authorization": marker, "password": marker, "access_token": marker}],
                   "Cookie": marker, "Set-Cookie": marker, "refresh_token": marker}
        self.assertNotIn(marker, json.dumps(redact(payload)))

    def test_tenant_is_preserved_for_same_subject_number(self):
        payload = {"records": [
            {"tenant_id": "alpha", "member_id": "U100", "phone": "010-0000-0101"},
            {"tenant_id": "beta", "member_id": "U100", "phone": "010-0000-0303"},
        ]}
        identities = {(x["tenant"], x["namespace"], x["subject_id"]) for x in observations(payload)}
        self.assertEqual(identities, {("alpha", "synthetic-member-v1", "U100"),
                                      ("beta", "synthetic-member-v1", "U100")})

    def test_ambiguous_id_without_subject_namespace_is_not_joined(self):
        self.assertEqual(observations({"tenant_id": "alpha", "order_id": "U100", "name": "동명이인"}), [])
        self.assertEqual(observations({"member_id": "U100", "name": "테넌트 미상"}), [])


class AuthorizationSemanticsTests(unittest.TestCase):
    @staticmethod
    def policy(expected="deny", state="approved"):
        return {"state": state, "expected": expected, "category": "BOLA", "reason": "Independent test policy",
                "public_fields": ["tenant_id", "member_id", "display_name", "bio"]}

    def test_unknown_policy_abstains(self):
        verdict, *_ = decide(self.policy(state="unknown"), 200, {"member_id": "U100"})
        self.assertEqual(verdict, "needs_review")

    def test_public_other_person_is_allowed(self):
        verdict, *_ = decide(self.policy(expected="allow_fields"), 200,
                             {"tenant_id": "alpha", "member_id": "U100", "display_name": "public"})
        self.assertEqual(verdict, "allowed")

    def test_private_field_in_public_response_is_confirmed(self):
        verdict, category, _, fields = decide(self.policy(expected="allow_fields"), 200,
                                               {"member_id": "U100", "phone": "010-0000-0101"})
        self.assertEqual((verdict, category), ("confirmed", "BOPLA"))
        self.assertIn("phone", fields)

    def test_deny_403_is_blocked(self):
        self.assertEqual(decide(self.policy(), 403, {"detail": "denied"})[0], "blocked")

    def test_server_failure_is_review_not_proof_of_secure_authorization(self):
        self.assertEqual(decide(self.policy(), 500, {"detail": "database offline"})[0], "needs_review")

    def test_empty_200_is_not_proof_of_target_exposure(self):
        for payload in ({}, [], {"error": "resource not available"}, {"success": False}):
            with self.subTest(payload=payload):
                self.assertEqual(decide(self.policy(), 200, payload)[0], "needs_review")


class ReturnedObjectTests(unittest.IsolatedAsyncioTestCase):
    async def test_own_data_returned_for_foreign_path_is_review_not_confirmed(self):
        from gateway import app as gateway_app

        payload = {"tenant_id": "alpha", "member_id": "U200", "name": "요청자 본인 데이터"}
        client = SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(status_code=200, json=lambda: payload)))
        with patch.object(gateway_app.app.state, "http", client, create=True), patch.object(gateway_app.store, "save", return_value=(1, 1)) as save:
            await gateway_app.forward("vulnerable", "profile/private/U100", "Bearer demo-bob", "unit-no-db")
            event, finding, _ = save.call_args.args
        self.assertEqual(finding["verdict"], "needs_review")
        self.assertEqual(event["subjects"], ["alpha:U200"])
        self.assertNotIn("alpha:U100", event["subjects"])

    async def test_same_id_wrong_tenant_is_review_not_requested_subject_exposure(self):
        from gateway import app as gateway_app

        payload = {"tenant_id": "beta", "member_id": "U100", "name": "다른 테넌트 데이터"}
        client = SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(status_code=200, json=lambda: payload)))
        with patch.object(gateway_app.app.state, "http", client, create=True), patch.object(gateway_app.store, "save", return_value=(1, 1)) as save:
            await gateway_app.forward("vulnerable", "profile/private/U100", "Bearer demo-bob", "unit-no-db")
            event, finding, _ = save.call_args.args
        self.assertEqual(finding["verdict"], "needs_review")
        self.assertEqual(event["subjects"], ["beta:U100"])


class DatabaseFailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_database_failure_returns_503_without_claiming_saved_evidence(self):
        import httpx
        import psycopg
        from psycopg_pool import PoolTimeout
        from gateway import app as gateway_app

        # Inject only in this in-process application; the running PostgreSQL is untouched.
        marker = "synthetic-database-error-detail-must-not-leak"
        for error in (psycopg.OperationalError(marker), PoolTimeout(marker)):
            with self.subTest(exception=type(error).__name__):
                with patch.object(gateway_app.store, "connect", side_effect=error):
                    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway_app.app), base_url="http://testserver") as client:
                        response = await client.get("/health")
                self.assertEqual(response.status_code, 503)
                self.assertIn("not confirmed saved", response.json()["detail"])
                self.assertNotIn(marker, response.text)
                self.assertNotIn("evidence_ids", response.json())
                self.assertNotEqual(response.json().get("status"), "ok")

    async def test_failed_evidence_write_does_not_return_successful_upstream_data(self):
        import httpx
        import psycopg
        from gateway import app as gateway_app

        payload = {"tenant_id": "alpha", "member_id": "U100", "name": "synthetic-upstream-data-must-not-be-success"}
        upstream = SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(status_code=200, json=lambda: payload)))
        with patch.object(gateway_app.app.state, "http", upstream, create=True), \
                patch.object(gateway_app.store, "new_run"), \
                patch.object(gateway_app.store, "finish_run"), \
                patch.object(gateway_app.store, "save", side_effect=psycopg.OperationalError("synthetic write failure")):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway_app.app), base_url="http://testserver") as client:
                response = await client.get("/proxy/vulnerable/profile/private/U100", headers={"Authorization": "Bearer demo-bob"})
        self.assertEqual(response.status_code, 503)
        self.assertIn("not confirmed saved", response.json()["detail"])
        self.assertNotIn(payload["name"], response.text)
        self.assertNotIn("X-Demo-Event-Id", response.headers)


if __name__ == "__main__":
    unittest.main(verbosity=2)
