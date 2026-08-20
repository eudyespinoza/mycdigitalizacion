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
