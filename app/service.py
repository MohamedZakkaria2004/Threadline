"""One local tool per request; model plans never authorize side effects."""
import hashlib
import json
import re
import time
from .llm import prompt
from .schemas import ToolPlan
from .storage import dump, now, uid

PREFIX = r"^(?:(?:please|can you|could you|would you|i want you to|i need you to)\s+)*"
INTENTS = {
    "create_ticket": r"(?:create|open|log|raise|submit)\s+(?:(?:a|an|new|support|helpdesk|service|high|low|normal|critical|priority|urgent)\s+)*ticket\b",
    "generate_report": r"(?:create|write|generate|prepare|draft)\s+(?:(?:a|an|new|policy|summary)\s+)*(?:report|briefing)\b",
    "request_access": r"(?:request|grant|revoke|change)\s+(?:(?:my|me|a|an|new|admin|administrator|elevated|temporary)\s+)*(?:access|permission|permissions|privileges)\b",
}
SENSITIVE = re.compile(r"\b(access|permissions?|privileges?|admin\w*|delet\w*|export\w*|payments?|transfers?|refund\w*|credentials?|password\w*|production|payroll|confidential|sensitive|security|phishing|breach|bank|customer data|personal data)\b", re.I)


def explicit_intent(text):
    for tool, pattern in INTENTS.items():
        if re.match(PREFIX + pattern, text.strip(), re.I):
            return tool
    return "answer"


def approval_reason(plan, original_request):
    if plan.tool == "request_access":
        return "Access requests need independent human review. Approval creates a review ticket; permissions stay unchanged."
    if plan.tool == "create_ticket":
        if plan.priority in {"high", "critical"}:
            return "High and critical priority tickets need independent human review."
        if SENSITIVE.search(original_request + " " + plan.title + " " + plan.description):
            return "This ticket concerns a sensitive operation and needs independent human review."
    return None


def digest(payload):
    return hashlib.sha256(payload.encode()).hexdigest()


class Copilot:
    def __init__(self, settings, store, llm, knowledge, chat):
        self.settings, self.store, self.llm = settings, store, llm
        self.knowledge, self.knowledge_chat = knowledge, chat

    @staticmethod
    def step(name, detail):
        return {"name": name, "detail": detail, "at": now()}

    def fresh_user(self, user_id, conn=None):
        sql = "SELECT id,username,name,role,department FROM users WHERE id=?"
        row = conn.execute(sql, (user_id,)).fetchone() if conn else self.store.one(sql, (user_id,))
        if not row:
            raise PermissionError("Account is no longer available.")
        return dict(row)

    @staticmethod
    def can_review(row, user):
        return row["requester_id"] != user["id"] and (user["role"] == "admin" or (
            user["role"] == "manager" and row["department"] == user["department"] == row["requester_department"]))

    @staticmethod
    def can_see_ticket(row, user):
        return row["user_id"] == user["id"] or user["role"] == "admin" or (
            user["role"] == "manager" and row["department"] == user["department"] == row["requester_department"])

    def chat(self, request, user):
        if not request.message.strip():
            raise ValueError("Enter a request containing text.")
        prior = self.store.one("SELECT * FROM workflows WHERE user_id=? AND request_id=?", (user["id"], request.request_id))
        if prior:
            if prior["mode"] != request.mode or prior["input"] != request.message or (request.conversation_id and request.conversation_id != prior["conversation_id"]):
                raise ValueError("This request ID belongs to a different request. Use a new request ID.")
            if prior["status"] not in {"completed", "waiting_approval", "rejected"}:
                raise ValueError("The previous request did not complete. Review Operations and use a new request ID to retry.")
            return self.knowledge_chat.safe_result(json.loads(prior["result"]), user)
        conversation_id = request.conversation_id or uid()
        if request.conversation_id and not self.store.one("SELECT id FROM conversations WHERE id=? AND user_id=?", (conversation_id, user["id"])):
            raise PermissionError("Conversation not found.")
        workflow_id, started = uid(), time.perf_counter()
        steps = [self.step("Authorize", "Bound to your account and one explicit local action.")]
        with self.store.connect() as conn:
            if not request.conversation_id:
                conn.execute("INSERT INTO conversations VALUES (?,?,?,?)", (conversation_id, user["id"], request.message[:70], now()))
            conn.execute("INSERT INTO workflows(id,request_id,conversation_id,user_id,input,status,steps,created_at,updated_at,mode) VALUES (?,?,?,?,?,'running',?,?,?,'agent')", (workflow_id, request.request_id, conversation_id, user["id"], request.message, dump(steps), now(), now()))
            conn.execute("INSERT INTO messages VALUES (?,?,?,?,?,?)", (uid(), conversation_id, "user", request.message, "{}", now()))
            self.store.audit(user["id"], "workflow.started", workflow_id, {"mode": "agent"}, conn=conn)
        try:
            intent = explicit_intent(request.message)
            plan = ToolPlan(tool="answer", title=request.message[:120], description=request.message[:1200], priority="normal")
            planner_hash = None
            if intent != "answer":
                instruction = prompt("planner", self.settings.prompt_version)
                planner_hash = digest(instruction)
                plan = self.llm.structured([{"role": "system", "content": instruction}, {"role": "user", "content": request.message}], ToolPlan, "planner", user["id"], workflow_id)
                if plan.tool != intent or not plan.title.strip() or not plan.description.strip():
                    raise ValueError("The planner could not match this action. Use an explicit request such as 'Create a support ticket for my broken monitor'.")
                # Original user details, not model-created operational facts.
                # ToolPlan caps description at 1200, so long write requests fail closed.
                if len(request.message) > 1200:
                    raise ValueError("Keep action requests within 1200 characters.")
                plan.description = request.message
                subject = re.sub(PREFIX + INTENTS[intent], '', request.message.strip(), count=1, flags=re.I).strip(' .:')
                plan.title = re.sub(r'^(?:for|on|about|to)\s+', '', subject, flags=re.I)[:120] or request.message[:120]
                plan.priority = "critical" if re.search(r"\bcritical\b", request.message, re.I) else "high" if re.search(r"\b(high|urgent|emergency)\b", request.message, re.I) else "low" if re.search(r"\blow\b", request.message, re.I) else "normal"
                steps.append(self.step("Plan", f"Local model selected {intent}; code verified intent and risk policy."))
            else:
                steps.append(self.step("Read only", "No explicit supported action; no write tool authorized."))
            payload = dump(plan.model_dump())
            self.store.run("UPDATE workflows SET tool=?,payload=?,steps=?,updated_at=? WHERE id=?", (plan.tool, payload, dump(steps), now(), workflow_id))
            user = self.fresh_user(user["id"])
            reason = approval_reason(plan, request.message)
            if plan.tool == "generate_report":
                result = self.knowledge_chat.answer(request.message, user, workflow_id)
                steps.append(self.step("Retrieve and verify", "Retrieved permitted evidence and checked quotes and numerical support."))
            elif plan.tool == "answer":
                result = {"answer": "Actions supports one explicit request at a time: 'Create a support ticket for…', 'Generate a report on…', or 'Request access to…'. Use Knowledge for policy questions. No action was taken.", "citations": [], "insufficient_evidence": False, "action_unavailable": True}
            else:
                result = {"answer": "", "citations": [], "insufficient_evidence": False}
            result.update({"workflow_id": workflow_id, "conversation_id": conversation_id, "message_id": uid(), "status": "completed", "tool": plan.tool, "model": self.settings.model, "prompt_version": self.settings.prompt_version, "planner_sha256": planner_hash})
            # Side effects, terminal state, message and audit share a single commit.
            with self.store.connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                user = self.fresh_user(user["id"], conn)
                if reason:
                    available = conn.execute("SELECT id,role,department FROM users WHERE id<>? AND (role='admin' OR (role='manager' AND department=?))", (user["id"], user["department"])).fetchone()
                    if not available:
                        raise ValueError("No independent reviewer is configured for your account. In this demo, submit the request as Employee or Manager and review it as Admin.")
                    approval_id = uid()
                    conn.execute("INSERT INTO approvals(id,workflow_id,requester_id,reason,payload,created_at,department,payload_hash) VALUES (?,?,?,?,?,?,?,?)", (approval_id, workflow_id, user["id"], reason, payload, now(), user["department"], digest(payload)))
                    result.update(status="waiting_approval", approval_id=approval_id, answer="Waiting for human review. " + reason)
                    steps.append(self.step("Await approval", reason))
                    self.store.audit(user["id"], "approval.requested", approval_id, {"workflow_id": workflow_id}, conn=conn)
                elif plan.tool == "create_ticket":
                    ticket = self.create_ticket(conn, workflow_id, user, plan)
                    result.update(ticket=ticket, answer=f"Created local support ticket {ticket['id']}: {ticket['title']}. Priority: {ticket['priority']}.")
                    steps.append(self.step("Create ticket", ticket["id"] + " saved in the local service desk."))
                elif plan.tool == "generate_report":
                    if self.knowledge_chat.safe_result(result, user).get("access_changed"):
                        raise PermissionError("Source access changed during generation. Submit a new request.")
                    if result["insufficient_evidence"]:
                        result["answer"] = "No report was saved because supporting evidence was insufficient. " + result["answer"]
                        steps.append(self.step("No report saved", "A policy conclusion could not be supported."))
                    else:
                        report = self.create_report(conn, workflow_id, user, plan.title, result)
                        result["report"] = report
                        result["answer"] = f"Report saved: {report['title']}.\n\n" + result["answer"]
                        steps.append(self.step("Save report", report["id"] + " saved with sources and your own SQL ticket counts."))
                result["steps"] = steps + [self.step("Waiting" if reason else "Complete", result["status"].replace("_", " "))]
                result["latency_ms"] = round((time.perf_counter() - started) * 1000)
                self.persist_result(conn, result)
                self.store.audit(user["id"], "workflow." + result["status"], workflow_id, {"tool": plan.tool, "latency_ms": result["latency_ms"]}, conn=conn)
            return result
        except Exception as exc:
            with self.store.connect() as conn:
                failure = {"status": "failed", "workflow_id": workflow_id, "conversation_id": conversation_id, "answer": "This action failed. No ticket, report, or approval request was created. Review Operations before retrying.", "steps": steps + [self.step("Failed", type(exc).__name__)]}
                conn.execute("UPDATE workflows SET status='failed',result=?,steps=?,updated_at=? WHERE id=?", (dump(failure), dump(failure["steps"]), now(), workflow_id))
                conn.execute("INSERT INTO messages VALUES (?,?,?,?,?,?)", (uid(), conversation_id, "assistant", failure["answer"], dump(failure), now()))
                self.store.audit(user["id"], "workflow.failed", workflow_id, {"error_type": type(exc).__name__}, conn=conn)
            raise

    def persist_result(self, conn, result, update_message=False):
        if update_message:
            changed = conn.execute("UPDATE messages SET content=?,metadata=? WHERE id=? AND conversation_id=?", (result["answer"], dump(result), result["message_id"], result["conversation_id"])).rowcount
            if changed != 1:
                raise ValueError("Saved workflow message missing; the decision was not applied.")
        else:
            conn.execute("INSERT INTO messages VALUES (?,?,?,?,?,?)", (result["message_id"], result["conversation_id"], "assistant", result["answer"], dump(result), now()))
        conn.execute("UPDATE workflows SET status=?,result=?,steps=?,updated_at=? WHERE id=?", (result["status"], dump(result), dump(result["steps"]), now(), result["workflow_id"]))

    def create_ticket(self, conn, workflow_id, user, plan):
        ticket = {"id": "TKT-" + uid()[:8].upper(), "workflow_id": workflow_id, "user_id": user["id"], "title": plan.title, "description": plan.description, "priority": plan.priority, "status": "open", "category": "access_review" if plan.tool == "request_access" else "support", "created_at": now(), "department": user["department"]}
        conn.execute("INSERT INTO tickets(id,workflow_id,user_id,title,description,priority,status,category,created_at,department,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (*ticket.values(), ticket["created_at"]))
        self.store.audit(user["id"], "ticket.created", ticket["id"], {"workflow_id": workflow_id, "category": ticket["category"]}, conn=conn)
        return ticket

    def create_report(self, conn, workflow_id, user, title, result):
        report = {"id": "RPT-" + uid()[:8].upper(), "title": title, "created_at": now()}
        counts = [dict(row) for row in conn.execute("SELECT status,priority,COUNT(*) AS count FROM tickets WHERE user_id=? GROUP BY status,priority ORDER BY status,priority", (user["id"],))]
        lines = [f"# {title}", "", f"Generated: {report['created_at']}", f"Model: {self.settings.model} | Prompt: {self.settings.prompt_version}", "", "## Evidence-based briefing", "", result["answer"], "", "## Your service desk snapshot", "", "Only your own local tickets, counted by SQL at generation time.", "", "| Status | Priority | Tickets |", "| --- | --- | ---: |"]
        lines += [f"| {r['status']} | {r['priority']} | {r['count']} |" for r in counts] or ["| No tickets | — | 0 |"]
        lines += ["", "## Sources", ""]
        for c in result["citations"]:
            lines += [f"- {c['title']} ({c['filename']}, version {c['version']}, {c['locator']}): {c['quote']}"]
        lines += ["", "AI-generated draft for human review. Quote and number checks do not prove semantic correctness."]
        metadata = {"citations": result["citations"], "answer": result["answer"], "ticket_counts": counts, "model": self.settings.model, "prompt_version": self.settings.prompt_version, "prompt_sha256": result.get("prompt_sha256")}
        conn.execute("INSERT INTO reports(id,workflow_id,user_id,title,markdown,created_at,metadata) VALUES (?,?,?,?,?,?,?)", (report["id"], workflow_id, user["id"], title, "\n".join(lines), report["created_at"], dump(metadata)))
        self.store.audit(user["id"], "report.created", report["id"], {"workflow_id": workflow_id, "citations": len(result["citations"])}, conn=conn)
        return report

    def overview(self, user):
        tickets = self.store.all("SELECT t.*,u.name AS requester,u.department AS requester_department FROM tickets t JOIN users u ON u.id=t.user_id ORDER BY t.created_at DESC")
        tickets = [t for t in tickets if self.can_see_ticket(t, user)]
        approvals = self.store.all("SELECT a.*,u.name AS requester,u.department AS requester_department,w.input FROM approvals a JOIN users u ON u.id=a.requester_id JOIN workflows w ON w.id=a.workflow_id ORDER BY a.created_at DESC")
        visible_approvals = []
        for a in approvals:
            reviewable = self.can_review(a, user)
            if a["requester_id"] == user["id"] or reviewable:
                a["can_review"] = reviewable and a["status"] == "pending"
                a["plan"] = json.loads(a.pop("payload"))
                a.pop("payload_hash")
                visible_approvals.append(a)
        reports = []
        for r in self.store.all("SELECT id,title,created_at,metadata FROM reports WHERE user_id=? ORDER BY created_at DESC", (user["id"],)):
            safe = self.knowledge_chat.safe_result(json.loads(r.pop("metadata")), user)
            r["available"] = bool(safe.get("citations")) and not safe.get("access_changed", False)
            r["historical_sources"] = safe.get("historical_sources", False)
            if not r["available"]:
                r["title"] = "Report unavailable: source evidence cannot be authorized"
            reports.append(r)
        workflows = self.store.all("SELECT id,input,tool,status,steps,created_at,updated_at FROM workflows WHERE user_id=? AND mode='agent' ORDER BY created_at DESC LIMIT 100", (user["id"],))
        for w in workflows:
            w["steps"] = json.loads(w["steps"])
        return {"tickets": tickets, "approvals": visible_approvals, "reports": reports, "workflows": workflows}

    def report(self, report_id, user):
        row = self.store.one("SELECT * FROM reports WHERE id=? AND user_id=?", (report_id, user["id"]))
        if not row:
            raise PermissionError("Report not found.")
        metadata = self.knowledge_chat.safe_result(json.loads(row["metadata"]), user)
        if metadata.get("access_changed") or not metadata.get("citations"):
            raise PermissionError("You can no longer access a source in this report. Generate a new report from current evidence.")
        row["metadata"] = metadata
        if metadata.get("historical_sources"):
            row["markdown"] = "> Historical report: a source has been superseded. Generate a new report for current policy.\n\n" + row["markdown"]
        return row

    def decide(self, approval_id, decision, user):
        if len(decision.reason.strip()) < 3:
            raise ValueError("Give a meaningful reason for the decision.")
        with self.store.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            user = self.fresh_user(user["id"], conn)
            row = conn.execute("SELECT a.*,u.department AS requester_department FROM approvals a JOIN users u ON u.id=a.requester_id WHERE a.id=?", (approval_id,)).fetchone()
            if not row or not self.can_review(row, user):
                raise PermissionError("Review requires a different administrator or a manager in the requester's department.")
            workflow = conn.execute("SELECT * FROM workflows WHERE id=?", (row["workflow_id"],)).fetchone()
            expected = "approved" if decision.decision == "approve" else "rejected"
            if row["status"] != "pending":
                if row["status"] == expected and row["decided_by"] == user["id"] and row["decision_note"] == decision.reason:
                    return json.loads(workflow["result"])
                raise ValueError("This request has already been decided. Refresh Operations.")
            if workflow["status"] != "waiting_approval" or row["payload_hash"] != digest(row["payload"]) or row["payload"] != workflow["payload"]:
                raise ValueError("The saved approval no longer matches the workflow. Nothing was executed.")
            plan = ToolPlan.model_validate_json(row["payload"])
            if plan.tool not in {"create_ticket", "request_access"} or plan.tool != explicit_intent(workflow["input"]) or plan.description != workflow["input"]:
                raise ValueError("Unsupported or altered approval action.")
            result = json.loads(workflow["result"])
            if decision.decision == "approve":
                requester = self.fresh_user(row["requester_id"], conn)
                if requester["department"] != row["department"]:
                    raise ValueError("The requester changed department. Reject this request and ask them to submit a new one.")
                ticket = self.create_ticket(conn, row["workflow_id"], requester, plan)
                result.update(ticket=ticket, status="completed", answer=f"Human review completed. Created local ticket {ticket['id']}: {ticket['title']}." + (" This is an access-review ticket; no permissions were changed." if plan.tool == "request_access" else ""))
            else:
                result.update(status="rejected", answer="The request was rejected. Reason: " + decision.reason)
            result["steps"] = json.loads(workflow["steps"]) + [self.step("Human decision", f"{expected.capitalize()} by {user['name']}: {decision.reason}")]
            result["approval_status"] = expected
            conn.execute("UPDATE approvals SET status=?,decided_by=?,decision_note=?,decided_at=? WHERE id=?", (expected, user["id"], decision.reason, now(), approval_id))
            self.persist_result(conn, result, update_message=True)
            self.store.audit(user["id"], "approval." + expected, approval_id, {"workflow_id": workflow["id"]}, conn=conn)
        return result

    def update_ticket(self, ticket_id, change, user):
        with self.store.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            user = self.fresh_user(user["id"], conn)
            row = conn.execute("SELECT t.*,u.department AS requester_department FROM tickets t JOIN users u ON u.id=t.user_id WHERE t.id=?", (ticket_id,)).fetchone()
            if not row or not self.can_see_ticket(row, user):
                raise PermissionError("Ticket not found.")
            if row["status"] != change.expected_status:
                raise ValueError("This ticket changed. Refresh Operations before updating it.")
            transitions = {"open": {"in_progress", "resolved"}, "in_progress": {"resolved"}, "resolved": {"open"}}
            if change.status not in transitions[row["status"]]:
                raise ValueError("Unsupported ticket status transition.")
            conn.execute("UPDATE tickets SET status=?,updated_at=? WHERE id=?", (change.status, now(), ticket_id))
            self.store.audit(user["id"], "ticket.status_changed", ticket_id, {"from": row["status"], "to": change.status, "workflow_id": row["workflow_id"]}, conn=conn)
            return {"id": ticket_id, "status": change.status}
