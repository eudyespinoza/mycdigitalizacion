from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import queue


MIB = 1024 * 1024
CGROUP = Path("/sys/fs/cgroup")
BACKUP_PATH = Path("/tmp/backup-overlap.bin")


def read_number(name: str) -> int:
    value = (CGROUP / name).read_text(encoding="utf-8").strip()
    if value == "max":
        raise RuntimeError(f"{name} is not bounded")
    return int(value)


def read_events() -> dict[str, int]:
    return {
        key: int(value)
        for key, value in (
            line.split(maxsplit=1)
            for line in (CGROUP / "memory.events").read_text(encoding="utf-8").splitlines()
        )
    }


def service_load(
    service: str,
    limit_bytes: int,
    ready: multiprocessing.Queue,
    release: multiprocessing.Event,
) -> None:
    try:
        allocation = bytearray(max(MIB, limit_bytes - 16 * MIB))
        for offset in range(0, len(allocation), 4096):
            allocation[offset] = (offset // 4096) % 251
        digest = hashlib.sha256()
        sample = memoryview(allocation)[:MIB]
        for _ in range(32):
            digest.update(sample)
        if service == "backup":
            with BACKUP_PATH.open("wb", buffering=0) as target:
                for _ in range(64):
                    target.write(sample)
                os.fsync(target.fileno())
        ready.put({"service": service, "digest": digest.hexdigest()})
        release.wait(timeout=120)
    except Exception as error:
        ready.put({"service": service, "error": f"{type(error).__name__}: {error}"})
        raise


def main() -> int:
    limits = {
        key: int(value)
        for key, value in json.loads(os.environ["SERVICE_LIMITS_JSON"]).items()
    }
    memory_max = read_number("memory.max")
    before = read_events()
    context = multiprocessing.get_context("fork")
    ready = context.Queue()
    release = context.Event()
    processes = [
        context.Process(target=service_load, args=(service, limit, ready, release))
        for service, limit in limits.items()
    ]
    for process in processes:
        process.start()
    results: list[dict[str, str]] = []
    try:
        for _ in processes:
            results.append(ready.get(timeout=120))
        failures = [result for result in results if "error" in result]
        if failures:
            raise RuntimeError(json.dumps(failures, sort_keys=True))
        memory_current = read_number("memory.current")
        memory_peak = read_number("memory.peak")
    except (Exception, queue.Empty):
        release.set()
        for process in processes:
            process.join(timeout=5)
        raise
    release.set()
    for process in processes:
        process.join(timeout=30)
        if process.exitcode != 0:
            raise RuntimeError(f"service workload exited {process.exitcode}")
    after = read_events()
    backup_sha256 = hashlib.sha256(BACKUP_PATH.read_bytes()).hexdigest()
    print(json.dumps({
        "memory_max_bytes": memory_max,
        "memory_current_bytes": memory_current,
        "memory_peak_bytes": memory_peak,
        "oom_kill_delta": after.get("oom_kill", 0) - before.get("oom_kill", 0),
        "concurrent_services": sorted(result["service"] for result in results),
        "backup_bytes": BACKUP_PATH.stat().st_size,
        "backup_sha256": backup_sha256,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
