# Enterprise business brief — completed portfolio

The complete [enterprise case, cost/ROI scenarios, deployment roadmap and adoption KPIs](ENTERPRISE_CASE.md) expands this brief. The application now includes scoped Insights, a local quality benchmark with separate reviewer judgments, answer feedback, prompt inspection and an interactive business-case calculator.

## Problem and intended value

Employees spend time finding policies across departments and asking colleagues for routine procedural guidance. Answers can be inconsistent, and ordinary document search often returns a file rather than the relevant passage. Threadline provides permission-aware answers linked to evidence, using local models and local storage.

The demonstration focuses on a fictional telecom organization with HR, IT, and Operations. Its synthetic policies let reviewers inspect known answers and restricted-document behavior without processing real employee or customer records.

## Stakeholders

| Stakeholder | Need | Demonstrated capability |
|---|---|---|
| Employees | Find accurate answers quickly | Chat, follow-ups, saved conversations, source links |
| Document owners | Maintain current authoritative guidance | Administrator upload, explicit replacement and document versions |
| Department managers | Access relevant restricted guidance | Department-aware leadership permissions |
| IT/platform team | Run and troubleshoot locally | Startup scripts, dependency lock, health endpoint, audit and failure records |
| Security/privacy reviewer | Check disclosure boundaries | Restricted retrieval, server-side roles, ownership checks, local storage |
| Business sponsor | Establish measurable value | Baseline questions and latency/quality evidence for a later pilot |

## Build versus buy decision

Build this small portfolio MVP using free components and already-installed models. It exposes the architecture and demonstrates custom evidence handling, access controls and working local approval workflows. The direct cost is developer effort and operation of existing hardware; there is no hosted inference subscription.

Buying an enterprise product may reduce integration, identity and operational work, but introduces product-specific licensing and deployment constraints. No vendor pricing claim is made here. A real procurement decision would compare integration effort, data residency, permission fidelity, support and total operating cost using actual quotations.

## Success measures

The system must return correct policy facts with valid source quotes, abstain when evidence is absent, prevent cross-department/leadership leaks, and preserve conversations and the index across restarts. The test set is a demonstration sample, not a statistical estimate of enterprise accuracy. The enterprise case formalizes pilot KPI definitions and cost/ROI assumptions in the enterprise case.

## Responsible use

All included policies and personas are fictional. The model cannot approve a request, send email or change permissions. The application can create local support tickets and cited reports; sensitive requests wait for a different authorized human. An approved access request creates a review ticket only. Answers remain subject to source review. Local inference reduces external data transfer, but does not remove the need for authorization, reliable source management or protection of the local machine.

## Operational enterprise value

Employees can move from a policy question to a trackable local request or a source-backed briefing. Service-desk owners can review the user's original problem, manage status, and see who approved a sensitive request. Managers review requests only in their department; administrators provide the demo's cross-department review path. The sponsor can inspect real workflow records and timings instead of a scripted chat response that merely claims work was done.

The current build-versus-buy choice remains a small local implementation: SQLite transactions, one bounded Qwen plan, and a local service desk avoid external licenses and integration setup. This demonstrates the workflow/control pattern; it does not replace an organization's identity provider or ticketing system. Before any future connector, the human decision and idempotency contract must be mapped to the external system's semantics.

Adoption measures: successful local task completion, approval turnaround, duplicate side effects (target zero), source-backed report rate, failed/abstained requests, and user-perceived response latency. A statistically meaningful quality score or enterprise ROI cannot be inferred from this small synthetic test corpus. The enterprise case provides explicit baseline assumptions, implementation/operating cost scenarios, modeled ROI, rollout stages and KPI definitions; Insights provides the available local measurements.
