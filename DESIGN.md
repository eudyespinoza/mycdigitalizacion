---
name: "mycdigitalizacion - Pulso Comercial"
description: "Sistema visual luminoso, confiable y orientado a conversión para el ecommerce argentino mycdigitalizacion."
colors:
  ink: "#020530"
  structural-blue: "#002788"
  brand-cyan: "#08AECD"
  brand-magenta: "#F34887"
  wayfinding: "#007F96"
  conversion: "#BD1D59"
  conversion-deep: "#A41449"
  surface: "#FFFFFF"
  surface-cold: "#F6F9FF"
  surface-cyan: "#EAFAFF"
  muted: "#536078"
  line: "#DCE3F0"
  field-line: "#9EABC0"
  danger: "#AD173F"
  success: "#006B57"
typography:
  display:
    fontFamily: "Rubik, sans-serif"
    fontSize: "clamp(3.35rem, 4.4vw, 4.35rem)"
    fontWeight: 760
    lineHeight: 1.01
    letterSpacing: "-0.025em"
  headline:
    fontFamily: "Rubik, sans-serif"
    fontSize: "clamp(1.75rem, 3vw, 2.45rem)"
    fontWeight: 750
    letterSpacing: "-0.025em"
  title:
    fontFamily: "Rubik, sans-serif"
    fontSize: "1.2rem"
    fontWeight: 700
    lineHeight: 1.25
  body:
    fontFamily: "Nunito Sans, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Nunito Sans, sans-serif"
    fontSize: "0.82rem"
    fontWeight: 800
    lineHeight: 1.5
  action:
    fontFamily: "Rubik, sans-serif"
    fontSize: "1rem"
    fontWeight: 650
    lineHeight: 1
rounded:
  control: "12px"
  surface: "16px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "20px"
  2xl: "24px"
  3xl: "32px"
  4xl: "40px"
components:
  button-primary:
    backgroundColor: "{colors.conversion}"
    textColor: "{colors.surface}"
    typography: "{typography.action}"
    rounded: "{rounded.pill}"
    padding: "11px 24px"
    height: "46px"
  button-primary-hover:
    backgroundColor: "{colors.conversion-deep}"
    textColor: "{colors.surface}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.structural-blue}"
    typography: "{typography.action}"
    rounded: "{rounded.pill}"
    padding: "11px 24px"
    height: "46px"
  field:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "10px 12px"
    height: "46px"
  search:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.pill}"
    padding: "0 20px"
    height: "52px"
  product-card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.surface}"
    padding: "16px 18px 20px"
  filter-chip:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.structural-blue}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "7px 12px"
    height: "44px"
---

# Design System: mycdigitalizacion

## Overview

**Creative North Star: "Pulso Comercial"**

Pulso Comercial combina la energía de una tienda multirrubro con la certeza de una operación auditable. El buscador y los productos conducen la experiencia; la identidad visual aporta ritmo sin competir con precios, disponibilidad, envío ni estados de pago. La landing persuade, mientras catálogo, cuenta, checkout y administración priorizan operación clara.

La composición evita el hero genérico centrado y la repetición de tarjetas iguales. Usa superficies blancas y frías, estructura navy, orientación cian, conversión magenta, fotografía de producto nítida y asimetría controlada. Los valores de referencia son `DESIGN_VARIANCE: 7`, `MOTION_INTENSITY: 4` y `VISUAL_DENSITY: 6`.

**Características clave:**

- Buscador protagonista y navegación de categorías inmediatamente reconocible.
- Jerarquía comercial media: mucha información útil, agrupada con aire y contraste.
- Imágenes de campaña a escala amplia, con producto real como foco visual.
- Estados honestos y recuperables para stock, identidad, dirección, envío y pago.
- Español de Argentina directo, amable y sin afirmaciones comerciales inventadas.

## Colors

La paleta parte del logo suministrado. Los colores de marca y los colores de interacción son deliberadamente distintos para conservar identidad y contraste.

### Primary

- **Tinta Pulso** (`ink`): títulos, footer, bandas de confianza y estructura de máxima jerarquía.
- **Azul Estructural** (`structural-blue`): precios, enlaces jerárquicos, bordes seleccionados y navegación.
- **Magenta de Conversión** (`conversion`): compra, exploración y oferta accionable. Su variante `conversion-deep` pertenece a hover y énfasis accesible.

### Secondary

- **Cian de Orientación** (`wayfinding`): foco, categorías, iconos informativos y señales de ubicación.
- **Cian de Marca** (`brand-cyan`): identidad, selección y fondos decorativos. No reemplaza a `wayfinding` en texto pequeño.
- **Magenta de Marca** (`brand-magenta`): campañas y recursos gráficos. No reemplaza a `conversion` en botones o texto funcional.

### Neutral

- **Blanco Comercial** (`surface`): fondo general y controles.
- **Frío de Catálogo** (`surface-cold`): paneles, estados vacíos, medios de producto y agrupaciones operativas.
- **Cian Neblina** (`surface-cyan`): avisos informativos y énfasis suave.
- **Texto Secundario** (`muted`): descripciones y ayuda, nunca acciones principales.
- **Línea Fría** (`line`) y **Línea de Campo** (`field-line`): separación y contorno sin crear una grilla visual pesada.
- **Peligro** (`danger`) y **Éxito** (`success`): estados semánticos acompañados siempre por texto.

**The Conversion Rule.** El magenta oscuro indica una acción comercial. No usarlo como decoración distribuida por toda la página.

**The Guidance Rule.** El cian orienta y confirma posición. No comunica compra, descuento ni error.

**The Trust Rule.** Navy y superficies frías dominan la estructura; los acentos nunca sustituyen la legibilidad.

### Paletas administrables

Pulso Comercial es la paleta predeterminada. Administración ofrece además Océano, Creativa y Natural, junto con una opción personalizada basada en cinco roles semánticos: estructura, acción, orientación, fondo y texto. La selección se aplica desde la raíz tanto a la tienda como a Administración; no se implementan temas parciales por página.

- Estructura gobierna navegación, bandas y superficies de máxima jerarquía.
- Acción gobierna compra, guardado y llamados comerciales.
- Orientación gobierna foco, enlaces informativos y posición.
- Fondo y texto gobiernan todas las superficies y la lectura normal.
- Los estados de error, éxito y las marcas oficiales de redes sociales conservan sus colores semánticos.
- Una paleta personalizada sólo se guarda si mantiene contraste accesible entre texto, estructura, orientación, acciones y sus fondos de uso.

## Typography

**Display Font:** Rubik, cargada con `next/font` y fallback sans-serif.  
**Body Font:** Nunito Sans, cargada con `next/font` y fallback sans-serif.

**Carácter:** Rubik aporta una voz redondeada, enérgica y compatible con el logo. Nunito Sans mantiene legibles descripciones, formularios, estados y datos extensos.

### Hierarchy

- **Display** (760, escala fluida, `1.01`): hero y títulos de entrada. En escritorio el hero se limita a dos líneas; en móvil se adapta sin recorte.
- **Headline** (750, escala fluida): encabezados de secciones comerciales y páginas.
- **Title** (700, `1.2rem`): tarjetas, paneles y títulos operativos.
- **Body** (400, `1rem`, `1.6`): lectura normal. Limitar prosa a aproximadamente 62-65 caracteres cuando el layout lo permita.
- **Label** (800, `0.82rem`): disponibilidad, categorías, estados y ayudas breves.
- **Action** (Rubik 650, `1rem`): botones y acciones principales, siempre en una sola línea.

Los precios usan cifras tabulares para evitar saltos visuales. Los pesos 650-800 refuerzan jerarquía, pero el cuerpo no debe convertirse en una pared de negrita.

**The Two-Voice Rule.** Rubik habla por marca y acción; Nunito Sans explica y permite operar. No agregar una tercera familia tipográfica.

## Layout

El contenedor público usa `min(100% - 40px, 1320px)`. En escritorio, el header distribuye logo, buscador y cuenta/carrito; el hero combina copia a la izquierda con una escena de producto amplia a la derecha. Las colecciones alternan imagen y texto, mientras catálogo y checkout usan grillas operativas más previsibles.

La escala espacial sigue un ritmo base de 4/8 px. Separaciones de componente usan 8-24 px; grupos y paneles, 24-40 px; secciones de landing, 58-84 px. No introducir espacios arbitrarios cuando uno de esos niveles resuelve la jerarquía.

### Responsive

- **Mayor a 1024 px:** contenedor de 1320 px máximo, cuatro productos por fila, hero asimétrico y categorías amplias.
- **Hasta 1024 px:** header compacto, tres productos por fila, categorías en cuatro columnas y servicios en dos.
- **Hasta 768 px:** navegación móvil, hero en una columna con copia compacta e imagen limitada a 280-320 px, controles dentro del recorte, productos en dos columnas y flujos operativos en una columna.
- **Hasta 420 px:** encabezados comerciales se apilan, controles de carrusel caben completos, logo se reduce y acciones mantienen su objetivo táctil.

Las pruebas de referencia son 360, 768, 1024 y 1440 px. Ninguna superficie puede ensanchar el documento más que el viewport.

### Media administrable

- Hero, promociones, colecciones y popup admiten archivo desktop y móvil.
- El ancho lo define el componente; el editor no introduce anchos libres que puedan romper la composición.
- El punto focal X/Y se guarda de 0 a 100 y se aplica con `object-position`.
- La altura segura es independiente para móvil, tablet y escritorio, dentro del rango validado de 120 a 1200 px.
- Si sólo existe una imagen, debe degradar de forma predecible sin duplicar preload ni reemplazar el foco editorial.
- Los derivados AVIF/WebP y el original se publican desde el mismo origen, con espacio reservado para evitar CLS.

**The Mobile Reset Rule.** Toda asimetría editorial se convierte en una columna clara por debajo de 768 px; nunca se comprime hasta volverse ilegible.

## Elevation & Depth

El sistema es plano por defecto y usa profundidad sólo para distinguir una superficie interactiva o flotante. Los fondos fríos y las líneas sutiles hacen la mayor parte del trabajo.

### Shadow Vocabulary

- **Card** (`0 10px 30px rgba(0, 39, 136, 0.09)`): productos y superficies comerciales elevadas.
- **Soft** (`0 20px 60px rgba(0, 39, 136, 0.12)`): colecciones destacadas y hover de tarjeta.
- **Primary action** (`0 9px 22px rgba(189, 29, 89, 0.24)`): sólo botones de conversión.
- **Overlay** (`0 24px 70px rgba(2, 5, 48, 0.35)`): popup. Drawer y controles flotantes usan la misma familia navy translúcida.

**The Flat-by-Default Rule.** No agregar sombras a paneles informativos que ya están separados por tono, borde o espacio.

## Shapes

La geometría traduce las curvas del logo en tres niveles estables:

- **Píldora** (`999px`): botones, buscador, chips, paginación y controles agrupados.
- **Superficie suave** (`16px`): tarjetas, campañas, paneles, popup y bloques principales.
- **Control** (`12px`): inputs, avisos, líneas de carrito y componentes internos.
- **Círculo**: icon buttons, pasos y marcadores, con área interactiva mínima de 44 x 44 px.

Los bordes son fríos y finos. No mezclar esquinas rectas, redondeos arbitrarios y píldoras sin una razón funcional. Las imágenes ocupan su marco con `cover` para campañas y `contain` para producto o marca.

**The Logo Integrity Rule.** El logo administrado se muestra una sola vez por header, con proporción natural, `object-fit: contain` y espacio claro. No recortar partes internas del raster para reconstruir el lockup.

## Components

### Buttons and links

- **Primary:** píldora magenta accesible, texto blanco, altura mínima de 46 px, sombra de conversión y `scale(0.98)` al presionar.
- **Secondary:** blanco con borde y texto azul. En hover toma `surface-cyan` sin competir con el primario.
- **Text action:** azul, subrayada y con objetivo mínimo de 44 px.
- Las transiciones duran 160-200 ms con `cubic-bezier(0.23, 1, 0.32, 1)` y declaran propiedades específicas.

### Fields and search

- Las etiquetas son visibles y aparecen sobre el campo; el placeholder nunca reemplaza la etiqueta.
- Inputs y selects miden al menos 46 px, usan fondo blanco, borde `field-line` y radio de control.
- El buscador principal mide 52 px y usa forma de píldora.
- Foco: borde `wayfinding` y halo `0 0 0 3px rgba(0, 127, 150, 0.20)`. El foco global usa outline de 3 px con offset de 3 px.
- Error, ayuda y estado se ubican junto al campo y ofrecen una forma clara de recuperación.

### Product cards and catalog controls

- La tarjeta usa superficie blanca, marco de 16 px y medio de producto sobre `surface-cold`.
- La imagen de producto usa `contain`; campañas y colecciones usan `cover`.
- Precio en azul estructural, disponibilidad en éxito y oferta en magenta profundo.
- Un único producto se presenta como composición editorial imagen/copia en tablet y escritorio, y como tarjeta simple en móvil.
- Chips y facets tienen al menos 44 px de alto. Filtros activos son removibles y el estado vive en la URL.

### Header and navigation

- Franja de confianza delgada, header buscable y navegación de categorías forman un único sistema.
- El logo y favicon se leen desde `SiteSettings`; el activo suministrado es el fallback determinístico.
- El header usa una sola imagen de logo con fuentes responsivas, mantiene proporción para formatos cuadrados u horizontales y conserva un nombre accesible de inicio.
- Iconografía exclusivamente Phosphor, con tamaño y peso coherentes. No usar emoji como icono estructural.

### Hero and promotion carousels

- Cada slide consume su intervalo CMS, validado entre 1 y 30 segundos. El fallback actual es 6 segundos.
- La rotación se pausa con hover, foco, pestaña oculta y, cuando el editor lo indica, `prefers-reduced-motion`.
- Los controles anterior/siguiente son siempre visibles, miden al menos 44 px y anuncian posición con `aria-live`.
- El carrusel promocional admite scroll-snap táctil y sincroniza el indicador con el slide realmente visible.
- El cambio automático nunca impide control manual ni mueve el foco.

### Promotion popup

- El editor controla activación, calendario, delay hasta 60 segundos, CTA, imagen desktop/móvil, foco, altura, frecuencia, versión y posibilidad de cierre.
- Las frecuencias son `once_session`, `daily`, `weekly` y `always`. La impresión se registra cuando el popup se vuelve visible, incluso si no es descartable; `always` no persiste supresión.
- Cambiar la versión reinicia la ventana de frecuencia de una campaña nueva.
- Es no bloqueante, se anuncia de forma educada y reduce su entrada a un cambio casi instantáneo con movimiento reducido.

### CMS authoring and ownership

- **Contenido:** administra textos, CTA, agenda, orden, habilitación, imágenes desktop/móvil, alt, foco y alturas seguras.
- **Marca:** el singleton `SiteSettings` administra nombre público, logo, favicon, anuncio y datos de retiro, con previews y fallback seguro.
- **Código:** mantiene tokens, breakpoints, anchos de slot, composición, semántica, límites y políticas de accesibilidad. El panel no es un constructor libre.
- **Operación:** revisa contenido publicado, datos reales de catálogo y credenciales. Un asset válido no implica que un proveedor externo esté operativo.

### States, accessibility and motion

- Cubrir loading, vacío, error, sin stock, disabled, identidad en revisión, pago pendiente/fallido/aprobado por servidor y entrega/tracking.
- Mantener skip link, orden de foco, traps y retorno de foco en drawer/sheets, Escape, mensajes `aria-live`, alt obligatorio y alternativa textual al mapa.
- Color nunca es la única señal. Texto normal debe alcanzar 4.5:1; foco y gráficos de control, 3:1.
- En dispositivos con hover fino, una tarjeta puede elevarse hasta 4 px. En touch no depender de hover.
- `prefers-reduced-motion: reduce` elimina desplazamientos, suavizado de scroll y loops; conserva cambios de estado legibles.

### QA checkpoints

- Verificar 360/768/1024/1440 px, teclado completo, zoom, reduced motion y ausencia de scroll horizontal.
- Ejecutar axe sin hallazgos serious/critical y comprobar contraste de acciones, foco, badge y estados.
- Probar logo CMS cuadrado y horizontal, favicon reemplazado, imágenes desktop/móvil, foco y alturas límite.
- Probar intervalos distintos, hover/foco/visibilidad, scroll táctil y posición anunciada de ambos carruseles.
- Probar popup descartable y no descartable para las cuatro frecuencias, delay, remount/reload, versión e imagen.
- Reservar espacio para imágenes y sostener los objetivos LCP menor a 2.5 s, CLS menor a 0.1 e INP menor a 200 ms.
- Las validaciones sandbox o simuladas no autorizan afirmar éxito productivo de Mercado Pago, SID RENAPER o Correo Argentino.

## Do's and Don'ts

### Do:

- **Do** conservar el buscador como acción dominante y la compra como único CTA primario por bloque.
- **Do** usar navy para estructura, cian para orientación y magenta oscuro para conversión.
- **Do** etiquetar como sintético cualquier catálogo, precio o promoción de desarrollo.
- **Do** mantener imágenes administrables dentro de los slots, puntos focales y alturas seguras definidos.
- **Do** escribir estados directos, específicos y recuperables en español de Argentina.
- **Do** validar cada cambio de CMS en móvil y escritorio antes de publicarlo.

### Don't:

- **Don't** volver a un hero centrado, una pared de tarjetas iguales o gradientes genéricos sin función.
- **Don't** usar el magenta o cian brillante de marca para texto funcional cuando sus pares accesibles existen.
- **Don't** hardcodear logo, favicon, campañas o popup si el recurso pertenece al panel.
- **Don't** deformar, duplicar o recortar el logo administrado.
- **Don't** usar animación decorativa continua, `transition: all` ni movimiento automático contra la preferencia del usuario.
- **Don't** inventar stock, descuentos, reseñas, costos de envío, aprobación de identidad o éxito de pago.
- **Don't** confirmar pagos desde parámetros de redirección; sólo el estado verificado por servidor es autoritativo.
- **Don't** ampliar el CMS con libertad de ancho, HTML arbitrario o estilos capaces de romper Pulso Comercial.
