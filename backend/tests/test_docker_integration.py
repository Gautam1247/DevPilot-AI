"""Opt-in real Docker tests. No real AI calls; uploaded code never runs on host."""
import os
import shutil
from pathlib import Path
import pytest
from app.ai import Provider
from app.config import Settings
from app.engine import Engine
from app.runner import DockerRunner
from app.workspaces import Store


@pytest.mark.skipif(os.getenv('RUN_DOCKER_TESTS') != '1', reason='Set RUN_DOCKER_TESTS=1 with Docker running and image built.')
@pytest.mark.parametrize('benchmark', ['discount_bug','off_by_one_bug','sorting_bug'])
def test_real_benchmark(tmp_path, benchmark):
    cfg = Settings(workspace=tmp_path, mock_ai=True)
    project, _ = Store(cfg).create(benchmark+'.zip')
    source = Path(__file__).resolve().parents[2]/'benchmarks'/benchmark
    shutil.copytree(source, project.root/'original', dirs_exist_ok=True)
    Engine(DockerRunner(cfg), Provider(cfg)).analyze(project)
    assert project.result.status == 'VERIFIED', project.result.message
    assert project.result.full_suite_success
