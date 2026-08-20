# Task 6A — backend, security and operations verification

Date: 2026-08-20  
Scope: backend, backend dependency locks, operations, Compose/Caddy runtime and security contracts. Frontend functional/visual work remained concurrent and out of scope, except for the requested read-only production dependency audit. No Impeccable detector was run and no `DESIGN.md` was created.

## Outcome

All non-credential-gated backend/operations checks listed below have fresh exit-zero evidence after the fixes. Two real findings were reproduced and closed:

1. **High — vulnerable frozen backend dependencies (resolved).** `pip-audit -r backend/requirements.lock` initially exited 1 with 75 advisory rows, including duplicate aliases, concentrated in Django 5.2.9, cryptography 46.0.3 and Pillow 12.1.0. Direct pins are now Django 5.2.17, cryptography 50.0.0 and Pillow 12.3.0; both runtime and development locks were regenerated with hashes. Django remains on its 5.2 LTS line. A fresh no-cache image installed both locks with `--require-hashes`, the full SQLite and PostgreSQL matrices passed, and the final audit exited 0 with `No known vulnerabilities found`.
2. **Medium — operations correlation ID could be corrupted by PII redaction (resolved).** A generated UUID ending in 12 numeric characters was passed through the free-text number redactor only on subprocess events, so one backup appeared under two job IDs. The existing RED was made deterministic with `OPS_JOB_ID=123e4567-e89b-12d3-a456-123456789012`. `emit_event` now treats `job_id` as its reserved structured field and does not allow a duplicate free-text field to overwrite it. The exact regression and full operations suite are GREEN.

One informational exception remains: the development Celery container warns when run as root. Production `worker`, `beat`, backend, frontend and backup services are configured/tested as non-root. This was not changed because it is confined to the disposable bind-mounted development topology and changing its UID can break cross-platform developer mounts.

## Fresh verification matrix

| Area | Command/evidence | Result |
|---|---|---|
| Frozen backend build | `docker compose build --pull --no-cache backend`, then rebuilt again with the remediated locks | Exit 0; runtime and dev requirements installed with `--require-hashes` |
| Production backend build | Production Compose backend build; version probe inside final image | Exit 0; Django 5.2.17, cryptography 50.0.0, Pillow 12.3.0 |
| Full backend | `pytest -q` on the final rebuilt image | `222 passed, 18 skipped in 184.32s` |
| PostgreSQL/Redis | PostgreSQL-enabled migrations, inventory, checkout, locking, admin and refund concurrency selection | `66 passed in 186.17s` |
| Provider/security/admin selection | Provider adapters, webhook signature/dedup/retry/mismatch, CSRF, ownership, throttles, uploads, spreadsheet neutralization, admin permissions/exports and Celery task regressions | `134 passed in 134.13s` before dependency-only upgrades; the final full suite covers the same files after upgrades |
| Ruff | `ruff check .` | `All checks passed` |
| Django checks | `manage.py check` and production-like `manage.py check --deploy` with strong synthetic secrets | Both exit 0, `0 issues` |
| Migration drift | `manage.py makemigrations --check --dry-run` | Exit 0, `No changes detected` |
| OpenAPI | `manage.py spectacular --format openapi-json --validate` to `/tmp` | Exit 0 |
| Static assets | isolated `/tmp` `collectstatic --clear` | 166 copied, 478 post-processed |
| Redis/Celery | rebuilt worker, Redis broker/result backend, `release_expired_reservations.delay().get(timeout=30)` and final `celery inspect ping` | Task returned `0`; one node replied `pong` |
| Operations unit/drill | `python -m unittest discover -s infra/tests -p "test_*.py" -v` after correlation fix | 33 tests OK, 7 explicitly runtime-gated |
| Caddy/media/backup runtime | enabled runtime tests for admin CIDR, forwarded host, redacted failure logs, media/static persistence and killed-backup lock recovery | `5 tests in 316.903s`, OK |
| Backup/restore semantics | operations suite uses isolated dumps/media, manifest hashes, fake restic snapshot confirmation, refusal of existing/unsafe targets, failed-target cleanup and lock recovery | All exercised tests passed; no production data was touched |
| Compose | dev and production-example `compose config --quiet`; production example `config-check` | Configs exit 0; placeholder runtime fails closed with exit 2 |
| Health/readiness | live dev backend `/healthz` and `/readyz` | `200 {"status":"ok"}`; `200` ready with database/Redis `ok` |
| Caddy configuration/images | final production backend, Caddy and ops image builds; `caddy validate` | Builds and validation exit 0 |

## Security evidence

- **Dependency advisories:** final `pip-audit` ran in an ephemeral Python 3.13 container against the final hashed backend runtime lock and the default Python package advisory source; exit 0, no known vulnerabilities. `pnpm 11.19.0 --dir frontend audit --prod` queried `https://registry.npmjs.org/` against the concurrent final lock state; exit 0, no known vulnerabilities. The audit did not modify frontend files.
- **Secrets:** current tracked files and full Git patch history were searched for common live AWS/GitHub/Stripe/Mercado Pago tokens and private-key blocks; no matches. There are no tracked `.env`, private key or PEM files. Final client static bundles, production image configuration/history and current backend/worker logs were searched for live-token patterns and the synthetic verification secrets; no matches. Placeholder examples remain deliberately tracked and fail runtime validation.
- **Production runtime settings:** the clean `check --deploy` verifies secure cookies, session/CSRF middleware, HTTPS redirect, HSTS, proxy SSL header and clickjacking protections under `APP_ENV=production`. Tests also exercise stable JSON CSRF failures for missing/stale tokens.
- **Data boundaries:** focused and full tests cover owner-only carts/orders/addresses, verified-user gates, login/email/IP throttles, admin least privilege, cost/export permissions, spreadsheet formula neutralization and masked sensitive exports.
- **Uploads/media:** tests cover MIME/extension mismatch, byte/dimension/pixel/decompression limits, safe UUID names, derivative cleanup/rollback and same-origin media serialization. Runtime tests serve persisted originals/derivatives through read-only Caddy media mounts.
- **Provider/webhooks:** deterministic tests cover HTTPS/config validation, secret-redacted transports, HMAC timestamp tolerance, invalid-signature persistence, retry without dedupe poisoning, provider fetch mismatch fields, queued recovery and OpenAPI signed-header/body contracts.
- **Operational logs:** subprocess output is byte-bounded and redacted; real Caddy proxy-failure logs retain request/path/status correlation without request PII. The fixed reserved `job_id` remains identical across scheduler, subprocess, backup and alert payloads.

## Credential-gated and environment-gated evidence

- Mercado Pago sandbox smoke: `1 skipped` with the exact reason `sandbox credentials absent`; no access token/payment ID was fabricated.
- SID and Correo Argentino: contract/error/redaction behavior is covered with deterministic adapters, but live sandbox/production calls were not made because credentials were absent.
- Public ACME/TLS issuance and a real Donweb hostname were not exercised locally; the production Caddy image/config and local proxy runtime were validated.
- Real offsite restic storage and production restore were not invoked. Snapshot confirmation, encrypted-repository configuration, restore refusal/cleanup and killed-process recovery used isolated test storage/fake provider commands.
- External notification/email delivery remains intentionally provider-gated; retry state is tested without fabricating delivery.

## Scope and artifacts

- No generated schema, media, static, audit or browser artifact is committed; outputs were written to containers or temporary directories.
- Concurrent frontend files and `pnpm-lock.yaml` changes visible during verification were not edited or staged by Task 6A.
- Task 6A-owned paths are the three backend dependency inputs/locks, the operations correlation fix/regression, and this report.
