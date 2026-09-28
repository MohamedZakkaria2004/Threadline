"""Phase 1 review: fault injection and response-contract regressions."""
import json
import sqlite3
import pytest
from app.knowledge import validate_answer
from app.schemas import ChatRequest, GroundedAnswer
from conftest import ask, login, upload


def fail_audit_event(store, event):
    with store.connect() as conn:
        conn.execute(f"CREATE TRIGGER review_audit_failure BEFORE INSERT ON audit WHEN NEW.event='{event}' BEGIN SELECT RAISE(FAIL, 'injected audit failure'); END")


def test_replacement_audit_failure_preserves_previous_policy(client):
    login(client)
    old = upload(client).json()
    store = client.app.state.store
    fail_audit_event(store, 'document.ingested')
    with pytest.raises(sqlite3.IntegrityError):
        client.app.state.knowledge.ingest('policy.txt', b'Employees receive 30 working days of annual leave per calendar year.', 'internal', 'admin', replaces_id=old['id'])
    assert store.one('SELECT status FROM documents WHERE id=?', (old['id'],))['status'] == 'ready'
    new = store.one('SELECT * FROM documents WHERE supersedes_id=?', (old['id'],))
    assert new['status'] == 'failed'
    assert not store.all('SELECT id FROM chunks WHERE document_id=?', (new['id'],))
    assert '25 working days' in ask(client).json()['answer']


def test_chat_completion_audit_failure_has_one_consistent_failure(client):
    login(client)
    upload(client)
    store = client.app.state.store
    fail_audit_event(store, 'chat.completed')
    with pytest.raises(sqlite3.IntegrityError):
        client.app.state.chat.chat(ChatRequest(message='How many days of annual leave?', request_id='completion-fault'), client.get('/api/me').json())
    flow = store.one('SELECT * FROM workflows')
    assert flow['status'] == 'failed'
    assert json.loads(flow['result']) == {}
    replies = store.all("SELECT * FROM messages WHERE role='assistant'")
    assert len(replies) == 1
    assert json.loads(replies[0]['metadata'])['status'] == 'failed'
    assert '25 working days' not in replies[0]['content']


def test_chat_start_audit_failure_does_not_leave_orphan_work(client):
    login(client)
    store = client.app.state.store
    fail_audit_event(store, 'chat.started')
    with pytest.raises(sqlite3.IntegrityError):
        client.app.state.chat.chat(ChatRequest(message='How many days of annual leave?', request_id='start-fault'), client.get('/api/me').json())
    assert store.all('SELECT * FROM workflows') == []
    assert store.all('SELECT * FROM conversations') == []
    assert store.all('SELECT * FROM messages') == []


def test_redacted_replay_preserves_response_identifiers(client):
    login(client)
    doc = upload(client).json()
    login(client, 'employee')
    first = ask(client, request_id='redacted-replay').json()
    client.app.state.store.run("UPDATE documents SET department='HR' WHERE id=?", (doc['id'],))
    replay = ask(client, request_id='redacted-replay').json()
    assert replay['access_changed'] and not replay['citations']
    for field in ('conversation_id', 'workflow_id', 'message_id', 'status'):
        assert replay.get(field) == first[field]
    assert '25 working days' not in json.dumps(replay)


@pytest.mark.parametrize('blank_part', ['quote', 'answer'])
def test_blank_content_is_never_grounded(blank_part):
    text = 'Employees must ask their line manager before sharing restricted documents.'
    source = {'source_id': 'S1', 'text': text}
    answer = GroundedAnswer(answer=' ' if blank_part == 'answer' else 'All employees may share documents publicly.', citations=[{'source_id': 'S1', 'quote': ' ' * 20 if blank_part == 'quote' else text}], insufficient_evidence=False)
    result = validate_answer(answer, [source])
    assert result['insufficient_evidence']
    assert not result['citations']

def test_login_audit_failure_does_not_create_a_session(client):
    import re
    from conftest import HEADERS
    store = client.app.state.store
    credentials = (client.app.state.settings.data_dir / 'demo-credentials.txt').read_text()
    password = re.search(r'^admin: (\S+)', credentials, re.M).group(1)
    fail_audit_event(store, 'auth.login')
    with pytest.raises(sqlite3.IntegrityError):
        client.post('/api/login', headers=HEADERS, json={'username':'admin','password':password})
    assert store.all('SELECT * FROM sessions') == []
