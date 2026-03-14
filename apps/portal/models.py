from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.ops.models import Family, Student
from apps.tenancy.models import Tenant


class PortalAccessLink(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="portal_access_links")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="portal_access_links",
    )
    family = models.ForeignKey(
        Family,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="portal_access_links",
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="portal_access_links",
    )
    can_view_billing = models.BooleanField(default=True)
    can_view_resources = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invited_portal_access_links",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(family__isnull=False) | Q(student__isnull=False),
                name="portal_access_requires_target",
            ),
            models.UniqueConstraint(
                fields=["tenant", "user", "family", "student"],
                name="uniq_portal_access_target",
            ),
        ]
        indexes = [models.Index(fields=["tenant", "user", "is_active"])]

    def save(self, *args, **kwargs):
        if self.family is not None:
            self.tenant_id = self.family.tenant_id
        elif self.student is not None:
            self.tenant_id = self.student.tenant_id
        super().save(*args, **kwargs)
