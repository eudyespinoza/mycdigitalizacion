# Diseño de rendimiento: PgBouncer, PostgreSQL y catálogo

Fecha: 2026-08-20

## Objetivo

Reducir el tiempo de acceso a las pantallas de gestión y acelerar búsqueda, filtros y paginación del catálogo en una VPS Donweb inicial de 2 GB de RAM, manteniendo una ruta de crecimiento para ampliar recursos sin rediseñar la aplicación.

## Decisiones

- Incorporar PgBouncer en modo `transaction` como único punto de conexión de Django, Celery Worker y Celery Beat hacia PostgreSQL.
- Mantener conexiones directas a PostgreSQL exclusivamente para migraciones, backups, restauraciones y tareas operativas que necesiten semántica de sesión.
- Deshabilitar cursores de servidor en la conexión Django que pasa por PgBouncer.
- Mantener Redis para caché de configuración, estados de integraciones y facetas del catálogo.
- No incorporar Elasticsearch, Meilisearch ni otro servicio de búsqueda en esta etapa.
- Optimizar primero las consultas y luego agregar únicamente índices que correspondan a predicados y ordenamientos reales.
- Conservar el cálculo autoritativo de promociones. Los filtros SQL reducen primero el conjunto candidato; el cálculo comercial se ejecuta sobre ese conjunto reducido.

## Topología

```text
Next.js -> Django API -> PgBouncer:6432 -> PostgreSQL:5432
                         ^
Celery Worker -----------|
Celery Beat -------------|

Migraciones ----------------------------> PostgreSQL:5432
Backup y restore ------------------------> PostgreSQL:5432
```

PgBouncer tendrá health check propio. Django no se considerará listo si Redis, PgBouncer o PostgreSQL no están disponibles. PostgreSQL no se expondrá fuera de la red interna de Compose.

## Presupuesto para 2 GB

Los límites iniciales de memoria son deliberadamente conservadores:

| Servicio | Límite inicial |
|---|---:|
| PostgreSQL | 384 MB |
| PgBouncer | 32 MB |
| Django/Gunicorn | 320 MB |
| Celery Worker | 256 MB |
| Celery Beat | 80 MB |
| Redis | 128 MB |
| Next.js | 256 MB |
| Caddy | 64 MB |
| Backup scheduler | 128 MB |

Gunicorn usará dos workers. Celery comenzará con concurrencia uno. Los trabajos intensivos de backup no se solaparán con migraciones ni despliegues. Los límites dejan margen para Docker y el sistema operativo; se documentará cómo ampliarlos cuando la VPS crezca.

## Configuración de PgBouncer

- `pool_mode = transaction`
- `default_pool_size = 10`
- `min_pool_size = 2`
- `reserve_pool_size = 2`
- `max_client_conn = 100`
- `max_db_connections = 20`
- `server_idle_timeout = 60`
- `query_wait_timeout = 15`
- `server_reset_query = DISCARD ALL`
- Autenticación SCRAM con credenciales provistas mediante secretos o variables fuera del repositorio.
- Imagen fijada a una versión concreta; no se utilizará `latest`.

Django usará `CONN_MAX_AGE = 0` y `DISABLE_SERVER_SIDE_CURSORS = True` en la conexión agrupada. Una variable `POSTGRES_DIRECT_HOST=postgres` conservará el acceso operativo directo.

## Consultas e índices

### Catálogo público

1. Categoría y descendientes, marca, publicación y variantes activas se filtran en SQL antes de materializar productos.
2. Disponibilidad se resuelve mediante `EXISTS` sobre variantes y reservas vigentes.
3. Atributos se resuelven con `EXISTS` tipados sobre `AttributeValue` y `AttributeOption`.
4. Búsqueda usa full-text en español y similitud por trigramas.
5. La paginación se aplica en base de datos antes de serializar medios y variantes.
6. Precio efectivo y mejor promoción se calculan únicamente sobre los candidatos resultantes. Facetas se cachean por combinación normalizada de filtros durante 60 segundos.

Índices previstos:

- Producto parcial por `(category_id, created_at DESC, id)` donde `is_active AND is_sellable`.
- Producto parcial por `(brand_id, created_at DESC, id)` con la misma condición.
- GIN de búsqueda full-text sobre nombre y descripción.
- GIN trigram para nombre de producto y SKU.
- Variante por `(product_id, is_active)` incluyendo precio y stock físico.
- Reserva por `(variant_id, status, expires_at)`.
- Valores de atributo por `(definition_id, option_id, variant_id)` y equivalentes parciales para valores tipados usados como filtro.
- Promociones por estado y ventana temporal.

### Panel de gestión

- Productos: índice y consulta por nombre, slug y SKU, con paginación en PostgreSQL.
- Pedidos: índices por fecha descendente y combinaciones de pago/entrega utilizadas por los filtros.
- Clientes: búsqueda por email normalizado, nombre y hashes de DNI/CUIT sin descifrar datos sensibles.
- Auditoría: índice por fecha descendente, recurso, acción y actor.
- Contenido: índices por tipo, habilitación, orden y vigencia.
- Configuración e integraciones: respuesta cacheada en Redis; cualquier modificación invalida su clave inmediatamente.

## Caché

- Configuración general y branding: 5 minutos.
- Resumen de integraciones sin secretos: 60 segundos.
- Facetas del catálogo: 60 segundos por clave normalizada.
- Listado público de categorías: 5 minutos.
- No se cachean stock autoritativo, carrito, checkout, identidad ni estado de pago.
- La invalidación se ejecuta al guardar productos, categorías, marcas, atributos, promociones, contenido o configuración relevante.

## Medición

- Pruebas PostgreSQL reales verifican que los índices existan y que las consultas críticas no hagan secuencias completas cuando el volumen de prueba justifique el índice.
- Se usarán `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` sobre búsqueda, categoría, marca, atributos y panel de pedidos.
- Se registrará tiempo de consulta, filas examinadas y cantidad de consultas por endpoint.
- Presupuesto inicial: máximo 12 consultas SQL para listado de catálogo y máximo 10 para cada listado principal del panel, sin crecimiento lineal por fila.
- Prueba de concurrencia valida más clientes Django que conexiones PostgreSQL y confirma reutilización mediante PgBouncer.

## Despliegue y reversión

1. Crear índices mediante migraciones PostgreSQL; los índices pesados usarán operaciones concurrentes separadas de transacciones atómicas.
2. Levantar PgBouncer y validar su health check antes de redirigir Django y Celery.
3. Ejecutar migraciones y backup por la conexión directa.
4. Ejecutar smoke tests de readiness, catálogo, panel, Celery y backup.
5. Para revertir, restaurar `POSTGRES_HOST=postgres`, reiniciar aplicaciones y conservar los índices, que son compatibles con la versión anterior.

## Criterios de aceptación

- Backend, Worker y Beat utilizan PgBouncer; migraciones y backup usan PostgreSQL directo.
- No existen errores por cursores o estado de sesión bajo `pool_mode=transaction`.
- El catálogo filtra y pagina antes de cargar objetos en Python.
- Búsqueda tolerante a errores utiliza índices PostgreSQL.
- Las pantallas principales del panel no presentan consultas N+1.
- Compose local y productivo validan health checks, límites de memoria y secretos.
- La configuración inicial cabe en una VPS de 2 GB y documenta el escalado posterior.

## Referencias

- Django 5.2, bases de datos y pooling: https://docs.djangoproject.com/en/5.2/ref/databases/
- PostgreSQL, índices GIN: https://www.postgresql.org/docs/current/gin.html
- PostgreSQL 17, `pg_trgm`: https://www.postgresql.org/docs/17/pgtrgm.html
