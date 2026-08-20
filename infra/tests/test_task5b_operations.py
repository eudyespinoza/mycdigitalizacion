from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
OPS = ROOT / "infra" / "ops"


def run_script(name: str, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    merged.update(env or {})
    return subprocess.run(
        [sys.executable, str(OPS / name), *args],
        cwd=ROOT,
        env=merged,
        text=True,
        capture_output=True,
        check=False,
    )


def valid_environment() -> dict[str, str]:
    return {
        "APP_ENV": "production",
        "SITE_ADDRESS": "tienda.mycdigitalizacion.com.ar",
        "ACME_EMAIL": "ops@mycdigitalizacion.com.ar",
        "ADMIN_ALLOWED_CIDRS": "203.0.113.10/32",
        "DJANGO_ALLOWED_HOSTS": "tienda.mycdigitalizacion.com.ar",
        "DJANGO_SECRET_KEY": "prod-signing-key-8f3db7c4f19a4e58a051",
        "PERSONAL_DATA_ENCRYPTION_KEY": "prod-personal-data-key-32-bytes-minimum",
        "POSTGRES_DB": "storefront",
        "POSTGRES_USER": "storefront_app",
        "POSTGRES_PASSWORD": "database-password-9aa4f49f8c28",
        "REDIS_PASSWORD": "redis-password-bf313f241c14",
        "SID_MODE": "disabled",
        "MERCADOPAGO_LIVE_MODE": "false",
        "CORREO_ARGENTINO_ENABLED": "false",
    }


class ProductionContractTests(unittest.TestCase):
    def test_production_compose_defines_resilient_non_root_service_topology(self) -> None:
        compose = yaml.safe_load((ROOT / "compose.prod.yaml").read_text(encoding="utf-8"))
        required = {"caddy", "frontend", "backend", "worker", "beat", "postgres", "redis", "backup"}
        self.assertTrue(required.issubset(compose["services"]))
        for name in required:
            service = compose["services"][name]
            self.assertEqual(service.get("restart"), "unless-stopped", name)
            self.assertIn("healthcheck", service, name)
            self.assertIn("limits", service.get("deploy", {}).get("resources", {}), name)
        for name in {"frontend", "backend", "worker", "beat", "backup"}:
            self.assertNotEqual(str(compose["services"][name].get("user", "0")).split(":", 1)[0], "0", name)
        self.assertTrue({"postgres_data", "media_data", "static_data", "backup_data", "caddy_data", "caddy_config"}.issubset(compose["volumes"]))

    def test_production_environment_rejects_placeholders_and_accepts_real_secrets(self) -> None:
        rejected = run_script("validate_env.py", env={**valid_environment(), "DJANGO_SECRET_KEY": "CHANGE_ME"})
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("DJANGO_SECRET_KEY", rejected.stderr)
        accepted = run_script("validate_env.py", env=valid_environment())
        self.assertEqual(accepted.returncode, 0, accepted.stderr)

    def test_production_environment_rejects_a_public_admin_allow_all(self) -> None:
        result = run_script("validate_env.py", env={**valid_environment(), "ADMIN_ALLOWED_CIDRS": "0.0.0.0/0"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ADMIN_ALLOWED_CIDRS", result.stderr)

    def test_restic_repository_requires_a_non_placeholder_encryption_secret(self) -> None:
        result = run_script(
            "validate_env.py",
            env={**valid_environment(), "RESTIC_REPOSITORY": "/encrypted/offsite", "RESTIC_PASSWORD": "CHANGE_ME"},
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("RESTIC_PASSWORD", result.stderr)

    def test_committed_production_example_is_deliberately_not_deployable(self) -> None:
        values: dict[str, str] = {}
        for raw_line in (ROOT / ".env.production.example").read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key] = value
        result = run_script("validate_env.py", env=values)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("placeholder", result.stderr.lower())

    def test_caddy_contract_terminates_tls_and_keeps_sensitive_routes_same_origin(self) -> None:
        caddyfile = (ROOT / "infra" / "caddy" / "Caddyfile").read_text(encoding="utf-8")
        self.assertIn("{$SITE_ADDRESS}", caddyfile)
        self.assertIn("encode zstd gzip", caddyfile)
        self.assertIn("request_body", caddyfile)
        self.assertIn("Strict-Transport-Security", caddyfile)
        self.assertIn("/api/*", caddyfile)
        self.assertIn("/admin/*", caddyfile)
        self.assertIn("/static/*", caddyfile)
        self.assertIn("/media/*", caddyfile)
        self.assertNotIn("tls internal", caddyfile)


class BackupRestoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.media = self.root / "media"
        self.media.mkdir()
        (self.media / "catalog").mkdir()
        (self.media / "catalog" / "photo.txt").write_text("safe media", encoding="utf-8")
        self.backups = self.root / "backups"
        self.fake = self.root / "fake_pg.py"
        self.fake.write_text(textwrap.dedent(
            """
            from pathlib import Path
            import os
            import sys

            mode = os.environ["FAKE_PG_MODE"]
            log = Path(os.environ["FAKE_PG_LOG"])
            if os.environ.get("FAKE_FAIL_MODE") == mode:
                with log.open("a", encoding="utf-8") as handle:
                    handle.write(mode + " failed\\n")
                raise SystemExit(7)
            if mode == "dump":
                target = Path(sys.argv[sys.argv.index("--file") + 1])
                target.write_bytes(b"portable pg dump")
            elif mode == "exists":
                print("1" if os.environ.get("FAKE_DB_EXISTS") == "true" else "0")
            else:
                with log.open("a", encoding="utf-8") as handle:
                    handle.write(mode + " " + " ".join(sys.argv[1:]) + "\\n")
            """
        ), encoding="utf-8")
        self.log = self.root / "pg.log"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def backup_env(self) -> dict[str, str]:
        return {
            **valid_environment(),
            "BACKUP_ROOT": str(self.backups),
            "MEDIA_ROOT": str(self.media),
            "PG_DUMP_COMMAND": f'"{sys.executable}" "{self.fake}"',
            "FAKE_PG_MODE": "dump",
            "FAKE_PG_LOG": str(self.log),
            "BACKUP_RETENTION_DAYS": "14",
        }

    def create_backup(self) -> Path:
        result = run_script("backup.py", "--timestamp", "20260820T120000Z", env=self.backup_env())
        self.assertEqual(result.returncode, 0, result.stderr)
        return self.backups / "20260820T120000Z"

    def test_backup_creates_dump_media_archive_and_verifiable_manifest(self) -> None:
        backup = self.create_backup()
        manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["format_version"], 1)
        self.assertEqual(manifest["database"]["file"], "database.dump")
        self.assertEqual(len(manifest["database"]["sha256"]), 64)
        self.assertEqual(len(manifest["media"]["sha256"]), 64)
        with tarfile.open(backup / "media.tar.gz", "r:gz") as archive:
            self.assertIn("media/catalog/photo.txt", archive.getnames())

    def test_backup_lock_prevents_overlapping_runs(self) -> None:
        self.backups.mkdir()
        (self.backups / ".backup.lock").write_text("busy", encoding="utf-8")
        result = run_script("backup.py", "--timestamp", "20260820T120000Z", env=self.backup_env())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already running", result.stderr)

    def test_restore_refuses_existing_targets_and_restores_only_to_new_targets(self) -> None:
        backup = self.create_backup()
        existing_media = self.root / "existing-media"
        existing_media.mkdir()
        base = {
            **valid_environment(),
            "PG_DATABASE_EXISTS_COMMAND": f'"{sys.executable}" "{self.fake}"',
            "PG_CREATEDB_COMMAND": f'"{sys.executable}" "{self.fake}"',
            "PG_RESTORE_COMMAND": f'"{sys.executable}" "{self.fake}"',
            "FAKE_PG_LOG": str(self.log),
            "FAKE_DB_EXISTS": "false",
        }
        refused = run_script(
            "restore.py", "--backup", str(backup), "--target-db", "restore_drill", "--target-media", str(existing_media),
            env={**base, "FAKE_PG_MODE": "exists"},
        )
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("target media already exists", refused.stderr)

        target_media = self.root / "restored-media"
        restored = run_script(
            "restore.py", "--backup", str(backup), "--target-db", "restore_drill", "--target-media", str(target_media),
            env=base,
        )
        self.assertEqual(restored.returncode, 0, restored.stderr)
        self.assertEqual((target_media / "catalog" / "photo.txt").read_text(encoding="utf-8"), "safe media")
        log = self.log.read_text(encoding="utf-8")
        self.assertIn("createdb", log)
        self.assertIn("restore", log)

    def test_restore_refuses_an_existing_database_without_explicit_confirmation(self) -> None:
        backup = self.create_backup()
        result = run_script(
            "restore.py",
            "--backup", str(backup),
            "--target-db", "existing_database",
            "--target-media", str(self.root / "new-media"),
            env={
                **valid_environment(),
                "PG_DATABASE_EXISTS_COMMAND": f'"{sys.executable}" "{self.fake}"',
                "PG_CREATEDB_COMMAND": f'"{sys.executable}" "{self.fake}"',
                "PG_RESTORE_COMMAND": f'"{sys.executable}" "{self.fake}"',
                "FAKE_PG_LOG": str(self.log),
                "FAKE_DB_EXISTS": "true",
            },
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("target database already exists", result.stderr)

    def test_restore_rejects_an_unsafe_database_identifier_before_calling_postgres(self) -> None:
        backup = self.create_backup()
        result = run_script(
            "restore.py",
            "--backup", str(backup),
            "--target-db", "restore'; DROP DATABASE storefront;--",
            "--target-media", str(self.root / "new-media"),
            env={
                **valid_environment(),
                "PG_DATABASE_EXISTS_COMMAND": f'"{sys.executable}" "{self.fake}"',
                "FAKE_PG_LOG": str(self.log),
            },
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid target database name", result.stderr)
        self.assertFalse(self.log.exists())

    def test_failed_restore_removes_the_new_database_target(self) -> None:
        backup = self.create_backup()
        result = run_script(
            "restore.py",
            "--backup", str(backup),
            "--target-db", "restore_failure_drill",
            "--target-media", str(self.root / "new-media"),
            env={
                **valid_environment(),
                "PG_DATABASE_EXISTS_COMMAND": f'"{sys.executable}" "{self.fake}"',
                "PG_CREATEDB_COMMAND": f'"{sys.executable}" "{self.fake}"',
                "PG_RESTORE_COMMAND": f'"{sys.executable}" "{self.fake}"',
                "PG_DROPDB_COMMAND": f'"{sys.executable}" "{self.fake}"',
                "FAKE_PG_LOG": str(self.log),
                "FAKE_DB_EXISTS": "false",
                "FAKE_FAIL_MODE": "restore",
            },
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("dropdb", self.log.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
