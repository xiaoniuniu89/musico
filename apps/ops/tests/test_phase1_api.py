import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.tenancy.services import create_tenant_with_owner


@override_settings(
    APP_PORTAL_BASE_DOMAIN="teach.test",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class Phase1ApiTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="owner@phase1.test",
            email="owner@phase1.test",
            password="testpass123",
        )
        self.tenant = create_tenant_with_owner(
            name="Phase One Studio",
            slug="phase-one",
            owner_user=self.owner,
        ).tenant
        self.client.force_login(self.owner)

    def _create_family(self):
        response = self.client.post(
            "/api/families/",
            data=json.dumps(
                {
                    "name": "Callaghan Family",
                    "email": "family@test.com",
                    "phone": "123456",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def _create_student(self, family_id: int):
        response = self.client.post(
            "/api/students/",
            data=json.dumps(
                {
                    "family_id": family_id,
                    "first_name": "Amy",
                    "last_name": "Callaghan",
                    "instrument": "Piano",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def test_students_and_families_crud(self):
        family = self._create_family()

        contact_response = self.client.post(
            f"/api/families/{family['id']}/contacts/",
            data=json.dumps(
                {
                    "full_name": "Daniel Callaghan",
                    "relationship": "parent",
                    "email": "dan@test.com",
                    "is_primary": True,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(contact_response.status_code, 201)

        student = self._create_student(family["id"])

        patch_response = self.client.patch(
            f"/api/students/{student['id']}/",
            data=json.dumps({"level": "Grade 3", "instrument": "Violin"}),
            content_type="application/json",
        )
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(patch_response.json()["instrument"], "Violin")

        delete_response = self.client.delete(f"/api/students/{student['id']}/")
        self.assertEqual(delete_response.status_code, 200)

    def test_calendar_recurrence_and_attendance(self):
        family = self._create_family()
        student = self._create_student(family["id"])

        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(minutes=30)

        create_response = self.client.post(
            "/api/events/",
            data=json.dumps(
                {
                    "title": "Weekly Lesson",
                    "student_id": student["id"],
                    "start_at": start.isoformat(),
                    "end_at": end.isoformat(),
                    "recurrence_type": "weekly",
                    "recurrence_interval": 1,
                    "recurrence_until": (start.date() + timedelta(days=14)).isoformat(),
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.json()["occurrences_created"], 2)

        event_id = create_response.json()["event"]["id"]
        attendance_response = self.client.post(
            f"/api/events/{event_id}/attendance/",
            data=json.dumps({"status": "present", "note": "Great focus"}),
            content_type="application/json",
        )
        self.assertEqual(attendance_response.status_code, 201)
        self.assertEqual(attendance_response.json()["status"], "present")

    def test_invoice_creation_send_and_payment(self):
        family = self._create_family()

        create_response = self.client.post(
            "/api/invoices/",
            data=json.dumps(
                {
                    "family_id": family["id"],
                    "due_date": (timezone.localdate() + timedelta(days=7)).isoformat(),
                    "items": [
                        {"description": "Lesson Block", "quantity": "4", "unit_price_cents": 3000}
                    ],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 201)
        invoice = create_response.json()
        self.assertEqual(invoice["total_cents"], 12000)
        self.assertEqual(invoice["currency"], "USD")

        send_response = self.client.post(f"/api/invoices/{invoice['id']}/send/")
        self.assertEqual(send_response.status_code, 200)
        self.assertEqual(send_response.json()["status"], "sent")

        pay_link_response = self.client.post(
            f"/api/invoices/{invoice['id']}/pay-link/",
            data=json.dumps({"provider": "stripe"}),
            content_type="application/json",
        )
        self.assertEqual(pay_link_response.status_code, 201)
        payment = pay_link_response.json()
        self.assertIn("checkout.stripe.com", payment["checkout_url"])

        confirm_response = self.client.post(
            f"/api/payments/{payment['id']}/confirm/",
            data=json.dumps({"status": "succeeded", "provider_reference": "ch_test_123"}),
            content_type="application/json",
        )
        self.assertEqual(confirm_response.status_code, 200)

        invoice_detail = self.client.get(f"/api/invoices/{invoice['id']}/")
        self.assertEqual(invoice_detail.status_code, 200)
        self.assertEqual(invoice_detail.json()["status"], "paid")

        eur_invoice_response = self.client.post(
            "/api/invoices/",
            data=json.dumps(
                {
                    "family_id": family["id"],
                    "currency": "EUR",
                    "due_date": (timezone.localdate() + timedelta(days=10)).isoformat(),
                    "items": [
                        {"description": "One-off", "quantity": "1", "unit_price_cents": 5000}
                    ],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(eur_invoice_response.status_code, 201)
        self.assertEqual(eur_invoice_response.json()["currency"], "EUR")

    def test_message_send_and_reminder_run(self):
        family = self._create_family()
        student = self._create_student(family["id"])

        send_response = self.client.post(
            "/api/messages/send/",
            data=json.dumps(
                {
                    "to_email": "family@test.com",
                    "subject": "Manual Message",
                    "body": "Hello from Musico",
                    "family_id": family["id"],
                    "student_id": student["id"],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(send_response.status_code, 201)
        self.assertEqual(send_response.json()["status"], "sent")

        event_start = timezone.now() + timedelta(hours=12)
        event_end = event_start + timedelta(minutes=45)
        self.client.post(
            "/api/events/",
            data=json.dumps(
                {
                    "title": "Reminder Lesson",
                    "student_id": student["id"],
                    "start_at": event_start.isoformat(),
                    "end_at": event_end.isoformat(),
                }
            ),
            content_type="application/json",
        )

        reminder_response = self.client.post(
            "/api/messages/reminders/run/",
            data=json.dumps({"hours_ahead": 24}),
            content_type="application/json",
        )
        self.assertEqual(reminder_response.status_code, 200)
        self.assertGreaterEqual(reminder_response.json()["queued"], 1)
        self.assertGreaterEqual(reminder_response.json()["sent"], 1)
        self.assertGreaterEqual(len(mail.outbox), 2)

    def test_resource_upload_and_assignment(self):
        family = self._create_family()
        student = self._create_student(family["id"])

        resource_response = self.client.post(
            "/api/resources/",
            data=json.dumps(
                {
                    "title": "Scale Sheet",
                    "description": "C major scales",
                    "file_path": "resources/c-major-scale.pdf",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(resource_response.status_code, 201)
        resource = resource_response.json()

        assignment_response = self.client.post(
            f"/api/resources/{resource['id']}/assign/",
            data=json.dumps(
                {
                    "student_id": student["id"],
                    "note": "Practice daily",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(assignment_response.status_code, 201)

        list_response = self.client.get("/api/resource-assignments/")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()["results"]), 1)
