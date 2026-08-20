import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def rendered_compose(filename):
    if not shutil.which("docker"):
        pytest.skip("Docker Compose is required to validate the deployed media topology")
    environment = {
        **os.environ,
        "POSTGRES_DB": "contract",
        "POSTGRES_USER": "contract",
        "POSTGRES_PASSWORD": "contract-password",
        "SITE_ADDRESS": "store.example.test",
        "DJANGO_SECRET_KEY": "contract-secret",
        "PERSONAL_DATA_ENCRYPTION_KEY": "contract-personal-data-key",
        "DJANGO_ALLOWED_HOSTS": "store.example.test,backend",
    }
    result = subprocess.run(
        ["docker", "compose", "-f", filename, "config"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return yaml.safe_load(result.stdout)


@pytest.mark.parametrize("filename", ("compose.yaml", "compose.prod.yaml"))
def test_rendered_compose_has_persistent_backend_media_and_read_only_caddy_mount(filename):
    config = rendered_compose(filename)

    assert "media_data" in config["volumes"]
    backend_media = next(
        volume
        for volume in config["services"]["backend"]["volumes"]
        if volume["target"] == "/app/media"
    )
    caddy_media = next(
        volume
        for volume in config["services"]["caddy"]["volumes"]
        if volume["target"] == "/srv/media"
    )
    assert backend_media == {
        "type": "volume",
        "source": "media_data",
        "target": "/app/media",
        "volume": {},
    }
    assert caddy_media["type"] == "volume"
    assert caddy_media["source"] == "media_data"
    assert caddy_media["read_only"] is True
    assert config["services"]["backend"]["environment"]["MEDIA_ROOT"] == "/app/media"
    frontend = config["services"]["frontend"]
    assert frontend["environment"]["API_INTERNAL_URL"] == "http://backend:8000/api/v1"
    assert frontend["environment"]["API_PROXY_TARGET"] == "http://backend:8000"
    if filename == "compose.prod.yaml":
        assert frontend["build"]["args"] == {
            "API_INTERNAL_URL": "http://backend:8000/api/v1",
            "API_PROXY_TARGET": "http://backend:8000",
        }
