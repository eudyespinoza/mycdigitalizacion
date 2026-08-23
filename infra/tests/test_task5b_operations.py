from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import threading
import time
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
        "SITE_WWW_ADDRESS": "www.tienda.mycdigitalizacion.com.ar",
        "ACME_EMAIL": "ops@mycdigitalizacion.com.ar",
        "ADMIN_ALLOWED_CIDRS": "203.0.113.10/32",
        "DJANGO_ALLOWED_HOSTS": (
            "tienda.mycdigitalizacion.com.ar,www.tienda.mycdigitalizacion.com.ar"
        ),
        "DJANGO_SECRET_KEY": "prod-signing-key-8f3db7c4f19a4e58a051",
        "PERSONAL_DATA_ENCRYPTION_KEY": "prod-personal-data-key-32-bytes-minimum",
        "POSTGRES_DB": "storefront",
        "POSTGRES_USER": "storefront_app",
        "POSTGRES_PASSWORD": "database-password-9aa4f49f8c28",
        "REDIS_PASSWORD": "redis-password-bf313f241c14",
        "RELEASE_ID": "release-20260820-abcdef1",
        "SID_MODE": "disabled",
        "MERCADOPAGO_LIVE_MODE": "false",
        "CORREO_ARGENTINO_ENABLED": "false",
    }


def rendered_production_compose() -> dict[str, object]:
    environment = os.environ.copy()
    environment["PRODUCTION_ENV_FILE"] = ".env.production.example"
    result = subprocess.run(
        ["docker", "compose", "--env-file", ".env.production.example", "-f", "compose.prod.yaml", "config"],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return yaml.safe_load(result.stdout)


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

    def test_production_requires_a_distinct_www_host_allowed_by_django_and_caddy(self) -> None:
        missing = run_script(
            "validate_env.py",
            env={**valid_environment(), "SITE_WWW_ADDRESS": ""},
        )
        not_allowed = run_script(
            "validate_env.py",
            env={**valid_environment(), "DJANGO_ALLOWED_HOSTS": "tienda.mycdigitalizacion.com.ar"},
        )
        duplicate = run_script(
            "validate_env.py",
            env={
                **valid_environment(),
                "SITE_WWW_ADDRESS": "tienda.mycdigitalizacion.com.ar",
            },
        )
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("SITE_WWW_ADDRESS", missing.stderr)
        self.assertNotEqual(not_allowed.returncode, 0)
        self.assertIn("DJANGO_ALLOWED_HOSTS", not_allowed.stderr)
        self.assertNotEqual(duplicate.returncode, 0)
        self.assertIn("SITE_WWW_ADDRESS", duplicate.stderr)

        compose = rendered_production_compose()
        self.assertIn("SITE_WWW_ADDRESS", compose["services"]["caddy"]["environment"])

    def test_production_environment_rejects_a_public_admin_allow_all(self) -> None:
        result = run_script("validate_env.py", env={**valid_environment(), "ADMIN_ALLOWED_CIDRS": "0.0.0.0/0"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ADMIN_ALLOWED_CIDRS", result.stderr)

    def test_pool_bypass_switch_requires_an_explicit_boolean(self) -> None:
        result = run_script(
            "validate_env.py",
            env={**valid_environment(), "POSTGRES_BYPASS_POOL": "sometimes"},
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("POSTGRES_BYPASS_POOL", result.stderr)

    def test_admin_cidrs_use_spaces_and_reject_an_effective_public_union(self) -> None:
        comma = run_script(
            "validate_env.py",
            env={**valid_environment(), "ADMIN_ALLOWED_CIDRS": "203.0.113.10/32,198.51.100.20/32"},
        )
        public_union = run_script(
            "validate_env.py",
            env={**valid_environment(), "ADMIN_ALLOWED_CIDRS": "0.0.0.0/1 128.0.0.0/1"},
        )
        self.assertNotEqual(comma.returncode, 0)
        self.assertNotEqual(public_union.returncode, 0)
        self.assertIn("ADMIN_ALLOWED_CIDRS", comma.stderr)
        self.assertIn("ADMIN_ALLOWED_CIDRS", public_union.stderr)

    def test_restic_repository_requires_a_non_placeholder_encryption_secret(self) -> None:
        result = run_script(
            "validate_env.py",
            env={**valid_environment(), "RESTIC_REPOSITORY": "/encrypted/offsite", "RESTIC_PASSWORD": "CHANGE_ME"},
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("RESTIC_PASSWORD", result.stderr)

    def test_backup_controls_are_bounded_and_password_file_must_exist(self) -> None:
        invalid_values = {
            "BACKUP_INTERVAL_HOURS": "0",
            "BACKUP_RETENTION_DAYS": "-1",
            "RESTIC_KEEP_DAILY": "not-a-number",
            "RESTIC_KEEP_WEEKLY": "0",
            "RESTIC_KEEP_MONTHLY": "9999",
        }
        for name, value in invalid_values.items():
            with self.subTest(name=name):
                result = run_script("validate_env.py", env={**valid_environment(), name: value})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(name, result.stderr)
        missing_file = run_script(
            "validate_env.py",
            env={
                **valid_environment(),
                "RESTIC_REPOSITORY": "/encrypted/offsite",
                "RESTIC_PASSWORD_FILE": str(ROOT / "does-not-exist.secret"),
            },
        )
        self.assertNotEqual(missing_file.returncode, 0)
        self.assertIn("RESTIC_PASSWORD_FILE", missing_file.stderr)

    def test_release_initializer_and_bounded_next_cache_are_runtime_dependencies(self) -> None:
        compose = rendered_production_compose()
        services = compose["services"]
        self.assertIn("assets-init", services)
        self.assertEqual(services["backend"]["depends_on"]["assets-init"]["condition"], "service_completed_successfully")
        self.assertEqual(services["worker"]["depends_on"]["assets-init"]["condition"], "service_completed_successfully")
        assets_mounts = services["assets-init"].get("volumes", [])
        self.assertTrue(any("/backups" in str(item) for item in assets_mounts))
        cache_mounts = services["frontend"].get("tmpfs", [])
        self.assertTrue(any(item.startswith("/app/frontend/.next/cache:") and "size=" in item for item in cache_mounts))

    def test_initial_service_and_release_overlap_fits_two_gib_profile(self) -> None:
        compose = rendered_production_compose()
        names = (
            "postgres",
            "redis",
            "backend",
            "worker",
            "beat",
            "frontend",
            "backup",
            "caddy",
            "assets-init",
        )

        def mebibytes(value: str | int) -> int:
            if isinstance(value, int) or str(value).isdigit():
                return int(value) // (1024 * 1024)
            suffix = value[-1].upper()
            amount = int(value[:-1])
            return amount if suffix == "M" else amount * 1024

        total = sum(mebibytes(compose["services"][name]["deploy"]["resources"]["limits"]["memory"]) for name in names)
        self.assertLessEqual(total, 2048)

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

    def test_production_verifier_runs_real_config_and_runtime_boundaries(self) -> None:
        source = (ROOT / "scripts" / "verify-production.py").read_text(encoding="utf-8")
        self.assertIn('"run", "--rm", "config-check"', source)
        self.assertIn("TASK5B_DOCKER_RUNTIME", source)
        self.assertIn("test_task5b_runtime_boundaries", source)


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
            import time

            mode = os.environ["FAKE_PG_MODE"]
            log = Path(os.environ["FAKE_PG_LOG"])
            if os.environ.get("FAKE_EMIT_SENSITIVE") == "true":
                print("diagnostic https://provider.test/path?email=ana@example.com&token=stdout-secret")
                print("credential " + os.environ["POSTGRES_PASSWORD"])
                print("password=stderr-secret cookie=session-secret", file=sys.stderr)
            if os.environ.get("FAKE_EMIT_OVERSIZED") == "true":
                payload = "email=oversized@example.test token=oversized-secret " + ("x" * 1024)
                for _ in range(2048):
                    print(payload)
            if os.environ.get("FAKE_SLEEP_MODE") == mode:
                time.sleep(float(os.environ.get("FAKE_SLEEP_SECONDS", "2")))
            if os.environ.get("FAKE_FAIL_MODE") == mode:
                with log.open("a", encoding="utf-8") as handle:
                    handle.write(mode + " failed\\n")
                raise SystemExit(7)
            if mode == "dump":
                target = Path(sys.argv[sys.argv.index("--file") + 1])
                target.write_bytes(b"portable pg dump")
            elif mode == "exists":
                print("1" if os.environ.get("FAKE_DB_EXISTS") == "true" else "0")
            elif mode == "restic" and "snapshots" in sys.argv:
                with log.open("a", encoding="utf-8") as handle:
                    handle.write(mode + " " + " ".join(sys.argv[1:]) + "\\n")
                print(os.environ.get("FAKE_RESTIC_SNAPSHOTS", "[]"))
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
        self.assertEqual(manifest["release_id"], valid_environment()["RELEASE_ID"])
        self.assertIn("configuration_fingerprint", manifest)
        self.assertEqual(manifest["database"]["file"], "database.dump")
        self.assertEqual(len(manifest["database"]["sha256"]), 64)
        self.assertEqual(len(manifest["media"]["sha256"]), 64)
        with tarfile.open(backup / "media.tar.gz", "r:gz") as archive:
            self.assertIn("media/catalog/photo.txt", archive.getnames())

    def test_restic_backup_is_successful_only_after_snapshot_listing_confirms_target(self) -> None:
        target = str(self.backups / "20260820T120000Z")
        environment = {
            **self.backup_env(),
            "RESTIC_REPOSITORY": "/encrypted/offsite",
            "RESTIC_PASSWORD": "restic-password-32-safe-characters",
            "RESTIC_COMMAND": f'"{sys.executable}" "{self.fake}"',
            "FAKE_RESTIC_SNAPSHOTS": json.dumps([{"id": "snapshot-1", "paths": [target]}]),
        }
        success = run_script("backup.py", "--timestamp", "20260820T120000Z", env=environment)
        self.assertEqual(success.returncode, 0, success.stderr)
        self.assertIn("snapshots", self.log.read_text(encoding="utf-8"))

        empty_root = self.root / "empty-snapshot-backups"
        failed = run_script(
            "backup.py",
            "--timestamp",
            "20260820T120100Z",
            env={
                **environment,
                "BACKUP_ROOT": str(empty_root),
                "FAKE_RESTIC_SNAPSHOTS": "[]",
            },
        )
        self.assertNotEqual(failed.returncode, 0)
        failure = json.loads(failed.stderr.strip().splitlines()[-1])
        self.assertEqual(failure["event"], "backup.failed")

    def test_operational_failures_use_redacted_json_logs(self) -> None:
        result = run_script(
            "backup.py",
            "--timestamp",
            "20260820T120000Z",
            env={
                **self.backup_env(),
                "FAKE_FAIL_MODE": "dump",
                "BACKUP_ALERT_WEBHOOK_URL": (
                    "https://alerts.example.test/hook?email=ana@example.com&token=secret"
                ),
            },
        )
        self.assertNotEqual(result.returncode, 0)
        event = json.loads(result.stderr.strip().splitlines()[-1])
        self.assertEqual(event["service"], "backup")
        self.assertEqual(event["event"], "backup.failed")
        self.assertNotIn("ana@example.com", result.stderr)
        self.assertNotIn("token=secret", result.stderr)

    def test_subprocess_stdout_and_stderr_are_redacted_json_events(self) -> None:
        result = run_script(
            "backup.py",
            "--timestamp",
            "20260820T120000Z",
            env={**self.backup_env(), "FAKE_EMIT_SENSITIVE": "true"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        combined = result.stdout + result.stderr
        self.assertNotIn("ana@example.com", combined)
        self.assertNotIn("stdout-secret", combined)
        self.assertNotIn("stderr-secret", combined)
        self.assertNotIn("session-secret", combined)
        self.assertNotIn(self.backup_env()["POSTGRES_PASSWORD"], combined)
        events = [json.loads(line) for line in combined.splitlines() if line.strip()]
        subprocess_events = [event for event in events if event["event"].startswith("subprocess.")]
        self.assertTrue(all(event["job_id"] for event in events))
        self.assertEqual(
            {event["event"] for event in subprocess_events},
            {"subprocess.stdout", "subprocess.stderr"},
        )
        self.assertTrue(all(event["service"] == "backup" for event in subprocess_events))
        self.assertTrue(all(event["job_id"] for event in subprocess_events))

    def test_oversized_subprocess_output_is_killed_and_reported_as_bounded_json(self) -> None:
        result = run_script(
            "backup.py",
            "--timestamp",
            "20260820T120000Z",
            env={**self.backup_env(), "FAKE_EMIT_OVERSIZED": "true"},
        )
        self.assertNotEqual(result.returncode, 0)
        combined = result.stdout + result.stderr
        self.assertLess(len(combined), 20_000)
        self.assertNotIn("oversized@example.test", combined)
        self.assertNotIn("oversized-secret", combined)
        events = [json.loads(line) for line in combined.splitlines() if line.strip()]
        overflow = [event for event in events if event["event"] == "subprocess.output_limit_exceeded"]
        self.assertEqual(len(overflow), 1, events)
        self.assertEqual(overflow[0]["limit_bytes"], 1024 * 1024)

    def test_scheduler_backup_and_subprocess_share_one_job_id(self) -> None:
        result = run_script(
            "scheduler.py",
            "--run-once",
            env={
                **self.backup_env(),
                "BACKUP_HEALTH_FILE": str(self.root / "scheduler-health.json"),
                "FAKE_EMIT_SENSITIVE": "true",
                "OPS_JOB_ID": "123e4567-e89b-12d3-a456-123456789012",
            },
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        events = [
            json.loads(line)
            for line in (result.stdout + result.stderr).splitlines()
            if line.strip().startswith("{")
        ]
        event_names = {event["event"] for event in events}
        self.assertTrue(
            {"subprocess.stdout", "subprocess.stderr", "backup.completed"}.issubset(event_names)
        )
        self.assertEqual(len({event["job_id"] for event in events}), 1, events)

    def test_concurrent_scheduler_jobs_keep_distinct_correlation_ids(self) -> None:
        processes: list[subprocess.Popen[str]] = []
        for suffix in ("a", "b"):
            environment = os.environ.copy()
            environment.update(
                {
                    **self.backup_env(),
                    "BACKUP_ROOT": str(self.root / f"backups-{suffix}"),
                    "BACKUP_HEALTH_FILE": str(self.root / f"health-{suffix}.json"),
                    "FAKE_SLEEP_MODE": "dump",
                    "FAKE_SLEEP_SECONDS": "0.5",
                }
            )
            processes.append(
                subprocess.Popen(
                    [sys.executable, str(OPS / "scheduler.py"), "--run-once"],
                    cwd=ROOT,
                    env=environment,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            )
        job_ids: list[str] = []
        for process in processes:
            stdout, stderr = process.communicate(timeout=15)
            self.assertEqual(process.returncode, 0, stdout + stderr)
            events = [
                json.loads(line)
                for line in (stdout + stderr).splitlines()
                if line.strip().startswith("{")
            ]
            ids = {event["job_id"] for event in events}
            self.assertEqual(len(ids), 1, events)
            job_ids.append(ids.pop())
        self.assertEqual(len(set(job_ids)), 2, job_ids)

    def test_scheduler_job_id_reaches_backup_alert_payload(self) -> None:
        received: list[dict[str, str]] = []

        class AlertHandler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 - HTTP handler API
                length = int(self.headers["Content-Length"])
                received.append(json.loads(self.rfile.read(length)))
                self.send_response(204)
                self.end_headers()

            def log_message(self, format: str, *args: object) -> None:
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), AlertHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = run_script(
                "scheduler.py",
                "--run-once",
                env={
                    **self.backup_env(),
                    "BACKUP_HEALTH_FILE": str(self.root / "alert-health.json"),
                    "BACKUP_ALERT_WEBHOOK_URL": f"http://127.0.0.1:{server.server_port}/alert",
                    "FAKE_FAIL_MODE": "dump",
                },
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        self.assertNotEqual(result.returncode, 0)
        events = [
            json.loads(line)
            for line in (result.stdout + result.stderr).splitlines()
            if line.strip().startswith("{")
        ]
        self.assertEqual(len(received), 1, received)
        self.assertEqual(received[0]["job_id"], events[0]["job_id"])

    def test_backup_lock_prevents_overlapping_runs(self) -> None:
        environment = os.environ.copy()
        environment.update({**self.backup_env(), "FAKE_SLEEP_MODE": "dump", "FAKE_SLEEP_SECONDS": "2"})
        first = subprocess.Popen(
            [sys.executable, str(OPS / "backup.py"), "--timestamp", "20260820T120000Z"],
            cwd=ROOT,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for _ in range(50):
            if (self.backups / ".backup.lock").exists():
                break
            time.sleep(0.05)
        second = run_script("backup.py", "--timestamp", "20260820T120100Z", env=self.backup_env())
        first_stdout, first_stderr = first.communicate(timeout=10)
        self.assertEqual(first.returncode, 0, first_stderr or first_stdout)
        self.assertNotEqual(second.returncode, 0)
        self.assertIn("already running", second.stderr)

    def test_stale_lock_file_is_recovered_and_next_snapshot_is_created(self) -> None:
        self.backups.mkdir()
        (self.backups / ".backup.lock").write_text('{"pid":999999,"host":"dead-container"}', encoding="utf-8")
        result = run_script("backup.py", "--timestamp", "20260820T120000Z", env=self.backup_env())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.backups / "20260820T120000Z" / "manifest.json").is_file())

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

    def test_restore_has_no_existing_target_override(self) -> None:
        backup = self.create_backup()
        result = run_script(
            "restore.py",
            "--backup", str(backup),
            "--target-db", "existing_database",
            "--target-media", str(self.root / "existing-media"),
            "--confirm-existing",
            env=valid_environment(),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unrecognized arguments: --confirm-existing", result.stderr)

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
