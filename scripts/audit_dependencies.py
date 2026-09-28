"""Check installed versions against the lock and OSV's public advisory database."""
import importlib.metadata
import json
from pathlib import Path
import httpx
from app.config import ROOT
from app.storage import now

def main():
    packages = []
    for line in (ROOT / 'requirements.lock.txt').read_text().splitlines():
        if '==' in line:
            name, version = line.split('==')
            packages.append({'name':name,'locked':version,'installed':importlib.metadata.version(name)})
    report = {'at':now(),'packages':packages,'lock_matches':all(p['locked']==p['installed'] for p in packages),
              'advisory_source':'https://api.osv.dev/v1/querybatch','limitations':'Point-in-time public advisory lookup; absence of known advisories is not proof of security.'}
    try:
        with httpx.Client(timeout=90, trust_env=False) as client:
            response = client.post(report['advisory_source'], json={'queries':[{'package':{'name':p['name'],'ecosystem':'PyPI'},'version':p['installed']} for p in packages]})
            response.raise_for_status()
            results = response.json()['results']
            assert len(results)==len(packages)
            report['advisories'] = [{'package':p['name'],'version':p['installed'],'vulnerabilities':r.get('vulns',[])} for p,r in zip(packages,results) if r.get('vulns')]
            report['lookup_completed'] = True
    except Exception as exc:
        report['lookup_completed'] = False
        report['lookup_error'] = str(exc)
    (ROOT / 'artifacts' / 'e2e-audit-dependencies.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='packages'},indent=2))

if __name__ == '__main__':
    main()
