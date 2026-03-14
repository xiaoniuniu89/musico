from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.shortcuts import render

from apps.tenancy.context import get_active_membership
from apps.tenancy.localization import activate_tenant_localization


def web_tenant_member_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(next=request.get_full_path(), login_url="/app/login/")

        membership = get_active_membership(request)
        if membership is None:
            return render(request, "web/no_access.html", status=403)

        request.membership = membership
        request.tenant = membership.tenant
        with activate_tenant_localization(membership.tenant, membership=membership) as localization:
            request.tenant_locale = localization.locale
            request.tenant_currency = localization.currency
            request.tenant_timezone = localization.timezone_name
            return view_func(request, *args, **kwargs)

    return _wrapped


def web_roles_required(*allowed_roles):
    def _decorator(view_func):
        @web_tenant_member_required
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if request.membership.role not in allowed_roles:
                return render(request, "web/forbidden.html", status=403)
            return view_func(request, *args, **kwargs)

        return _wrapped

    return _decorator
