import hashlib
import secrets
import shutil
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from .config import Settings
from .schemas import Result


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


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for p in sorted(root.rglob('*')):
        if p.is_file():
            digest.update(p.relative_to(root).as_posix().encode())
            digest.update(b'\x00')
            digest.update(p.read_bytes())
    return digest.hexdigest()


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
