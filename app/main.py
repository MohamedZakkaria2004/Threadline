"""Same-origin, loopback-only HTTP application for the local portfolio MVP."""
from contextlib import asynccontextmanager, contextmanager
import hashlib
import json
import logging
import secrets
import threading
import time
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form, Depends, BackgroundTasks, Query
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .config import ROOT, Settings
from .storage import Store, password_hash, now
from .llm import Ollama, ModelUnavailable, prompt_inventory
from .knowledge import Knowledge, MAX_UPLOAD, permitted, IndexUnavailable
from .chat import KnowledgeChat
from .service import Copilot
from .schemas import Login, ChatRequest, Decision, TicketStatus, Feedback, EvaluationStart, QualityReview, BusinessInputs
from .insights import Insights
from .evaluation import Evaluator
from .business import calculate, scenarios
from typing import Literal

COOKIE = "copilot_session"
logger = logging.getLogger("copilot")


class BodyLimit:
    """Bound bodies before multipart parsing, including chunked requests."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] in {"GET", "HEAD", "OPTIONS"}:
            return await self.app(scope, receive, send)
        limit = MAX_UPLOAD + 64 * 1024 if scope["path"] == "/api/documents" else 32 * 1024
        chunks, size = [], 0
        while True:
            msg = await receive()
            if msg["type"] == "http.disconnect":
                return
            size += len(msg.get("body", b""))
            if size > limit:
                return await JSONResponse({"detail": "Request body is too large."}, status_code=413)(scope, receive, send)
            chunks.append(msg)
            if not msg.get("more_body", False):
                break
        index = 0
        async def replay():
            nonlocal index
            if index < len(chunks):
                msg = chunks[index]
                index += 1
                return msg
            return await receive()
        await self.app(scope, replay, send)


def create_app(settings=None, llm_factory=None):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        store = Store(settings.data_dir / "copilot.db")
        llm = llm_factory(settings, store) if llm_factory else Ollama(settings, store)
        try:
            knowledge = Knowledge(settings, store, llm)
        except Exception:
            llm.close()
            raise
        app.state.store, app.state.llm, app.state.knowledge = store, llm, knowledge
        app.state.chat = KnowledgeChat(settings, store, llm, knowledge)
        app.state.operations = Copilot(settings, store, llm, knowledge, app.state.chat)
        app.state.insights = Insights(settings, store, app.state.chat)
        app.state.evaluator = Evaluator(settings, store, app.state.chat)
        app.state.work_lock = threading.Lock()
        app.state.login_lock, app.state.login_failures = threading.Lock(), {}
        app.state.settings = settings
        try:
            store.recover_interrupted()
            yield
        finally:
            knowledge.close()
            llm.close()

    app = FastAPI(title="Atlas · Enterprise Knowledge & Operations Copilot", version="0.3.1", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.build_id = hashlib.sha256(b''.join(p.relative_to(ROOT).as_posix().encode() + p.read_bytes() for p in sorted(list((ROOT / 'app').rglob('*.py')) + list((ROOT / 'prompts').rglob('*.txt'))))).hexdigest()[:16]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"])
    app.add_middleware(BodyLimit)

    @app.middleware("http")
    async def local_security(request, call_next):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            expected = str(request.base_url).rstrip("/")
            if request.headers.get("x-copilot-request") != "1" or (origin and origin != expected):
                return JSONResponse({"detail": "Use the local application to submit this request."}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        response.headers["Cache-Control"] = "no-store"
        return response

    def current_user(request: Request):
        token = request.cookies.get(COOKIE, "")
        if not token or len(token) > 200:
            raise HTTPException(401, "Sign in to continue.")
        user = request.app.state.store.one("SELECT u.id,u.username,u.name,u.role,u.department FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>?", (hashlib.sha256(token.encode()).hexdigest(), time.time()))
        if not user:
            raise HTTPException(401, "Your session has expired. Please sign in again.")
        return user

    def admin(user=Depends(current_user)):
        if user["role"] != "admin":
            raise HTTPException(403, "An administrator must manage documents.")
        return user

    @contextmanager
    def inference_slot(request):
        if not request.app.state.work_lock.acquire(blocking=False):
            raise HTTPException(409, "The local model is busy with another request. Wait briefly and try again.")
        try:
            yield
        finally:
            request.app.state.work_lock.release()

    @app.exception_handler(ValueError)
    async def value_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(PermissionError)
    async def permission_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=403)

    @app.exception_handler(ModelUnavailable)
    async def model_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=503)

    @app.exception_handler(IndexUnavailable)
    async def index_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=503)

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        logger.error("Request failed: %s", type(exc).__name__)
        return JSONResponse({"detail": "The request failed. Your existing documents remain available. Check the local server and retry."}, status_code=500)

    @app.get("/api/health")
    def health(request: Request):
        if request.app.state.work_lock.locked():
            return {"status": "busy", "model": settings.model, "embedding_model": settings.embed_model, "connected": None, "missing": [], "phase": 3, "build": app.state.build_id}
        state = request.app.state.llm.health()
        return {"status": "ready" if state["ready"] else "model_unavailable", "model": settings.model, "embedding_model": settings.embed_model, "connected": state["connected"], "missing": state["missing"], "error": state.get("error"), "phase": 3, "build": app.state.build_id}

    @app.post("/api/login")
    def login(data: Login, request: Request):
        store = request.app.state.store
        # A fixed account list and one loopback client keep this in-memory limiter bounded.
        key = (request.client.host if request.client else "local")
        with request.app.state.login_lock:
            attempts = [t for t in request.app.state.login_failures.get(key, []) if t > time.monotonic() - 300]
            if len(attempts) >= 8:
                raise HTTPException(429, "Too many unsuccessful sign-ins. Try again in five minutes.")
            user = store.one("SELECT * FROM users WHERE username=?", (data.username.strip().lower(),))
            computed = password_hash(data.password, user["salt"] if user else "00" * 16)
            if not user or not secrets.compare_digest(computed, user["password_hash"]):
                request.app.state.login_failures[key] = attempts + [time.monotonic()]
                raise HTTPException(401, "Incorrect username or password.")
            request.app.state.login_failures[key] = []
        token = secrets.token_urlsafe(32)
        with store.connect() as conn:
            conn.execute("DELETE FROM sessions WHERE expires_at<?", (time.time(),))
            old = request.cookies.get(COOKIE)
            if old:
                conn.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(old.encode()).hexdigest(),))
            conn.execute("INSERT INTO sessions VALUES (?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), user["id"], time.time() + 8 * 3600))
            store.audit(user["id"], "auth.login", conn=conn)
        response = JSONResponse({k: user[k] for k in ["id", "username", "name", "role", "department"]})
        response.set_cookie(COOKIE, token, httponly=True, samesite="strict", secure=False, max_age=8 * 3600)
        return response

    @app.get("/api/me")
    def me(user=Depends(current_user)):
        return user

    @app.post("/api/logout")
    def logout(request: Request, user=Depends(current_user)):
        request.app.state.store.run("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(request.cookies[COOKIE].encode()).hexdigest(),))
        response = JSONResponse({"ok": True})
        response.delete_cookie(COOKIE)
        return response

    @app.get("/api/documents")
    def documents(request: Request, user=Depends(current_user)):
        rows = request.app.state.knowledge.visible_documents(user, active_only=user["role"] != "admin")
        return [{k: row[k] for k in ["id", "title", "filename", "classification", "department", "status", "chunk_count", "version", "created_at", "error", "embed_model"]} for row in sorted(rows, key=lambda r: r["created_at"], reverse=True)]

    @app.get("/api/documents/{document_id}")
    def document(document_id: str, request: Request, user=Depends(current_user)):
        store = request.app.state.store
        doc = store.one("SELECT * FROM documents WHERE id=?", (document_id,))
        if not doc or not permitted(doc, user):
            raise HTTPException(404, "Document not found.")
        return {"document": {k: doc[k] for k in ["id", "title", "filename", "version", "department", "classification", "status"]}, "chunks": store.all("SELECT id,position,text,locator FROM chunks WHERE document_id=? ORDER BY position", (document_id,))}

    @app.post("/api/documents")
    def upload(request: Request, file: UploadFile = File(...), title: str = Form(""), classification: str = Form("internal"), department: str = Form("All"), replaces_id: str = Form(""), user=Depends(admin)):
        if len(title) > 150 or len(replaces_id) > 50:
            raise HTTPException(400, "Document title or replacement reference is too long.")
        content = file.file.read(MAX_UPLOAD + 1)
        with inference_slot(request):
            result = request.app.state.knowledge.ingest(file.filename or "", content, classification, user["id"], title=title, department=department, replaces_id=replaces_id or None)
        return result

    @app.get("/api/conversations")
    def conversations(request: Request, user=Depends(current_user)):
        return request.app.state.store.all("SELECT id,title,created_at FROM conversations WHERE user_id=? ORDER BY created_at DESC LIMIT 100", (user["id"],))

    @app.get("/api/conversations/{conversation_id}")
    def conversation(conversation_id: str, request: Request, user=Depends(current_user)):
        store = request.app.state.store
        if not store.one("SELECT id FROM conversations WHERE id=? AND user_id=?", (conversation_id, user["id"])):
            raise HTTPException(404, "Conversation not found.")
        rows = store.all("SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at,rowid", (conversation_id,))
        for row in rows:
            row["metadata"] = request.app.state.chat.safe_result(json.loads(row["metadata"]), user)
            feedback = store.one('SELECT rating FROM feedback WHERE message_id=? AND user_id=?', (row['id'], user['id']))
            if feedback:
                row['metadata']['feedback'] = feedback['rating']
            if row["metadata"].get("access_changed"):
                row["content"] = row["metadata"]["answer"]
        return rows

    @app.post("/api/chat")
    def chat(data: ChatRequest, request: Request, user=Depends(current_user)):
        with inference_slot(request):
            service = request.app.state.operations if data.mode == "agent" else request.app.state.chat
            return service.chat(data, user)

    @app.get("/api/operations")
    def operations(request: Request, user=Depends(current_user)):
        return request.app.state.operations.overview(user)

    @app.post("/api/approvals/{approval_id}/decision")
    def decide(approval_id: str, data: Decision, request: Request, user=Depends(current_user)):
        return request.app.state.operations.decide(approval_id, data, user)

    @app.patch("/api/tickets/{ticket_id}")
    def update_ticket(ticket_id: str, data: TicketStatus, request: Request, user=Depends(current_user)):
        return request.app.state.operations.update_ticket(ticket_id, data, user)

    @app.get("/api/reports/{report_id}")
    def report(report_id: str, request: Request, user=Depends(current_user)):
        return request.app.state.operations.report(report_id, user)

    @app.get("/api/reports/{report_id}/download")
    def download_report(report_id: str, request: Request, user=Depends(current_user)):
        row = request.app.state.operations.report(report_id, user)
        return PlainTextResponse(row["markdown"], media_type="text/markdown", headers={"Content-Disposition": f'attachment; filename="{row["id"]}.md"'})

    @app.get("/")
    def index():
        return FileResponse(ROOT / "app" / "static" / "index.html")

    @app.get('/api/insights')
    def insights(request: Request, days: int = Query(30, ge=1, le=90), scope: Literal['mine', 'platform'] = 'mine', user=Depends(current_user)):
        return request.app.state.insights.summary(user, days, scope)

    @app.put('/api/messages/{message_id}/feedback')
    def feedback(message_id: str, data: Feedback, request: Request, user=Depends(current_user)):
        return request.app.state.insights.feedback(message_id, data, user)

    @app.get('/api/prompts')
    def prompts(user=Depends(admin)):
        return {'active_version': settings.prompt_version, 'model': settings.model, 'embedding_model': settings.embed_model, 'templates': prompt_inventory()}

    @app.get('/api/business-case')
    def business_case(user=Depends(current_user)):
        return {'scenarios': scenarios()}

    @app.post('/api/business-case')
    def business_calculation(data: BusinessInputs, user=Depends(current_user)):
        return calculate(data)

    @app.get('/api/evaluations')
    def evaluations(request: Request, user=Depends(admin)):
        return request.app.state.evaluator.listing()

    @app.post('/api/evaluations', status_code=202)
    def start_evaluation(data: EvaluationStart, request: Request, background: BackgroundTasks, user=Depends(admin)):
        lock = request.app.state.work_lock
        if not lock.acquire(blocking=False):
            raise HTTPException(409, 'The local model is busy. Start the benchmark after it finishes.')
        evaluator = request.app.state.evaluator
        try:
            run = evaluator.start(data.suite, user)
        except Exception:
            lock.release()
            raise
        def execute():
            try:
                evaluator.run(run['id'])
            finally:
                lock.release()
        background.add_task(execute)
        return run

    @app.get('/api/evaluations/{run_id}')
    def evaluation(run_id: str, request: Request, user=Depends(admin)):
        return request.app.state.evaluator.get(run_id)

    @app.get('/api/evaluations/{run_id}/download')
    def evaluation_download(run_id: str, request: Request, user=Depends(admin)):
        row = request.app.state.evaluator.get(run_id)
        return JSONResponse(row, headers={'Content-Disposition': f'attachment; filename="evaluation-{row["id"]}.json"'})

    @app.post('/api/evaluations/{run_id}/cancel')
    def cancel_evaluation(run_id: str, request: Request, user=Depends(admin)):
        return request.app.state.evaluator.cancel(run_id, user)

    @app.put('/api/evaluations/{run_id}/cases/{case_id}/review')
    def review_evaluation(run_id: str, case_id: str, data: QualityReview, request: Request, user=Depends(admin)):
        return request.app.state.evaluator.review(run_id, case_id, data, user)

    app.mount("/static", StaticFiles(directory=ROOT / "app" / "static"), name="static")
    return app
