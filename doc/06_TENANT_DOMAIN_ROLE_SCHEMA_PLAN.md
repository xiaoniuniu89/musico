# Tenant, Domain, Role Schema

Detailed specification and delivery plan for Backlog Phase 0, Step 2.

## 1. Objective

Build the core multi-tenant identity layer so one platform can safely host many schools and let one user belong to multiple schools with different roles.

This step must enable:

1. Tenant records (`school/account` level).
2. Domain mapping (`host -> tenant`).
3. Membership-based roles (`user + tenant + role`).

## 2. Scope

In scope for this step:

1. Django app for tenancy models.
2. Database schema + constraints + indexes.
3. Django admin registration.
4. Service methods for tenant/domain/membership creation.
5. Management command for local/staging tenant bootstrap.
6. Model/service tests for core invariants.

Out of scope for this step:

1. DNS TXT verification and SSL automation (Phase 2).
2. Full auth flows and UI guards (Phase 0 Step 3).
3. Request host middleware resolution (Phase 0 Step 4).
4. Billing/plans/paywall behavior.

## 3. Proposed Django App Layout

Create new app: `apps/tenancy`

Suggested files:

1. `apps/tenancy/apps.py`
2. `apps/tenancy/models.py`
3. `apps/tenancy/admin.py`
4. `apps/tenancy/services.py`
5. `apps/tenancy/validators.py`
6. `apps/tenancy/tests/test_models.py`
7. `apps/tenancy/tests/test_services.py`
8. `apps/tenancy/management/commands/create_tenant.py`

## 4. Data Model Specification

Use `settings.AUTH_USER_MODEL` for user relation (currently Django default user).

### 4.1 Tenant

Model: `Tenant`

Fields:

1. `id` (`BigAutoField`, PK).
2. `slug` (`SlugField`, unique, max 63, lowercase).
3. `name` (`CharField`, max 160).
4. `status` (`CharField`, choices: `active`, `suspended`, `archived`; default `active`).
5. `timezone` (`CharField`, max 64, default `UTC`).
6. `created_at` (`DateTimeField`, auto_now_add).
7. `updated_at` (`DateTimeField`, auto_now).

Indexes/constraints:

1. Unique: `slug`.
2. Optional index on `status`.

### 4.2 Domain

Model: `Domain`

Fields:

1. `id` (`BigAutoField`, PK).
2. `tenant` (`ForeignKey(Tenant, on_delete=CASCADE, related_name=\"domains\")`).
3. `host` (`CharField`, max 255, unique, stored lowercase).
4. `domain_type` (`CharField`, choices: `platform_subdomain`, `custom_domain`).
5. `is_primary` (`BooleanField`, default `False`).
6. `verification_status` (`CharField`, choices: `not_required`, `pending`, `verified`, `failed`; default `not_required`).
7. `verification_token` (`CharField`, max 64, nullable/blank, unique when present).
8. `verified_at` (`DateTimeField`, nullable/blank).
9. `ssl_status` (`CharField`, choices: `unmanaged`, `pending`, `active`, `error`; default `unmanaged`).
10. `last_checked_at` (`DateTimeField`, nullable/blank).
11. `created_at` (`DateTimeField`, auto_now_add).
12. `updated_at` (`DateTimeField`, auto_now).

Indexes/constraints:

1. Unique: `host`.
2. Partial unique per tenant for primary domain:
   `UniqueConstraint(fields=[\"tenant\"], condition=Q(is_primary=True), name=\"uniq_primary_domain_per_tenant\")`.
3. Index: `tenant`, `verification_status`.
4. Validation: normalize host to lowercase and disallow scheme/path.

### 4.3 Membership

Model: `Membership`

Fields:

1. `id` (`BigAutoField`, PK).
2. `user` (`ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE, related_name=\"memberships\")`).
3. `tenant` (`ForeignKey(Tenant, on_delete=CASCADE, related_name=\"memberships\")`).
4. `role` (`CharField`, choices: `owner`, `admin`, `teacher`, `staff`, `parent`, `student`).
5. `status` (`CharField`, choices: `invited`, `active`, `suspended`, `revoked`; default `active`).
6. `is_default` (`BooleanField`, default `False`).
7. `invited_by` (`ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=SET_NULL, related_name=\"issued_membership_invites\")`).
8. `joined_at` (`DateTimeField`, null=True, blank=True).
9. `created_at` (`DateTimeField`, auto_now_add).
10. `updated_at` (`DateTimeField`, auto_now).

Indexes/constraints:

1. Unique together: `user + tenant`.
2. Partial unique default tenant per user:
   `UniqueConstraint(fields=[\"user\"], condition=Q(is_default=True), name=\"uniq_default_tenant_per_user\")`.
3. Index: `tenant + role + status`.

## 5. Business Rules

1. A tenant can have many domains, but exactly one primary domain.
2. `host` is globally unique.
3. On tenant creation, create platform domain:
   `<tenant.slug>.<APP_PORTAL_BASE_DOMAIN>`.
4. Platform domain starts as verified/not required for DNS checks.
5. On tenant creation, owner membership is created for the supplied user.
6. Every tenant must have at least one active owner.
7. Prevent removal/revocation of the final active owner.
8. User may belong to many tenants and have different roles per tenant.

## 6. Environment Variables (Step 2)

1. `APP_PORTAL_BASE_DOMAIN` (example: `teach.musico.com`).
2. `APP_DEFAULT_TIMEZONE` (default `UTC`).

## 7. Service Layer Contract

Implement `apps.tenancy.services`:

1. `create_tenant_with_owner(name, slug, owner_user, timezone=\"UTC\") -> Tenant`
2. `add_domain(tenant, host, domain_type, is_primary=False) -> Domain`
3. `set_primary_domain(tenant, domain) -> None`
4. `add_membership(user, tenant, role, status=\"active\", is_default=False) -> Membership`
5. `assert_tenant_has_owner(tenant) -> None`

Implementation details:

1. Wrap writes in DB transactions.
2. Use `select_for_update` when reassigning primary domain.
3. Normalize host before save.
4. Raise domain-specific exceptions for duplicate/invalid values.

## 8. Admin UI Requirements

Register `Tenant`, `Domain`, `Membership` in Django admin with:

1. Search fields:
   `Tenant.slug`, `Tenant.name`, `Domain.host`, `Membership.user__email`.
2. List filters:
   statuses, role, domain type, primary flag.
3. Read-only timestamps.
4. Inline domains and memberships on tenant admin page.

## 9. Migration Plan

1. Create app `apps.tenancy` and add to `INSTALLED_APPS`.
2. Migration `0001_initial` for models + constraints.
3. No destructive migration in this step.
4. Run migration checks in CI (`makemigrations --check --dry-run` already configured).

## 10. Test Plan

Required automated tests:

1. `Tenant.slug` unique and lowercase behavior.
2. `Domain.host` normalization and uniqueness.
3. Single primary domain constraint per tenant.
4. Membership unique (`user`, `tenant`) constraint.
5. Single default membership constraint per user.
6. Service creates tenant + platform domain + owner membership atomically.
7. Service blocks deletion/revocation of final active owner.

## 11. Delivery Plan (Execution Order)

Estimated effort: 1.5 to 3 working days.

1. Day 1, part 1:
   create `apps.tenancy`, model enums/constants, model classes, validators.
2. Day 1, part 2:
   generate migration, wire admin pages, add service layer skeleton.
3. Day 2, part 1:
   implement tenant/domain/membership services and transaction safety.
4. Day 2, part 2:
   add tests for models/services and pass lint/test/migration checks.
5. Day 3 (buffer):
   refine indexes, naming, docs, and add command `create_tenant`.

## 12. Acceptance Criteria

Step is done when all are true:

1. Schema exists and migrates cleanly.
2. Admin can create tenant, map domain, assign memberships.
3. Core invariants are enforced by DB constraints and tests.
4. `create_tenant` command can seed a tenant in dev/staging.
5. CI passes lint, checks, and tests.

## 13. Open Decisions

1. Role list freeze for MVP:
   include `parent/student` now, or add later with migrations?
2. Keep Django default user long-term, or switch to custom user before production?
3. Should tenant slug be immutable after creation?
4. Should custom domains require `app.` prefix policy, or allow root/apex?
