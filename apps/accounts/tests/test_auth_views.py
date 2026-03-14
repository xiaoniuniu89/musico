import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.tenancy.models import Membership
from apps.tenancy.services import create_tenant_with_owner


@override_settings(APP_PORTAL_BASE_DOMAIN="teach.test")
class AuthViewsTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.owner = self.user_model.objects.create_user(
            username="owner@demo.test",
            email="owner@demo.test",
            password="testpass123",
        )
        result = create_tenant_with_owner(
            name="Demo School",
            slug="demo-school",
            owner_user=self.owner,
        )
        self.tenant = result.tenant

    def test_login_sets_authenticated_session_and_active_tenant(self):
        response = self.client.post(
            "/auth/login/",
            data=json.dumps(
                {
                    "identifier": "owner@demo.test",
                    "password": "testpass123",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["authenticated"])
        self.assertEqual(body["active_tenant"]["slug"], "demo-school")

    def test_login_rejects_bad_credentials(self):
        response = self.client.post(
            "/auth/login/",
            data=json.dumps(
                {
                    "identifier": "owner@demo.test",
                    "password": "wrong",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)

    def test_session_view_works_for_anonymous(self):
        response = self.client.get("/auth/session/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["authenticated"])

    def test_switch_tenant_changes_active_tenant(self):
        second_tenant = create_tenant_with_owner(
            name="School Two",
            slug="school-two",
            owner_user=self.owner,
        ).tenant

        # ensure this membership is non-default so switch behavior is visible
        membership = Membership.objects.get(user=self.owner, tenant=second_tenant)
        membership.is_default = False
        membership.save(update_fields=["is_default", "updated_at"])

        self.client.post(
            "/auth/login/",
            data=json.dumps(
                {
                    "identifier": "owner@demo.test",
                    "password": "testpass123",
                }
            ),
            content_type="application/json",
        )

        response = self.client.post(
            "/auth/switch-tenant/",
            data=json.dumps({"tenant_slug": "school-two"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["active_tenant"]["slug"], "school-two")
