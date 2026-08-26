# Analítica propia y estadísticas comerciales

Fecha: 2026-08-26
Estado: arquitectura y composición aprobadas; pendiente de revisión de este documento

## Objetivo

Agregar analítica propia, privada y accionable para administrar el ecommerce sin depender de Google Analytics ni de otro proveedor. El trabajo incorpora dos superficies operativas:

- `/gestion/metricas`: comportamiento de la tienda, embudo y rendimiento de adquisición y producto.
- `/gestion/estadisticas`: ventas, margen, rotación, valor de inventario y reposición sugerida para Compras y Ventas.

Los tableros deben mostrar únicamente datos comprobables. La medición comienza cuando se despliega el módulo; no se reconstruyen visitas históricas. Los pedidos existentes siguen disponibles para estadísticas transaccionales, pero su margen sólo se incluye cuando poseen un costo histórico confiable.

## Decisiones aprobadas

- La analítica es de primera parte y vive en la infraestructura actual de Django, PostgreSQL, Redis y Celery.
- No se integra Google Analytics ni se envían eventos comerciales a terceros.
- El comportamiento web se mide con identificadores aleatorios seudónimos que no contienen identidad externa. No se almacena IP, geolocalización, email, teléfono, DNI ni user-agent completo.
- Los pedidos, pagos e inventario son la fuente oficial de ventas; un evento del navegador nunca confirma una compra.
- Los eventos detallados se conservan 90 días. Las sesiones y agregados diarios se conservan 24 meses.
- El costo unitario se captura como instantánea al crear cada ítem de pedido. Los pedidos anteriores sin esa instantánea muestran margen no disponible y una cobertura explícita.
- El tráfico de `/gestion`, health checks, previsualizaciones administrativas y bots conocidos se excluye.
- La interfaz extiende el modo `Operate` de Administración y consume exclusivamente la paleta global configurada.

## Alternativas consideradas

### A. Modelo híbrido — elegido

Los eventos anónimos explican el comportamiento; pedidos, pagos e inventario aportan la verdad comercial. Permite un embudo útil sin confiar en eventos del cliente para dinero, stock o margen.

Ventajas: métricas auditables, atribución razonable, privacidad, consultas operativas y libertad para cambiar la presentación. Riesgo: exige correlacionar sesiones con carrito, checkout y pedido sin guardar datos personales.

### B. Contadores agregados únicamente

Reduce almacenamiento, pero impide recalcular embudos, comparar cohortes de fechas, depurar anomalías o responder nuevas preguntas. También vuelve difícil deduplicar sesiones y visitantes.

### C. Registro de toda interacción

Capturar clics y gestos indiscriminadamente agrega volumen, ruido y riesgo de privacidad sin mejorar las decisiones principales. Se descarta en favor de un catálogo estricto de eventos comerciales.

## Arquitectura

### Aplicación Django

Se creará `backend/analytics`, separada de `commerce`, `catalog` y `backoffice`.

- `analytics.models`: sesiones, eventos y agregados.
- `analytics.services`: normalización, deduplicación, sesión, atribución y rollups.
- `analytics.public_views`: recepción de eventos permitidos.
- `analytics.management_views`: consultas y exportaciones de los dos tableros.
- `analytics.tasks`: agregación diaria y purga por retención.
- `analytics.selectors`: consultas de lectura sin lógica de presentación.

Las estadísticas comerciales leerán modelos de `commerce` y `catalog`, pero no modificarán pedidos ni inventario.

### Frontend

- Un `AnalyticsTracker` liviano en el layout público registra navegación de App Router sin bloquear el render.
- Producto, carrito y checkout emiten eventos sólo después de que la acción correspondiente termina correctamente.
- El pago aprobado se vincula en el servidor desde el pedido; no depende de una pantalla de retorno ni de JavaScript.
- Las nuevas páginas administrativas serán server-rendered para la primera carga y usarán navegación por URL para filtros.
- Los cambios de período o dimensión actualizarán únicamente el contenido del tablero, conservarán el shell de Administración y permitirán compartir la URL.

## Identidad anónima y sesión

El navegador recibe dos valores opacos aleatorios:

- `analytics_visitor`: identificador persistente de primera parte para estimar visitantes únicos.
- `analytics_session`: identificador de una sesión de actividad.

El servidor sólo persiste un hash HMAC versionado de cada valor. Los tokens legibles no aparecen en base de datos, logs ni respuestas administrativas. Las cookies usan `Secure` en producción y `SameSite=Lax`; no contienen campos de identidad.

Una sesión nueva comienza cuando no existe sesión previa o transcurrieron 30 minutos sin actividad. La sesión no se prolonga por sondeos, recursos estáticos ni actividad de Administración. Autenticarse no vincula la cuenta con la sesión de analítica; la conversión se correlaciona mediante el identificador de sesión transportado por el checkout. Los tableros nunca exponen identidades ni permiten buscar personas por actividad.

## Catálogo de eventos

Sólo se aceptan estos eventos:

| Evento | Momento válido | Dimensiones permitidas |
|---|---|---|
| `page_view` | navegación pública completada | ruta normalizada y título funcional |
| `product_view` | detalle de producto visible | producto |
| `add_to_cart` | API de carrito confirmó el alta | producto, variante y cantidad |
| `checkout_started` | usuario ingresó al flujo con carrito válido | cantidad de líneas |
| `delivery_selected` | entrega válida confirmada | `shipping`, `pickup` o `manual_agreement` |
| `payment_started` | servidor creó o reutilizó una preferencia válida | pedido |

La compra pagada no es un evento público. Se obtiene de `Order.payment_status=paid` y se asocia a la sesión conservada en el checkout.

Cada evento tiene un UUID de idempotencia generado por el cliente. El endpoint acepta un máximo de 20 eventos por lote, rechaza nombres y campos desconocidos y limita longitud y cardinalidad. Los fallos de medición son silenciosos para el comprador y nunca bloquean catálogo, carrito o checkout.

## Atribución y dimensiones

En la primera página de cada sesión se capturan:

- `utm_source`, `utm_medium` y `utm_campaign`, saneados y limitados.
- Dominio de referencia, nunca la URL completa ni su query string.
- Tipo de dispositivo: `desktop`, `mobile`, `tablet` o `unknown`.
- Ruta de entrada normalizada, sin identificadores, tokens ni parámetros sensibles.

La atribución del tablero es de primera interacción de la sesión. Tráfico directo se etiqueta `Directo`. El dominio propio se considera navegación interna y no reemplaza la fuente original. No se implementa atribución multicanal en V1.

## Modelo de datos

### `AnalyticsSession`

- `public_id`: UUID de sesión.
- `visitor_hash`: HMAC del visitante anónimo.
- `started_at`, `last_seen_at` y `ended_at` opcional.
- Fuente, medio, campaña, dominio de referencia, dispositivo y ruta de entrada.
- Indicadores booleanos: vio producto, agregó carrito, inició checkout, eligió entrega e inició pago.
- `first_converted_at`: fecha de la primera conversión opcional; una sesión puede originar más de un pedido.
- Fechas e índices por período, fuente, dispositivo y conversión.

Las sesiones se conservan 24 meses y no se relacionan directamente con una cuenta. El checkout transporta únicamente el identificador de sesión para que el servidor pueda vincular la conversión al pedido.

### `AnalyticsEvent`

- `event_id`: UUID único de idempotencia.
- Sesión asociada.
- Tipo permitido.
- Producto y variante opcionales.
- Pedido opcional sólo para eventos creados o validados por el servidor.
- Ruta normalizada, cantidad y dimensiones estrictamente tipadas.
- `occurred_at` del servidor; la hora del cliente sólo se usa como referencia limitada para ordenar lotes.

Los eventos se conservan 90 días y se indexan por tipo, fecha, sesión y producto.

### `AnalyticsConversion`

- Sesión asociada.
- Pedido único y transacción de pago aprobada.
- Fecha efectiva de aprobación.
- Total, subtotal, descuento y envío capturados desde el pedido.
- Clave única por pedido para que retornos y webhooks repetidos no dupliquen la conversión.

Se crea idempotentemente en el servidor cuando una transacción pasa a aprobada. Una sesión puede tener varias conversiones; el embudo cuenta la sesión una sola vez y la facturación suma todas las conversiones válidas.

### `AnalyticsDailyProduct`

Agregado por fecha y producto con vistas, sesiones con vistas, agregados al carrito, checkouts atribuidos, pedidos pagados, unidades, ingreso de productos y descuentos. Permite comparar productos después de purgar eventos crudos.

### `AnalyticsDailyChannel`

Agregado por fecha, fuente, medio, campaña y dispositivo con sesiones, visitantes diarios, etapas del embudo, pedidos e ingreso atribuido.

Los agregados diarios no guardan hashes de visitantes ni usuarios y se conservan 24 meses.

### Instantánea de costo

`OrderItem` incorpora `unit_cost_snapshot`, decimal no negativo y nullable sólo para compatibilidad histórica. En pedidos nuevos se completa obligatoriamente desde `ProductVariant.cost` dentro de la misma transacción que crea el ítem.

La migración no copia el costo actual a pedidos anteriores porque produciría un margen histórico falso. Esos registros quedan nulos. Toda respuesta de margen incluye `cost_coverage_percentage`.

## Definiciones de métricas web

Todos los períodos se interpretan como `[desde, hasta)` en `America/Buenos_Aires`. La comparación usa el período inmediatamente anterior con igual duración.

- **Sesiones:** sesiones iniciadas en el período.
- **Visitantes:** `visitor_hash` distintos entre esas sesiones.
- **Conversión:** sesiones iniciadas en el período que tienen al menos una conversión pagada, divididas por sesiones; se muestra además la cobertura de atribución.
- **Facturación atribuida:** total de conversiones pagadas vinculadas a las sesiones iniciadas en el período. Los reembolsos aprobados se descuentan y se informan por separado.
- **Ticket promedio atribuido:** facturación atribuida dividida por pedidos atribuidos.
- **Abandono de checkout:** sesiones que iniciaron checkout, maduraron al menos 24 horas y no se vincularon a un pedido pagado, dividido por sesiones maduras que iniciaron checkout.
- **Tasa de producto visto:** sesiones con `product_view` divididas por sesiones.
- **Tasa de carrito:** sesiones con `add_to_cart` divididas por sesiones con producto visto.
- **Tasa de inicio de checkout:** sesiones con checkout dividido por sesiones con carrito.
- **Tasa de llegada al pago:** sesiones con pago iniciado divididas por sesiones con checkout.

Los pasos del embudo cuentan sesiones únicas, no cantidad de eventos. Los porcentajes sin denominador muestran `Sin datos`, nunca `0 %` engañoso.

## Definiciones de compras y ventas

- **Cobros aprobados:** suma de `PaymentTransaction.amount` con `approved_at` dentro del período.
- **Reembolsos aprobados:** suma de `Refund.amount` con estado aprobado y `updated_at` dentro del período.
- **Ventas netas:** cobros aprobados menos reembolsos aprobados.
- **Pedidos cobrados:** pedidos distintos con transacción aprobada en el período.
- **Unidades netas:** unidades de pedidos cobrados menos unidades de pedidos reembolsados en el período. El tablero muestra ambas partes cuando el resultado incluye devoluciones.
- **Ticket promedio:** cobros aprobados divididos por pedidos cobrados; los reembolsos se muestran aparte para no ocultar el valor original de las operaciones.
- **Descuentos:** descuentos de pedidos cobrados menos descuentos restituidos por reembolsos aprobados.
- **Ingreso por envío:** envío cobrado menos envío reembolsado; no se interpreta como margen de logística.
- **Margen bruto de productos:** margen de ítems cobrados menos margen de ítems reembolsados, usando `line_total_snapshot - unit_cost_snapshot × quantity` sólo cuando existe costo cubierto.
- **Cobertura de costo:** ingreso neto de producto con costo conocido dividido por ingreso neto total de producto.
- **Valor de inventario a costo:** suma de costo por stock físico disponible de variantes finitas activas.
- **Velocidad diaria:** unidades pagadas del SKU en el período divididas por cantidad de días del período.
- **Cobertura de stock:** stock disponible dividido por velocidad diaria. Sin ventas se muestra `Sin rotación`; stock infinito se excluye.
- **Reposición sugerida:** `max(ceil(velocidad diaria × días objetivo) - stock disponible, 0)` para objetivos de 15, 30 o 60 días.

La reposición sugerida es una ayuda cuantitativa, no una orden de compra. V1 no conoce proveedor, lote mínimo ni plazo de entrega y lo informa junto a la tabla.

## API pública

| Método | Contrato | Uso |
|---|---|---|
| `POST` | `/api/v1/analytics/events/` | Registrar lote permitido y devolver aceptación sin datos de tablero |

La vista aplica límites por sesión e IP sólo en memoria de rate limiting; la IP no se persiste. Respuestas inválidas no revelan configuración interna.

## API administrativa

| Método | Contrato | Uso |
|---|---|---|
| `GET` | `/api/v1/management/analytics/web/` | KPI, embudo, series, productos, canales y dispositivos |
| `GET` | `/api/v1/management/analytics/commercial/` | ventas, margen, categorías, SKU, inventario y reposición |
| `GET` | `/api/v1/management/analytics/commercial/export.csv` | exportar detalle agregado con los filtros activos |

Parámetros comunes: `from`, `to`, `compare`. El tablero comercial agrega `category`, `brand` y `coverage_days=15|30|60`. Los rangos máximos interactivos son 24 meses; parámetros inválidos reciben errores de campo claros.

Las respuestas incluyen `data_since`, zona horaria, filtros normalizados, cobertura de atribución y cobertura de costo. Las series devuelven todos los días del período, incluso los que tienen valor cero.

## Permisos y auditoría

Se agregan permisos separados:

- `analytics.view_web_analytics` para `/gestion/metricas`.
- `analytics.view_commercial_analytics` para `/gestion/estadisticas`.
- `analytics.export_commercial_analytics` para CSV.

La sincronización de roles asigna permisos exactos:

- `Owner`: ambos tableros y exportación.
- `Content`: métricas web.
- `Catalog`: estadísticas comerciales agregadas, sin exportación.
- `Orders/Logistics`: ambos tableros y exportación.

Los enlaces de navegación se ocultan si la sesión no posee el permiso correspondiente y los endpoints siempre vuelven a validarlo. Ninguna respuesta de estos tableros incluye clientes, sesiones individuales o pedidos identificables.

Las exportaciones quedan en `ManagementAuditEvent` con actor, período y filtros, sin copiar resultados ni identificadores de visitantes.

## Pantalla de métricas web

Ruta: `/gestion/metricas`.

### Jerarquía

1. Encabezado compacto, fecha desde la que existen datos y selector de período.
2. Fila de KPI: sesiones, visitantes, conversión, facturación, ticket promedio y abandono.
3. Embudo horizontal en escritorio y vertical en móvil, con cantidad y tasa entre etapas.
4. Serie diaria que compara sesiones, carritos y ventas sin mezclar escalas monetarias con cantidades.
5. Rendimiento de producto: más vistos, mejor conversión y mayor abandono.
6. Canales y dispositivos, con sesiones, conversión e ingreso atribuido.

Cada KPI muestra valor, variación frente al período anterior y definición accesible. Una variación no se colorea como positiva o negativa cuando el sentido depende del indicador. Las filas de producto enlazan al producto administrativo y los pedidos enlazan al listado filtrado.

### Estados

- Antes del primer dato: explica que la medición comenzó en `data_since`.
- Período sin actividad: muestra `Sin datos en este período` y conserva filtros.
- Cobertura parcial de atribución: muestra porcentaje y no extrapola.
- Error: mantiene encabezado y filtros, ofrece reintento y no sustituye datos por cero.

## Pantalla de Compras y Ventas

Ruta: `/gestion/estadisticas`.

### Jerarquía

1. Encabezado, período, comparación, categoría, marca y objetivo de cobertura.
2. KPI: ventas netas, pedidos cobrados, unidades netas, ticket promedio, descuentos y margen bruto de productos; reembolsos aparecen como desglose visible.
3. Serie de ventas y margen, con ejes y leyendas explícitos.
4. Rendimiento por categoría, producto y SKU.
5. Resumen de inventario: valor a costo, variantes con riesgo y unidades sugeridas.
6. Tabla priorizada de reposición: SKU, producto, stock disponible, unidades vendidas, velocidad, cobertura y sugerencia.
7. Productos sin movimiento en el período, separados de productos nuevos sin historia suficiente.
8. Exportación CSV con filtros actuales.

La cobertura de costo se muestra junto al margen. Si es menor a 100 %, el tablero dice qué proporción está cubierta y no proyecta el resto.

## Sistema visual

Ambas superficies son una extensión `Operate` de Administración:

- Variables globales de tema para estructura, acción, orientación, fondo y texto.
- Densidad alta pero legible: KPI compactos, separación por espacio y líneas antes que sombras.
- Magenta de acción sólo para exportar o una acción principal; cian para selección, foco y orientación.
- Gráficos con paleta derivada del tema y patrones o etiquetas que evitan depender sólo del color.
- Cifras tabulares, unidades explícitas y formato monetario `es-AR`.
- Ningún color de Pulso Comercial queda fijado dentro de los componentes.

La navegación agrega `Métricas web` y `Compras y ventas` después de Inicio. El resumen operativo actual de `/gestion` se conserva y puede enlazar a ambos tableros sin duplicar sus gráficos.

## Responsive y accesibilidad

- 1440 y 1024 px: seis KPI en una grilla compacta, embudo horizontal y tablas amplias.
- 768 px: KPI en tres o dos columnas, filtros en dos filas y gráficos con leyenda inferior.
- 360 px: KPI en una columna o dos cuando el contenido cabe, embudo vertical y tablas transformadas en filas operativas sin scroll horizontal del documento.
- Todos los gráficos incluyen resumen textual y tabla accesible equivalente.
- Teclado completo, foco visible, encabezados de tabla asociados y orden lógico.
- `aria-live` sólo para actualizaciones solicitadas, no para anunciar cada punto de una serie.
- Contraste WCAG 2.2 AA en todas las paletas configurables.
- `prefers-reduced-motion` elimina interpolaciones y conserva cambios instantáneos legibles.

## Rendimiento y operación

- Los eventos se insertan en lotes pequeños y no recalculan tableros durante la compra.
- Celery agrega el día anterior y repara de forma idempotente una ventana reciente para absorber pagos tardíos.
- Una tarea diaria purga eventos de más de 90 días y sesiones/agregados de más de 24 meses.
- Redis cachea respuestas administrativas por combinación de período y filtros durante un intervalo corto; pago, pedido o movimiento de inventario invalidan la familia correspondiente.
- Consultas usan agregados y anotaciones; ninguna pantalla trae eventos individuales.
- Se agregan índices compuestos para fecha/tipo/producto, sesión/fecha, pedido y dimensiones de canal.
- Fallar la tarea de agregación genera alerta operativa, pero nunca bloquea ventas.

## Pruebas

La implementación seguirá TDD: cada comportamiento se observa fallar antes de escribir producción.

### Backend

- Creación, renovación a 30 minutos y hashing de visitante/sesión.
- Rechazo de eventos, dimensiones y lotes no permitidos.
- Idempotencia y rate limiting sin persistir IP.
- Exclusión de Administración, bots, health checks y datos sensibles.
- Asociación servidor de pedido pagado y no duplicación por webhook repetido.
- Rollups idempotentes, retención y reparación de pagos tardíos.
- Límites de período, zona horaria y comparación anterior.
- Fórmulas de embudo, abandono maduro, atribución y días sin actividad.
- Fórmulas de ventas, margen, cobertura de costo, valor de inventario y reposición.
- Pedidos reembolsados, cancelados, costo nulo, stock infinito y SKU sin rotación.
- Permisos separados y auditoría de exportación.
- Presupuesto de consultas para períodos y tablas representativas.

### Frontend

- Registro de navegación App Router sin duplicar el primer render.
- Eventos sólo después de altas de carrito y pasos de checkout correctos.
- Un fallo de analítica no altera la acción comercial ni muestra error al comprador.
- Filtros en URL, comparación, recarga parcial y vínculos operativos.
- Estados sin datos, datos parciales, error y reintento.
- Fórmulas mostradas con denominadores y cobertura correctos.
- Tablas y resúmenes accesibles equivalentes a cada gráfico.
- Aplicación de todas las paletas sin colores fijos.
- Vitest y Playwright en 360, 768, 1024 y 1440 px; Axe sin hallazgos `serious` o `critical`.

### Cierre visual con Impeccable

Después de implementar se realizará una inspección agrupada de escritorio y móvil, una corrección por lotes y una confirmación final. Se ejecutará el detector sobre los objetivos modificados y el revisor de cierre recibirá las capturas, este documento, el pedido original y el contrato visual de las superficies.

## Migración y despliegue

1. Crear tablas e índices de analítica y agregar `unit_cost_snapshot` nullable.
2. Desplegar backend compatible sin activar captura pública.
3. Activar tracker, instrumentación comercial y tareas Celery.
4. Registrar `data_since` en la primera captura aceptada.
5. Habilitar las rutas administrativas y permisos.
6. Validar que no se reciben rutas sensibles, parámetros, IP ni PII.
7. Supervisar volumen, latencia de inserción, rollup, cache y cobertura de atribución.

No se intenta backfill de comportamiento web. Las estadísticas transaccionales pueden mostrar pedidos históricos; margen y su cobertura respetan la presencia real de `unit_cost_snapshot`.

## Criterios de aceptación

- Las dos pantallas existen, están enlazadas por permiso y usan la paleta configurada.
- Visitas, embudo y canales provienen sólo de eventos anónimos permitidos.
- Ventas, pagos, unidades e inventario provienen de modelos transaccionales.
- Una compra no se duplica por retorno, recarga o webhook repetido.
- Ningún fallo de analítica bloquea navegación, carrito, checkout o pago.
- No se persiste IP, user-agent completo, query strings sensibles ni campos directos de identidad en analítica.
- Períodos, comparación, zona horaria, denominadores y coberturas son explícitos.
- Margen histórico no se inventa para pedidos sin costo capturado.
- La reposición excluye stock infinito y distingue falta de rotación de cobertura amplia.
- Los gráficos tienen equivalencia textual/tabular y funcionan con teclado.
- Las pantallas no recargan el shell completo al cambiar filtros.
- El módulo funciona en 360, 768, 1024 y 1440 px sin scroll horizontal del documento.
- Eventos detallados, sesiones y agregados cumplen la retención definida.
- La exportación respeta permisos, filtros y auditoría.

## Fuera de alcance

- Google Analytics, Meta Pixel, heatmaps, grabación de sesiones o seguimiento entre sitios.
- Identificación de personas por comportamiento o perfiles publicitarios.
- Atribución multicanal, cohortes avanzadas, predicción con inteligencia artificial o forecasting estacional.
- Proveedores, órdenes de compra, lotes mínimos, plazos de entrega y recepción de mercadería.
- Costos logísticos reales, impuestos o gastos operativos dentro del margen bruto de productos.
- Backfill de visitas, sesiones o costo histórico estimado.
- Tableros en tiempo real por WebSocket; la actualización por período y el rollup son suficientes para V1.
