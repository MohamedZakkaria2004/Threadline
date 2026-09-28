# Testing and evaluation

Threadline separates **software correctness, model behavior, source factuality, and human approval**. A valid response schema or HTTP 200 is not enough: verify original evidence, permission boundaries, and the actual saved artifact/state.

## Layers of evidence

| Layer | Method | What it establishes / does not establish |
|---|---|---|
| Python regressions | pytest; temporary real SQLite/Qdrant, deterministic model double | Authorization, ingestion, validation, transactions, failures and recovery; not real-model accuracy |
| UI state regressions | Node test runner with synthetic DOM/state | Stale responses, account switching, duplicate submissions, review UI; not full browser rendering |
| Public gold corpus | Real local Qwen and nomic, original NIST PDFs and controlled fixtures | Case-level retrieval, citation, factuality and workflow evidence for a small fixed corpus |
| Quality lab | 3-case quick / 8-case full; structural checks + separate local semantic judge | Automated screening against exact seed policies; same-model judging is fallible |
| Source review | Compare complete answers with original source pages and intended behavior | Historical AI-assisted engineering review; not independent domain-owner signoff |
| Live workflow/demo | Actual API/browser use, database state and artifact inspection | Working role journeys and logical continuity, within the tested scenario |

## Public enterprise validation documents

| Source | Version / size | Coverage |
|---|---|---|
| [NIST SP 1300: CSF 2.0 Small Business Quick-Start Guide](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.1300.pdf) | February 2024; 9 physical PDF pages | Framework functions, inventory, access and security guidance |
| [NIST Small Business Fact Sheet: Phishing](https://www.nist.gov/document/sbccphishingpdf) | March 2024; 2 physical PDF pages | Recognizing/reporting phishing and employee guidance |
| Controlled synthetic fixtures | Five TXT files | Inclusive purchasing threshold, conflicting rules, prompt injection, restricted canary |

Original PDFs, extracted page text, official URLs, timestamps and SHA-256 hashes are retained in [the corpus](../evaluation/audit/README.md). Physical PDF pages are one-based. No NIST endorsement is implied. Synthetic fixtures are explicitly fictional; the restricted canary is not a real secret.

## Gold-standard case schema

The [21-case dataset](../evaluation/audit/gold.json) records each question, expected answer/behavior, document, page/paragraph citation, expected source content, agent/tool action where applicable, and refusal/failure expectations. Cases cover 16 RAG questions and five agent workflows. Expected evidence is compared with canonical SQL and original source text, not model-created quotations alone.

Representative expectations:

| Scenario | Required behavior |
|---|---|
| Answerable public policy question | Retrieve intended document/passage; factual complete answer; traceable quote |
| Missing knowledge | Admit insufficient evidence instead of inventing an answer |
| Restricted source | Do not retrieve or expose unauthorized content |
| Conflicting numeric rule | Refuse an arbitrary selection between competing active rules |
| Embedded instruction attack | Treat source instructions as data; no unauthorized action |
| Routine ticket | Correct tool and one persisted local artifact |
| Access request | Pause, enforce independent review, create review ticket only |
| Unsupported external action | No tool execution or fabricated success |

## Recorded metrics and denominators

Historical public-corpus acceptance is dated **27 September 2026** and combines a full run with an explicitly recorded focused rerun after a clarification fix. It is not one pristine 21-case run on a single build. The [acceptance JSON](evidence/e2e-audit-acceptance.json) records both build fingerprints and exact model digests.

| Metric | Definition | Historical result |
|---|---|---|
| Overall acceptance | Accepted RAG and agent cases / gold cases | 21/21 |
| Retrieval evidence hit | Answerable cases containing intended evidence / answerable cases | 11/11 |
| Answer factuality | Source-correct answered RAG cases / answered RAG cases | 11/11 |
| Negative behavior | Correct absent/restricted/conflict/clarification behavior / negative cases | 5/5 |
| Citation traceability | Quotes traceable to original source / emitted citations | 12/12 |
| Agent workflow acceptance | Correct tool, authorization, side effect/state / agent cases | 5/5 |
| Repeated-query consistency | Correct and text-matching repeated pairs | 1/1 pair only |
| RAG latency | End-to-end P50 / P95 on recorded CPU host | 65.96 s / 142.88 s |
| Hosted-model API spend | Hosted inference charges incurred by these local runs | USD 0; hardware/electricity excluded |

No corpus-wide recall, MRR, nDCG, statistical confidence interval, universal hallucination rate, or production SLA is claimed. Citation support is not semantic entailment. The corpus is small and fixed; broaden it and obtain independent human review before a real pilot.

## Current publication verification

The local publication run passed **230 Python tests** and **32 UI-state tests**, with one existing TestClient deprecation warning. A current OSV query returned no advisories for the 34 matching pinned versions; that is a point-in-time lookup, not proof of security. See [publication evidence](evidence/publication-checks-2026-09-28.json) for exact scope.

The recorded demo includes a fresh actual-model quick evaluation: **3/3 automated cases passed, zero human reviews recorded**. Its 38 media/workflow checks verify the video and demonstrated scenario; they are not 38 independent model-accuracy cases. The full historical 21-case corpus was not rerun for documentation publication.

## Reproduce

```powershell
# Model-independent checks; do not alter the normal demo store.
.\.venv\Scripts\python.exe -m pytest -q --junitxml=artifacts/repository-tests.xml
node --test tests/ui_state.test.mjs
.\.venv\Scripts\python.exe -m scripts.repository_check

# Actual installed models; sequential, isolated store; may take many minutes.
.\.venv\Scripts\python.exe -m scripts.e2e_audit --output public-corpus-new-run.json

# Isolated quick Quality lab run.
.\.venv\Scripts\python.exe -m scripts.phase3_reaudit_live --isolated --suite quick --output quality-new-run.json
```

The public runner creates a retained store under LocalAppData/EnterpriseCopilotAudit. Its passwords, raw outputs, machine paths, and databases remain private. Corpus refresh and targeted/resume options are documented in the [corpus guide](../evaluation/audit/README.md). Advanced live scripts can create synthetic operational records; use disposable data, and do not run competing model workloads.

## Human review and acceptance

For each answer, compare all claims, exceptions, amounts and units against the original evidence; inspect citation location; verify no unauthorized content was used. For actions, inspect the exact user intent, tool, requester/reviewer permissions, SQL side effect, workflow state and replay behavior. Record correct/incorrect/uncertain judgments and a reason independently of the model judge.

Quality lab requires explicit correct human judgments for every case before the demo quality gate is reviewed-correct. Partial runs, uncertain/incorrect judgments and model errors cannot silently pass. Current historical evidence does not claim independent policy-owner signoff.

GitHub Actions runs only deterministic tests and publication checks on Windows. It never downloads model weights or declares a real-model benchmark passed. Historical regressions, faults and remaining performance/reliability concerns are preserved in the [end-to-end audit](E2E_AUDIT.md).
