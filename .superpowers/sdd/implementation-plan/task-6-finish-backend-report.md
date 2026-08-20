# Task 6 finish — backend CMS contract repair

Date: 2026-08-20
Review source: `task-6-finish-review.md` at reviewed target `f1c84ef5f514c9b27d6064eb24af8e82af057bfc`.

## Scope and outcome

This change closes the backend portion of REQUIRED R3 and supplies the versioned popup contract needed by R2. It does not edit frontend files, replace the accepted supplied logo, run the Impeccable detector, or create `DESIGN.md`.

- Singleton `SiteSettings` now accepts validated optional `logo` and `favicon` uploads. The logo has responsive derivatives; favicon retains its validated original. Replacements are transactional and delete superseded originals/derivatives only after publication succeeds.
- Django Admin exposes both upload controls plus safe previews. The Content role already includes non-delete SiteSettings permissions through the existing exact role synchronizer.
- Public settings add non-empty same-origin `logo_url`, `logo_responsive_sources`, and `favicon_url`. With no upload, both URLs deterministically preserve `/brand/mycdigitalizacion-logo.png`; uploaded files use `/media/branding/...` UUID paths derived from decoded MIME.
- `PromotionPopup.version` is an administrable positive integer, default 1, and is published for a stable `id + version` frequency-storage key.
- Existing Hero/Promotion/Popup API fields were audited and retained: schedule, order, interval, reduced-motion pause, frequency, delay, dismissibility, desktop/mobile URLs and responsive sources, alt text, focal coordinates and safe heights.
- Image validation now reads MIME from either the direct upload or the underlying file wrapped by a model `FieldFile`, closing a validation gap discovered by the new logo/favicon model tests.

## TDD evidence

- Initial focused RED: `3 failed`. PromotionPopup rejected `version`; SiteSettings/Admin had no logo/favicon fields; OpenAPI had no branding properties.
- Compatibility RED: the historical singleton-overwrite test showed PK uniqueness validation after adding `full_clean`; fixed by excluding the intentionally fixed singleton PK while retaining all field validation.
- Validation RED: model-wrapped spoofed MIME did not raise because the wrapper hid `content_type`; fixed at the shared validator boundary.
- Storage-isolation RED: the first full suite had one test-only failure because a test mixed Django's `override_settings` decorator with pytest's `settings` fixture, restoring the temporary static backend after decorator teardown. The test now uses one fixture-owned settings lifecycle; the exact sequence is `5 passed` and no product setting changed.
- Final focused CMS/media/storefront selection: `83 passed in 62.74s`.
- Exact new contract file plus historical singleton/media/OpenAPI checks: `9 passed in 15.81s`.

## Final verification

- Full SQLite-compatible backend suite: `226 passed, 18 skipped in 160.83s`.
- PostgreSQL selection covering migration application, CMS/admin contract, inventory/checkout locking and migration regressions: `18 passed in 90.14s`.
- Ruff: `All checks passed`.
- Django system check: `0 issues`.
- Migration drift: `No changes detected`; data-safe migration `landing.0007` adds blank branding fields, empty derivative manifest and popup version default 1.
- OpenAPI JSON generation and validation: exit 0. `SiteSettings` documents string logo/favicon URLs and typed responsive sources; `PromotionPopup.version` is integer with minimum 1.
- Isolated collectstatic: 166 files copied, 478 post-processed.
- Test media used an isolated temporary `MEDIA_ROOT`; no generated media/schema/static artifact is committed.

## Public contract additions

```text
settings.logo_url: string                         # never empty
settings.logo_responsive_sources: ResponsiveMediaSource[]
settings.favicon_url: string                      # never empty
promotion_popups[].version: integer               # >= 1, default 1
```

`ResponsiveMediaSource` remains `{width, fallback, webp?, avif?}`. All generated paths are same-origin relative `/media/...`; the supplied fallback remains same-origin `/brand/mycdigitalizacion-logo.png`. Absent campaign images continue to serialize as empty URL strings and empty source arrays; schedule bounds remain ISO datetime strings or null.
