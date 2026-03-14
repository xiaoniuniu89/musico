from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.tenancy.services import TenancyError, create_tenant_with_owner


class Command(BaseCommand):
    help = "Create a tenant with its default platform domain and owner membership."

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True, help="Tenant display name")
        parser.add_argument("--slug", required=True, help="Tenant slug")
        parser.add_argument("--owner-email", required=True, help="Owner email")
        parser.add_argument(
            "--owner-password",
            default="changeme123",
            help="Owner password if user must be created",
        )
        parser.add_argument("--timezone", default=None, help="Tenant timezone")
        parser.add_argument("--locale", default=None, help="Tenant locale (e.g. en-us, fr, de)")
        parser.add_argument("--currency", default=None, help="Tenant currency (ISO code)")

    def handle(self, *args, **options):
        user_model = get_user_model()
        owner_email = options["owner_email"].strip().lower()

        owner = user_model.objects.filter(email=owner_email).first()
        if owner is None:
            username = getattr(user_model, "USERNAME_FIELD", "username")
            create_kwargs = {
                "email": owner_email,
                "password": options["owner_password"],
            }
            if username == "email":
                create_kwargs["email"] = owner_email
            else:
                create_kwargs[username] = owner_email
            owner = user_model.objects.create_user(**create_kwargs)

        try:
            result = create_tenant_with_owner(
                name=options["name"],
                slug=options["slug"],
                owner_user=owner,
                timezone_name=options["timezone"],
                locale_code=options["locale"],
                currency_code=options["currency"],
            )
        except TenancyError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                "Created tenant "
                f"id={result.tenant.id} "
                f"slug={result.tenant.slug} "
                f"locale={result.tenant.locale} "
                f"currency={result.tenant.currency} "
                f"timezone={result.tenant.timezone} "
                f"primary_domain={result.primary_domain.host} "
                f"owner_user_id={owner.id}"
            )
        )
