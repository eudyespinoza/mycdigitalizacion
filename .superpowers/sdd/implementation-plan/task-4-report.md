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
