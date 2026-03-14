import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.ops.models import MessageLog
from apps.tenancy.models import Membership
from apps.tenancy.services import add_membership, create_tenant_with_owner


@override_settings(
    APP_PORTAL_BASE_DOMAIN="teach.test",
    ALLOWED_HOSTS=["*"],
    SMS_PROVIDER="console",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class Phase3GrowthTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="owner@growth.test",
            email="owner@growth.test",
            password="testpass123",
        )
        self.teacher = user_model.objects.create_user(
            username="teacher@growth.test",
            email="teacher@growth.test",
            password="testpass123",
        )
        self.tenant = create_tenant_with_owner(
            name="Growth Studio",
            slug="growth-studio",
            owner_user=self.owner,
        ).tenant
        add_membership(
            user=self.teacher,
            tenant=self.tenant,
            role=Membership.Role.TEACHER,
            status=Membership.Status.ACTIVE,
            is_default=True,
        )

        self.client.force_login(self.owner)

        family_resp = self.client.post(
            "/api/families/",
            data=json.dumps({"name": "Growth Family", "email": "family@growth.test"}),
            content_type="application/json",
            HTTP_HOST="growth-studio.teach.test",
        )
        self.family_id = family_resp.json()["id"]

        student_resp = self.client.post(
            "/api/students/",
            data=json.dumps(
                {
                    "family_id": self.family_id,
                    "first_name": "Lily",
                    "last_name": "Jones",
                    "instrument": "Piano",
                }
            ),
            content_type="application/json",
            HTTP_HOST="growth-studio.teach.test",
        )
        self.student_id = student_resp.json()["id"]

    def test_reporting_sms_payroll_and_site_builder(self):
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(minutes=45)

        event_resp = self.client.post(
            "/api/events/",
            data=json.dumps(
                {
                    "title": "Teacher Lesson",
                    "student_id": self.student_id,
                    "start_at": start.isoformat(),
                    "end_at": end.isoformat(),
                }
            ),
            content_type="application/json",
            HTTP_HOST="growth-studio.teach.test",
        )
        self.assertEqual(event_resp.status_code, 201)
        event_id = event_resp.json()["event"]["id"]

        self.client.patch(
            f"/api/events/{event_id}/",
            data=json.dumps({"status": "completed"}),
            content_type="application/json",
            HTTP_HOST="growth-studio.teach.test",
        )

        invoice_resp = self.client.post(
            "/api/invoices/",
            data=json.dumps(
                {
                    "family_id": self.family_id,
                    "due_date": (timezone.localdate() + timedelta(days=7)).isoformat(),
                    "items": [
                        {"description": "Monthly fee", "quantity": "1", "unit_price_cents": 10000}
                    ],
                }
            ),
            content_type="application/json",
            HTTP_HOST="growth-studio.teach.test",
        )
        invoice_id = invoice_resp.json()["id"]

        self.client.post(f"/api/invoices/{invoice_id}/send/", HTTP_HOST="growth-studio.teach.test")
        pay_link = self.client.post(
            f"/api/invoices/{invoice_id}/pay-link/",
            data=json.dumps({"provider": "stripe"}),
            content_type="application/json",
            HTTP_HOST="growth-studio.teach.test",
        ).json()
        self.client.post(
            f"/api/payments/{pay_link['id']}/confirm/",
            data=json.dumps({"status": "succeeded", "provider_reference": "pay_123"}),
            content_type="application/json",
            HTTP_HOST="growth-studio.teach.test",
        )

        report_resp = self.client.get(
            "/api/growth/reports/summary/", HTTP_HOST="growth-studio.teach.test"
        )
        self.assertEqual(report_resp.status_code, 200)
        self.assertIn("payments_succeeded_total_cents", report_resp.json())

        sms_resp = self.client.post(
            "/api/growth/messages/sms/send/",
            data=json.dumps({"to_phone": "+353870000000", "body": "Lesson reminder"}),
            content_type="application/json",
            HTTP_HOST="growth-studio.teach.test",
        )
        self.assertEqual(sms_resp.status_code, 201)
        self.assertEqual(sms_resp.json()["status"], "sent")
        self.assertEqual(sms_resp.json()["channel"], MessageLog.Channel.SMS)

        plan_resp = self.client.post(
            "/api/growth/payroll/plans/",
            data=json.dumps(
                {
                    "teacher_id": self.teacher.id,
                    "comp_type": "per_lesson",
                    "rate_cents": 2500,
                }
            ),
            content_type="application/json",
            HTTP_HOST="growth-studio.teach.test",
        )
        self.assertEqual(plan_resp.status_code, 201)

        period_resp = self.client.post(
            "/api/growth/payroll/periods/",
            data=json.dumps(
                {
                    "start_date": (timezone.localdate() - timedelta(days=7)).isoformat(),
                    "end_date": (timezone.localdate() + timedelta(days=7)).isoformat(),
                }
            ),
            content_type="application/json",
            HTTP_HOST="growth-studio.teach.test",
        )
        self.assertEqual(period_resp.status_code, 201)
        period_id = period_resp.json()["id"]

        finalize_resp = self.client.post(
            f"/api/growth/payroll/periods/{period_id}/finalize/",
            HTTP_HOST="growth-studio.teach.test",
        )
        self.assertEqual(finalize_resp.status_code, 200)

        period_detail = self.client.get(
            f"/api/growth/payroll/periods/{period_id}/",
            HTTP_HOST="growth-studio.teach.test",
        )
        self.assertEqual(period_detail.status_code, 200)
        lines = period_detail.json()["lines"]
        self.assertGreaterEqual(len(lines), 1)

        payout_resp = self.client.post(
            f"/api/growth/payroll/lines/{lines[0]['id']}/payout/",
            data=json.dumps({"reference": "bank_001"}),
            content_type="application/json",
            HTTP_HOST="growth-studio.teach.test",
        )
        self.assertEqual(payout_resp.status_code, 201)

        theme_patch = self.client.patch(
            "/api/growth/site/theme/",
            data=json.dumps(
                {
                    "brand_name": "Growth Studio",
                    "primary_color": "#111827",
                    "hero_title": "Music for Life",
                }
            ),
            content_type="application/json",
            HTTP_HOST="growth-studio.teach.test",
        )
        self.assertEqual(theme_patch.status_code, 200)

        page_resp = self.client.post(
            "/api/growth/site/pages/",
            data=json.dumps(
                {
                    "slug": "home",
                    "title": "Welcome",
                    "layout": "landing",
                    "is_homepage": True,
                    "is_published": True,
                    "content": {"sections": [{"type": "hero", "title": "Start Learning"}]},
                }
            ),
            content_type="application/json",
            HTTP_HOST="growth-studio.teach.test",
        )
        self.assertEqual(page_resp.status_code, 201)
        page_id = page_resp.json()["id"]

        menu_resp = self.client.post(
            "/api/growth/site/menu/",
            data=json.dumps({"label": "Home", "page_id": page_id, "order": 1}),
            content_type="application/json",
            HTTP_HOST="growth-studio.teach.test",
        )
        self.assertEqual(menu_resp.status_code, 201)

        public_page = self.client.get(
            "/api/growth/public/pages/home/", HTTP_HOST="growth-studio.teach.test"
        )
        self.assertEqual(public_page.status_code, 200)
        public_payload = public_page.json()
        self.assertEqual(public_payload["tenant"]["slug"], "growth-studio")
        self.assertEqual(public_payload["page"]["slug"], "home")
        self.assertEqual(public_payload["theme"]["brand_name"], "Growth Studio")
        self.assertGreaterEqual(len(public_payload["menu"]), 1)
