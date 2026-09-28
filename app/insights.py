"""Scoped, reproducible operational summaries; never expose conversation content."""
import json
import math
from datetime import datetime, timedelta, timezone
from .storage import now


def percentile(values, fraction):
    values = sorted(values)
    return round(values[max(0, math.ceil(len(values) * fraction) - 1)], 2) if values else None


def ratio(numerator, denominator):
    return round(100 * numerator / denominator, 2) if denominator else None


class Insights:
    def __init__(self, settings, store, chat):
        self.settings, self.store, self.chat = settings, store, chat

    def summary(self, user, days=30, scope='mine'):
        if scope == 'platform' and user['role'] != 'admin':
            raise PermissionError('Platform aggregates require an administrator.')
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        own = scope == 'mine'
        clause, params = (' AND user_id=?', (cutoff, user['id'])) if own else ('', (cutoff,))
        # A read transaction keeps all aggregate denominators in one snapshot.
        with self.store.connect() as conn:
            conn.execute('BEGIN')
            flows = [dict(r) for r in conn.execute('SELECT status,mode,tool,result,user_id,created_at FROM workflows WHERE created_at>=?' + clause, params)]
            metrics = [dict(r) for r in conn.execute("SELECT operation,latency_ms,prompt_tokens,output_tokens,estimated_energy_usd,status FROM metrics WHERE created_at>=? AND (workflow_id IS NULL OR workflow_id NOT LIKE 'eval:%')" + clause, params)]
            feedback = [dict(r) for r in conn.execute('SELECT rating FROM feedback WHERE created_at>=?' + clause, params)]
            events = [dict(r) for r in conn.execute('SELECT event,entity_id,created_at FROM audit WHERE created_at>=?' + clause + ' ORDER BY id DESC LIMIT 30', params)]
            users_total = conn.execute('SELECT count(*) FROM users').fetchone()[0]
        states = {key: sum(f['status'] == key for f in flows) for key in ['completed', 'failed', 'waiting_approval', 'running', 'rejected']}
        terminal = sum(states[k] for k in ['completed', 'failed', 'rejected'])
        answers, latencies, action_outcomes = [], [], {'created': 0, 'waiting_review': states['waiting_approval'], 'rejected': states['rejected'], 'no_artifact': 0}
        for flow in flows:
            result = json.loads(flow['result'])
            latency = result.get('latency_ms')
            if isinstance(latency, (int, float)) and math.isfinite(latency) and latency >= 0:
                latencies.append(latency / 1000)
            if flow['mode'] == 'ask' and flow['status'] == 'completed' and not result.get('action_unavailable'):
                answers.append(result)
            if flow['mode'] == 'agent' and flow['status'] == 'completed':
                action_outcomes['created' if result.get('ticket') or result.get('report') else 'no_artifact'] += 1
        generations = [m for m in metrics if m['operation'] in {'answer', 'answer_repair', 'planner'}]
        abstained = sum(bool(a.get('insufficient_evidence')) for a in answers)
        cited = sum(bool(a.get('citations')) for a in answers)
        guard_rejections = sum(bool(a.get('checks', {}).get('unsupported_numbers')) or bool(a.get('checks', {}).get('invalid_citations')) for a in answers)
        helpful = sum(f['rating'] == 'helpful' for f in feedback)
        return {
            'scope': scope, 'days': days, 'since': cutoff, 'as_of': now(), 'requests': len(flows), 'states': states,
            'failure_rate_percent': ratio(states['failed'], terminal), 'terminal_requests': terminal,
            'latency': {'samples': len(latencies), 'p50_seconds': percentile(latencies, 0.5), 'p95_seconds': percentile(latencies, 0.95)},
            'knowledge': {'answers': len(answers), 'abstained': abstained, 'cited': cited, 'guard_rejections': guard_rejections, 'abstention_percent': ratio(abstained, len(answers))},
            'actions': action_outcomes,
            'generation': {'calls': len(generations), 'errors': sum(m['status'] != 'ok' for m in generations), 'prompt_tokens': sum(m['prompt_tokens'] for m in generations), 'output_tokens': sum(m['output_tokens'] for m in generations), 'estimated_electricity_usd': round(sum(m['estimated_energy_usd'] for m in generations), 6)},
            'feedback': {'rated': len(feedback), 'helpful': helpful, 'helpful_percent': ratio(helpful, len(feedback))},
            'active_users': len({f['user_id'] for f in flows}), 'registered_users': users_total if not own else 1,
            'events': events,
            'definitions': 'Request latency uses recorded processing time, not the sum of overlapping retrieval/model calls or human review wait. Missing latency is excluded. Failure rate is failed / terminal requests; human rejection is not a system failure. Evaluation model calls are excluded. Electricity estimates cover generation only, not full hardware or operating costs. Demo/test traffic is included.'}

    def feedback(self, message_id, data, user):
        with self.store.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute("SELECT m.metadata,m.role FROM messages m JOIN conversations c ON c.id=m.conversation_id WHERE m.id=? AND c.user_id=?", (message_id, user['id'])).fetchone()
            fresh = conn.execute('SELECT id,role,department FROM users WHERE id=?', (user['id'],)).fetchone()
            if not row or row['role'] != 'assistant' or not fresh:
                raise PermissionError('Answer not found.')
            meta = self.chat.safe_result(json.loads(row['metadata']), fresh, conn=conn)
            if meta.get('access_changed') or meta.get('status') != 'completed' or meta.get('action_unavailable') or meta.get('tool') not in {'answer', 'generate_report'}:
                raise ValueError('Feedback is available for accessible completed knowledge answers and reports.')
            conn.execute('INSERT INTO feedback(message_id,user_id,rating,created_at) VALUES (?,?,?,?) ON CONFLICT(message_id) DO UPDATE SET rating=excluded.rating,created_at=excluded.created_at', (message_id, user['id'], data.rating, now()))
            self.store.audit(user['id'], 'answer.feedback', message_id, {'rating': data.rating}, conn=conn)
        return {'message_id': message_id, 'rating': data.rating}
