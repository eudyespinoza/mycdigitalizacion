# Task 8 report — support conversations

## Scope

- Added the theme-aware Support CSS section, mock API support contracts, public/management E2E coverage, accessibility coverage, and OpenAPI semantic coverage.
- Narrow scope extension authorized by the parent: `CaseCreateDialog` now focuses **Asunto** once when the async configuration finishes rendering the dialog form. The guard avoids stealing focus on subsequent renders within the same dialog opening.

## TDD

- **RED:** Added the focused `SupportHub` regression for a dialog that opens while configuration is loading, then resolves. It asserts that **Asunto** receives focus and that moving focus afterward is not overridden. The initial browser-level accessibility check failed for the same behavior: `expect(dialog.getByLabel("Asunto")).toBeFocused()` received an inactive element.
- **GREEN:** Added a subject-input ref plus a request-animation-frame focus effect gated by configuration readiness and a per-mount focus guard. The focused accessibility flow completed after the fix with no Playwright failure artifact.

## Responsive and accessibility coverage

- `support.spec.ts` covers the public list, on-demand creation/recovery UI, thread reply, problem-report form, management filter, management detail reply without document reload, and document-width checks at 360 and 1440 px.
- `accessibility.spec.ts` covers keyboard dialog entry/escape/focus return, the closed read-only thread, management inbox axe checks, and the asynchronous focus regression.
- Support CSS uses only theme roles after `/* Support conversations */`; it includes public and management layouts for 360/768/1024/1440, contained table scroll, wrapped attachments, dialog-safe sizing, token-based focus/disabled/error states, and the existing reduced-motion policy applies to the support interactions.

## Verification notes

- The normal Playwright server could not start on 3000 because the shared Docker frontend owns that port. Verification was rerun through a temporary, untracked configuration using mock port 4020 and Next port 3100; the temporary configuration was removed afterward.
- Actual RED E2E failures repaired in test code were strict locator ambiguity (`Mensaje` also named the messages list; `Categoría` matched the hidden category navigation) and the management-link timing on the slow filesystem. Selectors now target the textarea/field exactly and the detail route is loaded directly after the inbox assertion.
- Focused Vitest/TypeScript/backend suites exceed this harness's 30-second command-output window and do not return a final stream here. No failing assertion from those suites was captured. The focused Vitest command used `--pool=forks --maxWorkers=1 --no-file-parallelism` as requested.
- Full frontend test:ci, lint, typecheck, build, and Docker backend focused suite remain for parent-level verification.
