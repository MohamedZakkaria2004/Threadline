"""Fault scenarios added by the public-corpus end-to-end audit."""
import pytest
from qdrant_client import models
from conftest import login, upload, ask


@pytest.mark.parametrize('partial', [False, True])
def test_missing_vectors_are_an_operational_failure_not_a_knowledge_gap(client, partial):
    login(client)
    document = upload(client).json()
    if partial:
        upload(client, 'Laptop support is available on weekdays through the local service desk and its staff.')
    knowledge = client.app.state.knowledge
    chunks = client.app.state.store.all('SELECT id FROM chunks WHERE document_id=?', (document['id'],))
    knowledge.client.delete(knowledge.collection, models.PointIdsList(points=[c['id'] for c in chunks]))
    with _client(client) as http:
        response = ask(http)
    assert response.status_code == 503
    assert 'index' in response.json()['detail'].lower()
    assert not any(kind == 'generate' for kind, _ in client.app.state.llm.calls)
    assert client.app.state.store.one('SELECT status FROM workflows ORDER BY rowid DESC')['status'] == 'failed'


class _client:
    """Preserve the already-open app lifespan while exposing handled HTTP errors."""
    def __init__(self, client):
        self.client = client
    def __enter__(self):
        self.previous = self.client._transport.raise_server_exceptions
        self.client._transport.raise_server_exceptions = False
        return self.client
    def __exit__(self, *args):
        self.client._transport.raise_server_exceptions = self.previous


def test_upload_reauthorizes_after_long_embedding_call(client, monkeypatch):
    login(client)
    original = upload(client).json()
    state = client.app.state
    embed = state.llm.embed
    def revoke_then_embed(*args, **kwargs):
        state.store.run("UPDATE users SET role='employee' WHERE id='admin'")
        return embed(*args, **kwargs)
    monkeypatch.setattr(state.llm, 'embed', revoke_then_embed)
    response = upload(client, 'The revised leave policy grants 30 working days of leave per calendar year.', replaces_id=original['id'])
    assert response.status_code == 403
    assert state.store.one('SELECT status FROM documents WHERE id=?', (original['id'],))['status'] == 'ready'
    assert state.store.one("SELECT COUNT(*) AS n FROM documents WHERE status='ready'")['n'] == 1
    assert state.knowledge.client.count(state.knowledge.collection, exact=True).count == original['chunk_count']


def test_db_read_failure_does_not_return_successful_answer(client, monkeypatch):
    import sqlite3
    login(client)
    upload(client)
    original = client.app.state.store.all
    def broken(sql, *args, **kwargs):
        if 'FROM documents WHERE' in sql:
            raise sqlite3.OperationalError('injected database unavailable')
        return original(sql, *args, **kwargs)
    monkeypatch.setattr(client.app.state.store, 'all', broken)
    with _client(client) as http:
        response = ask(http)
    assert response.status_code == 500
    assert 'injected' not in response.text
    assert client.app.state.store.one('SELECT status FROM workflows ORDER BY rowid DESC')['status']=='failed'
    assert not client.app.state.work_lock.locked()


def test_vector_query_failure_is_not_a_grounded_answer(client, monkeypatch):
    login(client)
    upload(client)
    def broken(*args, **kwargs):
        raise RuntimeError('injected vector failure')
    monkeypatch.setattr(client.app.state.knowledge.client, 'query_points', broken)
    with _client(client) as http:
        response = ask(http)
    assert response.status_code >= 500
    assert 'injected' not in response.text
    assert not client.app.state.work_lock.locked()


@pytest.mark.parametrize('damage', ['point', 'collection', 'sql_chunk'])
def test_identical_reupload_repairs_index_without_losing_version_history(client, damage):
    login(client)
    document = upload(client).json()
    state = client.app.state
    chunk = state.store.one('SELECT id FROM chunks WHERE document_id=?', (document['id'],))
    if damage == 'point':
        state.knowledge.client.delete(state.knowledge.collection, models.PointIdsList(points=[chunk['id']]))
    elif damage == 'collection':
        state.knowledge.client.delete_collection(state.knowledge.collection)
    else:
        state.store.run('DELETE FROM chunks WHERE id=?', (chunk['id'],))
    response = upload(client)
    assert response.status_code == 200
    replacement = response.json()
    assert replacement['version'] == 2 and replacement['id'] != document['id']
    assert state.store.one('SELECT status FROM documents WHERE id=?', (document['id'],))['status']=='superseded'
    answer = ask(client).json()
    assert '25 working days' in answer['answer']
    assert all(c['document_id']==replacement['id'] for c in answer['citations'])


@pytest.mark.parametrize('repair_ok', [True, False])
def test_exact_quote_repair_is_bounded_and_never_accepts_fabrication(client, monkeypatch, repair_ok):
    import json
    from app.schemas import GroundedAnswer
    login(client)
    upload(client)
    calls = []
    def generate(messages, schema, operation, *args):
        calls.append(operation)
        source = json.loads(messages[1]['content'])['evidence'][0]
        quote = source['text'] if repair_ok and operation=='answer_repair' else 'This invented quote never occurs in the source.'
        return GroundedAnswer(answer='Employees receive 25 working days of annual leave.', citations=[{'source_id':source['source_id'],'quote':quote}], insufficient_evidence=False)
    monkeypatch.setattr(client.app.state.llm, 'structured', generate)
    result = ask(client).json()
    assert calls == ['answer', 'answer_repair']
    assert result['grounding_retry']
    assert result['insufficient_evidence'] is not repair_ok
    if not repair_ok:
        assert result['citations']==[]


def test_audit_ground_truth_spans_exist_in_original_documents():
    import json
    from app.config import ROOT
    from app.knowledge import extract_sections, normalized
    corpus = ROOT / 'evaluation' / 'audit'
    gold = json.loads((corpus / 'gold.json').read_text(encoding='utf-8'))
    for case in gold['cases']:
        if not case.get('expected_source_document') or not case.get('expected_retrieved_content'):
            continue
        path = corpus / case['expected_source_document']
        sections = dict(extract_sections(path.name, path.read_bytes()))
        assert normalized(case['expected_retrieved_content']) in normalized(sections[case['expected_citation']['locator']]), case['id']


def test_conflicting_active_numeric_rules_do_not_choose_a_winner(client):
    login(client)
    for amount in (80,120):
        upload(client, f'The Zephyr meal allowance is AED {amount} per employee per day. This policy is active.')
    result = ask(client, 'What is the Zephyr meal allowance per employee per day?').json()
    assert result['insufficient_evidence'] and result['checks']['conflicting_evidence']
    assert 'conflict' in result['answer'] and not result['citations']
    assert not any(kind=='generate' for kind,_ in client.app.state.llm.calls)


def test_numeric_conflict_guard_respects_identity_format_and_topic():
    from app.knowledge import has_numeric_conflict
    rule = 'The Zephyr meal allowance is AED {} per employee per day.'
    sources = [{'document_id':'a','text':rule.format('5,000')}, {'document_id':'b','text':rule.format('5000.00')}]
    assert not has_numeric_conflict(sources,'What is the Zephyr meal allowance?')
    sources[1]['text'] = rule.format('120')
    assert has_numeric_conflict(sources,'What is the Zephyr meal allowance?')
    assert not has_numeric_conflict(sources,'Who is the CEO?')
    sources[1]['document_id'] = 'a'
    assert not has_numeric_conflict(sources,'What is the Zephyr meal allowance?')


def test_neighbor_context_keeps_canonical_locator_and_permission_boundary(client, monkeypatch):
    from types import SimpleNamespace
    login(client)
    doc = upload(client, ' '.join('inventory asset policy' for _ in range(160))).json()
    private = upload(client, 'Leadership secret canary is never evidence available to an ordinary employee.', classification='leadership').json()
    state = client.app.state
    chunks = state.store.all('SELECT * FROM chunks WHERE document_id=? ORDER BY position',(doc['id'],))
    assert len(chunks)>=3
    state.store.run("UPDATE chunks SET locator='Other page' WHERE id=?",(chunks[2]['id'],))
    secret = state.store.one('SELECT id FROM chunks WHERE document_id=?',(private['id'],))['id']
    monkeypatch.setattr(state.knowledge.client,'query_points',lambda *a,**kw:SimpleNamespace(points=[SimpleNamespace(id=secret,score=.99),SimpleNamespace(id=chunks[1]['id'],score=.95)]))
    result = state.knowledge.search('inventory asset policy',{'id':'employee','role':'employee','department':'IT'})
    assert {s['chunk_id'] for s in result} == {chunks[0]['id'],chunks[1]['id']}
    assert all(s['document_id']==doc['id'] and s['locator']=='Paragraph 1' for s in result)
    assert len({s['source_id'] for s in result})==2


@pytest.mark.parametrize('quote, accepted', [
    ('These Functions help manage cybersecurity risk.',True),
    ('These Functions help eliminate cybersecurity risk.',False),
    ('These Functions do not help manage cybersecurity risk.',False),
    ('These Functions help manage cybersecurity risk...',False),
])
def test_pdf_whitespace_alignment_returns_original_span_without_fuzzy_facts(quote, accepted):
    from app.knowledge import validate_answer
    from app.schemas import GroundedAnswer
    source = {'source_id':'S1','filename':'guide.pdf','text':'TheseFunctions help manage cybersecurity risk.'}
    candidate = GroundedAnswer(answer='These functions help manage cybersecurity risk.', citations=[{'source_id':'S1','quote':quote}], insufficient_evidence=False)
    result = validate_answer(candidate,[source])
    assert result['insufficient_evidence'] is not accepted
    if accepted:
        assert result['citations'][0]['quote']==source['text']
        assert result['checks']['pdf_layout_quotes_recovered']==1


def test_retrieval_query_preserves_question_and_expands_common_enterprise_acronyms():
    from app.knowledge import retrieval_query
    assert retrieval_query('According to Manual X, which accounts require MFA?') == 'which accounts require multi-factor authentication?'
    assert retrieval_query('Does SSO require a VPN?') == 'Does single sign-on require a virtual private network?'
    assert retrieval_query('Compare the access policies, including exceptions.') == 'Compare the access policies, including exceptions.'


@pytest.mark.parametrize('text, accepted', [
    ('According to NIST SP 1300, require MFA on all accounts that offer it.',True),
    ('According to NIST SP 1300, employees receive 1300 days of leave.',False),
    ('According to NIST SP 9999, require MFA on all accounts that offer it.',False),
    ('For a purchase of AED 6000, require MFA on all accounts that offer it.',False),
])
def test_publication_reference_is_removed_without_whitelisting_claim_numbers(text, accepted):
    from app.knowledge import validate_answer
    from app.schemas import GroundedAnswer
    source = {'source_id':'S1','filename':'nist-csf-1300.pdf','title':'nist-csf-1300','text':'Prioritize requiring MFA on all accounts that offer it.'}
    candidate = GroundedAnswer(answer=text,citations=[{'source_id':'S1','quote':source['text']}],insufficient_evidence=False)
    result = validate_answer(candidate,[source])
    assert result['insufficient_evidence'] is not accepted
    if accepted:
        assert result['answer']=='Require MFA on all accounts that offer it.'
        assert result['checks']['document_reference_removed']


@pytest.mark.parametrize('requires_finance', [False, True])
def test_quality_grader_distinguishes_finance_requirement_from_its_negation(requires_finance):
    from app.evaluation import CASES, grade
    from app.config import ROOT
    text = (ROOT / 'sample_docs' / 'procurement.md').read_text()
    case = next(c for c in CASES if c['id']=='purchase_5000')
    answer = {'answer':'At AED 5000, Procurement approval is required; Finance approval is ' + ('required.' if requires_finance else 'not required.'), 'insufficient_evidence':False, 'citations':[{'filename':'procurement.md','text':text,'quote':text[:200]}]}
    checks = grade(case,answer,{'verdict':'contradicted' if requires_finance else 'supported'})
    assert all(checks.values()) is not requires_finance
    assert not all(grade(case,answer).values())  # No semantic verdict can never pass.


@pytest.mark.parametrize('question', ['What is the limit?', 'Who approves it?', 'What are the rules?', 'How much?'])
def test_generic_question_without_context_requests_clarification_without_model(client, question):
    login(client)
    upload(client)
    client.app.state.llm.calls.clear()
    result = ask(client,question).json()
    assert result['clarification_required'] and result['insufficient_evidence'] and not result['citations']
    assert client.app.state.llm.calls==[]


def test_generic_followup_uses_existing_topic_instead_of_guessing(client):
    login(client)
    upload(client,'The purchase limit is AED 5000 for the standard purchasing workflow. Procurement approves the request.')
    first = ask(client,'Describe the purchasing workflow.').json()
    client.app.state.llm.calls.clear()
    result = ask(client,'What is the limit?',conversation_id=first['conversation_id']).json()
    assert not result['insufficient_evidence']
    embedded = [value for kind,value in client.app.state.llm.calls if kind=='embed']
    assert 'Describe the purchasing workflow.' in embedded[0][0]
