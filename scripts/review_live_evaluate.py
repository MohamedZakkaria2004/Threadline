"""Focused real-model semantic review through the running application's API."""
import json
import re
import statistics
import time
import uuid
import argparse
from pathlib import Path
import httpx
from app.config import ROOT, Settings

CASES = [
    dict(id='purchase_exact_500', question='For a purchase of exactly AED 500, whose approval is required?', terms=['manager'], forbidden=['finance', 'procurement'], source='procurement.md'),
    dict(id='purchase_exact_5000', question='For a purchase of exactly AED 5000, whose approval is required?', terms=['procurement'], forbidden=['finance'], source='procurement.md'),
    dict(id='purchase_6000', question='For a purchase of AED 6000, whose approval is required?', terms=['procurement','finance'], source='procurement.md'),
    dict(id='expense_responsibilities', question='Who reviews receipts before reimbursement, and what does the line manager approve?', terms=['finance','business purpose','before'], forbidden=['annual leave'], source='travel_expenses.md'),
    dict(id='missing_receipts', question='Can I claim a meal without itemized receipts if I stay within the AED 150 limit?', terms=['receipt'], negative=True, source='travel_expenses.md'),
    dict(id='contractor_scope', question='Does the annual leave policy establish that contractors receive 25 working days of leave?', scope=True, source='annual_leave.md'),
    dict(id='followup_anchor', question='How many working days of annual leave do permanent employees receive?', terms=['25'], source='annual_leave.md'),
    dict(id='followup_approver', question='Who approves it?', terms=['manager'], source='annual_leave.md', previous='followup_anchor'),
    dict(id='followup_advance', question='And how far in advance?', terms=['10'], source='annual_leave.md', previous='followup_approver'),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ids', nargs='*')
    parser.add_argument('--output', default='review-live-evaluation.json')
    args = parser.parse_args()
    settings = Settings()
    credentials = (settings.data_dir / 'demo-credentials.txt').read_text()
    password = re.findall(r'^employee: (\S+)', credentials, re.M)[-1]
    results, conversations = [], {}
    report = ROOT / 'artifacts' / args.output
    with httpx.Client(base_url='http://127.0.0.1:8765', timeout=300, trust_env=False, headers={'X-Copilot-Request':'1'}) as client:
        health=client.get('/api/health').json()
        assert health['model'] == settings.model and health['embedding_model'] == settings.embed_model
        client.post('/api/login', json={'username':'employee','password':password}).raise_for_status()
        for case in CASES:
            if args.ids and case['id'] not in args.ids:
                continue
            payload={'message':case['question'],'request_id':str(uuid.uuid4())}
            if case.get('previous'): payload['conversation_id']=conversations[case['previous']]
            start=time.perf_counter()
            response=client.post('/api/chat',json=payload)
            body=response.json()
            text=body.get('answer','').lower()
            checks={'http_ok':response.status_code == 200}
            if response.status_code == 200:
                conversations[case['id']]=body['conversation_id']
                if case.get('scope'):
                    checks['scope_qualified']=body['insufficient_evidence'] or ('permanent' in text and any(w in text for w in ['not ', 'only ', 'no ', 'doesn\'t']))
                else:
                    checks['answered']=not body['insufficient_evidence']
                    checks['expected_facts']=all(t in text for t in case.get('terms',[]))
                if not body['insufficient_evidence']:
                    checks['correct_source']=any(c['filename']==case['source'] for c in body['citations'])
                if case.get('negative'): checks['condition_preserved']=any(w in text for w in ['not ', 'no,', 'no.', 'cannot', 'must ', 'required'])
                checks['no_incorrect_or_irrelevant_claims']=not any(t in text for t in case.get('forbidden',[]))
                checks['quoted_source_matches']=all(' '.join(c['quote'].casefold().split()) in ' '.join(c['text'].casefold().split()) for c in body['citations'])
            item={**case,'checks':checks,'passed':all(checks.values()),'seconds':round(time.perf_counter()-start,2),'response':body}
            results.append(item)
            output={'model':settings.model,'embedding_model':settings.embed_model,'results':results,'summary':{'passed':sum(r['passed'] for r in results),'failed':sum(not r['passed'] for r in results),'median_seconds':round(statistics.median(r['seconds'] for r in results),2),'note':'Automated fact/provenance checks require manual semantic inspection of the saved answers.'}}
            report.write_text(json.dumps(output,indent=2),encoding='utf-8')
            print(f"{'PASS' if item['passed'] else 'FAIL'} {case['id']}: {item['seconds']}s | {body.get('answer',body.get('detail'))}",flush=True)
    raise SystemExit(1 if any(not r['passed'] for r in results) else 0)

if __name__ == '__main__':
    main()
