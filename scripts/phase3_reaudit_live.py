"""Fresh real-model checks for the Phase 3 re-review, without operational writes."""
import hashlib
import argparse
from contextlib import ExitStack
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import tempfile
import time
import httpx
from app.config import ROOT, Settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--isolated', action='store_true', help='Run current code with real Ollama and a temporary SQL/vector store, without restarting the running app.')
    parser.add_argument('--suite', choices=['quick', 'full'], default='quick')
    parser.add_argument('--output', default='phase3-reaudit-live.json')
    args = parser.parse_args()
    with ExitStack() as stack:
        settings = Settings()
        if args.isolated:
            from fastapi.testclient import TestClient
            from app.main import create_app
            temporary = stack.enter_context(tempfile.TemporaryDirectory(prefix='atlas-phase3-reaudit-'))
            settings = Settings(data_dir=Path(temporary))
            client = stack.enter_context(TestClient(create_app(settings), headers={'X-Copilot-Request': '1'}))
        else:
            client = stack.enter_context(httpx.Client(base_url='http://127.0.0.1:8765', timeout=30, trust_env=False, headers={'X-Copilot-Request': '1'}))
        credentials = (settings.data_dir / 'demo-credentials.txt').read_text()
        password = re.findall(r'^admin: (\S+)', credentials, re.M)[-1]
        client.post('/api/login', json={'username': 'admin', 'password': password}).raise_for_status()
        if args.isolated:
            from app.evaluation import FILES
            for filename in FILES:
                client.post('/api/documents', files={'file': (filename, (ROOT / 'sample_docs' / filename).read_bytes(), 'text/plain')}, data={'classification': 'internal', 'department': 'All'}).raise_for_status()
            print('Temporary isolated datastore seeded; inference uses installed local Qwen.', flush=True)
        before = client.get('/api/insights?scope=platform').json()
        total = 3 if args.suite == 'quick' else 8
        start_future = None
        if args.isolated:
            # TestClient waits for Starlette background work before returning.
            # Submit in a worker so real progress and busy behavior remain visible.
            executor = stack.enter_context(ThreadPoolExecutor(max_workers=1))
            start_future = executor.submit(client.post, '/api/evaluations', json={'suite':args.suite})
            while True:
                rows = client.app.state.store.all('SELECT id FROM evaluations ORDER BY created_at DESC LIMIT 1')
                if rows:
                    run_id = rows[0]['id']
                    break
                if start_future.done():
                    response = start_future.result()
                    response.raise_for_status()
                    run_id = response.json()['id']
                    break
                time.sleep(.5)
        else:
            response = client.post('/api/evaluations', json={'suite': args.suite})
            response.raise_for_status()
            run_id = response.json()['id']
        print('Re-review benchmark ' + run_id, flush=True)
        busy_checks = {}
        if client.get('/api/evaluations/' + run_id).json()['status']=='running':
            busy = client.get('/api/health').json()['status'] == 'busy'
            busy_checks['busy_status_visible'] = busy
            # Only probe writes while a live benchmark owns the inference slot.
            # They must reject before creating operational state.
            busy_checks['second_benchmark_refused'] = busy and client.post('/api/evaluations', json={'suite': 'quick'}).status_code == 409
            busy_checks['concurrent_chat_refused'] = busy and client.post('/api/chat', json={'message': 'How many days of annual leave?', 'request_id': 'busy-probe-' + run_id}).status_code == 409
        deadline, finished = time.monotonic() + 3600, -1
        while True:
            response = client.get('/api/evaluations/' + run_id)
            response.raise_for_status()
            run = response.json()
            if len(run['results']) != finished:
                finished = len(run['results'])
                print(run['status'] + ': ' + str(finished) + '/' + str(total), flush=True)
                if run['results']:
                    item = run['results'][-1]
                    print(json.dumps({'case': item['id'], 'answer': item['answer']['answer'], 'quotes': [c['quote'] for c in item['answer']['citations']]}), flush=True)
            if run['status'] != 'running':
                break
            if time.monotonic() > deadline:
                raise RuntimeError('Check the persisted benchmark before retrying; no automatic replay.')
            time.sleep(3)
        if start_future:
            start_future.result().raise_for_status()
        after = client.get('/api/insights?scope=platform').json()
        allowed = {f['id'] for f in run['config']['fixtures']}
        checks = {
            **busy_checks,
            'completed_expected_cases': run['status'] == 'completed' and finished == total,
            'all_automated_passes': run['summary']['passed'] == total,
            'no_invented_human_judgments': run['summary']['human_reviewed'] == 0,
            'citations_within_sql_allowlist': all(c['document_id'] in allowed for r in run['results'] for c in r['answer']['citations']),
            'fixture_hashes_unchanged': all(f['digest'] == hashlib.sha256((ROOT / 'sample_docs' / f['filename']).read_bytes()).hexdigest() for f in run['config']['fixtures']),
            'prompt_hashes_unchanged': all(digest == hashlib.sha256((ROOT / 'prompts' / run['config']['prompt_version'] / (name + '.txt')).read_bytes()).hexdigest() for name, digest in run['config']['prompt_hashes'].items()),
            'export_matches_saved_run': client.get('/api/evaluations/' + run_id + '/download').json() == run,
            'no_new_operational_requests': before['requests'] == after['requests'],
            'benchmark_excluded_from_operational_model_calls': before['generation']['calls'] == after['generation']['calls'],
            'model_slot_released': client.get('/api/health').json()['status'] == 'ready',
            'semantic_supported_all_cases': all(r.get('semantic', {}).get('verdict') == 'supported' for r in run['results']) and finished == total,
            'semantic_prompt_fingerprint': run['config'].get('semantic_prompt_hash') == hashlib.sha256((ROOT / 'prompts' / run['config']['semantic_prompt_version'] / 'semantic_review.txt').read_bytes()).hexdigest(),
            'model_fingerprints_recorded': len(run['config'].get('model_digests', {})) == 2 and all(run['config']['model_digests'].values()),
            'human_signoff_still_pending': run['summary'].get('quality_gate') == 'needs_human_review',
            'runtime_build_visible': bool(client.get('/api/health').json().get('build')),
        }
    report = {'execution': 'Current code, real Ollama, temporary isolated SQL/Qdrant; running server untouched' if args.isolated else 'Running HTTP server', 'checks': checks, 'passed': sum(checks.values()), 'failed': sum(not v for v in checks.values()), 'run': run}
    (ROOT / 'artifacts' / Path(args.output).name).write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'passed': report['passed'], 'failed': report['failed']}), flush=True)
    raise SystemExit(0 if all(checks.values()) else 1)


if __name__ == '__main__':
    main()
