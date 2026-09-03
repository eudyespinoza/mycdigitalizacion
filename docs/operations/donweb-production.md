# Operación en producción sobre Donweb

Este runbook despliega una única instancia de mycdigitalizacion con TLS automático, aplicaciones sin privilegios, PostgreSQL, Redis y copias verificables. Los comandos se ejecutan desde la raíz del repositorio en el servidor. Sustituí `tienda.ejemplo.com.ar`, revisiones y nombres de restauración por valores reales; nunca pegues secretos en tickets o logs.

## 1. Prerrequisitos y borde de red

- VPS Donweb con Ubuntu 24.04 LTS, 2 vCPU, 2 GB RAM iniciales, 40 GB SSD y 1 GB de swap acotada. El perfil inicial limita los servicios permanentes a 1648 MiB; con `assets-init` suma como máximo 1904 MiB. Es un perfil austero: no construyas imágenes ni ejecutes restauraciones con tráfico activo, vigilá swap/OOM y ampliá a 4 GB cuando crezcan catálogo, concurrencia o tareas de imágenes. El gate runtime reproduce las nueve cargas dentro de un cgroup agregado de 2 GiB y debe terminar sin `oom_kill`.
- Usuario operador con sudo y acceso SSH por clave. Deshabilitá contraseña y root remoto después de comprobar una segunda sesión.
- Docker Engine y plugin Compose actuales. Confirmá con `docker version` y `docker compose version`.
- Registro horario UTC y sincronización NTP activa. Reservá espacio fuera del volumen PostgreSQL para `backup_data`.
- Un registro DNS `A` para el dominio hacia la IPv4 del VPS; agregá `AAAA` sólo si IPv6 está correctamente ruteado. Eliminá registros anteriores que apunten a otro servidor. Esperá propagación antes de iniciar Caddy.
- Firewall Donweb y `ufw`: permití `22/tcp` sólo desde IP/VPN operativa y `80/tcp`, `443/tcp` desde Internet. No publiques 3000, 5432, 6379, 8000 ni 2019.

Ejemplo de firewall, después de verificar la IP administrativa:

```sh
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from DIRECCION_ADMINISTRATIVA to any port 22 proto tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status verbose
```

## 2. Código, entorno y secretos

Cloná a una ruta estable propiedad del operador, fijá una revisión aprobada y creá el archivo privado:

```sh
git clone URL_DEL_REPOSITORIO /opt/mycdigitalizacion
cd /opt/mycdigitalizacion
git checkout REVISION_APROBADA
cp .env.production.example .env.production
chmod 600 .env.production
```

Generá valores independientes con un gestor de secretos; por ejemplo `openssl rand -base64 48`. `DJANGO_SECRET_KEY`, `PERSONAL_DATA_ENCRYPTION_KEY`, contraseñas PostgreSQL/Redis y Restic no se reutilizan. Configurá:

- `SITE_ADDRESS` con el dominio canónico sin esquema, `SITE_WWW_ADDRESS` con su variante `www`,
  `ACME_EMAIL` y `DJANGO_ALLOWED_HOSTS` incluyendo ambos hostnames. Caddy redirige `www` al
  dominio canónico y conserva la ruta solicitada.
- `RELEASE_ID` con el commit/digest inmutable que se despliega; cambialo en cada release.
- `ADMIN_ALLOWED_CIDRS` con CIDR de oficina o VPN separados únicamente por espacios. El validador rechaza comas, `0.0.0.0/0`, `::/0` y uniones que equivalgan a acceso público.
- Credenciales SID, Mercado Pago y Correo Argentino sólo para los modos realmente habilitados. Un campo vacío no demuestra que el proveedor funciona.

### Conexión de Mercado Pago con un botón

La cuenta vendedora no necesita copiar un access token al panel. La preparación se hace una sola
vez en el servidor:

1. Creá la aplicación de la tienda en Mercado Pago Developers y habilitá Checkout Pro/OAuth.
2. Registrá como URL de redirección exacta
   `https://TU_DOMINIO/api/v1/payments/mercadopago/oauth/callback/`.
3. Completá `MERCADOPAGO_OAUTH_CLIENT_ID`, `MERCADOPAGO_OAUTH_CLIENT_SECRET` y
   `MERCADOPAGO_WEBHOOK_SECRET` en `.env.production`. La URL de redirección se deriva del dominio;
   sólo definí `MERCADOPAGO_OAUTH_REDIRECT_URI` si necesitás sobrescribirla.
4. Volvé a desplegar `backend`, `worker` y `beat`.
5. En **Administración → Integraciones → Mercado Pago**, presioná **Conectar Mercado Pago**,
   iniciá sesión y confirmá. El regreso al panel es automático.

El `client_secret`, los tokens de acceso y renovación nunca llegan al navegador. Los tokens se
guardan cifrados, se renuevan automáticamente y se eliminan al desconectar la cuenta.
- `RESTIC_REPOSITORY=s3:s3.amazonaws.com/NOMBRE_BUCKET/prefijo`, `RESTIC_PASSWORD` y credenciales S3 de mínimo privilegio si habrá copia remota cifrada. Como alternativa, guardá el secreto no versionado en `infra/secrets/restic-password` con modo `0600` y usá `RESTIC_PASSWORD_FILE=/run/secrets/restic-password`. El bucket debe tener versionado/bloqueo acorde a la política del negocio.
- `BACKUP_ALERT_WEBHOOK_URL` a un endpoint que acepte JSON de estado. Nunca apunta a un canal público.

El ejemplo está diseñado para fallar. Validalo antes de abrir tráfico:

```sh
docker compose --env-file .env.production -f compose.prod.yaml build config-check
docker compose --env-file .env.production -f compose.prod.yaml run --rm --no-deps config-check
```

No sigas si el segundo comando no emite el evento JSON `config.valid` para `production`.

## 3. Primer despliegue

Definí una abreviatura para evitar mezclar Compose de desarrollo y producción:

```sh
dc='docker compose --env-file .env.production -f compose.prod.yaml'
$dc config --quiet
$dc build
$dc up -d postgres redis pgbouncer
$dc ps
$dc run --rm -e POSTGRES_BYPASS_POOL=true backend python manage.py migrate --noinput
$dc run --rm -e POSTGRES_BYPASS_POOL=true backend python manage.py setup_admin_roles
$dc run --rm -e POSTGRES_BYPASS_POOL=true backend python manage.py createsuperuser
$dc up -d
$dc ps
```

`assets-init` corre como one-shot antes de backend/worker/beat: fija ownership de media/backups, ejecuta `collectstatic` y publica atómicamente `/srv/static/current` hacia `releases/$RELEASE_ID`. Si falla, los consumidores no arrancan. Media queda con dueño UID 1000, grupo lector de backup GID 10001 y setgid; Caddy/backup sólo la montan read-only.

`backend` espera `/readyz`; no marques el despliegue sano mientras PostgreSQL o Redis figuren indisponibles. `worker`, `beat`, `frontend`, `backup` y `caddy` también deben llegar a `healthy`. Inspeccioná sólo la ventana necesaria de logs y no copies cookies, tokens ni parámetros de búsqueda:

```sh
$dc logs --since=10m backend worker beat caddy
```

Web, worker, beat y operaciones emiten JSON con `timestamp`, `level`, `service`, `event` y `request_id` o `job_id` cuando aplica. Caddy genera un UUID en el borde; un listener loopback del mismo proceso lo conserva en access/error sin confiar en IDs del cliente, mantiene `error_id` separado, restaura el Host externo con puerto y sólo confía en ese loopback para preservar cliente/protocolo antes del backend. El puerto interno nunca se publica. Django sólo acepta ese formato y Celery lo propaga al publicar trabajos. El scheduler genera un `job_id` por ejecución y lo heredan backup, herramientas y alertas; dos ejecuciones concurrentes no lo comparten. Los logs omiten query strings, cookies, autorización, referrer y PII detectada; aun así, tratá todo log como dato operativo sensible.

Caddy solicita certificados públicos automáticamente. Si falla, comprobá DNS, reloj y acceso entrante 80/443 antes de reintentar; no habilites `tls internal` en producción.

## 4. Configuración funcional y proveedores

1. Ingresá a `https://DOMINIO/gestion/` con una cuenta de gestión. El Django Admin no es el panel operativo del comercio.
2. Comprobá los grupos Owner, Catalog, Orders/Logistics y Content; asigná sólo los permisos necesarios.
3. Cargá identidad fiscal, retiro, cajas/medidas y contenido real. No publiques campañas ni productos de prueba.
4. Habilitá SID, Mercado Pago o Correo Argentino de a uno. Verificá credenciales, URL pública de webhook, firma, modo live y un caso controlado de error. Una redirección del navegador no confirma un pago.
5. Reiniciá servicios afectados tras cambiar `.env.production`: `$dc up -d --force-recreate backend worker beat frontend caddy backup`.

## 5. Smoke test de salida

Ejecutá desde una red externa y verificá contenido, códigos y headers:

```sh
curl -fsS https://DOMINIO/healthz
curl -fsS https://DOMINIO/readyz
curl -fsSI https://DOMINIO/
curl -fsSI https://DOMINIO/static/rest_framework/docs/css/base.css
curl -fsS https://DOMINIO/api/v1/storefront/home/
```

Los cuerpos esperados son `{"status":"ok"}` en liveness y, con dependencias sanas, `{"status":"ready","dependencies":{"database":"ok","redis":"ok"}}`. Confirmá HSTS, `X-Content-Type-Options`, `X-Frame-Options` y `X-Request-ID`. Desde una IP no autorizada, `/admin/` debe devolver 403. Probá además registro/verificación, búsqueda, carrito y checkout sin inventar éxito de proveedores. Una imagen real `/media/...` debe responder por el mismo origen.

## 6. Backups y alertas

El servicio `backup` ejecuta `pg_dump` en formato custom, archiva media, calcula SHA-256 y escribe `manifest.json` mediante un directorio parcial y lock de sistema operativo. El manifiesto incluye `RELEASE_ID` y fingerprint sanitizado. Todo child stdout/stderr se lee concurrentemente con un límite duro de 1 MiB por stream: al excederlo, el proceso se termina y sólo se emite un resumen JSON saneado. Un kill libera el lock; la contención dispara alerta con el mismo `job_id`. Conserva copias locales por `BACKUP_RETENTION_DAYS`; si Restic está configurado, aplica retención diaria/semanal/mensual, confirma el snapshot JSON y cifra el repositorio.

Inicializá Restic una sola vez y hacé la primera copia manual:

```sh
$dc run --rm --no-deps backup restic init
$dc run --rm backup python /ops/backup.py
$dc run --rm --no-deps backup restic snapshots
$dc run --rm --no-deps backup restic check
```

Omití `restic init` cuando no exista repositorio remoto. En ese caso documentá explícitamente que la copia vive en el mismo VPS y no cubre pérdida total del servidor. Alertá si el servicio no está healthy, si el webhook recibe `backup_failed`, si no hay snapshot reciente o si el volumen supera 80%.

## 7. Simulacro de restauración seguro

Elegí un backup y nombres nuevos. El script siempre rechaza la base activa, cualquier base existente y cualquier ruta media existente. No existe bypass de overwrite: una promoción/swap posterior exige una ventana y procedimiento aprobados por separado.

```sh
$dc run --rm --no-deps backup ls -la /backups
docker volume create mycdigitalizacion_restore_media_drill
$dc run --rm -v mycdigitalizacion_restore_media_drill:/restore-target backup \
  python /ops/restore.py \
  --backup /backups/AAAAMMDDTHHMMSSZ \
  --target-db restore_drill_aaaammdd \
  --target-media /restore-target/media
$dc exec postgres sh -c 'psql -U "$POSTGRES_USER" -d restore_drill_aaaammdd -c "select 1;"'
docker run --rm -v mycdigitalizacion_restore_media_drill:/restore-target:ro alpine test -d /restore-target/media
```

Revisá el nombre exacto antes de limpiar el simulacro. La limpieza es destructiva y requiere una aprobación operativa separada:

```sh
# Tras aprobación explícita y sólo para los dos targets del simulacro:
$dc exec postgres sh -c 'dropdb -U "$POSTGRES_USER" restore_drill_aaaammdd'
docker volume rm mycdigitalizacion_restore_media_drill
```

Nunca uses `docker compose down -v`, `docker volume prune` ni una restauración sobre producción como prueba.

## 8. Actualización

### Flujo establecido desde la estación Windows (sin GitHub CLI)

Este proyecto no usa GitHub CLI (`gh`) para desplegar. El flujo ya probado usa Git HTTPS con las credenciales guardadas en Git Credential Manager, consulta GitHub Actions por REST y actualiza el servidor con el alias SSH `mycdigitalizacion-prod`. No instales `gh` como requisito ni detengas un despliegue porque no esté disponible.

Primero fijá el commit local y comprobá que `main` remoto continúa exactamente en su padre. Esta guarda evita sobrescribir trabajo remoto. El usuario incluido en la URL selecciona la cuenta correcta de Git Credential Manager; nunca agregues un token a la URL, al comando ni a los logs.

```powershell
$ErrorActionPreference = 'Stop'
$releaseSha = (git rev-parse HEAD).Trim()
$expectedMain = (git rev-parse HEAD^).Trim()

git fetch origin main
$remoteMain = (git rev-parse origin/main).Trim()
if ($remoteMain -ne $expectedMain) {
    throw "origin/main cambió: esperado $expectedMain, encontrado $remoteMain"
}

$env:GCM_INTERACTIVE = 'Never'
$env:GIT_TERMINAL_PROMPT = '0'
$repositoryUrl = 'https://eudyespinoza@github.com/eudyespinoza/mycdigitalizacion.git'

git push --atomic --porcelain $repositoryUrl `
    "${releaseSha}:refs/heads/feat/ecommerce-foundation" `
    "${releaseSha}:refs/heads/main"
```

El workflow requerido se llama `CI` y corre al actualizar `main`. Consultalo sin `gh`, esperando el run cuyo `head_sha` sea exactamente `$releaseSha`:

```powershell
$headers = @{ 'User-Agent' = 'mycdigitalizacion-deploy' }
$runsUrl = 'https://api.github.com/repos/eudyespinoza/mycdigitalizacion/actions/runs?branch=main&event=push&per_page=20'
$deadline = (Get-Date).AddMinutes(30)

do {
    $run = (Invoke-RestMethod -Headers $headers -Uri $runsUrl).workflow_runs |
        Where-Object { $_.name -eq 'CI' -and $_.head_sha -eq $releaseSha } |
        Sort-Object created_at -Descending |
        Select-Object -First 1

    if ($run -and $run.status -eq 'completed') { break }
    if ((Get-Date) -ge $deadline) { throw "Timeout esperando CI para $releaseSha" }
    Start-Sleep -Seconds 30
} while ($true)

if ($run.conclusion -ne 'success') {
    throw "CI no aprobó $releaseSha: $($run.conclusion) ($($run.html_url))"
}
```

No actualices producción si el run falta, corresponde a otro SHA, sigue en ejecución o no concluyó en `success`. Guardá la URL del run en el informe del despliegue.

Antes de modificar el VPS, comprobá por SSH la revisión actual, que el checkout esté limpio, el backup reciente, el espacio disponible y la salud de los servicios. La ruta estable es `/opt/mycdigitalizacion`.

La actualización remota debe ser un fast-forward al SHA aprobado y debe abortar ante cualquier diferencia:

```sh
ssh mycdigitalizacion-prod 'set -e
cd /opt/mycdigitalizacion
git rev-parse HEAD
test -z "$(git status --porcelain)"'

ssh mycdigitalizacion-prod 'set -euo pipefail
cd /opt/mycdigitalizacion
expected=SHA_APROBADO
test -z "$(git status --porcelain)"
git fetch origin main
test "$(git rev-parse FETCH_HEAD)" = "$expected"
git merge --ff-only "$expected"
test "$(git rev-parse HEAD)" = "$expected"
sed -i "s/^RELEASE_ID=.*/RELEASE_ID=$expected/" .env.production
chmod 600 .env.production
dc="docker compose --env-file .env.production -f compose.prod.yaml"
$dc config --quiet
$dc build config-check backend worker beat frontend
$dc run --rm --no-deps config-check
$dc run --rm -e POSTGRES_BYPASS_POOL=true backend python manage.py migrate --noinput
$dc up -d backend worker beat frontend
$dc ps'
```

Reemplazá `SHA_APROBADO` por el valor literal de `$releaseSha` antes de ejecutar el comando remoto; no dependas de una variable local dentro de las comillas SSH. Si cambian otros servicios, incluilos explícitamente en `build` y `up`.

Finalmente confirmá que el `HEAD` remoto y `RELEASE_ID` coincidan con el SHA aprobado, que los nueve servicios estén sanos y sin reinicios, que no haya errores críticos recientes y que `/healthz`, `/readyz`, `/` y `/api/v1/storefront/home/` respondan correctamente. Conservá las imágenes anteriores hasta cerrar la ventana de rollback.

1. Registrá revisión actual: `git rev-parse HEAD`.
2. Confirmá backup local/remoto reciente y espacio libre.
3. Descargá y fijá la nueva revisión, sin ejecutar código no revisado, y actualizá `RELEASE_ID` al identificador exacto.
4. Ejecutá `python scripts/verify-production.py --env-file .env.production --build`. El comando ejecuta config-check real y drills Docker aislados de Caddy, volúmenes, cache, backup y el cgroup agregado de 2 GiB; reservá capacidad y no uses `--skip-runtime` para aprobar una release.
5. Construí imágenes, migrá y recreá servicios:

```sh
$dc build
$dc run --rm -e POSTGRES_BYPASS_POOL=true backend python manage.py migrate --noinput
$dc up -d
$dc ps
```

Repetí el smoke test y observá errores, latencia, cola y backup. No borres imágenes anteriores hasta cerrar la ventana de rollback.

El nuevo `assets-init` publica una release static nueva aun cuando `static_data` ya exista; comprobá un asset de Admin por Caddy antes de cerrar la ventana.

## 9. Rollback e incidente

- Si no hubo migración incompatible, fijá la revisión/imágenes anteriores, ejecutá `$dc build` y `$dc up -d`; repetí health y smoke.
- Si cambió el esquema, no improvises una migración inversa. Detené escritura, conservá evidencia, restaurá a una base y volumen nuevos con el procedimiento anterior, verificá integridad y recién entonces cambiá los targets en una ventana aprobada.
- Ante sospecha de credenciales expuestas: restringí borde, rotá el secreto en su proveedor y `.env.production`, recreá sólo servicios consumidores, revocá el valor anterior y revisá auditoría. No publiques el secreto en logs.
- Ante disco lleno: detené escrituras si es necesario y ampliá capacidad. No borres volúmenes ni backups sin inventario y aprobación.

Las imágenes base aún se actualizan por tags de versión mayor/menor. Para rollback reproducible, publicá las imágenes resultantes con tag/digest de `RELEASE_ID` en un registry y registrá sus digests antes de borrar capas anteriores. CSP se mantiene como decisión pendiente: Next y Django Admin requieren una política con nonce probada en browser; no se agregó un `unsafe-inline` cosmético. Evaluá primero `Content-Security-Policy-Report-Only`, COOP y CORP en staging.

Documentá inicio/fin, revisión, operador, resultado de smoke, último backup verificable y cualquier desviación del runbook.
