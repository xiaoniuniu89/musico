from django.contrib import admin

from .models import (
    Event,
    EventAttendance,
    Family,
    FamilyContact,
    Invoice,
    InvoiceItem,
    MessageLog,
    Payment,
    Resource,
    ResourceAssignment,
    SchedulerJobRun,
    Student,
)


@admin.register(Family)
class FamilyAdmin(admin.ModelAdmin):
    list_display = ["id", "tenant", "name", "email", "is_archived"]
    list_filter = ["is_archived"]
    search_fields = ["name", "email"]


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ["id", "tenant", "first_name", "last_name", "family", "is_archived"]
    list_filter = ["is_archived"]
    search_fields = ["first_name", "last_name", "family__name"]


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["id", "tenant", "title", "event_type", "start_at", "status"]
    list_filter = ["event_type", "status"]
    search_fields = ["title"]


admin.site.register(FamilyContact)
admin.site.register(EventAttendance)
admin.site.register(Invoice)
admin.site.register(InvoiceItem)
admin.site.register(Payment)
admin.site.register(MessageLog)
admin.site.register(Resource)
admin.site.register(ResourceAssignment)
admin.site.register(SchedulerJobRun)
