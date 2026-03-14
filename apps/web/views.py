from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.views.decorators.http import require_http_methods

from apps.growth.services import reporting_summary
from apps.ops.models import (
    Event,
    Family,
    Invoice,
    MessageLog,
    MessageTemplate,
    Payment,
    Resource,
    ResourceAssignment,
    ResourceTemplate,
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
    send_due_messages,
    send_invoice,
)
from apps.tenancy.context import get_active_membership, switch_active_tenant_by_slug
from apps.tenancy.localization import (
    normalize_currency_code,
    normalize_locale_code,
    normalize_timezone_name,
    tenant_localization,
)
from apps.tenancy.models import Domain, Membership
from apps.tenancy.services import (
    DomainVerificationError,
    request_custom_domain,
    set_primary_domain,
    verify_and_activate_domain,
)

from .decorators import web_roles_required, web_tenant_member_required

TIMEZONE_CHOICES = [
    "UTC",
    "Europe/Dublin",
    "Europe/London",
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "Australia/Sydney",
]

CURRENCY_CHOICES = ["USD", "EUR", "GBP", "CAD", "AUD", "NZD"]

EVENT_QUICK_PRESETS = [
    {
        "label": "1:1 Lesson (45m)",
        "title": "Lesson",
        "event_type": Event.EventType.LESSON,
        "duration_minutes": 45,
    },
    {
        "label": "Group Class (60m)",
        "title": "Group Class",
        "event_type": Event.EventType.LESSON,
        "duration_minutes": 60,
    },
    {
        "label": "Parent Meeting (30m)",
        "title": "Parent Meeting",
        "event_type": Event.EventType.MEETING,
        "duration_minutes": 30,
    },
    {
        "label": "Recital Slot (20m)",
        "title": "Recital",
        "event_type": Event.EventType.RECITAL,
        "duration_minutes": 20,
    },
]


def _current_tenants_for_user(request):
    if not request.user.is_authenticated:
        return []
    return (
        request.user.memberships.filter(status=Membership.Status.ACTIVE)
        .select_related("tenant")
        .order_by("tenant__name")
    )


def _coerce_dt(value: str | None):
    parsed = parse_datetime(value or "")
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone=timezone.get_current_timezone())
    return parsed


def _coerce_int(value: str | None, *, default: int, minimum: int | None = None):
    try:
        parsed = int(value or "")
    except (TypeError, ValueError):
        return default

    if minimum is not None and parsed < minimum:
        return default
    return parsed


from apps.portal.services import PortalAccessError, resolve_portal_scope


def _base_context(request, **extra):
    membership = getattr(request, "membership", None)
    tenant = getattr(request, "tenant", None)
    localization = tenant_localization(tenant) if tenant is not None else None
    ctx = {
        "membership": membership,
        "tenant": tenant,
        "active_role": membership.role if membership else None,
        "available_tenants": _current_tenants_for_user(request),
        "tenant_locale": getattr(
            request,
            "tenant_locale",
            localization.locale if localization is not None else settings.LANGUAGE_CODE,
        ),
        "tenant_currency": getattr(
            request,
            "tenant_currency",
            localization.currency
            if localization is not None
            else getattr(settings, "APP_DEFAULT_CURRENCY", "USD"),
        ),
        "tenant_timezone": getattr(
            request,
            "tenant_timezone",
            localization.timezone_name if localization is not None else settings.TIME_ZONE,
        ),
    }
    ctx.update(extra)
    return ctx


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect("web_dashboard")

    if request.method == "POST":
        identifier = (request.POST.get("identifier") or "").strip()
        password = (request.POST.get("password") or "").strip()
        if not identifier or not password:
            messages.error(request, "Enter email/username and password.")
            return render(request, "web/login.html", {"identifier": identifier})

        user_model = get_user_model()
        username_field = user_model.USERNAME_FIELD

        username_value = identifier
        if username_field != "email" and "@" in identifier:
            user = user_model.objects.filter(email__iexact=identifier).first()
            if user is not None:
                username_value = getattr(user, username_field)

        auth_kwargs = {username_field: username_value, "password": password}
        user = authenticate(request, **auth_kwargs)
        if user is None:
            messages.error(request, "Invalid credentials.")
            return render(request, "web/login.html", {"identifier": identifier})

        login(request, user)
        get_active_membership(request)
        return redirect(request.GET.get("next") or "web_dashboard")

    return render(request, "web/login.html")


@require_http_methods(["POST"])
def logout_view(request):
    logout(request)
    return redirect("landing_page")


@require_http_methods(["POST"])
@web_tenant_member_required
def switch_tenant_view(request):
    slug = (request.POST.get("tenant_slug") or "").strip()
    if not slug:
        messages.error(request, "Tenant slug is required.")
        return redirect(request.META.get("HTTP_REFERER") or "/app/")

    membership = switch_active_tenant_by_slug(request=request, user=request.user, tenant_slug=slug)
    if membership is None:
        messages.error(request, "Could not switch tenant.")
    else:
        messages.success(request, f"Switched to {membership.tenant.name}.")

    return redirect(request.META.get("HTTP_REFERER") or "/app/")


@web_tenant_member_required
def dashboard_view(request):
    now = timezone.now()
    membership = request.membership

    try:
        scope = resolve_portal_scope(membership=membership)
    except PortalAccessError:
        scope = None

    if membership.role in {Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.STAFF}:
        events_query = Event.objects.filter(tenant=request.tenant, start_at__gte=now)
        outstanding_invoices = Invoice.objects.filter(
            tenant=request.tenant,
            status__in=[Invoice.Status.SENT, Invoice.Status.OVERDUE],
        )
        summary = reporting_summary(
            tenant=request.tenant,
            start=now - timezone.timedelta(days=30),
            end=now,
        )
    elif membership.role == Membership.Role.TEACHER:
        events_query = Event.objects.filter(tenant=request.tenant, teacher=request.user, start_at__gte=now)
        outstanding_invoices = Invoice.objects.none()
        summary = None
    else:
        # Parents & Students
        if scope:
            events_query = Event.objects.filter(
                tenant=request.tenant, 
                student_id__in=scope.student_ids, 
                start_at__gte=now
            )
            if scope.can_view_billing:
                outstanding_invoices = Invoice.objects.filter(
                    tenant=request.tenant,
                    family_id__in=scope.family_ids,
                    status__in=[Invoice.Status.SENT, Invoice.Status.OVERDUE],
                )
            else:
                outstanding_invoices = Invoice.objects.none()
        else:
            events_query = Event.objects.none()
            outstanding_invoices = Invoice.objects.none()
        summary = None

    upcoming_events = events_query.select_related("student").order_by("start_at")[:6]
    
    if outstanding_invoices.exists():
        outstanding_count = outstanding_invoices.count()
        outstanding_total = outstanding_invoices.aggregate(total=Sum("total_cents"))["total"] or 0
    else:
        outstanding_count = 0
        outstanding_total = 0

    return render(
        request,
        "web/dashboard.html",
        _base_context(
            request,
            upcoming_events=upcoming_events,
            outstanding_count=outstanding_count,
            outstanding_total=outstanding_total,
            summary=summary,
        ),
    )


@require_http_methods(["GET", "POST"])
@web_tenant_member_required
def students_view(request):
    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "create_family":
                Family.objects.create(
                    tenant=request.tenant,
                    name=(request.POST.get("family_name") or "").strip(),
                    email=(request.POST.get("family_email") or "").strip(),
                    phone=(request.POST.get("family_phone") or "").strip(),
                )
                messages.success(request, "Family created.")
            elif action == "create_student":
                family = Family.objects.get(
                    tenant=request.tenant, id=int(request.POST["family_id"])
                )
                Student.objects.create(
                    tenant=request.tenant,
                    family=family,
                    first_name=(request.POST.get("first_name") or "").strip(),
                    last_name=(request.POST.get("last_name") or "").strip(),
                    instrument=(request.POST.get("instrument") or "").strip(),
                    level=(request.POST.get("level") or "").strip(),
                )
                messages.success(request, "Student created.")
            elif action == "archive_student":
                student = Student.objects.get(
                    tenant=request.tenant, id=int(request.POST["student_id"])
                )
                student.is_archived = True
                student.save(update_fields=["is_archived", "updated_at"])
                messages.success(request, "Student archived.")
        except Exception as exc:
            messages.error(request, f"Action failed: {exc}")

        return redirect("/app/students/")

    families = Family.objects.filter(tenant=request.tenant).order_by("name")
    students = (
        Student.objects.filter(tenant=request.tenant).select_related("family").order_by("last_name")
    )
    return render(
        request,
        "web/students.html",
        _base_context(request, families=families, students=students),
    )


@require_http_methods(["GET", "POST"])
@web_tenant_member_required
def calendar_view(request):
    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "create_event":
                student = None
                if request.POST.get("student_id"):
                    student = Student.objects.get(
                        tenant=request.tenant,
                        id=int(request.POST["student_id"]),
                    )

                start_at = _coerce_dt(request.POST.get("start_at"))
                end_at = _coerce_dt(request.POST.get("end_at"))
                duration_minutes = _coerce_int(
                    request.POST.get("duration_minutes"), default=45, minimum=1
                )
                if start_at is None:
                    raise ValueError("start_at is required")
                if end_at is None:
                    end_at = start_at + timezone.timedelta(minutes=duration_minutes)

                event_type = (request.POST.get("event_type") or "").strip()
                if event_type not in Event.EventType.values:
                    event_type = Event.EventType.OTHER

                recurrence_until = parse_date(request.POST.get("recurrence_until") or "")
                recurrence_type = request.POST.get("recurrence_type") or Event.RecurrenceType.NONE
                recurrence_interval = _coerce_int(
                    request.POST.get("recurrence_interval"), default=1, minimum=1
                )
                title = (request.POST.get("title") or "").strip()
                if not title:
                    raise ValueError("title is required")

                create_event_with_recurrence(
                    tenant=request.tenant,
                    title=title,
                    start_at=start_at,
                    end_at=end_at,
                    event_type=event_type,
                    student=student,
                    teacher=request.user,
                    created_by=request.user,
                    notes=(request.POST.get("notes") or "").strip(),
                    recurrence_type=recurrence_type,
                    recurrence_interval=recurrence_interval,
                    recurrence_until=recurrence_until,
                )
                messages.success(request, "Event created.")

            elif action == "mark_attendance":
                event = Event.objects.get(tenant=request.tenant, id=int(request.POST["event_id"]))
                student = Student.objects.get(
                    tenant=request.tenant, id=int(request.POST["student_id"])
                )
                mark_attendance(
                    event=event,
                    student=student,
                    status=request.POST.get("status"),
                    marked_by=request.user,
                    note=(request.POST.get("note") or "").strip(),
                )
                messages.success(request, "Attendance recorded.")

            elif action == "cancel_event":
                event = Event.objects.get(tenant=request.tenant, id=int(request.POST["event_id"]))
                event.status = Event.Status.CANCELLED
                event.save(update_fields=["status", "updated_at"])
                messages.success(request, "Event cancelled.")

        except Exception as exc:
            messages.error(request, f"Action failed: {exc}")

        return redirect("/app/calendar/")

    now = timezone.now()
    events = (
        Event.objects.filter(tenant=request.tenant, start_at__gte=now - timezone.timedelta(days=7))
        .select_related("student")
        .order_by("start_at")[:120]
    )
    students = Student.objects.filter(tenant=request.tenant, is_archived=False).order_by(
        "last_name"
    )
    event_default_start = timezone.localtime(now + timezone.timedelta(hours=1)).replace(
        minute=0,
        second=0,
        microsecond=0,
    )
    event_default_end = event_default_start + timezone.timedelta(minutes=45)

    return render(
        request,
        "web/calendar.html",
        _base_context(
            request,
            events=events,
            students=students,
            event_default_start=event_default_start.strftime("%Y-%m-%dT%H:%M"),
            event_default_end=event_default_end.strftime("%Y-%m-%dT%H:%M"),
            event_default_duration=45,
            event_type_choices=Event.EventType.choices,
            event_quick_presets=EVENT_QUICK_PRESETS,
        ),
    )


@require_http_methods(["GET", "POST"])
@web_tenant_member_required
def invoices_view(request):
    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "create_invoice":
                family = Family.objects.get(
                    tenant=request.tenant, id=int(request.POST["family_id"])
                )
                due_date = parse_date(request.POST.get("due_date") or "")
                if due_date is None:
                    raise ValueError("due date is required")

                quantity = request.POST.get("item_quantity") or "1"
                unit_price = int(request.POST.get("item_unit_price_cents") or 0)
                description = (request.POST.get("item_description") or "Lesson").strip()

                create_invoice(
                    tenant=request.tenant,
                    family=family,
                    due_date=due_date,
                    created_by=request.user,
                    notes=(request.POST.get("notes") or "").strip(),
                    currency=request.POST.get("currency") or request.tenant_currency,
                    items=[
                        {
                            "description": description,
                            "quantity": quantity,
                            "unit_price_cents": unit_price,
                        }
                    ],
                )
                messages.success(request, "Invoice created.")

            elif action == "send_invoice":
                invoice = Invoice.objects.get(
                    tenant=request.tenant, id=int(request.POST["invoice_id"])
                )
                send_invoice(invoice=invoice)
                messages.success(request, "Invoice sent.")

            elif action == "create_pay_link":
                invoice = Invoice.objects.get(
                    tenant=request.tenant, id=int(request.POST["invoice_id"])
                )
                payment = create_payment_checkout(invoice=invoice, provider=Payment.Provider.STRIPE)
                messages.success(request, f"Pay link generated: {payment.checkout_url}")

            elif action == "mark_paid_manual":
                invoice = Invoice.objects.get(
                    tenant=request.tenant, id=int(request.POST["invoice_id"])
                )
                payment = Payment.objects.create(
                    tenant=request.tenant,
                    invoice=invoice,
                    provider=Payment.Provider.MANUAL,
                    amount_cents=invoice.total_cents,
                    currency=invoice.currency,
                    status=Payment.Status.PENDING,
                )
                apply_payment_result(
                    payment=payment,
                    status=Payment.Status.SUCCEEDED,
                    provider_reference="manual_marked_paid",
                )
                messages.success(request, "Invoice marked paid.")

        except OpsError as exc:
            messages.error(request, str(exc))
        except Exception as exc:
            messages.error(request, f"Action failed: {exc}")

        return redirect("/app/invoices/")

    families = Family.objects.filter(tenant=request.tenant).order_by("name")
    invoices = (
        Invoice.objects.filter(tenant=request.tenant)
        .prefetch_related("payments")
        .order_by("-created_at")
    )
    return render(
        request,
        "web/invoices.html",
        _base_context(
            request,
            families=families,
            invoices=invoices,
            invoice_due_date_default=(
                timezone.localdate() + timezone.timedelta(days=7)
            ).isoformat(),
            currency_choices=CURRENCY_CHOICES,
        ),
    )


@require_http_methods(["GET", "POST"])
@web_tenant_member_required
def resources_view(request):
    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "create_resource":
                template = None
                if request.POST.get("template_id"):
                    template = ResourceTemplate.objects.get(
                        tenant=request.tenant,
                        id=int(request.POST["template_id"]),
                        is_archived=False,
                    )

                title = (request.POST.get("title") or "").strip()
                if not title and template is not None:
                    title = template.title
                if not title:
                    raise ValueError("title is required")

                Resource.objects.create(
                    tenant=request.tenant,
                    title=title,
                    description=(request.POST.get("description") or "").strip()
                    or (template.description if template is not None else ""),
                    file_path=(request.POST.get("file_path") or "").strip()
                    or (template.file_path if template is not None else ""),
                    external_url=(request.POST.get("external_url") or "").strip()
                    or (template.external_url if template is not None else ""),
                    uploaded_by=request.user,
                )
                messages.success(request, "Resource created.")

            elif action == "save_resource_template":
                name = (request.POST.get("template_name") or "").strip()
                title = (request.POST.get("template_title") or "").strip()
                if not name:
                    raise ValueError("template name is required")
                if not title:
                    raise ValueError("template title is required")

                due_days = None
                due_days_raw = (request.POST.get("template_assignment_due_days") or "").strip()
                if due_days_raw:
                    due_days = _coerce_int(due_days_raw, default=7, minimum=0)

                _, created = ResourceTemplate.objects.update_or_create(
                    tenant=request.tenant,
                    name=name,
                    defaults={
                        "title": title,
                        "description": (request.POST.get("template_description") or "").strip(),
                        "file_path": (request.POST.get("template_file_path") or "").strip(),
                        "external_url": (request.POST.get("template_external_url") or "").strip(),
                        "assignment_note": (
                            request.POST.get("template_assignment_note") or ""
                        ).strip(),
                        "assignment_due_days": due_days,
                        "is_archived": False,
                        "created_by": request.user,
                    },
                )
                messages.success(
                    request,
                    "Resource template saved." if created else "Resource template updated.",
                )

            elif action == "assign_resource":
                resource = Resource.objects.get(
                    tenant=request.tenant, id=int(request.POST["resource_id"])
                )
                template = None
                if request.POST.get("resource_template_id"):
                    template = ResourceTemplate.objects.get(
                        tenant=request.tenant,
                        id=int(request.POST["resource_template_id"]),
                        is_archived=False,
                    )

                student = None
                family = None
                if request.POST.get("student_id"):
                    student = Student.objects.get(
                        tenant=request.tenant, id=int(request.POST["student_id"])
                    )
                if request.POST.get("family_id"):
                    family = Family.objects.get(
                        tenant=request.tenant, id=int(request.POST["family_id"])
                    )

                note = (request.POST.get("note") or "").strip()
                if not note and template is not None:
                    note = template.assignment_note

                due_date = parse_date(request.POST.get("due_date") or "")
                if (
                    due_date is None
                    and template is not None
                    and template.assignment_due_days is not None
                ):
                    due_date = timezone.localdate() + timezone.timedelta(
                        days=template.assignment_due_days
                    )

                create_resource_assignment(
                    resource=resource,
                    assigned_by=request.user,
                    student=student,
                    family=family,
                    note=note,
                    due_date=due_date,
                )
                messages.success(request, "Resource assigned.")

        except OpsError as exc:
            messages.error(request, str(exc))
        except Exception as exc:
            messages.error(request, f"Action failed: {exc}")

        return redirect("/app/resources/")

    resources = Resource.objects.filter(tenant=request.tenant).order_by("-created_at")
    assignments = (
        ResourceAssignment.objects.filter(tenant=request.tenant)
        .select_related("resource", "student", "family")
        .order_by("-assigned_at")
    )
    students = Student.objects.filter(tenant=request.tenant, is_archived=False).order_by(
        "last_name"
    )
    families = Family.objects.filter(tenant=request.tenant, is_archived=False).order_by("name")
    resource_templates = ResourceTemplate.objects.filter(
        tenant=request.tenant,
        is_archived=False,
    ).order_by("name")
    return render(
        request,
        "web/resources.html",
        _base_context(
            request,
            resources=resources,
            assignments=assignments,
            students=students,
            families=families,
            resource_templates=resource_templates,
            resource_due_date_default=(
                timezone.localdate() + timezone.timedelta(days=7)
            ).isoformat(),
        ),
    )


@require_http_methods(["GET", "POST"])
@web_tenant_member_required
def messages_view(request):
    if request.method == "POST":
        action = request.POST.get("action") or "send_message"
        try:
            if action == "save_template":
                name = (request.POST.get("template_name") or "").strip()
                body = (request.POST.get("template_body") or "").strip()
                if not name:
                    raise ValueError("template name is required")
                if not body:
                    raise ValueError("template body is required")

                channel = (request.POST.get("template_channel") or "").strip()
                if channel not in MessageLog.Channel.values:
                    channel = MessageLog.Channel.EMAIL

                template, created = MessageTemplate.objects.update_or_create(
                    tenant=request.tenant,
                    name=name,
                    defaults={
                        "channel": channel,
                        "subject": (request.POST.get("template_subject") or "").strip(),
                        "body": body,
                        "is_archived": False,
                        "created_by": request.user,
                    },
                )
                messages.success(
                    request,
                    "Message template saved." if created else "Message template updated.",
                )
                return redirect(f"/app/messages/?template_id={template.id}")

            template = None
            if request.POST.get("template_id"):
                template = MessageTemplate.objects.get(
                    tenant=request.tenant,
                    id=int(request.POST["template_id"]),
                    is_archived=False,
                )

            channel = (request.POST.get("channel") or "").strip()
            if not channel and template is not None:
                channel = template.channel
            if channel not in MessageLog.Channel.values:
                channel = MessageLog.Channel.EMAIL

            body = (request.POST.get("body") or "").strip()
            if not body and template is not None:
                body = template.body
            if not body:
                raise ValueError("message body is required")

            subject = (request.POST.get("subject") or "").strip()
            if not subject and template is not None:
                subject = template.subject
            if not subject:
                subject = "Message"

            to_email = (request.POST.get("to_email") or "").strip()
            to_phone = (request.POST.get("to_phone") or "").strip()
            if channel == MessageLog.Channel.EMAIL and not to_email:
                raise ValueError("to_email is required for email messages")
            if channel == MessageLog.Channel.SMS and not to_phone:
                raise ValueError("to_phone is required for sms messages")

            queue_message(
                tenant=request.tenant,
                channel=channel,
                to_email=to_email,
                to_phone=to_phone,
                subject=subject,
                body=body,
                template_key=template.name if template is not None else "manual",
                created_by=request.user,
            )
            stats = send_due_messages(tenant=request.tenant)
            messages.success(
                request,
                f"Queued message. Sent: {stats['sent']}, retries: {stats['retry_scheduled']}",
            )
        except Exception as exc:
            messages.error(request, f"Action failed: {exc}")
        return redirect("/app/messages/")

    logs = MessageLog.objects.filter(tenant=request.tenant).order_by("-id")[:120]
    message_templates = MessageTemplate.objects.filter(
        tenant=request.tenant,
        is_archived=False,
    ).order_by("name")
    selected_template = None
    template_id = (request.GET.get("template_id") or "").strip()
    if template_id:
        try:
            selected_template = message_templates.get(id=int(template_id))
        except (ValueError, MessageTemplate.DoesNotExist):
            selected_template = None

    return render(
        request,
        "web/messages.html",
        _base_context(
            request,
            logs=logs,
            message_templates=message_templates,
            selected_message_template=selected_template,
        ),
    )


@require_http_methods(["GET", "POST"])
@web_roles_required(Membership.Role.OWNER, Membership.Role.ADMIN)
def domains_view(request):
    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "create_domain":
                request_custom_domain(
                    tenant=request.tenant,
                    host=(request.POST.get("host") or "").strip(),
                    is_primary=bool(request.POST.get("is_primary")),
                    request=request,
                )
                messages.success(request, "Domain requested.")

            elif action == "update_preferences":
                request.tenant.locale = normalize_locale_code(request.POST.get("locale"))
                request.tenant.currency = normalize_currency_code(request.POST.get("currency"))
                request.tenant.timezone = normalize_timezone_name(request.POST.get("timezone"))
                request.tenant.save(update_fields=["locale", "currency", "timezone", "updated_at"])
                messages.success(request, "Studio preferences updated.")

            elif action == "verify_domain":
                domain = Domain.objects.get(
                    tenant=request.tenant, id=int(request.POST["domain_id"])
                )
                txt_raw = (request.POST.get("txt_records") or "").replace("\n", ",")
                txt_records = [token.strip() for token in txt_raw.split(",") if token.strip()]
                verify_and_activate_domain(domain=domain, txt_records=txt_records, request=request)
                messages.success(request, "Domain verified and SSL activated.")

            elif action == "set_primary":
                domain = Domain.objects.get(
                    tenant=request.tenant, id=int(request.POST["domain_id"])
                )
                set_primary_domain(tenant=request.tenant, domain=domain)
                messages.success(request, "Primary domain updated.")

        except DomainVerificationError as exc:
            messages.error(request, str(exc))
        except Exception as exc:
            messages.error(request, f"Action failed: {exc}")

        return redirect("/app/domains/")

    domains = Domain.objects.filter(tenant=request.tenant).order_by("-is_primary", "host")
    return render(
        request,
        "web/domains.html",
        _base_context(
            request,
            domains=domains,
            locale_choices=getattr(settings, "LANGUAGES", []),
            timezone_choices=TIMEZONE_CHOICES,
            currency_choices=CURRENCY_CHOICES,
        ),
    )


@require_http_methods(["GET", "POST"])
@web_tenant_member_required
def portal_view(request):
    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "update_language":
                lang = request.POST.get("preferred_language")
                request.membership.preferred_language = normalize_locale_code(lang)
                request.membership.save(update_fields=["preferred_language", "updated_at"])
                messages.success(request, "Language preference updated.")
        except Exception as exc:
            messages.error(request, f"Action failed: {exc}")
        return redirect("/app/portal/")

    return render(
        request,
        "web/portal.html",
        _base_context(
            request,
            locale_choices=getattr(settings, "LANGUAGES", []),
        ),
    )
