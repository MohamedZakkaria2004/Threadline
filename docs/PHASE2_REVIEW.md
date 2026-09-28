# Phase 2 engineering review

> Publication note: raw run artifacts are private and excluded from Git. See the [evidence guide](evidence/README.md) for the reviewed public summaries and reproduction scope.

Historical Phase 2 record. The latest implementation and sign-off are in the [Phase 3 review](PHASE3_REVIEW.md).

Date: 2026-09-27. Scope: the local portfolio MVP, not a production service. Work began at 09:40:54 UTC; implementation, review, fixes, and final verification finished at approximately 10:56 UTC (about 75 minutes, within the 3–4 hour limit). Phase 2 meets its intended local MVP requirements.

## Additional review requested after completion

A second review began at 11:16 UTC on the same date. It re-read the current action, RAG, storage, authentication, and browser code, checked the previous actual-model outputs against the synthetic source policies, and added fault-injection tests for gaps in the first review. Phase 3 remains unstarted.

| Severity | Newly reproduced issue | Resolution |
|---|---|---|
| High, conditional | Knowledge chat authorized retrieval but did not reauthorize the first answer after slow generation. A user department change or source access change during that interval could publish evidence that was no longer permitted. Reports already rejected this situation. The current UI has no permission editor; the test simulates a concurrent database change, relevant before adding administration features. | Knowledge publication now reloads the user and source permissions within the same `BEGIN IMMEDIATE` transaction as its saved answer and audit. Revoked evidence is redacted from the HTTP response, saved message, and workflow result. Both cases failed before the fix. All four knowledge/report access-change cases now pass. |
| Low | Closing a report by its close button or Escape did not invalidate a pending source request from that report, allowing a late source dialog to open after dismissal. | Both close paths now invalidate the pending source revision. Both new tests failed before the fix and pass afterward. |

The permission guarantee applies at the publication transaction. It cannot recall bytes already delivered or exported. Existing inference may already have processed evidence that was permitted when retrieval began. No production account or document permissions were altered during these tests.

Current regression evidence: `artifacts/phase2-reaudit-tests.xml` contains **128 passed, 0 failed** (85.63 seconds); `artifacts/phase2-reaudit-ui-tests.xml` contains **18 passed, 0 failed**. Before-fix evidence is retained in `phase2-reaudit-before.xml` (2 failed, 2 passed) and `phase2-reaudit-ui-before.xml` (2 failed, 16 passed). The four targeted backend cases are included in the full 128, not additional tests. The dependency dry run checked 34 installed packages and required no changes; one existing Starlette test-adapter deprecation remains.

The local HTTP service was stopped at the start of this additional review. Starting the existing application restored ready health with both installed models and all saved records. `artifacts/phase2-reaudit-browser-checks.json` records five fresh checks: persisted Operations records, report facts/SQL snapshot, source navigation/return, Escape dismissal, and no captured console warnings/errors. This is a fresh browser check; the original twelve-check journey is retained separately.

Fresh actual-model evidence in `artifacts/phase2-reaudit-live.json`: **2 passed, 0 failed**. The AED 6000 answer correctly required both Procurement and Finance, citing the rule for purchases above AED 5000 (167.06 seconds including one bounded correction). The expense answer correctly assigned receipt review to Finance and pre-travel business-purpose approval to the line manager, with a separate exact quote for each claim (48.24 seconds). Both returned and saved responses completed through the revised publication path. These outputs were manually compared with `sample_docs/procurement.md` and `sample_docs/travel_expenses.md`; this is logical verification of these cases, not a general semantic-accuracy guarantee.

The final idle `phase2-storage-check.json` run passed **all 8 checks**: no running workflows, consistent records/messages/approvals, valid provenance and database integrity. Counts remain 13 documents, 26 chunks, 6 tickets, 2 reports and 5 approvals. The follow-up created only two synthetic knowledge conversations; permission-change tests used isolated temporary stores. Review sign-off is **Ready for Phase 3 within the local portfolio scope**, after the two fixes above. The original 19-case actual-model acceptance was inspected but not rerun wholesale; the two fresh cases specifically cover the changed knowledge publication path.

### Requirements and next-phase implications

The eight requested review areas remain covered below. Local ticket creation, approvals/rejection, report ownership and provenance, persistence/recovery, input/role boundaries, and rollback behavior are exercised by the full regression suite. The additional fixes close two previously untested failure scenarios. No schema, dependency, model, prompt, or tool-registry change was needed. The synthetic policies, user roles, and existing operational records were preserved.

For Phase 3, the useful next tests are a small held-out set of conflicting-policy/exception/negation questions, warm versus cold latency samples under normal laptop load, and checks that monitoring/ROI views aggregate the actual persisted metrics correctly. These are proposed follow-ups, not tests claimed as passed. Any future permission editor or external action connector requires its own concurrency and authorization review; current approval authorizes only a local review ticket.

## Implemented requirements

| Requirement | Implementation and evidence |
|---|---|
| Locally hosted models | Existing Qwen 4B and nomic through loopback Ollama; no new models, paid APIs, or packages required |
| Agent/tool execution | Explicit Actions mode, strict structured plan, one allowlisted tool, server-side intent/risk checks |
| Support tickets | Real SQLite records; original user details; open/in progress/resolved/reopened lifecycle |
| Reports | Cited policy briefing, SQL counts of the creator's own tickets, formatted preview and Markdown download |
| Human approval | Independent reviewer, department scope, reason, approve/reject, no automatic grant of access |
| Workflow state | Persisted steps and running/waiting/completed/rejected/failed states; conversation updated after decision |
| Authentication and RBAC | Existing sessions, CSRF and document controls; role/department rechecked for mutations; private reports |
| Prompt/version and telemetry | Versioned v3 templates, prompt hashes, local model identity, latency/token metrics, audit events |
| Refined interface | Existing dark glass styling extended to Actions, Operations, approval forms, reports and traces |
| Enterprise context | Business brief and architecture updated; responsibilities and approval boundaries documented |

## Review method

Reviewed code paths and their authorization/transaction boundaries; used real SQLite/Qdrant with deterministic model doubles; injected failures and stale requests; ran actual Qwen inference over HTTP; compared saved outputs with the synthetic source policies and SQL records; inspected the real browser interface at desktop and 390 × 844 mobile sizes. Actual inference was kept sequential. Automated fixture stores are isolated from the demo library.

## Findings fixed

| Severity | Finding | Resolution and verification |
|---|---|---|
| High | The old unused agent scaffold could commit a side effect separately from terminal state/audit, replay mismatched requests, and expose tickets to managers outside their department. | Replaced before exposure. Side effect/state/message/audit share one transaction; mode/text/conversation bind replay; department rules apply to list and mutations. Fault, ownership, and replay tests pass. |
| High | Approval needed an immutable action binding, current authorization, independent reviewer, and protection against simultaneous decisions. | Persisted exact plan + digest; verify against workflow; reload roles inside `BEGIN IMMEDIATE`; unique ticket/workflow; forbid self-review. Two concurrent approvals create one ticket. |
| Medium | Phase 1 rejected the valid AED 6000 purchase scenario because the hypothetical amount was absent from source text. | One bounded correction under versioned prompts; the same strict validator checks the replacement. Live result correctly cites Procurement + Finance above AED 5000. User numbers never become evidence. |
| Medium | Numbers attached to units/currency could evade the numeric guard, and negative numbers borrowed positive-number support. | Reproduced all four cases before fixing token recognition/sign preservation. `phase2-number-guard-before.xml` records four failures; the corrected knowledge suite has 25 passes. |
| Medium | A generated expense answer merged an unrelated annual-leave responsibility into the travel approval sentence. A prompt-only correction passed once but failed on repetition. | Added a conservative evidence-focus heuristic for a dominant matching policy, retained similar/conflicting policies and multi-topic evidence, and strengthened the live evaluator to reject the irrelevant claim. Four retrieval-focus tests and two successive actual-model checks now pass; the final answer correctly assigns receipt review to Finance and pre-travel purpose approval to the line manager. |
| Medium | A saved report could outlive its creator's source access or have missing legacy provenance. | Recheck every view/download/replay; block missing/revoked provenance, redact listing and conversation metadata, mark superseded sources historical. |
| Medium | A retry after an uncertain browser response could create a second action; late responses could reveal a previous account's data. | Keep the idempotency key for uncertain retries; session/revision guards cover Operations and reports; duplicate form submission is suppressed. |
| Medium | A pending request could have no independent reviewer in the demo account set. | Fail clearly before inserting an approval; tell the user which demo accounts can complete the flow. |
| Medium | Interrupted actions and decision/message failures could leave inconsistent state. | Startup marks interrupted running work failed with a trace; pending approvals survive real application restart; missing message/audit failure rolls back ticket creation. |
| Low | An unavailable report linked to Tickets; late same-account dialog responses could replace a more recent selection or reopen a closed report. | Corrected Reports navigation and added independent dialog revision guards. All four added UI regression cases pass. Citation counts now describe supporting passages, avoiding a misleading distinct-source count when two quotes share a document. |

## Coverage of the eight requested review areas

1. **Functionality:** actual ticket creation/status changes, reports/downloads, approve/reject and scoped views exercised.
2. **Logic:** purchase boundary comparisons and report policy facts checked against source text; SQL report counts checked against actual ticket records; no access was granted by approval.
3. **Workflows:** repeated/concurrent decisions, request replay, updated conversations, new-session history, and restart/resume behavior verified.
4. **Failures:** unavailable/invalid local model, absent report evidence, audit failures, missing saved message, stale ticket status, interrupted planner, and no eligible reviewer tested.
5. **Assumptions/dependencies:** installed local models reused; dependency lock validated offline; one process/worker and serialized inference retained; no new runtime service needed.
6. **Data flow:** canonical permitted SQL source text reaches RAG, grounded outputs reach reports, and artifact/workflow/message/audit persistence stays atomic.
7. **Security/reliability:** self/cross-department approvals blocked; report ownership enforced even against another admin; source revocation and malformed requests denied; generated text rendered without HTML execution.
8. **Next-phase integration:** additive schema version 2, persisted provenance and trace IDs, model metrics and audit events provide inputs for Phase 3 monitoring/evaluation. No external-action connector is implicitly authorized.

## Remaining limitations and recommendations

| Severity | Remaining item | Effect / recommendation |
|---|---|---|
| Medium | Quote and numeric checks do not establish semantic entailment, including negation, eligibility, or every cross-policy relationship. | Keep answers/reports as drafts with source review. Expand semantic/adversarial evaluation in Phase 3; do not use generated text as an authorization decision. |
| Medium | CPU inference latency varies substantially with memory pressure. A concurrent test/inference run also triggered a Windows WMI memory-allocation diagnostic while writing the test report. | The final 124-test run completed cleanly with the model cache unloaded, followed by sequential live inference. Keep this order on this laptop. The UI preserves state and shows progress; record latency distributions in Phase 3. Final ticket/access requests took 14.01–28.73 s; the report took 117.45 s. The nine RAG cases had a 37.08 s median and 31.04–71.49 s range. These small samples are not latency guarantees. |
| Low | Operations lists are intentionally small-demo queries; workflow list shows the latest 100. | Add pagination/filtering if a pilot needs volume. |
| Low | Approval refresh is manual; pending reviews have no expiry/cancellation workflow. | Consider expiry/cancellation and notifications only if needed for the next scope. |
| Low | One test-library deprecation warning remains for Starlette's httpx adapter. | Tests run successfully with the locked versions. Review the adapter during the next dependency update; no speculative package churn required. |
| Deployment boundary | Local demo identity, HTTP cookies, filesystem-held demo credentials, no SSO, backup/HA, or shared vector service. | Appropriate only for the stated laptop portfolio. Reassess before any multi-user/public deployment. |

Downloaded reports are independent files; later permission changes cannot revoke an exported file. All demonstration policies and personas are fictional. Native iOS/Safari and physical devices have not been tested; this is an iOS-inspired responsive web app.

The additional review confirms the latency limitation: its two real answers took 48.24 and 167.06 seconds, with the latter using the bounded correction. The new 128-test regression run was clean. No production responsiveness or statistical quality guarantee is inferred from these samples.

## Original implementation acceptance evidence

- `artifacts/phase2-tests.xml`: **124 Python tests passed, 0 failed** in a clean sequential run (70.63 seconds). Includes all earlier regression tests plus Phase 2 contracts, four evidence-focus cases, and review fixes.
- `artifacts/phase2-ui-tests.xml`: **16 UI state tests passed, 0 failed**.
- `artifacts/phase2-live-evaluation.json`: **7 live integration cases passed**, covering four Qwen-generated requests and their real local records/state.
- `artifacts/phase2-sample-report.md`: saved actual-model report; manually verified 25 working days, 10 working days' notice, line-manager approval, carryover facts, real source quote, and own-ticket SQL snapshot.
- `artifacts/phase2-range-repair.json`: original purchase-range blocker passes after one bounded correction.
- `artifacts/phase2-topic-fix.json`: historical prompt-only success, subsequently shown insufficient on repetition; superseded by the retrieval fix and final acceptance run.
- `artifacts/phase2-focus-live.json`: after a repeat exposed the prompt-only limitation, the retrieval fix reduced four candidates to the directly matching travel source and returned the correct roles in 22.93 seconds.
- `artifacts/phase2-browser-checks.json`: twelve browser checks passed, including the full employee → Admin review → employee conversation flow, report/source inspection, mobile layout, and a final reload with the latest UI code. The final report displayed the verified SQL counts (1 in progress, 3 open, 2 resolved); source navigation returned correctly, with no console warnings/errors or page overflow.
- `artifacts/phase2-final-rag-evaluation.json`: **9 policy cases passed, 0 failed**. Manually inspected purchase thresholds, Procurement/Finance roles, mandatory receipts, permanent-employee eligibility, and follow-up context against the source policies.
- `artifacts/phase2-adversarial-evaluation.json`: **3 cases passed, 0 failed**. Real DOCX and PDF ingestion returned the correct 3-day booking notice and AED 150 meal limit; a retrieved instruction to claim administrator access was ignored while the correct 30-day parking fact was cited.
- `artifacts/phase2-storage-check.json`: **8 consistency checks passed**. SQLite integrity/foreign keys, terminal workflow/message agreement, ticket/approval linkage, report provenance, and absence of abandoned running workflows verified. Original 13 documents and 26 chunks remain intact.
- `scripts.verify_phase2` completed all four sequential suites with exit code 0. Total actual-model acceptance: **19 cases passed, 0 failed**, plus the eight datastore checks.

The initial failing prompt/number artifacts are retained as before-fix evidence, not accepted output. A live assertion's “PASS” is not sufficient by itself: the expense wording defect above was discovered through semantic inspection after its original keyword checks passed. The subsequent prompt-only false pass is also preserved; the final acceptance uses the stronger retrieval fix and stricter semantic expectation.

## Final decision

- **Critical issues to fix:** None outstanding for the agreed local MVP. The high-severity transaction, replay, approval-boundary, and publication-time access issues found across both reviews were fixed and regression-tested.
- **Recommended improvements:** Medium — broaden semantic/adversarial evaluation and measure latency under normal laptop load. Low — add pagination, approval expiry/cancellation, and address the test-adapter deprecation when those become useful.
- **Tests passed/failed:** Fresh review: 128 Python tests, 18 UI tests, 2 actual-model cases, 8 datastore checks, and 5 browser checks passed; 0 final failures. Original acceptance included 19 live cases and twelve browser checks, retained separately rather than claimed as rerun. Historical failures remain documented as before-fix evidence.
- **Ready for next phase: Yes.** Required local workflows are implemented, outputs were checked against source policies and SQL records, and failures/authorization/replay boundaries are covered. This supports Phase 3 evaluation, monitoring, and the business package within the portfolio scope. Phase 3 has not started.
