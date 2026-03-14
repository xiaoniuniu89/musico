from django.conf import settings
from django.db import models
from django.db.models import Q

from .validators import normalize_host, validate_host_format


class Tenant(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        ARCHIVED = "archived", "Archived"

    slug = models.SlugField(max_length=63, unique=True)
    name = models.CharField(max_length=160)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    locale = models.CharField(max_length=16, default="en-us")
    currency = models.CharField(max_length=3, default="USD")
    timezone = models.CharField(max_length=64, default="UTC")
    extensions = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["status"])]

    def save(self, *args, **kwargs):
        from .localization import (
            normalize_currency_code,
            normalize_locale_code,
            normalize_timezone_name,
        )

        self.slug = (self.slug or "").strip().lower()
        self.locale = normalize_locale_code(self.locale)
        self.currency = normalize_currency_code(self.currency)
        self.timezone = normalize_timezone_name(self.timezone)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class Domain(models.Model):
    class DomainType(models.TextChoices):
        PLATFORM_SUBDOMAIN = "platform_subdomain", "Platform subdomain"
        CUSTOM_DOMAIN = "custom_domain", "Custom domain"

    class VerificationStatus(models.TextChoices):
        NOT_REQUIRED = "not_required", "Not required"
        PENDING = "pending", "Pending"
        VERIFIED = "verified", "Verified"
        FAILED = "failed", "Failed"

    class SSLStatus(models.TextChoices):
        UNMANAGED = "unmanaged", "Unmanaged"
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        ERROR = "error", "Error"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="domains")
    host = models.CharField(max_length=255, unique=True, validators=[validate_host_format])
    domain_type = models.CharField(max_length=32, choices=DomainType.choices)
    is_primary = models.BooleanField(default=False)
    verification_status = models.CharField(
        max_length=16,
        choices=VerificationStatus.choices,
        default=VerificationStatus.NOT_REQUIRED,
    )
    verification_token = models.CharField(max_length=64, unique=True, null=True, blank=True)
    txt_record_name = models.CharField(max_length=255, blank=True)
    txt_record_value = models.CharField(max_length=255, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_error = models.TextField(blank=True)
    ssl_status = models.CharField(
        max_length=16,
        choices=SSLStatus.choices,
        default=SSLStatus.UNMANAGED,
    )
    ssl_provisioned_at = models.DateTimeField(null=True, blank=True)
    ssl_error = models.TextField(blank=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant"],
                condition=Q(is_primary=True),
                name="uniq_primary_domain_per_tenant",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "verification_status"]),
            models.Index(fields=["tenant", "ssl_status"]),
        ]

    def save(self, *args, **kwargs):
        self.host = normalize_host(self.host)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.host


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        TEACHER = "teacher", "Teacher"
        STAFF = "staff", "Staff"
        PARENT = "parent", "Parent"
        STUDENT = "student", "Student"

    class Status(models.TextChoices):
        INVITED = "invited", "Invited"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        REVOKED = "revoked", "Revoked"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=16, choices=Role.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    is_default = models.BooleanField(default=False)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="issued_membership_invites",
    )
    joined_at = models.DateTimeField(null=True, blank=True)
    preferred_language = models.CharField(max_length=16, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "tenant"], name="uniq_membership_user_tenant"),
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(is_default=True),
                name="uniq_default_tenant_per_user",
            ),
        ]
        indexes = [models.Index(fields=["tenant", "role", "status"])]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.tenant_id}:{self.role}"


class AuditLog(models.Model):
    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILURE = "failure", "Failure"

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=120)
    object_type = models.CharField(max_length=120, blank=True)
    object_id = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SUCCESS)
    method = models.CharField(max_length=10, blank=True)
    path = models.CharField(max_length=255, blank=True)
    ip_address = models.CharField(max_length=64, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "created_at"]),
            models.Index(fields=["action", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.action}:{self.status}:{self.created_at.isoformat()}"
