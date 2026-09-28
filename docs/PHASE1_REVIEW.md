# Phase 1 engineering review

> Publication note: raw run artifacts are private and excluded from Git. See the [evidence guide](evidence/README.md) for the reviewed public summaries and reproduction scope.

Historical review. The [current review after the UI redesign](PHASE1_REVIEW_CURRENT.md) supersedes this readiness decision and records additional repairs plus an unresolved RAG acceptance failure.

Review date: 2026-09-27. Scope: the local knowledge copilot only. Phase 2 tool execution is not enabled.

## Review method

Reviewed the implementation and its trust boundaries, ran deterministic tests against real SQLite/Qdrant stores, inspected the browser, and exercised actual local Qwen/nomic inference against known synthetic policies. Factual answers are checked against source text, not merely HTTP success or valid JSON. The live-evaluation artifacts retain answers and citations for independent inspection.

## Findings addressed before handover

| Severity | Finding | Resolution and verification |
|---|---|---|
| High | The original scaffold used a shared hardcoded demo password. | Generate separate random passwords, keep only salted password hashes in SQL, rotate known legacy passwords and invalidate their sessions. Auth and session tests pass. |
| High | Role-only retrieval did not enforce department scope. | Apply department/classification permissions before vector search, reload canonical SQL evidence, and recheck source endpoints. Cross-role and cross-department tests pass. |
| High | Saved answers and request replays could retain evidence after permission changes. | Reauthorize cited documents when loading history, replaying results and building model history. Revoked evidence is redacted. Regression tests pass. |
| High | A second seed/application process could run recovery before obtaining the vector-store lock and incorrectly fail a live request. | Acquire exclusive Qdrant ownership before recovery. A second-process regression test verifies the active workflow and its messages remain unchanged. |
| High | A valid quote did not prevent an unsupported numerical claim elsewhere in the answer. | Reject numeric claims absent from cited evidence. The initial 4B adversarial run generated 999 leave days; the guard blocked that output and returned an abstention. |
| Medium | A request ID could be reused with a changed question and return an unrelated cached response. | Bind replay to the original user/input/conversation. Identical successful requests replay without duplicate messages; changed input is rejected. |
| Medium | Document extraction lost PDF page references and offered no safe replacement workflow. | Preserve page/paragraph locations; stage replacement vectors and publish the new version transactionally. Failed replacement preserves the old active version. |
| Medium | Invalid model response shapes, unavailable embeddings and timeouts needed explicit handling. | Fail closed with actionable errors and persistent failed-request records. No partial document is published. Tests cover malformed JSON, invalid vectors and timeouts. |
| Medium | Formatting differences such as 5,000 versus 5000 could cause false abstention. | Normalize numeric formatting before support comparison; regression test passes. |
| Medium | Local 4B inference under concurrent browser/test load caused memory pressure and slow interactions. | Reject the smaller Qwen after a failed valid follow-up and an incorrect expense-approval detail. Retain Qwen 4B, reduce its context allocation to 4096, serialize inference/indexing, and release models after five idle minutes. Final selected-model results are recorded below. |
| Medium | Natural-language action requests could receive an explanation that implied a future action. | Add an explicit Phase 1 capability boundary for common action requests and strengthen the answer prompt. No operational write tools are exposed. |
| Medium | The pip fallback targeted Python 3.11, but the tested NumPy wheel requires Python 3.12. | Align the project, runtime selector, setup script and lock to Python 3.12. The frozen dependency sync reports no changes and compatibility checks pass. |
| Medium | A busy-engine health timeout could be mistaken for missing models. | Distinguish an active request from an unavailable endpoint and show timeout/retry guidance instead of an unverified missing-model claim. |
| Medium | Interrupted requests could leave a user message with no visible explanation after restart. | Recovery writes one terminal interruption message, marks incomplete indexing failed, and avoids duplicating messages on repeated restarts. Tests cover both running and previously failed orphan workflows. |
| Low | The live test runner could race server startup. | Add bounded health readiness checks and reject a server/evaluator model mismatch. |

## Known limitations and follow-up priorities

| Severity | Status | Limitation / recommendation |
|---|---|---|
| Medium | Accepted MVP limitation | Quote and numeric checks are not full semantic entailment checks. Valid words/numbers can still be combined into an incorrect claim. The small evaluated corpus is not evidence of enterprise-wide accuracy. Expand the reference set and review source support before a real pilot. |
| Medium | Deployment boundary | This is a single-process localhost demo with local demo accounts, not enterprise SSO or a public-facing service. Keep it local. A shared pilot needs identity integration and deployment hardening. |
| Medium | Phase 2 gate | `service.py` and agent tables are pre-existing, dormant scaffolding. Action-level permissions, approval semantics and side-effect idempotency require a separate review/test suite before enabling them. |
| Low | Recommended improvement | Pin/check model weight digests as well as model tags. Do not replace the embedding weights behind an existing tag without rebuilding its index. |
| Low | Recommended improvement | Add maintenance cleanup for orphaned vectors after abrupt crashes and a backup/restore command covering both stores. SQL visibility filtering prevents orphaned vectors from becoming evidence. |
| Medium | Trusted-input boundary | Parsing is in the application process, with file/page/text limits but no separate process sandbox. Use administrator-provided, trusted demo documents; isolate parsers before accepting arbitrary third-party files. |
| Low | Supported-input boundary | OCR, encrypted PDFs, complex layouts and DOCX headers/footers are outside the supported input scope. The application rejects unusable input and explains the limit. Original binaries are not retained; users inspect the indexed extracted source text. |
| Low | Dependency notice | The pinned Starlette test client emits a deprecation warning about its httpx adapter. Current tests pass; migrate the test adapter during a future dependency update. |

## Requirement checks

| Phase 1 requirement | Evidence |
|---|---|
| Python backend and usable interface | FastAPI + local HTML/CSS/JavaScript; browser login, library, chat history and source navigation inspected |
| Local model and local embeddings | Ollama adapter uses loopback only; live acceptance results include actual model outputs |
| SQL and vector database | SQLite and persistent embedded Qdrant; integration tests use both actual stores |
| Ingestion and chunking | TXT, Markdown, DOCX and PDF extraction; size, malformed-file, duplicate, replacement and overlap checks |
| Evidence-backed RAG and abstention | Source/quote validation, unsupported-number rejection, explicit insufficient evidence, live fact/abstention cases |
| Basic authentication/RBAC | Random passwords, sessions, role/department filters, upload restrictions, conversation ownership |
| Conversation state | Saved messages, reference follow-ups, same-request replay, restart persistence and failure records |
| Traceability | Prompt version and content hash, model tag, embedding model, source document version, workflow ID and latency |
| Enterprise framing | Business brief, stakeholder map, build-versus-buy rationale and architecture diagram |

## Final verification results

- **65/65 deterministic tests passed**, with no failures and one dependency deprecation warning. These exercise real SQLite/Qdrant storage and a controlled model double. Coverage includes authorization, session expiry, CSRF, ownership, document versions, failed replacements, malformed inputs/model outputs, embedding validation, timeouts, concurrency, restart recovery and request replay.
- **15/15 selected-model live acceptance cases passed** using Qwen 4B and nomic embeddings. Returned answers were inspected against the synthetic source text, including the follow-up approving authority, HR retention period, Operations incident timing, and restricted contingency reserve. Access denial, missing evidence, role spoofing and unsupported actions were also checked.
- **3/3 additional live checks passed:** actual DOCX and PDF ingestion-to-answer pipelines with correct paragraph/page citations, plus a retrieved document containing a malicious system-override instruction. The answer retained the supported parking duration and did not follow that injected instruction.
- **Browser verification passed:** employee/admin login, scoped library, conversation creation and reopening, follow-up answer, source inspection, and admin upload duplicate detection. A fresh browser-to-Qwen request returned the correct **25 working days**, the matching source quote, and a **43.4-second** latency. No browser console errors were recorded on that final tab. Desktop layout was visually inspected; mobile layouts were not separately tested.
- **Dependency and static checks passed:** frozen dependency resolution, installed-package compatibility, Python compilation and JavaScript syntax validation. The corpus contains **13 synthetic policies**. Application data persists outside the OneDrive project folder.
- **Final restart passed:** the updated application reported ready, the existing browser session reopened its saved answer and citation, all 13 documents remained ready, and no workflow remained running. Phase 1 implementation and review took approximately **72 minutes**, within the requested 3–4-hour maximum.
- **Measured CPU latency:** median **47.99 seconds**, p95 **83.46 seconds** across the 15-case acceptance run; the first request included model loading. This small sample is a local demonstration measurement, not a service-level commitment.

The initial 4B adversarial case safely abstained after the numerical guard blocked an invented value; its original test incorrectly required an answer instead of allowing a safe refusal. That expectation was corrected, then the full selected-model suite passed. A smaller 1.7B candidate was rejected after source inspection revealed an incorrect expense-approval detail and a failed valid follow-up. The initial and rejected-run artifacts are retained, rather than counted as passing final results.

Evidence: `artifacts/phase1-tests.xml`, `artifacts/live-evaluation.json`, `artifacts/adversarial-evaluation.json`, and `artifacts/environment.json`. These are synthetic-corpus checks, not a general hallucination-rate estimate.

## Handover decision

- **Critical issues to fix:** none open within the local Phase 1 scope; identified high-severity defects have regression coverage.
- **Recommended improvements:** expand semantic evaluation before a real pilot (Medium); profile CPU latency on larger corpora (Medium); add coordinated backup/restore and model-digest checks (Low). Implement and separately review action authorization, approvals and side-effect idempotency before enabling Phase 2 tools.
- **Tests passed/failed:** 65 deterministic and 18 actual-model checks passed; zero unresolved final test failures. Earlier rejected results and the dependency warning are described above.
- **Ready for next phase: Yes.** The ingestion, authorized retrieval, evidence presentation and persisted-state foundation is validated for continuing the portfolio MVP. This does not establish production readiness or authorize enabling dormant agent scaffolding unchanged.
