# Public audit evidence

The [28 September publication checks](publication-checks-2026-09-28.json) record
fresh local regressions, dependency review, and media scope for this repository
release. These are separate from the historical source-reviewed model results
below. The live CI badge reports the current remote deterministic check status.

These three reviewed summaries are unchanged copies of the 27 September 2026
engineering audit. They contain public/synthetic case judgments, aggregate
results and model/build fingerprints, without credentials, machine paths or
private document exports. [manifest.json](manifest.json) records their hashes.

- [Consolidated historical status](e2e-audit-final-status.json)
- [Gold acceptance and metrics](e2e-audit-acceptance.json)
- [Case-by-case source comparison](e2e-audit-source-review.json)

They are historical evidence, not a fresh test of every later checkout. Gold
acceptance combines a full run with an explicitly documented focused rerun; it
is not a claim of 21 cases executed in one run or independent human approval.
Raw outputs and earlier failure artifacts remain private in `artifacts/`.
Use the [public gold corpus](../../evaluation/audit/README.md) to repeat evaluation,
and the [engineering audit](../E2E_AUDIT.md) for scope and remaining limitations.

The separate [repository-check summary](repository-checks-2026-09-27.json) records
the later fresh setup, regression and 28-check live publication rehearsal. It is
an aggregate prepared for publication, not a raw export or a replacement for the
three historical artifacts above. Its scope and preliminary harness corrections
are documented in the [repository review](../REPOSITORY_READINESS.md).
