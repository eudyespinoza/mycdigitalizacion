from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time


STATE_FILE = Path(os.environ.get("BACKUP_HEALTH_FILE", "/tmp/backup-health.json"))


def write_state(*, status: str, returncode: int) -> None:
    STATE_FILE.write_text(
        json.dumps({"status": status, "returncode": returncode, "checked_at": datetime.now(timezone.utc).isoformat()}),
        encoding="utf-8",
    )


def run_backup() -> int:
    result = subprocess.run([sys.executable, "/ops/backup.py"], check=False)
    write_state(status="ok" if result.returncode == 0 else "failed", returncode=result.returncode)
    return result.returncode


def healthy() -> bool:
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        checked = datetime.fromisoformat(state["checked_at"])
        interval = max(1, int(os.environ.get("BACKUP_INTERVAL_HOURS", "24")))
        age = (datetime.now(timezone.utc) - checked).total_seconds()
        return state["status"] == "ok" and age <= (interval * 3600) + 3600
    except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Run and monitor scheduled production backups")
    parser.add_argument("--health", action="store_true")
    parser.add_argument("--run-once", action="store_true")
    arguments = parser.parse_args()
    if arguments.health:
        return 0 if healthy() else 1
    if arguments.run_once:
        return run_backup()
    interval = max(1, int(os.environ.get("BACKUP_INTERVAL_HOURS", "24"))) * 3600
    while True:
        run_backup()
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
