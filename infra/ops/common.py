from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import threading
from typing import Iterable
import uuid
from urllib import request
from datetime import datetime, timezone


EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
QUERY = re.compile(r"(?P<path>(?:https?://[^\s?]+|/[^\s?]*))\?[^\s]+")
PERSONAL_NUMBER = re.compile(r"(?<!\d)\d{7,15}(?!\d)")
SECRET_VALUE = re.compile(
    r"(?i)\b(?:authorization|cookie|password|secret|token)\s*[=:]\s*[^\s,;]+"
)
OPS_JOB_ID = os.environ.get("OPS_JOB_ID", "").strip() or str(uuid.uuid4())
SENSITIVE_ENV_MARKERS = ("PASSWORD", "SECRET", "TOKEN", "AUTHORIZATION", "COOKIE", "ACCESS_KEY")
SUBPROCESS_OUTPUT_LIMIT_BYTES = 1024 * 1024


def command_parts(value: str) -> list[str]:
    parts = shlex.split(value, posix=os.name != "nt")
    if os.name == "nt":
        parts = [part[1:-1] if len(part) > 1 and part[0] == part[-1] == '"' else part for part in parts]
    if not parts:
        raise ValueError("empty command")
    return parts


def run(
    command: str,
    arguments: Iterable[str],
    *,
    mode: str,
    capture: bool = False,
    service: str = "ops",
    cwd: str | Path | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["FAKE_PG_MODE"] = mode
    environment["PGPASSWORD"] = os.environ.get("POSTGRES_PASSWORD", "")
    process = subprocess.Popen(
        [*command_parts(command), *arguments],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
    )
    captured: dict[str, bytearray] = {"stdout": bytearray(), "stderr": bytearray()}
    totals = {"stdout": 0, "stderr": 0}
    overflow = threading.Event()

    def read_stream(name: str, stream) -> None:
        while chunk := stream.read(64 * 1024):
            totals[name] += len(chunk)
            remaining = SUBPROCESS_OUTPUT_LIMIT_BYTES - len(captured[name])
            if remaining > 0:
                captured[name].extend(chunk[:remaining])
            if totals[name] > SUBPROCESS_OUTPUT_LIMIT_BYTES and not overflow.is_set():
                overflow.set()
                process.kill()

    threads = [
        threading.Thread(target=read_stream, args=(name, stream), daemon=True)
        for name, stream in (("stdout", process.stdout), ("stderr", process.stderr))
    ]
    for thread in threads:
        thread.start()
    returncode = process.wait()
    for thread in threads:
        thread.join()
    result = subprocess.CompletedProcess(
        process.args,
        returncode,
        stdout=captured["stdout"].decode("utf-8", errors="replace"),
        stderr=captured["stderr"].decode("utf-8", errors="replace"),
    )
    for stream_name, detail in (("stdout", result.stdout), ("stderr", result.stderr)):
        if detail.strip():
            emit_event(
                service,
                f"subprocess.{stream_name}",
                level="error" if stream_name == "stderr" or result.returncode else "info",
                stream=sys.stderr if stream_name == "stderr" else sys.stdout,
                job_id=OPS_JOB_ID,
                tool=mode,
                returncode=result.returncode,
                detail=detail[:4000],
            )
    if overflow.is_set():
        emit_event(
            service,
            "subprocess.output_limit_exceeded",
            level="error",
            stream=sys.stderr,
            job_id=OPS_JOB_ID,
            tool=mode,
            returncode=returncode,
            limit_bytes=SUBPROCESS_OUTPUT_LIMIT_BYTES,
            stdout_bytes=totals["stdout"],
            stderr_bytes=totals["stderr"],
        )
        raise RuntimeError(f"{mode} output exceeded the bounded capture limit")
    if result.returncode:
        raise subprocess.CalledProcessError(
            result.returncode,
            result.args,
            output=result.stdout,
            stderr=result.stderr,
        )
    return result


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_text(value: object) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ")
    for name, secret in os.environ.items():
        if secret and len(secret) >= 4 and any(marker in name.upper() for marker in SENSITIVE_ENV_MARKERS):
            text = text.replace(secret, "[redacted-secret]")
    text = QUERY.sub(r"\g<path>", text)
    text = EMAIL.sub("[redacted-email]", text)
    text = SECRET_VALUE.sub("[redacted-secret]", text)
    return PERSONAL_NUMBER.sub("[redacted-number]", text)


def emit_event(service: str, event: str, *, level: str = "info", stream=None, **fields: object) -> None:
    payload: dict[str, object] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "service": service,
        "event": event,
        "job_id": OPS_JOB_ID,
    }
    for key, value in fields.items():
        if value is not None:
            payload[key] = safe_text(value) if isinstance(value, str) else value
    print(json.dumps(payload, separators=(",", ":")), file=stream or sys.stdout)


def post_alert(event: str, detail: str) -> None:
    url = os.environ.get("BACKUP_ALERT_WEBHOOK_URL", os.environ.get("ALERT_WEBHOOK_URL", "")).strip()
    if not url:
        return
    body = json.dumps(
        {"event": event, "detail": safe_text(detail[:500]), "job_id": OPS_JOB_ID}
    ).encode("utf-8")
    try:
        request.urlopen(request.Request(url, data=body, headers={"content-type": "application/json"}), timeout=5).close()
    except Exception as error:  # alerting must not hide the original failure
        emit_event(
            "backup",
            "alert.failed",
            level="error",
            stream=sys.stderr,
            error_type=type(error).__name__,
        )
