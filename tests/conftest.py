import hashlib
import json
import math
import re
import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.llm import ModelUnavailable
from app.schemas import GroundedAnswer, ToolPlan, SemanticVerdict

HEADERS = {'X-Copilot-Request': '1'}


class FakeLLM:
    def __init__(self, settings, store):
        self.calls = []
        self.fail_embed = False
        self.fail_generate = False
        self.settings = settings

    def health(self):
        return {'connected': True, 'ready': True, 'missing': [], 'models': []}

    def identity(self):
        return {self.settings.model: 'test-generation-digest', self.settings.embed_model: 'test-embedding-digest'}

    def embed(self, texts, query=False):
        if self.fail_embed:
            raise ModelUnavailable('Local embedding failed. Check Ollama.')
        self.calls.append(('embed', texts))
        vectors = []
        for text in texts:
            vector = [0.1] * 64
            for word in re.findall(r'\w+', text.lower()):
                vector[int(hashlib.sha256(word.encode()).hexdigest()[:8], 16) % 64] += 1
            norm = math.sqrt(sum(x*x for x in vector))
            vectors.append([x / norm for x in vector])
        return vectors

    def structured(self, messages, schema, operation, user_id=None, workflow_id=None):
        self.calls.append(('generate', messages))
        if self.fail_generate:
            raise ModelUnavailable('The local model did not return a valid response.')
        if schema is SemanticVerdict:
            return SemanticVerdict(verdict='supported', reason='Deterministic test double; real-model semantic behavior is checked separately.')
        if schema is ToolPlan:
            from app.service import explicit_intent
            text = messages[-1]['content']
            return ToolPlan(tool=explicit_intent(text), title=text[:120], description=text[:1200], priority='normal')
        data = json.loads(messages[-1]['content'])
        source = data['evidence'][0]
        text = source['text']
        return GroundedAnswer(answer=text, citations=[{'source_id': source['source_id'], 'quote': text[:min(350, len(text))]}], insufficient_evidence=False)

    def close(self):
        pass


@pytest.fixture
def app(tmp_path):
    return create_app(Settings(data_dir=tmp_path), llm_factory=FakeLLM)


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


def login(client, username='admin'):
    credentials = (client.app.state.settings.data_dir / 'demo-credentials.txt').read_text()
    password = re.search(r'^' + username + r': (\S+)', credentials, re.M).group(1)
    response = client.post('/api/login', headers=HEADERS, json={'username': username, 'password': password})
    assert response.status_code == 200, response.text
    return response


def upload(client, text='Employees receive 25 working days of annual leave per calendar year. Their line manager approves leave.', **fields):
    fields = {'classification': 'internal', 'department': 'All', **fields}
    return client.post('/api/documents', headers=HEADERS, files={'file': ('policy.txt', text.encode(), 'text/plain')}, data=fields)


def ask(client, message='How many days of annual leave?', **fields):
    import uuid
    return client.post('/api/chat', headers=HEADERS, json={'message': message, 'request_id': str(uuid.uuid4()), **fields})
