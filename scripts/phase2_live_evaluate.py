"""Actual Qwen + HTTP + SQLite integration review, using synthetic local requests."""
import json
import re
import statistics
import time
import uuid
from collections import Counter
from contextlib import ExitStack
import httpx
from app.config import ROOT, Settings


def main():
    settings = Settings()
    credentials = (settings.data_dir / 'demo-credentials.txt').read_text()
    results, durations = [], []
    artifact = ROOT / 'artifacts' / 'phase2-live-evaluation.json'

    def record(name, checks, response=None):
        item = {'case': name, 'checks': checks, 'passed': all(checks.values())}
        if response is not None:
            item['response'] = response
        results.append(item)
        artifact.write_text(json.dumps({'model': settings.model, 'embedding_model': settings.embed_model, 'prompt_version': settings.prompt_version, 'results': results, 'generation_seconds': durations, 'summary': {'passed': sum(r['passed'] for r in results), 'failed': sum(not r['passed'] for r in results), 'median_generation_seconds': round(statistics.median(durations), 2) if durations else None}}, indent=2), encoding='utf-8')
        print(f"{'PASS' if item['passed'] else 'FAIL'} {name}: {checks}", flush=True)

    with ExitStack() as stack:
        clients = {}
        for name in ['employee', 'admin', 'manager', 'hr']:
            client = stack.enter_context(httpx.Client(base_url='http://127.0.0.1:8765', timeout=780, trust_env=False, headers={'X-Copilot-Request': '1'}))
            password = re.findall(r'^' + name + r': (\S+)', credentials, re.M)[-1]
            client.post('/api/login', json={'username': name, 'password': password}).raise_for_status()
            clients[name] = client
        employee, admin, manager, hr = (clients[k] for k in ['employee', 'admin', 'manager', 'hr'])
        health = employee.get('/api/health').json()
        assert health['phase'] >= 2 and health['status'] == 'ready' and health['model'] == settings.model

        def action(message):
            payload = {'message': message, 'mode': 'agent', 'request_id': str(uuid.uuid4())}
            started = time.perf_counter()
            response = employee.post('/api/chat', json=payload)
            durations.append(round(time.perf_counter() - started, 2))
            response.raise_for_status()
            return payload, response.json()

        payload, ticket = action('Create a support ticket for my docking station screen disconnecting during a Phase 2 demo.')
        overview = employee.get('/api/operations').json()
        actual = next((t for t in overview['tickets'] if t['workflow_id'] == ticket['workflow_id']), None)
        record('routine_ticket_actual_record', {'completed': ticket['status'] == 'completed', 'one_real_ticket': actual is not None, 'original_details': bool(actual and actual['description'] == payload['message']), 'normal_priority': bool(actual and actual['priority'] == 'normal')}, ticket)
        replay = employee.post('/api/chat', json=payload).json()
        changed = employee.post('/api/chat', json={**payload, 'message': 'Create a support ticket for another issue.'})
        record('idempotent_replay_and_input_binding', {'same_ticket': replay.get('ticket', {}).get('id') == ticket.get('ticket', {}).get('id'), 'changed_input_rejected': changed.status_code == 400, 'exactly_one': sum(t['workflow_id'] == ticket['workflow_id'] for t in employee.get('/api/operations').json()['tickets']) == 1})
        ticket_id = ticket['ticket']['id']
        started = employee.patch('/api/tickets/' + ticket_id, json={'status': 'in_progress', 'expected_status': 'open'})
        stale = employee.patch('/api/tickets/' + ticket_id, json={'status': 'resolved', 'expected_status': 'open'})
        resolved = employee.patch('/api/tickets/' + ticket_id, json={'status': 'resolved', 'expected_status': 'in_progress'})
        record('ticket_lifecycle', {'started': started.status_code == 200, 'stale_rejected': stale.status_code == 400, 'resolved': resolved.status_code == 200})

        _, risky = action('Create a critical support ticket for a simulated production outage in the Phase 2 demo.')
        aid = risky.get('approval_id')
        own = employee.post(f'/api/approvals/{aid}/decision', json={'decision': 'approve', 'reason': 'Self approval attempt'})
        outside = manager.post(f'/api/approvals/{aid}/decision', json={'decision': 'approve', 'reason': 'Wrong department attempt'})
        rejected = admin.post(f'/api/approvals/{aid}/decision', json={'decision': 'reject', 'reason': 'Synthetic review: no real production outage exists.'})
        record('risky_request_rejected_safely', {'paused': risky['status'] == 'waiting_approval', 'no_ticket_before': 'ticket' not in risky, 'self_denied': own.status_code == 403, 'other_department_denied': outside.status_code == 403, 'rejected': rejected.status_code == 200 and rejected.json()['status'] == 'rejected', 'no_ticket_after': not any(t['workflow_id'] == risky['workflow_id'] for t in employee.get('/api/operations').json()['tickets'])}, risky)

        payload, access = action('Request access to the network planning workspace for a Phase 2 demo project.')
        identity = employee.get('/api/me').json()
        decision = {'decision': 'approve', 'reason': 'Synthetic review complete; create a local review ticket only.'}
        approved = admin.post(f"/api/approvals/{access.get('approval_id')}/decision", json=decision)
        approved.raise_for_status()
        body = approved.json()
        repeated = admin.post(f"/api/approvals/{access['approval_id']}/decision", json=decision).json()
        messages = employee.get('/api/conversations/' + access['conversation_id']).json()
        record('approved_access_is_ticket_only', {'paused_first': access['status'] == 'waiting_approval', 'review_ticket': body['ticket']['category'] == 'access_review', 'identity_unchanged': employee.get('/api/me').json() == identity, 'states_updated': messages[-1]['metadata']['status'] == 'completed', 'decision_replay_same_ticket': repeated['ticket']['id'] == body['ticket']['id'], 'one_ticket': sum(t['workflow_id'] == access['workflow_id'] for t in employee.get('/api/operations').json()['tickets']) == 1}, body)

        _, report_result = action('Generate a report on annual leave entitlement for permanent employees, approval, and the notice period.')
        report_id = report_result.get('report', {}).get('id')
        report_response = employee.get('/api/reports/' + str(report_id))
        report = report_response.json()
        text = report_result['answer'].lower()
        counts = Counter((t['status'], t['priority']) for t in employee.get('/api/operations').json()['tickets'])
        saved = {(row['status'], row['priority']): row['count'] for row in report.get('metadata', {}).get('ticket_counts', [])}
        citations = report_result.get('citations', [])
        record('grounded_report_and_sql_snapshot', {'saved': report_response.status_code == 200 and report_id is not None, 'entitlement_correct': '25' in text and 'working' in text, 'approval_correct': 'manager' in text, 'notice_correct': '10' in text and 'working' in text, 'source_correct': any(c['filename'] == 'annual_leave.md' for c in citations), 'quotes_exact': bool(citations) and all(' '.join(c['quote'].casefold().split()) in ' '.join(c['text'].casefold().split()) for c in citations), 'sql_counts_match': saved == dict(counts), 'download_matches': employee.get(f'/api/reports/{report_id}/download').text == report.get('markdown'), 'other_user_denied': hr.get(f'/api/reports/{report_id}').status_code == 403, 'admin_denied_private_report': admin.get(f'/api/reports/{report_id}').status_code == 403}, report_result)
        if report_id:
            (ROOT / 'artifacts' / 'phase2-sample-report.md').write_text(report.get('markdown', ''), encoding='utf-8')

        employee_view = employee.get('/api/operations').json()
        manager_view = manager.get('/api/operations').json()
        hr_view = hr.get('/api/operations').json()
        new_ids = {ticket['workflow_id'], risky['workflow_id'], access['workflow_id'], report_result['workflow_id']}
        record('scope_and_terminal_workflow_consistency', {'employee_has_all_workflows': new_ids <= {w['id'] for w in employee_view['workflows']}, 'other_department_tickets_hidden': not any(t['workflow_id'] in new_ids for t in manager_view['tickets']), 'other_employee_tickets_hidden': not any(t['workflow_id'] in new_ids for t in hr_view['tickets']), 'no_running_workflows': not any(w['status'] == 'running' for w in employee_view['workflows'] if w['id'] in new_ids)})
    raise SystemExit(0 if all(r['passed'] for r in results) else 1)


if __name__ == '__main__':
    main()
