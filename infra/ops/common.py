from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Iterable
from urllib import request


def command_parts(value: str) -> list[str]:
    parts = shlex.split(value, posix=os.name != "nt")
    if os.name == "nt":
        parts = [part[1:-1] if len(part) > 1 and part[0] == part[-1] == '"' else part for part in parts]
    if not parts:
        raise ValueError("empty command")
    return parts


def run(command: str, arguments: Iterable[str], *, mode: str, capture: bool = False) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["FAKE_PG_MODE"] = mode
    environment["PGPASSWORD"] = os.environ.get("POSTGRES_PASSWORD", "")
    return subprocess.run(
        [*command_parts(command), *arguments],
        env=environment,
        text=True,
        capture_output=capture,
        check=True,
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def post_alert(event: str, detail: str) -> None:
    url = os.environ.get("BACKUP_ALERT_WEBHOOK_URL", os.environ.get("ALERT_WEBHOOK_URL", "")).strip()
    if not url:
        return
    body = json.dumps({"event": event, "detail": detail[:500]}).encode("utf-8")
    try:
        request.urlopen(request.Request(url, data=body, headers={"content-type": "application/json"}), timeout=5).close()
    except Exception as error:  # alerting must not hide the original failure
        print(f"alert hook failed: {type(error).__name__}", file=sys.stderr)
