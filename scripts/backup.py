"""Offline local snapshots. Restore only to a new directory; never overwrite data."""
import argparse
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import uuid
import portalocker
from app.config import Settings


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def files(root):
    if root.is_symlink() or root.is_junction():
        raise ValueError('Snapshots do not follow links or junctions.')
    result = {}
    for path in root.rglob('*'):
        if path.is_symlink() or path.is_junction():
            raise ValueError('Snapshots do not follow links or junctions.')
        if path.is_file():
            result[path.relative_to(root).as_posix()] = path
    return result


@contextmanager
def offline(source):
    lock = source / 'vectors' / '.lock'
    if not (source / 'copilot.db').is_file() or not lock.is_file():
        raise ValueError('Choose an initialized Atlas data directory.')
    with lock.open('r+b') as handle:
        try:
            portalocker.lock(handle, portalocker.LOCK_EX | portalocker.LOCK_NB)
        except portalocker.LockException as exc:
            raise ValueError('Stop Atlas before taking a consistent SQL/vector snapshot.') from exc
        try:
            with closing(sqlite3.connect(source / 'copilot.db', timeout=1)) as conn:
                conn.execute('BEGIN IMMEDIATE')
                if conn.execute("SELECT count(*) FROM workflows WHERE status='running'").fetchone()[0] or conn.execute("SELECT count(*) FROM evaluations WHERE status='running'").fetchone()[0]:
                    raise ValueError('Interrupted work must be recovered by starting and cleanly stopping Atlas before backup.')
                yield
                conn.rollback()
        finally:
            portalocker.unlock(handle)


def verify(snapshot):
    snapshot = Path(snapshot).resolve()
    manifest = json.loads((snapshot / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('format') != 1 or not isinstance(manifest.get('files'), dict):
        raise ValueError('Unrecognized snapshot manifest.')
    for name in manifest['files']:
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or ':' in name or '\\' in name or not path.parts:
            raise ValueError('Unsafe snapshot path.')
    actual = files(snapshot / 'payload')
    if set(actual) != set(manifest['files']) or 'copilot.db' not in actual:
        raise ValueError('Snapshot file list does not match its manifest.')
    if any(digest(path) != manifest['files'][name] for name, path in actual.items()):
        raise ValueError('Snapshot checksum mismatch; restore refused.')
    with closing(sqlite3.connect(actual['copilot.db'].as_uri() + '?mode=ro&immutable=1', uri=True)) as conn:
        if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or conn.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Snapshot SQL integrity check failed.')
    return manifest


def create(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if destination == source or source in destination.parents:
        raise ValueError('Store the backup outside the active data directory.')
    if destination.exists():
        raise ValueError('Snapshot destination must not already exist.')
    with offline(source):
        entries = files(source)
        payload = destination / 'payload'
        payload.mkdir(parents=True, exist_ok=False)
        for name, path in entries.items():
            if name in {'vectors/.lock', 'copilot.db', 'copilot.db-wal', 'copilot.db-shm', 'copilot.db-journal'}:
                continue
            target = payload / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        with closing(sqlite3.connect((source / 'copilot.db').as_uri() + '?mode=ro', uri=True)) as src, closing(sqlite3.connect(payload / 'copilot.db')) as dst:
            src.backup(dst)
            dst.execute('PRAGMA journal_mode=DELETE')
        manifest = {'format': 1, 'created_at': datetime.now(timezone.utc).isoformat(), 'source': str(source), 'files': {name: digest(path) for name, path in files(payload).items()}, 'note': 'Local sensitive snapshot; keep outside source control and cloud-sync. Restore invalidates sessions.'}
        (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    verify(destination)
    return destination


def restore(snapshot, destination):
    snapshot, destination = Path(snapshot).resolve(), Path(destination).resolve()
    manifest = verify(snapshot)
    if destination.exists() or snapshot == destination or snapshot in destination.parents:
        raise ValueError('Restore destination must be a new directory outside the snapshot.')
    shutil.copytree(snapshot / 'payload', destination)
    # Verify the copy before opening either SQL or vector storage.
    if any(digest(destination / name) != value for name, value in manifest['files'].items()):
        raise ValueError('Restored copy failed checksum verification.')
    with closing(sqlite3.connect(destination / 'copilot.db')) as conn:
        conn.execute('DELETE FROM sessions')
        conn.commit()
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['create', 'verify', 'restore'])
    parser.add_argument('--snapshot', type=Path)
    parser.add_argument('--destination', type=Path)
    args = parser.parse_args()
    if args.action == 'create':
        settings = Settings()
        target = args.destination or settings.data_dir.parent / 'EnterpriseCopilotBackups' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8])
        print(create(settings.data_dir, target))
    elif args.action == 'verify':
        if not args.snapshot:
            parser.error('--snapshot is required')
        print(json.dumps({'verified_files': len(verify(args.snapshot)['files'])}))
    else:
        if not args.snapshot or not args.destination:
            parser.error('--snapshot and --destination are required')
        print(restore(args.snapshot, args.destination))


if __name__ == '__main__':
    main()
