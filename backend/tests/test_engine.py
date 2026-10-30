import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest
from app.ai import Provider
from app.config import Settings
from app.engine import Engine, verification
from app.patching import apply_patch
from app.schemas import Patch, TestRun as Run
from app.security import SafeError
from app.workspaces import Store


def run(tests, code=None, **kwargs):
    return Run(tests=tests, collected=list(tests), exit_code=code if code is not None else int('failed' in tests.values()), complete=True, **kwargs)


def patch(**kwargs):
    return Patch(**(dict(root_cause='Percentage is not a fraction.', target_file='pricing.py', original_code='price * (1 - percent)', replacement_code='price * (1 - percent / 100)', explanation='Divide by 100.', confidence=.9) | kwargs))


@pytest.fixture
def original(tmp_path):
    root = tmp_path/'original'
    shutil.copytree(Path(__file__).resolve().parents[2]/'benchmarks'/'discount_bug', root)
    return root


@pytest.mark.parametrize('changes', [
    {'target_file':'test_pricing.py'}, {'target_file':'../pricing.py'}, {'target_file':'.env'},
    {'target_file':'new.py'}, {'target_file':'config.py'}, {'original_code':'not present'},
    {'replacement_code':'!invalid'}, {'replacement_code':'__import__("os")'},
    {'replacement_code':'0\nimport requests'},
])
def test_disallowed_patch(original, changes):
    with pytest.raises(SafeError):
        apply_patch(original, original.parent/'candidate', patch(**changes))


def test_ambiguous(original):
    p = original/'pricing.py'
    p.write_text(p.read_text()+'\n# price * (1 - percent)\n')
    with pytest.raises(SafeError, match='ambiguous'):
        apply_patch(original, original.parent/'candidate', patch())


def test_original_unchanged(original):
    before = (original/'pricing.py').read_bytes()
    diff = apply_patch(original, original.parent/'candidate', patch())
    assert '+    return price * (1 - percent / 100)' in diff
    assert (original/'pricing.py').read_bytes() == before


@pytest.mark.parametrize('candidate,expected', [
    ({'target':'passed','safe':'passed'}, 'VERIFIED'),
    ({'target':'failed','safe':'passed'}, 'FAILED'),
    ({'target':'passed','safe':'failed'}, 'FAILED'),
    ({'target':'passed','safe':'skipped'}, 'FAILED'),
    ({'target':'passed'}, 'INCONCLUSIVE'),
])
def test_verification(candidate, expected):
    baseline = run({'target':'failed','safe':'passed'})
    assert verification(baseline, run({'target':'passed'}), run(candidate), 'target')[0] == expected


def test_partial_improvement():
    baseline = run({'target':'failed','other':'failed','safe':'passed'})
    candidate = run({'target':'passed','other':'failed','safe':'passed'})
    assert verification(baseline, run({'target':'passed'}), candidate, 'target')[0] == 'VERIFIED'


def test_timeout_is_inconclusive():
    assert verification(run({'t':'failed'}), Run(timed_out=True), run({'t':'passed'}), 't')[0] == 'INCONCLUSIVE'


@pytest.mark.parametrize('baseline,message,status', [
    (run({}, code=5), 'No tests collected', 'INCONCLUSIVE'),
    (Run(errors=['collection failed'], exit_code=2), 'Baseline tests were incomplete', 'INCONCLUSIVE'),
    (run({'t':'passed'}), 'No baseline test failed', 'NO_BASELINE_FAILURE'),
])
def test_baseline_outcomes(tmp_path, baseline, message, status):
    cfg = Settings(workspace=tmp_path, mock_ai=True)
    p, _ = Store(cfg).create('demo.zip')
    runner, provider = MagicMock(), MagicMock()
    runner.run.return_value = baseline
    Engine(runner, provider).analyze(p)
    assert p.result.status == status and message in p.result.message
    provider.propose.assert_not_called()


def test_missing_key():
    with pytest.raises(SafeError, match='key missing'):
        Provider(Settings(api_key='', mock_ai=False)).propose({})


def test_malformed_ai(monkeypatch):
    client = MagicMock()
    generate = AsyncMock(return_value=MagicMock(text='{"unexpected":true}'))
    client.__enter__.return_value.aio.__aenter__.return_value.models.generate_content = generate
    monkeypatch.setattr('app.ai.genai.Client', lambda **kwargs: client)
    with pytest.raises(SafeError, match='malformed'):
        Provider(Settings(api_key='test-only', mock_ai=False)).propose({})
    assert generate.await_count == 1


@pytest.mark.parametrize('code,fragment', [(400,'rejected'),(401,'invalid'),(403,'denied'),(404,'unavailable'),(429,'quota')])
def test_gemini_errors(monkeypatch, code, fragment):
    from google.genai.errors import APIError
    client = MagicMock()
    client.__enter__.return_value.aio.__aenter__.return_value.models.generate_content = AsyncMock(side_effect=APIError(code, {'error': {'message':'Do not expose raw server text'}}))
    monkeypatch.setattr('app.ai.genai.Client', lambda **kwargs: client)
    with pytest.raises(SafeError, match=fragment):
        Provider(Settings(api_key='test-only', mock_ai=False)).propose({})
