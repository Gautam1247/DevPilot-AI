import hashlib
import secrets
import shutil
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from .config import Settings
from .schemas import Result
from .security import SafeError


@dataclass
class Project:
    root: Path
    token_hash: str
    expires_at: float
    result: Result
    lock: threading.Lock = field(default_factory=threading.Lock)
    candidate_hash: str = ''

    def save(self):
        self.root.joinpath('result.json').write_text(self.result.model_dump_json(indent=2), encoding='utf-8')


def snapshot_files(root: Path) -> list[tuple[str, bytes]]:
    def linked(path):
        return path.is_symlink() or getattr(path, 'is_junction', lambda: False)()
    if linked(root) or not root.is_dir():
        raise SafeError('Candidate workspace is missing or linked.')
    files = []
    for p in sorted(root.rglob('*')):
        if linked(p):
            raise SafeError('Candidate contains a filesystem link.')
        if p.is_file():
            files.append((p.relative_to(root).as_posix(), p.read_bytes()))
    return files


def snapshot_hash(files: list[tuple[str, bytes]]) -> str:
    digest = hashlib.sha256()
    for name, content in files:
        encoded = name.encode('utf-8')
        # Length-prefix both fields so different file trees cannot concatenate
        # to the same input without breaking SHA-256 itself.
        digest.update(len(encoded).to_bytes(8, 'big'))
        digest.update(encoded)
        digest.update(len(content).to_bytes(8, 'big'))
        digest.update(content)
    return digest.hexdigest()


def tree_hash(root: Path) -> str:
    return snapshot_hash(snapshot_files(root))


class Store:
    def __init__(self, cfg: Settings):
        self.cfg = cfg
        self.projects: dict[str, Project] = {}
        cfg.workspace.mkdir(parents=True, exist_ok=True)

    def cleanup(self):
        # Only direct, generated directories within this controlled root.
        import re
        for p in self.cfg.workspace.iterdir():
            if p.is_dir() and not p.is_symlink() and re.fullmatch('[a-f0-9]{32}', p.name):
                if time.time() - p.stat().st_mtime > self.cfg.ttl:
                    shutil.rmtree(p)

    def create(self, name: str) -> tuple[Project, str]:
        ident, token = secrets.token_hex(16), secrets.token_urlsafe(32)
        root = self.cfg.workspace / ident
        (root / 'original').mkdir(parents=True)
        result = Result(project_id=ident, name=name, created_at=time.time(), model='MOCK' if self.cfg.mock_ai else self.cfg.model, mock_generated=self.cfg.mock_ai)
        project = Project(root, hashlib.sha256(token.encode()).hexdigest(), time.time() + self.cfg.ttl, result)
        self.projects[ident] = project
        return project, token
