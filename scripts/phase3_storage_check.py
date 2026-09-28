"""Read-only datastore and independent SQL-to-dashboard reconciliation."""
import json
import argparse
import math
import re
import sqlite3
import httpx
from app.config import ROOT, Settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reaudit', action='store_true', help='Save a separate follow-up review artifact.')
    parser.add_argument('--output')
    args = parser.parse_args()
    settings = Settings()
    credentials = (settings.data_dir / 'demo-credentials.txt').read_text()
    with httpx.Client(base_url='http://127.0.0.1:8765', timeout=30, trust_env=False, headers={'X-Copilot-Request': '1'}) as client:
        password = re.findall(r'^admin: (\S+)', credentials, re.M)[-1]
        client.post('/api/login', json={'username': 'admin', 'password': password}).raise_for_status()
        response = client.get('/api/insights?scope=platform')
        response.raise_for_status()
        dashboard = response.json()
        health = client.get('/api/health').json()
    path = settings.data_dir / 'copilot.db'
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as conn:
        scalar = lambda sql, args=(): conn.execute(sql, args).fetchone()[0]
        checks = {
            'integrity': scalar('PRAGMA quick_check') == 'ok',
            'foreign_keys': not conn.execute('PRAGMA foreign_key_check').fetchall(),
            'schema_3': scalar('PRAGMA user_version') == 3,
            'no_running_workflows': scalar("SELECT count(*) FROM workflows WHERE status='running'") == 0,
            'completed_ticket_workflows_have_ticket': scalar("SELECT count(*) FROM workflows w LEFT JOIN tickets t ON t.workflow_id=w.id WHERE w.mode='agent' AND w.tool IN ('create_ticket','request_access') AND w.status='completed' AND t.id IS NULL") == 0,
            'pending_or_rejected_have_no_ticket': scalar("SELECT count(*) FROM workflows w JOIN tickets t ON t.workflow_id=w.id WHERE w.status IN ('waiting_approval','rejected','failed')") == 0,
            'approval_and_workflow_states_agree': scalar("SELECT count(*) FROM approvals a JOIN workflows w ON w.id=a.workflow_id WHERE (a.status='pending' AND w.status<>'waiting_approval') OR (a.status='approved' AND w.status<>'completed') OR (a.status='rejected' AND w.status<>'rejected')") == 0,
            'reports_have_provenance': scalar("SELECT count(*) FROM reports WHERE coalesce(json_array_length(metadata,'$.citations'),0)=0") == 0,
            'action_messages_match_workflow': scalar("SELECT count(*) FROM workflows w LEFT JOIN messages m ON m.id=json_extract(w.result,'$.message_id') WHERE w.mode='agent' AND w.status IN ('completed','waiting_approval','rejected') AND (m.id IS NULL OR json_extract(m.metadata,'$.status')<>w.status)") == 0,
            'no_running_evaluations': scalar("SELECT count(*) FROM evaluations WHERE status='running'") == 0,
            'evaluation_progress_matches_saved_cases': scalar("SELECT count(*) FROM evaluations WHERE suite<>'legacy' AND json_array_length(results)<>json_extract(summary,'$.finished')") == 0,
            'completed_evaluations_have_all_cases': scalar("SELECT count(*) FROM evaluations WHERE suite<>'legacy' AND status='completed' AND json_array_length(results)<>json_array_length(config,'$.case_ids')") == 0,
            'completed_evaluations_have_audit': scalar("SELECT count(*) FROM evaluations e WHERE e.suite<>'legacy' AND e.status='completed' AND NOT EXISTS(SELECT 1 FROM audit a WHERE a.entity_id=e.id AND a.event='evaluation.completed')") == 0,
            'one_feedback_vote_per_answer': scalar('SELECT count(*)-count(DISTINCT message_id) FROM feedback') == 0,
        }
        since = (dashboard['since'],)
        checks['request_totals_match_sql'] = dashboard['requests'] == scalar('SELECT count(*) FROM workflows WHERE created_at>=?', since)
        times = [r[0] for r in conn.execute("SELECT json_extract(result,'$.latency_ms')/1000.0 AS t FROM workflows WHERE created_at>=? AND json_type(result,'$.latency_ms') IN ('integer','real') AND json_extract(result,'$.latency_ms')>=0 ORDER BY t", since)]
        expected_p95 = round(times[math.ceil(len(times) * .95) - 1], 2) if times else None
        checks['latency_matches_independent_sql'] = dashboard['latency']['samples'] == len(times) and dashboard['latency']['p95_seconds'] == expected_p95
        calls = scalar("SELECT count(*) FROM metrics WHERE created_at>=? AND operation IN ('answer','answer_repair','planner') AND (workflow_id IS NULL OR workflow_id NOT LIKE 'eval:%')", since)
        checks['generation_count_excludes_benchmarks'] = dashboard['generation']['calls'] == calls
        rated = scalar('SELECT count(*) FROM feedback WHERE created_at>=?', since)
        helpful = scalar("SELECT count(*) FROM feedback WHERE created_at>=? AND rating='helpful'", since)
        checks['feedback_denominator_matches_sql'] = dashboard['feedback'] == {'rated': rated, 'helpful': helpful, 'helpful_percent': round(100 * helpful / rated, 2) if rated else None}
        checks['application_ready'] = health['status'] == 'ready' and health['phase'] == 3
        counts = {table: scalar(f'SELECT count(*) FROM {table}') for table in ['documents', 'chunks', 'tickets', 'reports', 'approvals', 'evaluations', 'feedback', 'audit', 'metrics']}
    report = {'checks': checks, 'passed': sum(checks.values()), 'failed': sum(not value for value in checks.values()), 'counts': counts, 'dashboard': dashboard}
    from pathlib import Path
    filename = Path(args.output).name if args.output else ('phase3-reaudit-storage.json' if args.reaudit else 'phase3-storage-check.json')
    (ROOT / 'artifacts' / filename).write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k: report[k] for k in ['passed', 'failed', 'counts']}))
    raise SystemExit(0 if all(checks.values()) else 1)


if __name__ == '__main__':
    main()
