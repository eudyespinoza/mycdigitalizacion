# Task 6B frontend verification report

Date: 2026-08-20

Branch: `feat/ecommerce-foundation`

Visual authority: Pulso Comercial approved comp, seed `db399cd4`

## Outcome

The storefront frontend completed its final functional, accessibility, production-media,
performance and responsive visual verification. The deterministic browser harness covers the
complete shipping and pickup paths without claiming a provider payment success. A separate fresh
Compose project supplied real PostgreSQL, Redis, Django and Caddy data for the final production
standalone captures.

The task-specific instruction deferred the Impeccable mechanical detector and `DESIGN.md`; neither
was run or created in Task 6B. The four required design skills were applied to the audit and visual
comparison. No shipping raster was regenerated or replaced.

## TDD and defects closed

| Boundary | RED evidence | GREEN result |
| --- | --- | --- |
| Automated accessibility | The first real axe scan reported one serious `aria-command-name` violation on Leaflet's draggable marker. | The marker exposes the authored label `Mover punto de entrega`; repeated axe scans report zero serious or critical findings. |
| Production harness fidelity | The initial performance test could not decode the logo because the standalone harness omitted Docker's `public` and `.next/static` runtime copies. | `tests/prepare-standalone.mjs` now mirrors both Docker copies before starting the real `.next/standalone/frontend/server.js`. |
| Hero loading | The component regression received `loading="lazy"` for the above-fold prioritized campaign image. | The single responsive/picture resource uses eager loading only when prioritized, while retaining one image, one mobile source, authored focal position, alt and sizes. |
| Full commerce journey | Early browser runs exposed hydration-sensitive catalog filtering, mobile sheet obstruction and premature login/profile continuation. | Explicit state synchronization now carries desktop and phone through persisted registration, email verification, checkout, mocked Mercado Pago redirect, server-polled paid result and order tracking. |

## Fresh gates

| Gate | Command | Result |
| --- | --- | --- |
| Frozen dependency graph | `pnpm install --lockfile-only`; `pnpm install --frozen-lockfile` | PASS; lockfile matches the pinned frontend manifest. |
| Lint | `pnpm lint` | PASS. |
| TypeScript | `pnpm typecheck` | PASS. |
| Components | `pnpm test:ci` | PASS: 5 files, 25 tests. |
| Production build/media/performance | `pnpm test:e2e:production` | PASS: 3/3 using the actual standalone artifact. Includes a 200 response for optimized relative `/media`, cache headers, one responsive priority hero, zero duplicate hero preloads and local Web Vitals budgets. |
| Browser matrix | `pnpm test:e2e` | PASS: 50 passed, 10 deliberately viewport-gated, 0 failed in 4.6 minutes at 360/768/1024/1440. |

The final production rerun first encountered `EBUSY` because the already-verified capture server
still held the standalone directory. After stopping that bounded process, the unchanged suite
passed 3/3. No test or application change was used to bypass the failure.

### Playwright skip disposition

The ten skips are cross-viewport reductions, not disabled requirements:

- Address map/far reverse confirmation skips 768 and 1440; it runs at 360 and 1024 to cover phone
  and full desktop interaction.
- Mobile/tablet filter sheet skips 1024 and 1440; it runs at 360 and 768, while URL filters/chips
  remain covered elsewhere on desktop.
- Bounded payment polling skips 360 and 768; it runs at 1024 and 1440 because polling semantics are
  viewport independent.
- The complete persisted shipping journey skips 768 and 1024; it runs end to end at 360 and 1440.
- The configured pickup journey skips 768 and 1024; it runs end to end at 360 and 1440.

All three accessibility scenarios run in every project. Core registration, CSRF/profile,
CMS recovery, checkout recovery, pickup gating and contrast scenarios also retain relevant
cross-viewport coverage.

## Accessibility and interaction

`@axe-core/playwright` 4.13.0 scans the landing page, catalog, product detail, registration, cart
dialog, checkout and textual address path with WCAG 2.0/2.1/2.2 A/AA tags. The serious/critical
result is **0** across all four projects.

Browser checks additionally verify:

- initial dialog focus, Shift+Tab focus trapping, Escape and focus return;
- mobile catalog sheet focus return;
- reduced-motion media emulation and one-millisecond transitions/animations;
- the non-map address path and associated checkout content;
- first-invalid profile focus;
- primary, focus-indicator and cart-badge contrast thresholds.

## Deterministic commerce evidence

The mock records exact methods and request bodies while keeping payment authority on the server.
The 360 and 1440 journeys perform landing search, brand filtering, PDP variant selection, cart,
registration/profile, email verification, checkout address, shipping quote, complete review,
mock Mercado Pago handoff, bounded payment polling and persisted order timeline/tracking. The mock
page explicitly says it does not represent an approved payment. A second journey proves configured
pickup reaches review without requesting a shipping quote. Existing scenarios retain pending
identity/review and code-specific recovery coverage.

For real-stack evidence, a new Compose project (`mycd-task6`) created isolated PostgreSQL, Redis and
media volumes, applied all migrations, ran `seed_synthetic_data`, and exposed Django through Caddy
on local port 8090. The database contained exactly one explicitly labeled synthetic hero and one
synthetic product. The production standalone was rebuilt against that API for the final captures.
The temporary standalone, Caddy, frontend and isolated Compose containers were stopped afterward.
The pre-existing shared backend/PostgreSQL/Redis/worker services remained running; no existing
volume or development data was deleted.

Real SID, Mercado Pago and Correo Argentino smoke tests remain credential-gated. No secrets were
invented and no live provider success is claimed; provider/security verification belongs to Task 6A
commit `7671022`.

## Performance and production media

Lighthouse is not installed in the frozen workspace, so no transient dependency was added. A real
Chromium run against the seeded production standalone recorded the required lab proxies:

| Metric | Result |
| --- | ---: |
| LCP proxy | 648 ms |
| CLS | 0.0000 |
| Interaction to next animation frame (INP lab proxy) | 2 ms |
| TTFB | 395.3 ms |
| DOMContentLoaded | 446.6 ms |
| Load | 722.5 ms |

The authored hero's optimized 1200px response was 257,243 bytes with
`Cache-Control: public, max-age=14400, must-revalidate`; the warm local request completed in 5.6 ms.
The production test independently proves backend-relative `/media/cms/hero.png` optimization returns
HTTP 200. The built static chunk inventory is 23 files / 974,422 bytes total, with a 228,838-byte
largest chunk.

The development-only warning that labels a below-fold collection image as LCP occurs after the
full-page screenshot scrolls the intentionally sparse fixture. The initial production viewport uses
the single eager/high-priority hero, and production HTML contains no duplicate hero preload/srcset.

## Visual evidence and provenance

The final files were captured from document top after fonts, images and reduced motion settled:

- `.impeccable/review/desktop.png` — 1440 × 1959, 581,822 bytes.
- `.impeccable/review/mobile.png` — 375 × 2939, 221,665 bytes.
- `.impeccable/review/hero-repro.png` — 1536 × 1024, 509,003 bytes, matching the approved comp dimensions.

One batched visual inspection compared all three with
`.impeccable/mocks/decision/pulso-comercial-approved.png`. The captures are loaded, legible and retain
the search-led hierarchy, stacked supplied logo, asymmetric hero, focal crop, editorial one-product
layout, responsive 375px reading order and accessible navy/cyan/magenta system. The content is
visibly labeled synthetic development data. No material defect justified a visual change, so the
single permitted correction/recapture round was not consumed.

A binary provenance scan found C2PA `trainedAlgorithmicMedia` assertions plus embedded
`impeccable:prompt` metadata in both shipping campaign rasters:

- `frontend/public/campaigns/pulso-comercial-hero.png`
- `frontend/public/campaigns/pulso-libreria-collection.png`

## Remaining boundaries

- The Impeccable detector and generated `DESIGN.md` are intentionally deferred by the Task 6B
  instruction; this report does not present a detector or finish-reviewer verdict.
- Live provider and real transactional-payment smoke tests require authorized credentials and safe
  provider environments.
- Review screenshots remain ignored local review artifacts rather than production assets; their
  dimensions, byte sizes and inspected content are recorded above.
