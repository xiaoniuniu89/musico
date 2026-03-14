from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from apps.tenancy.models import Domain, Membership, Tenant


class TenancyModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="owner@example.com",
            email="owner@example.com",
            password="testpass123",
        )

    def test_tenant_slug_saved_lowercase(self):
        tenant = Tenant.objects.create(name="Fake School", slug="Fake-School")
        self.assertEqual(tenant.slug, "fake-school")

    def test_domain_host_normalizes_and_is_unique(self):
        tenant = Tenant.objects.create(name="School A", slug="school-a")
        domain = Domain.objects.create(
            tenant=tenant,
            host="App.School-A.Example.Com",
            domain_type=Domain.DomainType.CUSTOM_DOMAIN,
        )
        self.assertEqual(domain.host, "app.school-a.example.com")

        with self.assertRaises(IntegrityError):
            Domain.objects.create(
                tenant=tenant,
                host="app.school-a.example.com",
                domain_type=Domain.DomainType.CUSTOM_DOMAIN,
            )

    def test_single_primary_domain_constraint(self):
        tenant = Tenant.objects.create(name="School B", slug="school-b")
        Domain.objects.create(
            tenant=tenant,
            host="school-b.teach.example.com",
            domain_type=Domain.DomainType.PLATFORM_SUBDOMAIN,
            is_primary=True,
        )

        with self.assertRaises(IntegrityError):
            Domain.objects.create(
                tenant=tenant,
                host="app.school-b.com",
                domain_type=Domain.DomainType.CUSTOM_DOMAIN,
                is_primary=True,
            )

    def test_membership_uniques(self):
        tenant1 = Tenant.objects.create(name="School C", slug="school-c")
        tenant2 = Tenant.objects.create(name="School D", slug="school-d")

        Membership.objects.create(
            user=self.user,
            tenant=tenant1,
            role=Membership.Role.OWNER,
            is_default=True,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Membership.objects.create(
                    user=self.user,
                    tenant=tenant1,
                    role=Membership.Role.ADMIN,
                )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Membership.objects.create(
                    user=self.user,
                    tenant=tenant2,
                    role=Membership.Role.TEACHER,
                    is_default=True,
                )

    @override_settings(
        LANGUAGES=[("en-us", "English (US)"), ("en-gb", "English (UK)"), ("fr", "French")],
        APP_DEFAULT_LOCALE="en-us",
        APP_DEFAULT_CURRENCY="USD",
        APP_DEFAULT_TIMEZONE="UTC",
    )
    def test_tenant_normalizes_locale_currency_and_timezone(self):
        tenant = Tenant.objects.create(
            name="School E",
            slug="school-e",
            locale="EN_GB",
            currency="eur",
            timezone="Europe/London",
        )
        self.assertEqual(tenant.locale, "en-gb")
        self.assertEqual(tenant.currency, "EUR")
        self.assertEqual(tenant.timezone, "Europe/London")

        tenant.locale = "unsupported-locale"
        tenant.currency = "x"
        tenant.timezone = "Invalid/Timezone"
        tenant.save()

        self.assertEqual(tenant.locale, "en-us")
        self.assertEqual(tenant.currency, "USD")
        self.assertEqual(tenant.timezone, "UTC")
