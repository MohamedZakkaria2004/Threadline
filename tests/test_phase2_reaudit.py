"""Additional Phase 2 review: authorization changes during slow generation."""
import json
import pytest
from conftest import ask, login, upload


@pytest.mark.parametrize('mode', ['ask', 'agent'])
@pytest.mark.parametrize('changed', ['user', 'document'])
def test_access_revoked_during_generation_never_returns_or_saves_evidence(client, monkeypatch, mode, changed):
    login(client)
    source = upload(client, department='IT').json()
    login(client, 'employee')
    original = client.app.state.llm.structured
    store = client.app.state.store

    def generate_and_revoke(*args, **kwargs):
        result = original(*args, **kwargs)
        if args[2] == 'answer':
            if changed == 'user':
                store.run("UPDATE users SET department='HR' WHERE id='employee'")
            else:
                store.run("UPDATE documents SET department='HR' WHERE id=?", (source['id'],))
        return result

    monkeypatch.setattr(client.app.state.llm, 'structured', generate_and_revoke)
    question = 'Generate a report on annual leave.' if mode == 'agent' else 'How many days of annual leave?'
    response = ask(client, question, mode=mode)
    if mode == 'agent':
        assert response.status_code == 403
        assert store.one('SELECT COUNT(*) AS n FROM reports')['n'] == 0
    else:
        assert response.status_code == 200
        assert response.json()['access_changed']
        assert response.json()['citations'] == []
    assert '25 working days' not in response.text
    for message in store.all("SELECT content,metadata FROM messages WHERE role='assistant'"):
        assert '25 working days' not in json.dumps(message)
    assert '25 working days' not in store.one('SELECT result FROM workflows')['result']
