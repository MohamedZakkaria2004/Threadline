"""Publication boundary checks must catch staged secrets even after local cleanup."""
import subprocess
import pytest
from scripts.repository_check import check, inspect_content


@pytest.mark.parametrize('name', ['.env.local', 'data/copilot.db', 'artifacts/run.json', 'backup.sqlite3-wal', 'demo-credentials.txt', 'weights.gguf'])
def test_private_paths_are_rejected(name):
    assert inspect_content(name, b'placeholder')


def test_public_fixtures_and_environment_template_are_allowed():
    assert not inspect_content('.env.example', b'COPILOT_PORT=8765')
    assert not inspect_content('evaluation/audit/private.txt', b'Fictional test-only canary.')
    assert not inspect_content('artifacts/README.md', b'Local evidence is excluded.')


def test_password_scan_never_returns_the_password():
    sample = b'only-a-controlled-secret-fixture'
    reasons = inspect_content('notes.md', sample, [sample])
    assert reasons == ['matches a local demo password']
    assert sample.decode() not in repr(reasons)


def test_staged_secret_is_caught_after_working_file_is_cleaned(tmp_path):
    def git(*args):
        subprocess.run(['git', '-C', str(tmp_path), *args], check=True, capture_output=True)
    git('init', '--quiet')
    key = b'ghp_' + b'A' * 36
    (tmp_path / 'notes.txt').write_bytes(key)
    git('add', 'notes.txt')
    (tmp_path / 'notes.txt').write_text('clean')
    result = check(tmp_path)
    assert result['status'] == 'FAIL'
    assert result['issues'] == [{'file': 'notes.txt', 'version': 'index', 'problem': 'possible credential/private key signature'}]


def test_ignore_cannot_hide_already_staged_runtime_data(tmp_path):
    for args in [('init', '--quiet'),]:
        subprocess.run(['git', '-C', str(tmp_path), *args], check=True, capture_output=True)
    (tmp_path / '.env').write_text('LOCAL_SETTING=example')
    subprocess.run(['git', '-C', str(tmp_path), 'add', '.env'], check=True, capture_output=True)
    (tmp_path / '.gitignore').write_text('.env\n')
    assert check(tmp_path)['status'] == 'FAIL'


def test_ignored_link_target_fails_even_when_it_exists_locally(tmp_path):
    subprocess.run(['git', '-C', str(tmp_path), 'init', '--quiet'], check=True, capture_output=True)
    (tmp_path / '.gitignore').write_text('local.txt\n')
    (tmp_path / 'local.txt').write_text('local result')
    (tmp_path / 'README.md').write_text('[Evidence](local.txt)')
    result = check(tmp_path)
    assert result['issues'][0]['problem'] == 'local link target is not in the publication set'
