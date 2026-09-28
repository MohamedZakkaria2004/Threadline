"""Read-only consistency checks for the running local portfolio datastore."""
import json
import sqlite3
from app.config import ROOT, Settings


def main():
    path = Settings().data_dir / 'copilot.db'
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as conn:
        checks = {
            'integrity': conn.execute('PRAGMA quick_check').fetchone()[0] == 'ok',
            'foreign_keys': not conn.execute('PRAGMA foreign_key_check').fetchall(),
            'no_running_workflows': conn.execute("SELECT count(*) FROM workflows WHERE status='running'").fetchone()[0] == 0,
            'completed_ticket_workflows_have_ticket': conn.execute("SELECT count(*) FROM workflows w LEFT JOIN tickets t ON t.workflow_id=w.id WHERE w.mode='agent' AND w.tool IN ('create_ticket','request_access') AND w.status='completed' AND t.id IS NULL").fetchone()[0] == 0,
            'pending_or_rejected_have_no_ticket': conn.execute("SELECT count(*) FROM workflows w JOIN tickets t ON t.workflow_id=w.id WHERE w.status IN ('waiting_approval','rejected','failed')").fetchone()[0] == 0,
            'approval_and_workflow_states_agree': conn.execute("SELECT count(*) FROM approvals a JOIN workflows w ON w.id=a.workflow_id WHERE (a.status='pending' AND w.status<>'waiting_approval') OR (a.status='approved' AND w.status<>'completed') OR (a.status='rejected' AND w.status<>'rejected')").fetchone()[0] == 0,
            'reports_have_provenance': conn.execute("SELECT count(*) FROM reports WHERE coalesce(json_array_length(metadata,'$.citations'),0)=0").fetchone()[0] == 0,
            'completed_workflows_have_saved_message': conn.execute("SELECT count(*) FROM workflows w LEFT JOIN messages m ON m.id=json_extract(w.result,'$.message_id') WHERE w.mode='agent' AND w.status IN ('completed','waiting_approval','rejected') AND (m.id IS NULL OR json_extract(m.metadata,'$.status')<>w.status)").fetchone()[0] == 0,
        }
        counts = {table: conn.execute(f'SELECT count(*) FROM {table}').fetchone()[0] for table in ['documents', 'chunks', 'tickets', 'reports', 'approvals', 'audit', 'metrics']}
        report = {'checks': checks, 'passed': all(checks.values()), 'counts': counts, 'agent_states': dict(conn.execute("SELECT status,count(*) FROM workflows WHERE mode='agent' GROUP BY status").fetchall()), 'schema_version': conn.execute('PRAGMA user_version').fetchone()[0]}
    (ROOT / 'artifacts' / 'phase2-storage-check.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
