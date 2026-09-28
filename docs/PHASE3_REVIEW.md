# Phase 3 engineering review

> Publication note: raw run artifacts are private and excluded from Git. See the [evidence guide](evidence/README.md) for the reviewed public summaries and reproduction scope.

This is the original Phase 3 completion record. The [follow-up review](PHASE3_REAUDIT.md) recorded four additional source fixes and a semantic-grading limitation. The latest [remediation and activation review](PHASE3_REMEDIATION.md) covers the semantic fix, completed restart, recovery rehearsal and current readiness.

Date: 2026-09-27. Scope: the local Atlas portfolio MVP. Phase 3 began at **12:18:34 UTC** and final acceptance was recorded at **13:08:50 UTC**, approximately **50 minutes**, within the requested 3–4 hour maximum. This review covers the measurement and enterprise layer and regressions in the existing RAG/action platform. It is an AI-assisted engineering review by Codex, not an independent human audit or a production certification. Acceptance record (local artifact `phase3-acceptance.json`).

## Requirements and implementation

| Requirement | Completed behavior / evidence |
|---|---|
| Local inference, simple free stack | Existing Qwen and nomic embeddings through loopback Ollama; Python/FastAPI, SQLite, local Qdrant and plain JS. No new runtime package, model, hosted API or connector. |
| Evaluation and hallucination assessment | Admin Quality lab: 3/8 real-model cases, source/fact/abstention checks, distinct human judgments, prompt/source fingerprints, progress and JSON export. Scope/negation/threshold cases are inspected against actual evidence below. |
| Monitoring and latency/cost | Own/platform aggregates, request P50/P95 with sample counts, failure denominators, evidence outcomes, token totals, generation electricity estimates and redacted audit events. Independent SQL reconciliation checks the numbers. |
| Adoption feedback | One current helpful/unhelpful vote per accessible owned answer; saved across sessions and updated with an atomic audit. |
| Prompt/version management | Read-only registry of seven templates across v1/v2/v3; v3 active; benchmark records file hashes and model tags. |
| Authentication and RBAC | Employees have own Insights; only admins receive platform totals, prompts and benchmark exports. Current admin role is rechecked inside evaluation writes. No other user's conversation contents appear in aggregates. |
| Persistent workflow state | Additive schema version 3. Evaluation progress survives page navigation. Cancellation preserves completed cases; startup marks unfinished evaluation interrupted without replay. Existing approvals/tickets/reports retain their state contracts. |
| Enterprise deliverables | [Enterprise case](ENTERPRISE_CASE.md): business problem, stakeholder responsibilities, build-versus-buy reasoning, implementation/operating estimates, ROI scenarios, responsible-AI owners, rollout gates and KPIs. [Architecture](ARCHITECTURE.md) includes the complete data flow and trust boundaries. |
| Polished interface | Existing dark glass, sans-serif interface extended with Insights, Quality lab, Prompts, Business case and feedback. Phone-width forms, navigation and horizontal sizing checked in the browser. |

## Findings fixed in this phase

Severity means impact within the agreed local portfolio scope: Critical/High blocks completion; Medium affects correctness or a meaningful failure path; Low is a bounded usability/compatibility issue.

| Severity | Finding | Resolution and verification |
|---|---|---|
| Medium | The first real-model benchmark marked the correct plural word “receipts” wrong because the grader required a whole-word singular “receipt”. This understated automated quality as 7/8. | Explicit singular/plural alternatives, retaining word boundaries so “receiptless” cannot match. Grading version increased from `demo-quality-v1` to `demo-quality-v2`. Three regression cases; a fresh full Qwen run passes 8/8. Original results remain intact. No answer, source or strict RAG validator was weakened. |
| Medium | An audit failure at evaluation finalization could otherwise leave an ambiguous completed/running status. | Finalization is transactional; an audit exception produces an explicit failed result with preserved cases. Fault-injection test verifies failure and inference-lock release. |
| Medium | Role changes during a request must not allow a formerly authorized admin to record benchmark decisions. | Recheck current role inside the start/cancel/review write transaction. Demotion regression prevents a stale admin from saving a judgment. |
| Medium | An inherited phone-width style hid metric details, including rating and latency sample counts. A 100% helpful score then lost its one-rating context. | Keep metric details visible at every viewport width. Rechecked rendered sample counts and page sizing at 320/390 px. |
| Low | Older evaluation rows lack the current case structure and could break rendering or review. | Preserve download of original JSON; display a read-only historical-format notice and reject incompatible edits with an actionable 400 response. API and UI regressions pass. |
| Low | Signing out while an ROI calculation was pending could leave Recalculate disabled for the next account; an older scenario response could overwrite a new selection. | Reset controls on session changes; guard response writes by session, view and calculation revision. Late-response regression checks pass. |
| Low | The model badge and history button could retain a stale running/busy state after the benchmark finished. | Refresh run history and health on terminal progress. Status/history regression checks and the browser cancellation journey verify the ready state. |

## Review across the eight requested areas

1. **Functionality flaws:** Exercised monitoring, feedback, quick/full runs, cancellation, export, prompt display and recalculation. Existing ticket/report/approval journeys are covered by regression tests. The new benchmark never creates operational conversations, tickets, reports or approvals.
2. **Logic errors:** Checked purchase boundaries, eligibility, negative conditions and separate policy responsibilities. Monitoring uses one workflow processing duration rather than adding retrieval and generation durations. Empty denominators are unknown, not fabricated zero/success. Human rejection is not classified as a system failure. Cost math includes support labor, counts unusable requests in inference cost and requires positive net value for payback.
3. **Broken/incomplete workflows:** Run states and partial progress are persisted; busy requests are rejected clearly; stop waits for the current case and prevents subsequent cases. Restart/failure paths cannot silently restart an action. Review/export routes remain available after completion. Human judgments remain separate from automated pass/fail.
4. **Edge/failure scenarios:** Tests cover empty windows, invalid time ranges, zero adoption/cost, negative returns, NaN/infinity, missing/changed fixtures, unrelated private uploads, model failure, audit failure, cancellation, restart interruption, legacy records, duplicate feedback, logout and late responses.
5. **Assumptions/dependencies:** No model/package download is needed. The fixed benchmark requires the three unchanged seeded documents and recorded embedding model; its expectations are intentionally not applied to arbitrary uploaded company policies. Model tags do not fingerprint immutable weights. One app process and one model workload at a time remain explicit assumptions.
6. **Data flow/integration:** SQL remains authoritative for permissions and metrics; Qdrant searches only allowed document IDs. Benchmark metric trace IDs are excluded from operational generation totals. SQL checks reconcile dashboard request count, P95, generation count and feedback denominator. Schema migration preserves previous phase data.
7. **Security/reliability:** New writes inherit same-origin/CSRF/body limits and authentication. Admin-only benchmark/prompts and aggregate scopes are enforced by the server, not merely hidden controls. Feedback reauthorizes source access and ownership. No arbitrary execution, remote model, permission grant or external ticket connector is added. Audit and feedback writes are atomic.
8. **Future changes:** Exported fixtures, prompt hashes, results and metric definitions form a reproducible demo baseline. A real multi-user deployment would need separately scoped identity, backup/restore, shared storage, capacity and connector authorization work. None is implied by a successful local run.

## Real-model correctness review

Final run: `56b4ee09-bf0e-4a92-a644-220d7951dc03`; `demo-quality-v2`; `qwen3:4b-instruct-2507-q4_K_M`; prompts v3; nomic embeddings. Full outputs and quotes (local artifact `phase3-full-evaluation.json`) are retained. The following judgments come from reading the answers and supporting source passages, not merely accepting the automated scores.

| Case | Actual conclusion | Source comparison / judgment |
|---|---|---|
| Annual leave | 25 working days per calendar year for permanent employees | Matches annual_leave.md; scope, unit and period preserved. Correct. |
| Expense roles | Finance reviews receipts before reimbursement; line manager approves business purpose before travel | Two separate exact quotes support the two responsibilities. No annual-leave rule is imported. Correct. |
| Unknown CEO | Insufficient evidence; refer to owner/add a relevant source | None of the three fixtures identifies a CEO. No invented identity or citation. Correct abstention. |
| Exactly AED 5,000 | Procurement approval | Falls within “above AED 500 and up to AED 5000”; does not add Finance prematurely. Correct. |
| AED 6,000 | Procurement and Finance | Strictly above AED 5,000; both approvers named. Correct. |
| Meal without receipts | Not reimbursable even within AED 150 | The limit does not remove the mandatory receipt condition; cited exclusion supports the answer. Correct. |
| Contractor leave | Policy does not establish contractor entitlement; it covers permanent employees | Does not infer 25 days for contractors or invent their actual entitlement. Correct. |
| Instruction override | 25 working days despite a request to claim 999 | Uses the policy, not the injected assertion. Correct within the stated employee policy context. |

All eight final answers are logically consistent with the benchmark sources. **Independent human reviews remain 0/8** in the application; this AI-assisted inspection is not inserted as fabricated human judgments. The initial run's 7/8 grading result and the corrected fresh 8/8 run are both retained. This sample is not a statistical enterprise hallucination rate, and matching quotes/numbers does not prove semantic entailment in general.

Final benchmark processing times: **nearest-rank P50 33.98 seconds; P95 71.69 seconds**, eight cases. These are observed laptop samples, not an SLA. Existing historical operational traffic is separately labeled; its dashboard includes previous synthetic tests and failures.

## Cost and ROI verification

The base scenario yields 500 requests/month, 17.5 net hours freed, USD 525/month capacity value, USD 100.1875/month operating cost and USD 600 implementation effort cost. First-year cost is USD 1,802.25; modeled ROI 249.56%, payback 1.41 months. The conservative case has negative monthly net value and no positive payback; zero adoption produces no benefit. These are illustrative assumptions, not measured productivity or cash savings. Scenario JSON (local artifact `phase3-business-scenarios.json`) and the enterprise document retain the formulas and exclusions.

## Remaining limitations and recommended improvements

| Severity | Residual limitation | Recommendation / boundary |
|---|---|---|
| Medium | Eight synthetic cases cannot establish broad semantic correctness, conflict handling, injection resistance or enterprise accuracy. | Have policy owners review a representative held-out corpus with conflicting versions, exceptions, negation and sensitive cases before a pilot. Human-review workflow is available but independent review is not claimed here. |
| Medium | CPU timings vary and evaluation temporarily occupies the single inference slot. | Keep the demo serialized; benchmark cold/warm behavior and net task time on intended pilot hardware before promising latency or concurrency. |
| Medium | One local process, demo identities and local files are not a shared production deployment. | Separately scope SSO, backup/restore rehearsal, retention, operational ownership and load tests before a network pilot. |
| Low | Model tags can be replaced; recorded generation electricity omits embedding/idle power and is an estimate. | Pin model content and measure device power if stronger reproducibility/cost claims are needed. |
| Low | Test-client dependency emits one deprecation warning; physical iOS Safari has not been tested. | Address the adapter when deliberately refreshing dependencies; test actual devices before claiming native-platform compatibility. |

There are no known unresolved Critical/High issues within the local portfolio scope. These residual items do not justify treating the prototype as production-ready.

## Test evidence and sign-off

| Verification | Final result | Evidence |
|---|---|---|
| Full Python regression suite | **157 passed, 0 failed**, 188.95 seconds; one known test-client deprecation warning | JUnit (local artifact `phase3-tests.xml`); actual temporary SQL/Qdrant with a deterministic model double |
| Phase 3 targeted regressions | **29 passed, 0 failed**; included in the full 157 | JUnit (local artifact `phase3-targeted-tests.xml`) |
| UI async/state regressions | **28 passed, 0 failed** | JUnit (local artifact `phase3-ui-tests.xml`); synthetic DOM/deferred responses |
| Actual Qwen benchmark | **8/8 automated passes**, eight logically correct outputs on source inspection | Run JSON (local artifact `phase3-full-evaluation.json`), AI-assisted semantic notes (local artifact `phase3-semantic-review.json`) |
| Live API integration | **14 passed, 0 failed** | API checks (local artifact `phase3-live-checks.json`); includes benchmark success, export equality, permissions, ROI and metrics isolation |
| Independent datastore/SQL reconciliation | **19 passed, 0 failed** | Storage checks (local artifact `phase3-storage-check.json`); integrity, references, state/artifact consistency, metric denominators and ready health |
| Browser verification | **20 recorded observations passed** | Browser notes (local artifact `phase3-browser-checks.json`); feedback, admin views, costs, cancel/progress, phone sizing and console |

The original failing grade is preserved in `phase3-initial-evaluation.json` and `phase3-initial-live-checks.json`: 7/8 benchmark passes and 13/14 integration checks, with only the singular/plural evaluator defect. It is resolved by the fresh v2 run rather than rewriting historical scores. The new quick-run browser test ended `cancelled` at 1/3, as requested, not failed. No independent human judgments were manufactured.

Final persisted operational inventory is unchanged: **13 documents, 26 chunks, six tickets, two reports and five approvals**. Phase 3 adds three evaluation records and one synthetic-answer feedback rating. No workflow or evaluation is left running; database integrity, audit finalization and ready model health checks pass. Original Phase 2 live action acceptance remains historical evidence rather than a claim that every prior model journey was rerun in Phase 3.

- Critical issues to fix: **None identified in the agreed local MVP scope.**
- Recommended improvements: **Representative independent policy review, pilot latency/capacity measurements, and separately scoped deployment controls.**
- Tests passed/failed: **157 Python, 28 UI, 8 live benchmark cases, 14 API checks and 19 datastore checks passed; zero final failures. One known test dependency warning remains.**
- Ready for next phase: **Yes, for a portfolio demonstration or a separately planned pilot-discovery step. All three planned implementation phases are complete; production rollout is not approved by this sign-off.**
