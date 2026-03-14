from __future__ import annotations

from datetime import date, datetime

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.growth.models import (
    PayrollLine,
    PayrollPayout,
    PayrollPeriod,
    SitePage,
    SiteTheme,
    TeacherCompPlan,
)
from apps.ops.models import Event, EventAttendance, Invoice, MessageLog, Payment
from apps.tenancy.models import Membership


class GrowthError(Exception):
    """Base growth exception."""


def reporting_summary(
    *, tenant, start: datetime, end: datetime, teacher_id: int | None = None
) -> dict:
    event_qs = Event.objects.filter(tenant=tenant, start_at__gte=start, start_at__lte=end)
    attendance_qs = EventAttendance.objects.filter(
        tenant=tenant,
        event__start_at__gte=start,
        event__start_at__lte=end,
    )
    if teacher_id:
        event_qs = event_qs.filter(teacher_id=teacher_id)
        attendance_qs = attendance_qs.filter(event__teacher_id=teacher_id)

    invoices_qs = Invoice.objects.filter(
        tenant=tenant, issue_date__gte=start.date(), issue_date__lte=end.date()
    )
    payments_qs = Payment.objects.filter(
        tenant=tenant,
        status=Payment.Status.SUCCEEDED,
        paid_at__gte=start,
        paid_at__lte=end,
    )
    messages_qs = MessageLog.objects.filter(
        tenant=tenant,
        created_at__gte=start,
        created_at__lte=end,
    )

    attendance_breakdown = {
        row["status"]: row["count"]
        for row in attendance_qs.values("status").annotate(count=Count("id"))
    }
    message_channel_stats = {
        row["channel"]: {
            "sent": row["sent"],
            "failed": row["failed"],
        }
        for row in messages_qs.values("channel").annotate(
            sent=Count("id", filter=Q(status=MessageLog.Status.SENT)),
            failed=Count("id", filter=Q(status=MessageLog.Status.FAILED)),
        )
    }

    outstanding_qs = Invoice.objects.filter(
        tenant=tenant,
        status__in=[Invoice.Status.SENT, Invoice.Status.OVERDUE],
    )

    top_instruments = list(
        tenant.students.values("instrument")
        .exclude(instrument="")
        .annotate(count=Count("id"))
        .order_by("-count")[:5]
    )

    return {
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "events_count": event_qs.count(),
        "lesson_events_count": event_qs.filter(event_type=Event.EventType.LESSON).count(),
        "attendance_count": attendance_qs.count(),
        "attendance_breakdown": attendance_breakdown,
        "invoices_issued_count": invoices_qs.count(),
        "invoices_issued_total_cents": invoices_qs.aggregate(total=Sum("total_cents"))["total"]
        or 0,
        "payments_succeeded_count": payments_qs.count(),
        "payments_succeeded_total_cents": payments_qs.aggregate(total=Sum("amount_cents"))["total"]
        or 0,
        "outstanding_invoices_count": outstanding_qs.count(),
        "outstanding_total_cents": outstanding_qs.aggregate(total=Sum("total_cents"))["total"] or 0,
        "messages_by_channel": message_channel_stats,
        "top_instruments": top_instruments,
    }


def _event_minutes(event: Event) -> int:
    delta = event.end_at - event.start_at
    return max(int(delta.total_seconds() // 60), 0)


def _teacher_lesson_queryset(*, tenant, teacher_id: int, start_date: date, end_date: date):
    start_dt = datetime.combine(
        start_date, datetime.min.time(), tzinfo=timezone.get_current_timezone()
    )
    end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.get_current_timezone())

    return Event.objects.filter(
        tenant=tenant,
        teacher_id=teacher_id,
        event_type=Event.EventType.LESSON,
        start_at__gte=start_dt,
        start_at__lte=end_dt,
    ).exclude(status=Event.Status.CANCELLED)


def _compute_teacher_compensation(
    *, plan: TeacherCompPlan | None, tenant, teacher_id: int, start_date: date, end_date: date
):
    lessons = list(
        _teacher_lesson_queryset(
            tenant=tenant, teacher_id=teacher_id, start_date=start_date, end_date=end_date
        )
    )
    lesson_count = len(lessons)
    lesson_minutes = sum(_event_minutes(event) for event in lessons)

    if plan is None:
        gross = 0
        details = {"comp_type": "none", "reason": "no_active_plan"}
        return lesson_count, lesson_minutes, gross, details

    if plan.comp_type == TeacherCompPlan.CompType.PER_LESSON:
        gross = lesson_count * plan.rate_cents
        details = {"comp_type": plan.comp_type, "rate_cents": plan.rate_cents}
    elif plan.comp_type == TeacherCompPlan.CompType.HOURLY:
        gross = int((lesson_minutes / 60) * plan.rate_cents)
        details = {
            "comp_type": plan.comp_type,
            "rate_cents": plan.rate_cents,
            "minutes": lesson_minutes,
        }
    else:
        family_ids = list(
            _teacher_lesson_queryset(
                tenant=tenant,
                teacher_id=teacher_id,
                start_date=start_date,
                end_date=end_date,
            )
            .exclude(student__family_id__isnull=True)
            .values_list("student__family_id", flat=True)
            .distinct()
        )
        start_dt = datetime.combine(
            start_date, datetime.min.time(), tzinfo=timezone.get_current_timezone()
        )
        end_dt = datetime.combine(
            end_date, datetime.max.time(), tzinfo=timezone.get_current_timezone()
        )
        revenue_pool = (
            Payment.objects.filter(
                tenant=tenant,
                status=Payment.Status.SUCCEEDED,
                invoice__family_id__in=family_ids,
                paid_at__gte=start_dt,
                paid_at__lte=end_dt,
            ).aggregate(total=Sum("amount_cents"))["total"]
            or 0
        )
        gross = int(revenue_pool * (plan.revenue_share_bps / 10000))
        details = {
            "comp_type": plan.comp_type,
            "revenue_share_bps": plan.revenue_share_bps,
            "revenue_pool_cents": revenue_pool,
        }

    return lesson_count, lesson_minutes, gross, details


def create_payroll_period_with_lines(
    *, tenant, start_date: date, end_date: date, generated_by=None
):
    if end_date < start_date:
        raise GrowthError("end_date must be after start_date")

    with transaction.atomic():
        period = PayrollPeriod.objects.create(
            tenant=tenant,
            start_date=start_date,
            end_date=end_date,
            generated_by=generated_by,
        )

        teacher_ids = list(
            Membership.objects.filter(
                tenant=tenant,
                role=Membership.Role.TEACHER,
                status=Membership.Status.ACTIVE,
            ).values_list("user_id", flat=True)
        )

        for teacher_id in teacher_ids:
            plan = (
                TeacherCompPlan.objects.filter(
                    tenant=tenant,
                    teacher_id=teacher_id,
                    is_active=True,
                    effective_from__lte=end_date,
                )
                .order_by("-effective_from", "-id")
                .first()
            )

            lessons_count, lesson_minutes, gross_cents, details = _compute_teacher_compensation(
                plan=plan,
                tenant=tenant,
                teacher_id=teacher_id,
                start_date=start_date,
                end_date=end_date,
            )

            PayrollLine.objects.create(
                period=period,
                tenant=tenant,
                teacher_id=teacher_id,
                comp_plan=plan,
                lessons_count=lessons_count,
                lesson_minutes=lesson_minutes,
                gross_cents=gross_cents,
                adjustments_cents=0,
                details=details,
            )

    return period


def finalize_payroll_period(*, period: PayrollPeriod):
    if period.status != PayrollPeriod.Status.DRAFT:
        raise GrowthError("Only draft periods can be finalized")

    period.status = PayrollPeriod.Status.FINALIZED
    period.finalized_at = timezone.now()
    period.save(update_fields=["status", "finalized_at", "updated_at"])
    return period


def record_payroll_payout(
    *, line: PayrollLine, amount_cents: int | None = None, reference: str = ""
):
    if line.period.status not in {PayrollPeriod.Status.FINALIZED, PayrollPeriod.Status.PAID}:
        raise GrowthError("Payroll period must be finalized before payout")

    payout = PayrollPayout.objects.create(
        line=line,
        tenant=line.tenant,
        amount_cents=amount_cents if amount_cents is not None else line.total_cents,
        status=PayrollPayout.Status.PAID,
        reference=reference,
        paid_at=timezone.now(),
    )

    unpaid_exists = (
        PayrollLine.objects.filter(period=line.period)
        .exclude(payouts__status=PayrollPayout.Status.PAID)
        .exists()
    )
    if not unpaid_exists:
        line.period.status = PayrollPeriod.Status.PAID
        line.period.save(update_fields=["status", "updated_at"])

    return payout


def get_or_create_theme(*, tenant, updated_by=None):
    theme, created = SiteTheme.objects.get_or_create(
        tenant=tenant,
        defaults={"brand_name": tenant.name, "updated_by": updated_by},
    )
    return theme, created


def publish_page(*, page: SitePage):
    page.is_published = True
    page.published_at = timezone.now()
    page.save(update_fields=["is_published", "published_at", "updated_at"])
    return page


def resolve_public_page(*, tenant, slug: str) -> SitePage | None:
    if slug == "home":
        page = SitePage.objects.filter(tenant=tenant, is_homepage=True, is_published=True).first()
        if page is not None:
            return page

    return SitePage.objects.filter(tenant=tenant, slug=slug, is_published=True).first()
