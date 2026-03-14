from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.tenancy.models import Membership
from apps.tenancy.permissions import tenant_member_required, tenant_roles_required


def index(request):
    """
    Main landing page.
    """
    if request.user.is_authenticated:
        return redirect("web_dashboard")
    return render(request, "core/landing.html")


@require_http_methods(["GET", "POST"])
def contact_view(request):
    """
    Beta contact form.
    """
    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        message = request.POST.get("message")
        
        if not name or not email or not message:
            messages.error(request, "Please fill in all fields.")
        else:
            # Send email
            subject = f"Beta Request: {name}"
            body = f"Name: {name}\nEmail: {email}\n\nMessage:\n{message}"
            send_mail(
                subject,
                body,
                settings.DEFAULT_FROM_EMAIL,
                [settings.CONTACT_EMAIL],
                fail_silently=False,
            )
            messages.success(request, "Your request has been sent! We will be in touch soon.")
            return redirect("landing_page")
            
    return render(request, "core/contact.html")


def signup_view(request):
    """
    Signup is currently invitation-only.
    """
    return render(request, "core/signup_invitation.html")


def healthz(request):
    return JsonResponse({"status": "ok"})


def tenant_context(request):
    tenant = getattr(request, "resolved_tenant", None)
    payload = {
        "host": getattr(request, "request_host", None),
        "source": getattr(request, "tenant_resolution_source", "none"),
        "tenant": None,
    }
    if tenant is not None:
        payload["tenant"] = {
            "id": tenant.id,
            "slug": tenant.slug,
            "name": tenant.name,
        }
    return JsonResponse(payload)


@tenant_member_required
def me(request):
    return JsonResponse(
        {
            "user_id": request.user.id,
            "tenant": {
                "id": request.tenant.id,
                "slug": request.tenant.slug,
                "name": request.tenant.name,
            },
            "role": request.membership.role,
        }
    )


@tenant_roles_required(Membership.Role.OWNER, Membership.Role.ADMIN)
def admin_ping(request):
    return JsonResponse({"status": "ok"})
