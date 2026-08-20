from __future__ import annotations

import os
from pathlib import Path
import subprocess
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]


def render_compose(filename: str) -> dict[str, object]:
    command = ["docker", "compose"]
    if filename == "compose.prod.yaml":
        command.extend(["--env-file", ".env.production.example"])
    command.extend(["-f", filename, "config"])
    environment = os.environ.copy()
    environment["PRODUCTION_ENV_FILE"] = ".env.production.example"
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    return yaml.safe_load(result.stdout)


class PgBouncerTopologyTests(unittest.TestCase):
    def test_dev_and_production_apps_use_transaction_pooling(self) -> None:
        for filename in ("compose.yaml", "compose.prod.yaml"):
            with self.subTest(filename=filename):
                services = render_compose(filename)["services"]
                pool = services["pgbouncer"]
                self.assertNotIn("DB_NAME", pool["environment"])
                self.assertIn("HEALTH_DB", pool["environment"])
                self.assertEqual(pool["environment"]["POOL_MODE"], "transaction")
                self.assertEqual(str(pool["environment"]["LISTEN_PORT"]), "6432")
                self.assertEqual(str(pool["environment"]["DEFAULT_POOL_SIZE"]), "10")
                self.assertEqual(str(pool["environment"]["MIN_POOL_SIZE"]), "2")
                self.assertEqual(str(pool["environment"]["RESERVE_POOL_SIZE"]), "2")
                self.assertEqual(str(pool["environment"]["MAX_CLIENT_CONN"]), "100")
                self.assertEqual(str(pool["environment"]["MAX_DB_CONNECTIONS"]), "20")
                for name in ("backend", "worker", "beat"):
                    self.assertEqual(services[name]["environment"]["POSTGRES_HOST"], "pgbouncer")
                    self.assertEqual(str(services[name]["environment"]["POSTGRES_PORT"]), "6432")
                    self.assertEqual(
                        services[name]["depends_on"]["pgbouncer"]["condition"],
                        "service_healthy",
                    )

    def test_operational_services_keep_a_direct_postgres_route(self) -> None:
        services = render_compose("compose.prod.yaml")["services"]
        for name in ("assets-init", "backup"):
            environment = services[name]["environment"]
            self.assertEqual(environment["POSTGRES_DIRECT_HOST"], "postgres")
            self.assertEqual(str(environment["POSTGRES_DIRECT_PORT"]), "5432")

    def test_pool_is_internal_pinned_non_root_and_memory_bounded(self) -> None:
        service = render_compose("compose.prod.yaml")["services"]["pgbouncer"]
        self.assertEqual(service["image"], "edoburu/pgbouncer:v1.25.2-p0")
        self.assertNotIn("ports", service)
        self.assertNotEqual(str(service.get("user", "0")).split(":", 1)[0], "0")
        self.assertEqual(int(service["deploy"]["resources"]["limits"]["memory"]), 32 * 1024 * 1024)
        self.assertIn("healthcheck", service)

    def test_initial_production_defaults_fit_two_gigabyte_vps(self) -> None:
        services = render_compose("compose.prod.yaml")["services"]
        expected_mebibytes = {
            "postgres": 384,
            "pgbouncer": 32,
            "backend": 320,
            "worker": 256,
            "beat": 80,
            "redis": 128,
            "frontend": 256,
            "caddy": 64,
            "backup": 128,
        }
        actual = {
            name: int(services[name]["deploy"]["resources"]["limits"]["memory"])
            for name in expected_mebibytes
        }
        self.assertEqual(
            actual,
            {name: value * 1024 * 1024 for name, value in expected_mebibytes.items()},
        )
        self.assertEqual(services["backend"]["command"][5], "2")
        self.assertIn("--concurrency=1", services["worker"]["command"])

    def test_pool_admin_console_is_limited_to_database_operator(self) -> None:
        for filename in ("compose.yaml", "compose.prod.yaml"):
            with self.subTest(filename=filename):
                environment = render_compose(filename)["services"]["pgbouncer"]["environment"]
                self.assertEqual(environment["ADMIN_USERS"], environment["DB_USER"])
                self.assertEqual(environment["STATS_USERS"], environment["DB_USER"])


if __name__ == "__main__":
    unittest.main()
