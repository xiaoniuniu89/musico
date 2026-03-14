from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.ops.models import (
    Event,
    EventAttendance,
    Family,
    Invoice,
    InvoiceItem,
    MessageLog,
    Payment,
    Resource,
    ResourceAssignment,
    SchedulerJobRun,
    Student,
)
from apps.tenancy.localization import normalize_currency_code


class OpsError(Exception):
    """Base ops exception."""


def _add_months(dt: datetime, months: int) -> datetime:
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(
        dt.day,
        [
            31,
            29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
            31,
            30,
            31,
            30,
            31,
            31,
            30,
            31,
            30,
            31,
        ][month - 1],
    )
    return dt.replace(year=year, month=month, day=day)


@dataclass
class RecurrenceResult:
    parent_event: Event
    occurrences_created: int


def create_event_with_recurrence(
    *,
    tenant,
    title: str,
    start_at: datetime,
    end_at: datetime,
    event_type: str = Event.EventType.LESSON,
    student: Student | None = None,
    teacher=None,
    created_by=None,
    notes: str = "",
    recurrence_type: str = Event.RecurrenceType.NONE,
    recurrence_interval: int = 1,
    recurrence_until: date | None = None,
) -> RecurrenceResult:
    if end_at <= start_at:
        raise OpsError("end_at must be after start_at")

    if recurrence_type != Event.RecurrenceType.NONE and recurrence_until is None:
        raise OpsError("recurrence_until is required for recurring events")

    if recurrence_interval < 1:
        raise OpsError("recurrence_interval must be >= 1")

    with transaction.atomic():
        parent = Event.objects.create(
            tenant=tenant,
            student=student,
            teacher=teacher,
            title=title,
            event_type=event_type,
            start_at=start_at,
            end_at=end_at,
            recurrence_type=recurrence_type,
            recurrence_interval=recurrence_interval,
            recurrence_until=recurrence_until,
            notes=notes,
            created_by=created_by,
        )

        occurrences = 0
        if recurrence_type != Event.RecurrenceType.NONE and recurrence_until is not None:
            next_start = start_at
            next_end = end_at
            while True:
                if recurrence_type == Event.RecurrenceType.DAILY:
                    next_start = next_start + timedelta(days=recurrence_interval)
                    next_end = next_end + timedelta(days=recurrence_interval)
                elif recurrence_type == Event.RecurrenceType.WEEKLY:
                    next_start = next_start + timedelta(weeks=recurrence_interval)
                    next_end = next_end + timedelta(weeks=recurrence_interval)
                else:
                    next_start = _add_months(next_start, recurrence_interval)
                    next_end = _add_months(next_end, recurrence_interval)

                if next_start.date() > recurrence_until:
                    break

                Event.objects.create(
                    tenant=tenant,
                    student=student,
                    teacher=teacher,
                    title=title,
                    event_type=event_type,
                    start_at=next_start,
                    end_at=next_end,
                    recurrence_type=Event.RecurrenceType.NONE,
                    recurrence_interval=1,
                    parent_event=parent,
                    notes=notes,
                    created_by=created_by,
                )
                occurrences += 1

    return RecurrenceResult(parent_event=parent, occurrences_created=occurrences)


def mark_attendance(*, event: Event, student: Student, status: str, marked_by=None, note: str = ""):
    if event.tenant_id != student.tenant_id:
        raise OpsError("event and student must belong to same tenant")

    attendance, _ = EventAttendance.objects.update_or_create(
        event=event,
        student=student,
        defaults={
            "tenant": event.tenant,
            "status": status,
            "note": note,
            "marked_by": marked_by,
            "marked_at": timezone.now(),
        },
    )
    return attendance


def _generate_invoice_number(*, tenant, invoice_id: int) -> str:
    return f"INV-{tenant.id}-{invoice_id:05d}"


def recalc_invoice_totals(*, invoice: Invoice) -> Invoice:
    subtotal = invoice.items.aggregate(total=Sum("line_total_cents"))["total"] or 0
    invoice.subtotal_cents = subtotal
    invoice.total_cents = subtotal
    invoice.save(update_fields=["subtotal_cents", "total_cents", "updated_at"])
    return invoice


def create_invoice(
    *,
    tenant,
    family: Family,
    due_date: date,
    items: list[dict],
    notes: str = "",
    currency: str | None = None,
    created_by=None,
):
    effective_currency = normalize_currency_code(currency or getattr(tenant, "currency", "USD"))
    with transaction.atomic():
        invoice = Invoice.objects.create(
            tenant=tenant,
            family=family,
            due_date=due_date,
            notes=notes,
            currency=effective_currency,
            created_by=created_by,
        )
        invoice.invoice_number = _generate_invoice_number(tenant=tenant, invoice_id=invoice.id)
        invoice.save(update_fields=["invoice_number", "updated_at"])

        for idx, item in enumerate(items):
            quantity = Decimal(str(item.get("quantity", "1")))
            unit_price_cents = int(item.get("unit_price_cents", 0))
            InvoiceItem.objects.create(
                tenant=tenant,
                invoice=invoice,
                description=item["description"],
                quantity=quantity,
                unit_price_cents=unit_price_cents,
                sort_order=idx,
            )

        recalc_invoice_totals(invoice=invoice)

    return invoice


def send_invoice(*, invoice: Invoice) -> Invoice:
    if invoice.status == Invoice.Status.VOID:
        raise OpsError("void invoice cannot be sent")

    invoice.status = Invoice.Status.SENT
    invoice.sent_at = timezone.now()
    invoice.save(update_fields=["status", "sent_at", "updated_at"])
    return invoice


def _invoice_paid_amount(*, invoice: Invoice) -> int:
    return (
        invoice.payments.filter(status=Payment.Status.SUCCEEDED).aggregate(
            total=Sum("amount_cents")
        )["total"]
        or 0
    )


def create_payment_checkout(
    *, invoice: Invoice, provider: str = Payment.Provider.STRIPE
) -> Payment:
    amount_due = max(invoice.total_cents - _invoice_paid_amount(invoice=invoice), 0)
    if amount_due <= 0:
        raise OpsError("invoice has no remaining balance")

    checkout_url = ""
    if provider == Payment.Provider.STRIPE:
        checkout_url = f"https://checkout.stripe.com/pay/{uuid4().hex}"

    payment = Payment.objects.create(
        tenant=invoice.tenant,
        invoice=invoice,
        provider=provider,
        status=Payment.Status.PENDING,
        amount_cents=amount_due,
        currency=invoice.currency,
        checkout_url=checkout_url,
        metadata={
            "mode": "simulated"
            if not getattr(settings, "STRIPE_SECRET_KEY", "")
            else "live-configured"
        },
    )
    return payment


def apply_payment_result(*, payment: Payment, status: str, provider_reference: str = "") -> Payment:
    payment.status = status
    payment.provider_reference = provider_reference
    if status == Payment.Status.SUCCEEDED:
        payment.paid_at = timezone.now()
    payment.save(update_fields=["status", "provider_reference", "paid_at", "updated_at"])

    invoice = payment.invoice
    paid_amount = _invoice_paid_amount(invoice=invoice)
    if paid_amount >= invoice.total_cents:
        invoice.status = Invoice.Status.PAID
        invoice.paid_at = timezone.now()
        invoice.save(update_fields=["status", "paid_at", "updated_at"])

    return payment


def mark_overdue_invoices(*, today: date | None = None) -> int:
    today = today or timezone.localdate()
    return Invoice.objects.filter(
        status=Invoice.Status.SENT,
        due_date__lt=today,
    ).update(status=Invoice.Status.OVERDUE, updated_at=timezone.now())


def queue_message(
    *,
    tenant,
    channel: str = MessageLog.Channel.EMAIL,
    to_email: str,
    to_phone: str = "",
    subject: str,
    body: str,
    template_key: str = "",
    family: Family | None = None,
    student: Student | None = None,
    scheduled_for: datetime | None = None,
    created_by=None,
    metadata: dict | None = None,
) -> MessageLog:
    return MessageLog.objects.create(
        tenant=tenant,
        family=family,
        student=student,
        channel=channel,
        to_email=to_email,
        to_phone=to_phone,
        subject=subject,
        body=body,
        template_key=template_key,
        scheduled_for=scheduled_for,
        created_by=created_by,
        metadata=metadata or {},
    )


def send_message_now(*, message: MessageLog) -> MessageLog:
    now = timezone.now()
    if message.status == MessageLog.Status.SENT:
        return message

    try:
        if message.metadata.get("force_fail"):
            raise RuntimeError("Forced message failure for retry flow.")

        if message.channel == MessageLog.Channel.SMS:
            provider = getattr(settings, "SMS_PROVIDER", "disabled").strip().lower()
            if provider in {"console", "simulated"} and message.to_phone:
                message.provider_message_id = f"sms_{uuid4().hex[:12]}"
            else:
                raise RuntimeError("SMS provider is disabled or recipient phone is missing.")
        else:
            send_mail(
                subject=message.subject,
                message=message.body,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@musico.local"),
                recipient_list=[message.to_email],
                fail_silently=False,
            )
            message.provider_message_id = message.provider_message_id or f"email_{uuid4().hex[:12]}"

        message.status = MessageLog.Status.SENT
        message.sent_at = now
        message.error_message = ""
        message.next_retry_at = None
    except Exception as exc:  # pragma: no cover
        message.retry_count += 1
        message.error_message = str(exc)
        if message.retry_count < message.max_retries:
            delay_minutes = min(60, 2**message.retry_count)
            message.status = MessageLog.Status.QUEUED
            message.next_retry_at = now + timedelta(minutes=delay_minutes)
        else:
            message.status = MessageLog.Status.FAILED
            message.next_retry_at = None

    message.last_attempt_at = now
    message.save(
        update_fields=[
            "status",
            "sent_at",
            "error_message",
            "provider_message_id",
            "retry_count",
            "last_attempt_at",
            "next_retry_at",
            "updated_at",
        ]
    )
    return message


def send_due_messages(*, tenant=None, up_to: datetime | None = None) -> dict:
    up_to = up_to or timezone.now()
    queryset = (
        MessageLog.objects.filter(status=MessageLog.Status.QUEUED)
        .filter(Q(scheduled_for__isnull=True) | Q(scheduled_for__lte=up_to))
        .filter(Q(next_retry_at__isnull=True) | Q(next_retry_at__lte=up_to))
    )
    if tenant is not None:
        queryset = queryset.filter(tenant=tenant)

    stats = {
        "processed": 0,
        "sent": 0,
        "failed": 0,
        "retry_scheduled": 0,
    }

    for message in queryset.order_by("id"):
        stats["processed"] += 1
        send_message_now(message=message)
        if message.status == MessageLog.Status.SENT:
            stats["sent"] += 1
        elif message.status == MessageLog.Status.QUEUED:
            stats["retry_scheduled"] += 1
        else:
            stats["failed"] += 1

    return stats


def run_reminders_job(*, tenant=None, hours_ahead: int = 24) -> SchedulerJobRun:
    run = SchedulerJobRun.objects.create(
        tenant=tenant,
        job_key="send_reminders",
        status=SchedulerJobRun.Status.RUNNING,
        started_at=timezone.now(),
    )

    try:
        queued = queue_upcoming_lesson_reminders(tenant=tenant, hours_ahead=hours_ahead)
        delivery_stats = send_due_messages(tenant=tenant)

        run.queued_count = queued
        run.processed_count = delivery_stats["processed"]
        run.success_count = delivery_stats["sent"]
        run.failure_count = delivery_stats["failed"]
        run.retry_scheduled_count = delivery_stats["retry_scheduled"]
        run.metadata = {
            "hours_ahead": hours_ahead,
            "delivery_stats": delivery_stats,
        }
        run.status = (
            SchedulerJobRun.Status.PARTIAL
            if run.failure_count > 0 or run.retry_scheduled_count > 0
            else SchedulerJobRun.Status.SUCCEEDED
        )
    except Exception as exc:  # pragma: no cover
        run.status = SchedulerJobRun.Status.FAILED
        run.metadata = {"error": str(exc), "hours_ahead": hours_ahead}
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "metadata", "finished_at", "updated_at"])
        raise

    run.finished_at = timezone.now()
    run.save(
        update_fields=[
            "queued_count",
            "processed_count",
            "success_count",
            "failure_count",
            "retry_scheduled_count",
            "metadata",
            "status",
            "finished_at",
            "updated_at",
        ]
    )
    return run


def queue_upcoming_lesson_reminders(*, tenant=None, hours_ahead: int = 24) -> int:
    now = timezone.now()
    window_end = now + timedelta(hours=hours_ahead)

    events = Event.objects.select_related("student", "student__family", "tenant").filter(
        start_at__gte=now,
        start_at__lte=window_end,
        status=Event.Status.SCHEDULED,
    )
    if tenant is not None:
        events = events.filter(tenant=tenant)

    created = 0
    for event in events:
        if event.student is None or event.student.family is None:
            continue
        to_email = event.student.family.email
        if not to_email:
            continue

        existing = MessageLog.objects.filter(
            tenant=event.tenant,
            template_key="lesson_reminder",
            metadata__event_id=event.id,
        ).exists()
        if existing:
            continue

        queue_message(
            tenant=event.tenant,
            family=event.student.family,
            student=event.student,
            to_email=to_email,
            subject=f"Lesson reminder: {event.title}",
            body=(
                f"Reminder: {event.student.full_name} has {event.title} at "
                f"{timezone.localtime(event.start_at).strftime('%Y-%m-%d %H:%M')}"
            ),
            template_key="lesson_reminder",
            metadata={"event_id": event.id},
            scheduled_for=None,
        )
        created += 1

    return created


def create_resource_assignment(
    *,
    resource: Resource,
    assigned_by,
    student: Student | None = None,
    family: Family | None = None,
    note: str = "",
    due_date: date | None = None,
) -> ResourceAssignment:
    if student is None and family is None:
        raise OpsError("either student or family target is required")

    if student is not None and student.tenant_id != resource.tenant_id:
        raise OpsError("student must belong to resource tenant")

    if family is not None and family.tenant_id != resource.tenant_id:
        raise OpsError("family must belong to resource tenant")

    return ResourceAssignment.objects.create(
        tenant=resource.tenant,
        resource=resource,
        student=student,
        family=family,
        note=note,
        due_date=due_date,
        assigned_by=assigned_by,
    )
