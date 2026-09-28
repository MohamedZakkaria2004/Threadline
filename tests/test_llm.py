import json
import httpx
import pytest
from app.config import Settings
from app.storage import Store
from app.llm import Ollama, ModelUnavailable
from app.schemas import GroundedAnswer


def adapter(tmp_path, response):
    settings = Settings(data_dir=tmp_path)
    store = Store(tmp_path / 'adapter.db')
    llm = Ollama(settings, store)
    llm.client.close()
    llm.client = httpx.Client(base_url=settings.ollama_url, transport=httpx.MockTransport(lambda request: httpx.Response(200, json=response)))
    return llm, store


@pytest.mark.parametrize('response', [{'embeddings': []}, {'embeddings': [[0, 0]]}, {'embeddings': [[1, float('inf')]]}, {'embeddings': [123]}, {}, {'embeddings': [[1, 2], [1]]}])
def test_bad_embedding_responses_fail_clearly(tmp_path, response):
    # httpx itself rejects non-JSON infinities; use a raw transport for that case.
    llm, _ = adapter(tmp_path, response)
    if response == {'embeddings': [[1, float('inf')]]}:
        llm.client.close()
        llm.client = httpx.Client(base_url='http://localhost', transport=httpx.MockTransport(lambda request: httpx.Response(200, content=json.dumps(response))))
    with pytest.raises(ModelUnavailable):
        llm.embed(['document'])
    llm.close()


@pytest.mark.parametrize('response', [[], {}, {'message': None}, {'message': {'content': 'not JSON'}}, {'message': {'content': '{"answer":"hello"}'}}])
def test_malformed_model_output_and_error_metric(tmp_path, response):
    llm, store = adapter(tmp_path, response)
    with pytest.raises(ModelUnavailable):
        llm.structured([{'role': 'user', 'content': 'question'}], GroundedAnswer, 'answer')
    assert store.one('SELECT status FROM metrics')['status'] == 'error'
    llm.close()


def test_timeout_is_actionable_and_logged(tmp_path):
    llm, store = adapter(tmp_path, {})
    llm.client.close()
    def unavailable(request):
        raise httpx.ReadTimeout('timeout')
    llm.client = httpx.Client(base_url='http://localhost', transport=httpx.MockTransport(unavailable))
    with pytest.raises(ModelUnavailable):
        llm.structured([], GroundedAnswer, 'answer')
    assert store.one('SELECT status FROM metrics')['status'] == 'error'
    assert not llm.health()['ready']
    llm.close()


def test_invalid_health_response(tmp_path):
    llm, _ = adapter(tmp_path, {'models': None})
    assert not llm.health()['ready']
    llm.close()


def test_nonfinite_cost_configuration_rejected(tmp_path):
    with pytest.raises(ValueError):
        Settings(data_dir=tmp_path, power_watts=float('nan'))
