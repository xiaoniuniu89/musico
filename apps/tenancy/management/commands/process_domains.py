from django.core.management.base import BaseCommand

from apps.tenancy.models import Domain
from apps.tenancy.services import DomainVerificationError, verify_and_activate_domain


class Command(BaseCommand):
    help = "Process pending custom domains for verification + SSL activation"

    def handle(self, *args, **options):
        pending_domains = Domain.objects.filter(
            domain_type=Domain.DomainType.CUSTOM_DOMAIN,
            verification_status=Domain.VerificationStatus.PENDING,
        ).order_by("id")

        activated = 0
        failed = 0
        for domain in pending_domains:
            try:
                verify_and_activate_domain(domain=domain)
                activated += 1
            except DomainVerificationError:
                failed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"processed={pending_domains.count()} activated={activated} failed={failed}"
            )
        )
