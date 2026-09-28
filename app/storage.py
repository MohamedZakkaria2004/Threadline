from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import secrets
import sqlite3
import uuid
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return str(uuid.uuid4())


def dump(value):
    return json.dumps(value, ensure_ascii=False)


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 260_000).hex()


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
 id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
 role TEXT NOT NULL CHECK(role IN ('employee','manager','admin')), salt TEXT NOT NULL, password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, user_id TEXT REFERENCES users(id), expires_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS documents (
 id TEXT PRIMARY KEY, title TEXT NOT NULL, filename TEXT NOT NULL, digest TEXT NOT NULL,
 classification TEXT NOT NULL CHECK(classification IN ('internal','leadership')),
 status TEXT NOT NULL, chunk_count INTEGER NOT NULL DEFAULT 0, embed_model TEXT NOT NULL,
 created_by TEXT REFERENCES users(id), created_at TEXT NOT NULL,
 department TEXT NOT NULL DEFAULT 'All', version INTEGER NOT NULL DEFAULT 1, supersedes_id TEXT, error TEXT
);
CREATE TABLE IF NOT EXISTS chunks (
 id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id), position INTEGER NOT NULL, text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, user_id TEXT REFERENCES users(id), title TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS messages (
 id TEXT PRIMARY KEY, conversation_id TEXT REFERENCES conversations(id), role TEXT NOT NULL,
 content TEXT NOT NULL, metadata TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workflows (
 id TEXT PRIMARY KEY, request_id TEXT NOT NULL, conversation_id TEXT REFERENCES conversations(id),
 user_id TEXT REFERENCES users(id), input TEXT NOT NULL, tool TEXT NOT NULL DEFAULT 'answer',
 status TEXT NOT NULL, steps TEXT NOT NULL DEFAULT '[]', payload TEXT NOT NULL DEFAULT '{}',
 result TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 UNIQUE(user_id, request_id)
);
CREATE TABLE IF NOT EXISTS approvals (
 id TEXT PRIMARY KEY, workflow_id TEXT UNIQUE REFERENCES workflows(id), requester_id TEXT REFERENCES users(id),
 status TEXT NOT NULL DEFAULT 'pending', reason TEXT NOT NULL, payload TEXT NOT NULL,
 decided_by TEXT REFERENCES users(id), decision_note TEXT, created_at TEXT NOT NULL, decided_at TEXT
);
CREATE TABLE IF NOT EXISTS tickets (
 id TEXT PRIMARY KEY, workflow_id TEXT UNIQUE REFERENCES workflows(id), user_id TEXT REFERENCES users(id),
 title TEXT NOT NULL, description TEXT NOT NULL, priority TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
 category TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reports (
 id TEXT PRIMARY KEY, workflow_id TEXT UNIQUE REFERENCES workflows(id), user_id TEXT REFERENCES users(id),
 title TEXT NOT NULL, markdown TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, event TEXT NOT NULL, entity_id TEXT,
 detail TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS metrics (
 id INTEGER PRIMARY KEY AUTOINCREMENT, workflow_id TEXT, user_id TEXT, operation TEXT NOT NULL,
 latency_ms REAL NOT NULL, prompt_tokens INTEGER NOT NULL DEFAULT 0, output_tokens INTEGER NOT NULL DEFAULT 0,
 model TEXT NOT NULL, prompt_version TEXT NOT NULL, status TEXT NOT NULL,
 estimated_energy_usd REAL NOT NULL DEFAULT 0, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS feedback (
 message_id TEXT PRIMARY KEY REFERENCES messages(id), user_id TEXT REFERENCES users(id), rating TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evaluations (
 id TEXT PRIMARY KEY, status TEXT NOT NULL, results TEXT NOT NULL DEFAULT '[]', summary TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_messages_conversation ON messages(conversation_id, created_at);
CREATE INDEX IF NOT EXISTS ix_workflows_user ON workflows(user_id, created_at);
CREATE INDEX IF NOT EXISTS ix_metrics_user ON metrics(user_id, created_at);
"""


class Store:
    def __init__(self, path):
        self.path = str(path)
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            # Additive migrations keep existing prototype data intact.
            additions = {
                "users": {"department": "TEXT NOT NULL DEFAULT 'IT'"},
                "documents": {"department": "TEXT NOT NULL DEFAULT 'All'", "version": "INTEGER NOT NULL DEFAULT 1", "supersedes_id": "TEXT", "error": "TEXT"},
                "chunks": {"locator": "TEXT NOT NULL DEFAULT 'Document'"},
                "workflows": {"mode": "TEXT NOT NULL DEFAULT 'ask'"},
                "approvals": {"department": "TEXT NOT NULL DEFAULT 'IT'", "payload_hash": "TEXT NOT NULL DEFAULT ''"},
                "tickets": {"department": "TEXT NOT NULL DEFAULT 'IT'", "updated_at": "TEXT"},
                "reports": {"metadata": "TEXT NOT NULL DEFAULT '{}'"},
                "evaluations": {"owner_id": "TEXT", "suite": "TEXT NOT NULL DEFAULT 'legacy'", "config": "TEXT NOT NULL DEFAULT '{}'", "updated_at": "TEXT", "cancel_requested": "INTEGER NOT NULL DEFAULT 0"},
            }
            for table, columns in additions.items():
                present = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
                for column, declaration in columns.items():
                    if column not in present:
                        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")
            credentials = []
            for username, name, role, department in [("employee", "Aisha Khan", "employee", "IT"), ("hr", "Leila Ahmed", "employee", "HR"), ("manager", "Daniel Reyes", "manager", "Operations"), ("admin", "Platform Admin", "admin", "All")]:
                existing = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
                legacy_password = existing and secrets.compare_digest(existing["password_hash"], password_hash("local-demo-2026", existing["salt"]))
                if not existing or legacy_password:
                    salt, password = secrets.token_hex(16), secrets.token_urlsafe(15)
                    if existing:
                        conn.execute("UPDATE users SET salt=?,password_hash=?,department=? WHERE id=?", (salt, password_hash(password, salt), department, existing["id"]))
                        conn.execute("DELETE FROM sessions WHERE user_id=?", (existing["id"],))
                    else:
                        conn.execute("INSERT INTO users(id,username,name,role,salt,password_hash,department) VALUES (?,?,?,?,?,?,?)", (username, username, name, role, salt, password_hash(password, salt), department))
                    credentials.append(f"{username}: {password}  ({role}, {department})")
            if credentials:
                credential_path = Path(self.path).parent / "demo-credentials.txt"
                with credential_path.open("a", encoding="utf-8") as output:
                    output.write("\nLocal demo accounts generated " + now() + "\n" + "\n".join(credentials) + "\n")
                try:
                    credential_path.chmod(0o600)
                except OSError:
                    pass
            conn.execute("PRAGMA user_version=3")

    def recover_interrupted(self):
        """Run only after the caller owns the exclusive embedded-vector-store lock."""
        with self.connect() as conn:
            # Interrupted work is visible and retryable; never silently replay a side effect.
            interrupted = conn.execute("SELECT id,conversation_id,user_id,status,steps FROM workflows WHERE status IN ('running','failed')").fetchall()
            for workflow in interrupted:
                terminal_messages = conn.execute("SELECT metadata FROM messages WHERE conversation_id=? AND role='assistant'", (workflow["conversation_id"],)).fetchall()
                if workflow["status"] == "failed" and any(json.loads(m["metadata"]).get("workflow_id") == workflow["id"] for m in terminal_messages):
                    continue
                steps = json.loads(workflow["steps"]) + [{"name": "Interrupted", "detail": "Server stopped before completion. No action is automatically replayed.", "at": now()}]
                result = {"status": "failed", "workflow_id": workflow["id"], "interrupted": True, "steps": steps}
                conn.execute("UPDATE workflows SET status='failed',steps=?,result=?,updated_at=? WHERE id=?", (dump(steps), dump(result), now(), workflow["id"]))
                if workflow["conversation_id"]:
                    conn.execute("INSERT INTO messages VALUES (?,?,?,?,?,?)", (uid(), workflow["conversation_id"], "assistant", "The previous request was interrupted by a server restart. Review its state before retrying.", dump(result), now()))
                conn.execute("INSERT INTO audit(user_id,event,entity_id,detail,created_at) VALUES (?,?,?,?,?)", (workflow["user_id"], "workflow.interrupted", workflow["id"], "{}", now()))
            conn.execute("UPDATE documents SET status='failed',error='Indexing was interrupted. Re-upload the file to retry.' WHERE status='indexing'")
            conn.execute("UPDATE evaluations SET status='interrupted',updated_at=? WHERE status='running'", (now(),))

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def all(self, sql, params=()):
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def one(self, sql, params=()):
        rows = self.all(sql, params)
        return rows[0] if rows else None

    def run(self, sql, params=()):
        with self.connect() as conn:
            return conn.execute(sql, params).rowcount

    def audit(self, user_id, event, entity_id=None, detail=None, conn=None):
        sql = "INSERT INTO audit(user_id,event,entity_id,detail,created_at) VALUES (?,?,?,?,?)"
        params = (user_id, event, entity_id, dump(detail or {}), now())
        if conn is not None:
            conn.execute(sql, params)
        else:
            self.run(sql, params)

    def add_message(self, conversation_id, role, content, metadata=None):
        message_id = uid()
        self.run("INSERT INTO messages VALUES (?,?,?,?,?,?)", (message_id, conversation_id, role, content, dump(metadata or {}), now()))
        return message_id
