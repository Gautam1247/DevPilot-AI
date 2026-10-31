import json
import re
import subprocess
import threading
import time
import uuid
from pathlib import Path
from .config import Settings
from .schemas import TestRun
from .security import SafeError

UNAVAILABLE = 'Sandbox execution unavailable. Start Docker Desktop to enable analysis.'


def parse_report(raw: str, exit_code: int) -> TestRun:
    # A single final frame avoids silently choosing an injected trailing report.
    # This is framing/consistency validation, NOT authentication of pytest code.
    frames = list(re.finditer(r'^DEVPILOT_REPORT=([^\n]*)', raw, re.MULTILINE))
    if len(frames) != 1 or raw[frames[0].end():].strip():
        return TestRun(exit_code=exit_code, errors=['Missing, duplicate or non-final test evidence.'], logs=raw[-24000:])
    def unique_keys(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('Duplicate evidence key.')
            value[key] = item
        return value
    try:
        report = TestRun.model_validate(json.loads(frames[0].group(1), object_pairs_hook=unique_keys))
    except (ValueError, TypeError, RecursionError):
        return TestRun(exit_code=exit_code, errors=['Invalid test evidence.'], logs=raw[-24000:])
    if report.exit_code != exit_code or not report.has_complete_evidence():
        report.complete = False
        report.errors.append('Incomplete or inconsistent test evidence.')
    # The host-observed process result is authoritative, including pytest exit 5.
    report.exit_code = exit_code
    report.logs = raw[:frames[0].start()][-24000:]
    return report


class DockerRunner:
    def __init__(self, cfg: Settings):
        self.cfg = cfg

    def available(self) -> bool:
        try:
            result = subprocess.run(['docker', 'info', '--format', '{{.OSType}}'], capture_output=True, timeout=5)
            return result.returncode == 0 and result.stdout.strip() == b'linux'
        except (OSError, subprocess.TimeoutExpired):
            return False

    def command(self, root: Path, name: str, target: str | None) -> list[str]:
        return ['docker', 'run', '--rm', '--pull=never', '--name', name,
                '--network=none', '--cpus=1', '--memory=256m', '--memory-swap=256m',
                '--pids-limit=64', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                '--read-only', '--user=10001:10001', '--ulimit', 'nofile=128:128',
                '--log-driver=none', '--tmpfs', '/tmp:rw,noexec,nosuid,size=64m,mode=1777',
                '--mount', f'type=bind,source={root.resolve()},target=/project,readonly',
                self.cfg.image, *([target] if target else [])]

    def run(self, root: Path, target: str | None = None) -> TestRun:
        if not self.available():
            raise SafeError(UNAVAILABLE)
        if ',' in str(root):
            raise SafeError('The workspace path cannot contain commas for Docker mounts.')
        if target and (len(target) > 500 or target.startswith('-') or '\x00' in target):
            raise SafeError('Unsupported test identifier.')
        name = 'devpilot-' + uuid.uuid4().hex
        start = time.monotonic()
        output = bytearray()
        exceeded = threading.Event()
        process = subprocess.Popen(self.command(root, name, target), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        def read_output():
            while chunk := process.stdout.read(4096):
                room = max(0, 256 * 1024 - len(output))
                output.extend(chunk[:room])
                if len(chunk) > room:
                    exceeded.set()
                    process.kill()
                    break

        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()
        timed_out = False
        try:
            process.wait(timeout=self.cfg.timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
        finally:
            # Killing the CLI alone does not stop its container.
            try:
                subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                pass
            process.wait(timeout=5)
            reader.join(timeout=5)
            process.stdout.close()
        raw = output.decode('utf-8', errors='replace')
        raw = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', raw)
        raw = raw.replace(str(root.resolve()), '<project>')
        if timed_out or exceeded.is_set():
            return TestRun(timed_out=timed_out, errors=['Execution timeout.' if timed_out else 'Test output exceeded limit.'], logs=raw[:24000], duration=time.monotonic()-start)
        if process.returncode == 125:
            raise SafeError('Sandbox could not start. Build devpilot-runner:local and check Docker Desktop file sharing.')
        report = parse_report(raw, process.returncode)
        report.duration = time.monotonic()-start
        return report
