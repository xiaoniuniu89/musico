import json

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from apps.tenancy.context import (
    get_active_membership,
    get_session_payload,
    switch_active_tenant_by_slug,
)


def _credentials_from_request(request):
    if request.content_type and "application/json" in request.content_type:
        payload = json.loads(request.body or "{}")
    else:
        payload = request.POST

    identifier = (
        payload.get("identifier")
        or payload.get("username")
        or payload.get("email")
        or ""
    ).strip()
    password = (payload.get("password") or "").strip()
    return identifier, password


def _resolve_username(identifier: str):
    user_model = get_user_model()
    username_field = user_model.USERNAME_FIELD
    if username_field == "email":
        return identifier

    if "@" in identifier:
        user = user_model.objects.filter(email__iexact=identifier).first()
        if user:
            return getattr(user, username_field)

    return identifier


@require_POST
def login_view(request):
    identifier, password = _credentials_from_request(request)
    if not identifier or not password:
        return JsonResponse(
            {"error": "identifier and password are required"},
            status=400,
        )

    username_value = _resolve_username(identifier)
    user_model = get_user_model()
    auth_kwargs = {user_model.USERNAME_FIELD: username_value, "password": password}
    user = authenticate(request, **auth_kwargs)

    if user is None:
        return JsonResponse({"error": "invalid credentials"}, status=401)

    login(request, user)

    # Eagerly resolve and cache active tenant session after login.
    get_active_membership(request)

    return JsonResponse(get_session_payload(request))


@require_POST
def logout_view(request):
    logout(request)
    return JsonResponse({"authenticated": False})


@require_GET
def session_view(request):
    return JsonResponse(get_session_payload(request))


@require_POST
def switch_tenant_view(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "authentication required"}, status=401)

    if request.content_type and "application/json" in request.content_type:
        payload = json.loads(request.body or "{}")
    else:
        payload = request.POST

    tenant_slug = (payload.get("tenant_slug") or "").strip()
    if not tenant_slug:
        return JsonResponse({"error": "tenant_slug is required"}, status=400)

    membership = switch_active_tenant_by_slug(
        request=request,
        user=request.user,
        tenant_slug=tenant_slug,
    )
    if membership is None:
        return JsonResponse({"error": "tenant membership not found"}, status=404)

    return JsonResponse(get_session_payload(request))
