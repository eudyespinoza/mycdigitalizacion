from __future__ import annotations

import ipaddress
import os
from pathlib import Path
import re
import sys

from common import emit_event


PLACEHOLDER = re.compile(r"change.?me|replace.?me|placeholder|unsafe|development|example\.(?:com|org|net)|\.invalid\b|todo|x{3,}", re.IGNORECASE)
CORE_REQUIRED = {
    "APP_ENV": 10,
    "SITE_ADDRESS": 4,
    "ACME_EMAIL": 6,
    "ADMIN_ALLOWED_CIDRS": 3,
    "DJANGO_ALLOWED_HOSTS": 4,
    "DJANGO_SECRET_KEY": 32,
    "PERSONAL_DATA_ENCRYPTION_KEY": 32,
    "POSTGRES_DB": 2,
    "POSTGRES_USER": 2,
    "POSTGRES_PASSWORD": 20,
    "REDIS_PASSWORD": 20,
    "RELEASE_ID": 7,
}
INTEGER_BOUNDS = {
    "BACKUP_INTERVAL_HOURS": (1, 168, "24"),
    "BACKUP_RETENTION_DAYS": (1, 365, "14"),
    "RESTIC_KEEP_DAILY": (1, 365, "7"),
    "RESTIC_KEEP_WEEKLY": (1, 104, "5"),
    "RESTIC_KEEP_MONTHLY": (1, 120, "12"),
}


def require(name: str, errors: list[str], minimum: int = 1) -> str:
    value = os.environ.get(name, "").strip()
    if len(value) < minimum or PLACEHOLDER.search(value):
        errors.append(f"{name} is missing, too short, or still a placeholder")
    return value


def validate() -> list[str]:
    errors: list[str] = []
    values = {name: require(name, errors, minimum) for name, minimum in CORE_REQUIRED.items()}
    if values["APP_ENV"] != "production":
        errors.append("APP_ENV must be production")
    if values["RELEASE_ID"].lower().startswith("replace_me") or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{6,79}", values["RELEASE_ID"]):
        errors.append("RELEASE_ID must be an immutable deploy identifier")
    site = values["SITE_ADDRESS"]
    if "://" in site or site.startswith("localhost") or "." not in site:
        errors.append("SITE_ADDRESS must be a real hostname without scheme")
    if site and site not in {host.strip() for host in values["DJANGO_ALLOWED_HOSTS"].split(",")}:
        errors.append("DJANGO_ALLOWED_HOSTS must include SITE_ADDRESS")
    if "@" not in values["ACME_EMAIL"] or values["ACME_EMAIL"].endswith("@"):
        errors.append("ACME_EMAIL must be a valid operational email")
    try:
        if "," in values["ADMIN_ALLOWED_CIDRS"]:
            raise ValueError
        admin_networks = [ipaddress.ip_network(item) for item in values["ADMIN_ALLOWED_CIDRS"].split() if item]
        collapsed = []
        for version in (4, 6):
            collapsed.extend(ipaddress.collapse_addresses(network for network in admin_networks if network.version == version))
        if not collapsed or any(network.prefixlen == 0 for network in collapsed):
            raise ValueError
    except ValueError:
        errors.append("ADMIN_ALLOWED_CIDRS must use spaces between bounded office or VPN CIDRs, never a public union")
    for name, (minimum, maximum, default) in INTEGER_BOUNDS.items():
        raw_value = os.environ.get(name, default).strip()
        try:
            parsed = int(raw_value)
            if not minimum <= parsed <= maximum:
                raise ValueError
        except ValueError:
            errors.append(f"{name} must be an integer between {minimum} and {maximum}")
    if os.environ.get("SID_MODE", "disabled") == "production":
        require("SID_BASE_URL", errors, 10)
        require("SID_ACCESS_TOKEN", errors, 16)
    if os.environ.get("MERCADOPAGO_LIVE_MODE", "false").lower() == "true":
        for name in ("MERCADOPAGO_ACCESS_TOKEN", "MERCADOPAGO_WEBHOOK_SECRET", "MERCADOPAGO_COLLECTOR_ID"):
            require(name, errors, 8)
    if os.environ.get("CORREO_ARGENTINO_ENABLED", "false").lower() == "true":
        for name in ("CORREO_ARGENTINO_USERNAME", "CORREO_ARGENTINO_PASSWORD", "CORREO_ARGENTINO_CUSTOMER_ID", "CORREO_ARGENTINO_ORIGIN_POSTAL_CODE"):
            require(name, errors, 3)
    repository = os.environ.get("RESTIC_REPOSITORY", "").strip()
    if repository:
        password = os.environ.get("RESTIC_PASSWORD", "").strip()
        password_file = os.environ.get("RESTIC_PASSWORD_FILE", "").strip()
        if not (password or password_file):
            errors.append("RESTIC_PASSWORD or RESTIC_PASSWORD_FILE is required with RESTIC_REPOSITORY")
        elif password:
            require("RESTIC_PASSWORD", errors, 20)
        else:
            path_value = require("RESTIC_PASSWORD_FILE", errors, 4)
            password_path = Path(path_value)
            if not password_path.is_file() or not os.access(password_path, os.R_OK):
                errors.append("RESTIC_PASSWORD_FILE must exist and be readable")
        if repository.startswith("s3:"):
            require("AWS_ACCESS_KEY_ID", errors, 8)
            require("AWS_SECRET_ACCESS_KEY", errors, 16)
    return errors


def main() -> int:
    errors = validate()
    if errors:
        emit_event("config-check", "config.invalid", level="error", stream=sys.stderr, detail="; ".join(errors))
        return 2
    emit_event("config-check", "config.valid", environment="production")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
