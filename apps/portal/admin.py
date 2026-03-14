from django.contrib import admin

from .models import PortalAccessLink


@admin.register(PortalAccessLink)
class PortalAccessLinkAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "tenant",
        "user",
        "family",
        "student",
        "can_view_billing",
        "can_view_resources",
        "is_active",
    ]
    list_filter = ["can_view_billing", "can_view_resources", "is_active"]
    search_fields = [
        "user__email",
        "tenant__slug",
        "family__name",
        "student__first_name",
        "student__last_name",
    ]
