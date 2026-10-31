"""Controlled audit fixtures; uploaded Python is never executed on the host."""
import io
import json
import subprocess
from unittest.mock import MagicMock

import pytest
from app.config import Settings
from app.engine import verification
from app.runner import DockerRunner, parse_report
from app.schemas import TestRun as Run
from app.workspaces import tree_hash


def evidence(status='passed', **changes):
    return Run(**(dict(tests={'test_example.py::test_value':status},
                       collected=['test_example.py::test_value'], complete=True,
                       exit_code=int(status == 'failed')) | changes))


def simulated_run(monkeypatch, tmp_path, output, exit_code=0, timeout=False):
    process = MagicMock()
    process.stdout = io.BytesIO(output.encode())
    process.returncode = exit_code
    if timeout:
        process.wait.side_effect = [subprocess.TimeoutExpired('docker', 1), exit_code]
    monkeypatch.setattr('app.runner.subprocess.Popen', lambda *a, **k: process)
    cleanup = MagicMock()
    monkeypatch.setattr('app.runner.subprocess.run', cleanup)
    runner = DockerRunner(Settings())
    monkeypatch.setattr(runner, 'available', lambda: True)
    return runner.run(tmp_path), process, cleanup


def frame(report):
    return 'DEVPILOT_REPORT=' + report.model_dump_json() + '\n'


def test_appended_stdout_report_cannot_replace_failure(monkeypatch, tmp_path):
    raw = frame(evidence('failed')) + frame(evidence())
    result, _, _ = simulated_run(monkeypatch, tmp_path, raw)
    assert not result.complete


def test_tree_digest_has_unambiguous_file_boundaries(tmp_path):
    original, changed = tmp_path/'original', tmp_path/'changed'
    original.mkdir()
    changed.mkdir()
    (original/'a.py').write_bytes(b'x = 1\n')
    (original/'b.py').write_bytes(b'y = 2\n')
    # Same byte stream under the old filename + NUL + content concatenation.
    # This is a storage-tampering fixture, not a valid uploaded Python file.
    (changed/'a.py').write_bytes(b'x = 1\nb.py\x00y = 2\n')
    assert tree_hash(original) != tree_hash(changed)


@pytest.mark.parametrize('changes', [
    {'exit_code':0},
    {'collected':['test_example.py::test_value','test_example.py::test_value']},
    {'collected':[]},
])
def test_inconsistent_baseline_cannot_verify(changes):
    baseline = evidence('failed', **changes)
    assert verification(baseline, evidence(), evidence(), 'test_example.py::test_value')[0] == 'INCONCLUSIVE'


@pytest.mark.parametrize('raw,exit_code', [
    ('', 0),
    ('prefix ' + frame(evidence()), 0),
    (frame(evidence()) + 'unexpected trailing output', 0),
    ('DEVPILOT_REPORT={"exit_code":1,"exit_code":0}\n', 0),
    (frame(evidence()), 1),
    (frame(evidence('failed')), 0),
    (frame(evidence(collected=[])), 0),
    (frame(evidence(collected=['test_example.py::test_value']*2)), 0),
    (frame(evidence(errors=['collection error'])), 0),
    (frame(evidence(complete=False)), 0),
    (frame(evidence(timed_out=True)), 0),
])
def test_invalid_or_incomplete_reports_are_rejected(raw, exit_code):
    assert not parse_report(raw, exit_code).has_complete_evidence()


@pytest.mark.parametrize('status,code', [('passed',0), ('failed',1), ('skipped',0)])
def test_valid_runner_frames_are_accepted(status, code):
    result = parse_report('pytest log\n' + frame(evidence(status)), code)
    assert result.has_complete_evidence() and result.logs == 'pytest log\n'


def test_no_tests_exit_is_preserved():
    result = parse_report(frame(Run(exit_code=5)), 5)
    assert result.exit_code == 5 and not result.has_complete_evidence()


def test_timeout_forces_container_cleanup(monkeypatch, tmp_path):
    result, process, cleanup = simulated_run(monkeypatch, tmp_path, frame(evidence()), timeout=True)
    assert result.timed_out and not result.complete
    process.kill.assert_called_once()
    assert cleanup.call_args.args[0][:3] == ['docker','rm','-f']


def test_output_limit_forces_container_cleanup(monkeypatch, tmp_path):
    result, process, cleanup = simulated_run(monkeypatch, tmp_path, 'x' * (256*1024+1))
    assert not result.complete and 'output exceeded' in result.errors[0]
    assert len(result.logs) <= 24000
    process.kill.assert_called_once()
    assert cleanup.call_args.args[0][:3] == ['docker','rm','-f']


def test_command_mounts_only_readonly_project(tmp_path):
    command = DockerRunner(Settings()).command(tmp_path, 'audit-test', None)
    assert command.count('--mount') == 1
    assert command[command.index('--mount')+1] == f'type=bind,source={tmp_path.resolve()},target=/project,readonly'
    assert command[command.index('--tmpfs')+1] == '/tmp:rw,noexec,nosuid,size=64m,mode=1777'
    assert '--memory-swap=256m' in command
    assert not any('docker.sock' in value for value in command)


def test_snapshot_rejects_a_link(monkeypatch, tmp_path):
    from app.security import SafeError
    from app.workspaces import snapshot_files
    # Windows symlink creation needs privileges; simulate the detected link type.
    (tmp_path/'source.py').write_text('x = 1')
    original = type(tmp_path).is_symlink
    monkeypatch.setattr(type(tmp_path), 'is_symlink', lambda p: p.name == 'source.py' or original(p))
    with pytest.raises(SafeError, match='filesystem link'):
        snapshot_files(tmp_path)
