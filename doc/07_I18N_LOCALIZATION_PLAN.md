# I18N + Localization Plan (Phase Seed)

## What Is Implemented Now
- Tenant-level defaults:
  - `tenant.locale` (for language/formatting)
  - `tenant.currency` (ISO code)
  - `tenant.timezone` (IANA timezone)
- Tenant-aware runtime activation in web + API request guards:
  - `timezone.override(...)`
  - `translation.override(...)`
- Locale-aware money formatting:
  - no hardcoded `$`
  - rendered as `CURRENCY_CODE localized_number`
- Studio Preferences UI (owner/admin):
  - update locale, currency, timezone in `/app/domains/`
- Invoice creation defaults to tenant currency (or explicit payload currency)

## Current Constraints
- Text labels are still English-only (no translation catalogs yet).
- Currency rendering is code-first (`EUR 123.45`), not symbol-placement aware by locale.
- Locale choices are from configured `settings.LANGUAGES`.
- Timezone choices are currently curated (not full timezone DB list in UI).

## Next Planning Phases

### Phase A: Translation Infrastructure
- Mark user-facing template strings with `{% trans %}` / `{% blocktrans %}`.
- Mark Python messages with `gettext_lazy` / `gettext`.
- Add locale catalogs under `locale/` and workflow for `makemessages` + `compilemessages`.
- Add CI check to prevent untranslated new strings in key flows.

### Phase B: Locale + Currency UX
- Add account-level language override (optional), with tenant default fallback.
- Add full timezone picker with search.
- Add currency precision map (JPY=0 decimals, KWD=3 decimals) and per-currency minor unit behavior.
- Support localized money display styles (symbol position, spacing, separators).

### Phase C: Data and API Contracts
- Include `locale`, `currency`, `timezone` metadata in all major API responses.
- Validate and normalize incoming currency/locale consistently in serializers/views.
- Ensure exports (CSV/PDF/email) format dates/numbers per tenant or user preference.

### Phase D: Regional Features
- Tax/VAT/GST profiles per region.
- Localized invoice templates and legal text by country.
- Region-aware payment providers and payout settings.

## Open Product Questions
- Should parent/teacher language be per-user or tenant-global by default?
- Should invoice currency be tenant-locked or family-specific?
- Do we need multi-currency reporting in one tenant (FX-aware dashboards)?
- Which launch regions are first (defines required languages, tax, and payment rails)?
