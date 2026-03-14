from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard_view, name="web_dashboard"),
    path("login/", views.login_view, name="web_login"),
    path("logout/", views.logout_view, name="web_logout"),
    path("switch-tenant/", views.switch_tenant_view, name="web_switch_tenant"),
    path("students/", views.students_view, name="web_students"),
    path("calendar/", views.calendar_view, name="web_calendar"),
    path("invoices/", views.invoices_view, name="web_invoices"),
    path("resources/", views.resources_view, name="web_resources"),
    path("messages/", views.messages_view, name="web_messages"),
    path("domains/", views.domains_view, name="web_domains"),
    path("portal/", views.portal_view, name="web_portal"),
]
