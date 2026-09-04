# SKU automatico de catalogo

## Objetivo

Reemplazar la carga manual de SKU por una numeracion automatica, estable y segura ante concurrencia para productos y variantes. Tambien se renumerara el catalogo existente respetando el orden historico disponible.

## Formato e invariantes

- Cada producto tiene un SKU base unico de seis digitos con formato `6NNNNN`.
- La migracion comienza en `600001`; `600000` queda reservado y no se asigna.
- Cada variante usa el SKU base del producto seguido por un sufijo correlativo de dos digitos: `600001-01`, `600001-02`, etc.
- Los SKU son de solo lectura para usuarios y administradores. No se pueden elegir ni modificar desde formularios, API o importaciones.
- Un numero asignado no se reutiliza si se elimina un producto o una variante.
- El rango admite hasta `699999` para productos y hasta 99 variantes por producto. Al agotarse, el alta falla con un mensaje explicito y no deja datos parciales.

## Asignacion y concurrencia

La numeracion de productos se respaldara con un contador persistente en la base de datos. La reserva del siguiente numero se realizara dentro de una transaccion y con bloqueo de fila, evitando que dos altas simultaneas reciban el mismo SKU.

Cada producto conservara su siguiente numero de variante. La creacion de una variante bloqueara el producto, reservara el sufijo y avanzara el contador en la misma transaccion. El contador no retrocede al eliminar variantes.

La generacion se centralizara en el dominio del catalogo y sera utilizada por la gestion web, Django Admin, importaciones y cualquier otro flujo normal de alta. Los serializadores no confiaran en valores de SKU enviados por el cliente.

## Migracion del catalogo existente

La migracion de datos se ejecutara de forma determinista:

1. Ordenar productos ascendentemente por `created_at` y usar `id` como desempate.
2. Asignar SKU base desde `600001` en adelante.
3. Ordenar las variantes de cada producto por `id` y asignar sufijos desde `01`.
4. Inicializar el contador global inmediatamente despues del ultimo producto migrado.
5. Inicializar el contador de variantes de cada producto inmediatamente despues del ultimo sufijo asignado.

`ProductVariant` no registra actualmente una fecha de creacion, por lo que su clave primaria es el unico indicador historico confiable para ordenar las variantes existentes.

La reescritura de los SKU de variantes se hara en dos fases, usando valores temporales unicos antes de colocar los definitivos, para no infringir la unicidad durante la migracion.

Los `sku_snapshot` de pedidos existentes no se modificaran: representan el SKU que tenia el articulo al confirmar la compra y forman parte del historial auditable.

Si los datos existentes exceden el rango admitido, la migracion abortara antes de publicar una asignacion parcial y describira el limite incumplido.

## Contratos de administracion

- El editor de producto mostrara el SKU base como solo lectura. Para un producto nuevo indicara que se asignara al guardar.
- Cada variante mostrara su SKU como solo lectura. Las variantes nuevas indicaran que se asignara al guardar.
- El listado principal mostrara el SKU del producto, no solamente el SKU de su primera variante.
- La busqueda administrativa aceptara tanto SKU base como SKU completos de variantes.
- Django Admin tambien tratara ambos SKU como campos de solo lectura.

## Importacion y exportacion CSV

- El SKU deja de ser obligatorio en las importaciones.
- Para mantener compatibilidad con archivos existentes, una columna `sku` presente sera aceptada pero ignorada al crear registros.
- Las exportaciones conservaran los SKU generados como informacion de consulta.
- La identidad del producto en una importacion seguira basandose en los campos funcionales ya utilizados por el importador, no en el SKU recibido.

## API y compatibilidad

- Los recursos de producto expondran el nuevo SKU base.
- Los SKU de variantes continuaran exponiendose, pero pasaran a ser de solo lectura en los endpoints de gestion.
- La creacion y edicion de productos no requerira que el frontend envie SKU.
- Los consumidores de catalogo y pedidos continuaran recibiendo cadenas SKU, por lo que no cambia el tipo del contrato.

## Validacion

Se cubriran al menos los siguientes casos:

- asignacion consecutiva de productos desde `600001`;
- asignacion consecutiva de variantes desde `-01`;
- ausencia de reutilizacion tras una baja;
- altas concurrentes sin duplicados;
- rechazo claro al superar los limites;
- SKU de solo lectura en API y administracion;
- importacion sin SKU y compatibilidad con CSV que aun lo incluya;
- migracion determinista de productos y variantes existentes;
- preservacion de SKU historicos en pedidos;
- visualizacion y busqueda por SKU base y de variante.

## Despliegue

El cambio requiere una migracion de base de datos. Antes de actualizar produccion se generara un respaldo, se verificara el CI del SHA exacto y se aplicara la migracion siguiendo `docs/operations/donweb-production.md`. Tras el despliegue se comprobaran la secuencia, la unicidad, la carga del catalogo y la creacion de un producto y sus variantes.
