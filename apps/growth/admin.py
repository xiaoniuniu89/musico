from django.contrib import admin

from .models import (
    PayrollLine,
    PayrollPayout,
    PayrollPeriod,
    SiteMenuItem,
    SitePage,
    SiteTheme,
    TeacherCompPlan,
)

admin.site.register(TeacherCompPlan)
admin.site.register(PayrollPeriod)
admin.site.register(PayrollLine)
admin.site.register(PayrollPayout)
admin.site.register(SiteTheme)
admin.site.register(SitePage)
admin.site.register(SiteMenuItem)
