from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.tenancy.models import Domain, Membership, Tenant
from apps.tenancy.services import (
    LastOwnerError,
    create_tenant_with_owner,
    set_membership_status,
    set_primary_domain,
)


@override_settings(APP_PORTAL_BASE_DOMAIN="teach.test")
class TenancyServiceTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.owner = self.user_model.objects.create_user(
            username="owner@music.test",
            email="owner@music.test",
            password="testpass123",
        )

    def test_create_tenant_with_owner_creates_domain_and_membership(self):
        result = create_tenant_with_owner(
            name="Music School",
            slug="music-school",
            owner_user=self.owner,
        )

        self.assertIsInstance(result.tenant, Tenant)
        self.assertEqual(result.primary_domain.host, "music-school.teach.test")
        self.assertEqual(result.primary_domain.is_primary, True)
        self.assertEqual(result.owner_membership.role, Membership.Role.OWNER)
        self.assertEqual(result.owner_membership.status, Membership.Status.ACTIVE)
        self.assertEqual(result.tenant.locale, "en-us")
        self.assertEqual(result.tenant.currency, "USD")
        self.assertEqual(result.tenant.timezone, "UTC")

    def test_create_tenant_with_owner_honors_locale_currency_timezone_inputs(self):
        result = create_tenant_with_owner(
            name="International Studio",
            slug="international-studio",
            owner_user=self.owner,
            timezone_name="Europe/Dublin",
            locale_code="fr",
            currency_code="EUR",
        )
        self.assertEqual(result.tenant.timezone, "Europe/Dublin")
        self.assertEqual(result.tenant.locale, "fr")
        self.assertEqual(result.tenant.currency, "EUR")

    def test_set_primary_domain_reassigns_primary(self):
        result = create_tenant_with_owner(
            name="North Studio",
            slug="north-studio",
            owner_user=self.owner,
        )
        custom_domain = Domain.objects.create(
            tenant=result.tenant,
            host="app.northstudio.com",
            domain_type=Domain.DomainType.CUSTOM_DOMAIN,
        )

        set_primary_domain(tenant=result.tenant, domain=custom_domain)

        result.primary_domain.refresh_from_db()
        custom_domain.refresh_from_db()

        self.assertFalse(result.primary_domain.is_primary)
        self.assertTrue(custom_domain.is_primary)

    def test_block_removing_final_active_owner(self):
        result = create_tenant_with_owner(
            name="Solo Studio",
            slug="solo-studio",
            owner_user=self.owner,
        )

        with self.assertRaises(LastOwnerError):
            set_membership_status(
                membership=result.owner_membership,
                status=Membership.Status.REVOKED,
            )

        second_owner_user = self.user_model.objects.create_user(
            username="coowner@music.test",
            email="coowner@music.test",
            password="testpass123",
        )
        second_owner_membership = Membership.objects.create(
            user=second_owner_user,
            tenant=result.tenant,
            role=Membership.Role.OWNER,
            status=Membership.Status.ACTIVE,
        )

        updated = set_membership_status(
            membership=result.owner_membership,
            status=Membership.Status.SUSPENDED,
        )

        self.assertEqual(updated.status, Membership.Status.SUSPENDED)
        self.assertEqual(
            Membership.objects.filter(
                tenant=result.tenant,
                role=Membership.Role.OWNER,
                status=Membership.Status.ACTIVE,
            ).count(),
            1,
        )
        self.assertEqual(second_owner_membership.status, Membership.Status.ACTIVE)
