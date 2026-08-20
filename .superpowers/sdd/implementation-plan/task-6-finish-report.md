# Task 6 finish fix report: CMS-authored storefront

Date: 2026-08-20

Branch: `feat/ecommerce-foundation`

Visual authority: Pulso Comercial approved comp, seed `db399cd4`

## Outcome

The three required CMS-to-storefront authoring gaps are closed without redesigning the accepted
Pulso composition. All scheduled hero and promotion rows now participate in accessible carousels;
popup delivery honors the authored policy; and every storefront header plus favicon metadata uses
the active singleton branding with the supplied raster as deterministic fallback. The two optional
mobile refinements are also complete.

The four required design skills were applied with the finish review as binding scope. The
Impeccable detector was not run and `DESIGN.md` was not created, as explicitly required.

## RED to GREEN

The first focused RED was `tests/cms-campaigns.test.tsx`: 1 file and all 8 tests failed against the
previous single-slide, session-only, hardcoded-brand implementation. The focused GREEN is 8/8 and
covers authored per-slide timing, manual state, hover/focus/visibility/reduced-motion pause,
promotion movement, popup delay and persistence windows, non-dismissible/image rendering, version
replacement, and CMS header branding. A subsequent responsive-logo-source assertion was captured
RED (1/1 failed) and GREEN (1/1 passed).

A browser regression exposed that popup imagery could cover the close control. The control now has
an explicit visual layer and the focused 360 px daily-policy flow passes. A separate existing login
test read the mock request log before the submitted profile PATCH completed; it now polls the real
request boundary instead of treating already-present masked-DNI copy as mutation completion.

## Review mapping

| Finding | Resolution |
| --- | --- |
| R1 | Hero and promotion use all ordered rows, each active row's `interval_ms`, `pause_on_reduced_motion`, visibility/focus/hover pauses, wraparound controls, and announced position. Reduced motion stops configured autoplay and changes promotion spatial movement from smooth to instant. |
| R2 | `PromotionPopupContent` preserves frequency, delay, dismissibility, version, schedules, responsive desktop/mobile media, alt and focal data. Keys include `id` and `version`; session/daily/weekly/always behavior uses injected time in unit tests. The popup is a nonmodal polite complementary region and never moves focus. |
| R3 | Root layout loads singleton branding with a safe supplied-asset fallback, provides it to every header, renders same-origin logo responsive AVIF/WebP sources when authored, retains the accessible public home name, and generates favicon metadata from `favicon_url`. Backend contract source is sibling commit `b1b5ad904270a6676a949d94d83c4488b91bcdb1`. |
| O1 | Below 420 px, the discovery heading owns the first row and the tertiary link moves to a 44 px second row. |
| O2 | Applied filter chips now have a 44 px minimum target. |

## Accessibility and visual result

The carousel has a named region, reachable previous/next controls and polite `X de N` state. It
pauses while a buyer hovers or works inside it and while the page is hidden. Motion preference is
observed without hiding content or preventing manual navigation. Popup delivery remains nonblocking
for keyboard and screen-reader users.

Refreshed 360 and 1440 full-page captures plus the 1536 hero reproduction were opened once. The
asymmetric search-led hero, supplied stacked logo, editorial one-product layout, focal crops and
navy/cyan/magenta hierarchy remain intact. The mobile discovery link now reads as a calm second row;
carousel controls remain legible and at least 44 px. No further visual correction was warranted.

## Verification

Final evidence is recorded after the last source change:

| Gate | Result |
| --- | --- |
| Frozen install | PASS: `pnpm install --frozen-lockfile`. |
| Lint | PASS: `pnpm lint`. |
| TypeScript | PASS: `pnpm typecheck`. |
| Vitest | PASS: 6 files / 38 tests after the final Round 2 popup change. |
| CMS browser matrix | PASS: 36/36 at 360/768/1024/1440 after Fix Round 2. |
| Full browser baseline | PASS: 62 passed / 10 deliberate viewport reductions / 0 failed at 360/768/1024/1440 before the narrow Round 2 repair; the affected CMS paths were then re-run 36/36. |
| Axe matrix after final logo positioning | PASS: 12/12; serious/critical 0 in every viewport. |
| Production standalone | PASS: 3/3; same-origin optimizer 200, one priority responsive hero/no duplicate preload, local performance budgets. |

The full Playwright suite retains ten deliberate cross-viewport reductions documented in the Task
6B report: map at 360/1024, mobile sheet at 360/768, polling at 1024/1440, and complete shipping and
pickup journeys at 360/1440. All new CMS scenarios, all three axe scenarios, registration,
CSRF/profile, CMS recovery, checkout recovery, pickup gating and contrast execute in every relevant
project.

The 62/10 full run surfaced a Next development warning after the responsive logo was wrapped in a
`picture`: the immediate `Image fill` parent had static positioning. A dedicated unit assertion was
captured RED, the picture received bounded absolute positioning, then the unit, 12 CMS browser
scenarios, 12 axe scenarios, lint/type/Vitest and the production standalone gates all passed with
the warning absent.

## Boundaries

- Live Mercado Pago, SID and shipping-provider success remains credential-gated; no provider
  authority or success was fabricated.
- The mechanical Impeccable detector and `DESIGN.md` remain intentionally outside this fix.
- Review screenshots are local evidence, not shipping application assets.

## Fix Round 2: independent re-review closure

The three partial REQUIRED findings from review commit `2523528` are now closed without changing
the backend contract or the accepted visual direction.

| Finding | Final repair |
| --- | --- |
| R1 | At 360 px the promotions heading and controls now form two bounded rows, so `documentElement.scrollWidth <= clientWidth` and both 44 px controls remain inside the viewport. The track listens for settled scroll/snap input, resolves the nearest authored slide, and updates the polite `Promoción X de N` state. Programmatic reduced-motion movement remains instant. |
| R2 | `once_session`, `daily`, and `weekly` record the impression in the effect that follows the visible render; dismissing is idempotent and records immediately as well. Non-dismissible campaigns therefore suppress remount/reload inside their window, while `always` writes no frequency key and recurs. The elapsed-window browser test now waits for a real hydrated client interaction before mutating its clock, avoiding the prior false pass on server HTML. |
| R3 | The header renders one complete CMS logo asset, not two private crops. A responsive `picture` retains authored AVIF/WebP/fallback sources; its single image uses intrinsic auto dimensions constrained by `max-width`/`max-height` and `object-fit: contain`, preserving square and horizontal proportions, clear space, the active URL, favicon and accessible public home name. |

### Round 2 RED to GREEN

- Unit RED: `tests/cms-campaigns.test.tsx` ran 13 tests, 8 passed and 5 failed exactly on touch
  state, three non-dismissible impression policies, and the duplicated logo. Final GREEN: 13/13.
- Browser RED at 360: 0/3; it measured `scrollWidth 387 > clientWidth 360`, no persisted
  non-dismissible impression, and two logo images. The adversarial GREEN is 6/6 at 360.
- Cross-viewport CMS GREEN: 36/36 across 360/768/1024/1440, including square/horizontal logos,
  each non-dismissible policy, `always`, legacy elapsed-window recovery and touch snap.
- Axe GREEN: 12/12, with zero serious or critical findings across the four viewports.
- Production standalone GREEN: 3/3; optimizer `/media` returned 200, hero HTML retained one
  responsive priority resource, and local performance proxies stayed within budget.
- Bounded visual capture GREEN: the responsive landing test passed 2/2 at 360 and 1440. Both
  refreshed captures were opened once; Pulso composition, search hierarchy, product editorial
  scale, contained logo, control bounds and mobile discovery hierarchy remained coherent. No
  second correction round was needed.

Final source gates after the last edit: lint PASS, TypeScript PASS, Vitest 38/38, production build
PASS, and CMS Playwright 36/36. One interrupted dev server had truncated ignored
`.next/dev/types`; removing only generated files restored a clean typecheck without touching
source. The detector remained unrun and `DESIGN.md` remained absent, as required.
