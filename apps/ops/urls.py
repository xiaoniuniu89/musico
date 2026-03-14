from django.urls import path

from . import views

urlpatterns = [
    path("dashboard/summary/", views.dashboard_summary_view, name="dashboard_summary"),
    path("families/", views.families_view, name="families"),
    path("families/<int:family_id>/", views.family_detail_view, name="family_detail"),
    path("families/<int:family_id>/contacts/", views.family_contacts_view, name="family_contacts"),
    path("students/", views.students_view, name="students"),
    path("students/<int:student_id>/", views.student_detail_view, name="student_detail"),
    path("events/", views.events_view, name="events"),
    path("events/<int:event_id>/", views.event_detail_view, name="event_detail"),
    path("events/<int:event_id>/attendance/", views.event_attendance_view, name="event_attendance"),
    path("invoices/", views.invoices_view, name="invoices"),
    path("invoices/<int:invoice_id>/", views.invoice_detail_view, name="invoice_detail"),
    path("invoices/<int:invoice_id>/send/", views.invoice_send_view, name="invoice_send"),
    path(
        "invoices/<int:invoice_id>/pay-link/", views.invoice_pay_link_view, name="invoice_pay_link"
    ),
    path("payments/<int:payment_id>/confirm/", views.payment_confirm_view, name="payment_confirm"),
    path("messages/", views.messages_view, name="messages"),
    path("messages/send/", views.messages_send_view, name="messages_send"),
    path(
        "messages/reminders/run/", views.messages_run_reminders_view, name="messages_run_reminders"
    ),
    path("domains/", views.domains_view, name="domains"),
    path("domains/<int:domain_id>/", views.domain_detail_view, name="domain_detail"),
    path("domains/<int:domain_id>/verify/", views.domain_verify_view, name="domain_verify"),
    path(
        "domains/<int:domain_id>/set-primary/",
        views.domain_set_primary_view,
        name="domain_set_primary",
    ),
    path("audit-logs/", views.audit_logs_view, name="audit_logs"),
    path("scheduler/runs/", views.scheduler_runs_view, name="scheduler_runs"),
    path(
        "scheduler/runs/<int:run_id>/",
        views.scheduler_run_detail_view,
        name="scheduler_run_detail",
    ),
    path("resources/", views.resources_view, name="resources"),
    path("resources/<int:resource_id>/", views.resource_detail_view, name="resource_detail"),
    path("resources/<int:resource_id>/assign/", views.resource_assign_view, name="resource_assign"),
    path("resource-assignments/", views.resource_assignments_view, name="resource_assignments"),
]
