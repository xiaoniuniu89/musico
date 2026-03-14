from django.contrib import admin

from .models import AuditLog, Domain, Membership, Tenant


class DomainInline(admin.TabularInline):
    model = Domain
    extra = 0


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ["user", "invited_by"]


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ["id", "slug", "name", "status", "timezone", "created_at"]
    list_filter = ["status", "timezone"]
    search_fields = ["slug", "name"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [DomainInline, MembershipInline]


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "tenant",
        "host",
        "domain_type",
        "is_primary",
        "verification_status",
        "ssl_status",
    ]
    list_filter = ["domain_type", "is_primary", "verification_status", "ssl_status"]
    search_fields = ["host", "tenant__slug", "tenant__name"]
    readonly_fields = [
        "created_at",
        "updated_at",
        "verified_at",
        "last_checked_at",
        "ssl_provisioned_at",
    ]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "tenant", "role", "status", "is_default", "joined_at"]
    list_filter = ["role", "status", "is_default"]
    search_fields = ["user__email", "tenant__slug", "tenant__name"]
    readonly_fields = ["created_at", "updated_at", "joined_at"]
    autocomplete_fields = ["user", "tenant", "invited_by"]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["id", "tenant", "user", "action", "status", "method", "path", "created_at"]
    list_filter = ["status", "method", "action"]
    search_fields = ["action", "path", "user__email", "tenant__slug"]
    readonly_fields = [
        "tenant",
        "user",
        "action",
        "object_type",
        "object_id",
        "status",
        "method",
        "path",
        "ip_address",
        "user_agent",
        "metadata",
        "created_at",
    ]
