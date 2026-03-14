from __future__ import annotations

from apps.tenancy.models import AuditLog


def _client_ip(request) -> str:
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def log_audit_event(
    *,
    action: str,
    request=None,
    tenant=None,
    user=None,
    object_type: str = "",
    object_id: str = "",
    status: str = AuditLog.Status.SUCCESS,
    metadata: dict | None = None,
) -> AuditLog:
    request_method = ""
    request_path = ""
    ip_address = ""
    user_agent = ""

    if request is not None:
        request_method = request.method
        request_path = request.path
        ip_address = _client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:255]

    if tenant is None and request is not None:
        tenant = getattr(request, "tenant", None) or getattr(request, "resolved_tenant", None)

    if user is None and request is not None and getattr(request, "user", None) is not None:
        if request.user.is_authenticated:
            user = request.user

    return AuditLog.objects.create(
        tenant=tenant,
        user=user,
        action=action,
        object_type=object_type,
        object_id=object_id,
        status=status,
        method=request_method,
        path=request_path,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata=metadata or {},
    )
