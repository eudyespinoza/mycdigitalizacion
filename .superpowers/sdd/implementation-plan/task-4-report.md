# Task 4 implementation report: storefront and checkout experience

## Outcome

Implemented the Next.js 16 storefront against the existing versioned API without changing backend
or infrastructure. The result covers the public landing, catalog/search, product detail, cart drawer
and page, account/authentication, email verification, fiscal profiles, address/geocode/map workflow,
multistep checkout, Mercado Pago handoff states, and authoritative order result/detail routes.

The frontend now includes:

- A typed same-origin `/api/v1` client with cookies, CSRF, anonymous cart-token headers and stable
  error normalization. Authentication tokens are never placed in web storage; the anonymous cart
  token uses `sessionStorage` only.
- Server Component reads for CMS, categories, catalog, product and public order data, with client
  leaves limited to cart, catalog filters, forms, checkout, carousel/popup and Leaflet interaction.
- Shareable URL catalog search/category/sort/page state, responsive category/filter controls,
  skeleton/no-results handling and an honest notice for facets the current API does not expose.
- Variant/quantity cart writes, authoritative cart refresh, coupon/quantity/removal controls, drawer
  feedback and full-cart checkout actions.
- Cookie-session register, six-digit verification, login and logout flows; customer profile and
  fiscal/address/order account views; profile editing is not claimed because the current customer
  endpoint is read-only.
- CP/CPA locality lookup, address candidates, Leaflet/OpenStreetMap pin confirmation, accessible
  text/coordinate confirmation and the required greater-than-150-metre reverse-lookup boundary.
- Account/identity, address or pickup, shipping quote, review and checkout confirmation steps.
  Identity review/provider-down states stop safely; no provider success is fabricated and redirect
  query parameters never establish payment state.
- Pulso Comercial visual implementation using the supplied logo and authored campaign rasters,
  Rubik/Nunito Sans, approved palette, asymmetric search-led composition, focus-visible behavior,
  44px targets, reduced motion and responsive layouts. The exact direction contract and seed
  `db399cd4` survive in optimized server output.

The design-taste, UI/UX Pro Max, Emil design-engineering and Impeccable craft guidance directly
shaped the asymmetric hierarchy, restrained motion, token system, accessible controls and bounded
desktop/mobile screenshot correction pass. Per the task boundary, the Impeccable detector was not
run and `DESIGN.md` was not created; those remain Task 6 work.

## TDD evidence

- RED: the first Task 4 Vitest run failed while the checkout state component did not exist. Tests
  already specified accessible navigation, CMS hero content, URL filter state, variant/quantity
  cart payload, six-digit verification, provider-outage recovery, campaign dismissal, map distance
  and redirect-state distrust.
- GREEN: after the smallest implementation slices, Vitest reached `2 passed` files and `10 passed`
  tests (`9` storefront behaviors plus the existing health test).
- Regression RED: the final all-tests invocation demonstrated that Vitest's default `*.spec.ts`
  discovery incorrectly collected the Playwright suite. Component assertions were `10 passed`, but
  the run exited red with one runner-boundary suite error.
- Regression GREEN: `vitest.config.ts` now includes only `tests/**/*.test.{ts,tsx}`; the repeat run
  completed with `2 passed` files and `10 passed` tests.
- Browser RED/GREEN: desktop/mobile mocked flows were written for landing → catalog → product →
  cart and checkout. Early runs exposed the absent Chromium binary, dev-origin/mock URL mismatches
  and an ambiguous cart assertion; after correcting those boundaries, all four flows passed. The
  checkout test explicitly proves identity review without a payment-approved claim.

## Final verification evidence

Commands were rerun after the final source changes:

- `pnpm --dir frontend lint` → exit `0`.
- `pnpm --dir frontend typecheck` → exit `0`.
- `pnpm --dir frontend test:ci` → `2 passed` files, `10 passed` tests.
- `pnpm --dir frontend build` → exit `0`; optimized Next build compiled, typechecked and generated
  all 15 reported application routes.
- `pnpm --dir frontend test:e2e` → `4 passed` Playwright tests: both flows at desktop and mobile.
- Source audit found no blanket `transition: all`, unsupported rating/urgency/WhatsApp content or
  production authorization based on redirect query parameters.
- Optimized-output audit found the full Pulso direction contract and `db399cd4` in `.next/server`.

Visual checkpoints were captured at:

- `.impeccable/review/hero-repro.png` (1536 × 1024 approved-comp checkpoint)
- `.impeccable/review/desktop.png` (desktop full page)
- `.impeccable/review/mobile.png` (mobile full page)

These review artifacts remain gitignored and are not shipping assets.

## Contract limits and operational concerns

- The current public product contract has no brand, availability, offer, arbitrary-attribute or
  stock fields and no pagination envelope. The UI supports the actual category/search/sort/page
  contract and does not invent those missing facets, discounts or stock claims.
- The current customer profile endpoint is GET-only, so profile display is read-only. Fiscal
  profiles and addresses use their published write endpoints.
- No SID, carrier or Mercado Pago credentials were used. Playwright intercepts the API and stops at
  identity review; a real provider success was neither attempted nor claimed.
- The supplied stacked logo naturally occupies less horizontal header area than the horizontal
  treatment in the approved comp. It was kept intact as required rather than cropped or replaced.
- Next development mode emits a non-failing LCP hint for the authored collection raster during the
  mocked catalog/product journey, plus environment-only `FORCE_COLOR` and slow-filesystem notices.
  The optimized production build is clean and successful.

## Fix Round 1 (2026-08-20)

This section supersedes the original contract-limit notes above. The frontend was repaired against
the finalized Task 4 backend/infra contract in commit `c0f858fb231372523dbae410edb2794fbe91859a`.
No backend or infrastructure file was changed as part of the frontend repair.

### REQUIRED finding closure

| Finding | Frontend closure |
| --- | --- |
| F1 | Authentication success clears the module CSRF cache; the next unsafe write fetches the rotated cookie-bound token. A named CSRF 403 retries exactly once after refetch. Unrelated 403s and provider operations are never retried arbitrarily. Regression tests assert `csrf-1` on login and `csrf-2` on the following profile PATCH. |
| F2 | Storefront registration requires first name, last name, phone, email, password and consent. Account profile editing PATCHes `/customers/me/` with first/last/phone/DNI and displays only the persisted `••••5678` response before checkout. |
| F3 | Address UI now covers CP/CPA lookup, save/geocode, unchanged or near written-address confirmation, greater-than-150-metre reverse lookup, explicit written/reverse choice, keyboard-editable text coordinates and persisted reviewed state. Confirmation bodies use decimal-7 strings and the exact `address_choice`. |
| F4 | CMS, product and promotion media normalize to same-origin `/media/...`; arbitrary remote origins are rejected. Next image optimization remains enabled with no invented remote hosts, and development `/media` proxying mirrors the public topology. |
| F5 | Checkout is ordered and recoverable: authoritative customer/email/profile, identity status/consent/validation, confirmed address or pickup, quote, full cart/address/fiscal/shipping review, edit/back controls, and confirmation/MP handoff. Stable domain codes return users to the correct correction step; a 202 without checkout URL remains pending review. |
| F6 | Catalog controls are server and URL driven for category hierarchy, brands, min/max price, availability, offer, dynamic attributes, ordering, removable chips and server pagination. Error, empty and retry states are distinct; no client slicing or business sorting remains. |
| F7 | CMS/category/catalog reads settle independently. CMS error differs from published-empty content; scheduled collections and `product_ids`, mobile images, focal positions and safe heights render from the backend rather than a hard-coded replacement. |
| F8 | Cart renders authoritative `line_subtotal`, `line_discount`, `line_total`, availability, stock and notices. Mutations are serialized, relevant controls disable while pending, quantity commits are bounded to blur/Enter, and PDP/cart failures remain visible and recoverable. |
| F9 | Payment result polling is bounded to six attempts with a manual retry. Order detail renders server timeline, carrier/tracking and configured pickup information; only server-permitted pending/rejected payment resume is exposed. |
| F10 | Interaction tokens use accessible darker approved-family colors: `#bd1d59` primary and `#007f96` focus/wayfinding. Browser-computed checks require primary text contrast at least 4.5:1 and focus contrast at least 3:1. |
| F11 | Cart drawer and mobile filter sheet implement dialog semantics, initial focus, Escape, focus containment, inert background and deferred focus return. Form errors are associated and first-invalid focus follows DOM order. Map coordinates have a stable keyboard/text alternative. |
| F12 | The same supplied stacked raster is recomposed with pixel-faithful CSS crops into a legible mark/word lockup. The desktop hero returns to two lines, mobile is calmer, collections are scaled down, and 1–3 product grids adapt without fake inventory. The asymmetric search-led Pulso composition remains intact. |
| F13 | The mock now enforces cookie/CSRF rotation and exact request shapes for profile, address, catalog, media, cart, checkout, payment and order data. Playwright explicitly runs 360/768/1024/1440 and covers registration/profile/DNI, address choices, optimized media, CMS failure, filters/chips, bounded polling, focus restoration, contrast and domain recovery. |

### Fix Round 1 TDD and verification

- Regression RED: the new component suite began with eight failing contract assertions covering
  CSRF rotation/retry, profile/DNI, media, catalog query state, serialized cart mutation, checkout
  recovery and bounded payment polling. The address decimal-7/choice assertion was also observed red
  before implementation.
- Component GREEN: `pnpm test -- --run` completed with `3 passed` files and `19 passed` tests.
- Browser RED: the first expanded Playwright run reported `8 failed`, `4 passed`, `24 skipped` and
  caught invalid-field focus ordering, unstable number-coordinate editing and premature cart focus
  restoration, plus four overly broad assertions. The production accessibility defects were fixed;
  assertions were narrowed to the authoritative element/state.
- Browser GREEN: `pnpm exec playwright test` completed with `12 passed`, `24` intentionally
  project-gated skips and `0 failed` across explicit 360, 768, 1024 and 1440 projects.
- `pnpm lint` → PASS.
- `pnpm typecheck` → PASS.
- `pnpm build` → PASS; the optimized Next 16 build compiled, typechecked and generated all routes.
- Final source and visual checks found no fabricated payment/provider success, redirect-query
  authority, localStorage auth token, unsupported ratings/urgency/WhatsApp, arbitrary remote image
  origin or hard-coded replacement CMS collection.

Refreshed visual checkpoints are `.impeccable/review/360.png`, `768.png`, `1024.png`, `1440.png`
and `hero-repro.png`. The bounded comparison against the Pulso Comercial comp confirmed the
two-line desktop hierarchy, calmer mobile hierarchy, supplied-logo legibility, asymmetric search-led
composition and adaptive product merchandising. These screenshots remain review artifacts rather
than shipping assets.

Per the explicit Task 4 boundary, the Impeccable detector was not run and `DESIGN.md` was not
created. The only remaining non-failing frontend advisory is Next development mode classifying the
mocked CMS collection image as LCP on the one-product long-page fixture; the production build is
clean, and the media is served through the optimized same-origin Image path.
