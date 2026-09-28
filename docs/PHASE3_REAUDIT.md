# Phase 3 follow-up engineering review

> Publication note: raw run artifacts are private and excluded from Git. See the [evidence guide](evidence/README.md) for the reviewed public summaries and reproduction scope.

**Historical review:** The user subsequently authorized remediation and restart. See [Phase 3 remediation and activation](PHASE3_REMEDIATION.md) for the updated implementation and current readiness. The findings and pending-restart status below describe this earlier review, not the subsequently restarted backend.

Date: 2026-09-27. Started 13:11:23 UTC; follow-up checks completed approximately 13:27 UTC. Scope: fresh review of Phase 3 and its integration with the existing local portfolio platform; no next-phase features or deployment expansion. This is an AI-assisted engineering assessment, not an independent human or production audit.

## Findings and disposition

Four medium-severity defects were reproduced and corrected in the source. No Critical/High issue was identified within the local portfolio scope. **The running Atlas backend has not yet loaded these fixes:** automatic approval review rejected its restart with only “blocked by policy” as the reason. The corrected source is tested separately; runtime adoption remains pending a normal application restart.

| ID / severity | Reproduction and impact | Fix / verification |
|---|---|---|
| R1 — Medium | Injecting a progress-write failure leaves `summary.finished=1` but `results=[]`. The UI/export falsely reports a finished case with no saved evidence. | Finalization writes results and their summary in the same transaction. The error fallback also stores matching results/summary. Tests cover both progress failure alone and progress plus final-audit failure; failed status and lock release remain explicit. |
| R2 — Medium | Change a fixture, prompt fingerprint or initiator role while the **last** model call is running. Pre-call checks pass, and the old code publishes the result as a completed unchanged benchmark. | Validate context after each model call as well as before it. Three fault-injection cases now discard the changed-context case, retain two preceding cases, report failure and release the lock. The test does not alter real policies or user roles. |
| R3 — Medium | Change an unrelated vector point's payload to name an allowed fixture. Qdrant's payload filter admits it; SQL reload previously checked permission but not membership in the benchmark allowlist. This contaminates a fixed benchmark with another document. | Recheck the canonical SQL document ID against the originally selected allowed IDs. Tested using actual isolated Qdrant storage with a corrupted payload. This reproduces a scope/integrity flaw, **not a demonstrated cross-role disclosure**: ordinary RBAC checks were already present. |
| R4 — Medium | Edit a cost assumption while a calculation is pending. The earlier response can place old results underneath the new input values; previously calculated results also remain after edits. | Every input edit invalidates the pending calculation revision, clears obsolete values and prompts recalculation. Deferred-response UI regression passes. Browser verification changes employees from 25 to 100, sees the dirty-input notice, then receives the correct recalculated values. |

Changes are limited to `app/evaluation.py`, the SQL allowlist check in `app/knowledge.py`, the calculator input handler in `app/static/app.js`, and review tests/docs/scripts. Answer/planner prompts, model settings, grading v2, SQL schema, operational data and action authorization semantics are unchanged.

## Remaining issues by severity

**Medium — automated grading cannot establish semantic correctness.** A constructed diagnostic negated both expense-policy responsibilities while retaining all expected terms and genuine supporting quotes. The proxy grader accepted it. The statements are incorrect on direct source comparison. Diagnostic evidence (local artifact `phase3-reaudit-diagnostic.json`) labels this as constructed input, not something the real Qwen run produced. This confirms a documented limitation rather than demonstrating a new actual-model failure. Never present automated pass rate as enterprise correctness or a hallucination-free guarantee. Use independent policy-owner review on a representative held-out corpus before operational reliance.

**Medium — deployment scope and capacity remain limited.** One local process, demo identities, local SQLite/Qdrant and serialized model work are appropriate for the portfolio. Shared use needs separately scoped SSO, backups/restore rehearsal, retention/ownership, concurrency and external-connector authorization. Laptop latency is variable; benchmark P50/P95 is not an SLA.

**Low — reproducibility/dependency boundaries.** Model tags are not immutable weight fingerprints; energy values are assumed generation-only estimates. One test-client deprecation warning remains. These checks are not a package vulnerability audit or a physical iOS Safari test.

**Pending operational step — restart the running app.** The attempted health-checked restart was rejected before execution. No second restart method was attempted. Source changes and the existing process are therefore deliberately distinguished in this report. Restarting through the normal launcher is required before treating the running backend as the corrected build.

## Assessment of the eight requested areas

1. **Functionality flaws:** Fixed result/summary disagreement and stale calculator output. Feedback, quality history, cancellation, export, prompt registry, insights and core actions remain covered by regression tests.
2. **Logic errors:** Re-read all three policy fixtures and inspected the eight saved actual-model answers. Leave scope/units, distinct approval responsibilities, inclusive/strict purchase thresholds, mandatory receipts, contractor limits and safe abstention remain logically correct. Recalculated cost arithmetic independently; no measured ROI is claimed.
3. **Workflow completeness:** Failed/cancelled/interrupted benchmarks retain meaningful state; finalization and audit failure paths are now tested together. No operational side effect is replayed. Runtime activation of fixes remains pending restart.
4. **Edge/failure scenarios:** Added storage-error, context-change, role-change, corrupted-vector and input-edit race tests. Existing tests cover empty metrics, invalid finite bounds, zero denominators, missing fixtures, model errors, cancellation, restart, stale sessions and ownership failures.
5. **Assumptions/dependencies:** Verified the fixed benchmark against seed-file contents and fingerprints. Existing local models and installed libraries are used; no download or hosted inference. A source revision is detected rather than silently scored under old expectations.
6. **Data flow/integration:** SQL is now authoritative for both permission and allowlist membership after vector retrieval. Results and summary stay consistent during storage failures. Benchmark metrics remain separate from operational totals; the read-only SQL check reconciles dashboard counts and latency.
7. **Security/reliability:** Reviewed authentication, CSRF/origin checks, current-role checks, feedback ownership, independent action approval and private-report paths. Tests run in isolated stores; the running demo's documents, users, tickets, reports and approvals are not mutated by fault injection. No external tools or permission grants are added.
8. **Readiness for further work:** The corrected source can be built on within the local MVP scope after activation. Independent semantic evaluation and deployment hardening remain explicit prerequisites for a real pilot, not silently completed features.

## Output correctness and evidence

The eight prior real-model outputs in the original full run (local artifact `phase3-full-evaluation.json`) were **reinspected, not all regenerated**. Every quote still occurs in the unchanged seed file; the conclusions match the source conditions. The constructed contradictory diagnostic above illustrates why this assessment is separate from keyword/quote checks. Independent human-review counters remain zero.

Browser cost check for **100 employees**, holding all base assumptions constant: 2,000 requests/month; 70 net hours freed; USD 2,100 capacity value; USD 100.75 operating cost; USD 1,809 first-year cost; USD 23,391 first-year net capacity value; **1,293.03% modeled ROI**; about 0.30-month payback. Input edits first remove old results. This is hypothetical capacity value, not observed savings. No browser console errors/warnings appeared in this check.

Fresh isolated real-Qwen run `327807aa-61f7-48a3-9a2a-a65a76ae307a` returned three logically correct answers: **25 working days per calendar year for permanent employees**; **Finance reviews receipts before reimbursement, while the line manager approves business purpose before travel**; and **insufficient evidence for the unknown CEO**. The exact quotes match the seed text. Case times were 58.85, 32.75 and 34.02 seconds. This used current source with the installed local models, fresh temporary SQL/Qdrant and ASGI routes; it does not claim that the old running HTTP process loaded the changes. The temporary store was cleaned up normally and the JSON evidence is retained.

## Tests and execution limits

| Check | Result / scope |
|---|---|
| Before-fix reproductions | Five new Python cases failed and one new UI case failed for the defects above; preserved in `phase3-reaudit-before.xml` and `phase3-ui-reaudit-before.xml`. |
| Final Python regression suite | **163 passed, 0 failed**, 163.19 seconds recorded in JUnit, one existing deprecation warning. Real temporary SQL/Qdrant, deterministic model double. JUnit (local artifact `phase3-reaudit-tests.xml`). |
| Final UI state suite | **29 passed, 0 failed**, including late calculator results after an input edit. JUnit (local artifact `phase3-ui-reaudit.xml`). |
| First targeted fix run | **34 passed, 0 failed**; a combined progress-plus-audit test was subsequently added and passed in the full 163. JUnit (local artifact `phase3-reaudit-targeted.xml`). |
| Semantic diagnostic | One intentionally contradictory answer accepted by proxy checks; **known medium limitation remains**, not counted as semantic success. |
| Fresh real-model integration | **3/3 Qwen cases and 10/10 ASGI integration checks passed**; fixtures/prompts, scope, export, no invented judgments, metric isolation and lock release verified. Isolated run (local artifact `phase3-reaudit-live.json`). |
| Running datastore / SQL reconciliation | **19 passed, 0 failed**. Read-only checks (local artifact `phase3-reaudit-storage.json`). Original 13 documents, 26 chunks, six tickets, two reports, five approvals, three evaluations and one feedback rating remain. The review adds a login audit event; no operational artifact or model metric was added to this store. |

Activation procedure: stop Atlas through its current terminal or run `.\stop.ps1`, then start `.\start.ps1` from the project folder. The launcher does not replace an already-running process. After restart, confirm `/api/health` is ready and run `.\.venv\Scripts\python.exe -m scripts.phase3_storage_check --reaudit`. The ordinary live review command is `.\.venv\Scripts\python.exe -m scripts.phase3_reaudit_live`; `--isolated` instead checks current source in temporary stores. These are instructions for the pending activation, not a claim that it has happened.

- Critical issues to fix: **None identified in the local portfolio scope; four medium defects are fixed in source.**
- Recommended improvements: **Activate the corrected backend by restarting Atlas; retain independent semantic review and plan pilot identity/recovery/capacity controls.**
- Tests passed/failed: **163 Python, 29 UI, three fresh local Qwen cases, 10 isolated integration checks and 19 datastore checks passed. Zero final regression failures; one deliberately contradictory diagnostic exposes the documented semantic-proxy limitation.**
- Ready for next phase: **No for the currently running backend until it is restarted to load the fixes. The corrected source passes regression checks; no next-phase work has been started.**
