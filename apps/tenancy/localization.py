from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.utils import timezone, translation


@dataclass(frozen=True)
class TenantLocalization:
    locale: str
    currency: str
    timezone_name: str
    timezone_info: ZoneInfo


def _supported_locales() -> dict[str, str]:
    languages = getattr(settings, "LANGUAGES", ())
    if not languages:
        return {}
    return {str(code).lower(): str(code) for code, _ in languages}


def default_locale() -> str:
    return str(getattr(settings, "APP_DEFAULT_LOCALE", "en-us")).strip() or "en-us"


def default_currency() -> str:
    value = str(getattr(settings, "APP_DEFAULT_CURRENCY", "USD")).strip().upper()
    if len(value) == 3 and value.isalpha():
        return value
    return "USD"


def default_timezone_name() -> str:
    value = str(getattr(settings, "APP_DEFAULT_TIMEZONE", "UTC")).strip()
    return value or "UTC"


def normalize_locale_code(value: str | None) -> str:
    raw = (value or "").strip().replace("_", "-").lower()
    supported = _supported_locales()
    if not raw:
        raw = default_locale().replace("_", "-").lower()

    if raw in supported:
        return supported[raw]

    language_only = raw.split("-", 1)[0]
    if language_only in supported:
        return supported[language_only]

    return default_locale()


def normalize_currency_code(value: str | None) -> str:
    raw = (value or "").strip().upper()
    if len(raw) != 3 or not raw.isalpha():
        return default_currency()
    return raw


def normalize_timezone_name(value: str | None) -> str:
    candidate = (value or "").strip() or default_timezone_name()
    try:
        ZoneInfo(candidate)
        return candidate
    except ZoneInfoNotFoundError:
        fallback = default_timezone_name()
        try:
            ZoneInfo(fallback)
            return fallback
        except ZoneInfoNotFoundError:
            return "UTC"


def tenant_localization(tenant) -> TenantLocalization:
    locale = normalize_locale_code(getattr(tenant, "locale", None))
    currency = normalize_currency_code(getattr(tenant, "currency", None))
    timezone_name = normalize_timezone_name(getattr(tenant, "timezone", None))
    timezone_info = ZoneInfo(timezone_name)
    return TenantLocalization(
        locale=locale,
        currency=currency,
        timezone_name=timezone_name,
        timezone_info=timezone_info,
    )


@contextmanager
def activate_tenant_localization(tenant, membership=None):
    locale_ctx = tenant_localization(tenant)
    target_locale = locale_ctx.locale
    if membership and membership.preferred_language:
        target_locale = normalize_locale_code(membership.preferred_language)

    with timezone.override(locale_ctx.timezone_info), translation.override(target_locale):
        yield locale_ctx
