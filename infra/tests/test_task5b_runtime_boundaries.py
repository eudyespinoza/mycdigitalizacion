from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from urllib.parse import quote
from urllib.request import urlopen
import uuid

import yaml


ROOT = Path(__file__).resolve().parents[2]


def docker(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *arguments], cwd=ROOT, text=True, capture_output=True, check=check
    )


def published_url(container: str, port: str) -> str:
    for _ in range(60):
        result = docker("port", container, port)
        if result.stdout.strip():
            host_port = result.stdout.strip().rsplit(":", 1)[1]
            url = f"http://127.0.0.1:{host_port}"
            try:
                urlopen(f"{url}/health", timeout=1).close()
                return url
            except Exception:
                pass
        time.sleep(0.25)
    logs = docker("logs", container, check=False)
    raise AssertionError(logs.stdout + logs.stderr)


@unittest.skipUnless(
    os.environ.get("TASK5B_DOCKER_RUNTIME") == "1", "set TASK5B_DOCKER_RUNTIME=1"
)
class RuntimeBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        suffix = uuid.uuid4().hex[:10]
        self.names = {
            "media": f"task5b-media-{suffix}",
            "static": f"task5b-static-{suffix}",
            "caddy_data": f"task5b-caddy-data-{suffix}",
            "caddy_config": f"task5b-caddy-config-{suffix}",
            "backup": f"task5b-backup-{suffix}",
            "network": f"task5b-runtime-{suffix}",
            "backend": f"task5b-runtime-backend-{suffix}",
            "frontend_stub": f"task5b-runtime-frontend-stub-{suffix}",
            "caddy": f"task5b-runtime-caddy-{suffix}",
            "frontend": f"task5b-runtime-frontend-{suffix}",
            "backup_runner": f"task5b-runtime-backup-{suffix}",
        }
        for volume in ("media", "static", "caddy_data", "caddy_config", "backup"):
            docker("volume", "create", self.names[volume])
        docker("network", "create", self.names["network"])

    def tearDown(self) -> None:
        for name in ("caddy", "frontend", "backend", "frontend_stub", "backup_runner"):
            docker("rm", "-f", self.names[name], check=False)
        docker("network", "rm", self.names["network"], check=False)
        for volume in ("media", "static", "caddy_data", "caddy_config", "backup"):
            docker("volume", "rm", "-f", self.names[volume], check=False)

    def init_assets(self, release: str) -> None:
        docker(
            "run", "--rm", "--user", "0:0",
            "-e", "APP_ENV=test", "-e", f"RELEASE_ID={release}",
            "-e", "MEDIA_ROOT=/app/media", "-e", "STATIC_DATA_ROOT=/static-data",
            "-v", f"{self.names['media']}:/app/media",
            "-v", f"{self.names['static']}:/static-data",
            "-v", f"{self.names['backup']}:/backups",
            "--mount", f"type=bind,src={ROOT / 'infra' / 'ops'},dst=/ops,readonly",
            "mycdigitalizaciones-backend-prod", "python", "/ops/init_assets.py",
        )

    def start_caddy(self) -> str:
        for name, alias in (("backend", "backend"), ("frontend_stub", "frontend")):
            if docker("inspect", self.names[name], check=False).returncode != 0:
                docker(
                    "run", "-d", "--name", self.names[name],
                    "--network", self.names["network"], "--network-alias", alias,
                    "python:3.13-alpine", "python", "-m", "http.server",
                    "8000" if alias == "backend" else "3000",
                )
        docker(
            "run", "-d", "--name", self.names["caddy"],
            "--network", self.names["network"], "--read-only",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m", "-p", "127.0.0.1::8080",
            "-e", "SITE_ADDRESS=http://:8080",
            "-e", "SITE_WWW_ADDRESS=http://www.localhost:8080",
            "-e", "ACME_EMAIL=ops@mycdigitalizacion.com.ar",
            "-e", "ADMIN_ALLOWED_CIDRS=203.0.113.10/32",
            "-e", "BACKEND_UPSTREAM=backend:8000", "-e", "FRONTEND_UPSTREAM=frontend:3000",
            "-v", f"{self.names['media']}:/srv/media:ro",
            "-v", f"{self.names['static']}:/srv/static:ro",
            "-v", f"{self.names['caddy_data']}:/data",
            "-v", f"{self.names['caddy_config']}:/config",
            "mycdigitalizaciones-caddy-prod", "caddy", "run", "--config", "/etc/caddy/Caddyfile",
        )
        for _ in range(60):
            port = docker("port", self.names["caddy"], "8080/tcp").stdout.strip()
            if port:
                url = f"http://127.0.0.1:{port.rsplit(':', 1)[1]}"
                try:
                    urlopen(f"{url}/static/rest_framework/docs/css/base.css", timeout=1).close()
                    return url
                except Exception:
                    pass
            time.sleep(0.25)
        raise AssertionError(docker("logs", self.names["caddy"], check=False).stderr)

    def test_media_derivative_static_upgrade_and_caddy_persist_across_recreation(self) -> None:
        self.init_assets("release-runtime-one")
        upload = (
            "import io,json,os;os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');"
            "import django;django.setup();from PIL import Image;"
            "from django.core.files.base import ContentFile;"
            "from django.core.files.storage import FileSystemStorage;"
            "from config.media import generate_image_derivatives;out=io.BytesIO();"
            "Image.new('RGB',(640,400),'#c51566').save(out,format='PNG');"
            "storage=FileSystemStorage(location='/app/media',base_url='/media/');"
            "name=storage.save('catalog/runtime.png',ContentFile(out.getvalue()));"
            "print(json.dumps({'name':name,'derivatives':generate_image_derivatives("
            "storage=storage,name=name,supported_formats={'WEBP'})}))"
        )
        result = docker(
            "run", "--rm", "--user", "1000:1000", "-e", "APP_ENV=test",
            "-e", "MEDIA_ROOT=/app/media", "-v", f"{self.names['media']}:/app/media",
            "mycdigitalizaciones-backend-prod", "python", "-c", upload,
        )
        media = json.loads(result.stdout.strip().splitlines()[-1])
        derivative = media["derivatives"]["widths"][0]["fallback"]

        self.init_assets("release-runtime-two")
        url = self.start_caddy()
        self.assertEqual(urlopen(f"{url}/media/{media['name']}", timeout=5).status, 200)
        self.assertEqual(urlopen(f"{url}/media/{derivative}", timeout=5).status, 200)
        self.assertEqual(urlopen(f"{url}/static/rest_framework/docs/css/base.css", timeout=5).status, 200)

        old_caddy = self.names["caddy"]
        docker("rm", "-f", old_caddy)
        self.names["caddy"] = f"{old_caddy}-recreated"
        url = self.start_caddy()
        self.assertEqual(urlopen(f"{url}/media/{derivative}", timeout=5).status, 200)
        link = docker(
            "run", "--rm", "-v", f"{self.names['static']}:/srv/static:ro",
            "alpine:3.21", "readlink", "/srv/static/current",
        )
        self.assertEqual(link.stdout.strip(), "releases/release-runtime-two")

    def test_frontend_read_only_root_has_bounded_cold_and_warm_image_cache(self) -> None:
        docker(
            "run", "-d", "--name", self.names["frontend"],
            "--network", self.names["network"], "--read-only", "--memory", "384m",
            "--user", "1000:1000", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            "--tmpfs", "/app/frontend/.next/cache:rw,noexec,nosuid,size=256m,uid=1000,gid=1000,mode=0750",
            "-p", "127.0.0.1::3000", "-e", "API_INTERNAL_URL=http://backend:8000/api/v1",
            "-e", "API_PROXY_TARGET=http://backend:8000", "mycdigitalizaciones-frontend-prod",
        )
        url = published_url(self.names["frontend"], "3000/tcp")
        path = "/_next/image?url=" + quote("/brand/mycdigitalizacion-logo.png") + "&w=640&q=75"
        cold = urlopen(f"{url}{path}", timeout=15).read()
        warm = urlopen(f"{url}{path}", timeout=15).read()
        self.assertGreater(len(cold), 100)
        self.assertEqual(cold, warm)
        logs = docker("logs", self.names["frontend"], check=False)
        combined = (logs.stdout + logs.stderr).lower()
        self.assertNotIn("erofs", combined)
        self.assertNotIn("eacces", combined)

    def test_killed_backup_releases_os_lock_and_next_constrained_run_succeeds(self) -> None:
        self.init_assets("release-runtime-backup")
        with tempfile.TemporaryDirectory() as temp:
            fake = Path(temp) / "fake_dump.py"
            fake.write_text(
                "import os,sys,time\n"
                "from pathlib import Path\n"
                "time.sleep(float(os.environ.get('FAKE_SLEEP_SECONDS','0')))\n"
                "Path(sys.argv[sys.argv.index('--file')+1]).write_bytes(b'pgdump')\n",
                encoding="utf-8",
            )
            environment = {
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
                "RELEASE_ID": "release-runtime-backup",
                "SID_MODE": "disabled",
                "MERCADOPAGO_LIVE_MODE": "false",
                "CORREO_ARGENTINO_ENABLED": "false",
                "BACKUP_ROOT": "/backups",
                "MEDIA_ROOT": "/srv/media",
                "PG_DUMP_COMMAND": "python /fixture/fake_dump.py",
            }
            env_args = [item for key, value in environment.items() for item in ("-e", f"{key}={value}")]
            common = [
                "--memory", "320m", *env_args,
                "-v", f"{self.names['media']}:/srv/media:ro",
                "-v", f"{self.names['backup']}:/backups",
                "--mount", f"type=bind,src={fake},dst=/fixture/fake_dump.py,readonly",
                "mycdigitalizaciones-ops-prod", "python", "/ops/backup.py",
            ]
            docker(
                "run", "-d", "--name", self.names["backup_runner"],
                "-e", "FAKE_SLEEP_SECONDS=30", *common, "--timestamp", "20260820T130000Z",
            )
            for _ in range(40):
                probe = docker(
                    "run", "--rm", "-v", f"{self.names['backup']}:/backups:ro",
                    "alpine:3.21", "test", "-f", "/backups/.backup.lock", check=False,
                )
                if probe.returncode == 0:
                    break
                time.sleep(0.25)
            self.assertEqual(probe.returncode, 0)
            docker("kill", self.names["backup_runner"])
            docker("rm", self.names["backup_runner"])
            result = docker(
                "run", "--rm", "-e", "FAKE_SLEEP_SECONDS=0", *common,
                "--timestamp", "20260820T130100Z", check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            verify = docker(
                "run", "--rm", "-v", f"{self.names['backup']}:/backups:ro",
                "alpine:3.21", "test", "-f", "/backups/20260820T130100Z/manifest.json",
                check=False,
            )
            self.assertEqual(verify.returncode, 0)

    def test_two_gib_release_overlap_is_enforced_concurrently(self) -> None:
        environment = {**os.environ, "PRODUCTION_ENV_FILE": ".env.production.example"}
        rendered = subprocess.run(
            [
                "docker", "compose", "--env-file", ".env.production.example",
                "-f", "compose.prod.yaml", "config",
            ],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=True,
        )
        services = yaml.safe_load(rendered.stdout)["services"]
        overlap = (
            "postgres", "redis", "backend", "worker", "beat",
            "frontend", "backup", "caddy", "assets-init",
        )
        limits = {
            name: int(services[name]["deploy"]["resources"]["limits"]["memory"])
            for name in overlap
        }
        self.assertLessEqual(sum(limits.values()), 2 * 1024**3)

        probe = ROOT / "infra" / "tests" / "fixtures" / "task5b_capacity_probe.py"
        result = docker(
            "run", "--rm", "--memory", "2g", "--memory-swap", "2g",
            "--cpus", "2", "--pids-limit", "128",
            "-e", f"SERVICE_LIMITS_JSON={json.dumps(limits)}",
            "--mount", f"type=bind,src={probe},dst=/probe.py,readonly",
            "python:3.13-alpine", "python", "/probe.py",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        measurement = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(measurement["memory_max_bytes"], 2 * 1024**3)
        self.assertGreaterEqual(measurement["memory_peak_bytes"], 1650 * 1024**2)
        self.assertEqual(measurement["oom_kill_delta"], 0)
        self.assertEqual(set(measurement["concurrent_services"]), set(overlap))
        self.assertEqual(measurement["backup_bytes"], 64 * 1024**2)
        self.assertEqual(len(measurement["backup_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
