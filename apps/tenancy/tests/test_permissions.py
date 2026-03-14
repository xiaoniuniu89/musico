from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.tenancy.models import Membership, Tenant


@override_settings(APP_PORTAL_BASE_DOMAIN="teach.test")
class PermissionGuardTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="teacher@demo.test",
            email="teacher@demo.test",
            password="testpass123",
        )
        self.tenant = Tenant.objects.create(name="Demo", slug="demo")

    def test_member_guard_rejects_anonymous(self):
        response = self.client.get("/me/")
        self.assertEqual(response.status_code, 401)

    def test_member_guard_rejects_user_without_membership(self):
        self.client.force_login(self.user)
        response = self.client.get("/me/")
        self.assertEqual(response.status_code, 403)

    def test_role_guard_rejects_insufficient_role(self):
        Membership.objects.create(
            user=self.user,
            tenant=self.tenant,
            role=Membership.Role.TEACHER,
            status=Membership.Status.ACTIVE,
            is_default=True,
        )
        self.client.force_login(self.user)

        response = self.client.get("/admin/ping/")
        self.assertEqual(response.status_code, 403)

    def test_role_guard_allows_owner(self):
        Membership.objects.create(
            user=self.user,
            tenant=self.tenant,
            role=Membership.Role.OWNER,
            status=Membership.Status.ACTIVE,
            is_default=True,
        )
        self.client.force_login(self.user)

        response = self.client.get("/admin/ping/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
