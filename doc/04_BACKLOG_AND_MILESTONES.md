# Backlog and Milestones

## Phase 0 - Foundation (1-2 weeks)

1. Repo scaffold, CI, env setup. (Done - `musico/` + `.github/workflows/musico-ci.yml`)
2. Tenant + domain + role schema. (Done - `apps/tenancy` models, admin, services, tests, migration)
3. Auth and permission guards. (Done - `apps/accounts` auth endpoints + tenancy decorators/tests)
4. Domain middleware and fallback subdomain routing. (Done - `TenantResolutionMiddleware` + host-aware guard behavior/tests)

Phase 0 status: Complete.

## Phase 1 - Core Ops MVP (3-5 weeks)

1. Students/Families CRUD. (Done - `/api/families`, `/api/students`, contacts)
2. Calendar with recurrence + attendance states. (Done - `/api/events`, `/api/events/{id}/attendance`)
3. Invoice creation and Stripe payment. (Done - `/api/invoices`, pay-link + payment confirm)
4. Basic messaging/reminders by email. (Done - `/api/messages`, reminders endpoint + `send_reminders` command)
5. Resource upload and assignment. (Done - `/api/resources`, `/api/resources/{id}/assign`)

Phase 1 status: Complete.

## Phase 2 - Production readiness (2-3 weeks)

1. Audit logs. (Done - `AuditLog` model + write middleware + `/api/audit-logs/`)
2. Domain verification + SSL automation. (Done - domain token flow + verify/activate endpoints + `process_domains`)
3. Scheduler hardening (retries/monitoring). (Done - retry fields, `SchedulerJobRun`, run stats endpoints)
4. Role-based UX polish for mobile and desktop. (Done - `/api/dashboard/summary/` role/viewport-aware payload)

Phase 2 status: Complete.

## Phase 3 - Growth (later)

1. Advanced reporting. (Done - `/api/growth/reports/summary/`)
2. Optional SMS channel. (Done - `/api/growth/messages/sms/send/` + `SMS_PROVIDER` support)
3. Teacher payroll depth. (Done - payroll plans/periods/lines/payout APIs)
4. Website builder and richer public-site tooling. (Done - theme/pages/menu APIs + public page endpoint)

Phase 3 status: Complete.

## Phase 4 - Portal Experience (new)

1. Parent/student scoped portal access model. (Done - `PortalAccessLink` + admin APIs)
2. Mobile-first portal endpoints for daily tasks. (Done - overview/calendar/invoices/resources APIs)
3. Staff-managed access link lifecycle. (Done - list/create/update/delete access links)
4. Tenant-safe portal data filtering by linked family/student scope. (Done - service-level scope resolution + tests)

Phase 4 status: Complete.
