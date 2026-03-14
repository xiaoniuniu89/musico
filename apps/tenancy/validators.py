import re

from django.core.exceptions import ValidationError

HOST_PATTERN = re.compile(
    r"^(?=.{1,255}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)(?:\.(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?))*$"
)


def normalize_host(value: str) -> str:
    return (value or "").strip().lower().rstrip(".")


def validate_host_format(value: str) -> None:
    host = normalize_host(value)
    if not host:
        raise ValidationError("Host is required.")

    invalid_chars = ["://", "/", "?", "#", "@", ":"]
    if any(token in host for token in invalid_chars):
        raise ValidationError("Host must be a bare domain without scheme, path, or port.")

    if host.startswith(".") or host.endswith("."):
        raise ValidationError("Host cannot start or end with a dot.")

    if ".." in host:
        raise ValidationError("Host cannot contain empty labels.")

    if not HOST_PATTERN.match(host):
        raise ValidationError("Host contains invalid characters.")
