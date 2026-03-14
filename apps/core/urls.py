from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="landing_page"),
    path("contact/", views.contact_view, name="contact"),
    path("signup/", views.signup_view, name="signup"),
    path("healthz/", views.healthz, name="healthz"),
    path("tenant-context/", views.tenant_context, name="tenant_context"),
    path("me/", views.me, name="me"),
    path("admin/ping/", views.admin_ping, name="admin_ping"),
]
