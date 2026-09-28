# Limitations and future work

**Current status: a working prototype suitable for a supervised portfolio demonstration.** The historical engineering audit is PASS WITH ISSUES because hardware/host reliability limitations remain. Repository publication does not make the running service production-ready.

## Current limitations

| Area | Limitation | Practical implication |
|---|---|---|
| Runtime | One process, one embedded vector-store owner, serialized model work | Concurrent inference returns busy; no horizontal scale or high availability |
| Performance | CPU/memory-dependent inference; one historical unexplained process interruption | Keep the host awake, free RAM and supervise the demo; no uptime/SLA claim |
| Documents | English text extraction; upload/page/text/chunk limits; no OCR or complex-layout understanding | Scans and unsupported documents fail explicitly; larger corpora need new evaluation |
| Truthfulness | Quote/number checks and narrow numeric-conflict guard | Semantic misinterpretation can survive valid citations; human review remains necessary |
| Evaluation | Small fixed public/synthetic corpus; same-model semantic judge | No enterprise-wide accuracy or independent human signoff claim |
| Agents | One explicit local tool per request | No autonomous task chains, browsing, shell, email or real permission grants |
| Identity/security | Demo accounts, local HTTP, plaintext files, local mutable audit | Trusted-loopback use only; not enterprise identity, encryption or immutable audit |
| Operations | Manual refresh, no notification service or automatic business-action retries | Users refresh saved state; interrupted work is explicit and not replayed |
| Reports | Short owner-private briefings and personal SQL ticket snapshot | Not department analytics; exported files cannot be revoked |
| Portability | Windows setup tested | Linux/macOS packaging remains unvalidated |

## Prioritized roadmap

| Stage | Proposed work | Exit criterion / owner |
|---|---|---|
| Demonstration | Keep seeded fixtures and local models ready; explain source and action boundaries | Core journeys reproducible by reviewer; project owner |
| Quality expansion | Representative domain questions, nonnumeric conflicts, ambiguity, independent review | Agreed safety-critical cases pass and review coverage is explicit; policy/QA owners |
| Controlled internal pilot | SSO/least privilege, protected storage, supervised process, retention and recovery | Security/operations signoff and recovery/capacity rehearsal before exposure |
| Capacity | Background ingestion, supported shared vector service, queueing and workload tests | Measured latency/throughput targets on representative workload; platform owner |
| Connected workflows | Approved ITSM/identity connectors, external idempotency, scoped credentials | No duplicate or unauthorized remote side effects; service owners |
| Adoption | Task-time baseline, rated-answer coverage, approval turnaround and cost attribution | Positive observed net benefit including waiting/review; sponsor |

These are proposals, not hidden implemented features. No automatic rollout or public deployment is included. See the [enterprise case](ENTERPRISE_CASE.md) for stakeholders, build-versus-buy analysis, editable ROI assumptions and KPI definitions.
