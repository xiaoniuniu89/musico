from __future__ import annotations

import json
from datetime import UTC

from django.db.models import Prefetch, Sum
from django.http import Http404, JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.views.decorators.http import require_GET, require_http_methods

from apps.ops.models import (
    Event,
    Family,
    FamilyContact,
    Invoice,
    MessageLog,
    Payment,
    Resource,
    ResourceAssignment,
    SchedulerJobRun,
    Student,
)
from apps.ops.services import (
    OpsError,
    apply_payment_result,
    create_event_with_recurrence,
    create_invoice,
    create_payment_checkout,
    create_resource_assignment,
    mark_attendance,
    queue_message,
    run_reminders_job,
    send_due_messages,
    send_invoice,
)
from apps.tenancy.models import AuditLog, Domain, Membership
from apps.tenancy.permissions import tenant_member_required, tenant_roles_required
from apps.tenancy.services import (
    DomainVerificationError,
    request_custom_domain,
    set_primary_domain,
    verify_and_activate_domain,
)


def _json_body(request):
    if request.content_type and "application/json" in request.content_type:
        try:
            return json.loads(request.body or "{}")
        except json.JSONDecodeError:
            return {}
    return dict(request.POST)


def _iso(dt):
    return dt.isoformat() if dt else None


def _get_tenant_object_or_404(queryset, *, tenant, **filters):
    obj = queryset.filter(tenant=tenant, **filters).first()
    if obj is None:
        raise Http404
    return obj


def _parse_datetime(value: str | None):
    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone=UTC)
    return parsed


def _family_payload(family: Family):
    return {
        "id": family.id,
        "name": family.name,
        "email": family.email,
        "phone": family.phone,
        "notes": family.notes,
        "tags": family.tags,
        "is_archived": family.is_archived,
    }


def _student_payload(student: Student):
    return {
        "id": student.id,
        "family_id": student.family_id,
        "first_name": student.first_name,
        "last_name": student.last_name,
        "display_name": student.display_name,
        "full_name": student.full_name,
        "instrument": student.instrument,
        "level": student.level,
        "is_archived": student.is_archived,
    }


def _event_payload(event: Event):
    return {
        "id": event.id,
        "title": event.title,
        "event_type": event.event_type,
        "student_id": event.student_id,
        "start_at": _iso(event.start_at),
        "end_at": _iso(event.end_at),
        "status": event.status,
        "recurrence_type": event.recurrence_type,
        "recurrence_until": event.recurrence_until.isoformat() if event.recurrence_until else None,
        "parent_event_id": event.parent_event_id,
    }


def _invoice_payload(invoice: Invoice):
    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "family_id": invoice.family_id,
        "status": invoice.status,
        "due_date": invoice.due_date.isoformat(),
        "subtotal_cents": invoice.subtotal_cents,
        "total_cents": invoice.total_cents,
        "currency": invoice.currency,
    }


def _resource_payload(resource: Resource):
    return {
        "id": resource.id,
        "title": resource.title,
        "description": resource.description,
        "file_path": resource.file_path,
        "external_url": resource.external_url,
        "visibility": resource.visibility,
        "is_archived": resource.is_archived,
    }


def _domain_payload(domain: Domain):
    return {
        "id": domain.id,
        "host": domain.host,
        "domain_type": domain.domain_type,
        "is_primary": domain.is_primary,
        "verification_status": domain.verification_status,
        "verification_token": domain.verification_token,
        "txt_record_name": domain.txt_record_name,
        "txt_record_value": domain.txt_record_value,
        "verification_error": domain.verification_error,
        "verified_at": _iso(domain.verified_at),
        "ssl_status": domain.ssl_status,
        "ssl_provisioned_at": _iso(domain.ssl_provisioned_at),
        "ssl_error": domain.ssl_error,
    }


def _quick_actions_for_role(role: str, *, viewport: str):
    actions_by_role = {
        Membership.Role.OWNER: [
            "create_student",
            "create_invoice",
            "run_reminders",
            "manage_domains",
        ],
        Membership.Role.ADMIN: [
            "create_student",
            "create_invoice",
            "run_reminders",
            "manage_domains",
        ],
        Membership.Role.STAFF: [
            "create_student",
            "create_invoice",
            "run_reminders",
        ],
        Membership.Role.TEACHER: [
            "mark_attendance",
            "reschedule_lesson",
            "share_resource",
            "message_family",
        ],
        Membership.Role.PARENT: [
            "view_upcoming_lesson",
            "pay_invoice",
            "open_resource",
            "message_teacher",
        ],
        Membership.Role.STUDENT: [
            "view_assignments",
            "view_calendar",
            "open_resource",
        ],
    }
    actions = actions_by_role.get(role, [])
    if viewport == "mobile":
        actions = actions[:4]
    return actions


@tenant_member_required
@require_http_methods(["GET", "POST"])
def families_view(request):
    if request.method == "GET":
        families = Family.objects.filter(tenant=request.tenant, is_archived=False).order_by("name")
        return JsonResponse({"results": [_family_payload(f) for f in families]})

    payload = _json_body(request)
    family = Family.objects.create(
        tenant=request.tenant,
        name=payload.get("name", "").strip(),
        email=payload.get("email", "").strip(),
        phone=payload.get("phone", "").strip(),
        address=payload.get("address", "").strip(),
        notes=payload.get("notes", "").strip(),
        tags=payload.get("tags") or [],
    )
    return JsonResponse(_family_payload(family), status=201)


@tenant_member_required
@require_http_methods(["GET", "PATCH", "DELETE"])
def family_detail_view(request, family_id: int):
    family = _get_tenant_object_or_404(Family.objects, tenant=request.tenant, id=family_id)

    if request.method == "GET":
        payload = _family_payload(family)
        payload["contacts"] = [
            {
                "id": c.id,
                "full_name": c.full_name,
                "relationship": c.relationship,
                "email": c.email,
                "phone": c.phone,
                "is_primary": c.is_primary,
            }
            for c in family.contacts.all().order_by("-is_primary", "id")
        ]
        return JsonResponse(payload)

    if request.method == "DELETE":
        family.is_archived = True
        family.save(update_fields=["is_archived", "updated_at"])
        return JsonResponse({"status": "archived"})

    payload = _json_body(request)
    for field in ["name", "email", "phone", "address", "notes", "tags", "is_archived"]:
        if field in payload:
            setattr(family, field, payload[field])
    family.save()
    return JsonResponse(_family_payload(family))


@tenant_member_required
@require_http_methods(["POST"])
def family_contacts_view(request, family_id: int):
    family = _get_tenant_object_or_404(Family.objects, tenant=request.tenant, id=family_id)
    payload = _json_body(request)
    contact = FamilyContact.objects.create(
        family=family,
        tenant=request.tenant,
        full_name=payload.get("full_name", "").strip(),
        relationship=payload.get("relationship", FamilyContact.Relationship.PARENT),
        email=payload.get("email", "").strip(),
        phone=payload.get("phone", "").strip(),
        is_primary=bool(payload.get("is_primary", False)),
        notes=payload.get("notes", "").strip(),
    )
    return JsonResponse(
        {
            "id": contact.id,
            "family_id": contact.family_id,
            "full_name": contact.full_name,
            "relationship": contact.relationship,
            "email": contact.email,
            "phone": contact.phone,
            "is_primary": contact.is_primary,
        },
        status=201,
    )


@tenant_member_required
@require_http_methods(["GET", "POST"])
def students_view(request):
    if request.method == "GET":
        students = (
            Student.objects.filter(tenant=request.tenant, is_archived=False)
            .select_related("family")
            .order_by("last_name")
        )
        return JsonResponse({"results": [_student_payload(s) for s in students]})

    payload = _json_body(request)
    family = _get_tenant_object_or_404(
        Family.objects, tenant=request.tenant, id=int(payload["family_id"])
    )
    student = Student.objects.create(
        family=family,
        tenant=request.tenant,
        first_name=payload.get("first_name", "").strip(),
        last_name=payload.get("last_name", "").strip(),
        display_name=payload.get("display_name", "").strip(),
        email=payload.get("email", "").strip(),
        phone=payload.get("phone", "").strip(),
        instrument=payload.get("instrument", "").strip(),
        level=payload.get("level", "").strip(),
        notes=payload.get("notes", "").strip(),
        tags=payload.get("tags") or [],
        date_of_birth=parse_date(payload.get("date_of_birth") or ""),
    )
    return JsonResponse(_student_payload(student), status=201)


@tenant_member_required
@require_http_methods(["GET", "PATCH", "DELETE"])
def student_detail_view(request, student_id: int):
    student = _get_tenant_object_or_404(
        Student.objects.select_related("family"),
        tenant=request.tenant,
        id=student_id,
    )

    if request.method == "GET":
        return JsonResponse(_student_payload(student))

    if request.method == "DELETE":
        student.is_archived = True
        student.save(update_fields=["is_archived", "updated_at"])
        return JsonResponse({"status": "archived"})

    payload = _json_body(request)
    for field in [
        "first_name",
        "last_name",
        "display_name",
        "email",
        "phone",
        "instrument",
        "level",
        "notes",
        "tags",
        "is_archived",
    ]:
        if field in payload:
            setattr(student, field, payload[field])
    if "family_id" in payload:
        family = _get_tenant_object_or_404(
            Family.objects, tenant=request.tenant, id=int(payload["family_id"])
        )
        student.family = family
    if "date_of_birth" in payload:
        student.date_of_birth = parse_date(payload["date_of_birth"])
    student.save()
    return JsonResponse(_student_payload(student))


@tenant_member_required
@require_http_methods(["GET", "POST"])
def events_view(request):
    if request.method == "GET":
        events = Event.objects.filter(tenant=request.tenant, is_archived=False).order_by("start_at")
        start = _parse_datetime(request.GET.get("start"))
        end = _parse_datetime(request.GET.get("end"))
        if start:
            events = events.filter(start_at__gte=start)
        if end:
            events = events.filter(start_at__lte=end)
        return JsonResponse({"results": [_event_payload(e) for e in events]})

    payload = _json_body(request)
    student = None
    if payload.get("student_id"):
        student = _get_tenant_object_or_404(
            Student.objects,
            tenant=request.tenant,
            id=int(payload["student_id"]),
        )

    start_at = _parse_datetime(payload.get("start_at"))
    end_at = _parse_datetime(payload.get("end_at"))
    if start_at is None or end_at is None:
        return JsonResponse({"error": "valid start_at and end_at are required"}, status=400)

    recurrence_until = parse_date(payload.get("recurrence_until") or "")

    try:
        result = create_event_with_recurrence(
            tenant=request.tenant,
            title=payload.get("title", "").strip(),
            start_at=start_at,
            end_at=end_at,
            event_type=payload.get("event_type", Event.EventType.LESSON),
            student=student,
            teacher=request.user,
            created_by=request.user,
            notes=payload.get("notes", "").strip(),
            recurrence_type=payload.get("recurrence_type", Event.RecurrenceType.NONE),
            recurrence_interval=int(payload.get("recurrence_interval", 1)),
            recurrence_until=recurrence_until,
        )
    except OpsError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse(
        {
            "event": _event_payload(result.parent_event),
            "occurrences_created": result.occurrences_created,
        },
        status=201,
    )


@tenant_member_required
@require_http_methods(["GET", "PATCH", "DELETE"])
def event_detail_view(request, event_id: int):
    event = _get_tenant_object_or_404(Event.objects, tenant=request.tenant, id=event_id)

    if request.method == "GET":
        return JsonResponse(_event_payload(event))

    if request.method == "DELETE":
        event.is_archived = True
        event.save(update_fields=["is_archived", "updated_at"])
        return JsonResponse({"status": "archived"})

    payload = _json_body(request)
    for field in ["title", "status", "notes", "event_type"]:
        if field in payload:
            setattr(event, field, payload[field])

    if "start_at" in payload:
        parsed = _parse_datetime(payload["start_at"])
        if parsed is None:
            return JsonResponse({"error": "invalid start_at"}, status=400)
        event.start_at = parsed

    if "end_at" in payload:
        parsed = _parse_datetime(payload["end_at"])
        if parsed is None:
            return JsonResponse({"error": "invalid end_at"}, status=400)
        event.end_at = parsed

    event.save()
    return JsonResponse(_event_payload(event))


@tenant_member_required
@require_http_methods(["POST"])
def event_attendance_view(request, event_id: int):
    event = _get_tenant_object_or_404(
        Event.objects.select_related("student"),
        tenant=request.tenant,
        id=event_id,
    )
    payload = _json_body(request)

    student = event.student
    if payload.get("student_id"):
        student = _get_tenant_object_or_404(
            Student.objects,
            tenant=request.tenant,
            id=int(payload["student_id"]),
        )

    if student is None:
        return JsonResponse({"error": "student_id is required for this event"}, status=400)

    try:
        record = mark_attendance(
            event=event,
            student=student,
            status=payload.get("status"),
            marked_by=request.user,
            note=payload.get("note", ""),
        )
    except OpsError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse(
        {
            "id": record.id,
            "event_id": record.event_id,
            "student_id": record.student_id,
            "status": record.status,
            "note": record.note,
        },
        status=201,
    )


@tenant_member_required
@require_http_methods(["GET", "POST"])
def invoices_view(request):
    if request.method == "GET":
        invoices = Invoice.objects.filter(tenant=request.tenant).order_by("-created_at")
        return JsonResponse({"results": [_invoice_payload(i) for i in invoices]})

    payload = _json_body(request)
    family = _get_tenant_object_or_404(
        Family.objects, tenant=request.tenant, id=int(payload["family_id"])
    )
    due_date = parse_date(payload.get("due_date") or "")
    items = payload.get("items") or []
    if due_date is None or not items:
        return JsonResponse({"error": "due_date and items are required"}, status=400)

    invoice = create_invoice(
        tenant=request.tenant,
        family=family,
        due_date=due_date,
        items=items,
        notes=payload.get("notes", ""),
        currency=payload.get("currency"),
        created_by=request.user,
    )
    return JsonResponse(_invoice_payload(invoice), status=201)


@tenant_member_required
@require_http_methods(["GET", "PATCH"])
def invoice_detail_view(request, invoice_id: int):
    invoice = _get_tenant_object_or_404(
        Invoice.objects.prefetch_related("items", Prefetch("payments")),
        tenant=request.tenant,
        id=invoice_id,
    )

    if request.method == "GET":
        payload = _invoice_payload(invoice)
        payload["items"] = [
            {
                "id": item.id,
                "description": item.description,
                "quantity": str(item.quantity),
                "unit_price_cents": item.unit_price_cents,
                "line_total_cents": item.line_total_cents,
            }
            for item in invoice.items.all()
        ]
        payload["payments"] = [
            {
                "id": payment.id,
                "status": payment.status,
                "provider": payment.provider,
                "amount_cents": payment.amount_cents,
                "checkout_url": payment.checkout_url,
            }
            for payment in invoice.payments.all().order_by("id")
        ]
        return JsonResponse(payload)

    payload = _json_body(request)
    if "notes" in payload:
        invoice.notes = payload["notes"]
    if "status" in payload:
        invoice.status = payload["status"]
    invoice.save()
    return JsonResponse(_invoice_payload(invoice))


@tenant_roles_required("owner", "admin", "staff", "teacher")
@require_http_methods(["POST"])
def invoice_send_view(request, invoice_id: int):
    invoice = _get_tenant_object_or_404(Invoice.objects, tenant=request.tenant, id=invoice_id)
    try:
        send_invoice(invoice=invoice)
    except OpsError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(_invoice_payload(invoice))


@tenant_member_required
@require_http_methods(["POST"])
def invoice_pay_link_view(request, invoice_id: int):
    invoice = _get_tenant_object_or_404(Invoice.objects, tenant=request.tenant, id=invoice_id)
    payload = _json_body(request)
    provider = payload.get("provider", Payment.Provider.STRIPE)

    try:
        payment = create_payment_checkout(invoice=invoice, provider=provider)
    except OpsError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse(
        {
            "id": payment.id,
            "invoice_id": payment.invoice_id,
            "status": payment.status,
            "provider": payment.provider,
            "amount_cents": payment.amount_cents,
            "checkout_url": payment.checkout_url,
        },
        status=201,
    )


@tenant_member_required
@require_http_methods(["POST"])
def payment_confirm_view(request, payment_id: int):
    payment = _get_tenant_object_or_404(
        Payment.objects.select_related("invoice"), tenant=request.tenant, id=payment_id
    )
    payload = _json_body(request)
    status = payload.get("status")
    reference = payload.get("provider_reference", "")

    payment = apply_payment_result(payment=payment, status=status, provider_reference=reference)
    return JsonResponse(
        {
            "id": payment.id,
            "status": payment.status,
            "invoice_id": payment.invoice_id,
            "provider_reference": payment.provider_reference,
        }
    )


@tenant_member_required
@require_http_methods(["GET"])
def messages_view(request):
    messages = MessageLog.objects.filter(tenant=request.tenant).order_by("-id")
    return JsonResponse(
        {
            "results": [
                {
                    "id": message.id,
                    "channel": message.channel,
                    "to_email": message.to_email,
                    "to_phone": message.to_phone,
                    "template_key": message.template_key,
                    "status": message.status,
                    "scheduled_for": _iso(message.scheduled_for),
                    "sent_at": _iso(message.sent_at),
                }
                for message in messages
            ]
        }
    )


@tenant_member_required
@require_http_methods(["POST"])
def messages_send_view(request):
    payload = _json_body(request)
    family = None
    student = None
    if payload.get("family_id"):
        family = _get_tenant_object_or_404(
            Family.objects, tenant=request.tenant, id=int(payload["family_id"])
        )
    if payload.get("student_id"):
        student = _get_tenant_object_or_404(
            Student.objects, tenant=request.tenant, id=int(payload["student_id"])
        )

    scheduled_for = _parse_datetime(payload.get("scheduled_for"))
    message = queue_message(
        tenant=request.tenant,
        channel=payload.get("channel", MessageLog.Channel.EMAIL),
        to_email=payload.get("to_email", "").strip(),
        to_phone=payload.get("to_phone", "").strip(),
        subject=payload.get("subject", "").strip(),
        body=payload.get("body", "").strip(),
        template_key=payload.get("template_key", "manual"),
        family=family,
        student=student,
        scheduled_for=scheduled_for,
        created_by=request.user,
    )

    if not scheduled_for:
        send_due_messages(tenant=request.tenant)
        message.refresh_from_db()

    return JsonResponse(
        {
            "id": message.id,
            "status": message.status,
            "to_email": message.to_email,
            "template_key": message.template_key,
        },
        status=201,
    )


@tenant_roles_required("owner", "admin", "staff", "teacher")
@require_http_methods(["POST"])
def messages_run_reminders_view(request):
    payload = _json_body(request)
    hours_ahead = int(payload.get("hours_ahead", 24))

    run = run_reminders_job(tenant=request.tenant, hours_ahead=hours_ahead)
    return JsonResponse(
        {
            "run_id": run.id,
            "status": run.status,
            "queued": run.queued_count,
            "processed": run.processed_count,
            "sent": run.success_count,
            "failed": run.failure_count,
            "retry_scheduled": run.retry_scheduled_count,
        }
    )


@tenant_member_required
@require_http_methods(["GET", "POST"])
def resources_view(request):
    if request.method == "GET":
        resources = Resource.objects.filter(tenant=request.tenant).order_by("-created_at")
        return JsonResponse({"results": [_resource_payload(r) for r in resources]})

    payload = _json_body(request)
    resource = Resource.objects.create(
        tenant=request.tenant,
        title=payload.get("title", "").strip(),
        description=payload.get("description", "").strip(),
        file_path=payload.get("file_path", "").strip(),
        external_url=payload.get("external_url", "").strip(),
        content_type=payload.get("content_type", "").strip(),
        visibility=payload.get("visibility", Resource.Visibility.STUDENT),
        uploaded_by=request.user,
    )
    return JsonResponse(_resource_payload(resource), status=201)


@tenant_member_required
@require_http_methods(["GET", "PATCH", "DELETE"])
def resource_detail_view(request, resource_id: int):
    resource = _get_tenant_object_or_404(Resource.objects, tenant=request.tenant, id=resource_id)

    if request.method == "GET":
        return JsonResponse(_resource_payload(resource))

    if request.method == "DELETE":
        resource.is_archived = True
        resource.save(update_fields=["is_archived", "updated_at"])
        return JsonResponse({"status": "archived"})

    payload = _json_body(request)
    for field in [
        "title",
        "description",
        "file_path",
        "external_url",
        "content_type",
        "visibility",
    ]:
        if field in payload:
            setattr(resource, field, payload[field])
    resource.save()
    return JsonResponse(_resource_payload(resource))


@tenant_member_required
@require_http_methods(["POST"])
def resource_assign_view(request, resource_id: int):
    resource = _get_tenant_object_or_404(Resource.objects, tenant=request.tenant, id=resource_id)
    payload = _json_body(request)

    student = None
    family = None
    if payload.get("student_id"):
        student = _get_tenant_object_or_404(
            Student.objects, tenant=request.tenant, id=int(payload["student_id"])
        )
    if payload.get("family_id"):
        family = _get_tenant_object_or_404(
            Family.objects, tenant=request.tenant, id=int(payload["family_id"])
        )

    try:
        assignment = create_resource_assignment(
            resource=resource,
            assigned_by=request.user,
            student=student,
            family=family,
            note=payload.get("note", ""),
            due_date=parse_date(payload.get("due_date") or ""),
        )
    except OpsError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse(
        {
            "id": assignment.id,
            "resource_id": assignment.resource_id,
            "student_id": assignment.student_id,
            "family_id": assignment.family_id,
            "note": assignment.note,
        },
        status=201,
    )


@tenant_member_required
@require_GET
def resource_assignments_view(request):
    assignments = ResourceAssignment.objects.filter(tenant=request.tenant).order_by("-assigned_at")
    return JsonResponse(
        {
            "results": [
                {
                    "id": assignment.id,
                    "resource_id": assignment.resource_id,
                    "student_id": assignment.student_id,
                    "family_id": assignment.family_id,
                    "assigned_at": _iso(assignment.assigned_at),
                }
                for assignment in assignments
            ]
        }
    )


@tenant_roles_required("owner", "admin")
@require_http_methods(["GET", "POST"])
def domains_view(request):
    if request.method == "GET":
        domains = Domain.objects.filter(tenant=request.tenant).order_by("-is_primary", "host")
        return JsonResponse({"results": [_domain_payload(domain) for domain in domains]})

    payload = _json_body(request)
    host = (payload.get("host") or "").strip()
    if not host:
        return JsonResponse({"error": "host is required"}, status=400)

    domain = request_custom_domain(
        tenant=request.tenant,
        host=host,
        is_primary=bool(payload.get("is_primary", False)),
        request=request,
    )
    return JsonResponse(_domain_payload(domain), status=201)


@tenant_roles_required("owner", "admin")
@require_http_methods(["GET"])
def domain_detail_view(request, domain_id: int):
    domain = _get_tenant_object_or_404(Domain.objects, tenant=request.tenant, id=domain_id)
    return JsonResponse(_domain_payload(domain))


@tenant_roles_required("owner", "admin")
@require_http_methods(["POST"])
def domain_verify_view(request, domain_id: int):
    domain = _get_tenant_object_or_404(Domain.objects, tenant=request.tenant, id=domain_id)
    payload = _json_body(request)
    txt_records = payload.get("txt_records") or []
    if not isinstance(txt_records, list):
        return JsonResponse({"error": "txt_records must be a list"}, status=400)

    try:
        verify_and_activate_domain(domain=domain, txt_records=txt_records, request=request)
    except DomainVerificationError as exc:
        domain.refresh_from_db()
        return JsonResponse({"error": str(exc), "domain": _domain_payload(domain)}, status=400)

    domain.refresh_from_db()
    return JsonResponse(_domain_payload(domain))


@tenant_roles_required("owner", "admin")
@require_http_methods(["POST"])
def domain_set_primary_view(request, domain_id: int):
    domain = _get_tenant_object_or_404(Domain.objects, tenant=request.tenant, id=domain_id)
    set_primary_domain(tenant=request.tenant, domain=domain)
    domain.refresh_from_db()
    return JsonResponse(_domain_payload(domain))


@tenant_roles_required("owner", "admin")
@require_GET
def audit_logs_view(request):
    limit = min(int(request.GET.get("limit", 50)), 200)
    logs = AuditLog.objects.filter(tenant=request.tenant).order_by("-id")[:limit]
    return JsonResponse(
        {
            "results": [
                {
                    "id": log.id,
                    "action": log.action,
                    "status": log.status,
                    "method": log.method,
                    "path": log.path,
                    "object_type": log.object_type,
                    "object_id": log.object_id,
                    "metadata": log.metadata,
                    "created_at": _iso(log.created_at),
                    "user_id": log.user_id,
                }
                for log in logs
            ]
        }
    )


@tenant_roles_required("owner", "admin", "staff")
@require_GET
def scheduler_runs_view(request):
    runs = SchedulerJobRun.objects.filter(tenant=request.tenant).order_by("-id")[:50]
    return JsonResponse(
        {
            "results": [
                {
                    "id": run.id,
                    "job_key": run.job_key,
                    "status": run.status,
                    "queued_count": run.queued_count,
                    "processed_count": run.processed_count,
                    "success_count": run.success_count,
                    "failure_count": run.failure_count,
                    "retry_scheduled_count": run.retry_scheduled_count,
                    "started_at": _iso(run.started_at),
                    "finished_at": _iso(run.finished_at),
                }
                for run in runs
            ]
        }
    )


@tenant_roles_required("owner", "admin", "staff")
@require_GET
def scheduler_run_detail_view(request, run_id: int):
    run = _get_tenant_object_or_404(SchedulerJobRun.objects, tenant=request.tenant, id=run_id)
    return JsonResponse(
        {
            "id": run.id,
            "job_key": run.job_key,
            "status": run.status,
            "queued_count": run.queued_count,
            "processed_count": run.processed_count,
            "success_count": run.success_count,
            "failure_count": run.failure_count,
            "retry_scheduled_count": run.retry_scheduled_count,
            "metadata": run.metadata,
            "started_at": _iso(run.started_at),
            "finished_at": _iso(run.finished_at),
        }
    )


@tenant_member_required
@require_GET
def dashboard_summary_view(request):
    role = request.membership.role
    viewport = (request.GET.get("viewport") or "").strip().lower()
    if viewport not in {"mobile", "desktop"}:
        user_agent = request.META.get("HTTP_USER_AGENT", "").lower()
        viewport = "mobile" if "mobile" in user_agent else "desktop"

    now = timezone.now()
    upcoming_events_count = Event.objects.filter(
        tenant=request.tenant,
        status=Event.Status.SCHEDULED,
        is_archived=False,
        start_at__gte=now,
    ).count()
    unpaid_invoices = Invoice.objects.filter(
        tenant=request.tenant,
        status__in=[Invoice.Status.SENT, Invoice.Status.OVERDUE],
    )
    unpaid_invoices_count = unpaid_invoices.count()
    unpaid_total_cents = unpaid_invoices.aggregate(total=Sum("total_cents"))["total"] or 0
    resources_count = Resource.objects.filter(tenant=request.tenant, is_archived=False).count()
    failed_messages_count = MessageLog.objects.filter(
        tenant=request.tenant,
        status=MessageLog.Status.FAILED,
    ).count()

    return JsonResponse(
        {
            "role": role,
            "viewport": viewport,
            "layout": {
                "navigation": "bottom-tabs" if viewport == "mobile" else "side-nav",
                "card_density": "compact" if viewport == "mobile" else "comfortable",
            },
            "quick_actions": _quick_actions_for_role(role, viewport=viewport),
            "kpis": {
                "upcoming_events_count": upcoming_events_count,
                "unpaid_invoices_count": unpaid_invoices_count,
                "unpaid_total_cents": unpaid_total_cents,
                "resources_count": resources_count,
                "failed_messages_count": failed_messages_count,
            },
        }
    )
