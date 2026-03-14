from django.urls import include, path

urlpatterns = [
    path("app/", include("apps.web.urls")),
    path("auth/", include("apps.accounts.urls")),
    path("api/", include("apps.ops.urls")),
    path("api/growth/", include("apps.growth.urls")),
    path("api/portal/", include("apps.portal.urls")),
    path("", include("apps.core.urls")),
]
