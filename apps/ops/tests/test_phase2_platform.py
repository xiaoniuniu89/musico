import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.ops.models import MessageLog
from apps.ops.services import queue_message
from apps.tenancy.models import Membership
from apps.tenancy.services import add_membership, create_tenant_with_owner


@override_settings(
    APP_PORTAL_BASE_DOMAIN="teach.test",
    DOMAIN_VERIFICATION_MODE="manual",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class Phase2PlatformTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="owner@phase2.test",
            email="owner@phase2.test",
            password="testpass123",
        )
        self.tenant = create_tenant_with_owner(
            name="Phase Two Studio",
            slug="phase-two",
            owner_user=self.owner,
        ).tenant
        self.client.force_login(self.owner)

    def test_domain_verification_and_ssl_activation(self):
        create_response = self.client.post(
            "/api/domains/",
            data=json.dumps({"host": "app.phase-two-school.com"}),
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 201)
        domain = create_response.json()
        self.assertEqual(domain["verification_status"], "pending")
        self.assertTrue(domain["txt_record_value"])

        bad_verify = self.client.post(
            f"/api/domains/{domain['id']}/verify/",
            data=json.dumps({"txt_records": ["musico-verify=wrong"]}),
            content_type="application/json",
        )
        self.assertEqual(bad_verify.status_code, 400)

        good_verify = self.client.post(
            f"/api/domains/{domain['id']}/verify/",
            data=json.dumps({"txt_records": [domain["txt_record_value"]]}),
            content_type="application/json",
        )
        self.assertEqual(good_verify.status_code, 200)
        verified = good_verify.json()
        self.assertEqual(verified["verification_status"], "verified")
        self.assertEqual(verified["ssl_status"], "active")

        set_primary = self.client.post(f"/api/domains/{domain['id']}/set-primary/")
        self.assertEqual(set_primary.status_code, 200)
        self.assertTrue(set_primary.json()["is_primary"])

    def test_audit_logs_capture_mutating_requests(self):
        create_family = self.client.post(
            "/api/families/",
            data=json.dumps({"name": "Audit Family", "email": "audit@test.com"}),
            content_type="application/json",
        )
        self.assertEqual(create_family.status_code, 201)

        logs_response = self.client.get("/api/audit-logs/")
        self.assertEqual(logs_response.status_code, 200)
        logs = logs_response.json()["results"]
        self.assertTrue(any(log["action"] == "http.post" for log in logs))
        self.assertTrue(any(log["path"] == "/api/families/" for log in logs))

    def test_scheduler_retry_and_monitoring(self):
        message = queue_message(
            tenant=self.tenant,
            to_email="retry@test.com",
            subject="Retry me",
            body="This should fail first",
            template_key="manual",
            metadata={"force_fail": True},
        )
        self.assertEqual(message.retry_count, 0)

        run_response = self.client.post(
            "/api/messages/reminders/run/",
            data=json.dumps({"hours_ahead": 2}),
            content_type="application/json",
        )
        self.assertEqual(run_response.status_code, 200)
        run_payload = run_response.json()
        self.assertIn(run_payload["status"], ["partial", "succeeded"])
        self.assertGreaterEqual(run_payload["retry_scheduled"], 1)

        message.refresh_from_db()
        self.assertEqual(message.status, MessageLog.Status.QUEUED)
        self.assertEqual(message.retry_count, 1)
        self.assertIsNotNone(message.next_retry_at)

        runs_response = self.client.get("/api/scheduler/runs/")
        self.assertEqual(runs_response.status_code, 200)
        run_ids = [item["id"] for item in runs_response.json()["results"]]
        self.assertIn(run_payload["run_id"], run_ids)

        run_detail = self.client.get(f"/api/scheduler/runs/{run_payload['run_id']}/")
        self.assertEqual(run_detail.status_code, 200)
        self.assertGreaterEqual(run_detail.json()["retry_scheduled_count"], 1)

    def test_dashboard_summary_role_based_by_viewport(self):
        owner_summary = self.client.get("/api/dashboard/summary/?viewport=desktop")
        self.assertEqual(owner_summary.status_code, 200)
        owner_payload = owner_summary.json()
        self.assertEqual(owner_payload["layout"]["navigation"], "side-nav")
        self.assertIn("manage_domains", owner_payload["quick_actions"])

        user_model = get_user_model()
        teacher = user_model.objects.create_user(
            username="teacher@phase2.test",
            email="teacher@phase2.test",
            password="testpass123",
        )
        add_membership(
            user=teacher,
            tenant=self.tenant,
            role=Membership.Role.TEACHER,
            status=Membership.Status.ACTIVE,
            is_default=True,
        )

        self.client.force_login(teacher)
        teacher_summary = self.client.get("/api/dashboard/summary/?viewport=mobile")
        self.assertEqual(teacher_summary.status_code, 200)
        teacher_payload = teacher_summary.json()
        self.assertEqual(teacher_payload["layout"]["navigation"], "bottom-tabs")
        self.assertIn("mark_attendance", teacher_payload["quick_actions"])
        self.assertNotIn("manage_domains", teacher_payload["quick_actions"])
