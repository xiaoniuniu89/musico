from django.urls import path

from . import views

urlpatterns = [
    path("access-links/", views.access_links_view, name="portal_access_links"),
    path(
        "access-links/<int:link_id>/",
        views.access_link_detail_view,
        name="portal_access_link_detail",
    ),
    path("me/overview/", views.portal_overview_view, name="portal_overview"),
    path("me/calendar/", views.portal_calendar_view, name="portal_calendar"),
    path("me/invoices/", views.portal_invoices_view, name="portal_invoices"),
    path("me/resources/", views.portal_resources_view, name="portal_resources"),
]
