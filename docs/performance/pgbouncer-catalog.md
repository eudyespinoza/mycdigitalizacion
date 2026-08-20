# PgBouncer y rendimiento del catálogo

Esta guía acompaña el perfil inicial de 2 GB de la VPS Donweb. Django, Celery Worker y Celery Beat usan PgBouncer en modo `transaction` sobre el puerto interno 6432. Migraciones, backups y restauraciones conectan directamente a PostgreSQL 5432.

## Topología y límites iniciales

| Servicio | Memoria máxima |
|---|---:|
| PostgreSQL | 384 MiB |
| PgBouncer | 32 MiB |
| Django/Gunicorn (2 workers) | 320 MiB |
| Celery Worker (concurrency 1) | 256 MiB |
| Celery Beat | 80 MiB |
| Redis | 128 MiB |
| Next.js | 256 MiB |
| Caddy | 64 MiB |
| Backup scheduler | 128 MiB |

PgBouncer comienza con `default_pool_size=10`, `min_pool_size=2`, `reserve_pool_size=2`, `max_client_conn=100` y `max_db_connections=20`. No se publica al host.

## Inspección del pool

Definí el mismo alias del runbook:

```sh
dc='docker compose --env-file .env.production -f compose.prod.yaml'
$dc exec pgbouncer sh -lc 'PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -p 6432 -U "$DB_USER" -d pgbouncer -c "SHOW POOLS;"'
$dc exec pgbouncer sh -lc 'PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -p 6432 -U "$DB_USER" -d pgbouncer -c "SHOW STATS;"'
```

Investigá si `cl_waiting` permanece por encima de cero durante más de un minuto, si `sv_active` alcanza de forma sostenida el máximo disponible o si `maxwait` crece. Antes de ampliar el pool, revisá consultas lentas, CPU, memoria y conexiones actuales de PostgreSQL. Un pool mayor sin RAM suficiente empeora el servidor.

El drill local de 24 clientes se ejecuta con:

```sh
RUN_PGBOUNCER_RUNTIME_TESTS=1 python -m unittest infra.tests.test_pgbouncer_runtime -v
```

## Operaciones directas

Las migraciones nunca atraviesan el pool transaccional:

```sh
$dc run --rm -e POSTGRES_BYPASS_POOL=true backend python manage.py migrate --noinput
$dc run --rm -e POSTGRES_BYPASS_POOL=true backend python manage.py makemigrations --check --dry-run
$dc run --rm backup python /ops/backup.py
```

`POSTGRES_BYPASS_POOL=true` es también el rollback de una sola variable. Para una contingencia de PgBouncer, fijalo temporalmente en `.env.production` y recreá `backend`, `worker` y `beat`:

```sh
$dc up -d --force-recreate backend worker beat
curl -fsS https://DOMINIO/readyz
```

Cuando el pool vuelva a estar sano, restaurá `POSTGRES_BYPASS_POOL=false` y recreá los mismos servicios. No elimines PgBouncer ni los índices durante el incidente.

## Índices y planes

El catálogo filtra y pagina candidatos en PostgreSQL antes de cargar variantes e imágenes. Existen índices parciales para categoría/marca publicadas, GIN de texto en español, trigramas para nombre/SKU, atributos tipados, reservas, pedidos, clientes, auditoría y contenido programado.

Para revisar un plan real:

```sh
$dc exec postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT id FROM catalog_product WHERE category_id = 1 AND is_active AND is_sellable ORDER BY created_at DESC, id DESC LIMIT 24;"'
```

No fuerces un índice sólo porque exista: en tablas pequeñas una lectura secuencial puede ser más barata. La prueba `backend/tests/test_postgres_catalog_plans.py` crea 20.000 productos, ejecuta `VACUUM ANALYZE` y comprueba los caminos indexados de catálogo, atributos, pedidos y clientes.

## Caché Redis

- Facetas públicas: 60 segundos.
- Categorías activas y branding general: 300 segundos.
- Claves versionadas con filtros públicos normalizados y SHA-256.
- Cambios confirmados de productos, variantes, imágenes, categorías, marcas, atributos, promociones y landing incrementan la versión al confirmar la transacción.
- Carrito, stock autoritativo, checkout, identidad y pagos nunca se cachean.

No borres Redis como mecanismo normal de publicación. Si un incidente exige vaciarlo, hacelo en una ventana y verificá catálogo, landing y límites de frecuencia después.

## Escalado a 4 GB

Primero medí. Como punto de partida después de ampliar la VPS, se puede elevar PostgreSQL a 768 MiB, backend a 512 MiB, worker a 512 MiB, Redis a 256 MiB y frontend a 384 MiB. Conservá el pool 10/20 hasta demostrar espera sostenida; luego subí de a cinco conexiones y repetí `SHOW POOLS`, planes, readiness y compra completa. Registrá los valores finales en `.env.production`.
