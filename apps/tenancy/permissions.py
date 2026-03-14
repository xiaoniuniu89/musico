from functools import wraps

from django.http import JsonResponse

from apps.tenancy.context import get_active_membership
from apps.tenancy.localization import activate_tenant_localization


def tenant_member_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "authentication required"}, status=401)

        membership = get_active_membership(request)
        if membership is None:
            return JsonResponse(
                {"error": "active tenant membership is required"},
                status=403,
            )

        request.membership = membership
        request.active_tenant = membership.tenant
        request.tenant = membership.tenant
        with activate_tenant_localization(membership.tenant) as localization:
            request.tenant_locale = localization.locale
            request.tenant_currency = localization.currency
            request.tenant_timezone = localization.timezone_name
            return view_func(request, *args, **kwargs)

    return _wrapped


def tenant_roles_required(*allowed_roles):
    def decorator(view_func):
        @tenant_member_required
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if request.membership.role not in allowed_roles:
                return JsonResponse({"error": "insufficient role"}, status=403)
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
