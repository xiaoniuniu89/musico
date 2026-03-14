# Musico Teach - App Bootstrap

This is the Phase 0 Step 1 app provisioning scaffold.

## Stack

- Django 5
- PostgreSQL (default through `DATABASE_URL`)
- Django templates + Tailwind-compatible structure

## Quickstart

1. Create environment file:

```bash
cp .env.example .env
```

2. Start local Postgres (optional, if not using your own):

```bash
docker compose up -d db
```

3. Install dependencies and run migrations:

```bash
make setup
make migrate
```

4. Start server:

```bash
make run
```

## Project layout

- `apps/` Django apps
- `config/` Django settings and URL config
- `requirements/` dependency files
- `doc/` product/tech specs and discovery snapshots

## Local endpoints

- `GET /healthz/` -> basic health JSON
- `GET /` -> bootstrap landing response
- `POST /auth/login/` -> session login (`identifier`, `password`)
- `POST /auth/logout/` -> session logout
- `GET /auth/session/` -> current auth + active tenant payload
- `POST /auth/switch-tenant/` -> switch active tenant (`tenant_slug`)
- `GET /tenant-context/` -> resolved tenant by request host (domain/fallback source)
- `GET /me/` -> tenant-member protected identity payload
- `GET /admin/ping/` -> owner/admin-only guard test endpoint
- `GET/POST /api/families/`, `GET/PATCH/DELETE /api/families/{id}/`, `POST /api/families/{id}/contacts/`
- `GET/POST /api/students/`, `GET/PATCH/DELETE /api/students/{id}/`
- `GET/POST /api/events/`, `GET/PATCH/DELETE /api/events/{id}/`, `POST /api/events/{id}/attendance/`
- `GET/POST /api/invoices/`, `GET/PATCH /api/invoices/{id}/`, `POST /api/invoices/{id}/send/`
- `POST /api/invoices/{id}/pay-link/`, `POST /api/payments/{id}/confirm/`
- `GET /api/messages/`, `POST /api/messages/send/`, `POST /api/messages/reminders/run/`
- `GET /api/domains/`, `POST /api/domains/`, `POST /api/domains/{id}/verify/`, `POST /api/domains/{id}/set-primary/`
- `GET /api/audit-logs/`
- `GET /api/scheduler/runs/`, `GET /api/scheduler/runs/{id}/`
- `GET /api/dashboard/summary/?viewport=mobile|desktop`
- `GET/POST /api/resources/`, `GET/PATCH/DELETE /api/resources/{id}/`, `POST /api/resources/{id}/assign/`
- `GET /api/resource-assignments/`
- `GET /api/growth/reports/summary/`
- `POST /api/growth/messages/sms/send/` (optional, controlled by `SMS_PROVIDER`)
- `GET/POST /api/growth/payroll/plans/`, `PATCH /api/growth/payroll/plans/{id}/`
- `GET/POST /api/growth/payroll/periods/`, `GET /api/growth/payroll/periods/{id}/`
- `POST /api/growth/payroll/periods/{id}/finalize/`, `POST /api/growth/payroll/lines/{id}/payout/`
- `GET/PATCH /api/growth/site/theme/`
- `GET/POST /api/growth/site/pages/`, `GET/PATCH/DELETE /api/growth/site/pages/{id}/`
- `GET/POST /api/growth/site/menu/`, `PATCH/DELETE /api/growth/site/menu/{id}/`
- `GET /api/growth/public/pages/{slug}/` (host-resolved tenant or `?tenant_slug=...`)
- `GET/POST /api/portal/access-links/`, `PATCH/DELETE /api/portal/access-links/{id}/`
- `GET /api/portal/me/overview/`
- `GET /api/portal/me/calendar/`
- `GET /api/portal/me/invoices/`
- `GET /api/portal/me/resources/`

## Reminder Job

```bash
python manage.py send_reminders --hours-ahead 24
```

## Domain Job

```bash
python manage.py process_domains
```

## SMS Config

```bash
SMS_PROVIDER=disabled  # or console
```

## CI

GitHub Actions workflow: `.github/workflows/musico-ci.yml`
# musico
