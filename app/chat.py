"""Conversational RAG; actions use the separately authorized Operations path."""
import json
import hashlib
import re
import time
from .knowledge import permitted, validate_answer, focus_sources, has_numeric_conflict, words
from .llm import prompt
from .schemas import GroundedAnswer
from .storage import dump, now, uid

GENERIC_QUESTION_TERMS = set('who why explain tell many much limit limits policy policies rule rules procedure procedures process processes amount amounts deadline deadlines approval approvals approve approves approver approvers requirement requirements required allowed happen happens next step steps'.split())


class KnowledgeChat:
    def __init__(self, settings, store, llm, knowledge):
        self.settings, self.store, self.llm, self.knowledge = settings, store, llm, knowledge

    def safe_result(self, result, user, conn=None):
        result = dict(result)
        old_versions = False
        for citation in result.get("citations", []):
            sql, params = "SELECT * FROM documents WHERE id=?", (citation["document_id"],)
            doc = conn.execute(sql, params).fetchone() if conn is not None else self.store.one(sql, params)
            if not doc or not permitted(doc, user):
                envelope = {key: result[key] for key in ("conversation_id", "workflow_id", "message_id", "status", "tool", "latency_ms", "model", "prompt_version") if key in result}
                return {**envelope, "answer": "This saved answer refers to a document you can no longer access. Ask a new question to retrieve current permitted evidence.", "citations": [], "insufficient_evidence": True, "access_changed": True}
            old_versions |= doc["status"] != "ready"
        result["historical_sources"] = old_versions
        return result

    def answer(self, question, user, workflow_id=None, history=None, document_ids=None):
        if not question.strip():
            raise ValueError("Enter a question containing text.")
        action_request = re.match(r"^(?:please\s+|can you\s+|could you\s+)?(?:approve\b|send\b|create\s+(?:a\s+)?(?:support\s+)?ticket\b|grant\b|revoke\b|delete\b)", question.strip(), re.I)
        if action_request:
            return {"answer": "In Knowledge mode I cannot approve requests or perform actions. Switch to Actions to create a local support ticket, report, or access-review request. I can also explain the relevant policy here.", "citations": [], "insufficient_evidence": False, "action_unavailable": True, "checks": {"method": "Knowledge mode capability boundary; no model or action was executed."}}
        query = question
        previous = [m["content"] for m in (history or []) if m["role"] == "user"]
        generic_question = bool(re.search(r'[a-z]', question, re.I)) and words(question) <= GENERIC_QUESTION_TERMS and not re.search(r'\bIT\b', question)
        if generic_question and not previous:
            return {'answer':'Please name the policy, topic, or process you mean so I can find the correct rule.', 'citations':[], 'insufficient_evidence':True, 'clarification_required':True, 'checks':{'citations_valid':True, 'method':'No topic or preceding conversation context; clarification required before retrieval.'}}
        is_followup = re.search(r"\b(it|that|those|these|them|this policy)\b|^(and\b|what about\b|who approves\b|how do i request\b)", question, re.I)
        if previous and (is_followup or generic_question):
            query = previous[-1][:700] + "\nFollow-up: " + question
        search_options = {'workflow_id': workflow_id}
        if document_ids is not None:
            search_options['document_ids'] = document_ids
        sources = self.knowledge.search(query, user, **search_options)
        if not sources:
            return {"answer": "I couldn't find supporting evidence in the documents you can access. Add a relevant document or ask the policy owner.", "citations": [], "insufficient_evidence": True, "checks": {"citations_valid": True, "method": "No accessible evidence found."}}
        retrieved_count = len(sources)
        sources = focus_sources(sources, query)
        if has_numeric_conflict(sources, query):
            return {'answer': "The available documents contain conflicting numerical rules for this question. I cannot select an authoritative value; ask the policy owner to resolve the conflict.", 'citations': [], 'insufficient_evidence': True, 'checks': {'citations_valid': True, 'conflicting_evidence': True, 'method': 'Matching relevant rule text with different values across active documents; no precedence inferred.'}}
        messages = [{"role": "system", "content": prompt("answer", self.settings.prompt_version)}, {"role": "user", "content": dump({
            "question": question,
            "conversation_history": [{"role": m["role"], "content": m["content"][:600]} for m in (history or [])[-4:]],
            "evidence": [{"source_id": s["source_id"], "title": s["title"], "text": s["text"]} for s in sources],
        })}]
        answer = self.llm.structured(messages, GroundedAnswer, "answer", user["id"], workflow_id)
        result = validate_answer(answer, sources)
        repair_needed = bool(result['checks'].get('unsupported_numbers')) or (self.settings.prompt_version == 'v4' and (result['checks']['invalid_citations'] or not answer.citations))
        if self.settings.prompt_version in {"v3", "v4"} and repair_needed and not answer.insufficient_evidence and (self.settings.prompt_version == 'v4' or result['checks']['invalid_citations'] == 0):
            # One bounded correction, with the same evidence and the same validator.
            # User-supplied amounts never become policy evidence or a numeric whitelist.
            repair = prompt("answer_repair", self.settings.prompt_version)
            revised = self.llm.structured(messages + [{"role": "assistant", "content": answer.model_dump_json()}, {"role": "user", "content": repair}], GroundedAnswer, "answer_repair", user["id"], workflow_id)
            result = validate_answer(revised, sources)
            result["grounding_retry"] = True
            result["repair_prompt_sha256"] = hashlib.sha256(repair.encode()).hexdigest()
        result["prompt_sha256"] = hashlib.sha256(messages[0]["content"].encode()).hexdigest()
        result["embedding_model"] = self.settings.embed_model
        result["retrieval_scope"] = {"retrieved": retrieved_count, "used": len(sources), "method": "Dominant query coverage; preserve competing documents and bounded neighboring evidence."}
        return result

    def chat(self, request, user):
        if not request.message.strip():
            raise ValueError("Enter a question containing text.")
        prior = self.store.one("SELECT * FROM workflows WHERE user_id=? AND request_id=?", (user["id"], request.request_id))
        if prior:
            if prior["mode"] != request.mode or prior["input"] != request.message or (request.conversation_id and prior["conversation_id"] != request.conversation_id):
                raise ValueError("This request ID belongs to a different question. Use a new request ID.")
            if prior["status"] != "completed":
                raise ValueError("The previous attempt did not complete. Retry with a new request ID.")
            return self.safe_result(json.loads(prior["result"]), user)
        conversation_id = request.conversation_id
        history = []
        if conversation_id:
            if not self.store.one("SELECT id FROM conversations WHERE id=? AND user_id=?", (conversation_id, user["id"])):
                raise PermissionError("Conversation not found.")
            rows = self.store.all("SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at DESC,rowid DESC LIMIT 4", (conversation_id,))[::-1]
            for row in rows:
                metadata = json.loads(row["metadata"])
                # Revoked evidence must not enter model history either.
                content = self.safe_result(metadata, user).get("answer", row["content"]) if row["role"] == "assistant" else row["content"]
                history.append({"role": row["role"], "content": content})
        else:
            conversation_id = uid()
        workflow_id, started = uid(), time.perf_counter()
        with self.store.connect() as conn:
            if not request.conversation_id:
                conn.execute("INSERT INTO conversations VALUES (?,?,?,?)", (conversation_id, user["id"], request.message[:70], now()))
            conn.execute("INSERT INTO workflows(id,request_id,conversation_id,user_id,input,status,created_at,updated_at) VALUES (?,?,?,?,?,'running',?,?)", (workflow_id, request.request_id, conversation_id, user["id"], request.message, now(), now()))
            conn.execute("INSERT INTO messages VALUES (?,?,?,?,?,?)", (uid(), conversation_id, "user", request.message, "{}", now()))
            self.store.audit(user["id"], "chat.started", workflow_id, conn=conn)
        try:
            result = self.answer(request.message, user, workflow_id, history)
            result.update({"workflow_id": workflow_id, "conversation_id": conversation_id, "status": "completed", "tool": "answer", "latency_ms": round((time.perf_counter() - started) * 1000), "model": self.settings.model, "prompt_version": self.settings.prompt_version, "message_id": uid()})
            with self.store.connect() as conn:
                # Local generation can take minutes. Reauthorize at publication,
                # using the same SQL snapshot as the saved answer and audit.
                conn.execute("BEGIN IMMEDIATE")
                fresh_user = conn.execute("SELECT id,role,department FROM users WHERE id=?", (user["id"],)).fetchone()
                if not fresh_user:
                    raise PermissionError("Account is no longer available.")
                result = self.safe_result(result, fresh_user, conn=conn)
                conn.execute("INSERT INTO messages VALUES (?,?,?,?,?,?)", (result["message_id"], conversation_id, "assistant", result["answer"], dump(result), now()))
                conn.execute("UPDATE workflows SET status='completed',result=?,updated_at=? WHERE id=?", (dump(result), now(), workflow_id))
                self.store.audit(user["id"], "chat.completed", workflow_id, {"abstained": result["insufficient_evidence"], "citations": len(result["citations"]), "latency_ms": result["latency_ms"]}, conn=conn)
            return result
        except Exception as exc:
            with self.store.connect() as conn:
                conn.execute("UPDATE workflows SET status='failed',updated_at=? WHERE id=?", (now(), workflow_id))
                conn.execute("INSERT INTO messages VALUES (?,?,?,?,?,?)", (uid(), conversation_id, "assistant", "The local request failed. Check model status and try again. Your question has been saved.", dump({"status": "failed", "workflow_id": workflow_id}), now()))
            self.store.audit(user["id"], "chat.failed", workflow_id, {"error_type": type(exc).__name__})
            raise
