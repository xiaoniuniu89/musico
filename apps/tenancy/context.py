from apps.tenancy.models import Membership

SESSION_ACTIVE_TENANT_ID = "active_tenant_id"


def get_active_membership(request):
    if not request.user.is_authenticated:
        return None

    base_qs = Membership.objects.select_related("tenant").filter(
        user=request.user,
        status=Membership.Status.ACTIVE,
    )

    resolved_tenant = getattr(request, "resolved_tenant", None)
    if resolved_tenant is not None:
        membership = base_qs.filter(tenant_id=resolved_tenant.id).first()
        if membership is None:
            return None

        request.session[SESSION_ACTIVE_TENANT_ID] = membership.tenant_id
        return membership

    tenant_id = request.session.get(SESSION_ACTIVE_TENANT_ID)
    membership = None
    if tenant_id:
        membership = base_qs.filter(tenant_id=tenant_id).first()

    if membership is None:
        membership = base_qs.order_by("-is_default", "id").first()
        if membership is not None:
            request.session[SESSION_ACTIVE_TENANT_ID] = membership.tenant_id

    return membership


def switch_active_tenant_by_slug(*, request, user, tenant_slug: str):
    membership = (
        Membership.objects.select_related("tenant")
        .filter(
            user=user,
            tenant__slug=tenant_slug,
            status=Membership.Status.ACTIVE,
        )
        .first()
    )
    if membership is None:
        return None

    request.session[SESSION_ACTIVE_TENANT_ID] = membership.tenant_id
    return membership


def get_session_payload(request):
    if not request.user.is_authenticated:
        return {
            "authenticated": False,
            "user": None,
            "active_tenant": None,
            "role": None,
        }

    membership = get_active_membership(request)
    active_tenant = None
    role = None
    if membership is not None:
        active_tenant = {
            "id": membership.tenant.id,
            "slug": membership.tenant.slug,
            "name": membership.tenant.name,
            "locale": membership.tenant.locale,
            "currency": membership.tenant.currency,
            "timezone": membership.tenant.timezone,
        }
        role = membership.role

    return {
        "authenticated": True,
        "user": {
            "id": request.user.id,
            "email": request.user.email,
            "username": request.user.get_username(),
        },
        "active_tenant": active_tenant,
        "role": role,
    }
