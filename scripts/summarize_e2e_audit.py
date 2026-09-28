"""Combine execution checks with explicit, separately recorded source reviews."""
import hashlib
import json
from pathlib import Path
from app.config import ROOT
from app.insights import percentile
from app.knowledge import normalized, extract_sections
from app.storage import now

def main():
    artifacts = ROOT / 'artifacts'
    run = json.loads((artifacts / 'e2e-audit-final.json').read_text(encoding='utf-8'))
    rerun_path = artifacts / 'e2e-audit-clarification-rerun.json'
    runs = [run]
    if rerun_path.exists():
        rerun = json.loads(rerun_path.read_text(encoding='utf-8'))
        assert rerun['gold_sha256']==run['gold_sha256'] and rerun['model_digests']==run['model_digests'] and rerun['fixture_hashes']==run['fixture_hashes']
        runs.append(rerun)
        replacements = {c['id']:c for c in rerun['cases']}
        run = {**run, 'cases':[replacements.get(c['id'],c) for c in run['cases']]}
    review = json.loads((artifacts / 'e2e-audit-source-review.json').read_text(encoding='utf-8'))
    gold = json.loads((ROOT / 'evaluation' / 'audit' / 'gold.json').read_text(encoding='utf-8'))
    cases = {c['id']:c for c in run['cases']}
    judgments = {c['id']:c for c in review['judgments']}
    assert set(cases)==set(judgments)=={c['id'] for c in gold['cases']}, 'Every frozen case requires both execution and source review.'
    assert run['gold_sha256']==hashlib.sha256((ROOT / 'evaluation' / 'audit' / 'gold.json').read_bytes()).hexdigest()
    citations = [s for c in run['cases'] for s in c['response'].get('citations',[])]
    originals = {}
    for source in citations:
        filename = source['filename']
        if filename not in originals:
            path = ROOT / 'evaluation' / 'audit' / filename
            originals[filename] = dict(extract_sections(filename,path.read_bytes()))
    traceable = sum(normalized(s['quote']) in normalized(originals[s['filename']][s['locator']]) for s in citations)
    rag = [c for c in run['cases'] if c['expected'].get('mode','ask')=='ask']
    actions = [c for c in run['cases'] if c['expected'].get('mode')=='agent']
    answered = [c for c in rag if not c['response'].get('insufficient_evidence',True)]
    answerable = [c for c in rag if c['expected'].get('expected_source_document')]
    negatives = [c for c in rag if c['id']=='conflicting-policy' or c['expected'].get('expect_abstention')]
    passed = [c for c in run['cases'] if c['screening_pass'] and judgments[c['id']]['verdict']=='pass']
    extra = {}
    for c in actions:
        if c['expected'].get('expected_source_document'):
            extra[c['id']+'_expected_source'] = any(s['filename']==c['expected']['expected_source_document'] and s['locator']==c['expected']['expected_citation']['locator'] for s in c['response'].get('citations',[]))
    summary = {'at':now(),'reviewer':review['reviewer'],'human_policy_owner_signoff':False,
               'execution_builds':[r['build'] for r in runs], 'provenance':'Full run plus explicitly recorded focused rerun after clarification fix; initial and intermediate failures retained.',
               'model':run['model_digests'],'rag_run_build':run['build'],'gold_sha256':run['gold_sha256'],
               'tests':{'gold_total':len(cases),'gold_passed':len(passed),'gold_failed':len(cases)-len(passed),
                        'additional_report_checks':extra,'restart_preserved_counts':all(r['restart_preserved_counts'] for r in runs),
                        'model_identity_unchanged':all(r['model_identity_unchanged'] for r in runs),'prompts_unchanged':all(r['prompts_unchanged'] for r in runs)},
               'metrics':{'rag_cases':len(rag),'agent_cases':len(actions),'answerable_rag_cases':len(answerable),
                          'answerable_correct':sum(judgments[c['id']]['verdict']=='pass' and not c['response'].get('insufficient_evidence',True) for c in answerable),
                          'answered_rag_cases':len(answered),'factually_correct_answered':sum(judgments[c['id']]['verdict']=='pass' for c in answered),
                          'negative_cases':len(negatives),'correct_negative_behavior':sum(judgments[c['id']]['verdict']=='pass' for c in negatives),
                          'retrieval_expected_evidence_hits':sum(c['checks'].get('expected_evidence_retrieved',False) for c in answerable),
                          'retrieval_denominator':len(answerable),'citations':len(citations),'citations_traceable_to_original':traceable,
                          'rag_p50_seconds':percentile([c['latency_s'] for c in rag],.5),'rag_p95_seconds':percentile([c['latency_s'] for c in rag],.95),
                          'all_cases_p50_seconds':percentile([c['latency_s'] for c in run['cases']],.5),'all_cases_p95_seconds':percentile([c['latency_s'] for c in run['cases']],.95),
                          'repeat_pair_both_correct':all(judgments[id]['verdict']=='pass' for id in ('csf-functions','repeat-functions')),
                          'repeat_pair_exact_text_match':normalized(cases['csf-functions']['response']['answer'])==normalized(cases['repeat-functions']['response']['answer']),
                          'hosted_model_api_cost_usd':0},
               'limitations':'Small fixed corpus and one repeat pair; AI-assisted source review, not independent human signoff or a production accuracy guarantee.'}
    (artifacts / 'e2e-audit-acceptance.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))

if __name__ == '__main__':
    main()
