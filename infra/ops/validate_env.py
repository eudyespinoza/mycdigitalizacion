from __future__ import annotations

import json
import ipaddress
import os
import re
import sys


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
    site = values["SITE_ADDRESS"]
    if "://" in site or site.startswith("localhost") or "." not in site:
        errors.append("SITE_ADDRESS must be a real hostname without scheme")
    if site and site not in {host.strip() for host in values["DJANGO_ALLOWED_HOSTS"].split(",")}:
        errors.append("DJANGO_ALLOWED_HOSTS must include SITE_ADDRESS")
    if "@" not in values["ACME_EMAIL"] or values["ACME_EMAIL"].endswith("@"):
        errors.append("ACME_EMAIL must be a valid operational email")
    try:
        admin_networks = [ipaddress.ip_network(item) for item in re.split(r"[\s,]+", values["ADMIN_ALLOWED_CIDRS"]) if item]
        if not admin_networks or any(network.prefixlen == 0 for network in admin_networks):
            raise ValueError
    except ValueError:
        errors.append("ADMIN_ALLOWED_CIDRS must contain bounded office or VPN CIDRs, never an allow-all")
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
            require("RESTIC_PASSWORD_FILE", errors, 4)
        if repository.startswith("s3:"):
            require("AWS_ACCESS_KEY_ID", errors, 8)
            require("AWS_SECRET_ACCESS_KEY", errors, 16)
    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 2
    print(json.dumps({"status": "ok", "environment": "production"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
