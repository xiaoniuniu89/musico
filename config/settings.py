import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-secret-key")
DEBUG = os.getenv("DJANGO_DEBUG", "True").lower() in {"1", "true", "yes"}

allowed_hosts = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,.localtest.me")
ALLOWED_HOSTS = [h.strip() for h in allowed_hosts.split(",") if h.strip()]

csrf_origins = os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = [o.strip() for o in csrf_origins.split(",") if o.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.accounts",
    "apps.core",
    "apps.growth",
    "apps.ops",
    "apps.portal",
    "apps.tenancy",
    "apps.web",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "apps.tenancy.middleware.TenantResolutionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.tenancy.middleware.AuditLogMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

default_db = f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
if os.path.exists("/data"):
    default_db = "sqlite:////data/db.sqlite3"

database_url = os.getenv("DATABASE_URL", default_db)

# Handle Fly.io/Postgres scheme mismatch for psycopg3
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

DATABASES = {
    "default": dj_database_url.config(
        default=database_url,
        conn_max_age=600,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = os.getenv("DJANGO_LANGUAGE_CODE", "en-us")
LANGUAGES = [
    ("en-us", "English (US)"),
    ("en-gb", "English (UK)"),
    ("fr", "French"),
    ("de", "German"),
    ("es", "Spanish"),
    ("it", "Italian"),
    ("pt-br", "Portuguese (Brazil)"),
]
TIME_ZONE = os.getenv("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True
LOCALE_PATHS = [BASE_DIR / "locale"]

APP_PORTAL_BASE_DOMAIN = os.getenv("APP_PORTAL_BASE_DOMAIN", "teach.localtest.me")
APP_DEFAULT_TIMEZONE = os.getenv("APP_DEFAULT_TIMEZONE", "UTC")
APP_DEFAULT_LOCALE = os.getenv("APP_DEFAULT_LOCALE", LANGUAGE_CODE)
APP_DEFAULT_CURRENCY = os.getenv("APP_DEFAULT_CURRENCY", "USD")
DOMAIN_VERIFICATION_MODE = os.getenv("DOMAIN_VERIFICATION_MODE", "manual")
APP_ENABLE_SUBDOMAIN_FALLBACK = os.getenv("APP_ENABLE_SUBDOMAIN_FALLBACK", "True").lower() in {
    "1",
    "true",
    "yes",
}
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@musico.local")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
SMS_PROVIDER = os.getenv("SMS_PROVIDER", "disabled")
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "niuwebdev@gmail.com")

if DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
