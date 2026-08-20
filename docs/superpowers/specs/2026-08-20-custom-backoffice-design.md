# Backoffice propio de mycdigitalizacion

Fecha: 2026-08-20
Estado: aprobado conceptualmente por el propietario; pendiente de revisión de este documento

## Objetivo

Reemplazar por completo el uso operativo de Django Admin por un backoffice visual propio, integrado a la aplicación y disponible en `/gestion`. Toda configuración comercial y operativa debe administrarse mediante pantallas diseñadas para usuarios no técnicos.

El acceso `/admin/` no formará parte del producto ni se enlazará desde ninguna pantalla. Al finalizar la migración funcional deberá responder `404` en producción. Los comandos técnicos de recuperación y despliegue seguirán disponibles únicamente por consola en la VPS.

## Alternativas consideradas

### A. Backoffice integrado en el Next.js actual — elegida

Agregar `/gestion` al frontend existente y crear una API REST privada y versionada en Django bajo `/api/v1/management/`. Reutiliza autenticación, componentes visuales, despliegue y dominio, pero mantiene una frontera clara entre storefront y operación.

Ventajas: experiencia coherente, una sola aplicación para desplegar, menor costo operativo, control visual completo y reutilización del dominio actual. Riesgo: exige disciplina para que el código del storefront y el backoffice permanezcan modularizados.

### B. Aplicación Next.js separada

Crear un segundo frontend y, opcionalmente, un subdominio como `gestion.dominio.com`. Aísla completamente los paquetes y el despliegue, pero duplica infraestructura, autenticación, componentes, builds y monitoreo sin aportar suficiente valor en esta etapa.

### C. Framework de administración genérico

Usar una biblioteca headless para generar CRUD rápidamente. Reduce el tiempo inicial de tablas, pero limita el control visual, favorece flujos técnicos y no resuelve bien editores de landing, productos con variantes, logística, mapas ni acciones sensibles.

Se elige la alternativa A. Django continuará siendo el backend y la fuente autoritativa del dominio, pero Django Admin dejará de ser una interfaz del sistema.

## Arquitectura

### Frontend

- Rutas privadas bajo `/gestion` dentro de Next.js App Router.
- Layout propio con navegación lateral colapsable, encabezado contextual, búsqueda global y accesos rápidos.
- Protección de rutas en servidor y revalidación de permisos en cada operación; ocultar un botón nunca será el control de seguridad.
- Componentes separados del storefront en `frontend/app/gestion`, `frontend/components/management` y `frontend/lib/management`.
- Formularios con validación cliente para asistencia y validación servidor como autoridad final.
- Tablas con filtros en URL, paginación, orden, selección, estados vacíos, exportación y vistas móviles utilizables.
- Editores complejos por secciones o pasos; no se expondrán formularios interminables que reflejen directamente modelos de base de datos.

### Backend

- API privada bajo `/api/v1/management/` con contratos OpenAPI explícitos.
- Vistas y serializers de gestión separados de los contratos públicos.
- Paginación, filtros, búsquedas y errores tipados comunes a todos los módulos.
- Servicios de dominio existentes para stock, cancelación, reembolso, identidad y contenido; las vistas no duplicarán reglas comerciales.
- Control de concurrencia mediante versión o `updated_at` para evitar que dos operadores sobrescriban cambios silenciosamente.
- Acciones sensibles transaccionales, idempotentes y auditadas.

### Eliminación de Django Admin

La migración se hará por paridad funcional. Una función se retira del Admin cuando su pantalla propia, permisos, auditoría y pruebas estén completas. En el cierre:

- se elimina la ruta `/admin/` y los accesos asociados;
- se retira el middleware y las plantillas específicas del Admin que ya no sean necesarias;
- se eliminan o archivan registros `ModelAdmin` sin uso;
- las operaciones de emergencia quedan como comandos de gestión documentados, no como una segunda interfaz oculta.

## Navegación y pantallas

### 1. Inicio

- Ventas, pedidos, pagos pendientes, alertas de stock y estado de integraciones.
- Tareas que requieren atención: identidad manual, pago tardío, envío sin tarifa, reembolso fallido y contenido por vencer.
- Acciones rápidas adaptadas al rol.

### 2. Catálogo

- Productos: listado, alta, edición, duplicación, baja lógica, SEO y vista previa pública.
- Variantes: SKU, código de barras, atributos, precio, costo, stock, peso y dimensiones.
- Imágenes: carga múltiple, orden, texto alternativo, punto focal y derivados.
- Categorías jerárquicas, marcas, definiciones de atributos y opciones.
- Importación CSV con simulación previa, errores por fila y confirmación atómica.
- Exportación segura a CSV/XLSX.

### 3. Inventario

- Stock actual, reservado y disponible por variante.
- Ajustes con motivo obligatorio.
- Historial inmutable de movimientos, actor, origen y pedido relacionado.
- Alertas y umbrales de reposición.

### 4. Pedidos y logística

- Listado con filtros por identidad, pago, entrega, fecha y atención requerida.
- Detalle con línea de tiempo, cliente, ítems, importes, dirección, bultos, pago y auditoría.
- Acciones permitidas según estado: aprobar identidad, preparar, despachar, cancelar y reintegrar.
- Etiqueta, tracking, reintentos y diagnóstico seguro de proveedores.
- Configuración de cajas, retiro, servicios habilitados, recargos y envío gratuito.

### 5. Clientes

- Búsqueda y detalle de cuenta, estado de email, identidad y pedidos.
- Datos personales y fiscales enmascarados por defecto.
- Revelado excepcional con permiso, reautenticación, motivo y auditoría.
- Direcciones, ubicación confirmada y revisiones manuales.

### 6. Marketing y landing

- Identidad de marca: logo, favicon y datos generales.
- Hero, promociones, colecciones, categorías destacadas y popup.
- Carga desktop/móvil, texto alternativo, punto focal, enlace, CTA, orden, programación y alturas seguras por breakpoint.
- Reordenamiento accesible, duplicación, activación y vista previa real antes de publicar.
- Popup con demora, frecuencia, versión, vigencia y comportamiento de cierre.

### 7. Promociones

- Reglas automáticas por producto o categoría.
- Cupones, límites, combinabilidad, vigencia y cupos.
- Simulador que explique qué descuento se aplicaría a un carrito de prueba.

### 8. Integraciones

- Mercado Pago: modo, credenciales, collector, webhook, prueba de conexión y último evento.
- Correo Argentino: ambiente, credenciales, servicios, origen, cotización y prueba de conexión.
- SID RENAPER: modo, credenciales, consentimiento y estado del servicio.
- SMTP: servidor, puerto, seguridad, remitente, credenciales y envío de prueba.
- Geolocalización: proveedor, límites y salud de sincronización de localidades.
- Backups externos: destino, retención, última copia y última restauración ensayada.
- Cada integración mostrará `Configurada`, `Incompleta`, `Con error` o `Deshabilitada`, sin mostrar secretos.

### 9. Usuarios, roles y auditoría

- Usuarios internos, activación, roles y segundo factor.
- Roles iniciales: Propietario, Catálogo, Pedidos/Logística y Contenido.
- Permisos de integraciones, datos sensibles, reembolsos y usuarios reservados al Propietario.
- Auditoría consultable y exportable de cambios y acciones críticas.

### 10. Configuración general

- Datos comerciales, contacto, moneda, zona horaria y textos legales.
- Punto de retiro, CP de origen y reglas de envío.
- Verificación de email, reserva de stock y plazos operativos dentro de rangos seguros.
- Configuración SEO general y enlaces institucionales.

## Secretos y configuración sensible

Los secretos operativos se podrán cargar y rotar desde `/gestion/integraciones`:

- se cifran antes de almacenarse;
- nunca se devuelven a ningún cliente, ni siquiera al Propietario;
- la API sólo informa si existen, cuándo cambiaron y quién los cambió;
- el formulario vacío conserva el valor actual y un reemplazo exige confirmación;
- cada integración ofrece una prueba controlada que no expone la credencial;
- cambios y pruebas quedan auditados, sin valores ni datos personales en logs.

Permanecerán fuera del panel únicamente los secretos necesarios para que la propia plataforma pueda arrancar: acceso a PostgreSQL y Redis, `DJANGO_SECRET_KEY`, clave maestra de cifrado, credencial del sistema de despliegue y acceso SSH. Se configuran en la VPS y el panel sólo puede mostrar su estado de disponibilidad.

Mercado Pago y webhooks admitirán rotación segura: el secreto anterior podrá validarse durante una ventana breve y explícita, tras la cual se eliminará. La preferencia de pagos siempre usará la configuración activa tomada del servidor.

## Autenticación, autorización y seguridad

- Cookies `HttpOnly`, `Secure`, `SameSite=Lax` y CSRF.
- Acceso a `/gestion` sólo para usuarios internos activos.
- Segundo factor obligatorio para Propietario y para acciones de alto impacto.
- Reautenticación reciente para revelar datos, cambiar secretos, reembolsar o modificar roles.
- Límites de frecuencia compartidos por Redis para login, 2FA y pruebas de proveedores.
- Protección contra asignación masiva: cada endpoint define campos editables.
- Archivos validados por contenido, dimensiones y nombre seguro.
- Registros de auditoría inmutables con actor, fecha, objeto, acción, motivo y resultado.

## Experiencia visual

El backoffice conservará la identidad Pulso Comercial, con un lenguaje más sobrio y denso que el storefront:

- azul como estructura y confianza, cian como navegación/estado informativo y magenta sólo para acciones primarias o alertas comerciales;
- escritorio optimizado desde 1024 px y operación completa en 360/768 px;
- navegación persistente sin robar ancho a formularios y tablas;
- espaciado consistente, etiquetas humanas y ningún texto técnico crudo para el operador;
- diagnósticos técnicos dentro de un detalle expandible, con mensaje principal accionable;
- foco visible, teclado completo, objetivos táctiles mínimos de 44 px y movimiento reducido.

## Estados y errores

- Guardados exitosos confirman qué cambió y cuándo.
- Conflictos de edición muestran la versión nueva y permiten revisar antes de sobrescribir.
- Fallos de proveedor distinguen configuración faltante, autenticación, indisponibilidad, límite y respuesta inválida.
- Una operación remota incierta nunca se reintenta con otra clave de idempotencia.
- Los formularios conservan datos no sensibles ante errores.
- Acciones destructivas requieren resumen, impacto, motivo y confirmación explícita.
- Ningún error de API, traceback, código interno o texto en inglés se muestra como mensaje principal.

## Entregas por etapas

El subsistema es demasiado amplio para una sola entrega segura. Se implementará en cortes verticales, y cada corte sustituirá funcionalidad real de Django Admin:

1. Base de `/gestion`: layout, sesión staff, permisos, 2FA, auditoría y dashboard.
2. Configuración general e integraciones, incluido almacenamiento cifrado y pruebas de conexión.
3. Catálogo, variantes, categorías, atributos, medios, importación y stock.
4. Pedidos, identidad, clientes, logística, cancelación y reintegro.
5. Landing, marca, promociones, cupones y vista previa.
6. Usuarios, roles, auditoría, exportaciones y retiro definitivo de Django Admin.

Cada etapa incluirá frontend, API, permisos, auditoría, migraciones, OpenAPI y pruebas de aceptación; no se considerará completa con pantallas estáticas o datos simulados.

## Pruebas y aceptación

- Unitarias de permisos, cifrado, rotación, validaciones y servicios de dominio.
- API por rol: lectura, escritura, denegación, errores tipados y no exposición de secretos.
- PostgreSQL para concurrencia, idempotencia y cambios de stock/pedidos.
- E2E de cada flujo operativo en 360, 768, 1024 y 1440 px.
- Axe y teclado para navegación, tablas, diálogos, editores y reordenamiento.
- Pruebas de conexión con adaptadores locales y sandbox cuando existan credenciales.
- Regresión que compruebe que `/admin/` devuelve `404` en producción.

La entrega final se acepta cuando:

- un Propietario puede operar y configurar toda la tienda desde `/gestion`;
- cada rol ve y ejecuta únicamente lo permitido;
- catálogo, stock, pedidos, clientes, landing, promociones, envíos e integraciones tienen pantallas propias completas;
- ningún secreto puede recuperarse por la API o los logs;
- toda acción sensible queda auditada;
- no existe enlace ni dependencia operativa de Django Admin;
- los mensajes visibles son claros para un usuario de negocio y están en español.

## Fuera de alcance

- Convertir el backoffice en una aplicación multiempresa.
- Crear un constructor libre de páginas.
- Exponer configuración de infraestructura que impediría arrancar la aplicación.
- Reemplazar Django, PostgreSQL, Celery, Redis o las integraciones ya elegidas.
