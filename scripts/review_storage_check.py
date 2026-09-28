"""Read-only final-state check; never starts recovery or opens the vector store."""
import json
import sqlite3
from app.config import ROOT, Settings


def main():
    path = (Settings().data_dir / "copilot.db").resolve()
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as conn:
        result = {
            "integrity": conn.execute("PRAGMA quick_check").fetchone()[0],
            "foreign_key_issues": conn.execute("PRAGMA foreign_key_check").fetchall(),
            "documents_by_status": conn.execute("SELECT status,COUNT(*) FROM documents GROUP BY status").fetchall(),
            "active_workflows": conn.execute("SELECT COUNT(*) FROM workflows WHERE status='running'").fetchone()[0],
        }
    (ROOT / "artifacts" / "review-storage-state.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
