import secrets
from dataclasses import dataclass

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .audit import log_audit_event
from .localization import default_currency, default_locale
from .models import Domain, Membership, Tenant
from .validators import normalize_host


class TenancyError(Exception):
    """Base tenancy exception."""


class DomainOwnershipError(TenancyError):
    """Raised when a domain does not belong to the specified tenant."""


class LastOwnerError(TenancyError):
    """Raised when a mutation would remove the last active owner from a tenant."""


class DomainVerificationError(TenancyError):
    """Raised when domain verification fails."""


@dataclass
class TenantBootstrapResult:
    tenant: Tenant
    primary_domain: Domain
    owner_membership: Membership


def _portal_base_domain() -> str:
    return settings.APP_PORTAL_BASE_DOMAIN.strip().lower()


def _default_timezone() -> str:
    return settings.APP_DEFAULT_TIMEZONE


def _default_locale() -> str:
    return default_locale()


def _default_currency() -> str:
    return default_currency()


def create_tenant_with_owner(
    *,
    name: str,
    slug: str,
    owner_user,
    timezone_name: str | None = None,
    locale_code: str | None = None,
    currency_code: str | None = None,
) -> TenantBootstrapResult:
    if owner_user.pk is None:
        raise TenancyError("Owner user must be persisted before tenant creation.")

    effective_timezone = timezone_name or _default_timezone()
    effective_locale = locale_code or _default_locale()
    effective_currency = currency_code or _default_currency()

    with transaction.atomic():
        tenant = Tenant.objects.create(
            name=name,
            slug=slug,
            timezone=effective_timezone,
            locale=effective_locale,
            currency=effective_currency,
        )
        primary_domain = Domain.objects.create(
            tenant=tenant,
            host=f"{tenant.slug}.{_portal_base_domain()}",
            domain_type=Domain.DomainType.PLATFORM_SUBDOMAIN,
            is_primary=True,
            verification_status=Domain.VerificationStatus.NOT_REQUIRED,
            ssl_status=Domain.SSLStatus.UNMANAGED,
        )

        has_default_membership = Membership.objects.filter(
            user=owner_user,
            is_default=True,
        ).exists()

        owner_membership = Membership.objects.create(
            user=owner_user,
            tenant=tenant,
            role=Membership.Role.OWNER,
            status=Membership.Status.ACTIVE,
            is_default=not has_default_membership,
            joined_at=timezone.now(),
        )

    return TenantBootstrapResult(
        tenant=tenant,
        primary_domain=primary_domain,
        owner_membership=owner_membership,
    )


def add_domain(*, tenant: Tenant, host: str, domain_type: str, is_primary: bool = False) -> Domain:
    normalized_host = normalize_host(host)
    verification_status = (
        Domain.VerificationStatus.NOT_REQUIRED
        if domain_type == Domain.DomainType.PLATFORM_SUBDOMAIN
        else Domain.VerificationStatus.PENDING
    )

    with transaction.atomic():
        domain = Domain.objects.create(
            tenant=tenant,
            host=normalized_host,
            domain_type=domain_type,
            is_primary=False,
            verification_status=verification_status,
            ssl_status=Domain.SSLStatus.UNMANAGED,
        )
        if is_primary:
            set_primary_domain(tenant=tenant, domain=domain)
            domain.refresh_from_db()

    return domain


def set_primary_domain(*, tenant: Tenant, domain: Domain) -> None:
    if domain.tenant_id != tenant.id:
        raise DomainOwnershipError("Cannot assign a domain as primary for a different tenant.")

    with transaction.atomic():
        Domain.objects.select_for_update().filter(
            tenant=tenant,
            is_primary=True,
        ).update(is_primary=False)
        Domain.objects.select_for_update().filter(id=domain.id).update(is_primary=True)


def add_membership(
    *,
    user,
    tenant: Tenant,
    role: str,
    status: str = Membership.Status.ACTIVE,
    is_default: bool = False,
    invited_by=None,
) -> Membership:
    joined_at = timezone.now() if status == Membership.Status.ACTIVE else None

    try:
        with transaction.atomic():
            if is_default:
                Membership.objects.select_for_update().filter(user=user, is_default=True).update(
                    is_default=False
                )

            membership = Membership.objects.create(
                user=user,
                tenant=tenant,
                role=role,
                status=status,
                is_default=is_default,
                invited_by=invited_by,
                joined_at=joined_at,
            )
    except IntegrityError as exc:
        raise TenancyError(
            "Membership could not be created because it violates a uniqueness rule."
        ) from exc

    return membership


def assert_tenant_has_owner(*, tenant: Tenant) -> None:
    has_active_owner = Membership.objects.filter(
        tenant=tenant,
        role=Membership.Role.OWNER,
        status=Membership.Status.ACTIVE,
    ).exists()
    if not has_active_owner:
        raise LastOwnerError("Tenant must always have at least one active owner.")


def set_membership_status(*, membership: Membership, status: str) -> Membership:
    with transaction.atomic():
        locked = Membership.objects.select_for_update().get(id=membership.id)
        is_owner_demotion = (
            locked.role == Membership.Role.OWNER
            and locked.status == Membership.Status.ACTIVE
            and status != Membership.Status.ACTIVE
        )

        if is_owner_demotion:
            owner_count = (
                Membership.objects.select_for_update()
                .filter(
                    tenant=locked.tenant,
                    role=Membership.Role.OWNER,
                    status=Membership.Status.ACTIVE,
                )
                .count()
            )
            if owner_count <= 1:
                raise LastOwnerError("Cannot remove or demote the final active owner.")

        locked.status = status
        if status == Membership.Status.ACTIVE and locked.joined_at is None:
            locked.joined_at = timezone.now()
        locked.save(update_fields=["status", "joined_at", "updated_at"])

    return locked


def _generate_domain_token() -> str:
    return secrets.token_urlsafe(24).replace("-", "").replace("_", "")[:48]


def _domain_verification_mode() -> str:
    return getattr(settings, "DOMAIN_VERIFICATION_MODE", "manual").strip().lower()


def request_custom_domain(
    *,
    tenant: Tenant,
    host: str,
    is_primary: bool = False,
    request=None,
) -> Domain:
    domain = add_domain(
        tenant=tenant,
        host=host,
        domain_type=Domain.DomainType.CUSTOM_DOMAIN,
        is_primary=is_primary,
    )

    token = _generate_domain_token()
    domain.verification_token = token
    domain.txt_record_name = f"_musico-verify.{domain.host}"
    domain.txt_record_value = f"musico-verify={token}"
    domain.verification_status = Domain.VerificationStatus.PENDING
    domain.ssl_status = Domain.SSLStatus.PENDING
    domain.verification_error = ""
    domain.ssl_error = ""
    domain.save(
        update_fields=[
            "verification_token",
            "txt_record_name",
            "txt_record_value",
            "verification_status",
            "ssl_status",
            "verification_error",
            "ssl_error",
            "updated_at",
        ]
    )

    log_audit_event(
        action="domain.requested",
        request=request,
        tenant=tenant,
        object_type="domain",
        object_id=str(domain.id),
        metadata={"host": domain.host, "is_primary": is_primary},
    )
    return domain


def verify_domain_dns(
    *,
    domain: Domain,
    txt_records: list[str] | None = None,
    request=None,
) -> Domain:
    mode = _domain_verification_mode()
    expected_value = (domain.txt_record_value or "").strip().lower()
    provided_values = {(record or "").strip().lower() for record in (txt_records or [])}

    verified = False
    verification_error = ""

    if mode == "auto_accept":
        verified = True
    elif expected_value and expected_value in provided_values:
        verified = True
    else:
        verification_error = "Verification TXT record did not match expected value."

    domain.last_checked_at = timezone.now()
    if verified:
        domain.verification_status = Domain.VerificationStatus.VERIFIED
        domain.verified_at = timezone.now()
        domain.verification_error = ""
    else:
        domain.verification_status = Domain.VerificationStatus.FAILED
        domain.verification_error = verification_error

    domain.save(
        update_fields=[
            "verification_status",
            "verified_at",
            "verification_error",
            "last_checked_at",
            "updated_at",
        ]
    )

    log_audit_event(
        action="domain.verification_checked",
        request=request,
        tenant=domain.tenant,
        object_type="domain",
        object_id=str(domain.id),
        status="success" if verified else "failure",
        metadata={
            "host": domain.host,
            "mode": mode,
            "verified": verified,
            "provided_count": len(provided_values),
        },
    )
    return domain


def provision_domain_ssl(*, domain: Domain, request=None) -> Domain:
    if domain.domain_type == Domain.DomainType.PLATFORM_SUBDOMAIN:
        domain.ssl_status = Domain.SSLStatus.UNMANAGED
        domain.ssl_error = ""
        domain.save(update_fields=["ssl_status", "ssl_error", "updated_at"])
        return domain

    if domain.verification_status != Domain.VerificationStatus.VERIFIED:
        domain.ssl_status = Domain.SSLStatus.ERROR
        domain.ssl_error = "Domain must be verified before SSL provisioning."
        domain.save(update_fields=["ssl_status", "ssl_error", "updated_at"])
        raise DomainVerificationError(domain.ssl_error)

    domain.ssl_status = Domain.SSLStatus.ACTIVE
    domain.ssl_provisioned_at = timezone.now()
    domain.ssl_error = ""
    domain.save(update_fields=["ssl_status", "ssl_provisioned_at", "ssl_error", "updated_at"])

    log_audit_event(
        action="domain.ssl_provisioned",
        request=request,
        tenant=domain.tenant,
        object_type="domain",
        object_id=str(domain.id),
        metadata={"host": domain.host},
    )
    return domain


def verify_and_activate_domain(
    *,
    domain: Domain,
    txt_records: list[str] | None = None,
    request=None,
) -> Domain:
    verify_domain_dns(domain=domain, txt_records=txt_records, request=request)
    if domain.verification_status != Domain.VerificationStatus.VERIFIED:
        raise DomainVerificationError("Domain verification failed.")

    provision_domain_ssl(domain=domain, request=request)
    return domain
