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

## Fix Round 1 — cierre de revisión 401874f

### Mapeo R1–R10

- **R1/R4:** `assets-init` root one-shot es dependencia obligatoria de backend/worker/beat. Inicializa media como UID 1000, GID lector 10001, modo setgid `2750`; inicializa backups UID/GID 10001; ejecuta `collectstatic` y publica `static_data/releases/$RELEASE_ID` mediante symlink atómico `current`. Un drill real escribió con Django storage, generó derivados, recreó Caddy y conservó/sirvió media y static de la segunda release.
- **R2/R3:** el bloque Caddy usa `route` explícito: bloqueo Admin antecede al proxy. El validador normaliza CIDR por espacios, rechaza comas y uniones públicas. Pruebas con Caddy real cubren IP permitida/denegada y fallo upstream; los eventos conservan path/status/request-id y eliminan query, cookie, Authorization y Referer.
- **R5:** frontend mantiene rootfs read-only y un tmpfs cache de imagen de 256 MiB, UID/GID 1000. Requests cold/warm reales al optimizador fueron idénticos y no emitieron `EROFS`/`EACCES`.
- **R6/R7:** backup usa lock del SO con metadata, exclusión concurrente y recuperación automática después de kill. Intervalo/retención local y Restic tienen bounds; password-file debe existir/ser legible. Success exige snapshot local presente con checksums y, si Restic está activo, un snapshot JSON que contenga el target.
- **R8:** se eliminó por completo el overwrite. Restore sólo acepta DB y media nuevas, usa staging para media y elimina la DB recién creada si falla.
- **R9:** Django liga UUID confiable de Caddy, responde `X-Request-ID` y emite JSON allow-list; Celery propaga el request-id en headers y liga job-id. Gunicorn error, web, worker, beat, config-check, assets, backup/scheduler y restore comparten logs JSON redacted. Tests cubren éxito, excepción y queued work.
- **R10:** defaults steady-state suman 2816 MiB y el peor overlap de release con `assets-init` suma 3072 MiB sobre el mínimo de 4 GiB. El runbook prohíbe build durante pico y recomienda CI/registry. Backup real corrió con recuperación tras kill; toda la matriz de servicios peligrosos corrió aislada.

### Opcionales seguros

- **O3 (parcial, explícito):** manifiesto agrega `RELEASE_ID` y fingerprint sanitizado de configuración. El estado de migraciones y las versiones de herramientas siguen fuera del manifiesto porque el contenedor de backup no debe importar Django ni inferir estado desde una base activa durante el dump; se programan como evolución versionada del formato, no como cambio lateral de este fix.
- **O4:** `infra/secrets` se monta read-only en config-check/backup y documenta `RESTIC_PASSWORD_FILE=/run/secrets/restic-password`; el payload queda ignorado por Git.
- **O5:** `verify-production.py` dejó de aceptar el ejemplo como aprobación: exige un env real, ejecuta el contenedor config-check y por defecto corre los drills Docker runtime después del build.
- **O1/O2 (pendientes, explícitos):** no se fijaron digests ni un CSP improvisado. El runbook exige publicar/registrar digests por release y documenta CSP Report-Only con nonces como trabajo de staging; agregar `unsafe-inline` o digests no verificados habría reducido seguridad o roto Next/Admin. O4/O5 permanecen resueltos por el secret mount validado y los drills runtime reales.

### Evidencia final

```text
python -m unittest infra.tests.test_task5b_operations -v
22 tests, OK

TASK5B_DOCKER_RUNTIME=1 python -m unittest \
  infra.tests.test_task5b_caddy_runtime \
  infra.tests.test_task5b_runtime_boundaries -v
6 tests, OK (376.698s)

APP_ENV=test python -m pytest -q  # backend shared state
224 passed, 16 skipped

python -m ruff check .
All checks passed

pnpm lint && pnpm typecheck && pnpm test:ci
5 files, 25 tests passed
```

- `docker compose ... config --quiet`: PASS, incluida compatibilidad de render sin Redis histórico; `DJANGO_DEBUG=false` queda forzado.
- `docker compose ... run --rm --no-deps config-check` con entorno production válido: evento `config.valid`.
- `caddy validate` real: PASS.
- Builds finales backend/frontend/Caddy/ops: PASS; frontend Next compiló, TypeScript, SSG y standalone.
- Matriz runtime final: Admin allowed/denied, access+error log sin PII, cache Next cold/warm, media+derivada+static upgrade+Caddy recreation, backup kill/restart y presupuesto concurrente de 4 GiB: 6/6 PASS.
- Al cerrar los drills no quedaron contenedores, redes ni volúmenes `task5b-*`.

### Límites restantes

- No se usaron credenciales S3 reales: el contrato Restic se probó con un comando controlado que exige snapshot JSON; el runbook mantiene `restic init`, `snapshots` y `check` como gate operativo.
- TLS público y CSP con nonces sólo pueden aprobarse contra DNS/staging reales. La configuración Caddy sí fue adaptada, validada y ejercitada en HTTP aislado.

## Fix Round 2 — cierre R3/R9/R10 residual

- **R3:** se restauró el logger de error real de Caddy. Su filtro elimina el mapa completo de headers, conserva method/path/status y renombra el `err_id` seguro a `request_id`; query y referrer no sobreviven. El access log conserva su UUID independiente. La regresión usa Caddy 2.10 real, fuerza upstream 502 y exige ambos eventos (`http.log.error.*` y `http.log.access.*`) sin el probe PII.
- **R9:** `common.run` siempre captura stdout/stderr, nunca permite herencia cruda, limita cada diagnóstico a 4000 caracteres y emite eventos JSON allow-list `subprocess.stdout|stderr` con service, job_id, tool y returncode; `emit_event` agrega el mismo `job_id` también a los eventos padres. Redacta query, email, números personales, claves etiquetadas y valores reales de variables sensibles. Backup, restore, Restic, PostgreSQL y collectstatic pasan por este wrapper. Una regresión ejecuta un proceso que escribe email/query/token, password/cookie y el secreto PostgreSQL desnudo a ambos streams; todas las líneas resultantes parsean como JSON, comparten correlación y ninguna conserva los probes.
- **R10:** beat baja de 160 a 128 MiB y backup de 384 a 320 MiB. El steady-state suma 2816 MiB; el peor overlap deliberado con `assets-init` suma exactamente 3072 MiB, reservando 1 GiB del host de 4 GiB. Además del cálculo contra Compose renderizado, un drill Docker crea/inicia simultáneamente nueve cgroups con los límites reales, inspecciona cada `HostConfig.Memory` y confirma concurrencia.

### RED → GREEN y verificación final de Fix Round 2

- **RED R3:** el upstream 502 no produjo evento `http.log.error.*`; **GREEN:** access + error saneados presentes en Caddy 2.10 real.
- **RED R9:** el proceso controlado filtró email/query/token/password/cookie por stdout/stderr crudos; **GREEN:** ambos streams sólo producen JSON saneado y correlacionado.
- **RED R10:** el overlap con límites previos fue 3168 MiB, por encima del techo operativo de 3072 MiB; **GREEN:** 2816 MiB steady/3072 MiB release y nueve contenedores concurrentes con sus cgroups exactos.
- `python -m unittest infra.tests.test_task5b_operations -v`: **22/22 PASS**.
- `TASK5B_DOCKER_RUNTIME=1 python -m unittest infra.tests.test_task5b_caddy_runtime infra.tests.test_task5b_runtime_boundaries -v`: **6/6 PASS** en 376.698 s.
- Backend compartido: **224 passed, 16 skipped**; Ruff, Django check y migration drift PASS.
- Frontend: lint/typecheck PASS, Vitest **5 archivos/25 tests**, Next production build/standalone PASS.
- `docker compose ... build`: backend, worker, beat, frontend, ops/config-check y Caddy PASS. Compose config y Caddy real validan; config-check con entorno production sintético válido emitió `config.valid`.
- Al cierre no quedaron contenedores, redes ni volúmenes `task5b-*`; `frontend/next-env.d.ts` fue restaurado y no existen `AGENTS.md`, `CLAUDE.md` ni `tsconfig.tsbuildinfo` generados.
