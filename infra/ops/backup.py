from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tarfile

from common import post_alert, run, sha256
from validate_env import validate


TIMESTAMP = re.compile(r"^\d{8}T\d{6}Z$")


def manifest_entry(path: Path) -> dict[str, str | int]:
    return {"file": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)}


def prune_local(root: Path, retention_days: int) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    for candidate in root.iterdir():
        if not candidate.is_dir() or not TIMESTAMP.fullmatch(candidate.name) or not (candidate / "manifest.json").is_file():
            continue
        created = datetime.strptime(candidate.name, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        if created < cutoff:
            shutil.rmtree(candidate)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a PostgreSQL and media backup")
    parser.add_argument("--timestamp")
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()
    errors = validate()
    for name in ("BACKUP_ROOT", "MEDIA_ROOT"):
        if not os.environ.get(name, "").strip():
            errors.append(f"{name} is required")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 2
    timestamp = arguments.timestamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if not TIMESTAMP.fullmatch(timestamp):
        print("invalid backup timestamp", file=sys.stderr)
        return 2
    root = Path(os.environ["BACKUP_ROOT"]).resolve()
    media = Path(os.environ["MEDIA_ROOT"]).resolve()
    if arguments.dry_run:
        print(json.dumps({"status": "dry-run", "target": str(root / timestamp), "media": str(media)}))
        return 0
    root.mkdir(parents=True, exist_ok=True)
    lock = root / ".backup.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.write(descriptor, str(os.getpid()).encode("ascii"))
        os.close(descriptor)
    except FileExistsError:
        print("backup already running", file=sys.stderr)
        return 3
    partial = root / f".{timestamp}.partial"
    target = root / timestamp
    try:
        if target.exists() or partial.exists():
            raise RuntimeError("backup target already exists")
        partial.mkdir(mode=0o700)
        database = partial / "database.dump"
        pg_arguments = [
            "--host", os.environ.get("POSTGRES_HOST", "postgres"),
            "--port", os.environ.get("POSTGRES_PORT", "5432"),
            "--username", os.environ["POSTGRES_USER"],
            "--format", "custom",
            "--file", str(database),
            os.environ["POSTGRES_DB"],
        ]
        run(os.environ.get("PG_DUMP_COMMAND", "pg_dump"), pg_arguments, mode="dump")
        media_archive = partial / "media.tar.gz"
        with tarfile.open(media_archive, "w:gz") as archive:
            archive.add(media, arcname="media", recursive=True)
        manifest = {
            "format_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": {"database": os.environ["POSTGRES_DB"], "site": os.environ["SITE_ADDRESS"]},
            "database": manifest_entry(database),
            "media": manifest_entry(media_archive),
        }
        (partial / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        partial.rename(target)
        repository = os.environ.get("RESTIC_REPOSITORY", "").strip()
        if repository:
            run(os.environ.get("RESTIC_COMMAND", "restic"), ["backup", str(target), "--tag", "mycdigitalizacion"], mode="restic")
            run(os.environ.get("RESTIC_COMMAND", "restic"), ["forget", "--keep-daily", os.environ.get("RESTIC_KEEP_DAILY", "7"), "--keep-weekly", os.environ.get("RESTIC_KEEP_WEEKLY", "5"), "--keep-monthly", os.environ.get("RESTIC_KEEP_MONTHLY", "12"), "--prune"], mode="restic")
        prune_local(root, int(os.environ.get("BACKUP_RETENTION_DAYS", "14")))
        print(json.dumps({"status": "ok", "backup": str(target)}))
        return 0
    except Exception as error:
        if partial.exists():
            shutil.rmtree(partial)
        post_alert("backup_failed", f"{type(error).__name__}: {error}")
        print(f"backup failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    finally:
        lock.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
