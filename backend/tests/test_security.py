import io
import zipfile
import pytest
from app.config import Settings
from app.security import SafeError, extract_zip


def archive(files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as z:
        for name, value in files.items():
            entry = zipfile.ZipInfo()
            entry.filename = name  # Preserve backslashes on Windows for adversarial ZIP tests.
            z.writestr(entry, value)
    return output.getvalue()


def test_valid(tmp_path):
    assert extract_zip(archive({'project/main.py': 'x = 1'}), tmp_path, Settings()) == ['main.py']


@pytest.mark.parametrize('name', ['../escape.py', '/root.py', 'C:/bad.py', 'a\\b.py', '.env', 'CON.py', 'photo.png', 'secrets.py'])
def test_bad_paths(tmp_path, name):
    with pytest.raises(SafeError):
        extract_zip(archive({name: 'x = 1'}), tmp_path, Settings())


@pytest.mark.parametrize('data', [b'not a zip', archive({'bad.py': 'def !'}), archive({'README.md': 'nothing'})])
def test_malformed(tmp_path, data):
    with pytest.raises(SafeError):
        extract_zip(data, tmp_path, Settings())


def test_size(tmp_path):
    with pytest.raises(SafeError):
        extract_zip(archive({'main.py': 'x=1'}), tmp_path, Settings(max_upload=5))


def test_symlink(tmp_path):
    import stat
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as z:
        entry = zipfile.ZipInfo('link.py')
        entry.external_attr = (stat.S_IFLNK | 0o777) << 16
        z.writestr(entry, '../target')
    with pytest.raises(SafeError, match='Links'):
        extract_zip(output.getvalue(), tmp_path, Settings())


@pytest.mark.parametrize('files', [
    {'main.py':'x=1','MAIN.py':'x=2'},
    {'a.py':'x=1','a.py/b.py':'y=2'},
])
def test_collisions(tmp_path, files):
    with pytest.raises(SafeError):
        extract_zip(archive(files), tmp_path, Settings())


def test_compression_bomb(tmp_path):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('bomb.py', '#'+ 'a'*100000)
    with pytest.raises(SafeError, match='compression ratio'):
        extract_zip(output.getvalue(), tmp_path, Settings())


def test_file_and_count_limits(tmp_path):
    data = archive({'a.py':'x=1','b.py':'y=2'})
    for cfg in (Settings(max_files=1), Settings(max_file=2), Settings(max_extracted=5)):
        with pytest.raises(SafeError):
            extract_zip(data, tmp_path, cfg)


def test_encrypted_entry_rejected(tmp_path):
    data = bytearray(archive({'main.py':'x=1'}))
    data[6] |= 1  # Local-file header encryption flag.
    central = data.index(b'PK\x01\x02')
    data[central+8] |= 1
    with pytest.raises(SafeError, match='encrypted'):
        extract_zip(bytes(data), tmp_path, Settings())


def test_nul_filename_rejected(tmp_path):
    with pytest.raises(SafeError):
        extract_zip(archive({'main.py\x00hidden.py':'x=1'}), tmp_path, Settings())
