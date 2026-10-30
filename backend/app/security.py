import ast
import io
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from .config import Settings


class SafeError(Exception):
    """Only curated, client-safe messages belong in this exception."""


def safe_path(name: str) -> str:
    if not name or '\\' in name or len(name) > 200 or ':' in name:
        raise SafeError('Archive contains an unsafe path.')
    parts = name.rstrip('/').split('/')
    reserved = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(10)), *(f'LPT{i}' for i in range(10))}
    if any(p in ('', '.', '..') or p.startswith('.') or p.endswith((' ', '.')) or
           p.split('.')[0].upper() in reserved or not re.fullmatch(r'[A-Za-z0-9_ .-]+', p) for p in parts):
        raise SafeError('Archive contains an unsafe or hidden path.')
    return str(PurePosixPath(*parts))


def source_allowed(name: str) -> bool:
    p = PurePosixPath(name)
    return (p.suffix == '.py' and not any(x.lower() in ('test', 'tests', '__pycache__') for x in p.parts)
            and not p.name.lower().startswith(('test_', 'conftest', 'setup', 'sitecustomize', 'usercustomize'))
            and p.name.lower() not in ('config.py', 'settings.py', 'noxfile.py', 'tasks.py')
            and not p.name.lower().endswith('_test.py')
            and not any(x.startswith('.') for x in p.parts))


def extract_zip(data: bytes, dest: Path, cfg: Settings) -> list[str]:
    if len(data) > cfg.max_upload:
        raise SafeError('Compressed upload exceeds the configured size limit.')
    records: list[tuple[str, bytes]] = []
    seen: set[str] = set()
    total = 0
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if len(archive.infolist()) > cfg.max_files:
                raise SafeError('Archive contains too many entries.')
            for entry in archive.infolist():
                # ZipInfo normalizes backslashes on Windows and truncates NULs in filename.
                # Validate the original central-directory name before either normalization.
                name = safe_path(entry.orig_filename)
                kind = stat.S_IFMT(entry.external_attr >> 16)
                if kind not in (0, stat.S_IFREG, stat.S_IFDIR) or entry.flag_bits & 1:
                    raise SafeError('Links, special files and encrypted entries are unsupported.')
                if name.casefold() in seen:
                    raise SafeError('Archive contains duplicate paths.')
                seen.add(name.casefold())
                if entry.is_dir():
                    continue
                p = PurePosixPath(name)
                if p.suffix != '.py' and p.name.lower() not in ('readme.md', 'readme.txt', 'license', 'requirements.txt', 'pyproject.toml'):
                    raise SafeError('Only Python source and README, LICENSE, requirements.txt or pyproject.toml metadata are accepted.')
                if any(word in p.stem.lower() for word in ('credential', 'secret')) or p.name in ('sitecustomize.py', 'usercustomize.py'):
                    raise SafeError('Sensitive or interpreter startup files are unsupported.')
                total += entry.file_size
                if entry.file_size > cfg.max_file or total > cfg.max_extracted or entry.file_size > max(1, entry.compress_size) * 200:
                    raise SafeError('Archive exceeds extraction size or compression ratio limits.')
                with archive.open(entry) as stream:
                    content = stream.read(cfg.max_file + 1)
                if len(content) != entry.file_size or b'\x00' in content:
                    raise SafeError('Invalid or binary archive content.')
                decoded = content.decode('utf-8')
                if p.suffix == '.py':
                    try:
                        ast.parse(decoded)
                    except (SyntaxError, ValueError, RecursionError):
                        raise SafeError('Project contains malformed Python source.') from None
                records.append((name, content))
    except (zipfile.BadZipFile, UnicodeError, RuntimeError, NotImplementedError, OSError):
        raise SafeError('Invalid, corrupted or unsupported ZIP archive.') from None
    if not any(n.endswith('.py') for n, _ in records):
        raise SafeError('Project must contain Python source.')
    file_names = {n.casefold() for n, _ in records}
    for name, _ in records:
        if any(str(parent).casefold() in file_names for parent in PurePosixPath(name).parents if str(parent) != '.'):
            raise SafeError('Archive contains conflicting file and directory paths.')
    # Normalize a single wrapper directory, as produced by GitHub ZIP downloads.
    prefixes = {n.split('/')[0] for n, _ in records}
    strip = len(prefixes) == 1 and all('/' in n for n, _ in records)
    names = []
    for name, content in records:
        name = name.split('/', 1)[1] if strip else name
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        names.append(name)
    return names
