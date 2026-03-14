import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.tenancy.models import AuditLog, Membership
from apps.tenancy.services import create_tenant_with_owner
from apps.ops.models import Event

@override_settings(
    APP_PORTAL_BASE_DOMAIN="teach.test",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class PolishTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="owner@polish.test",
            email="owner@polish.test",
            password="testpass123",
        )
        self.tenant = create_tenant_with_owner(
            name="Polish Studio",
            slug="polish-one",
            owner_user=self.owner,
        ).tenant
        self.client.force_login(self.owner)

    def test_event_soft_deletion_and_filtering(self):
        # 1. Create an event
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(minutes=30)
        
        create_response = self.client.post(
            "/api/events/",
            data=json.dumps({
                "title": "To be archived",
                "start_at": start.isoformat(),
                "end_at": end.isoformat(),
            }),
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 201)
        event_id = create_response.json()["event"]["id"]

        # 2. Verify it shows up in list
        list_response = self.client.get("/api/events/")
        self.assertEqual(len(list_response.json()["results"]), 1)

        # 3. Soft-delete (archive) it
        delete_response = self.client.delete(f"/api/events/{event_id}/")
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.json()["status"], "archived")

        # 4. Verify it no longer shows up in list
        list_response_v2 = self.client.get("/api/events/")
        self.assertEqual(len(list_response_v2.json()["results"]), 0)

        # 5. Check model field directly
        event = Event.objects.get(id=event_id)
        self.assertTrue(event.is_archived)

    def test_audit_log_metadata_and_id_extraction(self):
        # Create a family to have a detail endpoint to hit
        create_response = self.client.post(
            "/api/families/",
            data=json.dumps({
                "name": "Audit Test Family",
                "email": "audit@test.com",
            }),
            content_type="application/json",
        )
        family_id = create_response.json()["id"]

        # Clear logs from setup/creation to focus on the next call
        AuditLog.objects.all().delete()

        # Perform a PATCH which triggers the middleware logic for object_id extraction
        self.client.patch(
            f"/api/families/{family_id}/",
            data=json.dumps({"notes": "Updated for audit test"}),
            content_type="application/json",
        )

        # Verify the AuditLog entry
        log = AuditLog.objects.filter(action="http.patch").latest("id")
        self.assertEqual(log.object_id, str(family_id))
        self.assertEqual(log.object_type, "families")
        self.assertEqual(log.metadata["path"], f"/api/families/{family_id}/")
        self.assertEqual(log.metadata["status_code"], 200)

    def test_dashboard_summary_excludes_archived(self):
        # Create one active and one archived event
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(minutes=30)
        
        # Active
        self.client.post(
            "/api/events/",
            data=json.dumps({
                "title": "Active Event",
                "start_at": start.isoformat(),
                "end_at": end.isoformat(),
            }),
            content_type="application/json",
        )
        # Archived
        archived_event = Event.objects.create(
            tenant=self.tenant,
            title="Archived Event",
            start_at=start + timedelta(hours=1),
            end_at=end + timedelta(hours=1),
            is_archived=True
        )

        response = self.client.get("/api/dashboard/summary/")
        self.assertEqual(response.status_code, 200)
        kpis = response.json()["kpis"]
        # Should only count the 1 active event
        self.assertEqual(kpis["upcoming_events_count"], 1)
