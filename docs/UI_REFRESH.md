# Atlas UI refresh

> Publication note: raw run artifacts are private and excluded from Git. See the [evidence guide](evidence/README.md) for the reviewed public summaries and reproduction scope.

The interface now uses a dark, iOS-inspired glass design across sign-in, the workspace, chat, library, uploads, and source dialogs.

## Design decisions

- Charcoal and midnight surfaces, translucent layered panels, fine illuminated borders, restrained blue accents, and consistent rounded controls.
- A system sans-serif stack: SF on Apple platforms when available, Segoe UI on Windows, and Helvetica/Arial fallbacks. No font downloads, CDN scripts, or additional dependencies.
- Grouped suggestion rows, custom local SVG line icons, a glass composer, and a frosted source sheet.
- Short opacity/transform transitions. Blur is not continuously animated. Reduced-motion and reduced-transparency preferences have CSS fallbacks.
- Responsive navigation drawer with an overlay, Escape dismissal, keyboard focus containment, focus restoration, and an inert background.
- Existing APIs, model configuration, access controls, and persisted data are unchanged.

## Verification

- JavaScript syntax validation passed.
- HTML checks passed: 65 unique element IDs; all literal JavaScript element targets and SVG references resolve.
- Six targeted existing API regression tests passed: protected data routes, security headers/CSRF, Phase 1 action boundaries, ingestion with source quotes, duplicate/replacement behavior, and conversation ownership/replay. The existing test-client deprecation warning remains.
- Browser checks passed for sign-in/out, document library and upload controls, source-dialog opening/closing, and mobile navigation with keyboard focus containment and Escape restoration.
- The 390 x 844 phone layout was visually inspected. A decorative element's horizontal overflow was corrected. At 320 px and 390 px wide, the inspected chat layout has no horizontal overflow.
- Desktop layout was visually inspected in the local browser. Native iOS Safari and physical-device rendering have not been tested.
- A fresh question sent through a suggestion row completed using the real local Qwen model in 52.6 seconds, returning the expected 25-day leave allowance with the annual-leave source quote and paragraph citation. No browser console errors were observed.

This is an iOS-inspired responsive web interface, not a native iOS application.

## Phase 2 extension

The same system sans-serif typography and dark glass surfaces now include a Knowledge/Actions segmented control, action suggestions, Operations counts and category tabs, ticket lifecycle controls, independent approval forms, owner-private reports, and expandable workflow traces. Reports use formatted DOM headings, paragraphs, SQL tables, and source cards; generated HTML is never injected.

The live browser journey created a Qwen-planned ticket, changed its status, submitted a pending access request, approved it as a different account, and reopened the employee's saved conversation to verify the completed decision and audit trace. The report viewer and citation/source return path were inspected at a 390 × 844 viewport. Desktop page width matched viewport width; no console warnings/errors were captured. Details are in `artifacts/phase2-browser-checks.json` and the current engineering review. Eighteen synthetic DOM tests now cover session changes, stale responses, duplicate decisions, uncertain-request replay, unavailable-report navigation, and late source/report dialog responses. The additional review found and fixed pending source requests reopening a dialog after its parent report was closed, by either its close button or Escape.

## Phase 3 extension

Insights adds personal and admin aggregate monitoring, the local Quality lab, prompt inspection and a business-case calculator in the same dark glass interface. Answer feedback persists in the existing conversation cards. Forms and evidence use DOM text nodes rather than injecting model HTML.

Final verification: **28 UI state tests passed**, covering the existing flows plus account/view changes during Insights requests, stale scenario calculations, duplicate feedback, legacy evaluation records and terminal benchmark status/health updates. Browser checks verified employee/admin navigation, saved answer feedback, prompt content and hashes, real progress, cancellation after one case, export availability, cost scenarios and no page overflow at 320/390 px. Phone screenshots were inspected at 390 × 844. An inherited style that hid metric sample counts on phones was fixed: denominators remain visible on every screen size. No console errors or warnings were captured; the viewport override was reset.

Details: browser observations (local artifact `phase3-browser-checks.json`) and [Phase 3 engineering review](PHASE3_REVIEW.md). These are responsive browser checks, not physical-device Safari certification.

The Phase 3 follow-up review adds a calculator input-edit guard: changing any assumption immediately clears the previous results and invalidates an in-flight response. All **29 UI state tests** pass, including the deferred-response regression. A desktop browser check confirmed the dirty-input notice and correct recalculation after changing employees from 25 to 100, with no console warnings or errors. See the [follow-up review](PHASE3_REAUDIT.md) for evidence and the separate backend activation status.

The subsequent remediation adds semantic verdicts and reasons to Quality lab, an explicit pending-human-review state, a historical warning for older keyword-only scores, and direct full-policy access for reviewers. The existing dark glass design is retained. **32 UI state tests pass**. Browser verification of the restarted app confirms historical labeling, active-run progress, the completed eight-case result with human review still pending, and full source-dialog access. See the [current remediation review](PHASE3_REMEDIATION.md).
