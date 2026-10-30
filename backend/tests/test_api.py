import io
import time
import zipfile
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.runner import DockerRunner, UNAVAILABLE
from app.schemas import TestRun as Run
from app.security import SafeError
from test_security import archive


def outcome(statuses):
    return Run(tests=statuses, collected=list(statuses), complete=True, exit_code=int('failed' in statuses.values()))


@pytest.fixture
def setup(tmp_path):
    runner = MagicMock()
    runner.available.return_value = True
    fail = {'test_pricing.py::test_twenty_percent':'failed','test_pricing.py::test_no_discount':'passed'}
    runner.run.side_effect = [outcome(fail), outcome({'test_pricing.py::test_twenty_percent':'passed'}), outcome({t:'passed' for t in fail})]
    app = create_app(Settings(workspace=tmp_path, mock_ai=True), runner=runner)
    with TestClient(app) as client:
        yield client, app, runner


def upload(client):
    root = Path(__file__).resolve().parents[2]/'benchmarks'/'discount_bug'
    data = archive({p.name:p.read_bytes() for p in root.iterdir()})
    response = client.post('/api/projects/upload', content=data, headers={'Content-Type':'application/zip','X-Filename':'discount.zip'})
    assert response.status_code == 201
    body = response.json()
    return body['project']['project_id'], {'Authorization':'Bearer '+body['capability_token']}


def test_mock_end_to_end_approval(setup):
    client, app, runner = setup
    ident, auth = upload(client)
    prefix = '/api/projects/'+ident
    assert client.get(prefix+'/download', headers=auth).status_code == 403
    assert client.post(prefix+'/analyze', headers=auth).status_code == 202
    result = client.get(prefix+'/results', headers=auth).json()
    assert result['status'] == 'VERIFIED' and result['full_suite_success'] and result['mock_generated']
    assert result['patch']['root_cause'].startswith('MOCK:')
    assert client.post(prefix+'/analyze', headers=auth).status_code == 409
    assert client.post(prefix+'/approve', headers=auth, json={'approve':True}).status_code == 200
    response = client.get(prefix+'/download', headers=auth)
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        assert b'percent / 100' in z.read('pricing.py')
    assert b'percent / 100' not in (app.state.store.projects[ident].root/'original'/'pricing.py').read_bytes()
    assert client.post(prefix+'/approve', headers=auth, json={'approve':False}).status_code == 200
    assert client.get(prefix+'/download', headers=auth).status_code == 403
    assert runner.run.call_count == 3


def test_capabilities_origins_and_expiry(setup):
    client, app, _ = setup
    ident, auth = upload(client)
    prefix = '/api/projects/'+ident
    assert client.get(prefix+'/results').status_code == 403
    assert client.post(prefix+'/analyze').status_code == 403
    assert client.post(prefix+'/analyze', headers=auth | {'Origin':'https://evil.example'}).status_code == 403
    app.state.store.projects[ident].expires_at = time.time()-1
    assert client.get(prefix+'/results', headers=auth).status_code == 410
    assert client.get('/api/health', headers={'Host':'evil.example'}).status_code == 400


def test_missing_docker(setup):
    client, _, runner = setup
    runner.run.side_effect = SafeError(UNAVAILABLE)
    ident, auth = upload(client)
    client.post(f'/api/projects/{ident}/analyze', headers=auth)
    result = client.get(f'/api/projects/{ident}/results', headers=auth).json()
    assert result['status'] == 'INCONCLUSIVE' and result['message'] == UNAVAILABLE


def test_unverified_approval_blocked(setup):
    client, _, runner = setup
    runner.run.side_effect = [outcome({'t':'failed'}), outcome({'t':'failed'}), outcome({'t':'failed'})]
    ident, auth = upload(client)
    client.post(f'/api/projects/{ident}/analyze', headers=auth)
    assert client.post(f'/api/projects/{ident}/approve', headers=auth, json={'approve':True}).status_code == 409


def test_candidate_integrity(setup):
    client, app, _ = setup
    ident, auth = upload(client)
    client.post(f'/api/projects/{ident}/analyze', headers=auth)
    (app.state.store.projects[ident].root/'candidate'/'pricing.py').write_text('changed = True')
    assert client.post(f'/api/projects/{ident}/approve', headers=auth, json={'approve':True}).status_code == 409


def test_upload_validation_and_limit(setup):
    client, _, _ = setup
    headers = {'Content-Type':'application/zip','X-Filename':'a.zip'}
    assert client.post('/api/projects/upload', content=b'bad', headers=headers).status_code == 400
    assert client.post('/api/projects/upload', content=b'x'* (5*1024**2+1), headers=headers).status_code == 413
    for _ in range(5):
        client.post('/api/projects/upload', content=b'bad', headers=headers)
    assert client.post('/api/projects/upload', content=b'bad', headers=headers).status_code == 429


def test_runner_is_hardened(tmp_path, monkeypatch):
    runner = DockerRunner(Settings())
    command = runner.command(tmp_path, 'test', None)
    for flag in ['--network=none','--cpus=1','--memory=256m','--pids-limit=64','--cap-drop=ALL','--security-opt=no-new-privileges','--read-only','--user=10001:10001','--pull=never']:
        assert flag in command
    assert 'readonly' in command[command.index('--mount')+1]
    assert '--privileged' not in command
    monkeypatch.setattr('app.runner.subprocess.run', MagicMock(side_effect=FileNotFoundError))
    assert not runner.available()
    with pytest.raises(SafeError, match='Sandbox execution unavailable'):
        runner.run(tmp_path)
