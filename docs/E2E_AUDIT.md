# End-to-end engineering, AI quality and security audit

> Publication note: raw run artifacts are private and excluded from Git. See the [evidence guide](evidence/README.md) for the reviewed public summaries and reproduction scope.

Audit date: 27 September 2026. Scope: the local, production-style portfolio prototype, not production certification. **Overall: PASS WITH ISSUES. Ready for a supervised portfolio demonstration: Yes.** No Critical or High findings remain in the tested scope. Two Medium host/performance concerns remain (A07 and A12); the application and prompt fixes are active in build `9ca7a344b04ced13`.

## Evidence and method

The audit uses unchanged official PDFs: [NIST SP 1300, February 2024](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.1300.pdf) and the [NIST Phishing fact sheet, March 2024](https://www.nist.gov/document/sbccphishingpdf), linked from [NIST's phishing guidance](https://www.nist.gov/itl/smallbusinesscyber/guidance-topic/phishing). The original files, source URLs, edition, hashes, page extraction and 21-case gold dataset are retained in `evaluation/audit/`. Five explicitly fictional fixtures test thresholds, conflicting rules, document injection and restricted evidence. Nothing was added to the user's saved demo library.

Actual Qwen and nomic embeddings run through the application's HTTP routes, SQL and embedded Qdrant in separate local stores. Evidence retrieval and complete outputs are saved. Quotes are checked against the original PDF page/text and canonical SQL, not just the model's own citation text. Tool checks inspect persisted records, ownership, decision state, idempotency and unchanged roles. Fault tests use controlled failures in temporary stores. Review judgments made by this engineering audit are AI-assisted source comparisons, **not invented human policy-owner approvals**.

The first run passed only **14/21** after source review, although generic screening reported 15/21. The discrepancy was an answer that cited a real but conflicting policy. Six other failures were false abstentions or an unsaved report. Both initial artifacts are preserved: `artifacts/e2e-audit-initial.json` and `artifacts/e2e-audit-initial-review.json`. Repeatedly giving the same wrong/refused answer was not counted as factual correctness.

## Reproduced findings and fixes

### A01 — High — RAG conflict handling

**Problem:** Asked for the Zephyr daily meal allowance, the model answered AED 120 even though equally active policy A stated AED 80 and neither established precedence. A valid quotation was misleading evidence for a single authoritative answer.

**Reproduce:** In an isolated store, upload `conflict-a.txt` and `conflict-b.txt`; ask gold case `conflicting-policy`. The initial artifact preserves the AED 120 answer and both retrieved policies.

**Root cause:** Quote/number validation checks the existence of text and numbers, not precedence or contradictory evidence; the answer prompt did not explicitly require conflict resolution.

**Minimum fix implemented:** Refuse relevant, otherwise matching numerical rules with different values across active documents; add explicit conflict/precedence instructions in prompt v4. Do not invent which policy wins. The detector is intentionally narrow and is not presented as a universal semantic contradiction detector.

**Verification:** `test_conflicting_active_numeric_rules_do_not_choose_a_winner`, `test_numeric_conflict_guard_respects_identity_format_and_topic`, and the fresh real-model conflict case.

### A02 — High — Document publication authorization

**Problem:** An administrator demoted while embeddings were running could still publish a replacement and supersede the active policy.

**Reproduce:** `test_upload_reauthorizes_after_long_embedding_call` changes the uploader's role from inside the embedding call, then attempts replacement. Before the fix, upload returned 200 and published.

**Root cause:** Upload authority was checked before inference but not inside the publication transaction.

**Minimum fix implemented:** Acquire the SQL write transaction, reread the current role and replacement state, then publish. Revocation returns 403, removes unpublished vectors, and leaves the existing document active.

**Verification:** The regression checks HTTP status, current policy, ready-document count and vector count.

### A03 — Medium — Missing index records and recovery

**Problem:** Deleting all or some vectors for a ready SQL document returned a normal 200 response, interpreted as missing evidence or allowing an unrelated source to answer. Re-uploading identical bytes could not repair it because duplicate detection returned early.

**Reproduce:** `test_missing_vectors_are_an_operational_failure_not_a_knowledge_gap` deletes an isolated document's vector IDs; `test_identical_reupload_repairs_index_without_losing_version_history` covers missing points, collection and SQL chunks.

**Root cause:** Ready SQL metadata was assumed to imply a complete vector index; duplicate detection checked the digest without index integrity.

**Minimum fix implemented:** Reconcile permitted SQL chunk IDs and expected counts with the vector store before searching. Missing records return actionable 503 and fail the workflow without calling generation. Identical re-upload republishes through the normal atomic versioning path when an index is damaged.

**Verification:** Five fault/recovery variants pass, including a correct answer from the repaired version. Arbitrary physical disk failure is not claimed to have been tested.

### A04 — Medium — Retrieval loses neighboring rule context

**Problem:** The MFA question retrieved a practical account checklist but omitted the neighboring Page 5 chunk stating the all-accounts rule.

**Reproduce:** Gold case `csf-mfa` with both official PDFs indexed. Inspect the initial retrieved chunks against Page 5 of SP 1300.

**Root cause:** Four ranked chunks were treated as self-contained; chunk boundaries could separate an example from the governing rule.

**Minimum fix implemented:** Search the substantive part of questions beginning with a publication reference, and expand common enterprise acronyms (MFA, SSO, VPN) for retrieval. Preserve the original question for generation. Keep all four ranked hits and add at most two adjacent chunks from the same canonical page/paragraph as the leading hits. Preserve competing documents, source identity and access boundaries.

**Verification:** `test_neighbor_context_keeps_canonical_locator_and_permission_boundary` plus actual retrieval and answer checks on the public corpus. This bounded approach does not promise perfect recall for a large enterprise collection.

### A05 — Medium — Citation errors caused false abstentions and missing reports

**Problem:** Supported function/inventory questions and a NIST report failed because generated quotes did not match the selected text exactly. A repeated question repeated the failure. The document-injection case safely abstained but did not answer the legitimate hours question.

**Reproduce:** Initial gold cases `csf-functions`, `csf-inventory`, `repeat-functions`, `document-injection`, and `report`; inspect validation results and original evidence.

**Root cause:** The small model could paraphrase or misattribute quotations. PDF extraction also fused words (`TheseFunctions`) that the model separated (`These Functions`). A diagnostic run proved that retrying alone did not resolve this whitespace mismatch. Only numerical failures previously had a bounded correction path; publication identifiers could also trip numerical validation.

**Minimum fix implemented:** Versioned prompt v4 requires exact source IDs and continuous copied text and makes one correction attempt for invalid/missing quotations or unsupported numbers. For PDF whitespace-only mismatches, map the candidate back to the original canonical source span and display that original span. Letters, punctuation, digits and negation may not change. Remove a leading publication reference only if it matches a genuinely cited document's canonical metadata; validate every number remaining in the actual claim. A publication number is never added to a numerical whitelist. No approximate semantic quote matching is used.

**Verification:** Both successful and failed correction paths are covered by `test_exact_quote_repair_is_bounded_and_never_accepts_fabrication`; numerical repair tests remain in the full suite. Real Qwen outputs are independently compared with source pages.

### A06 — Low — Audit fixture wording

**Problem:** The original MFA gold retrieval fragment said “Require” while the PDF said “Prioritize requiring”. The expected all-accounts answer was correct.

**Reproduce:** Compare the initial case's expected fragment with the retained Page 5 extraction.

**Root cause:** A manually entered fragment had not been checked against source bytes before the initial run.

**Minimum fix implemented:** Gold v1.1 corrects only the quotation fragment, records the correction, and adds a test that every expected source span exists on the specified page. Original results remain unchanged. The application retrieval defect was separately confirmed by inspecting the actual missing chunk.

### A07 — Medium — Host memory pressure and slow inference

**Problem:** During concurrent model work and an intermediate test run, Windows WMI reported `0x8007000e` while creating the test report. Runtime inventory measured 98% physical memory utilization (about 266 MB available of 16 GB).

**Root cause:** Host resource exhaustion under concurrent workloads; this was not a successful acceptance test and is not hidden from the report.

**Minimum mitigation applied:** Finish inference, unload idle test models, and run the regression suite sequentially. The complete sequential suite passed. Do not run benchmarks alongside a live demo. Adequate free RAM or a faster host remains necessary for comfortable response times.

### A08 — Medium — Quality grader rejects correct negation

**Problem:** A correct statement that only Procurement is required at AED 5000 and Finance is not required failed `no_forbidden_claims`, even with a supported semantic verdict.

**Reproduce:** Call `grade` for `purchase_5000` with “Only Procurement approval is required at AED 5000; Finance approval is not required”, a real procurement citation and a supported verdict. The old word blacklist returns false for the mention of Finance.

**Root cause:** A forbidden word was treated as a forbidden affirmative claim, ignoring negation.

**Minimum fix implemented:** Benchmark version `demo-quality-v4` removes this incorrect word blacklist and explicitly includes the legitimate negation in the expected behavior. Valid sources, Procurement coverage, valid quotes and the existing semantic verdict remain required; a contradicted or missing verdict cannot pass.

**Verification:** Two regression variants cover the correct negation and incorrect affirmative requirement; the full real-model Quality lab run exercises the revised grader. This grader-only change does not alter the public-corpus RAG execution path.

### A09 — High — Underspecified questions select an arbitrary policy

**Problem:** In a post-fix model run, “What is the limit?” returned the AED 120 meal allowance even though no policy or topic had been specified. The number existed in a document but was not a justified answer to the question.

**Reproduce:** Gold case `ambiguous-question` with the mixed public/synthetic library and no preceding conversation. The full-run artifact retains the erroneous response; its focused rerun is recorded separately.

**Root cause:** Retrieval produced some relevant-looking limit content, and generation selected one policy despite the lack of a topic. Prompt instructions alone did not enforce clarification.

**Minimum fix implemented:** Common generic questions without a topic or preceding conversation ask for clarification before retrieval or generation. A generic follow-up with an existing topic includes that preceding question in retrieval instead of guessing a new policy. This is a conservative clarification rule, not a universal natural-language ambiguity detector.

**Verification:** Four no-context variants and a contextual follow-up regression, plus the focused HTTP rerun of the frozen ambiguous case.

### A10 — Low — Audit export interrupted by a transient filesystem lock

**Problem:** The first focused clarification rerun stopped before executing a case when OneDrive briefly denied replacement of the result artifact. Application data was unaffected.

**Reproduce:** Attempt atomic replacement of the workspace result JSON while another process denies replacement. The observed failure was `PermissionError` during `Path.replace`, not a model or application failure.

**Root cause:** The audit runner assumed immediate atomic replacement would always be available in the synced workspace.

**Minimum fix implemented:** Save a local progress journal outside OneDrive and use eight bounded retries for the workspace export. A persistent failure still raises an error rather than claiming the export succeeded.

**Verification:** The subsequent focused run completed and produced both the local journal and the workspace artifact. Persistent-lock exhaustion was not separately fault-injected.

### A11 — Low — Stale new-topic regression expectation

**Problem:** The final regression suite initially reported one failure because an older test expected the literal acronym `VPN` in the embedding query. The new retrieval behavior correctly expands it to `virtual private network`.

**Reproduce:** Run `tests/test_api.py::test_followup_history_and_new_topic_query` against the old assertion. The artifact `e2e-audit-tests-before-expectation-update.xml` retains the mismatch.

**Root cause:** The assertion encoded the previous search representation. An initial strengthening also incorrectly assumed generation would run when the fixture library contained only an unrelated leave policy; the application correctly abstained without generation.

**Minimum fix implemented:** Assert the expanded new-topic query, absence of inherited leave context, and correct abstention without VPN evidence. Then upload actual VPN evidence and verify a supported response and the unchanged original question in the generation input.

**Verification:** The strengthened targeted test passes. No application code change was needed for this finding.

### A12 — Medium — Audit process lifetime interruption (host-level cause unresolved)

**Problem:** After successful browser verification, both Python server listeners and the then-running regression process were no longer present. Application error logs showed successful startup and no exception or shutdown explanation. The incomplete regression run is not counted as passing.

**Reproduction/evidence:** This was observed once during cleanup: connections to ports 8765/8766 were refused and the command runner no longer recognized its test session. It has not been deterministically reproduced. No Windows System resource-exhaustion event was found in the preceding 45 minutes; that does not establish the cause.

**Root cause:** Unresolved process-host/session lifetime interruption; there is insufficient evidence to attribute it to application logic, memory pressure, or a particular external process.

**Minimum mitigation:** Rerun the final suite with persistent file output, restart the backend, and recheck build identity and saved state. Keep the normal `start.ps1` terminal running during a demonstration and verify the health indicator before presenting. Durable workflow recovery and backup restoration are separately tested, but unattended process supervision is outside this prototype.

**Remaining concern:** The host interruption's cause remains unproven. The final health check establishes that the audited build is running at handoff; it is not a long-duration uptime guarantee.

## Coverage of the requested twenty areas

| Area | Verification and practical limit |
|---|---|
| 1. Ingestion/parsing/chunking/metadata/index | Two original PDFs: 11 physical pages, 31 chunks; five synthetic chunks. TXT/MD/PDF/DOCX parsing, size limits, overlap, metadata, SQL/vector joins and index repair tested. Scanned PDF OCR is explicitly unsupported. |
| 2. Retrieval/source selection | Gold page/content expectations; ACL-before-model tests; canonical SQL allowlist; bounded neighbor checks. Small-corpus recall only. |
| 3. Factuality | Complete answers compared with original source facts, threshold inclusivity, exceptions and conflicts; keyword presence alone is not a pass. |
| 4. Citations/traceability | Original-page quotation containment, canonical chunk/document IDs, page locator, version and source-view workflows. |
| 5. Hallucinations | Fabricated quotes, numbers, wrong source IDs, contradictory policies and semantic quality-grader regression cases. General semantic truth is not mathematically guaranteed. |
| 6. Unknown answers | Missing CEO contact and inaccessible secret must abstain; empty-library behavior tested without generation. |
| 7. Ambiguous/malformed/adversarial | Ambiguous limit, user/document injections, blank/oversized input, invalid enums, corrupted and unsupported uploads. |
| 8. Agent selection/execution | Actual Qwen planner plus deterministic allowlist; real ticket/report records; unsupported external email refused; substituted model tools blocked. |
| 9. Multistep/state | Planning → approval → independent decision → execution; rejection, replay, concurrency, interrupted recovery, conversation follow-up and restart persistence. |
| 10. Authentication/authorization | Random credentials, hashed passwords/sessions, expiration, rate limit, cross-user ownership, department/leadership permissions, self-approval denial and mid-request revocation. |
| 11. Validation/injection | Strict request models, body limits, CSRF/origin/host checks, CSP and text-based DOM rendering; source and user instruction attacks. Local-host compromise is outside this boundary. |
| 12. Errors/retries/fallbacks | Embedding/generation failure, bounded correction, API failure state, inference lock release and atomic side-effect rollback; no automatic replay of writes. |
| 13. Duplicate/missing/corrupt/conflicting documents | Duplicate idempotency, version replacement, failed replacement rollback, missing index repair, corrupt/encrypted/scanned documents and conflicting active policy checks. |
| 14. API/SQL/vector/integration failure | Controlled SQL/vector/model/API/audit failures and physical backup restoration. External ITSM/email integrations do not exist; local ticket/report tools are tested as local tools. |
| 15. Repeated-query consistency | Same functions question repeated with a fresh request; both correctness and agreement assessed. One pair is not a statistical consistency study. |
| 16. Performance | Actual end-to-end timings, bounded serialized inference, busy response, dashboard percentiles and explicit estimated-energy assumptions. No concurrent-load capacity claim. |
| 17. Config/dependencies/deployment | Python compile/import execution, exact installed lock versions, `uv pip check`, public OSV advisory query, loopback listeners, single-store ownership and runtime build verification. |
| 18. Dead code/imports/paths/assumptions | Application, scripts, static UI, launch/config and persistence paths inspected; test/import execution; operational documentation updated for v4 and repair behavior. Older prompts/reviews are intentional history. |
| 19. Valid but wrong results | The conflicting-policy false positive was found by source review, fixed and given an explicit assertion. Numeric threshold and source-scope cases test logical correctness. |
| 20. User journeys | Authenticated upload/query/source access, conversation follow-up, ticket, human approval/rejection, report/download, monitoring and quality workflows; browser smoke verification accompanies API tests. |

## Remaining boundaries

- This is a bounded agent: one explicitly requested local tool per request, with durable approval/execution steps. It is not an unrestricted autonomous agent, and approved access requests create review tickets rather than changing real permissions.
- Exact quotes and numeric checks do not prove arbitrary entailment. The numerical conflict detector is deliberately narrow; the quality lab's same-model semantic judge can share model errors. Human source review and a larger independently labeled domain corpus remain necessary for a real pilot.
- The document-injection fixture's malicious instructions remain visible in its verbatim source quotation. The observed protection is that the answer did not obey them and no tool ran; this is not a claim that displayed source text is sanitized of hostile instructions. Source text is rendered as text, not executable markup.
- Local demo authentication, HTTP/loopback, single-process SQLite/Qdrant, plaintext local storage/backup and local credentials are deliberate portfolio constraints. Production use needs enterprise identity, transport/storage protection, retention policy, monitored backup/recovery and capacity/security testing.
- PDF tables, scans and layout-heavy documents need a separate OCR/layout extraction capability; OCR is not silently simulated. The corpus demonstrates text-based PDFs and the supported formats.
- Zero returned OSV advisories is a point-in-time lookup result, not proof of absence of vulnerabilities. One Starlette/httpx test-client deprecation warning remains; it does not affect runtime routes.

## Final acceptance evidence

| Verification | Final result | Evidence |
|---|---|---|
| Python functional/security/fault regressions | **219 passed, 0 failed, 0 skipped**, 149.45 seconds | `artifacts/e2e-audit-tests.xml`, `e2e-audit-tests.log` |
| UI asynchronous state regressions | **32 passed, 0 failed** | `artifacts/e2e-audit-ui.xml` |
| Public/synthetic gold scenarios, actual local models | **21/21 passed after fixes and the recorded focused rerun** | `artifacts/e2e-audit-acceptance.json`, `e2e-audit-source-review.json` |
| Quality lab actual model cases | **8/8 automated passes**, 8 supported semantic verdicts; human signoff pending | `artifacts/e2e-audit-quality-lab.json` |
| Quality lab integration controls | **18/18 passed** | Same artifact: busy controls, fingerprinting, export, isolation and lock release |
| Live SQL/dashboard reconciliation | **19/19 passed after final restart** | `artifacts/e2e-audit-storage.json` |
| Fresh backup restoration | **12/12 passed** | `artifacts/e2e-audit-recovery.json` |
| Actual browser smoke observations | **12/12 passed** | `artifacts/e2e-audit-browser.json` |
| Dependencies | **34 locked versions match**, compatibility check passed, no advisories returned by completed OSV lookup | `artifacts/e2e-audit-dependencies.json` |
| Compile/import and runtime | Compileall passed; backend ready on the current source/prompt build | `artifacts/e2e-audit-runtime-final.json` |

The complete post-fix gold run passed 20/21, with the remaining ambiguity defect preserved in `e2e-audit-final.json`. A separate rerun of that frozen question passed after A09 on the same corpus/model identities. The aggregate records both execution builds (`338c8e8bf1b37e8f` and `9ca7a344b04ced13`); no failed artifact was relabeled as passing. The latest full Python suite covers the final code and strengthened tests. The interrupted test invocation has no acceptance value. Initial and diagnostic failures remain available for inspection.

### Evaluation metrics

- Correct answerable knowledge cases: **11/11**. Correct factual answers among answered knowledge cases: **11/11**.
- Expected evidence retrieved: **11/11**, with at most six chunks per query, including bounded neighbors.
- Citations traceable to the original source: **12/12**, including the generated report.
- Correct unknown/restricted/ambiguous/conflict refusal behavior: **5/5**.
- Agent scenarios: **5/5**: local ticket creation, independently approved access-review ticket, sensitive request rejection, persisted report, unsupported tool refusal.
- Repeated functions question: both answers correct and matching, **one pair only**.
- End-to-end RAG latency: **P50 65.96 seconds; P95 142.88 seconds** on this CPU host. Quality lab case latency: P50 116.76 seconds; P95 147.66 seconds, including semantic judgment.
- Hosted model API charges: **$0**. Electricity/hardware costs are not zero; no measured energy-cost claim is made.

These are small fixed-corpus results, not a production accuracy estimate. Complete-output engineering source comparison is recorded separately from automated screening; it is AI-assisted, not independent human policy-owner signoff. The Quality lab correctly retains `needs_human_review` with zero invented human reviews.

### Runtime, security and reliability conclusion

The backend was restarted and verified at `http://127.0.0.1:8765`, with PID 8132, current build `9ca7a344b04ced13`, installed local generation/embedding models and no missing dependency in health. The temporary browser server is stopped. The saved demo retains **13 documents, 26 chunks, 6 tickets, 2 reports and 5 approvals**. Audit test documents and browser mutations were confined to a separate store. A fresh sensitive backup remains outside source control and cloud-sync; its local location is recorded in the private snapshot-path artifact.

No unresolved Critical or High security finding was demonstrated. Authorization, injection resistance, fail-closed evidence checks, independent approvals and transactional side effects passed the executed tests. This does not establish resistance to every possible prompt injection or semantic error. Keep local credentials and backup contents private; do not expose the HTTP service publicly. The local identity, plaintext storage, single-process databases and absence of enterprise ITSM/SSO integrations remain deliberate prototype boundaries.

The two Medium concerns are CPU/memory constraints and the one unexplained host process interruption. The fresh suite and runtime checks passed afterward. One Low test-client deprecation warning remains; changing the runtime dependency stack solely to suppress it was not necessary for this audit.

### Exact remaining actions

1. **Before the portfolio demo:** ensure adequate free RAM, keep the backend's normal launch terminal/session alive, confirm **Local models ready**, and avoid running a benchmark during the demo. Allow up to a few minutes for local model responses.
2. **Before claiming unattended reliability:** investigate the observed host process interruption and use a supervised process lifecycle with an uptime/restart rehearsal outside the audit runner.
3. **Before a real pilot:** obtain independent human source/answer review, expand the domain-specific gold corpus (including nonnumerical conflicts and paraphrased ambiguity), establish performance targets, and add enterprise identity, transport/storage protection and capacity/security tests.

There are **no remaining functional code blockers for the bounded portfolio demonstration**. General autonomous task chaining, OCR, external service execution and production deployment are outside the promised prototype scope. The machine-readable consolidated decision is `artifacts/e2e-audit-final-status.json`; rerun `python -m scripts.audit_final_status` to reconcile the saved evidence with the current backend build.
