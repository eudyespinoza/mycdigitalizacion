# Task 5B — Infraestructura y operación Donweb

## Alcance entregado

- `compose.prod.yaml` define Caddy, frontend, backend Gunicorn, worker, beat, PostgreSQL, Redis autenticado, validador fail-fast y backup programado.
- Procesos de aplicación no-root, filesystem de aplicación read-only, `no-new-privileges`, tmpfs acotados, restart `unless-stopped`, healthchecks y límites CPU/memoria configurables.
- Volúmenes persistentes separados para PostgreSQL, Redis, media, static, backups y estado/configuración Caddy.
- Caddy termina TLS público, comprime zstd/gzip, limita cuerpos a 25 MB, agrega headers de seguridad/request id, filtra credenciales y consultas sensibles del access log, restringe Admin por CIDR y sirve API/Admin/static/media/frontend por el mismo origen.
- La imagen frontend ejecuta el standalone como `node`; el Dockerfile backend crea ownership durante `COPY`, ejecuta collectstatic como `appuser` y evita el `chown -R /app` costoso.
- Backup PostgreSQL custom + media tar.gz + manifiesto SHA-256 atómico, lock exclusivo, retención local, Restic opcional cifrado/S3 con retención y webhook de fallo.
- Restore valida identificador, manifiesto y checksums; rechaza DB/media existentes por defecto, trabaja sólo contra targets explícitos y elimina una DB nueva si el restore no termina.
- `.env.production.example` contiene sentinels deliberadamente inválidos. `validate_env.py` exige secretos, dominio, email ACME, Redis, allowlist Admin acotada y credenciales de proveedor/Restic según flags.
- Runbook Donweb cubre capacidad, DNS, firewall, Docker, secretos, primer deploy, migraciones, roles/superuser, proveedores, smoke, backups, simulacro, actualización, rollback e incidentes.

## TDD

RED inicial:

- 5 fallos: no existían backup/restore/validador ni topología resiliente.
- RED adicional para env de ejemplo, Caddy, allow-all de Admin, nombre SQL inseguro, secreto Restic placeholder y rollback tras restore fallido.

GREEN final:

```text
python -m unittest infra.tests.test_task5b_operations -v
12 tests, OK
```

Los tests ejecutan scripts reales con comandos PostgreSQL controlados: crean/verifican dump, archivo media y manifiesto; prueban lock, rechazo de targets existentes, identificadores seguros, cleanup de DB nueva, env fail-fast y contrato Compose/Caddy.

## Evidencia de consumidores reales

- `docker compose --env-file .env.production.example -f compose.prod.yaml config --quiet`: PASS.
- `backend/tests/test_media_topology.py`: 2 passed, incluida compatibilidad histórica sin `REDIS_PASSWORD`; el sentinel sólo permite render y config-check lo rechaza al ejecutar.
- `backend/tests/test_health.py` + media topology: 3 passed.
- Caddy 2.10 `caddy validate`: configuración válida con automatic HTTPS; no `tls internal`.
- Builds producción: backend, worker, beat, frontend, ops y Caddy PASS.
- Usuarios de imagen: backend/worker=`appuser`, frontend=`node`, ops=`10001:10001`, Caddy=`1000:1000`.
- Backend image: `/app/staticfiles/admin/css/base.css` presente y UID efectivo distinto de 0.
- Frontend production build: Next compile, TypeScript, SSG y standalone PASS.
- Collectstatic del build final: 165 copiados, 1 sin cambio, 434 postprocesados.
- Fail-fast real: config-check con `.env.production.example` salió 2 antes de arrancar aplicación y enumeró placeholders.

## Smoke aislado real

Proyecto temporal `task5bverify` (red, DB, Redis y volúmenes propios):

- PostgreSQL y Redis healthy; migraciones completas PASS.
- Backend healthcheck healthy; `/readyz` devolvió `{"status":"ready","dependencies":{"database":"ok","redis":"ok"}}`.
- Backup real devolvió OK; manifiesto versión 1 y ambos SHA-256 de 64 caracteres.
- Restore real devolvió OK a `restore_drill_task5b` y volumen nuevo; 46 migraciones y media restaurada verificadas.
- Caddy non-root sirvió una imagen `/media/probe.png` con 200, `image/png`, HSTS, nosniff, SAMEORIGIN y `X-Request-ID`.
- Contenedores, red y volúmenes temporales fueron inventariados y eliminados al finalizar. No se tocó ningún contenedor compartido.

## Límites operativos

- No se ejecutó un backup S3/Restic real porque no se proporcionaron credenciales ni bucket. La imagen incluye Restic, el validador obliga secreto cifrado y el runbook exige `restic init`, snapshots y `restic check`.
- TLS público no se emitió en local: se validó la configuración con Caddy real y el runbook exige DNS propagado/80+443 antes del primer arranque.
- Los límites de recursos son defaults; deben ajustarse al plan Donweb y carga observada.
