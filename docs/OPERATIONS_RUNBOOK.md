# Local operation, recovery and pilot handoff

Threadline remains a one-laptop portfolio application. These procedures make that build reviewable and recoverable. Enterprise identity and external connectors are a separately scoped pilot, not prerequisites for demonstrating the local application.

If a query reports an incomplete index, do not interpret it as a missing policy. Restore a verified offline backup, or sign in as admin and re-upload the original affected file. Identical content repairs the index through a new version while preserving the previous document until publication succeeds. Re-upload all affected files if an entire collection was lost. An upload whose administrator loses permission during indexing is rejected before publication.

The public-corpus audit is reproducible from `evaluation/audit/README.md`. On this 16 GB laptop, a concurrent inference/test run observed 98% memory use and a Windows WMI error during test-report creation. Finish inference, unload idle test models if necessary (`ollama stop <model>`), then run regression tests sequentially. Installed models remain available and reload on the next request. No service restart or model deletion is required.

## Starting and stopping

Use `start.ps1` from the project directory. Use `stop.ps1` to stop only the recorded Threadline process, or Ctrl+C in its foreground terminal. Wait for any active request or benchmark to finish before stopping. Keep the listener on loopback. `/api/health` reports readiness and a source/prompt build fingerprint captured when the process starts; compare it after source updates. Python changes require a restart.

The local inference slot serializes ingestion, generation and evaluations. A concurrent request receives HTTP 409 and an actionable busy message, rather than creating a second side effect or hidden queue. A benchmark case now includes answer generation plus semantic assessment; its latency must not be presented as ordinary chat latency. Inspect sample count alongside P50/P95. Stop starting benchmarks during a demonstration of employee actions.

## Backup and restore

Backups contain policies, conversations, users, password hashes and the local demo credential file. Keep them under the same user's local profile, outside source control and cloud-synchronized folders. They are **not encrypted archives**. Do not share them as portfolio artifacts; share the redacted verification report instead. The supplied script uses the installed Qdrant locking dependency and Python SQLite; no service or model download is needed.

1. Wait until health is ready, then stop Threadline.
2. Run `.\.venv\Scripts\python.exe -m scripts.backup create`. This creates a unique directory under `%LOCALAPPDATA%\EnterpriseCopilotBackups` by default. It refuses a running vector store, interrupted work, an existing destination, or a destination inside active data. SQL is snapshotted with SQLite's backup API while writes are locked; vectors and other local files are copied under the vector-store lock.
3. Run `.\.venv\Scripts\python.exe -m scripts.backup verify --snapshot "<snapshot path>"`. Every file must match the SHA-256 manifest; SQL integrity and foreign keys must pass. The manifest detects accidental damage, not tampering by someone who can also replace the manifest.
4. Start Threadline again. Record the snapshot date and successful verification in your local operations notes.

For a restore rehearsal, run `.\.venv\Scripts\python.exe -m scripts.backup restore --snapshot "<snapshot path>" --destination "<new empty path>"`. The destination must **not exist**; existing data is never replaced. The copied payload is rechecked, and all restored login sessions are invalidated. Open the restored database/vector store and check document/chunk counts, vector-to-SQL IDs, policy retrieval, tickets/reports and pending approval consistency before choosing it as the active data directory. Keep the original store for rollback. If a restore fails, leave the partial target alone for diagnosis and use a different new directory after correcting the cause.

To switch to a verified restore, stop Threadline, set `COPILOT_DATA_DIR` to the restored path in the launching shell, and run `start.ps1`. Sign in again using the restored local credential file. Unset that variable to return to the original default store. The rehearsal report does not mean the active store was replaced.

Suggested local cadence: snapshot before schema/model changes and after a demonstration that creates useful records. Retain the latest three successful local snapshots as a manual policy; no automatic deletion is enabled. Agree actual retention, encryption and recovery targets with a pilot owner before using real internal data.

## Meaning checks and human review

Quality benchmark v3 requires structural evidence checks **and** a separate local-Qwen judgment of every claim against canonical SQL policy text. The judge receives the expected behavior and authoritative policies, not candidate-supplied evidence as authority. Negation, role swaps, numeric boundaries, scope and invented abstentions are challenge cases. Missing/invalid output fails the run; uncertain or unsupported judgments fail the case. Prompt hashes and installed Ollama model digests are recorded and checked throughout the run. Old scores remain historical and are not relabeled as semantically checked.

The same local model can make correlated mistakes in generation and grading. Its judgment is automated evidence, not independent human approval. A run with all automated checks passing remains **needs human review** until every case has an explicit correct review; any incorrect/uncertain judgment blocks sign-off. Failed automated checks cannot be overridden by marking the answer correct. This gate describes the demo benchmark, not authorization for enterprise deployment.

A policy owner should review a held-out set they have not used to tune prompts. Include at least these scenario types: positive fact lookup, valid paraphrase, negation, swapped responsibilities, exact/above/below approval boundaries, mandatory receipt exceptions, excluded employee groups, genuinely missing evidence, misleading user premises and attempted evaluator manipulation. For each case:

- Compare **every substantive claim**, its conditions and units with the current source; a correct quotation beside an incorrect conclusion fails.
- Mark **incorrect** for any contradicted or invented claim; mark **uncertain** for ambiguous policy or incomplete evidence; record which clause determines the verdict.
- Review abstentions too: a refusal that also invents a name or number is not safe abstention.
- Record correct/incorrect/uncertain, source version and a short reason in Quality lab; export the run. Report review coverage and uncertainty alongside correctness. Do not fill human-review counters using automated scripts.

The included challenge set is a regression fixture, not an independent held-out enterprise dataset. Actual policy-owner review cannot be substituted by this coding agent.

## Pilot decisions and ownership

| Area | Portfolio control | Pilot handoff / owner |
|---|---|---|
| Identity | Salted password hashes, expiring sessions, current database roles, loopback-only access | Security owner selects organization SSO, maps employee/manager/admin roles and departments, proves deprovisioning and separation of duties before network access. No real identity provider is configured here. |
| Source ownership | Versioned SQL documents, permission filtering, fixture hashes | HR/IT/Operations owners approve authoritative documents, dates, ACLs, review intervals and ambiguity resolution. |
| Recovery | Verified offline SQL/vector snapshots; restore to a fresh directory; sessions invalidated | Platform owner defines RPO/RTO, protected storage, retention and restore rehearsal cadence. Proposed pilot targets require agreement, not inferred promises. |
| Capacity | One inference slot; visible busy responses; observed latency and sample counts | Platform owner measures a representative workload and concurrent-user arrival pattern on intended hardware; choose a queue or dedicated model service only if needed. Do not infer an SLA from eight cases. |
| Data retention | User-owned local store; no automatic deletion | Privacy/data owner sets conversation, report, ticket, audit and backup retention together; exported reports cannot be recalled. |
| External actions | Local tickets/reports only; independent approval for risky requests | Service-desk/security owners define connector-specific permissions, idempotency, audit, rollback and approval-to-action binding. No credentials or connectors are added during this work. |
| Quality and value | Automated checks plus explicit reviewer judgments; assumption-based cost calculator | Policy owner signs off the held-out set; sponsor measures baseline versus assisted task time including waiting/review, and agrees acceptable error/latency rates. |

Before a real pilot, owners must resolve the above decisions and record sign-off. For local portfolio demonstration and further development, the verification report provides the current technical readiness decision.
