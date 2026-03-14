from __future__ import annotations

import json
from datetime import datetime, timedelta

from django.http import Http404, JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET, require_http_methods

from apps.growth.models import PayrollLine, PayrollPeriod, SiteMenuItem, SitePage, TeacherCompPlan
from apps.growth.services import (
    GrowthError,
    create_payroll_period_with_lines,
    finalize_payroll_period,
    get_or_create_theme,
    publish_page,
    record_payroll_payout,
    reporting_summary,
    resolve_public_page,
)
from apps.ops.models import MessageLog
from apps.ops.services import queue_message, send_due_messages
from apps.tenancy.models import Tenant
from apps.tenancy.permissions import tenant_member_required, tenant_roles_required


def _json_body(request):
    if request.content_type and "application/json" in request.content_type:
        try:
            return json.loads(request.body or "{}")
        except json.JSONDecodeError:
            return {}
    return dict(request.POST)


def _iso(dt):
    return dt.isoformat() if dt else None


def _tenant_object_or_404(queryset, *, tenant, **filters):
    obj = queryset.filter(tenant=tenant, **filters).first()
    if obj is None:
        raise Http404
    return obj


@tenant_member_required
@require_GET
def report_summary_view(request):
    now = timezone.now()
    start_str = request.GET.get("start")
    end_str = request.GET.get("end")
    teacher_id = request.GET.get("teacher_id")

    if start_str and end_str:
        start_date = parse_date(start_str)
        end_date = parse_date(end_str)
        if start_date is None or end_date is None:
            return JsonResponse({"error": "invalid start/end date"}, status=400)
        start = datetime.combine(
            start_date, datetime.min.time(), tzinfo=timezone.get_current_timezone()
        )
        end = datetime.combine(
            end_date, datetime.max.time(), tzinfo=timezone.get_current_timezone()
        )
    else:
        end = now
        start = now - timedelta(days=30)

    teacher_filter = int(teacher_id) if teacher_id else None
    summary = reporting_summary(
        tenant=request.tenant,
        start=start,
        end=end,
        teacher_id=teacher_filter,
    )
    return JsonResponse(summary)


@tenant_roles_required("owner", "admin", "staff", "teacher")
@require_http_methods(["POST"])
def sms_send_view(request):
    payload = _json_body(request)
    to_phone = (payload.get("to_phone") or "").strip()
    if not to_phone:
        return JsonResponse({"error": "to_phone is required"}, status=400)

    message = queue_message(
        tenant=request.tenant,
        channel=MessageLog.Channel.SMS,
        to_email="",
        to_phone=to_phone,
        subject=payload.get("subject", "SMS"),
        body=(payload.get("body") or "").strip(),
        template_key=payload.get("template_key", "manual_sms"),
        created_by=request.user,
    )
    send_due_messages(tenant=request.tenant)
    message.refresh_from_db()

    return JsonResponse(
        {
            "id": message.id,
            "channel": message.channel,
            "status": message.status,
            "to_phone": message.to_phone,
            "provider_message_id": message.provider_message_id,
            "error_message": message.error_message,
        },
        status=201,
    )


@tenant_roles_required("owner", "admin")
@require_http_methods(["GET", "POST"])
def payroll_plans_view(request):
    if request.method == "GET":
        plans = TeacherCompPlan.objects.filter(tenant=request.tenant).order_by("teacher_id")
        return JsonResponse(
            {
                "results": [
                    {
                        "id": plan.id,
                        "teacher_id": plan.teacher_id,
                        "comp_type": plan.comp_type,
                        "rate_cents": plan.rate_cents,
                        "revenue_share_bps": plan.revenue_share_bps,
                        "effective_from": plan.effective_from.isoformat(),
                        "is_active": plan.is_active,
                    }
                    for plan in plans
                ]
            }
        )

    payload = _json_body(request)
    plan = TeacherCompPlan.objects.create(
        tenant=request.tenant,
        teacher_id=int(payload["teacher_id"]),
        comp_type=payload["comp_type"],
        rate_cents=int(payload.get("rate_cents", 0)),
        revenue_share_bps=int(payload.get("revenue_share_bps", 0)),
        effective_from=parse_date(payload.get("effective_from") or "") or timezone.localdate(),
        is_active=bool(payload.get("is_active", True)),
        notes=payload.get("notes", ""),
    )
    return JsonResponse({"id": plan.id}, status=201)


@tenant_roles_required("owner", "admin")
@require_http_methods(["PATCH"])
def payroll_plan_detail_view(request, plan_id: int):
    plan = _tenant_object_or_404(TeacherCompPlan.objects, tenant=request.tenant, id=plan_id)
    payload = _json_body(request)
    for field in ["comp_type", "rate_cents", "revenue_share_bps", "is_active", "notes"]:
        if field in payload:
            setattr(plan, field, payload[field])
    if "effective_from" in payload:
        plan.effective_from = parse_date(payload["effective_from"]) or plan.effective_from
    plan.save()
    return JsonResponse({"id": plan.id, "is_active": plan.is_active})


@tenant_roles_required("owner", "admin", "staff")
@require_http_methods(["GET", "POST"])
def payroll_periods_view(request):
    if request.method == "GET":
        periods = PayrollPeriod.objects.filter(tenant=request.tenant).order_by("-start_date")
        return JsonResponse(
            {
                "results": [
                    {
                        "id": period.id,
                        "start_date": period.start_date.isoformat(),
                        "end_date": period.end_date.isoformat(),
                        "status": period.status,
                    }
                    for period in periods
                ]
            }
        )

    payload = _json_body(request)
    start_date = parse_date(payload.get("start_date") or "")
    end_date = parse_date(payload.get("end_date") or "")
    if start_date is None or end_date is None:
        return JsonResponse({"error": "start_date and end_date are required"}, status=400)

    try:
        period = create_payroll_period_with_lines(
            tenant=request.tenant,
            start_date=start_date,
            end_date=end_date,
            generated_by=request.user,
        )
    except GrowthError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse({"id": period.id, "status": period.status}, status=201)


@tenant_roles_required("owner", "admin", "staff")
@require_GET
def payroll_period_detail_view(request, period_id: int):
    period = _tenant_object_or_404(
        PayrollPeriod.objects.prefetch_related("lines__payouts"),
        tenant=request.tenant,
        id=period_id,
    )
    return JsonResponse(
        {
            "id": period.id,
            "status": period.status,
            "start_date": period.start_date.isoformat(),
            "end_date": period.end_date.isoformat(),
            "lines": [
                {
                    "id": line.id,
                    "teacher_id": line.teacher_id,
                    "lessons_count": line.lessons_count,
                    "lesson_minutes": line.lesson_minutes,
                    "gross_cents": line.gross_cents,
                    "adjustments_cents": line.adjustments_cents,
                    "total_cents": line.total_cents,
                    "payouts": [
                        {
                            "id": payout.id,
                            "status": payout.status,
                            "amount_cents": payout.amount_cents,
                            "paid_at": _iso(payout.paid_at),
                        }
                        for payout in line.payouts.all()
                    ],
                }
                for line in period.lines.all().order_by("id")
            ],
        }
    )


@tenant_roles_required("owner", "admin", "staff")
@require_http_methods(["POST"])
def payroll_period_finalize_view(request, period_id: int):
    period = _tenant_object_or_404(PayrollPeriod.objects, tenant=request.tenant, id=period_id)
    try:
        period = finalize_payroll_period(period=period)
    except GrowthError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse({"id": period.id, "status": period.status})


@tenant_roles_required("owner", "admin")
@require_http_methods(["POST"])
def payroll_line_payout_view(request, line_id: int):
    line = _tenant_object_or_404(
        PayrollLine.objects.select_related("period"), tenant=request.tenant, id=line_id
    )
    payload = _json_body(request)

    try:
        payout = record_payroll_payout(
            line=line,
            amount_cents=int(payload.get("amount_cents", line.total_cents)),
            reference=payload.get("reference", ""),
        )
    except GrowthError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse(
        {
            "id": payout.id,
            "status": payout.status,
            "line_id": payout.line_id,
            "amount_cents": payout.amount_cents,
        },
        status=201,
    )


@tenant_roles_required("owner", "admin", "staff")
@require_http_methods(["GET", "PATCH"])
def site_theme_view(request):
    theme, _ = get_or_create_theme(tenant=request.tenant, updated_by=request.user)

    if request.method == "GET":
        return JsonResponse(
            {
                "brand_name": theme.brand_name,
                "primary_color": theme.primary_color,
                "secondary_color": theme.secondary_color,
                "accent_color": theme.accent_color,
                "font_family": theme.font_family,
                "logo_url": theme.logo_url,
                "hero_title": theme.hero_title,
                "hero_subtitle": theme.hero_subtitle,
                "custom_css": theme.custom_css,
            }
        )

    payload = _json_body(request)
    for field in [
        "brand_name",
        "primary_color",
        "secondary_color",
        "accent_color",
        "font_family",
        "logo_url",
        "hero_title",
        "hero_subtitle",
        "custom_css",
    ]:
        if field in payload:
            setattr(theme, field, payload[field])
    theme.updated_by = request.user
    theme.save()

    return JsonResponse({"status": "updated"})


@tenant_roles_required("owner", "admin", "staff")
@require_http_methods(["GET", "POST"])
def site_pages_view(request):
    if request.method == "GET":
        pages = SitePage.objects.filter(tenant=request.tenant).order_by("slug")
        return JsonResponse(
            {
                "results": [
                    {
                        "id": page.id,
                        "slug": page.slug,
                        "title": page.title,
                        "layout": page.layout,
                        "is_homepage": page.is_homepage,
                        "is_published": page.is_published,
                    }
                    for page in pages
                ]
            }
        )

    payload = _json_body(request)
    page = SitePage.objects.create(
        tenant=request.tenant,
        slug=payload["slug"],
        title=payload["title"],
        layout=payload.get("layout", SitePage.Layout.INFO),
        meta_description=payload.get("meta_description", ""),
        content=payload.get("content") or {},
        is_homepage=bool(payload.get("is_homepage", False)),
        is_published=bool(payload.get("is_published", False)),
        updated_by=request.user,
    )
    if page.is_published and page.published_at is None:
        publish_page(page=page)
    return JsonResponse({"id": page.id}, status=201)


@tenant_roles_required("owner", "admin", "staff")
@require_http_methods(["GET", "PATCH", "DELETE"])
def site_page_detail_view(request, page_id: int):
    page = _tenant_object_or_404(SitePage.objects, tenant=request.tenant, id=page_id)

    if request.method == "GET":
        return JsonResponse(
            {
                "id": page.id,
                "slug": page.slug,
                "title": page.title,
                "layout": page.layout,
                "meta_description": page.meta_description,
                "content": page.content,
                "is_homepage": page.is_homepage,
                "is_published": page.is_published,
            }
        )

    if request.method == "DELETE":
        page.delete()
        return JsonResponse({"status": "deleted"})

    payload = _json_body(request)
    for field in [
        "slug",
        "title",
        "layout",
        "meta_description",
        "content",
        "is_homepage",
        "is_published",
    ]:
        if field in payload:
            setattr(page, field, payload[field])
    page.updated_by = request.user
    page.save()
    if page.is_published and page.published_at is None:
        publish_page(page=page)

    return JsonResponse({"id": page.id, "is_published": page.is_published})


@tenant_roles_required("owner", "admin", "staff")
@require_http_methods(["GET", "POST"])
def site_menu_view(request):
    if request.method == "GET":
        items = SiteMenuItem.objects.filter(tenant=request.tenant).order_by("order", "id")
        return JsonResponse(
            {
                "results": [
                    {
                        "id": item.id,
                        "label": item.label,
                        "page_id": item.page_id,
                        "external_url": item.external_url,
                        "order": item.order,
                        "is_visible": item.is_visible,
                    }
                    for item in items
                ]
            }
        )

    payload = _json_body(request)
    page = None
    if payload.get("page_id"):
        page = _tenant_object_or_404(
            SitePage.objects, tenant=request.tenant, id=int(payload["page_id"])
        )

    item = SiteMenuItem.objects.create(
        tenant=request.tenant,
        page=page,
        label=payload.get("label", "").strip(),
        external_url=payload.get("external_url", "").strip(),
        order=int(payload.get("order", 0)),
        is_visible=bool(payload.get("is_visible", True)),
    )
    return JsonResponse({"id": item.id}, status=201)


@tenant_roles_required("owner", "admin", "staff")
@require_http_methods(["PATCH", "DELETE"])
def site_menu_detail_view(request, item_id: int):
    item = _tenant_object_or_404(SiteMenuItem.objects, tenant=request.tenant, id=item_id)

    if request.method == "DELETE":
        item.delete()
        return JsonResponse({"status": "deleted"})

    payload = _json_body(request)
    if "page_id" in payload:
        item.page = None
        if payload["page_id"]:
            item.page = _tenant_object_or_404(
                SitePage.objects,
                tenant=request.tenant,
                id=int(payload["page_id"]),
            )

    for field in ["label", "external_url", "order", "is_visible"]:
        if field in payload:
            setattr(item, field, payload[field])
    item.save()
    return JsonResponse({"id": item.id})


@require_GET
def public_page_view(request, slug: str):
    tenant = getattr(request, "resolved_tenant", None)
    if tenant is None:
        tenant_slug = (request.GET.get("tenant_slug") or "").strip().lower()
        if tenant_slug:
            tenant = Tenant.objects.filter(slug=tenant_slug, status=Tenant.Status.ACTIVE).first()

    if tenant is None:
        return JsonResponse({"error": "tenant context not resolved"}, status=404)

    page = resolve_public_page(tenant=tenant, slug=slug)
    if page is None:
        raise Http404

    theme, _ = get_or_create_theme(tenant=tenant)
    menu = SiteMenuItem.objects.filter(tenant=tenant, is_visible=True).order_by("order", "id")

    return JsonResponse(
        {
            "tenant": {"slug": tenant.slug, "name": tenant.name},
            "theme": {
                "brand_name": theme.brand_name,
                "primary_color": theme.primary_color,
                "secondary_color": theme.secondary_color,
                "accent_color": theme.accent_color,
                "font_family": theme.font_family,
                "logo_url": theme.logo_url,
                "hero_title": theme.hero_title,
                "hero_subtitle": theme.hero_subtitle,
                "custom_css": theme.custom_css,
            },
            "page": {
                "slug": page.slug,
                "title": page.title,
                "layout": page.layout,
                "meta_description": page.meta_description,
                "content": page.content,
            },
            "menu": [
                {
                    "label": item.label,
                    "slug": item.page.slug if item.page_id else "",
                    "external_url": item.external_url,
                }
                for item in menu
            ],
        }
    )
