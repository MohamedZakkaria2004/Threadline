"""Exercise Phase 3 HTTP integration with a real local benchmark.

The benchmark is read-only and does not create operational tickets/conversations.
Human/reviewer judgments are deliberately not inferred from automated passes.
"""
import argparse
import json
import re
import time
import httpx
from app.config import ROOT, Settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id')
    args = parser.parse_args()
    settings = Settings()
    credentials = (settings.data_dir / 'demo-credentials.txt').read_text()
    report = {'checks': {}, 'run_id': None}
    with httpx.Client(base_url='http://127.0.0.1:8765', timeout=30, trust_env=False, headers={'X-Copilot-Request': '1'}) as admin, httpx.Client(base_url='http://127.0.0.1:8765', timeout=30, trust_env=False, headers={'X-Copilot-Request': '1'}) as employee:
        for client, username in [(admin, 'admin'), (employee, 'employee')]:
            password = re.findall(r'^' + username + r': (\S+)', credentials, re.M)[-1]
            client.post('/api/login', json={'username': username, 'password': password}).raise_for_status()
        checks = report['checks']
        checks['phase3_health'] = admin.get('/api/health').json()['phase'] == 3
        checks['employee_admin_views_denied'] = all(employee.get(path).status_code == 403 for path in ['/api/evaluations', '/api/prompts', '/api/insights?scope=platform'])
        own = employee.get('/api/insights').json()
        checks['own_scope'] = own['scope'] == 'mine' and own['registered_users'] == 1
        registry = admin.get('/api/prompts').json()
        checks['prompt_registry'] = registry['active_version'] == settings.prompt_version and any(p['version'] == 'quality-v1' and p['name'] == 'semantic_review' for p in registry['templates'])
        business = employee.get('/api/business-case').json()['scenarios']
        checks['business_base_correct'] = business['base']['results']['first_year_cost_usd'] == 1802.25 and business['base']['results']['monthly_hours_saved'] == 17.5
        checks['conservative_is_loss'] = business['conservative']['results']['monthly_net_value_usd'] < 0 and business['conservative']['results']['payback_months'] is None
        zero = employee.post('/api/business-case', json={'adoption': 0}).json()
        checks['zero_adoption_no_payback'] = zero['results']['monthly_capacity_value_usd'] == 0 and zero['results']['payback_months'] is None
        before = admin.get('/api/insights?scope=platform').json()
        if args.run_id:
            run_id = args.run_id
        else:
            started = admin.post('/api/evaluations', json={'suite': 'full'})
            started.raise_for_status()
            run_id = started.json()['id']
        report['run_id'] = run_id
        print('Benchmark ' + run_id, flush=True)
        last_finished, deadline = -1, time.monotonic() + 3600
        while True:
            response = admin.get('/api/evaluations/' + run_id)
            response.raise_for_status()
            run = response.json()
            if run['summary']['finished'] != last_finished:
                last_finished = run['summary']['finished']
                print(f"{run['status']}: {last_finished}/{run['summary']['total']}", flush=True)
                for item in run['results'][-1:]:
                    print(f"{'PASS' if item['passed'] else 'FAIL'} {item['id']}: {item['answer']['answer']}", flush=True)
            (ROOT / 'artifacts' / 'phase3-full-evaluation.json').write_text(json.dumps(run, indent=2), encoding='utf-8')
            if run['status'] != 'running':
                break
            if time.monotonic() > deadline:
                raise SystemExit('Benchmark is still running. Inspect the Quality lab; this script does not automatically replay it.')
            time.sleep(3)
        checks['benchmark_completed'] = run['status'] == 'completed' and run['summary']['finished'] == 8
        checks['benchmark_automated_checks'] = run['summary']['passed'] == 8
        checks['judgments_not_invented'] = run['summary']['human_reviewed'] == 0 if not args.run_id else True
        downloaded = admin.get('/api/evaluations/' + run_id + '/download')
        checks['export_matches'] = downloaded.status_code == 200 and downloaded.json() == run and 'attachment;' in downloaded.headers['content-disposition']
        after = admin.get('/api/insights?scope=platform').json()
        checks['evaluation_calls_excluded'] = after['generation']['calls'] == before['generation']['calls']
        checks['no_operational_workflows_created'] = after['requests'] == before['requests']
        checks['model_lock_released'] = admin.get('/api/health').json()['status'] == 'ready'
        report['summary'] = {'passed': sum(checks.values()), 'failed': sum(not value for value in checks.values())}
        report['monitoring'] = after
        (ROOT / 'artifacts' / 'phase3-live-checks.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        (ROOT / 'artifacts' / 'phase3-business-scenarios.json').write_text(json.dumps(business, indent=2), encoding='utf-8')
        print(json.dumps(report['summary']), flush=True)
        raise SystemExit(0 if all(checks.values()) else 1)


if __name__ == '__main__':
    main()
