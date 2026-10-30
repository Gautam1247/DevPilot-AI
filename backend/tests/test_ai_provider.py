"""Exercise real SDK serialization/retry behavior with in-memory HTTP only."""
import asyncio
import json
import runpy
import time
from pathlib import Path

import httpx
import pytest
from google import genai

from app import ai
from app.config import ROOT, Settings
from app.schemas import Patch
from app.security import SafeError

VALID_PATCH = dict(root_cause='Incorrect fraction.', target_file='pricing.py',
                   original_code='price * (1 - percent)', replacement_code='price * (1 - percent / 100)',
                   explanation='Convert the percentage to a fraction.', confidence=0.9)


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    async def blocked(*args, **kwargs):
        raise AssertionError('Live network access forbidden in provider tests.')
    monkeypatch.setattr(httpx.AsyncHTTPTransport, 'handle_async_request', blocked)
    def blocked_sync(*args, **kwargs):
        raise AssertionError('Live network access forbidden in provider tests.')
    monkeypatch.setattr(httpx.HTTPTransport, 'handle_request', blocked_sync)


@pytest.fixture
def sdk_transport(monkeypatch):
    real_client = genai.Client
    def install(handler):
        requests = []
        options = []
        async def capture(request):
            requests.append(request)
            return await handler(request)
        def factory(**kwargs):
            opts = kwargs['http_options']
            options.append(opts)
            opts.httpx_async_client = httpx.AsyncClient(transport=httpx.MockTransport(capture))
            opts.httpx_client = httpx.Client(transport=httpx.MockTransport(lambda request: pytest.fail('Unexpected synchronous SDK request')))
            return real_client(**kwargs)
        monkeypatch.setattr(ai.genai, 'Client', factory)
        return requests, options
    return install


def provider():
    return ai.Provider(Settings(api_key='synthetic-test-key', model='gemini-3.6-flash', mock_ai=False))


def success_response(text):
    return httpx.Response(200, json={'candidates': [{'content': {'role':'model', 'parts':[{'text':text}]}, 'finishReason':'STOP'}]})


def test_actual_sdk_wire_request(sdk_transport, monkeypatch):
    # Ambient Vertex/base-URL configuration must not change this provider.
    monkeypatch.setenv('GOOGLE_GENAI_USE_VERTEXAI', 'true')
    monkeypatch.setenv('GOOGLE_GEMINI_BASE_URL', 'https://invalid.example/')
    async def handler(request):
        return success_response(json.dumps(VALID_PATCH))
    requests, options = sdk_transport(handler)
    assert provider().propose({'sources':{'pricing.py':'example'}}) == Patch(**VALID_PATCH)
    assert len(requests) == 1
    request = requests[0]
    assert str(request.url) == 'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent'
    body = json.loads(request.content)
    config = body['generationConfig']
    assert config['responseMimeType'] == 'application/json'
    assert config['maxOutputTokens'] == 6000
    assert 'temperature' not in config  # Use the model default.
    assert 'responseSchema' not in config
    assert config['responseJsonSchema'] == ai.patch_response_schema()
    schema = config['responseJsonSchema']
    assert schema['additionalProperties'] is False
    assert set(schema['required']) == set(VALID_PATCH)
    assert schema['properties']['root_cause'] == {'type':'string'}
    assert body['systemInstruction']['parts'][0]['text'] == ai.SYSTEM
    assert json.loads(body['contents'][0]['parts'][0]['text'])['sources']['pricing.py'] == 'example'
    assert not body.get('tools')
    assert all(timeout == 15 for timeout in request.extensions['timeout'].values())
    assert options[0].retry_options.attempts == 1


@pytest.mark.parametrize('code,fragment', [(400,'request rejected'),(401,'authentication invalid'),
    (403,'access denied'),(404,'unavailable'),(429,'quota'),(503,'service unavailable')])
def test_http_status_is_distinct_sanitized_and_never_retried(sdk_transport, code, fragment):
    async def handler(request):
        return httpx.Response(code, json={'error': {'code':code, 'message':'synthetic-test-key private-source https://secret.example', 'status':'UNTRUSTED'}})
    requests, _ = sdk_transport(handler)
    with pytest.raises(SafeError) as caught:
        provider().propose({})
    message = str(caught.value)
    assert f'HTTP {code}' in message and fragment in message
    assert all(value not in message for value in ('synthetic-test-key', 'private-source', 'secret.example', 'UNTRUSTED'))
    assert len(requests) == 1


@pytest.mark.parametrize('error,fragment', [
    ({'message':'Unknown field response_schema max_length synthetic-test-key'}, 'structured-output schema rejected'),
    ({'message':'Unsupported temperature synthetic-test-key'}, 'generation settings rejected'),
    ({'message':'synthetic-test-key','details':[{'reason':'API_KEY_INVALID'}]}, 'API key invalid'),
])
def test_400_classification_does_not_echo_remote_text(sdk_transport, error, fragment):
    async def handler(request):
        return httpx.Response(400, json={'error':dict(code=400, **error)})
    requests, _ = sdk_transport(handler)
    with pytest.raises(SafeError) as caught:
        provider().propose({})
    assert fragment in str(caught.value) and 'synthetic-test-key' not in str(caught.value)
    assert len(requests) == 1


@pytest.mark.parametrize('error,fragment', [(httpx.ReadTimeout,'network operation timed out'),
    (httpx.ConnectTimeout,'network operation timed out'), (httpx.ConnectError,'network connection failed')])
def test_transport_failures(sdk_transport, error, fragment):
    async def handler(request):
        raise error('synthetic-test-key sensitive-url', request=request)
    requests, _ = sdk_transport(handler)
    with pytest.raises(SafeError) as caught:
        provider().propose({})
    assert fragment in str(caught.value) and 'synthetic-test-key' not in str(caught.value)
    assert len(requests) == 1


def test_total_deadline_cancels_pending_request(sdk_transport, monkeypatch):
    monkeypatch.setattr(ai, 'TOTAL_TIMEOUT_SECONDS', 0.2)
    cancelled = []
    async def handler(request):
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.append(True)
        return success_response(json.dumps(VALID_PATCH))
    requests, _ = sdk_transport(handler)
    started = time.monotonic()
    with pytest.raises(SafeError, match='total request deadline exceeded'):
        provider().propose({})
    assert time.monotonic() - started < 3
    assert len(requests) == 1 and cancelled == [True]


@pytest.mark.parametrize('payload', [
    '{bad json', '{}', json.dumps(VALID_PATCH | {'extra':'not allowed'}),
    json.dumps(VALID_PATCH | {'root_cause':''}), json.dumps(VALID_PATCH | {'confidence':2}),
    json.dumps(VALID_PATCH | {'confidence':'0.9'}), json.dumps(VALID_PATCH | {'target_file':'x'*201}),
])
def test_strict_local_patch_validation_retained(sdk_transport, payload):
    async def handler(request):
        return success_response(payload)
    sdk_transport(handler)
    with pytest.raises(SafeError, match='malformed structured patch'):
        provider().propose({})


def test_configuration_uses_root_env_from_another_directory(tmp_path, monkeypatch):
    import dotenv
    loaded = []
    def fake_load(path):
        loaded.append(Path(path))
        monkeypatch.setenv('GEMINI_API_KEY', 'synthetic-config-key')
        monkeypatch.setenv('GEMINI_MODEL', 'gemini-3.6-flash')
        return True
    monkeypatch.setattr(dotenv, 'load_dotenv', fake_load)
    monkeypatch.chdir(tmp_path)
    module = runpy.run_path(str(ROOT/'backend'/'app'/'config.py'))
    cfg = module['Settings']()
    assert loaded == [ROOT/'.env']
    assert cfg.api_key == 'synthetic-config-key' and cfg.model == 'gemini-3.6-flash'
    assert cfg.api_key not in repr(cfg)


@pytest.mark.parametrize('http_code,expected', [(200,'VERIFIED'), (400,'INCONCLUSIVE')])
def test_engine_receives_actual_sdk_result(sdk_transport, tmp_path, http_code, expected):
    from unittest.mock import MagicMock
    from app.engine import Engine
    from app.schemas import TestRun as Run
    from app.workspaces import Store

    async def handler(request):
        if http_code == 400:
            return httpx.Response(400, json={'error': {'code':400, 'message':'response schema rejected synthetic-test-key'}})
        return success_response(json.dumps(VALID_PATCH))
    requests, _ = sdk_transport(handler)
    cfg = Settings(workspace=tmp_path, api_key='synthetic-test-key', mock_ai=False, model='gemini-3.6-flash')
    project, _ = Store(cfg).create('provider-test.zip')
    source = project.root/'original'/'pricing.py'
    source.write_text('def discount(price, percent):\n    return price * (1 - percent)\n')
    runner = MagicMock()
    def evidence(status):
        return Run(tests={'test_discount.py::test_fraction':status}, collected=['test_discount.py::test_fraction'],
                   exit_code=int(status == 'failed'), complete=True)
    runner.run.side_effect = [evidence('failed'), evidence('passed'), evidence('passed')]
    Engine(runner, ai.Provider(cfg)).analyze(project)
    assert project.result.status == expected
    assert len(requests) == 1
    assert 'synthetic-test-key' not in (project.root/'result.json').read_text()
    assert 'percent / 100' not in source.read_text()
    if http_code == 200:
        assert project.result.full_suite_success
        assert runner.run.call_count == 3
    else:
        assert 'HTTP 400' in project.result.message
        assert runner.run.call_count == 1
        assert not (project.root/'candidate').exists()
