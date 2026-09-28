# Phase 1 review after the UI redesign

> Publication note: raw run artifacts are private and excluded from Git. See the [evidence guide](evidence/README.md) for the reviewed public summaries and reproduction scope.

**Historical review:** Phase 2 subsequently resolved the purchase-range blocker and enabled reviewed local workflows. The current acceptance decision is in [PHASE2_REVIEW.md](PHASE2_REVIEW.md). The findings below preserve the earlier evidence and decision.

Date: 2026-09-27. This review supersedes the earlier Phase 1 readiness decision. It covers the currently enabled local knowledge application, including the dark glass interface. Phase 2 remains disabled.

## Method and scope

Read the backend, frontend, storage transactions, retrieval/validation logic, model adapter, setup scripts, existing tests, and dormant agent integration boundary. Re-ran the existing suite, injected database failures, tested delayed UI responses with a synthetic DOM, and exercised the real Qwen model through the running HTTP application. Synthetic test stores are isolated from the user's 13-document library. Answers were inspected against policy text, not only status codes, expected words, or JSON validity.

## Newly reproduced defects, repaired in this review

| Severity | Finding and practical effect | Repair and evidence |
|---|---|---|
| High | An audit failure after publishing a replacement marked the new version failed while leaving the old version superseded. Neither policy remained available for retrieval. | Commit the publication, supersession and audit event in one SQL transaction. A trigger-injected audit failure now leaves the old policy ready and answerable. Response-read errors are outside publication rollback handling. |
| High | A response started under a previous account could finish after sign-out and repopulate the library with that account's document names. | Add a session generation check before consuming responses. Clear source text, the source dialog, drafts and upload state at sign-out. Deferred-response tests verify no previous-account library, answer or draft reaches the new session. |
| High | A quote consisting entirely of spaces passed validation because an empty normalized string matches every source. | Require meaningful normalized quote text. Blank answers also abstain. Both counterexamples were reproduced before repair and now fail closed. |
| Medium | Audit failures could leave a completed answer plus a failure message, an inconsistent stored result, or a running workflow with no handled failure. Login audit failure could also leave an unused session. | Couple start/completion/login audit events to their respective SQL transactions. Fault-injection tests verify rollback, one consistent failure reply, and no orphan conversation/session. |
| Medium | Redacting a replay after document permission changes also removed its conversation/workflow/message identifiers. | Preserve a small allowlist of protocol metadata while removing the evidence and answer. The response remains usable without disclosing the revoked text. |
| Medium | A delayed saved-conversation response could overwrite a newly opened conversation or the selected view. | Invalidate stale selections using a view revision. A deferred-response test confirms the new conversation stays empty and unselected. |
| Medium | A library-load failure after successful authentication was written to an invisible login error area. | Surface partial-load failures in the visible workspace banner; keep authentication and other loaded views usable. A regression test exercises the failure. |

The initial existing suite passed despite these defects. Six new Python cases and three initial UI cases failed before repairs. Additional login and UI failure cases were added to cover related transitions.

## Findings still open

| Severity | Finding | Required response |
|---|---|---|
| Medium — Phase 1 acceptance blocker | The valid question “For a purchase of AED 6000, whose approval is required?” returned insufficient evidence. The policy explicitly requires Procurement and Finance above AED 5000. Validation recorded `unsupported_numbers: ["6E+3"]`: it treats a restated hypothetical amount as an invented policy number. | Handle hypothetical/range questions without weakening the invented-number defense. Prefer an answer expressed using the cited threshold and required approvers. Re-test amounts below, at and above both thresholds, plus the malicious 999-day instruction. Do not simply exempt every number supplied by a user. |
| Medium | Exact quotes and numeric overlap do not establish logical support. A constructed answer reversed “requires prior line-manager approval” into “does not require ... approval” and the current validator accepted it. This was a validator diagnostic, not an observed model answer. | Keep source review explicit. Add contradiction, negation, eligibility and exception cases to evaluation. Do not use `citations_valid` as authorization or evidence that an agent action is safe. |
| Medium | CPU/RAM pressure causes variable response times and can make browser interaction slow. During this review a memory snapshot showed about 850 MiB free out of 15.7 GiB usable; browser automation also timed out during inference. | Establish a practical local latency baseline with ordinary user applications open. Keep inference serialized, limit contexts/documents and avoid launching concurrent model workloads. A stable latency target has not been demonstrated. |
| Low | The expense answer combined travel and annual-leave approval in one sentence. Its three citations support the individual facts, but “before travel and annual leave” is ambiguous and broader than the expense context. | Keep policy subjects and conditions separate; tighten answer relevance and review sentence meaning, not just matching keywords. This is not being reported as a proven invented approval authority. |
| Low | Model tags are not checked against their recorded weight digests; coordinated backup/restore is not implemented. | Pin/verify model digests before reusing an index and add a backup/restore procedure covering SQLite and Qdrant together. |
| Low | The test client reports an httpx adapter deprecation. | Address in a planned dependency update. Current dependency compatibility and frozen resolution checks pass. No claim of a full dependency vulnerability audit is made. |

## Coverage of the eight requested review areas

| Area | Assessment |
|---|---|
| Functionality | Uploads, source viewing, local inference, permissions and conversation persistence work. Range-based question answering has the reproducible acceptance failure above. |
| Logic | Repaired empty-evidence validation and transaction consistency. Numeric support remains a heuristic; semantic correctness needs separate inspection. |
| Workflows | Repaired redacted replay IDs, account-switch races, stale view selection, logout cleanup and hidden initialization errors. |
| Edge cases/failures | Tests cover malformed files/model output, invalid embeddings, timeouts, size limits, duplicate/version replacement, interrupted startup, busy requests, audit failures and late responses. |
| Dependencies/assumptions | Python 3.12 environment and 34 installed packages are compatible; frozen sync needs no changes. CPU latency, model-tag stability and English text extraction are explicit assumptions. |
| Data flow/integration | SQL remains authoritative for access and source text; Qdrant is filtered before generation. Visibility/audit transactions now fail consistently. Prompt hash, model tag, source version and workflow IDs remain traceable. |
| Security/reliability | Server-side ownership/department/classification controls, loopback binding, CSRF and session checks are exercised. The stale-account UI disclosure was repaired. Parsing remains trusted-admin, in-process parsing rather than an arbitrary-file sandbox. |
| Next-phase risks | Dormant `service.py` is not an approved tool implementation. It must not be exposed unchanged. Phase 2 needs action-specific authorization, immutable approval inputs, execution-time permission checks, crash/replay-safe writes, and rejection/double-approval tests. |

## Requirements boundary

The implemented Phase 1 scope is local RAG, four text-document formats, SQLite/Qdrant, citations and abstention, basic account/department permissions, conversation state, initial tracing/evaluation, and enterprise problem/architecture documentation. Scanned PDFs/OCR, native iOS delivery, public deployment/SSO, production isolation and enterprise-scale performance remain outside this MVP.

Tickets, report generation, human approvals and their persisted action states belong to Phase 2. Operational dashboards, expanded cost/ROI assumptions, adoption KPIs and the deployment roadmap belong to later work. Their absence is not being mislabeled as a Phase 1 implementation defect.

## Evidence

- `artifacts/review-baseline-tests.xml`: 65 existing tests passed before the new counterexamples.
- `artifacts/review-reproduced-defects.xml`: six Python counterexamples failed before repairs.
- `artifacts/review-final-tests.xml`: 72 Python tests passed after repairs.
- `artifacts/review-ui-tests.xml`: six synthetic-DOM UI state tests passed after repairs.
- `artifacts/review-live-evaluation.json`: fresh actual-model policy-boundary, exception and follow-up cases, including complete answers and citations.
- `artifacts/review-semantic-limitation.json`: the constructed semantic contradiction accepted by the quote/number validator.
- `artifacts/review-storage-state.json`: final read-only database check reports integrity OK, no foreign-key violations, all 13 documents ready and zero running workflows.

Browser verification after inference completed confirmed administrator source viewing, source-text clearing on sign-out, employee sign-in, seven permitted employee documents, and a hidden upload panel for that account. Browser interactions timed out while inference was under memory pressure; they succeeded afterward. This is recorded as an operational limitation rather than silently treating the earlier UI attempts as successful.

Earlier 15-case acceptance and three-case PDF/DOCX/injection results are historical evidence. They were not rerun in full here and do not cancel the newly discovered failure.

## Fresh live results and logical inspection

| Case | Observed behavior | Assessment |
|---|---|---|
| Purchase exactly AED 500 | Line-manager approval | Pass; matches the inclusive lower threshold. |
| Purchase exactly AED 5000 | Procurement approval | Pass; Finance is required only above that threshold. |
| Purchase AED 6000 | Insufficient evidence; numeric guard rejects 6000 | Fail; the policy does answer this scenario. |
| Expense responsibilities | Finance reviews receipts; line manager approves business purpose before travel; also mentions annual leave | Facts have supporting citations, but wording has the Low-severity ambiguity described above. |
| Meal claim without receipts | Refuses reimbursement despite the amount being within the limit | Pass; preserves the exclusion rather than applying the amount alone. |
| Contractor leave entitlement | Returns insufficient evidence | Safe refusal. The trace shows an invalid generated quote was rejected; this is not proof the model independently understood the eligibility distinction. |
| Annual leave, first turn | 25 working days | Pass; matches the permanent-employee policy. |
| “Who approves it?”, second turn | Line manager | Pass; correct conversation reference. |
| “And how far in advance?”, third turn | At least 10 working days, through the HR portal | Pass; current evidence supports the answer. |

The fresh live run finished **8 passed / 1 failed**, with an **80.4-second median** and **128.88-second maximum** across nine sequential requests. The earlier 47.99-second median is not representative of this run. These are small local samples, not an enterprise service-level estimate.

## Final decision

- **Critical issues to fix:** no Critical-severity issue remains identified in the enabled local scope. The Medium-severity AED 6000 false abstention is an acceptance blocker and must be corrected before the next phase.
- **Recommended improvements:** broaden semantic evaluation; retain human source review and action-level approvals; profile memory/latency; improve policy-specific wording; add coordinated backups and model-digest checks.
- **Tests passed/failed:** 72 Python tests and six UI state tests passed. Fresh actual-model checks: eight passed, one failed. A separate constructed diagnostic demonstrates that semantic contradictions can evade the current validator. Static syntax/compilation and dependency compatibility checks passed, with one known test-client deprecation warning.
- **Ready for next phase: No.** The storage and UI defects found during this review are repaired, but a supported core RAG scenario still fails. Correct it and rerun its boundary/adversarial checks before enabling agentic operations. No Phase 2 functionality was enabled.
