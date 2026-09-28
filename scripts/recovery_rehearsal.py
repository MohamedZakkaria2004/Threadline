"""Restore a real snapshot into a temporary directory and check SQL/vector fidelity."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import time
from qdrant_client import QdrantClient
from app.config import ROOT
from scripts.backup import restore, verify


def inspect_sql(path):
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as conn:
        counts = {table: conn.execute('SELECT count(*) FROM ' + table).fetchone()[0] for table in ['documents', 'chunks', 'users', 'tickets', 'reports', 'approvals', 'workflows', 'evaluations', 'feedback']}
        chunks = dict(conn.execute('SELECT id,document_id FROM chunks'))
        checks = {'sql_integrity': conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok', 'foreign_keys': not conn.execute('PRAGMA foreign_key_check').fetchall(), 'sessions_invalidated': conn.execute('SELECT count(*) FROM sessions').fetchone()[0] == 0, 'no_running_actions': conn.execute("SELECT count(*) FROM workflows WHERE status='running'").fetchone()[0] == 0, 'no_running_evaluations': conn.execute("SELECT count(*) FROM evaluations WHERE status='running'").fetchone()[0] == 0}
    return counts, chunks, checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', required=True, type=Path)
    parser.add_argument('--output', default='phase3-recovery-rehearsal.json')
    args = parser.parse_args()
    started = time.perf_counter()
    manifest = verify(args.snapshot)
    # The snapshot has DELETE journal mode, so this read does not create WAL files.
    original_counts, _, _ = inspect_sql((args.snapshot / 'payload' / 'copilot.db').resolve())
    with tempfile.TemporaryDirectory(prefix='atlas-recovery-rehearsal-') as folder:
        restored = restore(args.snapshot, Path(folder) / 'store')
        counts, chunks, checks = inspect_sql(restored / 'copilot.db')
        checks['business_counts_preserved'] = counts == original_counts
        checks['credential_file_preserved'] = (restored / 'demo-credentials.txt').is_file()
        client = QdrantClient(path=str(restored / 'vectors'))
        try:
            points = []
            query_ok = True
            for collection in client.get_collections().collections:
                offset = None
                while True:
                    page, offset = client.scroll(collection.name, limit=100, offset=offset, with_vectors=True)
                    points.extend(page)
                    if page:
                        result = client.query_points(collection.name, query=page[0].vector, limit=1).points
                        query_ok &= bool(result) and str(result[0].id) in chunks
                    if offset is None:
                        break
            checks['vector_count_matches_sql'] = len(points) == len(chunks)
            checks['all_vector_ids_match_sql'] = {str(p.id) for p in points} == set(chunks)
            checks['vector_document_payloads_match_sql'] = all(p.payload.get('document_id') == chunks.get(str(p.id)) for p in points)
            checks['restored_vector_query_works'] = bool(points) and query_ok
        finally:
            client.close()
    checks['original_snapshot_unchanged'] = verify(args.snapshot) == manifest
    report = {'snapshot_path': str(args.snapshot.resolve()), 'scope': 'Temporary restore only; original active data and snapshot retained. No model inference or human approvals.', 'checks': checks, 'passed': sum(checks.values()), 'failed': sum(not v for v in checks.values()), 'business_counts': counts, 'seconds': round(time.perf_counter() - started, 2)}
    (ROOT / 'artifacts' / Path(args.output).name).write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report), flush=True)
    raise SystemExit(0 if all(checks.values()) else 1)


if __name__ == '__main__':
    main()
