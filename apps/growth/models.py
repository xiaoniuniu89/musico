from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.tenancy.models import Tenant


class TeacherCompPlan(models.Model):
    class CompType(models.TextChoices):
        HOURLY = "hourly", "Hourly"
        PER_LESSON = "per_lesson", "Per lesson"
        REVENUE_SHARE = "revenue_share", "Revenue share"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="teacher_comp_plans")
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="teacher_comp_plans",
    )
    comp_type = models.CharField(max_length=24, choices=CompType.choices)
    rate_cents = models.PositiveIntegerField(default=0)
    revenue_share_bps = models.PositiveIntegerField(default=0)
    effective_from = models.DateField(default=timezone.localdate)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "teacher"],
                condition=Q(is_active=True),
                name="uniq_active_comp_plan_per_teacher",
            )
        ]
        indexes = [models.Index(fields=["tenant", "teacher", "is_active"])]


class PayrollPeriod(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        FINALIZED = "finalized", "Finalized"
        PAID = "paid", "Paid"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="payroll_periods")
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_payroll_periods",
    )
    finalized_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "start_date", "end_date"],
                name="uniq_payroll_period_window",
            )
        ]
        indexes = [models.Index(fields=["tenant", "status", "start_date"])]


class PayrollLine(models.Model):
    period = models.ForeignKey(PayrollPeriod, on_delete=models.CASCADE, related_name="lines")
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="payroll_lines")
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payroll_lines",
    )
    comp_plan = models.ForeignKey(
        TeacherCompPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payroll_lines",
    )
    lessons_count = models.PositiveIntegerField(default=0)
    lesson_minutes = models.PositiveIntegerField(default=0)
    gross_cents = models.IntegerField(default=0)
    adjustments_cents = models.IntegerField(default=0)
    total_cents = models.IntegerField(default=0)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["period", "teacher"], name="uniq_payroll_line_period_teacher"
            )
        ]
        indexes = [models.Index(fields=["tenant", "teacher"])]

    def save(self, *args, **kwargs):
        self.tenant_id = self.period.tenant_id
        self.total_cents = self.gross_cents + self.adjustments_cents
        super().save(*args, **kwargs)


class PayrollPayout(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"

    line = models.ForeignKey(PayrollLine, on_delete=models.CASCADE, related_name="payouts")
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="payroll_payouts")
    amount_cents = models.IntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    reference = models.CharField(max_length=120, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["tenant", "status"])]

    def save(self, *args, **kwargs):
        self.tenant_id = self.line.tenant_id
        super().save(*args, **kwargs)


class SiteTheme(models.Model):
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name="site_theme")
    brand_name = models.CharField(max_length=160, blank=True)
    primary_color = models.CharField(max_length=16, default="#1f2937")
    secondary_color = models.CharField(max_length=16, default="#0ea5e9")
    accent_color = models.CharField(max_length=16, default="#f59e0b")
    font_family = models.CharField(max_length=120, default="system-ui")
    logo_url = models.URLField(blank=True)
    hero_title = models.CharField(max_length=200, blank=True)
    hero_subtitle = models.TextField(blank=True)
    custom_css = models.TextField(blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_site_themes",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class SitePage(models.Model):
    class Layout(models.TextChoices):
        LANDING = "landing", "Landing"
        INFO = "info", "Info"
        CONTACT = "contact", "Contact"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="site_pages")
    slug = models.SlugField(max_length=120)
    title = models.CharField(max_length=200)
    layout = models.CharField(max_length=24, choices=Layout.choices, default=Layout.INFO)
    meta_description = models.CharField(max_length=255, blank=True)
    content = models.JSONField(default=dict, blank=True)
    is_homepage = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_site_pages",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "slug"], name="uniq_site_page_slug_per_tenant"
            ),
            models.UniqueConstraint(
                fields=["tenant"],
                condition=Q(is_homepage=True),
                name="uniq_homepage_per_tenant",
            ),
        ]
        indexes = [models.Index(fields=["tenant", "is_published"])]


class SiteMenuItem(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="site_menu_items")
    page = models.ForeignKey(
        SitePage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="menu_items",
    )
    label = models.CharField(max_length=120)
    order = models.PositiveIntegerField(default=0)
    external_url = models.URLField(blank=True)
    is_visible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "id"]
        indexes = [models.Index(fields=["tenant", "is_visible", "order"])]
