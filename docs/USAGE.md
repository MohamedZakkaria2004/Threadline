# Demonstrate the working system

Start with a seeded store and **Local models ready**. Policies and people in this demo are fictional. Use generated credentials from your own data directory. The [video](https://github.com/MohamedZakkaria2004/Threadline/releases/tag/v0.3.1) condenses real model waits; allow more time in a live walkthrough.

## Employee: trusted knowledge and trackable requests

1. Sign in as `employee`. Ask: **How many working days of annual leave do permanent employees receive?**
2. Verify **25 working days** and open the `annual_leave.md` citation. Inspect Paragraph 2 in the original indexed source.
3. Ask **Who approves it?** in the same conversation. The source says the line manager. Reopen the conversation from the sidebar to show persistence.
4. Ask **Who is the current CEO of Meridian Telecom?** in a new conversation. The corpus does not contain the answer; expect insufficient evidence.
5. Ask **What is the Operations leadership contingency reserve?** Employee must not receive the restricted amount or source.
6. Switch to **Actions** or **Operations → New action**: **Create a support ticket for my monitor flickering during meetings.** Inspect the real saved ticket; try Start work, Resolve, and Reopen.
7. Submit **Request access to the network planning workspace for my project.** Inspect the tool trace and `waiting_approval` state. No ticket or permission change occurs before review.

## Admin: complete the same governed workflow

1. Sign out, then sign in as `admin`. Open **Operations → Approvals**.
2. Inspect the Employee's exact request, risk reason, and proposed action. Enter a decision reason and choose **Approve & create ticket**, or reject it.
3. An approval creates one **access-review ticket**; rejection creates none. Neither path changes the Employee role or grants workspace access.
4. Sign back in as Employee. Refresh Operations or reopen the saved conversation. Confirm the decision, resulting ticket, and current workflow state agree.

The default Manager is in Operations and cannot review the IT Employee's request. Admin provides the standard cross-department demonstration. No account may review its own request.

## Manager: scoped decision support

1. Sign in as `manager`. Ask **What is the Operations leadership contingency reserve?** Verify **AED 250,000** against the fictional `leadership_reserve.md` source.
2. In Actions, request **Generate a report on the Operations leadership contingency reserve and its approval requirements.**
3. Open the report. Verify the reserve and written approval by the Operations director and Finance, inspect citations, and download Markdown.
4. Explain that the service-desk snapshot counts the Manager's own tickets at generation time. Reports and conversations remain private to their creator, including against another administrator.

Managers can also review another eligible user in their own department. The standard seed has no Operations Employee; this boundary is exercised with controlled test fixtures rather than a misleading cross-department demo.

## Admin: knowledge foundation and platform oversight

| Screen | Action | What to verify |
|---|---|---|
| Document library | Upload PDF, DOCX, TXT or MD; select department and visibility | Ready status only after full indexing; source scope is correct |
| Document library | Select a previous document under Version replacement and upload updated text | New version becomes current only after success; old source remains historical |
| Insights → Overview | Select Platform aggregates | Counts/latency/outcomes without other users' conversation text |
| Quality lab | Start quick (3 cases) or full (8 cases) evaluation | Actual local-model results, expected evidence, structural and semantic checks |
| Quality lab | Inspect full source and record an explicit correctness judgment | Human judgment remains distinct from automated scores |
| Prompts | Inspect active `v4` and prior templates | Version and SHA-256 fingerprints; read-only registry |
| Business case | Compare scenarios; edit adoption and recalculate | Illustrative assumptions, negative ROI and no-payback cases |

Quality lab uses unchanged seeded `annual_leave.md`, `procurement.md`, and `travel_expenses.md`. It shares the model-work lock; other model requests are busy while it runs. **Stop after current case** preserves completed cases and does not interrupt inference mid-case. Export JSON only after reviewing it for sensitive local information.

## Honest demonstration boundaries

Knowledge mode cannot write operational artifacts. Actions mode supports one explicit registered tool per request. Email, external ticketing, permission grants, arbitrary code/SQL and autonomous task chains are unsupported. Refresh Operations to see new decisions; no push notification service is present. The hero's interactive walkthrough is explicitly illustrative; authenticated workflows use the real backend.
