import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.tenancy.models import Membership
from apps.tenancy.services import add_membership, create_tenant_with_owner


@override_settings(APP_PORTAL_BASE_DOMAIN="teach.test", ALLOWED_HOSTS=["*"])
class Phase4PortalTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="owner@portal.test",
            email="owner@portal.test",
            password="testpass123",
        )
        self.parent = user_model.objects.create_user(
            username="parent@portal.test",
            email="parent@portal.test",
            password="testpass123",
        )
        self.tenant = create_tenant_with_owner(
            name="Portal Studio",
            slug="portal-studio",
            owner_user=self.owner,
        ).tenant
        add_membership(
            user=self.parent,
            tenant=self.tenant,
            role=Membership.Role.PARENT,
            status=Membership.Status.ACTIVE,
            is_default=True,
        )

        self.client.force_login(self.owner)

        family_resp = self.client.post(
            "/api/families/",
            data=json.dumps({"name": "Portal Family", "email": self.parent.email}),
            content_type="application/json",
            HTTP_HOST="portal-studio.teach.test",
        )
        self.family_id = family_resp.json()["id"]

        student_resp = self.client.post(
            "/api/students/",
            data=json.dumps(
                {
                    "family_id": self.family_id,
                    "first_name": "Ruby",
                    "last_name": "Stone",
                    "instrument": "Piano",
                }
            ),
            content_type="application/json",
            HTTP_HOST="portal-studio.teach.test",
        )
        self.student_id = student_resp.json()["id"]

        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(minutes=30)
        self.client.post(
            "/api/events/",
            data=json.dumps(
                {
                    "title": "Portal Lesson",
                    "student_id": self.student_id,
                    "start_at": start.isoformat(),
                    "end_at": end.isoformat(),
                }
            ),
            content_type="application/json",
            HTTP_HOST="portal-studio.teach.test",
        )

        invoice_resp = self.client.post(
            "/api/invoices/",
            data=json.dumps(
                {
                    "family_id": self.family_id,
                    "due_date": (timezone.localdate() + timedelta(days=5)).isoformat(),
                    "items": [{"description": "Lesson", "quantity": "1", "unit_price_cents": 7500}],
                }
            ),
            content_type="application/json",
            HTTP_HOST="portal-studio.teach.test",
        )
        self.invoice_id = invoice_resp.json()["id"]
        self.client.post(
            f"/api/invoices/{self.invoice_id}/send/", HTTP_HOST="portal-studio.teach.test"
        )

        resource_resp = self.client.post(
            "/api/resources/",
            data=json.dumps(
                {
                    "title": "Warmups",
                    "file_path": "resources/warmups.pdf",
                }
            ),
            content_type="application/json",
            HTTP_HOST="portal-studio.teach.test",
        )
        self.resource_id = resource_resp.json()["id"]
        self.client.post(
            f"/api/resources/{self.resource_id}/assign/",
            data=json.dumps({"family_id": self.family_id}),
            content_type="application/json",
            HTTP_HOST="portal-studio.teach.test",
        )

        self.client.post(
            "/api/messages/send/",
            data=json.dumps(
                {
                    "to_email": self.parent.email,
                    "subject": "Welcome",
                    "body": "Welcome to portal",
                    "family_id": self.family_id,
                    "student_id": self.student_id,
                }
            ),
            content_type="application/json",
            HTTP_HOST="portal-studio.teach.test",
        )

    def test_parent_without_link_is_forbidden(self):
        self.client.force_login(self.parent)
        response = self.client.get("/api/portal/me/overview/", HTTP_HOST="portal-studio.teach.test")
        self.assertEqual(response.status_code, 403)

    def test_parent_portal_with_link_sees_expected_data(self):
        self.client.force_login(self.owner)
        link_resp = self.client.post(
            "/api/portal/access-links/",
            data=json.dumps(
                {
                    "user_id": self.parent.id,
                    "family_id": self.family_id,
                    "can_view_billing": True,
                    "can_view_resources": True,
                }
            ),
            content_type="application/json",
            HTTP_HOST="portal-studio.teach.test",
        )
        self.assertEqual(link_resp.status_code, 201)

        self.client.force_login(self.parent)

        overview = self.client.get("/api/portal/me/overview/", HTTP_HOST="portal-studio.teach.test")
        self.assertEqual(overview.status_code, 200)
        payload = overview.json()
        self.assertEqual(payload["families_count"], 1)
        self.assertEqual(payload["students_count"], 1)
        self.assertGreaterEqual(payload["billing"]["outstanding_count"], 1)
        self.assertGreaterEqual(payload["resources"]["assigned_count"], 1)
        self.assertGreaterEqual(len(payload["upcoming_events"]), 1)

        invoices = self.client.get("/api/portal/me/invoices/", HTTP_HOST="portal-studio.teach.test")
        self.assertEqual(invoices.status_code, 200)
        self.assertGreaterEqual(len(invoices.json()["results"]), 1)

        resources = self.client.get(
            "/api/portal/me/resources/", HTTP_HOST="portal-studio.teach.test"
        )
        self.assertEqual(resources.status_code, 200)
        self.assertGreaterEqual(len(resources.json()["results"]), 1)

        calendar = self.client.get("/api/portal/me/calendar/", HTTP_HOST="portal-studio.teach.test")
        self.assertEqual(calendar.status_code, 200)
        self.assertGreaterEqual(len(calendar.json()["results"]), 1)
