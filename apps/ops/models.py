from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.tenancy.models import Tenant


class Family(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="families")
    name = models.CharField(max_length=160)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    extensions = models.JSONField(default=dict, blank=True)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["tenant", "is_archived"])]

    def __str__(self) -> str:
        return self.name


class FamilyContact(models.Model):
    class Relationship(models.TextChoices):
        PARENT = "parent", "Parent"
        GUARDIAN = "guardian", "Guardian"
        EMERGENCY = "emergency", "Emergency"
        OTHER = "other", "Other"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="family_contacts")
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="contacts")
    full_name = models.CharField(max_length=160)
    relationship = models.CharField(
        max_length=16, choices=Relationship.choices, default=Relationship.PARENT
    )
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    is_primary = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    extensions = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["family"],
                condition=Q(is_primary=True),
                name="uniq_primary_contact_per_family",
            )
        ]

    def save(self, *args, **kwargs):
        self.tenant_id = self.family.tenant_id
        super().save(*args, **kwargs)


class Student(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="students")
    family = models.ForeignKey(Family, on_delete=models.PROTECT, related_name="students")
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    display_name = models.CharField(max_length=160, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    instrument = models.CharField(max_length=80, blank=True)
    level = models.CharField(max_length=80, blank=True)
    notes = models.TextField(blank=True)
    extensions = models.JSONField(default=dict, blank=True)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["tenant", "is_archived"])]

    def save(self, *args, **kwargs):
        self.tenant_id = self.family.tenant_id
        super().save(*args, **kwargs)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class Event(models.Model):
    class EventType(models.TextChoices):
        LESSON = "lesson", "Lesson"
        RECITAL = "recital", "Recital"
        MEETING = "meeting", "Meeting"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        RESCHEDULED = "rescheduled", "Rescheduled"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"

    class RecurrenceType(models.TextChoices):
        NONE = "none", "None"
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="events")
    student = models.ForeignKey(
        Student, on_delete=models.SET_NULL, null=True, blank=True, related_name="events"
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teaching_events",
    )
    title = models.CharField(max_length=200)
    event_type = models.CharField(
        max_length=16, choices=EventType.choices, default=EventType.LESSON
    )
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SCHEDULED)
    timezone = models.CharField(max_length=64, default="UTC")
    recurrence_type = models.CharField(
        max_length=16,
        choices=RecurrenceType.choices,
        default=RecurrenceType.NONE,
    )
    recurrence_interval = models.PositiveIntegerField(default=1)
    recurrence_until = models.DateField(null=True, blank=True)
    occurrences = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="occurrences_set",
    )
    notes = models.TextField(blank=True)
    extensions = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_events",
    )
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "start_at"]),
            models.Index(fields=["tenant", "is_archived"]),
        ]


class EventAttendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = "present", "Present"
        ABSENT = "absent", "Absent"
        LATE = "late", "Late"
        EXCUSED = "excused", "Excused"
        CANCELLED = "cancelled", "Cancelled"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="attendances")
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="attendance_records")
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="attendance_records"
    )
    status = models.CharField(max_length=16, choices=Status.choices)
    note = models.TextField(blank=True)
    extensions = models.JSONField(default=dict, blank=True)
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="marked_attendance_records",
    )
    marked_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["event", "student"], name="uniq_attendance_event_student"
            )
        ]
        indexes = [models.Index(fields=["tenant", "status"])]

    def save(self, *args, **kwargs):
        self.tenant_id = self.event.tenant_id
        super().save(*args, **kwargs)


class Invoice(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        PAID = "paid", "Paid"
        OVERDUE = "overdue", "Overdue"
        VOID = "void", "Void"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="invoices")
    family = models.ForeignKey(Family, on_delete=models.PROTECT, related_name="invoices")
    invoice_number = models.CharField(max_length=40, blank=True)
    issue_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField()
    currency = models.CharField(max_length=8, default="USD")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    subtotal_cents = models.PositiveIntegerField(default=0)
    total_cents = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    extensions = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_invoices",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["tenant", "status", "due_date"])]


class InvoiceItem(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="invoice_items")
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    description = models.CharField(max_length=240)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1.00"))
    unit_price_cents = models.PositiveIntegerField()
    line_total_cents = models.PositiveIntegerField(default=0)
    sort_order = models.PositiveIntegerField(default=0)
    extensions = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def save(self, *args, **kwargs):
        quantity = self.quantity or Decimal("0")
        self.line_total_cents = int(quantity * self.unit_price_cents)
        self.tenant_id = self.invoice.tenant_id
        super().save(*args, **kwargs)


class InvoiceTemplate(models.Model):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="invoice_templates",
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    default_notes = models.TextField(blank=True)
    default_extensions = models.JSONField(default=dict, blank=True)
    default_items = models.JSONField(
        default=list,
        blank=True,
        help_text="List of dicts: [{'description': '...', 'unit_price_cents': 100}]",
    )
    is_archived = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_invoice_templates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"],
                name="uniq_invoice_template_per_tenant",
            )
        ]
        indexes = [models.Index(fields=["tenant", "is_archived"])]

    def __str__(self) -> str:
        return self.name


class Payment(models.Model):
    class Provider(models.TextChoices):
        STRIPE = "stripe", "Stripe"
        MANUAL = "manual", "Manual"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="payments")
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments")
    provider = models.CharField(max_length=16, choices=Provider.choices, default=Provider.STRIPE)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    amount_cents = models.PositiveIntegerField()
    currency = models.CharField(max_length=8, default="USD")
    provider_reference = models.CharField(max_length=120, blank=True)
    checkout_url = models.URLField(blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    extensions = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["tenant", "status"])]

    def save(self, *args, **kwargs):
        self.tenant_id = self.invoice.tenant_id
        super().save(*args, **kwargs)


class MessageLog(models.Model):
    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        SMS = "sms", "SMS"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="messages")
    family = models.ForeignKey(
        Family, on_delete=models.SET_NULL, null=True, blank=True, related_name="messages"
    )
    student = models.ForeignKey(
        Student, on_delete=models.SET_NULL, null=True, blank=True, related_name="messages"
    )
    channel = models.CharField(max_length=16, choices=Channel.choices, default=Channel.EMAIL)
    template_key = models.CharField(max_length=80, blank=True)
    subject = models.CharField(max_length=200)
    body = models.TextField()
    to_email = models.EmailField(blank=True)
    to_phone = models.CharField(max_length=32, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    provider_message_id = models.CharField(max_length=120, blank=True)
    error_message = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=3)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    extensions = models.JSONField(default=dict, blank=True)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_messages",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["tenant", "status", "scheduled_for"])]


class MessageTemplate(models.Model):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="message_templates",
    )
    name = models.CharField(max_length=120)
    channel = models.CharField(
        max_length=16,
        choices=MessageLog.Channel.choices,
        default=MessageLog.Channel.EMAIL,
    )
    subject = models.CharField(max_length=200, blank=True)
    body = models.TextField()
    is_archived = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_message_templates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"],
                name="uniq_message_template_per_tenant",
            )
        ]
        indexes = [models.Index(fields=["tenant", "is_archived"])]

    def __str__(self) -> str:
        return self.name


class Resource(models.Model):
    class Visibility(models.TextChoices):
        PRIVATE = "private", "Private"
        FAMILY = "family", "Family"
        STUDENT = "student", "Student"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="resources")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    file_path = models.CharField(max_length=255, blank=True)
    external_url = models.URLField(blank=True)
    content_type = models.CharField(max_length=80, blank=True)
    visibility = models.CharField(
        max_length=16, choices=Visibility.choices, default=Visibility.STUDENT
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_resources",
    )
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["tenant", "is_archived"])]


class ResourceAssignment(models.Model):
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="resource_assignments"
    )
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name="assignments")
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="resource_assignments",
    )
    family = models.ForeignKey(
        Family,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="resource_assignments",
    )
    note = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_resources",
    )
    assigned_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(student__isnull=False) | Q(family__isnull=False),
                name="resource_assignment_requires_target",
            )
        ]
        indexes = [models.Index(fields=["tenant", "assigned_at"])]

    def save(self, *args, **kwargs):
        self.tenant_id = self.resource.tenant_id
        super().save(*args, **kwargs)


class ResourceTemplate(models.Model):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="resource_templates",
    )
    name = models.CharField(max_length=120)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    file_path = models.CharField(max_length=255, blank=True)
    external_url = models.URLField(blank=True)
    assignment_note = models.TextField(blank=True)
    assignment_due_days = models.PositiveSmallIntegerField(null=True, blank=True)
    is_archived = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_resource_templates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"],
                name="uniq_resource_template_per_tenant",
            )
        ]
        indexes = [models.Index(fields=["tenant", "is_archived"])]

    def __str__(self) -> str:
        return self.name


class SchedulerJobRun(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        PARTIAL = "partial", "Partial"
        FAILED = "failed", "Failed"

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scheduler_job_runs",
    )
    job_key = models.CharField(max_length=80)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RUNNING)
    queued_count = models.PositiveIntegerField(default=0)
    processed_count = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    failure_count = models.PositiveIntegerField(default=0)
    retry_scheduled_count = models.PositiveIntegerField(default=0)
    extensions = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["job_key", "created_at"]), models.Index(fields=["status"])]

    def __str__(self) -> str:
        return f"{self.job_key}:{self.status}:{self.started_at.isoformat()}"
