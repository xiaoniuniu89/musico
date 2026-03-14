from django.urls import path

from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("session/", views.session_view, name="session"),
    path("switch-tenant/", views.switch_tenant_view, name="switch_tenant"),
]
