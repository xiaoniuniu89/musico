from django.urls import path

from . import views

urlpatterns = [
    path("reports/summary/", views.report_summary_view, name="growth_report_summary"),
    path("messages/sms/send/", views.sms_send_view, name="growth_sms_send"),
    path("payroll/plans/", views.payroll_plans_view, name="growth_payroll_plans"),
    path(
        "payroll/plans/<int:plan_id>/",
        views.payroll_plan_detail_view,
        name="growth_payroll_plan_detail",
    ),
    path("payroll/periods/", views.payroll_periods_view, name="growth_payroll_periods"),
    path(
        "payroll/periods/<int:period_id>/",
        views.payroll_period_detail_view,
        name="growth_payroll_period_detail",
    ),
    path(
        "payroll/periods/<int:period_id>/finalize/",
        views.payroll_period_finalize_view,
        name="growth_payroll_period_finalize",
    ),
    path(
        "payroll/lines/<int:line_id>/payout/",
        views.payroll_line_payout_view,
        name="growth_payroll_line_payout",
    ),
    path("site/theme/", views.site_theme_view, name="growth_site_theme"),
    path("site/pages/", views.site_pages_view, name="growth_site_pages"),
    path("site/pages/<int:page_id>/", views.site_page_detail_view, name="growth_site_page_detail"),
    path("site/menu/", views.site_menu_view, name="growth_site_menu"),
    path("site/menu/<int:item_id>/", views.site_menu_detail_view, name="growth_site_menu_detail"),
    path("public/pages/<slug:slug>/", views.public_page_view, name="growth_public_page"),
]
