# Threadline hero refresh

> Publication note: raw run artifacts are private and excluded from Git. See the [evidence guide](evidence/README.md) for the reviewed public summaries and reproduction scope.

Threadline describes the traceable connection between a source, an answer and a considered action. The browser title, wordmark, favicon, assistant label and welcome now use this name. Historical audit artifacts and existing launch commands retain their original identifiers.

The public hero includes an interactive three-scenario walkthrough: find a cited answer, prepare a briefing, and pause an access request for an independent reviewer. The policy excerpts match `sample_docs/annual_leave.md`. All scenarios are explicitly illustrative; switching them never invokes inference, reads private documents, creates tickets or submits approvals. Source text and scene content use text nodes. The signed-in welcome includes a separate compact explanation of source permissions, evidence and reviewed actions.

Visual changes include a woven thread mark, lavender/blue glass surfaces, a connecting evidence path, hover and state transitions, and locally bundled Manrope variable typography. The original font and SIL OFL license are in `app/static/fonts/`. No runtime CDN or new package dependency is needed. Reduced-motion and reduced-transparency preferences are respected.

Verification on 27 September 2026:

- Existing UI state suite: **32 passed, zero failed**, `artifacts/threadline-ui-tests.xml`.
- JavaScript syntax checks passed for `app.js` and `hero.js`.
- Seven static checks passed: unique HTML IDs and exact HTTP-to-file matches for HTML, both scripts, hero CSS, favicon and font (`artifacts/threadline-static-checks.json`).
- Actual browser: all public scenario content and selected states checked; mouse and Enter-key activation worked.
- Manrope was confirmed loaded. Desktop content width matched its 1270-pixel client width; mobile content width matched its 380-pixel client width within a 390-pixel viewport. No horizontal overflow was observed.
- Mobile workspace anchor brought the sign-in card into view. Existing employee credentials successfully signed in; all three welcome descriptions were checked, including keyboard activation. Sign-out worked.
- Desktop and mobile compositions were visually inspected; no browser error/warning entries were reported in the inspected log.
- Responsive viewport override was reset. Browser testing used the `localhost` hostname so the user's existing `127.0.0.1` session was not signed out.

This is a frontend change. The existing audited backend, model prompts, data store and authorization logic were not modified. Refresh an open page to load the new assets.
