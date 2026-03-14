from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.ops.models import (
    Event,
    Family,
    MessageLog,
    MessageTemplate,
    Resource,
    ResourceAssignment,
    ResourceTemplate,
    Student,
)
from apps.tenancy.services import create_tenant_with_owner


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class WebStreamlinedWorkflowTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="owner@webux.test",
            email="owner@webux.test",
            password="testpass123",
        )
        self.tenant = create_tenant_with_owner(
            name="Web UX Studio",
            slug="web-ux",
            owner_user=self.owner,
        ).tenant
        self.family = Family.objects.create(
            tenant=self.tenant,
            name="Jones Family",
            email="family@test.com",
        )
        self.student = Student.objects.create(
            tenant=self.tenant,
            family=self.family,
            first_name="Ruby",
            last_name="Jones",
        )
        self.client.force_login(self.owner)

    def test_calendar_custom_event_uses_duration_when_end_missing(self):
        start_at = timezone.localtime(timezone.now() + timedelta(days=1)).replace(
            minute=0,
            second=0,
            microsecond=0,
        )
        response = self.client.post(
            "/app/calendar/",
            data={
                "action": "create_event",
                "title": "Parent Meeting",
                "event_type": Event.EventType.MEETING,
                "student_id": str(self.student.id),
                "start_at": start_at.strftime("%Y-%m-%dT%H:%M"),
                "end_at": "",
                "duration_minutes": "30",
                "recurrence_type": Event.RecurrenceType.NONE,
                "recurrence_interval": "1",
                "notes": "Discuss progress and goals",
            },
        )
        self.assertEqual(response.status_code, 302)

        event = Event.objects.get(tenant=self.tenant, title="Parent Meeting")
        self.assertEqual(event.event_type, Event.EventType.MEETING)
        self.assertEqual(event.notes, "Discuss progress and goals")
        self.assertEqual(int((event.end_at - event.start_at).total_seconds() // 60), 30)

    def test_message_template_can_be_saved_and_reused(self):
        save_response = self.client.post(
            "/app/messages/",
            data={
                "action": "save_template",
                "template_name": "Lesson Reminder",
                "template_channel": MessageLog.Channel.EMAIL,
                "template_subject": "Lesson tomorrow",
                "template_body": "Friendly reminder: lesson starts at 4pm.",
            },
        )
        self.assertEqual(save_response.status_code, 302)

        template = MessageTemplate.objects.get(tenant=self.tenant, name="Lesson Reminder")
        send_response = self.client.post(
            "/app/messages/",
            data={
                "action": "send_message",
                "template_id": str(template.id),
                "to_email": "family@test.com",
                "subject": "",
                "body": "",
            },
        )
        self.assertEqual(send_response.status_code, 302)

        message = MessageLog.objects.filter(tenant=self.tenant).latest("id")
        self.assertEqual(message.template_key, "Lesson Reminder")
        self.assertEqual(message.subject, "Lesson tomorrow")
        self.assertEqual(message.body, "Friendly reminder: lesson starts at 4pm.")
        self.assertEqual(message.status, MessageLog.Status.SENT)
        self.assertEqual(len(mail.outbox), 1)

    def test_resource_template_defaults_apply_to_create_and_assign(self):
        save_response = self.client.post(
            "/app/resources/",
            data={
                "action": "save_resource_template",
                "template_name": "Scale Sheet",
                "template_title": "C Major Scale",
                "template_description": "Two octaves hands together",
                "template_file_path": "resources/scales/c-major.pdf",
                "template_assignment_due_days": "5",
                "template_assignment_note": "Use metronome at 70 bpm.",
            },
        )
        self.assertEqual(save_response.status_code, 302)

        template = ResourceTemplate.objects.get(tenant=self.tenant, name="Scale Sheet")

        create_response = self.client.post(
            "/app/resources/",
            data={
                "action": "create_resource",
                "template_id": str(template.id),
                "title": "",
                "description": "",
                "file_path": "",
                "external_url": "",
            },
        )
        self.assertEqual(create_response.status_code, 302)

        resource = Resource.objects.get(tenant=self.tenant, title="C Major Scale")
        self.assertEqual(resource.file_path, "resources/scales/c-major.pdf")

        assign_response = self.client.post(
            "/app/resources/",
            data={
                "action": "assign_resource",
                "resource_id": str(resource.id),
                "resource_template_id": str(template.id),
                "student_id": str(self.student.id),
                "family_id": "",
                "due_date": "",
                "note": "",
            },
        )
        self.assertEqual(assign_response.status_code, 302)

        assignment = ResourceAssignment.objects.filter(tenant=self.tenant).latest("id")
        self.assertEqual(assignment.note, "Use metronome at 70 bpm.")
        self.assertEqual(
            assignment.due_date,
            timezone.localdate() + timedelta(days=5),
        )
