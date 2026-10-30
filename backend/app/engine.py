import time
from .ai import Provider, context
from .patching import apply_patch
from .runner import DockerRunner
from .schemas import TestRun
from .security import SafeError
from .workspaces import Project, tree_hash


def verification(baseline: TestRun, targeted: TestRun, candidate: TestRun, target: str) -> tuple[str, str]:
    if not all(r.complete and not r.errors and not r.timed_out and r.exit_code in (0, 1) for r in (baseline, targeted, candidate)):
        return 'INCONCLUSIVE', 'Required test execution did not complete successfully.'
    if baseline.tests.get(target) != 'failed' or not baseline.tests:
        return 'INCONCLUSIVE', 'The target has no baseline failure evidence.'
    if set(targeted.collected) != {target} or set(targeted.tests) != {target}:
        return 'INCONCLUSIVE', 'Targeted verification did not collect exactly the intended test.'
    if set(candidate.collected) != set(baseline.collected) or set(candidate.tests) != set(baseline.tests):
        return 'INCONCLUSIVE', 'Test collection changed; a reliable comparison is unavailable.'
    if targeted.tests.get(target) != 'passed' or candidate.tests.get(target) != 'passed':
        return 'FAILED', 'The originally failing target test still does not pass.'
    if any(candidate.tests.get(t) != 'passed' for t, status in baseline.tests.items() if status == 'passed'):
        return 'FAILED', 'A previously passing test regressed or was skipped.'
    if any(candidate.tests.get(t) == 'failed' for t, status in baseline.tests.items() if status != 'failed'):
        return 'FAILED', 'Verification detected a new failure.'
    return 'VERIFIED', 'The target test now passes with no detected regressions. Review full-suite results for remaining failures.'


class Engine:
    def __init__(self, runner: DockerRunner, provider: Provider):
        self.runner, self.provider = runner, provider

    def analyze(self, project: Project):
        result = project.result
        started = time.monotonic()
        def phase(value):
            result.phase = value
            project.save()
        try:
            phase('running_baseline')
            result.baseline = self.runner.run(project.root / 'original')
            baseline = result.baseline
            if baseline.exit_code == 5:
                raise SafeError('No tests collected. Include pytest test_*.py files in your ZIP.')
            if not baseline.complete or baseline.errors or baseline.timed_out or not baseline.tests:
                raise SafeError('Baseline tests were incomplete: collection error, timeout or invalid evidence. See technical logs.')
            failures = [t for t, outcome in baseline.tests.items() if outcome == 'failed']
            if not failures:
                result.status = 'NO_BASELINE_FAILURE'
                result.message = 'No baseline test failed. No patch was requested.'
                return
            result.target_test = sorted(failures)[0]
            phase('analyzing_failure')
            data = context(project.root / 'original', baseline, result.target_test)
            phase('generating_patch')
            result.patch = self.provider.propose(data)
            phase('validating_patch')
            if result.patch.target_file not in data['sources']:
                raise SafeError('Patch target was not in the supplied source allowlist.')
            result.diff = apply_patch(project.root / 'original', project.root / 'candidate', result.patch)
            project.candidate_hash = tree_hash(project.root / 'candidate')
            phase('running_verification')
            result.targeted = self.runner.run(project.root / 'candidate', result.target_test)
            result.candidate = self.runner.run(project.root / 'candidate')
            if tree_hash(project.root / 'candidate') != project.candidate_hash:
                raise SafeError('Candidate changed during verification.')
            result.status, result.message = verification(baseline, result.targeted, result.candidate, result.target_test)
            result.full_suite_success = result.status == 'VERIFIED' and result.candidate.exit_code == 0 and all(v == 'passed' for v in result.candidate.tests.values())
        except SafeError as exc:
            result.status, result.message = 'INCONCLUSIVE', str(exc)
        except Exception:
            result.status, result.message = 'INCONCLUSIVE', 'Analysis could not complete. Check local service configuration and retry with a new upload.'
        finally:
            result.duration = round(time.monotonic()-started, 2)
            result.phase = 'completed' if result.status in ('VERIFIED', 'NO_BASELINE_FAILURE', 'FAILED') else 'failed'
            project.save()
