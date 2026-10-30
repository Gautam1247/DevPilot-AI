"""Fixed entry point. Runs ONLY in the Docker image, never on the API host."""
import json
import sys
import pytest


class Evidence:
    def __init__(self):
        self.tests = {}
        self.collected = []
        self.errors = []

    def pytest_collection_finish(self, session):
        self.collected = [item.nodeid for item in session.items]

    def pytest_collectreport(self, report):
        if report.failed:
            self.errors.append(str(report.longrepr)[:3000])

    def pytest_runtest_logreport(self, report):
        previous = self.tests.get(report.nodeid)
        if report.failed:
            self.tests[report.nodeid] = 'failed'
        elif previous != 'failed':
            if report.skipped:
                self.tests[report.nodeid] = 'skipped'
            elif report.when == 'call':
                self.tests[report.nodeid] = 'passed'


if __name__ == '__main__':
    sys.path.insert(0, '/project')
    evidence = Evidence()
    args = ['-c', '/runner/pytest.ini', '--rootdir=/project', '--noconftest', '-p', 'no:cacheprovider', '--tb=short', '-q', '--', *sys.argv[1:]]
    code = int(pytest.main(args, plugins=[evidence]))
    report = dict(tests=evidence.tests, collected=evidence.collected, errors=evidence.errors,
                  exit_code=code, complete=code in (0, 1) and not evidence.errors)
    print('\nDEVPILOT_REPORT=' + json.dumps(report), flush=True)
    sys.exit(code)
