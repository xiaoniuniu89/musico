# Session Handoff

Last updated: 2026-03-07

## Confirmed decisions

1. Build the teacher/school app first; postpone the musician app.
2. Mobile-first UX is required.
3. Keep admin-heavy pages desktop-oriented.
4. Multi-tenant from day one.
5. Support custom domains in future; keep tenant subdomain fallback.
6. Django-first architecture is preferred for backend-heavy scope.

## Domain model agreed

1. Default tenant URL: `fake-school.musicoteach.com` (or equivalent).
2. Later custom domain:
- Common split setup: `app.fake-school.com` points to platform.
- Full-domain setup: `fake-school.com` can point to platform if customer wants.
3. Important: DNS routes by host, not by URL path.

## Redis / scheduler clarity from discussion

1. Scheduler is required early (reminders, recurring invoices, overdue jobs).
2. Redis is useful for queueing, retries, rate limits, locks, short cache.
3. Redis is optional at MVP; can start with Postgres + cron + management commands.

## Immediate next build steps

1. Finalize brand/domain choice.
2. Scaffold Django monolith with tenant + domain middleware.
3. Implement auth + role model.
4. Build v1 modules in order:
- Students/Families
- Calendar
- Invoices/Payments
- Messaging/Reminders
- Resource sharing (PDF/files)
