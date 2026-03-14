from __future__ import annotations

import json

from django.http import Http404, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from apps.ops.models import Event, Invoice, MessageLog, Resource, ResourceAssignment
from apps.tenancy.permissions import tenant_member_required, tenant_roles_required

from .models import PortalAccessLink
from .services import PortalAccessError, resolve_portal_scope


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


@tenant_roles_required("owner", "admin", "staff")
@require_http_methods(["GET", "POST"])
def access_links_view(request):
    if request.method == "GET":
        links = PortalAccessLink.objects.filter(tenant=request.tenant).order_by("-id")
        return JsonResponse(
            {
                "results": [
                    {
                        "id": link.id,
                        "user_id": link.user_id,
                        "family_id": link.family_id,
                        "student_id": link.student_id,
                        "can_view_billing": link.can_view_billing,
                        "can_view_resources": link.can_view_resources,
                        "is_active": link.is_active,
                    }
                    for link in links
                ]
            }
        )

    payload = _json_body(request)
    link = PortalAccessLink.objects.create(
        tenant=request.tenant,
        user_id=int(payload["user_id"]),
        family_id=int(payload["family_id"]) if payload.get("family_id") else None,
        student_id=int(payload["student_id"]) if payload.get("student_id") else None,
        can_view_billing=bool(payload.get("can_view_billing", True)),
        can_view_resources=bool(payload.get("can_view_resources", True)),
        is_active=bool(payload.get("is_active", True)),
        invited_by=request.user,
    )
    return JsonResponse({"id": link.id}, status=201)


@tenant_roles_required("owner", "admin", "staff")
@require_http_methods(["PATCH", "DELETE"])
def access_link_detail_view(request, link_id: int):
    link = _tenant_object_or_404(PortalAccessLink.objects, tenant=request.tenant, id=link_id)

    if request.method == "DELETE":
        link.delete()
        return JsonResponse({"status": "deleted"})

    payload = _json_body(request)
    for field in ["can_view_billing", "can_view_resources", "is_active"]:
        if field in payload:
            setattr(link, field, payload[field])

    if "family_id" in payload:
        link.family_id = int(payload["family_id"]) if payload["family_id"] else None
    if "student_id" in payload:
        link.student_id = int(payload["student_id"]) if payload["student_id"] else None

    link.save()
    return JsonResponse({"id": link.id, "is_active": link.is_active})


@tenant_member_required
@require_GET
def portal_overview_view(request):
    try:
        scope = resolve_portal_scope(membership=request.membership)
    except PortalAccessError as exc:
        return JsonResponse({"error": str(exc)}, status=403)

    now = timezone.now()
    upcoming_events = Event.objects.filter(
        tenant=request.tenant,
        student_id__in=scope.student_ids,
        start_at__gte=now,
        status=Event.Status.SCHEDULED,
    ).order_by("start_at")[:8]

    invoice_qs = Invoice.objects.none()
    if scope.can_view_billing:
        invoice_qs = Invoice.objects.filter(tenant=request.tenant, family_id__in=scope.family_ids)

    outstanding_qs = invoice_qs.filter(status__in=[Invoice.Status.SENT, Invoice.Status.OVERDUE])

    resource_assignment_qs = ResourceAssignment.objects.none()
    if scope.can_view_resources:
        resource_assignment_qs = ResourceAssignment.objects.filter(
            tenant=request.tenant,
            student_id__in=scope.student_ids,
        ) | ResourceAssignment.objects.filter(tenant=request.tenant, family_id__in=scope.family_ids)

    recent_messages = (
        MessageLog.objects.filter(
            tenant=request.tenant,
            status=MessageLog.Status.SENT,
        )
        .filter(to_email=request.user.email)
        .order_by("-sent_at")[:10]
    )

    return JsonResponse(
        {
            "families_count": len(scope.family_ids),
            "students_count": len(scope.student_ids),
            "permissions": {
                "can_view_billing": scope.can_view_billing,
                "can_view_resources": scope.can_view_resources,
            },
            "upcoming_events": [
                {
                    "id": event.id,
                    "title": event.title,
                    "start_at": _iso(event.start_at),
                    "end_at": _iso(event.end_at),
                    "student_id": event.student_id,
                }
                for event in upcoming_events
            ],
            "billing": {
                "outstanding_count": outstanding_qs.count(),
                "outstanding_total_cents": sum(invoice.total_cents for invoice in outstanding_qs),
            },
            "resources": {
                "assigned_count": resource_assignment_qs.distinct().count(),
            },
            "recent_messages": [
                {
                    "id": message.id,
                    "channel": message.channel,
                    "subject": message.subject,
                    "sent_at": _iso(message.sent_at),
                }
                for message in recent_messages
            ],
        }
    )


@tenant_member_required
@require_GET
def portal_calendar_view(request):
    try:
        scope = resolve_portal_scope(membership=request.membership)
    except PortalAccessError as exc:
        return JsonResponse({"error": str(exc)}, status=403)

    events = Event.objects.filter(
        tenant=request.tenant,
        student_id__in=scope.student_ids,
    ).order_by("start_at")[:100]

    return JsonResponse(
        {
            "results": [
                {
                    "id": event.id,
                    "title": event.title,
                    "status": event.status,
                    "start_at": _iso(event.start_at),
                    "end_at": _iso(event.end_at),
                    "student_id": event.student_id,
                }
                for event in events
            ]
        }
    )


@tenant_member_required
@require_GET
def portal_invoices_view(request):
    try:
        scope = resolve_portal_scope(membership=request.membership)
    except PortalAccessError as exc:
        return JsonResponse({"error": str(exc)}, status=403)

    if not scope.can_view_billing:
        return JsonResponse({"error": "billing access is disabled"}, status=403)

    invoices = Invoice.objects.filter(
        tenant=request.tenant, family_id__in=scope.family_ids
    ).order_by("-issue_date")
    return JsonResponse(
        {
            "results": [
                {
                    "id": invoice.id,
                    "invoice_number": invoice.invoice_number,
                    "status": invoice.status,
                    "issue_date": invoice.issue_date.isoformat(),
                    "due_date": invoice.due_date.isoformat(),
                    "total_cents": invoice.total_cents,
                }
                for invoice in invoices
            ]
        }
    )


@tenant_member_required
@require_GET
def portal_resources_view(request):
    try:
        scope = resolve_portal_scope(membership=request.membership)
    except PortalAccessError as exc:
        return JsonResponse({"error": str(exc)}, status=403)

    if not scope.can_view_resources:
        return JsonResponse({"error": "resource access is disabled"}, status=403)

    assignments = (
        ResourceAssignment.objects.filter(tenant=request.tenant, student_id__in=scope.student_ids)
        | ResourceAssignment.objects.filter(tenant=request.tenant, family_id__in=scope.family_ids)
    ).select_related("resource")

    resource_ids = assignments.values_list("resource_id", flat=True).distinct()
    resources = Resource.objects.filter(
        tenant=request.tenant, id__in=resource_ids, is_archived=False
    ).order_by("title")

    return JsonResponse(
        {
            "results": [
                {
                    "id": resource.id,
                    "title": resource.title,
                    "description": resource.description,
                    "file_path": resource.file_path,
                    "external_url": resource.external_url,
                    "visibility": resource.visibility,
                }
                for resource in resources
            ]
        }
    )
