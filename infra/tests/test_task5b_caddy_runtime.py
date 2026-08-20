from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import time
import unittest
from urllib import error, request
import uuid


ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(os.environ.get("TASK5B_DOCKER_RUNTIME") == "1", "set TASK5B_DOCKER_RUNTIME=1")
class CaddyRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        suffix = uuid.uuid4().hex[:10]
        self.network = f"task5b-caddy-{suffix}"
        self.caddy = f"task5b-caddy-edge-{suffix}"
        self.backend = f"task5b-caddy-backend-{suffix}"
        subprocess.run(["docker", "network", "create", self.network], check=True, capture_output=True)

    def tearDown(self) -> None:
        for container in (self.caddy, self.backend):
            subprocess.run(["docker", "rm", "-f", container], check=False, capture_output=True)
        subprocess.run(["docker", "network", "rm", self.network], check=False, capture_output=True)

    def start_backend(self) -> None:
        subprocess.run(
            [
                "docker", "run", "-d", "--name", self.backend, "--network", self.network,
                "--network-alias", "backend", "python:3.13-alpine", "python", "-m", "http.server", "8000",
            ],
            check=True,
            capture_output=True,
        )

    def start_echo_backend(self) -> None:
        script = """
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        payload = json.dumps({
            'host': self.headers.get('Host'),
            'request_id': self.headers.get('X-Request-ID'),
            'forwarded_for': self.headers.get('X-Forwarded-For'),
            'forwarded_proto': self.headers.get('X-Forwarded-Proto'),
        }).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        return

HTTPServer(('0.0.0.0', 8000), Handler).serve_forever()
"""
        subprocess.run(
            [
                "docker", "run", "-d", "--name", self.backend, "--network", self.network,
                "--network-alias", "backend", "python:3.13-alpine", "python", "-c", script,
            ],
            check=True,
            capture_output=True,
        )

    def start_caddy(self, allowed_cidrs: str, *, backend_upstream: str = "backend:8000") -> str:
        caddyfile = str(ROOT / "infra" / "caddy" / "Caddyfile")
        subprocess.run(
            [
                "docker", "run", "-d", "--name", self.caddy, "--network", self.network,
                "-p", "127.0.0.1::8080",
                "-e", "SITE_ADDRESS=http://:8080",
                "-e", "ACME_EMAIL=ops@mycdigitalizacion.com.ar",
                "-e", f"ADMIN_ALLOWED_CIDRS={allowed_cidrs}",
                "-e", f"BACKEND_UPSTREAM={backend_upstream}",
                "-e", "FRONTEND_UPSTREAM=frontend:3000",
                "--mount", f"type=bind,src={caddyfile},dst=/etc/caddy/Caddyfile,readonly",
                "caddy:2.10-alpine", "caddy", "run", "--config", "/etc/caddy/Caddyfile",
            ],
            check=True,
            capture_output=True,
        )
        for _ in range(30):
            port_result = subprocess.run(
                ["docker", "port", self.caddy, "8080/tcp"], text=True, capture_output=True, check=True,
            )
            if port_result.stdout.strip():
                port = port_result.stdout.strip().rsplit(":", 1)[1]
                state = subprocess.run(
                    ["docker", "inspect", self.caddy, "--format", "{{.State.Status}}"],
                    text=True, capture_output=True, check=True,
                ).stdout.strip()
                if state == "running":
                    time.sleep(0.5)
                    return f"http://127.0.0.1:{port}"
            time.sleep(0.2)
        raise AssertionError(subprocess.run(["docker", "logs", self.caddy], text=True, capture_output=True).stderr)

    @staticmethod
    def status(url: str, path: str, headers: dict[str, str] | None = None) -> int:
        try:
            return request.urlopen(request.Request(f"{url}{path}", headers=headers or {}), timeout=5).status
        except error.HTTPError as response:
            return response.code

    def test_admin_route_denies_outside_cidr_and_allows_inside_cidr(self) -> None:
        self.start_backend()
        denied_url = self.start_caddy("203.0.113.10/32")
        self.assertEqual(self.status(denied_url, "/admin/"), 403)
        subprocess.run(["docker", "rm", "-f", self.caddy], check=True, capture_output=True)
        allowed_url = self.start_caddy("0.0.0.0/0")
        self.assertEqual(self.status(allowed_url, "/admin/"), 404)

    def test_proxy_failure_logs_path_status_request_id_without_request_pii(self) -> None:
        url = self.start_caddy("203.0.113.10/32", backend_upstream="127.0.0.1:65534")
        secret = "leak-probe@example.test"
        self.assertEqual(
            self.status(url, f"/api/v1/probe?email={secret}", {"Referer": f"https://referrer.test/?token={secret}"}),
            502,
        )
        time.sleep(0.2)
        logs = subprocess.run(["docker", "logs", self.caddy], text=True, capture_output=True, check=True)
        combined = logs.stdout + logs.stderr
        self.assertNotIn(secret, combined)
        events = []
        for line in combined.splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        failures = [event for event in events if event.get("status") == 502]
        access = next(event for event in failures if event.get("logger") == "http.log.access.log0")
        proxy_error = next(
            (event for event in failures if event.get("logger", "").startswith("http.log.error")),
            None,
        )
        self.assertIsNotNone(proxy_error, combined)
        self.assertEqual(access["request"]["uri"], "/api/v1/probe")
        self.assertEqual(proxy_error["request"]["uri"], "/api/v1/probe")
        self.assertEqual(proxy_error["request"]["method"], "GET")
        self.assertNotIn("headers", proxy_error["request"])
        self.assertRegex(access["request_id"], r"^[0-9a-f-]{36}$", combined)
        self.assertEqual(proxy_error["request"]["request_id"], access["request_id"], combined)
        self.assertRegex(proxy_error["error_id"], r"^[a-z0-9]+$", combined)

    def test_loopback_hop_restores_host_and_preserves_trusted_forwarding(self) -> None:
        self.start_echo_backend()
        url = self.start_caddy("0.0.0.0/0")
        with request.urlopen(f"{url}/api/v1/probe", timeout=5) as response:
            payload = json.loads(response.read())
            response_request_id = response.headers["X-Request-ID"]
        self.assertEqual(payload["host"], url.removeprefix("http://"))
        self.assertEqual(payload["request_id"], response_request_id)
        self.assertEqual(payload["forwarded_proto"], "http")
        self.assertNotEqual(payload["forwarded_for"], "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
