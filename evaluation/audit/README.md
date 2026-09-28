# Public-corpus end-to-end audit

This corpus is isolated from the saved Atlas demo library. The two PDFs are unchanged downloads from official NIST websites:

- [NIST SP 1300, Small Business Quick-Start Guide](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.1300.pdf), February 2024, nine physical PDF pages.
- [NIST Small Business Fact Sheet: Phishing](https://www.nist.gov/document/sbccphishingpdf), March 2024, two physical PDF pages; linked from the [official NIST phishing page](https://www.nist.gov/itl/smallbusinesscyber/guidance-topic/phishing).

`sources.json` records original URLs, editions, download times, SHA-256 hashes and sizes. Page locators use one-based physical PDF pages. The accompanying extracted JSON preserves the parser's text, including PDF typography artifacts; it is not silently corrected source evidence.

All five TXT documents are explicitly controlled, fictional test fixtures. They cover an inclusive purchasing threshold, two active contradictory policies, an embedded instruction attack, and a restricted canary. They are not real business policies or secrets.

`gold.json` contains 21 cases: 16 knowledge questions and five local agent workflows. Each records the expected answer, evidence, citation, tool and refusal behavior. Version 1.1 corrects the MFA quotation fragment to match the PDF; its question and expected answer are unchanged. Initial artifacts preserve the earlier expectation. The runner checks exact quote traceability to the original page and canonical SQL, relevant retrieval, permissions and real SQL side effects. Concept/keyword checks are screening only: the complete answers must also be inspected against the source. In particular, a source-valid quotation does not establish semantic correctness or resolve conflicting policies.

Reproduce from the repository root, with Ollama running and the installed local models available:

```powershell
.\.venv\Scripts\python.exe -m scripts.fetch_audit_sources
.\.venv\Scripts\python.exe -m scripts.build_audit_gold
.\.venv\Scripts\python.exe -m scripts.e2e_audit --output e2e-audit-new-run.json
```

Use `--only csf-functions,csf-inventory,csf-mfa` for a targeted run. Include the predecessor when selecting a follow-up case. Every run creates a separate store beneath `%LOCALAPPDATA%\EnterpriseCopilotAudit`; it does not overwrite demo conversations, documents or tickets. The result artifact records its path and build/model/gold fingerprints. Stores are retained for inspection and restart checks. They contain generated local demo passwords: do not publish their directory or credentials. Only publish the corpus, code, and reviewed result artifacts.

A completed, passing targeted run can be continued with `--resume <artifact-name> --output <new-artifact-name>`. This reopens the same isolated store, verifies unchanged build/model/prompt/gold/corpus fingerprints, retains all previous cases, and executes the remaining cases. It refuses to resume a failed or incomplete run. This avoids rerunning already verified model calls without hiding their provenance.

Run regression tests after real inference finishes on a memory-constrained laptop. Do not interpret a same-model quality judge as independent human signoff. Final assessment and remaining limitations are in `docs/E2E_AUDIT.md`.

Use `--store-from <completed-artifact-name> --only <case-id> --output <new-artifact-name>` to reuse a completed isolated corpus for a fresh targeted test after a code fix. It verifies the model identity, fixture bytes and stored document identities, records the new build, and does not carry forward old case results. The final acceptance summary explicitly combines the full run with the separate clarification rerun; it does not claim all cases ran on one build. A durable local progress journal and bounded workspace-export retries tolerate transient OneDrive locks.
