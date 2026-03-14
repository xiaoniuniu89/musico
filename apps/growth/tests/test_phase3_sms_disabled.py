import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.tenancy.services import create_tenant_with_owner


@override_settings(
    APP_PORTAL_BASE_DOMAIN="teach.test", ALLOWED_HOSTS=["*"], SMS_PROVIDER="disabled"
)
class SmsDisabledBehaviorTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="owner@smsdisabled.test",
            email="owner@smsdisabled.test",
            password="testpass123",
        )
        self.tenant = create_tenant_with_owner(
            name="SMS Disabled Studio",
            slug="sms-disabled",
            owner_user=self.owner,
        ).tenant
        self.client.force_login(self.owner)

    def test_sms_send_returns_failed_status_when_provider_disabled(self):
        response = self.client.post(
            "/api/growth/messages/sms/send/",
            data=json.dumps({"to_phone": "+353870000000", "body": "Ping"}),
            content_type="application/json",
            HTTP_HOST="sms-disabled.teach.test",
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["status"], "queued")
        self.assertTrue(payload["error_message"])
