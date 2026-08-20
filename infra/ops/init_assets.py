from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from common import emit_event


RELEASE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{6,79}$")


def main() -> int:
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        emit_event("assets-init", "assets.invalid_user", level="error", stream=sys.stderr)
        return 2
    release = os.environ.get("RELEASE_ID", "").strip()
    if not RELEASE.fullmatch(release) or release.lower().startswith("replace_me"):
        emit_event("assets-init", "assets.invalid_release", level="error", stream=sys.stderr)
        return 2
    media_root = Path(os.environ.get("MEDIA_ROOT", "/app/media")).resolve()
    static_root = Path(os.environ.get("STATIC_DATA_ROOT", "/static-data")).resolve()
    backup_root = Path(os.environ.get("BACKUP_ROOT", "/backups")).resolve()
    if (
        media_root != Path("/app/media")
        or static_root != Path("/static-data")
        or backup_root != Path("/backups")
    ):
        emit_event("assets-init", "assets.invalid_roots", level="error", stream=sys.stderr)
        return 2
    media_root.mkdir(parents=True, exist_ok=True)
    # Django owns writes; the backup process (GID 10001) receives read/traverse only.
    os.chown(media_root, 1000, 10001)
    os.chmod(media_root, 0o2750)
    backup_root.mkdir(parents=True, exist_ok=True)
    os.chown(backup_root, 10001, 10001)
    os.chmod(backup_root, 0o700)

    subprocess.run(
        [sys.executable, "manage.py", "collectstatic", "--noinput", "--clear"],
        cwd="/app",
        env=os.environ.copy(),
        check=True,
    )
    source = Path("/app/staticfiles")
    releases = static_root / "releases"
    releases.mkdir(parents=True, exist_ok=True)
    final = releases / release
    partial = releases / f".{release}.partial"
    if partial.exists():
        shutil.rmtree(partial)
    if not final.exists():
        shutil.copytree(source, partial)
        (partial / ".release.json").write_text(json.dumps({"release": release}), encoding="utf-8")
        partial.rename(final)
    next_link = static_root / ".current.next"
    next_link.unlink(missing_ok=True)
    next_link.symlink_to(Path("releases") / release, target_is_directory=True)
    os.replace(next_link, static_root / "current")
    emit_event(
        "assets-init",
        "assets.initialized",
        release_id=release,
        media_uid=1000,
        static_release=str(final),
        backup_uid=10001,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
