"""Phase 3 contracts: denominators, privacy, evaluation state, and cost math."""
import hashlib
import json
import pytest
from app.business import calculate
from app.config import ROOT
from app.evaluation import CASES, FILES, grade, summarize
from app.insights import percentile
from app.schemas import BusinessInputs, QualityReview
from app.storage import dump, now, uid
from conftest import HEADERS, ask, login, upload


def seed_benchmark(client):
    for filename in FILES:
        client.app.state.knowledge.ingest(filename, (ROOT / 'sample_docs' / filename).read_bytes(), 'internal', 'admin', department='All')


def flow(store, user='employee', status='completed', mode='ask', result=None):
    identity = uid()
    store.run('INSERT INTO workflows(id,request_id,user_id,input,status,result,created_at,updated_at,mode) VALUES (?,?,?,?,?,?,?,?,?)', (identity, identity, user, 'PRIVATE QUESTION MUST NOT APPEAR', status, dump(result or {}), now(), now(), mode))
    return identity


def test_monitoring_scope_denominators_and_no_content_leak(client):
    store = client.app.state.store
    flow(store, result={'latency_ms': 1000, 'citations': [{'text': 'PRIVATE EVIDENCE'}], 'answer': 'PRIVATE ANSWER'})
    flow(store, result={'latency_ms': 3000, 'insufficient_evidence': True})
    flow(store, status='failed')
    flow(store, status='rejected', mode='agent', result={'latency_ms': 2000})
    flow(store, status='waiting_approval', mode='agent')
    flow(store, user='hr', result={'latency_ms': 9000})
    login(client, 'employee')
    result = client.get('/api/insights').json()
    assert result['requests'] == 5 and result['terminal_requests'] == 4
    assert result['failure_rate_percent'] == 25
    assert result['latency'] == {'samples': 3, 'p50_seconds': 2, 'p95_seconds': 3}
    assert result['knowledge']['abstention_percent'] == 50
    assert result['feedback']['helpful_percent'] is None
    assert 'PRIVATE' not in dump(result)
    assert client.get('/api/insights?scope=platform').status_code == 403
    login(client)
    platform = client.get('/api/insights?scope=platform').json()
    assert platform['requests'] == 6 and platform['active_users'] == 2
    assert 'PRIVATE' not in dump(platform)


def test_monitoring_ignores_evaluation_calls_and_does_not_sum_latency(client):
    store = client.app.state.store
    flow_id = flow(store, result={'latency_ms': 3000})
    for operation, latency, tokens, energy, workflow in [('retrieval', 1000, 0, 0, flow_id), ('answer', 2000, 100, .001, flow_id), ('answer_repair', 500, 50, .0005, flow_id), ('answer', 9999, 999, 1, 'eval:test')]:
        store.run('INSERT INTO metrics(workflow_id,user_id,operation,latency_ms,prompt_tokens,output_tokens,model,prompt_version,status,estimated_energy_usd,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)', (workflow, 'employee', operation, latency, tokens, tokens, 'local', 'v3', 'ok', energy, now()))
    login(client, 'employee')
    result = client.get('/api/insights').json()
    assert result['latency']['p50_seconds'] == 3
    assert result['generation']['calls'] == 2
    assert result['generation']['output_tokens'] == 150
    assert result['generation']['estimated_electricity_usd'] == .0015


def test_empty_summary_and_bounded_query(client):
    login(client, 'employee')
    summary = client.get('/api/insights').json()
    assert summary['requests'] == 0 and summary['failure_rate_percent'] is None
    assert summary['latency']['p95_seconds'] is None
    for query in ['days=0', 'days=9999', 'scope=department']:
        assert client.get('/api/insights?' + query).status_code == 422


def test_monitoring_window_uses_utc_time(client):
    store = client.app.state.store
    identity = flow(store)
    store.run("UPDATE workflows SET created_at='2000-01-01T00:00:00+00:00' WHERE id=?", (identity,))
    login(client, 'employee')
    assert client.get('/api/insights?days=90').json()['requests'] == 0


def test_feedback_ownership_update_persistence_and_revocation(client):
    login(client)
    doc = upload(client, department='IT').json()
    login(client, 'employee')
    answer = ask(client).json()
    path = '/api/messages/' + answer['message_id'] + '/feedback'
    for rating in ['helpful', 'unhelpful']:
        assert client.put(path, headers=HEADERS, json={'rating': rating}).status_code == 200
    assert client.app.state.store.one('SELECT count(*) AS n FROM feedback')['n'] == 1
    assert client.get('/api/insights').json()['feedback'] == {'rated': 1, 'helpful': 0, 'helpful_percent': 0}
    messages = client.get('/api/conversations/' + answer['conversation_id']).json()
    assert messages[-1]['metadata']['feedback'] == 'unhelpful'
    login(client)
    assert client.put(path, headers=HEADERS, json={'rating': 'helpful'}).status_code == 403
    login(client, 'employee')
    client.app.state.store.run("UPDATE documents SET department='HR' WHERE id=?", (doc['id'],))
    assert client.put(path, headers=HEADERS, json={'rating': 'helpful'}).status_code == 400


def test_feedback_failure_rolls_back_vote(client, monkeypatch):
    login(client)
    upload(client)
    result = ask(client).json()
    store = client.app.state.store
    original = store.audit
    def audit(user_id, event, *args, **kwargs):
        if event == 'answer.feedback':
            raise RuntimeError('test audit failure')
        return original(user_id, event, *args, **kwargs)
    monkeypatch.setattr(store, 'audit', audit)
    with pytest.raises(RuntimeError):
        client.put('/api/messages/' + result['message_id'] + '/feedback', headers=HEADERS, json={'rating': 'helpful'})
    assert store.all('SELECT * FROM feedback') == []


def test_phase3_auth_and_admin_boundaries(client):
    for path in ['/api/insights', '/api/evaluations', '/api/prompts', '/api/business-case']:
        assert client.get(path).status_code == 401
    login(client, 'employee')
    for path in ['/api/evaluations', '/api/evaluations/unknown', '/api/evaluations/unknown/download', '/api/prompts']:
        assert client.get(path).status_code == 403
    assert client.post('/api/evaluations', headers=HEADERS, json={'suite': 'quick'}).status_code == 403
    assert client.post('/api/evaluations/unknown/cancel', headers=HEADERS).status_code == 403
    assert client.post('/api/business-case', json={}).status_code == 403


def test_business_base_math_and_negative_scenario():
    result = calculate(BusinessInputs())['results']
    assert result['monthly_requests'] == 500 and result['monthly_hours_saved'] == 17.5
    assert result['monthly_capacity_value_usd'] == 525
    assert result['monthly_electricity_usd'] == .1875
    assert result['monthly_operating_usd'] == 100.1875
    assert result['implementation_usd'] == 600
    assert result['first_year_cost_usd'] == 1802.25
    assert result['first_year_net_value_usd'] == 4497.75
    assert result['payback_months'] == pytest.approx(600 / (525 - 100.1875), abs=.0001)
    assert calculate(BusinessInputs(adoption=0))['results']['payback_months'] is None
    assert calculate(BusinessInputs(developer_hourly_usd=0, electricity_usd_kwh=0))['results']['first_year_roi_percent'] is None


@pytest.mark.parametrize('values', [{'adoption': 1.1}, {'minutes_saved': -1}, {'employees': 0}, {'power_watts': float('inf')}, {'inference_seconds': float('nan')}])
def test_business_invalid_assumptions_rejected(values):
    with pytest.raises(ValueError):
        BusinessInputs(**values)


def test_percentiles_are_nearest_rank_and_empty_is_unknown():
    assert percentile([], .95) is None
    assert percentile([10, 20, 30, 40], .5) == 20
    assert percentile([10, 20, 30, 40], .95) == 40


def test_benchmark_requires_exact_fixtures_and_releases_busy_lock(client):
    login(client)
    response = client.post('/api/evaluations', headers=HEADERS, json={'suite': 'quick'})
    assert response.status_code == 400
    assert client.app.state.store.all('SELECT * FROM evaluations') == []
    assert not client.app.state.work_lock.locked()


def test_benchmark_is_serialized_and_persists_partial_results(client):
    login(client)
    seed_benchmark(client)
    lock = client.app.state.work_lock
    lock.acquire()
    try:
        assert client.post('/api/evaluations', headers=HEADERS, json={'suite': 'quick'}).status_code == 409
    finally:
        lock.release()
    result = client.post('/api/evaluations', headers=HEADERS, json={'suite': 'quick'})
    assert result.status_code == 202
    run = client.get('/api/evaluations/' + result.json()['id']).json()
    assert run['status'] == 'completed' and run['summary']['finished'] == 3
    assert run['summary']['human_incorrect_percent'] is None
    assert not lock.locked()
    assert client.app.state.store.all('SELECT * FROM conversations') == []
    assert client.app.state.store.all('SELECT * FROM tickets') == []
    assert client.get('/api/evaluations/' + run['id'] + '/download').json()['id'] == run['id']


def test_benchmark_only_retrieves_allowlisted_fixtures(client):
    login(client)
    seed_benchmark(client)
    extra = upload(client, 'The CEO is PRIVATE CANARY. Employees receive 99 working days of annual leave.').json()
    run = client.post('/api/evaluations', headers=HEADERS, json={'suite': 'quick'}).json()
    saved = client.get('/api/evaluations/' + run['id']).json()
    assert 'PRIVATE CANARY' not in dump(saved)
    for item in saved['results']:
        assert all(c['document_id'] != extra['id'] for c in item['answer']['citations'])


def test_benchmark_model_error_is_visible_and_does_not_fake_a_pass(client):
    login(client)
    seed_benchmark(client)
    client.app.state.llm.fail_generate = True
    run = client.post('/api/evaluations', headers=HEADERS, json={'suite': 'quick'}).json()
    saved = client.get('/api/evaluations/' + run['id']).json()
    assert saved['status'] == 'failed'
    assert saved['summary']['finished'] == 0 and saved['summary']['automated_pass_percent'] is None
    assert saved['summary']['error'] and not client.app.state.work_lock.locked()


def test_benchmark_cancel_and_restart_do_not_silently_resume(client):
    login(client)
    seed_benchmark(client)
    evaluator = client.app.state.evaluator
    user = client.get('/api/me').json()
    run = evaluator.start('full', user)
    evaluator.cancel(run['id'], user)
    evaluator.run(run['id'])
    assert evaluator.get(run['id'])['status'] == 'cancelled'
    assert evaluator.get(run['id'])['results'] == []
    interrupted = evaluator.start('full', user)
    client.app.state.store.recover_interrupted()
    assert evaluator.get(interrupted['id'])['status'] == 'interrupted'


def test_benchmark_human_review_is_distinct_and_persistent(client):
    login(client)
    seed_benchmark(client)
    run = client.post('/api/evaluations', headers=HEADERS, json={'suite': 'quick'}).json()
    path = '/api/evaluations/' + run['id'] + '/cases/annual_leave/review'
    response = client.put(path, headers=HEADERS, json={'verdict': 'incorrect', 'note': 'Test judgment: one fact is incorrect.'})
    assert response.status_code == 200
    summary = response.json()['summary']
    assert summary['human_reviewed'] == 1 and summary['human_incorrect_percent'] == 100
    assert summary['passed'] == client.get('/api/evaluations/' + run['id']).json()['summary']['passed']
    assert client.put(path, headers=HEADERS, json={'verdict': 'correct', 'note': '   '}).status_code == 400


def test_grader_detects_wrong_source_and_forbidden_claim():
    case = CASES[1]
    answer = {'answer': 'Finance reviews receipts; the line manager approves business purpose before travel and annual leave.', 'citations': [{'filename': 'annual_leave.md', 'quote': 'annual leave', 'text': 'annual leave'}], 'insufficient_evidence': False}
    checks = grade(case, answer)
    assert not checks['no_forbidden_claims'] and not checks['expected_source']


def test_human_uncertain_is_not_a_correct_answer():
    result = summarize([{'passed': True, 'seconds': 1, 'review': {'verdict': 'uncertain'}}], 8)
    assert result['human_reviewed'] == 1 and result['human_correct'] == 0
    assert result['human_incorrect_percent'] is None
    assert result['finished'] == 1 and result['total'] == 8


def test_prompt_inventory_matches_local_bytes(client):
    login(client)
    body = client.get('/api/prompts').json()
    assert body['active_version'] == client.app.state.settings.prompt_version
    for item in body['templates']:
        assert item['sha256'] == hashlib.sha256((ROOT / 'prompts' / item['version'] / (item['name'] + '.txt')).read_bytes()).hexdigest()


def test_benchmark_final_audit_failure_is_visible_and_releases_lock(client, monkeypatch):
    login(client)
    seed_benchmark(client)
    original = client.app.state.store.audit
    def audit(user_id, event, *args, **kwargs):
        if event == 'evaluation.completed':
            raise RuntimeError('injected final audit failure')
        return original(user_id, event, *args, **kwargs)
    monkeypatch.setattr(client.app.state.store, 'audit', audit)
    started = client.post('/api/evaluations', headers=HEADERS, json={'suite': 'quick'}).json()
    run = client.get('/api/evaluations/' + started['id']).json()
    assert run['status'] == 'failed' and 'audit' in run['summary']['error']
    assert run['summary']['finished'] == 3
    assert not client.app.state.work_lock.locked()


def test_benchmark_review_rechecks_current_role(client):
    login(client)
    seed_benchmark(client)
    user = client.get('/api/me').json()
    evaluator = client.app.state.evaluator
    run = evaluator.start('quick', user)
    evaluator.run(run['id'])
    client.app.state.store.run("UPDATE users SET role='employee' WHERE id='admin'")
    with pytest.raises(PermissionError):
        evaluator.review(run['id'], 'annual_leave', QualityReview(verdict='correct', note='Checked the source.'), user)
    assert evaluator.get(run['id'])['summary']['human_reviewed'] == 0


@pytest.mark.parametrize('word,expected', [('receipt', True), ('receipts', True), ('receiptless', False)])
def test_receipt_grader_accepts_plural_but_not_substrings(word, expected):
    case = next(c for c in CASES if c['id'] == 'receipts')
    answer = {'answer': 'No, an itemized ' + word + ' is required.', 'citations': [{'filename': 'travel_expenses.md', 'quote': 'Itemized receipts are required.', 'text': 'Itemized receipts are required.'}], 'insufficient_evidence': False}
    assert grade(case, answer)['expected_terms'] is expected


def test_legacy_evaluation_export_is_preserved_but_review_is_rejected(client):
    login(client)
    identity = uid()
    client.app.state.store.run('INSERT INTO evaluations(id,status,results,summary,created_at) VALUES (?,?,?,?,?)', (identity, 'completed', '[{"question":"Legacy format"}]', '{}', now()))
    assert client.get('/api/evaluations/' + identity + '/download').json()['results'] == [{'question': 'Legacy format'}]
    response = client.put('/api/evaluations/' + identity + '/cases/annual_leave/review', headers=HEADERS, json={'verdict': 'correct', 'note': 'Must not reinterpret historical format.'})
    assert response.status_code == 400 and 'read-only' in response.json()['detail']
