"""Adversarial failure-path tests from the independent Phase 3 re-review."""
import sqlite3
import pytest
from app.config import ROOT
from app.evaluation import FILES
from conftest import HEADERS, login, upload


def prepare(client):
    login(client)
    for name in FILES:
        client.app.state.knowledge.ingest(name, (ROOT / 'sample_docs' / name).read_bytes(), 'internal', 'admin')
    return client.app.state.evaluator, client.app.state.store


@pytest.mark.parametrize('audit_failure', [False, True])
def test_failed_progress_write_keeps_summary_and_saved_results_consistent(client, monkeypatch, audit_failure):
    evaluator, store = prepare(client)
    original = store.run
    def fail_progress(sql, params=()):
        if sql.startswith('UPDATE evaluations SET results='):
            raise sqlite3.OperationalError('injected progress write failure')
        return original(sql, params)
    monkeypatch.setattr(store, 'run', fail_progress)
    original_audit = store.audit
    def audit(user_id, event, *args, **kwargs):
        if audit_failure and event == 'evaluation.failed':
            raise sqlite3.OperationalError('injected final audit failure')
        return original_audit(user_id, event, *args, **kwargs)
    monkeypatch.setattr(store, 'audit', audit)
    run = client.post('/api/evaluations', headers=HEADERS, json={'suite': 'quick'}).json()
    saved = evaluator.get(run['id'])
    assert saved['status'] == 'failed'
    assert saved['summary']['finished'] == len(saved['results']) == 1
    assert saved['summary']['error']
    assert not client.app.state.work_lock.locked()


@pytest.mark.parametrize('change', ['prompt', 'fixture', 'role'])
def test_change_during_last_case_cannot_be_published_as_unchanged_benchmark(client, monkeypatch, change):
    evaluator, store = prepare(client)
    original_answer = evaluator.chat.answer
    calls = 0
    def answer(*args, **kwargs):
        nonlocal calls
        result = original_answer(*args, **kwargs)
        calls += 1
        if calls == 3:
            if change == 'prompt':
                monkeypatch.setattr(evaluator, 'current_prompts', lambda: {'answer': 'changed-during-inference'})
            elif change == 'fixture':
                store.run("UPDATE documents SET digest='changed-during-inference' WHERE filename=?", (FILES[0],))
            else:
                store.run("UPDATE users SET role='employee' WHERE id='admin'")
        return result
    monkeypatch.setattr(evaluator.chat, 'answer', answer)
    run = client.post('/api/evaluations', headers=HEADERS, json={'suite': 'quick'}).json()
    saved = evaluator.get(run['id'])
    assert saved['status'] == 'failed'
    assert saved['summary']['finished'] == len(saved['results']) == 2
    assert saved['summary']['error']
    assert not client.app.state.work_lock.locked()


def test_sql_allowlist_rejects_vector_payload_pointing_at_another_document(client):
    evaluator, store = prepare(client)
    knowledge = client.app.state.knowledge
    text = 'CANARY ZEBRA telescope blueprint reserved project information.'
    extra = upload(client, text).json()
    point = store.one('SELECT id FROM chunks WHERE document_id=?', (extra['id'],))['id']
    fixture_id = evaluator.fixtures()[0]['id']
    # Corruption/old payload says this unrelated point belongs to a fixture.
    # The canonical SQL document id must still enforce the supplied allowlist.
    knowledge.client.set_payload(collection_name=knowledge.collection, payload={'document_id': fixture_id}, points=[point])
    result = knowledge.search(text, {'id': 'employee', 'role': 'employee', 'department': 'IT'}, document_ids=[fixture_id])
    assert all(row['document_id'] == fixture_id for row in result)
    assert all('CANARY' not in row['text'] for row in result)
