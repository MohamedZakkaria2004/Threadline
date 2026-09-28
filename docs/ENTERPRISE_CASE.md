# Threadline enterprise case and deployment roadmap

This is a completed local portfolio implementation for a fictional telecom company. Figures below are editable planning assumptions, not quotations, measured productivity benefits, or a claim that the single-process laptop app supports a shared enterprise deployment.

## Business problem and stakeholder decisions

Employees lose time locating policies, interpreting procedural rules, and moving a question into an operational request. Threadline links an answer to its evidence and can create a local ticket, save a cited briefing, or pause a sensitive request for review.

| Stakeholder | Responsibility | Demonstrated value | Decision before a pilot |
|---|---|---|---|
| Employees | Ask questions, inspect sources, rate usefulness | Evidence, follow-ups, private history, trackable requests | Is net time saved after waiting and verification? |
| HR/IT/Operations policy owners | Maintain documents and review edge cases | Versioned policies and exact source inspection | Which documents are authoritative and current? |
| Service-desk manager | Triage tickets and review scoped requests | Ticket lifecycle and recorded independent decisions | Which actions remain local versus connected to a real system? |
| Security/privacy owner | Approve identity and information boundaries | Server-side scope, approval checks, audit, local inference | Can proposed pilot identities and permissions be mapped accurately? |
| Platform owner | Operate models, recover storage, inspect errors | Health, metrics, trace IDs, test artifacts, prompt fingerprints | Are capacity, backup and recovery adequate for the intended users? |
| Sponsor | Own benefit assumptions and adoption | Scenario calculator, quality evidence, adoption measures | Does observed benefit justify the next increment? |

## Build versus buy

**Decision for this portfolio: build a small local solution using the already-installed models.** It exposes the complete ingestion, retrieval, generation, approval, state and measurement path without vendor integration setup or hosted-model charges. Python/FastAPI, SQLite, embedded Qdrant, Ollama and a plain browser interface are sufficient. The implementation avoids a separate orchestration service or hosted-model dependency.

For a real enterprise, compare a bought service desk/copilot product with a supported custom build using actual vendor quotations. Evaluate identity integration, document permission fidelity, data location, supported connectors, reliability, exportability and support responsibility. The prototype's zero additional software spend is not evidence that enterprise integration, model operations, support or staff time are free. No vendor price or model-redistribution entitlement is assumed.

## Estimated implementation and operating cost

The original compressed budget was **three phases of up to 3–4 hours each**, or **9–12 hours** of implementation/review effort. At an illustrative developer rate of **USD 50/hour**, that is **USD 450–600** in effort value. This is a planning envelope, not a timesheet or invoice. Existing hardware is assumed; incremental software/hosted-inference charges in this build are **USD 0**.

The interactive calculator uses a 12-hour / USD 600 base implementation estimate, two support hours per month at USD 50/hour, 100 W while serving inference, USD 0.15/kWh, and 90 seconds of inference per request. These are assumptions, not measured power consumption or a local tariff. The dashboard's separate generation-electricity estimate covers generation time only and must not be confused with the calculator's total monthly operating estimate.

## Expected value and ROI scenarios

Common assumptions: 25 employees, 2 candidate questions per working day, 20 working days per month, and USD 30/hour of employee capacity value. “Minutes saved” means **net time saved after inference wait, checking evidence and any review effort**. Unusable answers create no benefit; all attempted requests still incur assumed inference cost. Capacity value is not automatically a payroll saving.

| Scenario | Adoption | Usable answers | Net minutes saved | Capacity value/month | Operating cost/month | First-year modeled ROI | Payback |
|---|---:|---:|---:|---:|---:|---:|---|
| Conservative | 25% | 50% | 1 | $62.50 | $100.09 | −58.36% | No positive payback |
| Base | 50% | 70% | 3 | $525.00 | $100.19 | 249.56% | 1.41 months |
| Optimistic | 75% | 85% | 4 | $1,275.00 | $100.28 | 748.41% | 0.51 months |

The base case frees **17.5 hours/month**, with **USD 424.81/month** modeled net value after operating cost. First-year cost is **USD 1,802.25**; first-year net capacity value is **USD 4,497.75**. The conservative scenario loses value after support costs, showing why adoption and net time saved must be measured rather than assumed.

Formulas used in `app/business.py` and the interface:

- Monthly requests = employees × questions/day × working days × adoption.
- Hours freed = requests × usable-answer rate × net minutes saved ÷ 60.
- Capacity value = hours freed × employee hourly value.
- Electricity = requests × inference seconds ÷ 3600 × watts ÷ 1000 × USD/kWh.
- Monthly operating cost = electricity + support hours × developer hourly rate.
- First-year ROI (%) = 100 × (12 × monthly capacity value − implementation cost − 12 × operating cost) ÷ (implementation cost + 12 × operating cost).
- Payback = implementation cost ÷ positive monthly net value. Zero/negative net value has no positive payback; a zero cost denominator has undefined ROI.

The calculator also shows sequential compute demand against an eight-hour working day. Exceeding capacity produces a visible warning. This is only a throughput sanity check; it does not simulate arrival bursts, concurrency or queueing. Hardware purchase/depreciation, SSO, production integration, taxes and organizational change effort are excluded from these prototype scenarios.

## Responsible AI controls and remaining risks

| Risk | Current control | Residual risk / owner |
|---|---|---|
| Unsupported claims | Scoped evidence, exact quotes/numbers, abstention, bounded correction; benchmark v3 adds a local semantic judge and explicit human-review gate | The automated judge is fallible; policy owner reviews claims and exceptions on a held-out corpus |
| Prompt injection | Treat retrieved text/history as data; strict plans; deterministic tool registry | A small benchmark cannot establish general resistance; security owner expands adversarial cases |
| Unauthorized disclosure | Current sessions, department/role filtering, SQL evidence authority, publication-time reauthorization, private reports | Exported bytes cannot be recalled; platform/security owners govern endpoint and file access |
| Risky execution | Independent reviewer, immutable request binding, atomic and idempotent local writes | Approval creates a local ticket only; a future connector needs a new authorization design |
| Misleading quality metrics | Automated scores separated from reviewer judgments; explicit denominators and fixture hashes | Synthetic demo results do not estimate enterprise accuracy; sponsor sets a representative pilot dataset |
| Misleading value claims | Explicit assumptions, conservative case, net time saved, no-benefit cases | Claimed benefit must be observed and owned by the sponsor |
| Operational failure | Persisted state, restart recovery, no automatic side-effect replay, locks, failure tests, verified offline backup and restore rehearsal | One local process and filesystem are failure points; platform owner owns pilot hardening |

The demo uses fictional data and personas. It has no real permission-grant, payment, email or ticketing connector. The downloaded model remains local. Existing passwords/sessions are demonstration identity controls, not enterprise SSO.

The [operations and pilot runbook](OPERATIONS_RUNBOOK.md) now gives executable recovery procedures, a human-review rubric, manual retention guidance and an owner-by-owner identity/capacity/connector handoff. Installed model digests and prompt hashes accompany new evaluations. These are implemented portfolio improvements; organizational sign-off and SSO still require a separately scoped real pilot.

## Deployment roadmap

| Stage | Scope and owner | Exit criteria |
|---|---|---|
| Completed portfolio | One laptop, one process, synthetic policies; project owner | Core journeys, persisted evidence, regression tests, actual-model review and business artifacts complete |
| Short internal demonstration | Sponsor + policy owners; a small invited audience sees the local demo | Participants understand evidence/approval boundaries; questions and usability feedback recorded; no real sensitive uploads required |
| Optional limited pilot | Platform + security + department owner; separately scoped work | SSO/least-privilege identity plan, vetted corpus, source-owner sign-off, backup/restore rehearsal, representative quality/latency gates and support owner agreed before exposure |
| Optional enterprise integration | Platform + service-desk owners | External-system idempotency and approval semantics verified, load/capacity tested, retention and incident process agreed, phased rollout with rollback |

The latter stages are a roadmap, not additional work silently included in this 3–4 hour phase. Do not expose the current loopback demo directly to a network or infer approval for external connectors. Stop a rollout if answers lose source fidelity, permissions fail, or net task time is worse than the current process.

## Adoption and outcome KPIs

| KPI | Definition | Current evidence / pilot collection |
|---|---|---|
| Active adoption | Eligible users with a request in the window ÷ eligible invited users | Dashboard shows active/registered demo accounts; set a real invited-user denominator in a pilot |
| Useful-answer rate | Helpful ratings ÷ rated answers, with rating coverage reported | Per-answer feedback and counts; do not treat unrated answers as helpful |
| Answer correctness | Correct reviewer judgments ÷ determinate judgments, alongside review coverage and uncertainty | Quality lab records source comparison notes; use a held-out representative set before pilot claims |
| Unsafe-answer rate | Policy/security failures in independently reviewed cases ÷ reviewed cases | Separate pilot rubric; automated quote/number checks are only a proxy |
| Task completion | Requests that produce the intended artifact and valid final state ÷ eligible action attempts | Dashboard separates artifacts, no-artifact completions, waiting reviews, rejections and failures |
| Response latency | P50/P95 processing seconds, plus sample count | Persisted workflow times; human approval wait excluded; missing samples excluded |
| Approval turnaround | Decision timestamp − request timestamp | Available in approval records; review weekly during a pilot |
| Net time saved | Baseline task time − assisted time including waiting and source review | Observe matched tasks; this input is assumed in the calculator |
| Duplicate side effects | More than one artifact for the same authorized request | Target zero; replay/concurrent-decision tests and SQL uniqueness enforce the local contract |
| Cost per useful task | Full attributed operating cost ÷ useful completed tasks | Prototype generation-energy estimates are insufficient alone; include support/hardware/integration in a pilot |

Suggested pilot gates are **proposals**, not measured achievements: zero authorization/duplicate-action failures in the agreed acceptance suite; at least 90% correct determinate judgments on the agreed representative set with all safety-critical cases reviewed; and positive observed net time saved. Agree latency targets from actual hardware and workload before committing to them. No statistically defensible enterprise success rate is claimed from eight synthetic cases.

## Portfolio demonstration sequence

1. Employee asks a policy question, opens its evidence and leaves feedback.
2. Employee creates a routine ticket, then submits an access request; a different administrator reviews the exact request and creates only a review ticket.
3. Employee generates a cited briefing and inspects its SQL snapshot and source provenance.
4. Employee opens their Insights; administrator inspects platform totals and versioned prompts without reading others' conversation content.
5. Administrator runs the Quality lab, inspects a correct answer, abstention and threshold case, records explicit reviewer judgments, and exports the JSON evidence.
6. Explore conservative/base scenarios in Business case, explain every cost assumption, and discuss the optional pilot gates.
