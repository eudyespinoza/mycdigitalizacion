# Task 6 finish review: visual storefront and CMS authoring

Date: 2026-08-20

Reviewed target: `f1c84ef5f514c9b27d6064eb24af8e82af057bfc`

Method: fresh independent finish reviewer. The reviewer read and applied, in order,
`design-taste-frontend`, `ui-ux-pro-max`, `emil-design-eng`, and `impeccable`. The
Impeccable detector was not rerun; this review consumes the already authorized result `[]`.
No product code, screenshot, raster, or `DESIGN.md` was changed.

## Verdict

- **CHANGES REQUIRED.** The rendered storefront is visually approved, but the public UI does not
  honor three required CMS authoring contracts.
- **REQUIRED:** 3.
- **OPTIONAL:** 2.
- **Visual direction:** **PASS.** Pulso Comercial is specific, coherent, responsive, and close to
  the approved composition without inventing catalog breadth.
- **Accessibility and interaction baseline:** **PASS.** Supplied evidence reports zero serious or
  critical axe findings across 360/768/1024/1440, 50 Playwright passes with 10 explicit
  viewport reductions, passing computed contrast, keyboard dialogs/map alternative, and reduced
  motion. The measured LCP proxy is 648 ms, CLS 0, and interaction-frame proxy 2 ms.
- **CMS-to-storefront authoring:** **FAIL.** Hero/promotion timing, popup policy, and brand assets
  contain admin/API controls that are absent or ignored in the public frontend.

This is a targeted contract repair, not a visual redesign. Once the three REQUIRED findings are
closed, the accepted logo treatment, hero composition, density, and sparse merchandising should
remain unchanged.

## Evidence inspected

- Product and visual authority: `PRODUCT.md`, `docs/visual-direction.md`, Task 4 brief/report/review,
  Task 6B verification report, and the implementation plan approved by the owner.
- Approved comp: `.impeccable/mocks/decision/pulso-comercial-approved.png`.
- Final real-stack captures, opened and inspected at legible scale:
  `.impeccable/review/desktop.png` (1440 x 1959),
  `.impeccable/review/mobile.png` (375 x 2939), and
  `.impeccable/review/hero-repro.png` (1536 x 1024).
- Supplied logo raster: the owner-provided `codex-clipboard-41ce53f4-2940-4639-9472-10bfe6160ead.png`.
- Final storefront, campaign, checkout, account, address, catalog, cart, order, landing model,
  serializer, admin preview, and responsive CSS sources.
- Deterministic finish evidence: detector `[]`; axe serious/critical `0`; production media and
  responsive focal checks; performance budgets; prompt provenance for both shipping rasters.

Synthetic development content is explicitly labeled in the real captures. The synthetic category,
single product, placeholder product image, price, and campaign copy are therefore fixture evidence,
not visual or content defects.

## Design assessment

Design read: Argentine B2C multi-category commerce with a luminous, trustworthy, energetic retail
language. Appropriate dials are `DESIGN_VARIANCE 6`, `MOTION_INTENSITY 4`, and
`VISUAL_DENSITY 5`.

The implementation feels authored for mycdigitalizacion rather than interchangeable ecommerce:
the supplied rounded mark is legible, the navy/cyan/magenta roles are disciplined, search leads the
header, the hero is asymmetrical, and operational trust is expressed with real product constraints
rather than ratings, urgency, or fabricated social proof. The 1536 checkpoint retains the approved
two-line desktop hierarchy and visible primary action. The 375 capture collapses in a logical order,
keeps the search reachable, turns sparse inventory into one honest product card, and avoids
horizontal overflow. The desktop one-product state uses an editorial split instead of leaving a
narrow card in a dead four-column shell.

The shape system is consistent: pill actions, 12 px inputs, 16 px surfaces, tinted blue shadows, and
one light theme. Rubik and Nunito Sans preserve the friendly commercial tone. There is no visible
em dash, blanket `transition: all`, `h-screen`, scroll listener, `scale(0)` entrance, generic purple
glow, fake review score, or unsupported payment-success claim in the frontend sources.

### Design health

| # | Nielsen heuristic | Score | Evidence |
| ---: | --- | ---: | --- |
| 1 | Visibility of system status | 4/4 | Cart, forms, checkout, payment polling, order timeline, and provider failures expose busy/success/error state. |
| 2 | Match with the real world | 4/4 | DNI, CP/CPA, Mercado Pago, pickup, shipping quote, ARS, and Argentine copy follow the customer's language. |
| 3 | User control and freedom | 3/4 | Checkout has back/edit paths and filters can be cleared; some advertised CMS controls currently have no public effect. |
| 4 | Consistency and standards | 3/4 | The visual and interaction systems are consistent, but admin/API and storefront disagree on campaign behavior. |
| 5 | Error prevention | 4/4 | Server-authoritative cart/checkout, identity gating, address confirmation, stock checks, and disabled actions prevent invalid irreversible steps. |
| 6 | Recognition rather than recall | 4/4 | Labels, breadcrumbs, visible filters, stepper, order timeline, and textual map alternative retain context. |
| 7 | Flexibility and efficiency | 3/4 | Keyboard and mobile paths are strong; the checkout is intentionally linear and campaign controls need completion. |
| 8 | Aesthetic and minimalist design | 4/4 | Hierarchy is decisive and the sparse fixture is not padded with invented products or metrics. |
| 9 | Error recovery | 4/4 | Stable server codes, preserved input, bounded polling, retry paths, and correction-step routing are present. |
| 10 | Help and documentation | 2/4 | Contextual helper copy is useful, but the public storefront has no broader help/support surface beyond operational explanations. |
| **Total** |  | **35/40** | **Good, visually ready; contract repairs remain.** |

Cognitive load is low: the landing has one dominant discovery action, catalog options are grouped,
and checkout reveals one decision at a time while keeping review context visible. The emotional
journey also works: product energy peaks in the hero, the trust facts lower perceived risk, and the
checkout/payment copy becomes deliberately sober at the highest-stakes moment.

## REQUIRED findings

| # | Severity | Before | After | Why and exact evidence |
| ---: | --- | --- | --- | --- |
| R1 | **P1** | The backend publishes ordered hero and promotion slides with `interval_ms` and `pause_on_reduced_motion` (`backend/landing/models.py:163-178`, `backend/landing/serializers.py:80-97`), but the homepage renders only `home.hero_slides[0]` (`frontend/app/page.tsx:52`). `PromotionCarousel` provides manual `scrollBy(... behavior: "smooth")` only and never consumes interval or reduced-motion fields (`frontend/components/home/promotion-carousel.tsx:10-14`). The TypeScript contract omits both fields (`frontend/lib/types.ts:1-11`). | Add an accessible hero carousel that consumes all scheduled hero rows. Make hero and promotion timing use the authored interval, pause for focus/hover/page visibility, expose previous/next controls and slide state, and disable automatic/spatial motion when the row requests reduced-motion pause. Avoid `smooth` scrolling when reduced motion is active. Add unit and four-viewport browser tests with at least two slides and differing intervals. | The owner explicitly required a hero carousel and configurable carousel interval/pause. Today an editor can publish a second hero or change timing and see no corresponding public result. This is a real CMS authoring failure hidden by the one-slide synthetic fixture. |
| R2 | **P1** | `PromotionPopup` rows expose `frequency`, `display_delay_ms`, `dismissible`, desktop/mobile images, alt text, focal point, and schedule (`backend/landing/models.py:198-213`, `backend/landing/serializers.py:106-114`). The homepage passes only ID/title/body/CTA from the first row (`frontend/app/page.tsx:63`); the component appears immediately after hydration, always has a close button, always uses per-tab `sessionStorage`, and never renders the authored image (`frontend/components/home/promotion-popup.tsx:7-16`). The frontend popup type also erases the policy fields (`frontend/lib/types.ts:1-11`). | Define a typed popup contract and honor `once_session`, `daily`, `weekly`, and `always`, the authored delay, `dismissible`, and the optional responsive image/alt/focal data. Use a campaign/versioned storage key with testable time injection, keep the popup non-blocking and screen-reader announced, and cover remount, elapsed-day/week, non-dismissible, delayed, and image cases. | The admin currently presents meaningful controls that are no-ops in production. A daily notice behaves once per tab, a non-dismissible notice can be closed, delay is ignored, and uploaded popup imagery is invisible. This contradicts the approved popup/frequency/CMS contract. |
| R3 | **P1** | The public header hardcodes `/brand/mycdigitalizacion-logo.png` twice (`frontend/components/layout/site-header.tsx:23-25`), root metadata declares no icon (`frontend/app/layout.tsx:9-12`), and `SiteSettings` has no logo or favicon media fields (`backend/landing/models.py:16-23`). The current supplied-logo crop is visually accepted, but it cannot be replaced from the unified admin. | Add validated logo and favicon fields to the singleton settings model and admin, preserve the supplied assets as safe defaults, publish same-origin URLs/derivatives, load the active logo in every storefront header, and generate favicon metadata from the active setting with a deterministic fallback. Preserve aspect ratio, clear space, accessible home naming, and current Pulso colors. Add admin/API/storefront/metadata replacement tests. | The implementation plan explicitly requires logo and favicon control from the same panel as all landing media. Neither asset is authorable today, and no favicon ships from `frontend/app`. This is independent of the accepted visual quality of the current logo treatment. |

## OPTIONAL findings

| # | Severity | Before | After | Why and exact evidence |
| ---: | --- | --- | --- | --- |
| O1 | **P2** | At 375 px, the `Productos para descubrir` heading competes with `Ver más productos`; the link wraps to three short lines in the final mobile capture. Mobile keeps the shared horizontal heading and only reduces type (`frontend/app/styles.css:372-374`). | Below roughly 420 px, let the heading own the row and place the tertiary link below it or align it on a second row. Keep the link label unbroken where possible. | Nothing is inaccessible, but the current wrap adds avoidable visual noise at the exact point where product discovery should scan fastest. |
| O2 | **P2** | Applied-filter chip buttons have `min-height: 38px` (`frontend/app/styles.css:180-181`) while the project interaction contract uses 44 px touch targets. | Raise the chip hit area to at least 44 px without making the visual pill materially heavier. | Axe remains clean and the labels are usually wide, so this is not a release blocker; it is a measurable mobile motor-accessibility polish item. |

## Accepted strengths and non-findings

- The approved comp and real captures share the same search-led retail pulse, asymmetric hero,
  conversion color, cold surfaces, and practical trust language.
- The supplied logo is preserved and legible at desktop and phone sizes. R3 concerns authoring, not
  a request to redraw or replace the mark.
- Responsive CMS images, focal position, safe heights, same-origin optimization, and the sparse
  product composition are accepted. The previous double-preload/focal override defect is not
  reopened.
- Empty, loading, error, unavailable, identity-review, payment, shipment, and map-confirmation
  states are represented with direct recovery copy.
- Focus, dialog escape/containment/return, first-invalid focus, textual coordinates, contrast, and
  reduced-motion gates have credible automated evidence. The carousel repair must retain them.
- The four service notes form one divided operational strip, not an equal generic marketing-card
  wall. Their factual copy is supported by implemented flows.
- The synthetic badge and fixture labels prevent development data from becoming fabricated public
  claims. They should be removed by production content, not redesigned in code.

## Acceptance for the follow-up

1. Configure two hero slides with different intervals and prove both are reachable by controls;
   automatic movement must stop under the configured reduced-motion behavior.
2. Configure promotion timing and prove the public carousel follows the admin value without losing
   keyboard controls or focus.
3. Exercise popup `once_session`, `daily`, `weekly`, `always`, delay, non-dismissible, and image
   authoring with deterministic component/browser tests.
4. Replace logo and favicon through Django Admin and prove the public header plus favicon metadata
   update without a code change; fallback remains the supplied brand asset.
5. Re-run the existing axe/Playwright/production-media gates. A new visual comp is unnecessary; one
   bounded desktop/mobile regression capture is sufficient because the accepted layout should not
   change.

---

## Re-revisión final de las reparaciones

Fecha: 2026-08-20

Commits revisados:

- Backend: `b1b5ad904270a6676a949d94d83c4488b91bcdb1`.
- Frontend: `721c1cffe7d53f5d27589a0786971924306f79ed`.

Método: revisor independiente fresco. Se volvieron a leer y aplicar completamente, en este orden,
`design-taste-frontend`, `ui-ux-pro-max`, `emil-design-eng` e `impeccable`, además del informe
original y los informes de reparación backend/frontend. El detector Impeccable no se volvió a
ejecutar; se conservó el resultado autorizado `[]`. No se modificó producto, infraestructura,
capturas ni `DESIGN.md`.

### Veredicto final

- **SPEC: CHANGES REQUIRED.** R1, R2 y R3 avanzaron, pero los tres siguen parcialmente abiertos
  con reproducciones determinísticas que contradicen los criterios de aceptación originales.
- **QUALITY: CHANGES REQUIRED.** La dirección visual aceptada permanece fuerte, pero una anchura
  real de 360 px tiene desborde horizontal y un logo reemplazado desde CMS pierde su proporción.
- **Resultado agregado, sobre los cinco hallazgos originales:** `resolved 2`, `partial 3`,
  `unresolved 0`.
- **REQUIRED restantes:** 3 parciales. **OPTIONAL restantes:** 0.

La conclusión no pide rediseñar la tienda. Requiere tres correcciones acotadas de comportamiento y
presentación que preserven Pulso Comercial.

### Disposición de R1-R3 y O1-O2

| Hallazgo | Estado | Before | After requerido | Why / evidencia exacta |
| --- | --- | --- | --- | --- |
| R1 | **PARTIAL, P1** | Los dos carruseles ahora consumen todas las filas, el intervalo activo, pausa por hover/foco/visibilidad, controles manuales y reduced motion. Sin embargo, la cabecera de promociones conserva la fila horizontal genérica de `.section-heading` en 360 px; sólo `.featured .section-heading` cambia a columna bajo 420 px (`frontend/app/styles.css:105`, `frontend/app/styles.css:133`, `frontend/app/styles.css:430-431`). La pista también admite scroll táctil, pero no escucha `scroll`, por lo que el indicador sólo cambia por `carousel.go` (`frontend/components/home/promotion-carousel.tsx:15-18`). | Hacer que la cabecera de promociones se recomponga dentro de 360 px, sin recortar controles ni ampliar el documento. Sincronizar el índice con el slide que queda visible tras scroll/snap táctil, o impedir ese camino y conservar controles equivalentes. Mantener los intervalos, pausas y reduced motion ya correctos. | Runtime a 360 px: `innerWidth=360`, `document.documentElement.scrollWidth=387`; `.carousel-control-row` termina en `x=387.375` y el botón siguiente ocupa `343.375..387.375`, 27.375 px fuera del viewport. Tras mover la pista al final, `scrollLeft=330` pero el estado sigue siendo `Promoción 1 de 2`. La captura real `360.png` muestra el mismo control cortado. Esto incumple el checkpoint responsive de 360 y hace falsa la posición anunciada después de un gesto disponible. |
| R2 | **PARTIAL, P1** | Delay, imagen responsive, focal, versión, `always` y ventanas daily/weekly después de cerrar están implementados. La marca de frecuencia se escribe únicamente dentro de `dismiss()` (`frontend/components/home/promotion-popup.tsx:32-37`), y `dismiss()` sólo es alcanzable desde el botón condicionado por `popup.dismissible` (`frontend/components/home/promotion-popup.tsx:41`). | Registrar la impresión al hacerse visible para `once_session`, `daily` y `weekly`, o definir otra política equivalente que también funcione para campañas no descartables. Añadir un test de remount/reload del caso `dismissible=false`; conservar `always` sin supresión. | Runtime con `{ popupEnabled:true, popupFrequency:"once_session", popupDismissible:false }`: al mostrarse, `sessionStorage.getItem("myc-popup:8:v1") === null`; después de `reload`, el popup vuelve a estar visible y la clave sigue siendo `null`. La prueba actual sólo verifica que no exista el botón (`cms-campaigns.test.tsx:122-132`) y no remonta ese caso. La frecuencia de aparición configurada por el editor queda inoperante precisamente cuando el aviso no se puede cerrar. |
| R3 | **PARTIAL, P1** | El backend/admin/API ya publican logo y favicon, el layout genera metadata de favicon y todos los headers reciben el branding activo. No obstante, el mismo logo completo se dibuja dos veces (`frontend/components/layout/site-header.tsx:14-24`, `42-43`) y se corta con tamaños independientes que fuerzan ancho y alto (`frontend/app/styles.css:63`, `65`). | Mostrar el logo administrado sin depender de las coordenadas internas del raster entregado. Preservar su relación de aspecto y clear space con una sola cerradura visual, o modelar mark y wordmark como activos separados con previews/validación explícitos. `object-fit: contain` es un fallback seguro para un único logo. | Runtime con un reemplazo CMS cuadrado: el mark tiene natural `64x64` y render `108x87.83`; el word tiene natural `209x209` y render `151.03x145.8`; ambos reportan `object-fit: fill`. La sustitución cambia la URL, pero distorsiona y recorta cualquier activo que no replique exactamente la geometría privada del raster original. Esto no satisface el requisito original de preservar proporción y permitir reemplazo sin código. |
| O1 | **RESOLVED** | A 375 px el enlace competía con el título y se partía en tres líneas. | Bajo 420 px, el título ocupa su fila y el enlace pasa a una segunda fila de 44 px (`frontend/app/styles.css:430-431`). | La captura real de 360 px y el browser test confirman una jerarquía limpia; el enlace ya no compite con el título. |
| O2 | **RESOLVED** | Los chips tenían `min-height: 38px`. | Los chips tienen `min-height: 44px` (`frontend/app/styles.css:188`). | El test de navegador mide al menos 44 px en los cuatro proyectos. El objetivo motor se cumple sin engrosar visualmente la píldora. |

### Reproducción exacta de los REQUIRED restantes

Levantar el mismo runtime usado por Playwright:

```powershell
# Terminal 1
cd D:\mycdigitalizaciones\frontend
node tests/mock-api.mjs

# Terminal 2
cd D:\mycdigitalizaciones\frontend
$env:API_INTERNAL_URL='http://127.0.0.1:4010/api/v1'
$env:API_PROXY_TARGET='http://127.0.0.1:4010'
pnpm dev
```

R1, en Chromium con viewport `360x800`, abrir `/` y ejecutar:

```js
const controls = document.querySelector('.carousel-control-row').getBoundingClientRect();
const track = document.querySelector('.promo-track');
track.scrollLeft = track.scrollWidth - track.clientWidth;
track.dispatchEvent(new Event('scroll', { bubbles: true }));
({
  viewport: innerWidth,
  pageWidth: document.documentElement.scrollWidth,
  controlsRight: controls.right,
  scrollLeft: track.scrollLeft,
  announced: document.querySelector('.carousel-control-row span').textContent,
});
// { viewport: 360, pageWidth: 387, controlsRight: 387.375,
//   scrollLeft: 330, announced: "Promoción 1 de 2" }
```

R2, configurar el mock y recargar:

```js
await fetch('http://127.0.0.1:4010/__control', {
  method: 'POST',
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify({ reset: true, popupEnabled: true,
    popupFrequency: 'once_session', popupDismissible: false }),
});
location.href = 'http://127.0.0.1:3000/';
// Cuando aparezca el aviso:
sessionStorage.getItem('myc-popup:8:v1'); // null
location.reload();
// El aviso reaparece y la clave continúa null.
```

R3, configurar `logoUrl: "/media/branding/logo/active.png"`, abrir `/` y ejecutar:

```js
[...document.querySelectorAll('.brand img')].map((img) => {
  const rect = img.getBoundingClientRect();
  return {
    natural: [img.naturalWidth, img.naturalHeight],
    rendered: [rect.width, rect.height],
    objectFit: getComputedStyle(img).objectFit,
  };
});
// [{ natural:[64,64], rendered:[108,87.83], objectFit:'fill' },
//  { natural:[209,209], rendered:[151.03,145.8], objectFit:'fill' }]
```

### Inspección visual acotada

Se abrieron una sola vez las capturas finales solicitadas:

- `.impeccable/review/360.png`.
- `.impeccable/review/1440.png`.
- `.impeccable/review/hero-repro.png`.

Pulso Comercial conserva su especificidad: buscador protagonista, hero asimétrico, logo original
legible, jerarquía navy/cyan/magenta, densidad comercial media y tratamiento editorial honesto para
un catálogo sintético de un producto. Los datos marcados como sintéticos siguen siendo evidencia de
fixture y no defectos. La captura 360 confirma la mejora O1 y también el recorte del control R1; 1440
y el hero 1536 conservan la composición aprobada sin regresión visible.

### Verificación independiente

| Gate | Resultado |
| --- | --- |
| Frontend unitario focalizado | PASS: `pnpm exec vitest run tests/cms-campaigns.test.tsx`, 8/8. |
| Backend focalizado | PASS: `APP_ENV=test ... pytest tests/test_task6_finish_cms_contracts.py -q`, 4/4. Un primer intento sin `APP_ENV=test` fue rechazado por el guard de entorno antes de recolectar tests; no fue un fallo de producto. |
| Browser CMS, cuatro viewports | PASS: `pnpm exec playwright test tests/e2e/cms-finish.spec.ts`, 12/12. |
| Runtime adversarial | FAIL esperado: reprodujo R1, R2 y R3 con las métricas anteriores, casos que la suite verde no afirma cubrir. |
| Detector Impeccable | No ejecutado por instrucción; resultado heredado `[]`. |

Los gates existentes son válidos para lo que ejercitan. No invalidan los tres REQUIRED porque sus
assertions actuales no miden anchura total de documento/scroll táctil, remount no descartable ni
proporción renderizada de un logo reemplazado.

### Criterio de cierre actualizado

1. En 360 px, `documentElement.scrollWidth` no debe superar `clientWidth`; ambos controles de
   promociones deben quedar completamente dentro del viewport y el indicador debe seguir el snap
   visible después de touch/scroll.
2. Un popup `once_session`, `daily` o `weekly` no descartable debe registrar su impresión y no
   reaparecer antes de su ventana; `always` debe seguir reapareciendo.
3. Un logo CMS de relación 1:1 y otro horizontal deben conservar sus proporciones en header desktop
   y móvil. El favicon y el nombre accesible ya correctos no deben regresar.
4. Repetir los 8 unitarios, 4 contratos backend y 12 browser CMS, añadiendo los tres casos
   adversariales anteriores. No hace falta una nueva dirección visual ni ejecutar el detector.

---

## Re-revisión final acotada: Fix Round 2

Fecha: 2026-08-20

Commit revisado: `0450b12e073bf101d9bb422c6f0891f9f1ba98da`, sobre
`721c1cffe7d53f5d27589a0786971924306f79ed` y backend
`b1b5ad904270a6676a949d94d83c4488b91bcdb1`.

Alcance: exclusivamente las reproducciones adversariales R1, R2 y R3 del dictamen anterior y la
no regresión de O1/O2. Se revisó código y se volvieron a ejecutar los gates focalizados. No se
reabrieron capturas, no se modificó producto, no se ejecutó el detector Impeccable y no se creó
`DESIGN.md`.

### Veredicto definitivo

- **SPEC: APPROVED.** Los tres REQUIRED anteriores satisfacen sus criterios adversariales exactos.
- **QUALITY: APPROVED.** No queda desborde en 360 px, el estado táctil es veraz y el branding CMS
  conserva proporción en los dos formatos probados.
- **Resultado agregado, sobre los cinco hallazgos originales:** `resolved 5`, `partial 0`,
  `unresolved 0`.
- **REQUIRED restantes:** 0. **OPTIONAL restantes:** 0.

### Cierre por hallazgo

| Hallazgo | Estado | Before | After verificado | Why / evidencia exacta |
| --- | --- | --- | --- | --- |
| R1 | **RESOLVED** | A 360 px el documento medía 387 px, el botón siguiente terminaba fuera del viewport y un scroll/snap al segundo slide seguía anunciando `Promoción 1 de 2`. | La cabecera de promociones se apila bajo 420 px (`frontend/app/styles.css:425-426`). La pista calcula el slide más cercano tras scroll asentado y llama al estado autoritativo (`frontend/components/home/promotion-carousel.tsx:12-37`). | El browser test mide `scrollWidth <= clientWidth`, bounds completos de controles/botones y, después de mover la pista al final, observa `Promoción 2 de 2` (`frontend/tests/e2e/cms-finish.spec.ts:33-66`). Pasó en la matriz 36/36; el caso adversarial relevante pasó en 360 y el estado táctil también en 768. |
| R2 | **RESOLVED** | Un popup no descartable nunca ejecutaba `dismiss()`, no escribía la impresión y reaparecía en cada reload. | La impresión se registra en el efecto posterior al render visible para `once_session`, `daily` y `weekly`; `always` no escribe clave (`frontend/components/home/promotion-popup.tsx:20-42`). | Vitest remonta y valida las tres políticas no descartables más `always` (`frontend/tests/cms-campaigns.test.tsx:149-176`). Playwright repite el flujo con reload para `once_session`, `daily`, `weekly` y confirma recurrencia sin clave para `always` (`frontend/tests/e2e/cms-finish.spec.ts:89-109`). Todos pasaron. |
| R3 | **RESOLVED** | El mismo raster se dibujaba dos veces con crops y ancho/alto forzados, deformando reemplazos cuadrados u horizontales. | El header presenta un solo `picture/img`; el contenedor limita la caja y la imagen usa dimensiones automáticas más `object-fit: contain` (`frontend/components/layout/site-header.tsx:12-24`, `frontend/app/styles.css:60-62`). | El browser test exige un único `img`, compara `renderedRatio` contra `naturalRatio` con tolerancia menor a `0.02` y lo ejecuta con logo cuadrado y horizontal (`frontend/tests/e2e/cms-finish.spec.ts:111-128`). Pasó en los cuatro viewports. Favicon y nombre accesible permanecen cubiertos por el test base. |
| O1 | **RESOLVED, sin regresión** | El enlace de descubrimiento competía con el título en móvil. | El título y enlace conservan filas separadas bajo 420 px (`frontend/app/styles.css:423-424`). | El test mide que el enlace comienza después del final del título en móvil (`frontend/tests/e2e/cms-finish.spec.ts:130-141`). Pasó 36/36. |
| O2 | **RESOLVED, sin regresión** | Los chips tenían una altura mínima inferior a 44 px. | `min-height: 44px` permanece en `frontend/app/styles.css:184`. | El test vuelve a medir `height >= 44` (`frontend/tests/e2e/cms-finish.spec.ts:141-145`). Pasó en los cuatro viewports. |

### Evidencia independiente final

| Gate | Resultado fresco |
| --- | --- |
| Vitest CMS focalizado | **PASS 13/13**: `pnpm exec vitest run tests/cms-campaigns.test.tsx`. |
| Backend CMS focalizado | **PASS 4/4**: `APP_ENV=test ... pytest tests/test_task6_finish_cms_contracts.py -q`. |
| Playwright CMS | **PASS 36/36**: `pnpm exec playwright test tests/e2e/cms-finish.spec.ts`, proyectos 360/768/1024/1440. |
| R1 adversarial | **PASS**: ancho y bounds en 360; snap anunciado en móvil. |
| R2 adversarial | **PASS**: impresión inmediata + reload para no descartable `once_session`, `daily`, `weekly`; `always` recurre sin clave. |
| R3 adversarial | **PASS**: una sola imagen y proporción conservada para logo cuadrado/horizontal. |
| O1/O2 | **PASS**: segunda fila móvil y objetivo de 44 px. |
| Detector Impeccable | No ejecutado por instrucción; el resultado previo sigue siendo `[]`. |

No se encontraron REQUIRED ni OPTIONAL nuevos dentro del alcance acotado. La reparación preserva la
dirección Pulso Comercial ya aprobada y cierra el finish review.
