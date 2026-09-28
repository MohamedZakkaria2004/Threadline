import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.storage import Store, password_hash
from conftest import FakeLLM, HEADERS, login, upload, ask


def test_auth_required_on_all_data_routes(client):
    for path in ['/api/me', '/api/documents', '/api/documents/random', '/api/conversations', '/api/conversations/random']:
        assert client.get(path).status_code == 401
    assert ask(client).status_code == 401
    assert upload(client).status_code == 401


def test_random_passwords_and_cookie_security(client):
    users = client.app.state.store.all('SELECT * FROM users')
    assert len(users) == 4
    assert len({u['password_hash'] for u in users}) == 4
    for user in users:
        assert password_hash('local-demo-2026', user['salt']) != user['password_hash']
    response = login(client)
    cookie = response.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'samesite=strict' in cookie
    assert 'password' not in response.json() and 'salt' not in response.json()


def test_bad_password_and_sql_injection_login(client):
    for username in ['admin', "' OR 1=1--", 'unknown']:
        response = client.post('/api/login', headers=HEADERS, json={'username': username, 'password': 'wrong'})
        assert response.status_code == 401


def test_login_rate_limit(client):
    for _ in range(8):
        assert client.post('/api/login', headers=HEADERS, json={'username': 'admin', 'password': 'wrong'}).status_code == 401
    assert client.post('/api/login', headers=HEADERS, json={'username': 'admin', 'password': 'wrong'}).status_code == 429


def test_logout_and_expired_session(client):
    login(client)
    assert client.post('/api/logout', headers=HEADERS).status_code == 200
    assert client.get('/api/me').status_code == 401
    login(client)
    client.app.state.store.run('UPDATE sessions SET expires_at=?', (time.time() - 1,))
    assert client.get('/api/me').status_code == 401


def test_csrf_host_and_response_security(client):
    assert client.post('/api/login', json={'username': 'admin', 'password': 'x'}).status_code == 403
    assert client.post('/api/login', headers={**HEADERS, 'Origin': 'https://evil.example'}, json={'username': 'admin', 'password': 'x'}).status_code == 403
    assert client.get('/api/health', headers={'Host': 'evil.example'}).status_code == 400
    response = client.get('/')
    assert response.status_code == 200
    assert "script-src 'self'" in response.headers['content-security-policy']
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert response.headers['cache-control'] == 'no-store'


def test_employee_cannot_upload_or_self_assign_role(client):
    login(client, 'employee')
    assert upload(client).status_code == 403
    assert client.post('/api/login', headers=HEADERS, json={'username': 'employee', 'password': 'x', 'role': 'admin'}).status_code == 422


def test_department_and_leadership_filter_before_model(client):
    login(client)
    public = upload(client).json()
    hr_doc = upload(client, 'Personnel records are retained for 7 years after departure. Only HR can see these private records.', department='HR').json()
    secret = upload(client, 'Leadership contingency reserve is AED 250000 and the secret planning code is ORBIT.', classification='leadership', department='Operations').json()
    login(client, 'employee')
    ids = {d['id'] for d in client.get('/api/documents').json()}
    assert ids == {public['id']}
    assert client.get('/api/documents/' + hr_doc['id']).status_code == 404
    assert client.get('/api/documents/' + secret['id']).status_code == 404
    result = ask(client, 'What is the contingency reserve and ORBIT?')
    assert result.status_code == 200
    calls = client.app.state.llm.calls
    generated = [json.dumps(messages) for kind, messages in calls if kind == 'generate']
    assert all('250000' not in value and 'ORBIT' not in json.loads(value)[-1]['content'].split('"evidence":')[1] for value in generated)
    login(client, 'hr')
    assert {d['id'] for d in client.get('/api/documents').json()} == {public['id'], hr_doc['id']}
    login(client, 'manager')
    assert {d['id'] for d in client.get('/api/documents').json()} == {public['id'], secret['id']}


def test_empty_library_abstains_without_calling_model(client):
    login(client, 'employee')
    result = ask(client).json()
    assert result['insufficient_evidence'] and not result['citations']
    assert client.app.state.llm.calls == []


def test_phase_one_action_boundary_does_not_claim_execution(client):
    login(client, 'employee')
    result = ask(client, 'Approve my annual leave and send an email to my manager.').json()
    assert result['action_unavailable'] and 'cannot approve' in result['answer']
    assert client.app.state.llm.calls == []


def test_ingestion_answer_quotes_and_sql_vector_join(client):
    login(client)
    doc = upload(client).json()
    result = ask(client).json()
    assert not result['insufficient_evidence']
    assert '25 working days' in result['answer']
    cite = result['citations'][0]
    assert cite['document_id'] == doc['id'] and cite['locator'] == 'Paragraph 1'
    source = client.get('/api/documents/' + doc['id']).json()['chunks'][0]
    assert cite['quote'] in source['text']
    assert cite['chunk_id'] == source['id']


def test_duplicate_upload_and_replacement_versioning(client):
    login(client)
    first = upload(client).json()
    duplicate = upload(client).json()
    assert duplicate['duplicate'] and duplicate['id'] == first['id']
    replacement = upload(client, 'Employees receive 30 working days of annual leave per calendar year. Their line manager approves leave.', replaces_id=first['id']).json()
    assert replacement['version'] == 2
    old = client.get('/api/documents/' + first['id']).json()
    assert old['document']['status'] == 'superseded'
    result = ask(client).json()
    assert '30 working days' in result['answer']
    assert all(c['document_id'] != first['id'] for c in result['citations'])


def test_replacement_access_scope_immutable(client):
    login(client)
    first = upload(client, department='HR').json()
    response = upload(client, 'The updated HR retention policy contains a different statement and is restricted to HR.', replaces_id=first['id'], department='All')
    assert response.status_code == 400
    assert client.get('/api/documents/' + first['id']).json()['document']['status'] == 'ready'


def test_failed_replacement_preserves_active_document(client):
    login(client)
    first = upload(client).json()
    client.app.state.llm.fail_embed = True
    result = upload(client, 'The new policy grants 40 working days of leave and requires approval by the manager.', replaces_id=first['id'])
    assert result.status_code == 503
    assert client.get('/api/documents/' + first['id']).json()['document']['status'] == 'ready'
    failed = [d for d in client.get('/api/documents').json() if d['status'] == 'failed']
    assert len(failed) == 1
    client.app.state.llm.fail_embed = False
    assert '25 working days' in ask(client).json()['answer']


def test_failed_upload_retry_and_filename_sanitization(client):
    login(client)
    client.app.state.llm.fail_embed = True
    assert upload(client).status_code == 503
    client.app.state.llm.fail_embed = False
    response = client.post('/api/documents', headers=HEADERS, files={'file': ('../../evil.txt', b'This is a valid policy that specifies 25 working days of annual leave.', 'text/plain')})
    assert response.status_code == 200
    assert response.json()['filename'] == 'evil.txt'
    assert len(client.app.state.knowledge.visible_documents(client.get('/api/me').json())) == 1


def test_invalid_inputs_and_no_direct_ticket_creation(client):
    login(client)
    assert ask(client, '   ').status_code == 400
    assert ask(client, 'x'*3001).status_code == 422
    assert ask(client, mode='unknown').status_code == 422
    assert client.post('/api/tickets', headers=HEADERS, json={}).status_code == 404
    assert upload(client, classification='public').status_code == 400
    assert upload(client, department='Finance').status_code == 400
    assert client.post('/api/documents', headers=HEADERS, files={'file': ('code.exe', b'Long enough data but this is not a supported document file.', 'application/octet-stream')}).status_code == 400


def test_request_body_limits(client):
    login(client)
    assert client.post('/api/chat', headers=HEADERS, content=b'X'*33000).status_code == 413
    assert client.post('/api/documents', headers=HEADERS, files={'file': ('large.txt', b'X'*(10*1024*1024+1), 'text/plain')}).status_code == 400


def test_conversation_ownership_and_idempotency(client):
    login(client)
    upload(client)
    result = ask(client, request_id='same-request-001').json()
    again = ask(client, request_id='same-request-001').json()
    assert again['message_id'] == result['message_id']
    rows = client.get('/api/conversations/' + result['conversation_id']).json()
    assert len(rows) == 2
    assert ask(client, 'A different question?', request_id='same-request-001').status_code == 400
    login(client, 'employee')
    assert client.get('/api/conversations/' + result['conversation_id']).status_code == 404
    assert ask(client, conversation_id=result['conversation_id']).status_code == 403
    assert client.get('/api/conversations').json() == []


def test_followup_history_and_new_topic_query(client):
    login(client)
    upload(client)
    result = ask(client).json()
    follow = ask(client, 'Who approves it?', conversation_id=result['conversation_id'])
    assert follow.status_code == 200
    queries = [texts[0] for kind, texts in client.app.state.llm.calls if kind == 'embed']
    assert 'Follow-up: Who approves it?' in queries[-1]
    new_topic = ask(client, 'What is the VPN policy?', conversation_id=result['conversation_id']).json()
    queries = [texts[0] for kind, texts in client.app.state.llm.calls if kind == 'embed']
    assert queries[-1] == 'What is the virtual private network policy?'
    assert 'Follow-up:' not in queries[-1] and 'leave' not in queries[-1]
    assert new_topic['insufficient_evidence']
    upload(client, 'The virtual private network (VPN) policy requires multi-factor authentication for remote network access. IT approves VPN access.')
    supported = ask(client, 'What is the VPN policy?', conversation_id=result['conversation_id']).json()
    assert not supported['insufficient_evidence'] and 'VPN' in supported['answer']
    generations = [messages for kind, messages in client.app.state.llm.calls if kind == 'generate']
    assert json.loads(generations[-1][-1]['content'])['question'] == 'What is the VPN policy?'


def test_saved_answer_redacts_revoked_evidence(client):
    login(client)
    doc = upload(client).json()
    login(client, 'employee')
    result = ask(client).json()
    client.app.state.store.run("UPDATE documents SET department='HR' WHERE id=?", (doc['id'],))
    rows = client.get('/api/conversations/' + result['conversation_id']).json()
    assert '25 working days' not in json.dumps(rows)
    assert rows[-1]['metadata']['access_changed']
    replay = ask(client, request_id=client.app.state.store.one('SELECT request_id FROM workflows WHERE id=?', (result['workflow_id'],))['request_id']).json()
    assert replay['access_changed'] and not replay['citations']


def test_history_marks_superseded_policy(client):
    login(client)
    doc = upload(client).json()
    result = ask(client).json()
    upload(client, 'Employees receive 30 working days of annual leave per calendar year. Their line manager approves leave.', replaces_id=doc['id'])
    rows = client.get('/api/conversations/' + result['conversation_id']).json()
    assert rows[-1]['metadata']['historical_sources']


def test_model_failure_saved_and_retryable(client):
    login(client)
    upload(client)
    client.app.state.llm.fail_generate = True
    assert ask(client, request_id='failed-request-01').status_code == 503
    workflow = client.app.state.store.one('SELECT * FROM workflows')
    assert workflow['status'] == 'failed'
    assert len(client.get('/api/conversations/' + workflow['conversation_id']).json()) == 2
    assert ask(client, request_id='failed-request-01').status_code == 400
    client.app.state.llm.fail_generate = False
    assert ask(client).status_code == 200


def test_busy_request_fails_cleanly(client):
    login(client)
    with client.app.state.work_lock:
        assert client.get('/api/health').json()['status'] == 'busy'
        assert ask(client).status_code == 409
        assert upload(client).status_code == 409
    assert client.get('/api/conversations').json() == []


@pytest.mark.parametrize('interruption_status', ['running', 'failed'])
def test_restart_persistence_and_interrupted_recovery(tmp_path, interruption_status):
    settings = Settings(data_dir=tmp_path)
    with TestClient(create_app(settings, llm_factory=FakeLLM)) as first:
        login(first)
        doc = upload(first).json()
        result = ask(first).json()
        # Simulate a crash after saving the question but before committing an answer.
        first.app.state.store.run('DELETE FROM messages WHERE id=?', (result['message_id'],))
        first.app.state.store.run("UPDATE workflows SET status=? WHERE id=?", (interruption_status, result['workflow_id']))
    with TestClient(create_app(settings, llm_factory=FakeLLM)) as second:
        login(second)
        assert second.app.state.store.one('SELECT status FROM workflows WHERE id=?', (result['workflow_id'],))['status'] == 'failed'
        assert second.get('/api/documents/' + doc['id']).status_code == 200
        messages = second.get('/api/conversations/' + result['conversation_id']).json()
        assert len(messages) == 2
        assert messages[-1]['metadata']['interrupted']
        assert 'interrupted' in messages[-1]['content']
        assert '25 working days' in ask(second).json()['answer']
    with TestClient(create_app(settings, llm_factory=FakeLLM)) as third:
        login(third)
        assert len(third.get('/api/conversations/' + result['conversation_id']).json()) == 2


def test_vector_payload_cannot_override_sql_evidence(client):
    from qdrant_client import models
    login(client)
    doc = upload(client).json()
    chunk = client.app.state.store.one('SELECT id FROM chunks WHERE document_id=?', (doc['id'],))
    k = client.app.state.knowledge
    k.client.set_payload(k.collection, {'text': 'Forged evidence grants 999 leave days.', 'classification': 'internal'}, [chunk['id']])
    result = ask(client).json()
    assert '999' not in result['answer']
    assert '25 working days' in result['answer']


def test_loopback_configuration_required(tmp_path):
    with pytest.raises(ValueError):
        Settings(data_dir=tmp_path, ollama_url='https://remote.example')
    with pytest.raises(ValueError):
        Settings(data_dir=tmp_path, model='qwen:cloud')
    with pytest.raises(ValueError):
        Settings(data_dir=tmp_path, prompt_version='../secret')

@pytest.mark.parametrize('extension', ['pdf', 'docx'])
def test_document_format_full_ingestion(client, extension):
    from test_knowledge import pdf_bytes, docx_bytes, TEXT
    login(client)
    content = pdf_bytes(TEXT) if extension == 'pdf' else docx_bytes(TEXT)
    response = client.post('/api/documents', headers=HEADERS, files={'file': ('policy.' + extension, content, 'application/octet-stream')})
    assert response.status_code == 200
    result = ask(client).json()
    assert not result['insufficient_evidence']
    assert '25 working days' in result['answer']
    assert result['citations'][0]['locator'] == ('Page 1' if extension == 'pdf' else 'Paragraph 1')


def test_second_store_cannot_interrupt_active_application(client):
    from app.knowledge import Knowledge
    login(client)
    upload(client)
    result = ask(client).json()
    store = client.app.state.store
    store.run("UPDATE workflows SET status='running' WHERE id=?", (result['workflow_id'],))
    second_store = Store(client.app.state.settings.data_dir / 'copilot.db')
    with pytest.raises(RuntimeError, match='already accessed'):
        Knowledge(client.app.state.settings, second_store, client.app.state.llm)
    assert store.one('SELECT status FROM workflows WHERE id=?', (result['workflow_id'],))['status'] == 'running'
    assert len(client.get('/api/conversations/' + result['conversation_id']).json()) == 2
