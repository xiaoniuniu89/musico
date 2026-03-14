# Technical Spec (Django-first)

## Architecture

1. App style: modular Django monolith.
2. Backend: Django 5 + DRF or Django Ninja.
3. DB: PostgreSQL.
4. File storage: S3/R2.
5. Frontend: Django templates + Tailwind (+ HTMX/Alpine where useful).
6. Payments: Stripe.
7. Email: Postmark or Resend.
8. Monitoring: Sentry.

## Multi-tenant model

### Tenant resolution

1. Domain middleware reads incoming `Host`.
2. Maps host to `tenant_id` via `domains` table.
3. Injects active tenant context into request.
4. If no explicit domain match and host is `<slug>.<APP_PORTAL_BASE_DOMAIN>`, fallback to `Tenant.slug`.

### Core tables (minimum)

1. `tenants`
2. `domains` (`tenant_id`, `host`, `verified_at`, `is_primary`, `status`)
3. `users`
4. `memberships` (`user_id`, `tenant_id`, `role`)
5. `students`
6. `families`
7. `events`
8. `invoices`
9. `invoice_items`
10. `payments`
11. `messages`
12. `resources`
13. `resource_assignments`

## Domain onboarding flow

1. Customer enters domain (for example `app.fake-school.com`).
2. Platform generates TXT verification token.
3. Customer adds DNS records.
4. Platform verifies DNS and issues SSL.
5. Domain marked active and mapped to tenant.
6. Automation surfaces status in API (`pending`, `verified`, `failed`; SSL `pending`, `active`, `error`).

## Auth and permissions

1. Email/password auth, optional MFA.
2. Session or JWT with tenant context.
3. Every data query filtered by tenant + role policy.

## Jobs and scheduling

### MVP option (simpler)

1. Use cron/platform scheduler + Django management commands.
2. Persist run logs in Postgres.
3. Track retries and next-attempt timestamps per message.
4. Persist job run metrics (`queued`, `processed`, `sent`, `failed`, `retry_scheduled`).

### Scale option

1. Add Redis + Celery + Celery Beat.
2. Use Redis for queues, retries, locks, rate limits.
3. Keep business truth in Postgres.

## Security essentials

1. Tenant isolation tests (must-have).
2. CSRF protection on forms.
3. Secret management via environment variables.
4. File upload scanning/type checks.
5. Audit logs for admin actions.
6. Request-level audit middleware for mutating actions with tenant/user/path metadata.

## Deployment

1. Environments: dev, staging, prod.
2. CI: lint + tests + migration checks.
3. CD: automated deploy on main branch with rollback.
4. Managed Postgres backups and restore drills.

## Growth features

1. Reporting endpoint for rolling-window studio KPIs.
2. Optional SMS delivery channel controlled by `SMS_PROVIDER`.
3. Teacher payroll plans + computed payroll periods + payout records.
4. Tenant website builder primitives (theme/pages/menu) and public page rendering.

## Portal features

1. Parent/student portal access links map users to family/student scope.
2. Scoped portal APIs provide mobile-first overview/calendar/invoices/resources payloads.
3. Staff roles manage access links; data visibility enforced by scope resolver.
