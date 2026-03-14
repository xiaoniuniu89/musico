from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.tenancy.models import Domain, Membership, Tenant


@override_settings(
    APP_PORTAL_BASE_DOMAIN="teach.test",
    ALLOWED_HOSTS=["*"],
)
class TenantResolutionMiddlewareTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="member@demo.test",
            email="member@demo.test",
            password="testpass123",
        )
        self.school_a = Tenant.objects.create(name="School A", slug="school-a")
        self.school_b = Tenant.objects.create(name="School B", slug="school-b")

        Domain.objects.create(
            tenant=self.school_a,
            host="app.school-a.com",
            domain_type=Domain.DomainType.CUSTOM_DOMAIN,
            is_primary=True,
        )

        Membership.objects.create(
            user=self.user,
            tenant=self.school_a,
            role=Membership.Role.TEACHER,
            status=Membership.Status.ACTIVE,
            is_default=True,
        )

    def test_resolves_tenant_from_domain_table(self):
        response = self.client.get("/tenant-context/", HTTP_HOST="app.school-a.com")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["source"], "domain")
        self.assertEqual(body["tenant"]["slug"], "school-a")

    def test_resolves_tenant_from_subdomain_fallback(self):
        response = self.client.get("/tenant-context/", HTTP_HOST="school-b.teach.test")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["source"], "fallback_subdomain")
        self.assertEqual(body["tenant"]["slug"], "school-b")

    def test_unknown_subdomain_has_no_tenant(self):
        response = self.client.get("/tenant-context/", HTTP_HOST="unknown.teach.test")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["source"], "none")
        self.assertIsNone(body["tenant"])

    def test_member_guard_enforces_host_resolved_tenant_membership(self):
        # User belongs to school-a only; school-b host should reject /me/
        self.client.force_login(self.user)

        response = self.client.get("/me/", HTTP_HOST="school-b.teach.test")
        self.assertEqual(response.status_code, 403)

    def test_member_guard_uses_host_tenant_over_default_membership(self):
        Membership.objects.create(
            user=self.user,
            tenant=self.school_b,
            role=Membership.Role.ADMIN,
            status=Membership.Status.ACTIVE,
            is_default=False,
        )
        self.client.force_login(self.user)

        response = self.client.get("/me/", HTTP_HOST="school-b.teach.test")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["tenant"]["slug"], "school-b")
        self.assertEqual(body["role"], Membership.Role.ADMIN)
