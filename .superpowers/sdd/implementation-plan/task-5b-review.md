# Task 5B — independent production operations review

Review target: `7a09f49c04fd9e14bc177c741997102716ad67c1`

Specification: `.superpowers/sdd/implementation-plan/task-5-brief.md`, Media and production operations plus Verification; user-required Docker/VPS, security and recoverability checks.

Scope: production Compose, Docker images, Caddy, backup/restore, environment validation, logging/health and Donweb runbook. Concurrent Task 5A backend/admin changes were excluded and left untouched. This was a `qa-only` report pass: no product fixes, detector or `DESIGN.md`.

## Verdict

- **SPEC COMPLIANCE: FAIL — 10 REQUIRED findings.** The nominal topology builds, but the first deployment cannot write media, the Admin CIDR barrier is bypassed, failure logs leak request data, backup/restore has unrecoverable paths, and several production/runtime contracts fail outside structural tests.
- **CODE QUALITY: NEEDS WORK — 5 OPTIONAL findings.** The implementation is readable and the runbook is unusually useful, but verification is too declarative for security/volume/lifecycle behavior and rollback reproducibility needs hardening.
- **Counts:** 10 REQUIRED, 5 OPTIONAL.

## Verification evidence

All commands ran from an isolated archive of the exact commit, so concurrent Task 5A work could not affect results.

- `python -m unittest infra.tests.test_task5b_operations -v`: **12 tests, OK**.
- `docker compose --env-file .env.production.example -f compose.prod.yaml config --quiet`: **passed**.
- `python scripts/verify-production.py --env-file .env.production.example --build`: **passed**. It rebuilt backend, worker, beat, frontend, ops and Caddy; Next production build/TypeScript/SSG passed; Caddy real validation passed; declared image users matched.
- `backend/tests/test_health.py` plus `backend/tests/test_media_topology.py`: **3 passed**.
- Exact image users: backend/worker `appuser` (UID 1000), frontend `node` (UID 1000), ops `10001:10001`, Caddy `1000:1000`. Backend image contains `/app/staticfiles/admin/css/base.css`; frontend standalone contains `server.js`.
- Real Caddy `adapt`, live HTTPS request and container logs proved the Admin ordering and PII-log findings below. Single-CIDR validation passes; a comma-separated value accepted by `validate_env.py` fails real Caddy validation.
- Real read-only frontend smoke: `/health` returned 200 and `/_next/image` returned 200, but each optimization logged an `unhandledRejection`/cache-write failure.
- Real named-volume probes proved `/app/media` is root-owned/unwritable for UID 1000 and that an existing `static_data` volume is not refreshed from a new image.
- Six distinct backup/restore negative behaviors were exercised with controlled PostgreSQL commands: stale lock/no alert, existing-DB failure/no rollback, existing-media merge, invalid interval startup crash, two-network public allow-all acceptance, and negative retention deleting the new backup while reporting success.
- A frontend Vitest command from the archive could not start because the archive intentionally had no host `node_modules`; this is not counted as a product failure. The containerized Next build did run the affected production artifact end to end.

## REQUIRED findings

### R1. A fresh `media_data` volume is not writable by Django or Celery

**Files:** `backend/Dockerfile:3-15`, `compose.prod.yaml:44-52,117-120,131-138,224,247`.

The backend image never creates `/app/media`. Docker therefore initializes a fresh named volume at that missing path as `root:root` mode 0755, while backend and worker run as `1000:1000`. Caddy can read externally seeded files, which explains the implementation smoke, but Django cannot create an upload and the worker cannot write derivatives.

**Reproduction:** mount a new named volume at `/app/media` in `mycdigitalizaciones-backend-prod` and run as the image default user. `id` reports UID 1000, `ls -ld /app/media` reports `root root`, and `touch /app/media/upload-probe` returns `Permission denied`.

**Required acceptance:** initialize the volume with explicit UID/GID ownership before any app process starts, then prove a real Django upload and worker-generated derivative can be written, read by backend/worker, served read-only by Caddy, and retained across recreation.

### R2. The Caddy Admin CIDR restriction is ordered after the reverse proxy and never runs

**Files:** `infra/caddy/Caddyfile:37-48`, `compose.prod.yaml:243-247`, `infra/ops/validate_env.py:45-50`.

Although the Caddyfile writes `respond @blockedAdmin 403` before `handle @backend`, Caddy's directive ordering adapts the backend handle into the first terminal route and places the 403 route last. An unauthorized `/admin/` request is proxied instead of blocked.

There are two additional contract mismatches: the validator accepts comma-separated CIDRs but Caddy rejects `203.0.113.10/32,198.51.100.20/32`, and it accepts `0.0.0.0/1 128.0.0.0/1`, which together expose Admin to the entire IPv4 Internet.

**Reproduction:** `caddy adapt --pretty` shows the `/admin` reverse-proxy group before the static 403 route. A live request from `172.17.0.1`, with only `203.0.113.10/32` allowed, reached `backend:8000` and returned upstream 502 rather than 403. The comma form fails real `caddy validate`; the two `/1` values produce no validator errors.

**Required acceptance:** make Admin authorization part of a route whose order is explicit, normalize one documented separator, reject effectively public networks/unions, and integration-test allowed and denied client IPs against real adapted Caddy. A string-presence assertion is insufficient.

### R3. Caddy failure logs leak query parameters and referrer data

**Files:** `infra/caddy/Caddyfile:23-35`.

The custom filter applies only to `http.log.access.log0`. Reverse-proxy failures also go through Caddy's default error logger, which retains the full URI including query and request headers such as `Referer`. The access-log regular expression also erased the complete URI in the live probe, reducing observability instead of retaining the path safely.

**Reproduction:** send a synthetic `/admin/?email=probe@example.test` request with a synthetic `Referer` query while the upstream is unavailable. The access event removes Cookie/query, but `http.log.error.log0` records the full request URI and referrer. No real credential was used.

**Required acceptance:** configure both access and error loggers to retain method/path/status/request ID while removing query strings and sensitive/referrer headers, and test an upstream failure so the unfiltered logger cannot regress.

### R4. Static assets are collected into the image but never refreshed in the persistent volume

**Files:** `backend/Dockerfile:12-15`, `compose.prod.yaml:117-120,247,264-271`, `docs/operations/donweb-production.md:143-158`.

An empty named volume is populated from the image once. On later releases `static_data` is already non-empty, so Docker does not copy newly collected files from the new backend image. The update procedure builds, migrates and recreates services but never runs `collectstatic` against the mounted volume. Changed hashed assets can remain stale or be missing indefinitely.

**Reproduction:** seed a named volume with one existing file, mount it at `/app/staticfiles` in the new backend image, and check `admin/css/base.css`; Docker does not copy image contents into the existing volume. The exact runbook has no release-time collectstatic/init step.

**Required acceptance:** add a successful one-shot static initialization/collectstatic dependency for every release, with correct ownership and atomic publication, then smoke a newly introduced hashed file through Caddy after an upgrade using an existing volume.

### R5. Read-only frontend runtime disables the Next image cache and emits unhandled errors

**Files:** `frontend/Dockerfile:19-28`, `compose.prod.yaml:163-186`.

The standalone container is read-only and only `/tmp` is writable. Next attempts to create `/app/frontend/.next/cache` for `/_next/image`; the response is still generated, but it cannot be cached and logs an unhandled rejection on every uncached optimization. This wastes CPU and creates an easy amplification path under image traffic.

**Reproduction:** start the production image with the exact read-only/tmpfs settings. `/health` returns 200 and an optimized logo returns 200, followed by `ENOENT: no such file or directory, mkdir '/app/frontend/.next/cache'` and `Failed to write image to cache` in container logs.

**Required acceptance:** provide a bounded writable cache owned by `node` (volume/tmpfs with deliberate size/retention), retain read-only application code, and test cold then warm optimizer requests with no error logs.

### R6. A killed backup leaves a permanent lock and does not fire the alert hook

**Files:** `infra/ops/backup.py:55-69,99-106`, `infra/ops/scheduler.py:23-37,49-52`, `compose.prod.yaml:188-235`.

The lock is a persistent file in `backup_data`. If the process/container dies after `O_EXCL`, `finally` never removes it. Future runs return 3 before entering the exception/alert block, so no webhook fires. The scheduler marks failure, sleeps, becomes unhealthy and may restart, but every restart sees the same stale lock.

**Reproduction:** create `.backup.lock` containing a nonexistent PID and run backup with an unreachable alert URL. It returns 3, preserves the lock, and never attempts the alert hook. This behavior repeats indefinitely.

**Required acceptance:** use an OS lock or a lease with host/PID/start-time and safe stale-owner recovery; alert on lock contention/staleness; prove concurrent live exclusion, kill/restart recovery and a successful next scheduled backup.

### R7. Fail-fast validation accepts backup settings that crash scheduling or delete the new backup

**Files:** `infra/ops/validate_env.py:10-73`, `infra/ops/backup.py:24-31,92-97`, `infra/ops/scheduler.py:29-52`, `.env.production.example:35-45`.

The validator does not parse or bound interval/retention/Restic retention controls. `BACKUP_INTERVAL_HOURS=not-a-number` passes config-check then crashes the scheduler before it can write health or alert. Worse, `BACKUP_RETENTION_DAYS=-1` passes, completes a new backup, immediately prunes it, and prints `{"status":"ok"}` for a path that no longer exists.

**Reproduction:** both values return success from `validate_env.py`. The invalid interval raises `ValueError`; the negative retention backup exits 0 while the timestamp directory is absent afterward.

**Required acceptance:** fail config-check on non-integer/out-of-range interval and retention values (local and Restic), validate password-file existence/readability when selected, and test that success always implies a present, checksum-verifiable local snapshot.

### R8. Confirmed restore onto existing targets has no rollback and media is only merged

**Files:** `infra/ops/restore.py:31-70,85-130`.

Rollback only drops a database created by the current run. With `--confirm-existing`, `pg_restore --clean` can partially destroy an existing database; failure leaves it modified because `database_created` is false. Existing media uses `copytree(..., dirs_exist_ok=True)`, which retains files absent from the backup and can leave a mixed partial tree if copying fails. There is no pre-restore snapshot/swap-back.

**Reproduction:** simulate an existing DB and fail `pg_restore`; restore exits nonzero and never invokes `dropdb` or another rollback. Restore into existing media containing `stale.txt`; the command succeeds and both stale and restored files remain.

**Required acceptance:** keep new-target restore as the normal path. If overwrite confirmation remains, stage a replacement DB/media set, verify it, swap atomically where possible, and retain a tested rollback target. Do not call a directory merge a restore.

### R9. Structured JSON/correlation covers Caddy and Gunicorn access only

**Files:** `compose.prod.yaml:1-6,102-116,131-161,188-235`, `infra/caddy/Caddyfile:21-35`, `backend/config/settings.py` (no production `LOGGING`/request-ID context).

Docker's `json-file` driver wraps stdout metadata but does not make application messages structured. Django errors, Celery worker/beat and ops errors remain plain text; no backend middleware/log filter binds `X-Request-ID` to application logs or queued work. Caddy error logs likewise lacked the appended request ID in the live failure event.

**Reproduction:** inspect the production commands/settings and the live Caddy failure log: only Gunicorn access lines have the custom JSON format; application/error/worker/beat paths have no common schema or correlation context.

**Required acceptance:** emit one redacted JSON schema across web, worker, beat and ops with timestamp/level/service/event/request-or-job ID; propagate trusted Caddy IDs into Django and queued tasks; regression-test PII/query/cookie removal on success and exception paths.

### R10. Default memory limits consume the entire minimum recommended VPS

**Files:** `compose.prod.yaml:81-84,98-100,127-129,145-147,159-161,182-184,231-233,258-260`, `docs/operations/donweb-production.md:5-10`.

The documented minimum is 4 GB RAM. Default service limits sum to 4096 MB (PostgreSQL 768, Redis 256, backend 768, worker 768, beat 256, frontend 512, backup 512, Caddy 256), leaving no headroom for Ubuntu, Docker, page cache, builds, config-check or transient overlap. Under load the advertised minimum can OOM or thrash despite every service respecting its limit.

**Required acceptance:** either raise the stated minimum with measured headroom or lower/tune defaults for a 4 GB host, document non-concurrent backup/build capacity, and run a constrained-host smoke/load/backup overlap test.

## OPTIONAL findings

### O1. Production base images are mutable tags, weakening reproducible rollback

**Files:** `backend/Dockerfile:1`, `frontend/Dockerfile:1,19`, `infra/caddy/Dockerfile:1`, `infra/ops/Dockerfile:1`, `compose.prod.yaml:69,87`.

Rebuilding an old Git revision later can pull different Python/Node/Caddy/PostgreSQL/Redis layers. Pin reviewed digests or publish immutable application images per commit, with an explicit dependency-update process.

### O2. The edge header set lacks a deliberate CSP/modern isolation policy

**File:** `infra/caddy/Caddyfile:14-22`.

HSTS, nosniff, frame, referrer and permissions headers are useful, but no Content-Security-Policy is defined. Add and browser-test a policy compatible with Next/Django Admin, initially report-only if needed, plus a documented decision on COOP/CORP.

### O3. Backup manifest is too thin for disaster-recovery traceability

**File:** `infra/ops/backup.py:83-90`.

The manifest hashes DB/media and records DB/site, but not Git/image revision, schema/migration state, provider modes, sanitized config fingerprint or tool versions. Add non-secret recovery metadata so an operator can identify the matching code/config before restore.

### O4. `RESTIC_PASSWORD_FILE` is advertised without a mount or existence check

**Files:** `compose.prod.yaml:212-220,224`, `infra/ops/validate_env.py:60-72`.

The validator accepts any four-character path, but Compose mounts no secret/config path into the backup container. Document and mount a read-only secret file (or remove this mode) and verify Restic can read it before deployment.

### O5. Verification asserts text/config shape instead of the dangerous runtime boundaries

**Files:** `infra/tests/test_task5b_operations.py:52-108`, `scripts/verify-production.py:18-56`, `.superpowers/sdd/implementation-plan/task-5b-report.md`.

The tests check keys and Caddyfile substrings, so they missed route ordering, volume ownership, static upgrades, optimizer cache writes, stale-lock recovery and unfiltered error logs. `verify-production.py` also prints `Production container contract: OK` with the deliberately invalid example because it never runs the config-check container. Add real adapted-Caddy requests, UID volume writes, upgrade-on-existing-volume, backup kill/restart and restore-failure tests; make the verification command distinguish static contract from deployable environment.

## Compliance matrix

| Area | Result | Evidence |
|---|---|---|
| Required services/dependencies/restart/health/volumes | PARTIAL | Topology exists and nominal checks pass; media ownership, static lifecycle, cache and memory defaults fail runtime use |
| Non-root application processes | PASS | Image/runtime users are non-root; volume initialization is the blocker, not process UID |
| Caddy TLS/compress/body limit/same-origin routing | PARTIAL | Real validation passes, but Admin restriction is bypassed and failure logs leak request data |
| Backup dump/media/hash/atomic target/retention/Restic | PARTIAL | Happy path works; stale lock and unvalidated retention can permanently stop or erase backups |
| Restore new-target/checksum/cleanup | PARTIAL | New-target failure cleanup works; confirmed-existing mode is destructive and non-rollbackable |
| JSON logs/request ID/liveness/readiness/alerts | PARTIAL | Health endpoints pass; structured correlation and lock/scheduler alerts are incomplete |
| Fail-fast production example | PARTIAL | Placeholders are rejected; operational numeric/password-file and CIDR semantics are not |
| Donweb runbook | PARTIAL | Broad coverage is good; update/static, media-write, capacity and overwrite-restore assumptions are unsafe |
| Builds/collectstatic/standalone | PARTIAL | All images build and assets exist in images; mounted runtime lifecycle breaks static updates and optimizer caching |

## Final assessment

The commit delivers a solid skeleton: all named services exist, automatic TLS configuration validates, same-origin routes and basic security headers are present, images run application processes non-root, liveness/readiness are separated, the example rejects obvious placeholders, happy-path dump/media/checksum/Restic hooks work, new-target restore cleanup works, and the Donweb runbook covers the full operator journey.

It is not safe to accept as Task 5B yet. Three first-order production promises fail in live probes: Django cannot write media, unauthorized clients reach Admin, and request data leaks on proxy errors. Backup success/recovery also cannot be trusted under interruption or a simple retention typo. Those are release blockers even though every committed Task 5B test and image build is green.
