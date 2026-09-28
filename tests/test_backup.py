import json
import sqlite3
import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from scripts.backup import create, restore, verify
from conftest import FakeLLM, login, upload


def test_running_store_cannot_be_backed_up(client, tmp_path):
    target = tmp_path.parent / (tmp_path.name + '-snapshot')
    with pytest.raises(ValueError, match='Stop Atlas'):
        create(client.app.state.settings.data_dir, target)
    assert not target.exists()


def closed_store(tmp_path):
    settings = Settings(data_dir=tmp_path / 'source')
    with TestClient(create_app(settings, llm_factory=FakeLLM)) as client:
        login(client)
        doc = upload(client).json()
    return settings.data_dir, doc['id']


def test_snapshot_restore_preserves_sql_vectors_and_invalidates_sessions(tmp_path):
    source, doc = closed_store(tmp_path)
    snapshot = create(source, tmp_path / 'snapshot')
    manifest = verify(snapshot)
    assert 'copilot.db' in manifest['files'] and any(p.startswith('vectors/') for p in manifest['files'])
    restored = restore(snapshot, tmp_path / 'restored')
    with sqlite3.connect(restored / 'copilot.db') as conn:
        assert conn.execute('SELECT count(*) FROM sessions').fetchone()[0] == 0
    with TestClient(create_app(Settings(data_dir=restored), llm_factory=FakeLLM)) as client:
        login(client)
        assert client.get('/api/documents').json()[0]['id'] == doc
        rows = client.app.state.knowledge.search('annual leave', {'id': 'admin', 'role': 'admin', 'department': 'IT'})
        assert rows and rows[0]['document_id'] == doc
    assert verify(snapshot) == manifest


@pytest.mark.parametrize('change', ['corrupt', 'extra', 'unsafe'])
def test_bad_snapshot_refuses_restore_before_creating_target(tmp_path, change):
    source, _ = closed_store(tmp_path)
    snapshot = create(source, tmp_path / 'snapshot')
    if change == 'corrupt':
        (snapshot / 'payload' / 'demo-credentials.txt').write_text('corrupt')
    elif change == 'extra':
        (snapshot / 'payload' / 'extra.txt').write_text('untracked')
    else:
        path = snapshot / 'manifest.json'
        manifest = json.loads(path.read_text())
        manifest['files']['../escape'] = 'not-a-digest'
        path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        restore(snapshot, tmp_path / 'refused')
    assert not (tmp_path / 'refused').exists()


def test_snapshot_and_restore_never_overwrite_or_nest_in_active_store(tmp_path):
    source, _ = closed_store(tmp_path)
    with pytest.raises(ValueError):
        create(source, source / 'nested')
    snapshot = create(source, tmp_path / 'snapshot')
    with pytest.raises(ValueError):
        create(source, snapshot)
    with pytest.raises(ValueError):
        restore(snapshot, source)
