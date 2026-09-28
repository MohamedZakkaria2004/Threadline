# Security, governance and responsible AI

The prototype demonstrates defense in depth for a **trusted local workstation**. It is not approved for public hosting or sensitive production records. Its controls are inspectable and tested; they do not guarantee universal security or model correctness.

## Controls and residual risk

| Concern | Implemented control | Remaining boundary |
|---|---|---|
| Identity | Unique salted PBKDF2-HMAC-SHA256 hashes; random first-run passwords; hashed session tokens; 8-hour expiry; logout invalidation; login throttling | Fixed demo accounts, no SSO/MFA/provisioning; local credential helper is plaintext |
| Browser/API | Loopback bind, Host validation, HttpOnly/SameSite=Strict cookie, unsafe-request origin/header checks, CSP and text-based rendering | Local HTTP cookie is not Secure; transport design must change before any network deployment |
| Knowledge disclosure | Current role/department filters before search; canonical SQL evidence; access rechecks at publication and historical view | Already delivered/downloaded content cannot be recalled |
| Ownership | Private conversations, detailed activity and reports; Admin receives aggregate insights/redacted audit | Local filesystem administrators can bypass application RBAC |
| Prompt injection | Evidence/history treated as data; strict schemas; deterministic intent/tool match; bounded registry | Cannot guarantee resistance to every adversarial document or semantic attack |
| Hallucination | Exact quote validation, number support, abstention, bounded correction, limited numeric-conflict guard | Non-numerical contradictions and subtle inference errors remain possible |
| Risky actions | Exact plan/digest, independent reviewer, request-time/current department checks | Approval creates local review work only; no external authorization is implied |
| Duplicate writes | Request idempotency, unique artifact/workflow constraint, transactional decisions, stale-update guards | A future external connector needs a new end-to-end contract |
| Audit integrity | Audit and business state commit together; scoped read view omits raw detail | Local SQL audit is not an immutable external compliance log |
| Data retention | Local stores, ignored runtime files, verified offline backup/restore and manual retention guidance | Plaintext storage/backups; no automated enterprise retention or DLP |
| Measurement integrity | Explicit denominators, fingerprints, separate human judgments, assumption-based ROI | Small synthetic/public corpus; no independent policy-owner signoff |

## Human authority and decision support

Threadline supports a decision; it does not become the policy owner or approval authority. Reports are drafts for source review. User-entered ticket facts remain separate from generated policy text. Knowledge mode has no write tool. Sensitive operational requests pause before side effects and require a different eligible reviewer. The access-review workflow never changes RBAC.

Admin is a platform role, not a universal reader of conversations. Managers review only eligible department requests. Current permissions are reloaded instead of trusting a model plan, frontend flag, or stale session payload. See the [complete permission matrix](ROLES_AND_PERMISSIONS.md).

## Data and privacy

Application model traffic uses loopback Ollama. No hosted-model keys are required, and UI fonts/scripts load locally. Dependency/model downloads and optional source/advisory checks use the internet. “Local” does not mean encrypted, anonymous, or automatically compliant.

Use public or fictional documents. Runtime credentials, databases, vectors, logs, backups, raw evaluations and private exports must stay outside Git and cloud-synchronized folders. A source-control hygiene check scans current working/index contents, known credential patterns, local links and source hashes; it does not prove the absence of every possible secret or scan all Git history.

## Before a real pilot

Assign security, policy, data, and operations owners. Integrate enterprise identity; define transport/storage protection; review model terms; verify source permission mapping; expand adversarial and domain evaluations; obtain independent human source approval; test capacity, recovery, retention and incident response. External action integrations need separately reviewed permissions, review semantics and idempotency. These are roadmap items, not implemented claims.

Use the [security reporting policy](../SECURITY.md) for findings. Do not include passwords, private documents, or usable exploit credentials in public issues. Operational procedures are in the [runbook](OPERATIONS_RUNBOOK.md).
