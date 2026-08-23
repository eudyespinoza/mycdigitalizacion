# Consultas y reporte de problemas

Fecha: 2026-08-23
Estado: diseño funcional y visual aprobado; pendiente de revisión de este documento

## Objetivo

Agregar una mesa de ayuda propia que permita a clientes e invitados iniciar y continuar conversaciones con el equipo de la tienda. La experiencia tendrá dos entradas públicas —`/consultas` y `/reportar-problema`— y una bandeja administrativa unificada en `/gestion/consultas`.

El sistema debe conservar el hilo completo, admitir imágenes y documentos en ambos sentidos, permitir pegar adjuntos con `Ctrl + V` o con el comando nativo de clic derecho **Pegar**, y funcionar aunque no exista correo transaccional configurado.

## Decisiones aprobadas

- Consultas y problemas comparten un único motor de casos, mensajes, adjuntos, accesos y estados.
- Un invitado no se convierte automáticamente en cliente ni necesita crear una cuenta.
- El acceso del invitado se conserva mediante cookie segura; para otro navegador se usa número de caso más código privado.
- Si SMTP está configurado, se envía adicionalmente un enlace de acceso. El correo no es requisito para crear ni continuar el caso.
- Un caso sólo se vincula a una cuenta mediante el código privado; una coincidencia de email nunca alcanza para reclamarlo.
- Los formularios de alta no aparecen al abrir los listados. Se muestran únicamente después de que el usuario elige crear una consulta o reportar un problema.
- El frontend se diseña como una extensión `Operate` de Pulso Comercial y consume la paleta administrable desde las variables globales de tema.

## Alternativas consideradas

### A. Motor unificado de casos — elegida

Un modelo común distingue `consulta` y `problema`. Mensajes, adjuntos, permisos, estados, recuperación, notificaciones y administración se implementan una vez.

Ventajas: experiencia consistente, menos duplicación, reglas de seguridad únicas y posibilidad de agregar nuevos tipos posteriormente. Riesgo: los campos específicos deben modelarse sin convertir el caso común en un formulario genérico confuso.

### B. Módulos separados

Dos aplicaciones independientes simplifican cada formulario inicial, pero duplican almacenamiento, permisos, componentes y lógica de conversación. También fragmentan la bandeja de trabajo del equipo.

### C. Mesa de ayuda externa

Un proveedor externo aportaría automatizaciones avanzadas, pero introduce costo, dependencia, otra identidad visual y sincronización de datos personales fuera de la plataforma.

## Arquitectura

### Backend

Se creará la aplicación Django `support`, separada de `accounts`, `commerce` y `backoffice`.

- Los modelos y servicios del dominio vivirán en `backend/support`.
- La API pública se expondrá bajo `/api/v1/support/`.
- La API operativa se expondrá bajo `/api/v1/management/support/`.
- Las vistas públicas y administrativas reutilizarán servicios de dominio, pero tendrán serializers y permisos distintos.
- Los cambios de estado, responsable y prioridad serán transaccionales y auditados.
- Los contadores de pendientes usarán consultas indexadas y caché breve; no se cargarán hilos ni adjuntos para calcular el badge del menú.

### Frontend

- Rutas públicas en `frontend/app/consultas` y `frontend/app/reportar-problema`.
- Componentes compartidos en `frontend/components/support`.
- Contratos públicos en `frontend/lib/support`.
- Bandeja y detalle administrativo en `frontend/app/gestion/consultas` y `frontend/components/management/support`.
- Contratos administrativos separados en `frontend/lib/management`.
- Los filtros de la bandeja vivirán en la URL y las actualizaciones del hilo no recargarán la página completa.

### Actualización del hilo

V1 usará actualización después de cada acción y sondeo liviano mientras el hilo está visible. El sondeo se pausará en pestañas ocultas y no se ejecutará en casos cerrados. No se agregan WebSockets ni infraestructura en tiempo real en esta versión.

## Modelo de datos

### `SupportCase`

- `id`: clave interna.
- `public_id`: UUID no secuencial para URLs.
- `case_number`: identificador humano único, por ejemplo `CON-2026-000123`.
- `kind`: `consultation` o `problem`.
- `subject` y `category`.
- `status`: `new`, `waiting_staff`, `waiting_customer`, `resolved` o `closed`.
- `priority`: `low`, `normal`, `high` o `urgent`; sólo el equipo puede modificarla.
- `customer`: usuario opcional.
- Instantánea de contacto: nombre, email y teléfono opcional. Se conserva aunque el perfil cambie.
- `order` y `product`: relaciones opcionales.
- `source_url`: página opcional desde la que se reportó un problema, sin parámetros sensibles.
- `assigned_to`: usuario interno opcional.
- `recovery_code_hash`: nunca se almacena el código legible.
- Fechas de creación, actualización, resolución y cierre.
- Marcadores separados de última lectura para cliente y administración.

### `SupportMessage`

- Caso asociado.
- Autor autenticado opcional.
- Rol del autor: `customer`, `guest` o `staff`.
- Cuerpo de texto plano.
- Fecha de creación.
- Identificador de idempotencia para impedir mensajes duplicados por reintentos.
- Los mensajes enviados no se editan ni eliminan desde las interfaces normales; forman parte del historial del caso.

### `SupportAttachment`

- Mensaje asociado.
- Clave privada de almacenamiento y nombre original de presentación.
- MIME detectado, extensión, tamaño y hash SHA-256.
- Ancho y alto para imágenes.
- Miniatura sanitizada para imágenes permitidas.
- Fecha y actor de carga.

### Acceso invitado

`SupportGuestSession` representa un navegador mediante un token aleatorio almacenado únicamente como hash. `SupportGuestAccess` vincula esa sesión con los casos que puede abrir.

La cookie contiene el token opaco, es `HttpOnly`, `Secure` en producción y `SameSite=Lax`. Al recuperar un caso con número y código se agrega acceso a la sesión actual. Al vincularlo con una cuenta mediante el código, el caso pasa al usuario y se revocan accesos invitados recuperables.

El código privado se muestra una sola vez al crear el caso. Si SMTP está operativo, el mismo flujo envía un enlace de acceso de duración limitada. No se registran tokens, códigos, cuerpos de mensajes ni nombres de archivos en logs de aplicación.

## Categorías y flujo

### Consulta

Categorías iniciales: `productos`, `compra`, `envios`, `pagos`, `facturacion` y `otra`.

El alta solicita nombre, email, teléfono opcional, asunto, categoría y mensaje inicial. Un usuario autenticado recibe sus datos como valores iniciales editables para el caso.

### Reporte de problema

Categorías iniciales: `pedido`, `pago`, `envio`, `producto`, `cuenta`, `sitio` y `otro`.

Además de los datos de contacto y el mensaje, puede asociar un pedido propio, un producto o la página actual. Nunca puede elegir un pedido ajeno. Los datos del navegador no se recopilan automáticamente; sólo se guardará información técnica si se agrega posteriormente como campo explícito y consentido.

### Estados

1. Al crear un caso queda `new` y pendiente de administración.
2. Una respuesta del equipo lo deja `waiting_customer`.
3. Una respuesta del cliente o invitado lo deja `waiting_staff`.
4. El equipo puede marcarlo `resolved`.
5. Cliente o equipo pueden reabrir un caso resuelto con un nuevo mensaje.
6. Sólo el equipo puede cerrar. Un caso cerrado es de sólo lectura hasta que el equipo lo reabra.

Los estados se muestran con texto e icono; el color nunca es la única señal.

## API pública

| Método | Contrato | Uso |
|---|---|---|
| `GET` | `/api/v1/support/configuration/` | Categorías, límites y disponibilidad del correo |
| `GET` | `/api/v1/support/cases/` | Casos visibles para la cuenta o sesión invitada |
| `POST` | `/api/v1/support/cases/` | Crear caso y mensaje inicial mediante multipart |
| `GET` | `/api/v1/support/cases/{public_id}/` | Detalle y mensajes paginados |
| `POST` | `/api/v1/support/cases/{public_id}/messages/` | Responder con texto y adjuntos |
| `POST` | `/api/v1/support/access/` | Recuperar mediante número y código |
| `POST` | `/api/v1/support/cases/{public_id}/claim/` | Vincular a la cuenta autenticada usando el código |
| `GET` | `/api/v1/support/attachments/{public_id}/` | Descarga privada autorizada |

Los endpoints de escritura aceptan una clave de idempotencia. El servidor devuelve errores de campo en español y preserva datos no sensibles en el formulario.

## API administrativa

| Método | Contrato | Uso |
|---|---|---|
| `GET` | `/api/v1/management/support/cases/` | Bandeja paginada y filtrable |
| `GET` | `/api/v1/management/support/cases/{public_id}/` | Caso, contacto, relaciones y conversación |
| `PATCH` | `/api/v1/management/support/cases/{public_id}/` | Estado, prioridad y responsable |
| `POST` | `/api/v1/management/support/cases/{public_id}/messages/` | Respuesta administrativa con adjuntos |
| `GET` | `/api/v1/management/support/summary/` | Pendientes y badge del menú |
| `GET` | `/api/v1/management/support/attachments/{public_id}/` | Descarga privada autorizada |

La búsqueda cubre número, asunto, nombre y email mediante índices adecuados. Los filtros incluyen tipo, categoría, estado, prioridad, responsable, pendiente y rango de fechas.

## Archivos adjuntos

- Máximo 5 archivos por mensaje.
- Máximo 10 MB por archivo y 30 MB por mensaje.
- Tipos iniciales: JPEG, PNG, WebP, PDF, TXT, CSV, DOCX y XLSX.
- Ejecutables, scripts, HTML, SVG, archivos comprimidos y tipos no reconocidos se rechazan.
- Se valida extensión, MIME declarado, firma real y estructura cuando corresponda.
- Los nombres físicos son aleatorios y no conservan rutas suministradas por el cliente.
- Los archivos viven fuera del árbol público de media, bajo almacenamiento privado.
- Toda descarga pasa por una vista con autorización y usa `Content-Disposition: attachment` y `X-Content-Type-Options: nosniff`.
- Sólo miniaturas de imágenes decodificadas y regeneradas por el servidor se presentan en línea.
- Un fallo de un adjunto rechaza el envío completo; no se crea un mensaje incompleto.

La interfaz admite selector, arrastrar y soltar y pegado. El compositor escucha `ClipboardEvent`, agrega elementos de tipo archivo y conserva el texto pegado. El clic derecho utiliza el menú nativo del navegador sobre el área de escritura; no se crea un menú contextual falso. Los navegadores sólo permiten adjuntar los archivos o imágenes que expongan mediante el portapapeles.

## Permisos y privacidad

- Crear y recuperar casos admite invitados con límites de frecuencia por IP y sesión.
- Leer, responder o descargar exige ser dueño autenticado, poseer acceso invitado válido o tener permiso administrativo.
- Se añade el rol inicial `Atención`, con lectura, respuesta, asignación y cambios de estado.
- El Propietario conserva todos los permisos.
- Revelar datos de contacto completos exige permiso de atención; las listas muestran información compacta y no incluyen códigos ni tokens.
- Las respuestas administrativas, asignaciones y transiciones quedan en `ManagementAuditEvent` sin guardar cuerpos ni adjuntos.
- Los cuerpos se renderizan como texto, no como HTML. Enlaces detectados se muestran con atributos seguros.
- CSRF continúa siendo obligatorio para cookies autenticadas.
- Los límites de frecuencia cubren creación, recuperación, respuestas y descargas repetitivas.

## Notificaciones

- La administración muestra un contador de casos esperando respuesta.
- El cliente ve pendientes dentro de `/consultas` y en su cuenta.
- Cuando SMTP está configurado, Celery envía creación, respuesta y resolución con enlaces seguros.
- Cuando SMTP no está configurado, la operación continúa normalmente y no se promete un correo inexistente.
- Los intentos de correo son idempotentes y usan el sistema de notificaciones existente.

## Experiencia pública

### `/consultas`

La pantalla comienza con un listado compacto de casos visibles y la acción principal **Nueva consulta**. El alta se abre sólo al solicitarla. Cada fila muestra número, asunto, estado, última actividad y pendiente de lectura.

### `/reportar-problema`

Entrada específica con explicación breve y formulario enfocado. Después de crear, redirige al hilo común del caso.

### Hilo

- Encabezado con número, asunto, estado y última actualización.
- Conversación cronológica con autor, fecha, mensaje y adjuntos.
- Carga progresiva de mensajes anteriores.
- Compositor accesible al final con texto, adjuntos pendientes y acción de envío.
- Vista previa, tamaño, progreso, eliminación individual y error específico por archivo.
- Caso cerrado en modo lectura con explicación y sin compositor.
- Estados de carga, vacío, error, sin conexión, reintento e idempotencia visible.

## Experiencia administrativa

`/gestion/consultas` se agrega a la navegación lateral con contador de pendientes. La pantalla es una bandeja, no un formulario de alta.

- Encabezado compacto con búsqueda y filtros persistidos en URL.
- Filas completas seleccionables con tipo, número, asunto, contacto, responsable, estado y última actividad.
- Paginación servidor y carga sin traer mensajes o adjuntos.
- El detalle en `/gestion/consultas/{public_id}` usa hilo principal y panel lateral para contacto, relaciones, prioridad, responsable y estado.
- Las acciones se actualizan sin recargar toda la página y notifican conflictos de edición.
- El compositor administrativo reutiliza el comportamiento de adjuntos público, con rótulos adecuados al rol.

## Sistema visual y tema

La superficie adopta modo `Operate`: jerarquía, velocidad de lectura y estados honestos tienen prioridad. No crea una identidad paralela.

Todos los colores funcionales se resuelven desde las variables que `resolveThemeVariables` aplica en la raíz:

- `--blue` para estructura y navegación.
- `--magenta-action` para la acción primaria.
- `--cyan-action` para orientación, selección y foco.
- `--surface`, `--surface-elevated` y `--surface-cold` para fondos.
- `--ink`, `--muted` y `--line` para lectura y separación.

Pulso Comercial, Océano, Creativa, Natural y la paleta personalizada deben afectar tanto las rutas públicas como administrativas. Sólo los estados semánticos de peligro y éxito conservan sus roles accesibles globales. No se introducirán valores de marca fijos dentro de los nuevos componentes.

Los campos conservan etiquetas visibles; acciones principales miden al menos 46 px y objetivos táctiles al menos 44 px. El hilo usa superficies y separación espacial antes que sombras. No se utilizan burbujas de colores saturados que reduzcan contraste.

## Responsive y accesibilidad

- 1440/1024 px: hilo y panel de contexto en dos columnas; bandeja con columnas operativas.
- 768 px: panel de contexto debajo del encabezado y bandeja con información secundaria compactada.
- 360 px: una columna, filas apiladas y compositor dentro del viewport sin cubrir el último mensaje.
- Sin desplazamiento horizontal del documento.
- Teclado completo, foco visible, orden lógico y retorno de foco después de diálogos.
- `aria-live` para envío, progreso, errores, mensajes nuevos y cambios de estado.
- Zona de pegado y arrastre con alternativa de botón; ninguna acción depende sólo del gesto.
- Contraste WCAG 2.2 AA con todas las paletas guardables.
- `prefers-reduced-motion` elimina desplazamientos y conserva cambios de estado legibles.

## Rendimiento

- Índices por `case_number`, `kind`, `status`, `priority`, `assigned_to`, `updated_at`, email normalizado y combinaciones usadas por la bandeja.
- Listados usan `select_related`, anotaciones y paginación; nunca precargan cuerpos ni archivos.
- Mensajes se paginan por cursor y orden estable.
- Miniaturas se generan en Celery; el mensaje puede mostrarse mientras la miniatura queda pendiente.
- El sondeo usa ETag o marca `updated_at`, pausa fuera de foco y no invalida el layout completo.
- Las cargas muestran progreso y no se almacenan completas en memoria del navegador.

## Pruebas

La implementación seguirá ciclos TDD: cada comportamiento se prueba y se observa fallar antes de agregar código de producción.

### Backend

- Creación autenticada e invitada, numeración y código mostrado una sola vez.
- Acceso por cookie, recuperación correcta, código inválido, rotación y vinculación a cuenta.
- Aislamiento: otro usuario o invitado no puede listar, leer, responder ni descargar.
- Transiciones de estado y reapertura.
- Idempotencia de creación y mensajes.
- Límites, firmas, extensiones, nombres manipulados y rechazo atómico de adjuntos.
- Búsqueda, filtros, paginación e índices de gestión.
- Permisos del rol Atención y auditoría sin contenido sensible.
- SMTP habilitado/deshabilitado y reintentos idempotentes.

### Frontend

- Formularios cerrados inicialmente y apertura bajo acción explícita.
- Alta de consulta y problema, recuperación y vinculación.
- Pegado de texto, imagen y archivo; arrastre, selección, eliminación y límites.
- Hilo, mensajes nuevos, caso cerrado, error, sin conexión y reintento.
- Bandeja administrativa, filtros en URL, detalle y respuesta sin recarga completa.
- Aplicación de cada paleta mediante variables, sin estilos fijos en el módulo.
- Vitest para componentes y Playwright para flujos reales en 360, 768, 1024 y 1440 px.
- Axe sin hallazgos `serious` o `critical`, teclado completo y movimiento reducido.

### Cierre visual con Impeccable

Después de implementar se realizará una sola inspección agrupada en escritorio y móvil, una corrección por lotes y una confirmación final. Se ejecutará el detector mecánico sobre los objetivos modificados y el revisor de cierre de Impeccable recibirá las capturas, el pedido original y este contrato visual.

## Criterios de aceptación

- Un invitado puede crear, recuperar y continuar un caso sin convertirse en cliente y sin depender de SMTP.
- Cliente e invitado sólo acceden a sus propios casos y adjuntos.
- Ambos lados pueden enviar texto, imágenes y documentos mediante selector, arrastre o pegado.
- Un administrador puede buscar, filtrar, asignar, responder y cambiar estado desde `/gestion/consultas`.
- Consulta y reporte de problema tienen entradas distintas pero un hilo y una bandeja comunes.
- Los formularios de alta aparecen sólo cuando el usuario solicita agregar.
- Cambiar la paleta configurada modifica todo el módulo público y administrativo.
- El módulo funciona con teclado y en 360, 768, 1024 y 1440 px sin scroll horizontal.
- Los archivos privados no pueden recuperarse por URL pública ni mediante una sesión sin permiso.
- Ningún código, token, cuerpo o adjunto aparece en logs o auditoría.

## Fuera de alcance

- Chat en tiempo real con WebSockets.
- Bots, respuestas automáticas o inteligencia artificial.
- Notas internas, SLA, horarios de atención y escalamiento automático.
- Integraciones con WhatsApp, redes sociales o proveedores externos de helpdesk.
- Antivirus administrado; la arquitectura deja el punto de integración preparado, pero V1 se limita a lista permitida, verificación de contenido, almacenamiento privado y descarga forzada.
- Edición o eliminación ordinaria de mensajes ya enviados.
