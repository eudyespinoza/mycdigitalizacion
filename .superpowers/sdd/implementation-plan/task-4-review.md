# Task 4 independent review

## Verdict

- **SPEC COMPLIANCE: FAIL.** The storefront compiles and the mocked happy path runs, but a newly registered customer cannot complete checkout against the real backend. Four release blockers remain: post-login CSRF writes fail, customers cannot supply the DNI required by checkout, shipping addresses cannot reach a confirmed state, and uploaded CMS/catalog media is not deliverable in production.
- **CODE QUALITY: FAIL.** The type/lint/build baseline is clean and several trust boundaries are handled correctly, but the test suite replaces the critical backend semantics with permissive mocks and therefore reports green while the real end-to-end flow is broken.
- **Finding count:** 13 REQUIRED, 4 OPTIONAL.
- **Severity:** 4 P0, 9 P1, 3 P2, 1 P3.

## Scope and evidence

Reviewed `e1e95cd..068309a7f36008eba70afbfd63f2bd65bc17283d` against:

- `.superpowers/sdd/implementation-plan/task-4-brief.md`
- `PRODUCT.md`
- `docs/visual-direction.md`
- `.impeccable/mocks/decision/pulso-comercial-approved.png`
- `.impeccable/review/desktop.png`, `.impeccable/review/mobile.png`, and `.impeccable/review/hero-repro.png`
- the Django URL configuration, DRF serializers/views, checkout/address services, production Compose/Caddy routing, and OpenAPI contract tests
- the complete `design-taste-frontend`, `ui-ux-pro-max`, `emil-design-eng`, and `impeccable` skill instructions

Per the task constraint, the Impeccable detector was **not** run and `DESIGN.md` was **not** created.

## Audit health score

| Dimension | Score | Key finding |
| --- | ---: | --- |
| Accessibility | 1/4 | Primary/focus colors fail contrast; drawers/sheets and the map alternative are not keyboard complete. |
| Performance | 2/4 | Local hero is optimized, but real product/promo media is unoptimized and currently undeliverable. |
| Responsive design | 2/4 | Layout collapses exist, but the approved hierarchy regresses and 360/768/1024 are not exercised. |
| Theming | 4/4 | The approved token palette, radii, and tinted shadows are centralized and consistent. |
| Implementation integrity | 1/4 | Critical mocks diverge from CSRF, identity, media, address, and checkout behavior. |
| **Total** | **10/20** | **Acceptable only as an incomplete prototype; not releasable.** |

## REQUIRED findings

| # | Severity | Before | After | Why / evidence / reproduction |
| ---: | --- | --- | --- | --- |
| 1 | **P0** | `frontend/lib/api.ts:43-64` caches one CSRF token for the lifetime of the client module. `backend/api_views.py:322-348` calls Django `login()`, which rotates the CSRF token. | Clear/refetch CSRF after login/logout and retry one CSRF failure with a newly fetched token; add a real cookie-aware integration test. | **Repro:** register/verify/login without a hard reload, navigate client-side to fiscal data or addresses, then submit a POST. The header still sends the pre-login token while the cookie contains the rotated token, so Django returns 403. The mock API never validates cookies or `X-CSRFToken`, hiding the defect. |
| 2 | **P0** | Registration only accepts email/password/consent (`frontend/components/account/auth-forms.tsx:15-18`), the account explicitly says profile editing is unavailable (`frontend/components/account/account-dashboard.tsx:55-72`), and `/customers/me/` is GET-only (`backend/api_views.py:361-367`). Checkout rejects a customer with no DNI at `backend/commerce/checkout.py:163-170`. | Publish a protected profile/identity write contract and UI for the required customer fields, including DNI, then verify the persisted masked response before checkout. | **Repro:** register, verify email, log in, create billing/address data, and confirm checkout. A normal customer has no route that calls `CustomerProfile.set_dni`, so `/checkout/` returns `identity_missing`. Only staff admin can set DNI today. This breaks the product's core end-to-end purpose. |
| 3 | **P0** | Geocoding always sets `needs_review=True` (`backend/locations/services.py:64-92`). The UI only calls reverse geocoding after a move over 150 m and otherwise renders non-interactive text (`frontend/components/account/address-manager.tsx:17-20`). A far reverse lookup also keeps `needs_review=True` (`backend/locations/services.py:96-119`). Checkout rejects it at `backend/commerce/checkout.py:104-113`. | Add an explicit confirmation transition for both unchanged/near pins and the second confirmation after a far reverse lookup; expose an operable text/coordinate confirmation path and persist `reviewed_at`. | **Repro:** save and geocode an address, leave the suggested pin unchanged, and continue. There is no confirmation button, so the address remains blocked. Move it >150 m and press “Confirmar nuevo punto”; the returned address still requires review, but the UI now removes the button. Shipping checkout can never accept either path. |
| 4 | **P0** | Server reads use `http://backend:8000/api/v1` (`frontend/lib/api.ts:3-40`); CMS serializers turn media into absolute request-host URLs (`backend/landing/serializers.py:18-32`), product media also emits image URLs (`backend/catalog/serializers.py:13-16`), and production Caddy proxies `/api`, `/healthz`, and `/static` but not `/media` (`infra/caddy/Caddyfile:4-20`). `next.config.ts:3-10` has no remote image policy. | Serve `/media/*` through the public reverse proxy and make API image URLs public/same-origin, or normalize them in the frontend; configure Next image optimization for the final host. | **Repro:** run the production topology with an uploaded hero/product image. Server-rendered CMS URLs resolve to `backend:8000`, which a browser cannot resolve and Next Image does not allow; a public `/media/...` request is routed to the frontend and 404s. The Playwright mock uses relative `/campaigns/...` assets, so all four E2E tests pass incorrectly. |
| 5 | **P1** | The “Cuenta e identidad” step only GETs addresses and billing profiles (`frontend/components/checkout/checkout-flow.tsx:39-44`), never `/customers/me/`, `/identity/status/`, or `/identity/validate/`. The review step contains no cart items/totals/address summary or back controls, and every quote/checkout exception is rendered as `provider_down` (`:45-61`). | Implement the required sequence and recovery states using API error codes: account/profile/email, identity status/consent, address or pickup, shipping, full authoritative review, confirmation, and redirect. Preserve back navigation and entered state. | **Repro:** open checkout with an empty cart, missing DNI, invalid billing profile, unconfirmed address, or expired quote. All are local/domain problems, but the UI claims “El proveedor no respondió.” Users cannot correct the actual cause in place. |
| 6 | **P1** | Catalog UI exposes category, client-side name/first-variant-price sorting, and client slicing only (`frontend/components/catalog/catalog-browser.tsx:10-24`). It prints a note instead of price, availability, offer, brand, attribute facets, removable chips, category tree, or server pagination. The backend product contract contains none of those fields (`backend/catalog/serializers.py:19-48`) and the views only support category/search (`backend/api_views.py:107-146`). | Complete the versioned catalog contract and drive all required URL filters/facets/pagination from it; do not substitute explanatory copy for specified functionality. | **Repro:** visit `/catalogo` and try to filter by price, availability, offer, brand, or variant attribute. No control or shareable URL state exists. A five-level category tree is flattened into one select. This is a direct Task 4 completeness failure even though the UI is honest about the missing API. |
| 7 | **P1** | `frontend/app/page.tsx:11-25` catches any CMS/category/product failure and replaces it with empty arrays, so an outage is shown as “El catálogo se está preparando.” `home.collections` is never rendered; a hard-coded collection is rendered instead. `frontend/components/home/hero.tsx:28-37` ignores `mobile_image_url` and all safe-height fields, and the promo carousel ignores its mobile image/focal/safe-height contract. | Keep CMS empty, loading, and error states distinct; render scheduled collections/product IDs; honor authored mobile images, focal points, and safe heights with responsive `<picture>`/Image behavior. | **Repro:** stop the API and load `/`: no error or retry appears. Publish a landing collection or mobile-specific hero in admin: the storefront ignores it. A failure in categories also discards an otherwise valid CMS hero because all reads share one `Promise.all`. |
| 8 | **P1** | Cart line totals are recalculated in the browser (`frontend/components/cart/cart-page.tsx:13`) despite the “no business-total calculation” rule. Quantity changes fire on every input event and `CartProvider.perform` has no sequencing/cancellation (`frontend/components/cart/cart-provider.tsx:27-46`), so older responses can overwrite newer ones. PDP add failures are thrown from a `void` handler with no local error state (`frontend/components/product/product-purchase.tsx:11-21`). | Render only authoritative line/totals fields, serialize or cancel mutations, disable relevant controls while pending, and surface price/stock/change errors with retry/recovery. Extend the cart API if a line total/change notice is required. | **Repro:** rapidly change a quantity 1→2→3 under network throttling; responses may settle out of order and leave the cart at an older quantity. Reject an add-to-cart request; the PDP gives no error message. No stock/price-change notices exist because neither API nor UI publishes them. |
| 9 | **P1** | Pending payment maps to a generic `checking` panel but is fetched only once (`frontend/components/orders/order-result.tsx:8-11` and `checkout-flow.tsx:9-13`). Order detail has no fulfillment timeline/tracking events and pickup copy is a placeholder (`frontend/components/orders/order-detail.tsx:6-19`); the order serializer exposes no timeline/tracking data (`backend/commerce/serializers.py:70-105`). | Add bounded polling/manual retry for pending results, an order-specific recovery link, and an authoritative fulfillment/pickup/shipping timeline contract with only API-permitted resume/retry actions. | **Repro:** return from Mercado Pago while payment is pending: the page stays “consultando” forever unless reloaded. Open a shipped/pickup order: no carrier timeline, tracking, or configured pickup information is available. Redirect query distrust itself is correct. |
| 10 | **P1** | White text on `--magenta #F34887` is only **3.45:1**, and cyan text/focus on white is **2.64:1** (`frontend/app/styles.css:4-19,39,44-49,107,178`). | Use approved darker interaction/text tokens or ink text while preserving the Pulso palette; ensure primary labels reach 4.5:1 and focus/UI boundaries reach 3:1. | **Repro:** compute WCAG relative luminance for `#fff/#F34887` and `#08AECD/#fff`. Primary CTAs are normal-size text and fail WCAG 2.2 AA; the global cyan focus ring also misses non-text contrast. |
| 11 | **P1** | Cart drawer and mobile filters visually behave as modal surfaces but have no initial focus, Escape handling, focus containment, inert background, or focus return (`frontend/components/cart/cart-drawer.tsx:8-44`, `frontend/components/catalog/catalog-browser.tsx:24`, `frontend/app/styles.css:189-191,342-344`). The Leaflet marker is drag-only and displayed coordinates are not an operable alternative (`address-map-inner.tsx:7-10`, `address-manager.tsx:20`). | Implement complete dialog/sheet focus behavior and a keyboard/text coordinate/address confirmation control; associate form errors with fields and focus the first invalid field. | **Repro:** open cart or filters with keyboard, press Tab repeatedly, then Escape. Focus can move behind the surface and Escape does nothing. A keyboard-only user cannot adjust/confirm the map point. This violates the explicit keyboard-first and non-map-path requirements. |
| 12 | **P1** | The captured implementation materially misses the binding approved comp: the 720×617 stacked logo is forced into a 250×76/180×64 box and becomes a tiny wordmark (`site-header.tsx:18-20`, `styles.css:57-60,299-301`); the desktop hero wraps to three lines and mobile to four oversized lines (`styles.css:75-85,308-317`); a one-product payload leaves an unfinished four-column merchandising field (`styles.css:95-110`). | Recompose the header around the supplied asset (or use an approved horizontal treatment), restore the comp's two-line desktop hierarchy and calmer mobile scale, and adapt the featured layout for 1-3 products without stretching or empty-card-wall whitespace. | **Repro:** compare `.impeccable/review/hero-repro.png` and `desktop.png` to `pulso-comercial-approved.png`, then inspect `mobile.png`. These are not subjective micro-polish issues: brand recognition, first-viewport hierarchy, and merchandising density all visibly regress. The huge mobile collection headline reinforces the scale problem at `styles.css:331-333`. |
| 13 | **P1** | Vitest mostly tests pure helpers/presence and Playwright runs only 1440 plus Pixel 7 (`frontend/playwright.config.ts:19-22`). The mock ignores CSRF/cookies/login rotation, DNI/identity, address confirmation, real media URLs, stock changes, CMS failures, facets, result polling, and fulfillment timeline (`frontend/tests/mock-api.mjs:1-35`). | Add contract-faithful red/green tests for every Task 4 boundary and explicit 360/768/1024/1440 projects. Assert request method/path/body/CSRF/cookies, post-login writes, real media URL behavior, full checkout state order, keyboard focus, and error recovery. | **Repro:** current lint/type/Vitest/build/Playwright all pass while REQUIRED 1-4 make the real flow unusable. The “mocked checkout” skips login, identity APIs, address confirmation, and cart contents, returning `pending_review` directly from a permissive mock. |

## OPTIONAL findings

| # | Severity | Before | After | Why / evidence |
| ---: | --- | --- | --- | --- |
| 14 | **P2** | Product/PDP/promo API images use `unoptimized` (`product-card.tsx:9`, `app/producto/[slug]/page.tsx:34-44`, `promotion-carousel.tsx:12`), bypassing responsive encoding after media delivery is repaired. | Configure allowed public media origins or a same-origin loader and let Next emit sized AVIF/WebP variants. | Real catalogs can upload large originals; sending them unchanged harms LCP/data usage. The authored PNGs do contain embedded Impeccable prompt provenance, which is a positive finding. |
| 15 | **P2** | Reduced motion globally forces every animation/transition to 1 ms (`frontend/app/styles.css:385-387`). | Remove spatial/decorative motion while retaining short opacity/color/state feedback intentionally per component. | The current kill switch meets the basic “less motion” intent but removes useful state-change feedback rather than designing a reduced-motion alternative. |
| 16 | **P2** | Popup dismissal is stored only in `sessionStorage` for one tab (`frontend/components/home/promotion-popup.tsx:13-17`), and the test checks only a callback (`storefront-ux.test.tsx:84-99`). | Define a documented campaign frequency policy (session/day/until campaign changes), persist it accordingly, and test remount/new-tab/time behavior. | The current behavior is defensible as “once per tab session,” but it is not a configurable frequency system and is not actually covered end to end. |
| 17 | **P3** | The entire header is a client component (`frontend/components/layout/site-header.tsx:1-49`) even though logo/search/category navigation are static. | Keep the server-rendered shell and isolate menu/cart count/drawer into small client leaves if bundle profiling shows value. | This is an architecture/payload refinement, not a correctness blocker; the current Server/Client boundary is valid React. |

## Positive findings

- The root layout preserves the exact direction contract and seed `db399cd4` in production-surviving markup.
- The two authored campaign PNGs carry embedded `impeccable:prompt` provenance and have useful, non-invented alt text.
- Rubik/Nunito Sans, Phosphor, the approved color world, pill/card/input radius rules, tinted shadows, 44 px base controls, and explicit mobile collapses are implemented consistently.
- Public data reads are Server Components and interactive commerce/map/form behavior is isolated in client components; no unsupported reviews, stars, wishlists, WhatsApp, fake urgency, or payment approval from redirect query parameters was found.
- API calls use same-origin `/api/v1`, `credentials: include`, stable error normalization, and server-authoritative cart/order totals at the summary boundary.
- Checkout correctly treats a 202/no-checkout-URL response as pending identity review and does not reserve/payment-approve in the UI.
- No blanket `transition: all`, scroll listener, gradient blob, glass panel, or arbitrary motion dependency use was found.

## Verification performed

| Command | Result |
| --- | --- |
| `pnpm --dir frontend lint` | PASS |
| `pnpm --dir frontend typecheck` | PASS |
| `pnpm --dir frontend test:ci` | PASS, 2 files / 10 tests |
| `pnpm --dir frontend build` | PASS, 15 application routes reported |
| `pnpm --dir frontend test:e2e` | PASS, 4 tests (desktop/mobile) |
| `APP_ENV=test python -m pytest tests/test_openapi_semantics.py tests/test_api_contracts.py tests/test_checkout_api.py -q` from `backend/` | PASS, 12 tests |

The green command results are real, but they do not override the verified contract mismatches above.

## Recommended repair order

1. Fix REQUIRED 1-4 and add failing integration tests before changing presentation.
2. Complete the backend/frontend identity, address confirmation, catalog, cart-notice, media, and order timeline contracts.
3. Rebuild checkout as an ordered, recoverable flow with domain-specific errors and an authoritative review.
4. Repair WCAG contrast and modal/map keyboard behavior.
5. Recompose the header/hero/single-product merchandising against the approved comp at 360/768/1024/1440.
6. Re-run all verification plus one bounded desktop/mobile visual pass. Do not use the Impeccable detector until the task that explicitly authorizes it.
