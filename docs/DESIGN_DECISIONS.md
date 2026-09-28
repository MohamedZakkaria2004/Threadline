# Design decisions

The goal is a complete, inspectable enterprise AI prototype with modest setup effort. These decisions keep the demonstrated control path understandable while exposing the trade-offs a real pilot would need to address.

| Decision | Rationale | Trade-off / next boundary |
|---|---|---|
| Local Ollama with Qwen and nomic | Demonstrate generation and embeddings without hosted inference keys; keep application model traffic local | Hardware-sensitive latency; models still need download, memory and license review |
| FastAPI + direct HTML/CSS/JS | One app serves authenticated UI and API; no frontend build server or framework dependency | Manual UI state handling requires explicit stale-response and account-switch tests |
| SQLite for authoritative state | SQL transactions make actions, state and audits inspectable and atomic | Single-machine storage, no distributed availability or tenant isolation |
| Embedded Qdrant | Real vector retrieval without operating another server | One process owns the store; scale-out requires a different deployment |
| Canonical SQL evidence | Vector payloads can be stale/corrupt; source and access truth remain in one controlled representation | Cross-store integrity checks and staged publication add logic |
| Scoped retrieval before generation | Unauthorized passages should never enter the request's model context | Permission mapping and revocation timing require tests beyond UI hiding |
| Strict structured outputs and deterministic guards | A model proposal cannot invent tools or authorize writes | One explicit supported tool per request; no open-ended autonomous planning |
| Independent approval for sensitive work | Demonstrate separation of duties and accountable decisions | Human review adds waiting; an eligible reviewer must exist |
| Local service desk and Markdown briefings | Produce real saved outputs without paid integrations or external side effects | Does not replace ServiceNow, Jira, identity administration or long-form analytics |
| Versioned files for prompts | Small, reviewable change history and reproducible fingerprints | Read-only registry, no prompt editing/deployment control plane |
| Fixed gold fixtures + semantic and human checks | Make expected evidence explicit and avoid keyword-only confidence | Same-model judgment is correlated/fallible; independent domain review remains necessary |
| Transactional writes + request replay protection | Preserve state/output agreement through retry and failure | Distributed connector idempotency is not solved by local transactions |
| Assumption-based ROI calculator | Explain business value with transparent arithmetic and negative scenarios | Capacity value is not measured productivity or cash savings |

No orchestration framework is required for the bounded agent: [service.py](../app/service.py) explicitly manages planning, policy, approval and execution. State, errors and trace records remain visible to reviewers.

The original portfolio effort envelope was three short phases. [Enterprise planning](ENTERPRISE_CASE.md) labels that estimate as a planning assumption rather than a timesheet. Later review, media and documentation work should not be represented as included measured effort.
