from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], *, environment: dict[str, str] | None = None) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=ROOT, env=environment, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the production container contract")
    parser.add_argument("--env-file", default=".env.production.example")
    parser.add_argument("--build", action="store_true", help="Build every production image")
    arguments = parser.parse_args()

    environment = os.environ.copy()
    environment["PRODUCTION_ENV_FILE"] = arguments.env_file
    compose = ["docker", "compose", "--env-file", arguments.env_file, "-f", "compose.prod.yaml"]
    run([sys.executable, "-m", "unittest", "infra.tests.test_task5b_operations", "-v"], environment=environment)
    run([*compose, "config", "--quiet"], environment=environment)
    run([*compose, "build", "config-check", "backup", "caddy"], environment=environment)
    if arguments.build:
        run([*compose, "build", "backend", "worker", "beat", "frontend"], environment=environment)
    run([
        "docker", "run", "--rm",
        "-e", "SITE_ADDRESS=tienda.mycdigitalizacion.com.ar",
        "-e", "ACME_EMAIL=ops@mycdigitalizacion.com.ar",
        "-e", "ADMIN_ALLOWED_CIDRS=203.0.113.10/32",
        "mycdigitalizaciones-caddy-prod", "caddy", "validate", "--config", "/etc/caddy/Caddyfile",
    ])
    expected_users = {
        "mycdigitalizaciones-ops-prod": "10001:10001",
        "mycdigitalizaciones-caddy-prod": "1000:1000",
    }
    if arguments.build:
        expected_users.update({
            "mycdigitalizaciones-backend-prod": "appuser",
            "mycdigitalizaciones-frontend-prod": "node",
        })
    for image, expected in expected_users.items():
        result = subprocess.run(
            ["docker", "image", "inspect", image, "--format", "{{.Config.User}}"],
            cwd=ROOT, text=True, capture_output=True, check=True,
        )
        actual = result.stdout.strip()
        if actual != expected:
            raise RuntimeError(f"{image} runs as {actual or 'root'}, expected {expected}")
    print("Production container contract: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
