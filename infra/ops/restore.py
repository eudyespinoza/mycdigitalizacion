from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tarfile

from common import run, sha256
from validate_env import validate


DATABASE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")


def verify(backup: Path) -> dict[str, object]:
    manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format_version") != 1:
        raise ValueError("unsupported manifest format")
    for key in ("database", "media"):
        entry = manifest[key]
        path = backup / str(entry["file"])
        if not path.is_file() or sha256(path) != entry["sha256"]:
            raise ValueError(f"{key} checksum mismatch")
    return manifest


def extract_media(archive_path: Path, target: Path, confirm_existing: bool) -> None:
    if target.exists() and not confirm_existing:
        raise ValueError("target media already exists; pass --confirm-existing to overwrite")
    resolved = target.resolve()
    if resolved == Path(resolved.anchor) or resolved == Path.home().resolve():
        raise ValueError("unsafe media target")
    staging = target.parent / f".{target.name}.restore-partial"
    if staging.exists():
        raise ValueError("restore staging target already exists")
    staging.mkdir(parents=True)
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            for member in archive.getmembers():
                parts = Path(member.name).parts
                if not parts or parts[0] != "media" or ".." in parts:
                    raise ValueError("unsafe media archive entry")
                relative = Path(*parts[1:])
                if not relative.parts:
                    continue
                destination = (staging / relative).resolve()
                if staging.resolve() not in destination.parents:
                    raise ValueError("unsafe media archive path")
                if member.isdir():
                    destination.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    source = archive.extractfile(member)
                    if source is None:
                        raise ValueError("missing media archive payload")
                    with destination.open("wb") as output:
                        shutil.copyfileobj(source, output)
        if target.exists():
            shutil.copytree(staging, target, dirs_exist_ok=True)
            shutil.rmtree(staging)
        else:
            staging.rename(target)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore a verified backup to explicit targets")
    parser.add_argument("--backup", required=True)
    parser.add_argument("--target-db", required=True)
    parser.add_argument("--target-media", required=True)
    parser.add_argument("--confirm-existing", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()
    errors = validate()
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 2
    backup = Path(arguments.backup).resolve()
    target_media = Path(arguments.target_media).resolve()
    database_created = False
    try:
        if not DATABASE_NAME.fullmatch(arguments.target_db):
            raise ValueError("invalid target database name")
        manifest = verify(backup)
        if arguments.target_db == os.environ["POSTGRES_DB"] and not arguments.confirm_existing:
            raise ValueError("target database is the live source; confirmation required")
        if target_media.exists() and not arguments.confirm_existing:
            raise ValueError("target media already exists; pass --confirm-existing to overwrite")
        exists_result = run(
            os.environ.get("PG_DATABASE_EXISTS_COMMAND", "psql"),
            ["--host", os.environ.get("POSTGRES_HOST", "postgres"), "--port", os.environ.get("POSTGRES_PORT", "5432"), "--username", os.environ["POSTGRES_USER"], "--dbname", "postgres", "--tuples-only", "--no-align", "--command", f"SELECT 1 FROM pg_database WHERE datname = '{arguments.target_db}'"],
            mode="exists",
            capture=True,
        )
        database_exists = exists_result.stdout.strip() == "1"
        if database_exists and not arguments.confirm_existing:
            raise ValueError("target database already exists; pass --confirm-existing to overwrite")
        if arguments.dry_run:
            print(json.dumps({"status": "dry-run", "database_exists": database_exists, "target_db": arguments.target_db, "target_media": str(target_media)}))
            return 0
        if not database_exists:
            run(os.environ.get("PG_CREATEDB_COMMAND", "createdb"), ["--host", os.environ.get("POSTGRES_HOST", "postgres"), "--port", os.environ.get("POSTGRES_PORT", "5432"), "--username", os.environ["POSTGRES_USER"], arguments.target_db], mode="createdb")
            database_created = True
        restore_arguments = ["--host", os.environ.get("POSTGRES_HOST", "postgres"), "--port", os.environ.get("POSTGRES_PORT", "5432"), "--username", os.environ["POSTGRES_USER"], "--dbname", arguments.target_db]
        if database_exists:
            restore_arguments.extend(["--clean", "--if-exists"])
        restore_arguments.append(str(backup / str(manifest["database"]["file"])))
        run(os.environ.get("PG_RESTORE_COMMAND", "pg_restore"), restore_arguments, mode="restore")
        extract_media(backup / str(manifest["media"]["file"]), target_media, arguments.confirm_existing)
        print(json.dumps({"status": "ok", "target_db": arguments.target_db, "target_media": str(target_media)}))
        return 0
    except Exception as error:
        if database_created:
            try:
                run(
                    os.environ.get("PG_DROPDB_COMMAND", "dropdb"),
                    ["--host", os.environ.get("POSTGRES_HOST", "postgres"), "--port", os.environ.get("POSTGRES_PORT", "5432"), "--username", os.environ["POSTGRES_USER"], arguments.target_db],
                    mode="dropdb",
                )
            except Exception as cleanup_error:
                print(f"restore cleanup failed: {type(cleanup_error).__name__}", file=sys.stderr)
        print(f"restore refused: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
