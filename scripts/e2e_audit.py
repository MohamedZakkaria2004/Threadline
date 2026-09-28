"""Isolated real-Qwen audit. Screening checks supplement, never replace, source review."""
import argparse
import hashlib
import json
import re
import time
import uuid
from pathlib import Path
from fastapi.testclient import TestClient
from app.config import ROOT, Settings, default_data_dir
from app.main import create_app
from app.knowledge import extract_sections, normalized
from app.storage import now

CORPUS = ROOT / 'evaluation' / 'audit'

def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='e2e-audit-initial.json')
    parser.add_argument('--only', help='Comma-separated case IDs; dependencies must also be selected.')
    parser.add_argument('--resume', help='Continue a completed, passing targeted run with the same build, models and corpus.')
    parser.add_argument('--store-from', help='Reuse a completed isolated corpus for a new focused run; do not reuse old case results.')
    args = parser.parse_args()
    gold = json.loads((CORPUS / 'gold.json').read_text(encoding='utf-8'))
    selected = set(args.only.split(',')) if args.only else None
    prior = json.loads((ROOT / 'artifacts' / Path(args.resume).name).read_text(encoding='utf-8')) if args.resume else None
    reuse = json.loads((ROOT / 'artifacts' / Path(args.store_from).name).read_text(encoding='utf-8')) if args.store_from else None
    assert not (prior and reuse), 'Choose resume or store reuse, not both.'
    if reuse:
        assert reuse.get('ended_at') and reuse.get('restart_preserved_counts'), 'Only a completed isolated run can supply a corpus.'
    if prior:
        assert prior.get('ended_at') and prior.get('restart_preserved_counts') and all(c['screening_pass'] for c in prior['cases']), 'Only completed passing targeted runs can be resumed.'
        assert prior['gold_sha256']==hashlib.sha256((CORPUS / 'gold.json').read_bytes()).hexdigest(), 'Gold dataset changed.'
    data = Path((prior or reuse)['data_dir']) if (prior or reuse) else default_data_dir().parent / 'EnterpriseCopilotAudit' / str(uuid.uuid4())
    report = {'started_at':now(), 'data_dir':str(data), 'execution':'Actual local Ollama through application HTTP routes, isolated SQLite and embedded Qdrant',
              'gold_sha256':hashlib.sha256((CORPUS / 'gold.json').read_bytes()).hexdigest(),
              'sources':json.loads((CORPUS / 'sources.json').read_text()), 'ingestion':[], 'cases':[]}
    if prior:
        report.update(started_at=prior['started_at'],resumed_at=now(),resumed_from=Path(args.resume).name,cases=prior['cases'])
    if reuse:
        report['store_reused_from'] = Path(args.store_from).name
    output = ROOT / 'artifacts' / Path(args.output).name
    def save():
        # Keep a durable journal outside OneDrive even if its file watcher briefly
        # denies replacing the workspace export on Windows.
        (data / 'audit-progress.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        temporary = output.with_suffix('.tmp')
        temporary.write_text(json.dumps(report, indent=2), encoding='utf-8')
        for attempt in range(8):
            try:
                temporary.replace(output)
                return
            except PermissionError:
                if attempt == 7:
                    raise
                time.sleep(.25 * (attempt + 1))
    app = create_app(Settings(data_dir=data))
    with TestClient(app, headers={'X-Copilot-Request':'1'}, raise_server_exceptions=False) as client:
        state = app.state
        report['build'] = state.build_id
        report['model_digests'] = state.llm.identity()
        if reuse:
            assert report['model_digests']==reuse['model_digests'], 'Model identity changed; re-index in a fresh store.'
        report['prompt_hashes'] = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / 'prompts' / state.settings.prompt_version).glob('*.txt')}
        report['prompt_version'] = state.settings.prompt_version
        if prior:
            assert report['build']==prior['build'] and report['model_digests']==prior['model_digests'] and report['prompt_hashes']==prior['prompt_hashes'], 'Build, model or prompts changed; start a new run.'
        def login(username):
            credentials = (data / 'demo-credentials.txt').read_text()
            password = re.search(r'^' + username + r': (\S+)', credentials, re.M).group(1)
            response = client.post('/api/login', json={'username':username, 'password':password})
            response.raise_for_status()
        login('admin')
        source_sections = {}
        report['fixture_hashes'] = {}
        for path in sorted(list(CORPUS.glob('*.pdf')) + list(CORPUS.glob('*.txt'))):
            actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            report['fixture_hashes'][path.name] = actual_hash
            if prior:
                assert actual_hash==prior['fixture_hashes'][path.name], 'Corpus changed.'
            if reuse:
                assert actual_hash==reuse['fixture_hashes'][path.name], 'Corpus changed.'
            for official in report['sources']:
                if official['filename']==path.name:
                    assert actual_hash == official['sha256'], 'Official source bytes changed; do not grade against stale ground truth.'
            source_sections[path.name] = dict(extract_sections(path.name, path.read_bytes()))
            response = client.post('/api/documents', files={'file':(path.name,path.read_bytes())}, data={'classification':'leadership' if path.name=='private.txt' else 'internal','department':'All'})
            response.raise_for_status()
            doc = response.json()
            if reuse:
                assert doc['id']==next(d['id'] for d in reuse['ingestion'] if d['filename']==path.name), 'Stored source identity changed.'
            report['ingestion'].append(doc)
            print('Ingested ' + path.name + ': ' + str(doc.get('chunk_count')) + ' chunks', flush=True)
            save()
        retrieved = []
        search = state.knowledge.search
        def recording_search(*a, **kw):
            result = search(*a, **kw)
            retrieved.clear()
            retrieved.extend(result)
            return result
        state.knowledge.search = recording_search
        generations = []
        structured = state.llm.structured
        def recording_structured(*a, **kw):
            result = structured(*a, **kw)
            generations.append({'operation':a[2] if len(a)>2 else kw.get('operation'), 'output':result.model_dump()})
            return result
        state.llm.structured = recording_structured
        results = {c['id']:c['response'] for c in report['cases']}
        login('employee')
        for case in gold['cases']:
            if case['id'] in results:
                continue
            if selected and case['id'] not in selected:
                continue
            login('employee')
            retrieved.clear()
            generations.clear()
            request = {'message':case['test_question'],'mode':case.get('mode','ask'),'request_id':str(uuid.uuid4())}
            if case.get('follows'):
                request['conversation_id'] = results[case['follows']]['conversation_id']
            counts_before = {t:state.store.one(f'SELECT COUNT(*) AS n FROM {t}')['n'] for t in ('tickets','reports','approvals')}
            start = time.perf_counter()
            response = client.post('/api/chat', json=request)
            result = response.json()
            results[case['id']] = result
            checks = {'http_ok':response.status_code==200}
            row = {'id':case['id'],'question':case['test_question'],'expected':case,'http_status':response.status_code,
                   'latency_s':round(time.perf_counter()-start,3),'response':result,'retrieved':list(retrieved),'generations':list(generations),'checks':checks,
                   'source_review':'pending independent inspection of complete answer and original documents'}
            if response.status_code == 200:
                text = result.get('answer','')
                citations = result.get('citations',[])
                checks['correct_tool'] = result.get('tool') == case['expected_agent_tool_action']
                checks['quote_traceability'] = all(normalized(c['quote']) in normalized(source_sections[c['filename']][c['locator']]) for c in citations)
                checks['canonical_sql_traceability'] = all((r:=state.store.one('SELECT * FROM chunks WHERE id=?',(c['chunk_id'],))) and r['document_id']==c['document_id'] and normalized(c['quote']) in normalized(r['text']) for c in citations)
                checks['no_forbidden_output'] = all(w.casefold() not in text.casefold() for w in case.get('forbidden_output',[]))
                checks['no_forbidden_retrieval'] = all(s['filename'] not in case.get('forbidden_retrieval',[]) for s in retrieved)
                if case.get('mode','ask') == 'ask':
                    checks['no_side_effects'] = all(state.store.one(f'SELECT COUNT(*) AS n FROM {t}')['n']==n for t,n in counts_before.items())
                    if case['id'] != 'conflicting-policy':
                        checks['expected_abstention'] = result.get('insufficient_evidence') == case.get('expect_abstention',False)
                    else:
                        checks['conflict_not_arbitrarily_resolved'] = result.get('insufficient_evidence') is True or ('conflict' in text.lower() and {'conflict-a.txt','conflict-b.txt'} <= {c['filename'] for c in citations})
                    if case.get('expected_source_document'):
                        wanted = case['expected_source_document']
                        locator = case['expected_citation']['locator']
                        fragment = case['expected_retrieved_content']
                        checks['expected_evidence_retrieved'] = any(s['filename']==wanted and s['locator']==locator and normalized(fragment) in normalized(s['text']) for s in retrieved)
                        checks['expected_source_cited'] = any(c['filename']==wanted and c['locator']==locator for c in citations)
                    checks['required_concepts'] = all(term.casefold() in text.casefold() for term in case.get('required_concepts',[]))
                else:
                    tool = case['expected_agent_tool_action']
                    if case['id']=='routine-ticket':
                        checks['ticket_persisted'] = bool(state.store.one('SELECT * FROM tickets WHERE workflow_id=?',(result['workflow_id'],)))
                        checks['original_description'] = result.get('ticket',{}).get('description') == request['message']
                        replay = client.post('/api/chat',json=request)
                        checks['idempotent_replay'] = replay.status_code==200 and replay.json().get('ticket',{}).get('id')==result.get('ticket',{}).get('id') and state.store.one('SELECT COUNT(*) AS n FROM tickets')['n']==counts_before['tickets']+1
                    elif case['id'] in {'access-approval','sensitive-rejection'}:
                        checks['waiting_no_ticket'] = result.get('status')=='waiting_approval' and state.store.one('SELECT COUNT(*) AS n FROM tickets')['n']==counts_before['tickets']
                        approval = result.get('approval_id')
                        decision = {'decision':'approve' if case['id']=='access-approval' else 'reject','reason':'Independent audit review of a controlled fictional request.'}
                        denied = client.post(f'/api/approvals/{approval}/decision',json=decision)
                        checks['self_approval_denied'] = denied.status_code==403
                        login('admin')
                        decided = client.post(f'/api/approvals/{approval}/decision',json=decision)
                        checks['independent_decision'] = decided.status_code==200
                        row['decision_response'] = decided.json()
                        again = client.post(f'/api/approvals/{approval}/decision',json=decision)
                        checks['decision_idempotent'] = again.status_code==200 and again.json()==decided.json()
                        checks['correct_side_effect_count'] = state.store.one('SELECT COUNT(*) AS n FROM tickets')['n']==counts_before['tickets']+(case['id']=='access-approval')
                        checks['privileges_unchanged'] = state.store.one("SELECT role FROM users WHERE id='employee'")['role']=='employee'
                    elif case['id']=='report':
                        saved = result.get('report')
                        checks['report_saved'] = bool(saved)
                        if saved:
                            stored = state.store.one('SELECT * FROM reports WHERE id=?',(saved['id'],))
                            meta = json.loads(stored['metadata'])
                            counts = state.store.all("SELECT status,priority,COUNT(*) AS count FROM tickets WHERE user_id='employee' GROUP BY status,priority ORDER BY status,priority")
                            checks['sql_counts_exact'] = meta['ticket_counts']==counts
                            download = client.get('/api/reports/'+saved['id']+'/download')
                            checks['download_matches'] = download.status_code==200 and download.text==stored['markdown']
                            login('admin')
                            checks['report_private_even_from_admin'] = client.get('/api/reports/'+saved['id']).status_code==403
                    elif case['id']=='unsupported-tool':
                        checks['no_action'] = result.get('action_unavailable') is True and all(state.store.one(f'SELECT COUNT(*) AS n FROM {t}')['n']==n for t,n in counts_before.items())
            row['screening_pass'] = all(checks.values())
            report['cases'].append(row)
            save()
            print(json.dumps({'case':case['id'],'seconds':row['latency_s'],'failed_checks':[k for k,v in checks.items() if not v],'answer':result.get('answer',result)}),flush=True)
        report['storage'] = {t:state.store.one(f'SELECT COUNT(*) AS n FROM {t}')['n'] for t in ('documents','chunks','workflows','tickets','reports','approvals','metrics')}
        report['model_identity_unchanged'] = state.llm.identity()==report['model_digests']
        report['prompts_unchanged'] = report['prompt_hashes']=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / 'prompts' / state.settings.prompt_version).glob('*.txt')}
        report['ended_at'] = now()
        report['screening_passed'] = sum(c['screening_pass'] for c in report['cases'])
        report['screening_failed'] = len(report['cases'])-report['screening_passed']
        save()
    # Exercise application restart against the isolated persisted store.
    with TestClient(create_app(Settings(data_dir=data))) as restarted:
        report['restart_preserved_counts'] = all(restarted.app.state.store.one(f'SELECT COUNT(*) AS n FROM {t}')['n']==n for t,n in report['storage'].items())
    save()
    print(json.dumps({k:report[k] for k in ('screening_passed','screening_failed','restart_preserved_counts')}),flush=True)

if __name__ == '__main__':
    run()
