from django.conf import settings

from apps.tenancy.audit import log_audit_event
from apps.tenancy.models import AuditLog, Domain, Tenant
from apps.tenancy.validators import normalize_host


def _parse_request_host(request) -> str | None:
    try:
        raw_host = request.get_host()
    except Exception:
        return None

    host = normalize_host(raw_host)
    if not host:
        return None

    if ":" in host:
        host = host.split(":", 1)[0]

    return host or None


def _resolve_tenant_by_domain(host: str):
    domain = (
        Domain.objects.select_related("tenant")
        .filter(host=host, tenant__status=Tenant.Status.ACTIVE)
        .first()
    )
    if domain is None:
        return None, None, "none"
    return domain.tenant, domain, "domain"


def _resolve_tenant_by_subdomain_fallback(host: str):
    base_domain = settings.APP_PORTAL_BASE_DOMAIN.strip().lower()
    if not base_domain or host == base_domain:
        return None, "none"

    suffix = f".{base_domain}"
    if not host.endswith(suffix):
        return None, "none"

    subdomain = host[: -len(suffix)]
    if not subdomain or "." in subdomain:
        return None, "none"

    tenant = Tenant.objects.filter(slug=subdomain, status=Tenant.Status.ACTIVE).first()
    if tenant is None:
        return None, "none"

    return tenant, "fallback_subdomain"


class TenantResolutionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_host = _parse_request_host(request)
        request.request_host = request_host
        request.resolved_tenant = None
        request.resolved_domain = None
        request.tenant_resolution_source = "none"

        if request_host:
            tenant, domain, source = _resolve_tenant_by_domain(request_host)

            if tenant is None and settings.APP_ENABLE_SUBDOMAIN_FALLBACK:
                tenant, source = _resolve_tenant_by_subdomain_fallback(request_host)
                domain = None

            request.resolved_tenant = tenant
            request.resolved_domain = domain
            request.tenant_resolution_source = source

        response = self.get_response(request)
        return response


class AuditLogMiddleware:
    MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
    EXCLUDED_PREFIXES = ("/static/", "/favicon.ico")

    def __init__(self, get_response):
        self.get_response = get_response

    def _should_skip(self, request) -> bool:
        if request.method not in self.MUTATING_METHODS:
            return True
        path = request.path or ""
        return any(path.startswith(prefix) for prefix in self.EXCLUDED_PREFIXES)

    def __call__(self, request):
        if self._should_skip(request):
            return self.get_response(request)

        # Attempt to extract object_id if it's a detail endpoint (e.g. /api/students/123/)
        path_parts = [p for p in request.path.split("/") if p]
        object_id = ""
        object_type = "endpoint"
        if path_parts:
            last_part = path_parts[-1]
            if last_part.isdigit():
                object_id = last_part
                if len(path_parts) >= 2:
                    object_type = path_parts[-2]

        try:
            response = self.get_response(request)
            status = (
                AuditLog.Status.SUCCESS
                if getattr(response, "status_code", 500) < 400
                else AuditLog.Status.FAILURE
            )
            metadata = {
                "status_code": getattr(response, "status_code", None),
                "tenant_resolution_source": getattr(request, "tenant_resolution_source", "none"),
                "path": request.path,
            }
        except Exception as exc:
            response = None
            status = AuditLog.Status.FAILURE
            metadata = {
                "status_code": 500,
                "error": str(exc),
                "tenant_resolution_source": getattr(request, "tenant_resolution_source", "none"),
                "path": request.path,
            }
            self._safe_log(
                request=request, status=status, metadata=metadata,
                object_id=object_id, object_type=object_type
            )
            raise

        self._safe_log(
            request=request, status=status, metadata=metadata,
            object_id=object_id, object_type=object_type
        )
        return response

    def _safe_log(self, *, request, status: str, metadata: dict, object_id: str = "", object_type: str = "endpoint"):
        try:
            log_audit_event(
                action=f"http.{request.method.lower()}",
                request=request,
                object_type=object_type or "endpoint",
                object_id=object_id,
                status=status,
                metadata=metadata,
            )
        except Exception:
            # Audit writes must not break application request flow.
            return
