"""Reconcile final audit artifacts with the currently running local build."""
import hashlib
import json
import xml.etree.ElementTree as ET
import httpx
from app.config import ROOT
from app.storage import now


def main():
    artifacts = ROOT / 'artifacts'
    read = lambda name: json.loads((artifacts / name).read_text(encoding='utf-8-sig'))
    suite = ET.parse(artifacts / 'e2e-audit-tests.xml').getroot()
    suites = list(suite.iter('testsuite'))
    python = {k: sum(int(s.get(k, '0')) for s in suites) for k in ('tests', 'failures', 'errors', 'skipped')}
    ui = ET.parse(artifacts / 'e2e-audit-ui.xml').getroot()
    ui_results = {'tests': len(list(ui.iter('testcase'))), 'failures': len(list(ui.iter('failure'))), 'errors': len(list(ui.iter('error')))}
    acceptance = read('e2e-audit-acceptance.json')
    quality = read('e2e-audit-quality-lab.json')
    storage = read('e2e-audit-storage.json')
    recovery = read('e2e-audit-recovery.json')
    browser = read('e2e-audit-browser.json')
    dependencies = read('e2e-audit-dependencies.json')
    with httpx.Client(trust_env=False, timeout=20) as client:
        response = client.get('http://127.0.0.1:8765/api/health')
        response.raise_for_status()
        health = response.json()
    build = hashlib.sha256(b''.join(p.relative_to(ROOT).as_posix().encode() + p.read_bytes() for p in sorted(list((ROOT / 'app').rglob('*.py')) + list((ROOT / 'prompts').rglob('*.txt'))))).hexdigest()[:16]
    checks = {
        'python_regressions': python['tests'] == 219 and not any(python[k] for k in ('failures', 'errors', 'skipped')),
        'ui_state_regressions': ui_results == {'tests':32,'failures':0,'errors':0},
        'gold_source_review': acceptance['tests']['gold_passed'] == 21 and acceptance['tests']['gold_failed'] == 0,
        'quality_cases_and_integration': quality['run']['summary']['passed'] == 8 and quality['failed'] == 0,
        'storage_reconciliation': storage['failed'] == 0,
        'restoration': recovery['failed'] == 0,
        'browser_observations': browser['failed'] == 0,
        'locked_dependencies_and_advisories': dependencies['lock_matches'] and dependencies['lookup_completed'] and not dependencies['advisories'],
        'backend_ready_on_current_source': health['status'] == 'ready' and health['build'] == build == browser['build'],
        'no_invented_human_signoff': not acceptance['human_policy_owner_signoff'] and quality['run']['summary']['human_reviewed'] == 0,
    }
    result = {
        'at': now(), 'status': 'PASS WITH ISSUES' if all(checks.values()) else 'FAIL',
        'ready_for_portfolio_demonstration': all(checks.values()), 'checks': checks,
        'build':build, 'health':health, 'python':python, 'ui_state':ui_results,
        'gold':acceptance['tests'], 'metrics':acceptance['metrics'],
        'quality':quality['run']['summary'], 'quality_integration_passed':quality['passed'],
        'storage_passed':storage['passed'], 'recovery_passed':recovery['passed'], 'browser_passed':browser['passed'],
        'remaining':[
            'Slow CPU inference and host resource/process lifetime concerns; run a supervised local demo with adequate free RAM.',
            'Small fixed corpus, narrow conflict/clarification guards and same-model semantic judgment; independent human domain review remains pending.',
            'Local demo identity, plaintext storage, single-process databases and no external service integrations are portfolio boundaries, not production certification.',
            'One test-client deprecation warning; no runtime dependency incompatibility or returned OSV advisory.'
        ],
        'evidence_note':'Gold acceptance combines the preserved full run and a focused post-fix rerun; browser checks are explicit observations. Counts describe separate suites and should not be treated as independent statistical samples.'
    }
    (artifacts / 'e2e-audit-final-status.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if all(checks.values()) else 1)


if __name__ == '__main__':
    main()
