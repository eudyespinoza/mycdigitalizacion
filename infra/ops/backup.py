from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tarfile

from common import emit_event, post_alert, run, sha256
from locking import LockUnavailable, ProcessLock
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
        emit_event(
            "backup",
            "config.invalid",
            level="error",
            stream=sys.stderr,
            detail="; ".join(errors),
        )
        return 2
    timestamp = arguments.timestamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if not TIMESTAMP.fullmatch(timestamp):
        emit_event("backup", "backup.invalid_timestamp", level="error", stream=sys.stderr)
        return 2
    root = Path(os.environ["BACKUP_ROOT"]).resolve()
    media = Path(os.environ["MEDIA_ROOT"]).resolve()
    if arguments.dry_run:
        emit_event("backup", "backup.dry_run", target=str(root / timestamp), media=str(media))
        return 0
    root.mkdir(parents=True, exist_ok=True)
    try:
        lock_context = ProcessLock(root / ".backup.lock")
        lock_context.__enter__()
    except LockUnavailable as error:
        post_alert("backup_lock_contended", str(error))
        emit_event(
            "backup",
            "backup.lock_contended",
            level="error",
            stream=sys.stderr,
            detail=str(error),
        )
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
        run(
            os.environ.get("PG_DUMP_COMMAND", "pg_dump"),
            pg_arguments,
            mode="dump",
            service="backup",
        )
        media_archive = partial / "media.tar.gz"
        with tarfile.open(media_archive, "w:gz") as archive:
            archive.add(media, arcname="media", recursive=True)
        manifest = {
            "format_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "release_id": os.environ["RELEASE_ID"],
            "configuration_fingerprint": hashlib.sha256(
                json.dumps(
                    {
                        "release_id": os.environ["RELEASE_ID"],
                        "site": os.environ["SITE_ADDRESS"],
                        "database": os.environ["POSTGRES_DB"],
                        "restic_enabled": bool(os.environ.get("RESTIC_REPOSITORY", "").strip()),
                    },
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest(),
            "source": {"database": os.environ["POSTGRES_DB"], "site": os.environ["SITE_ADDRESS"]},
            "database": manifest_entry(database),
            "media": manifest_entry(media_archive),
        }
        (partial / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        partial.rename(target)
        repository = os.environ.get("RESTIC_REPOSITORY", "").strip()
        if repository:
            run(
                os.environ.get("RESTIC_COMMAND", "restic"),
                ["backup", str(target), "--tag", "mycdigitalizacion"],
                mode="restic",
                service="backup",
            )
            run(
                os.environ.get("RESTIC_COMMAND", "restic"),
                ["forget", "--keep-daily", os.environ.get("RESTIC_KEEP_DAILY", "7"), "--keep-weekly", os.environ.get("RESTIC_KEEP_WEEKLY", "5"), "--keep-monthly", os.environ.get("RESTIC_KEEP_MONTHLY", "12"), "--prune"],
                mode="restic",
                service="backup",
            )
            snapshots = run(
                os.environ.get("RESTIC_COMMAND", "restic"),
                ["snapshots", "--json", "--tag", "mycdigitalizacion"],
                mode="restic",
                capture=True,
                service="backup",
            )
            snapshot_data = json.loads(snapshots.stdout)
            if not any(
                target.resolve() == Path(str(path)).resolve()
                for snapshot in snapshot_data
                for path in snapshot.get("paths", [])
            ):
                raise RuntimeError("restic snapshot verification failed")
        prune_local(root, int(os.environ.get("BACKUP_RETENTION_DAYS", "14")))
        verify_manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
        for key in ("database", "media"):
            entry = verify_manifest[key]
            if sha256(target / entry["file"]) != entry["sha256"]:
                raise RuntimeError(f"local {key} snapshot verification failed")
        emit_event(
            "backup",
            "backup.completed",
            backup=str(target),
            release_id=os.environ["RELEASE_ID"],
        )
        return 0
    except Exception as error:
        if partial.exists():
            shutil.rmtree(partial)
        post_alert("backup_failed", f"{type(error).__name__}: {error}")
        emit_event(
            "backup",
            "backup.failed",
            level="error",
            stream=sys.stderr,
            error_type=type(error).__name__,
            detail=str(error),
        )
        return 1
    finally:
        lock_context.__exit__(None, None, None)


if __name__ == "__main__":
    raise SystemExit(main())
