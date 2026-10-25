"""PP-4: StagingArtifactSource reads artifacts from a staging directory and never leaves it."""
from __future__ import annotations

import ast
import hashlib
import inspect
import pathlib

import pytest

import controlplane.infrastructure.production_ports.artifact_source as artifact_source_module
from controlplane.infrastructure.production_ports.artifact_source import StagingArtifactSource
from controlplane.infrastructure.storage.drive_object_store import ArtifactSourcePort

SOURCE = pathlib.Path(artifact_source_module.__file__)
PAYLOAD = bytes(range(256)) * 40 + b'pp-4 tail'
ARTIFACT_ID = 'artifact-v1.bin'
BS = chr(92)


@pytest.fixture()
def staging(tmp_path: pathlib.Path) -> pathlib.Path:
    root = tmp_path / 'staging'
    root.mkdir()
    (root / ARTIFACT_ID).write_bytes(PAYLOAD)
    return root


def snapshot(root: pathlib.Path) -> dict[str, bytes | None]:
    return {p.name: (p.read_bytes() if p.is_file() else None) for p in sorted(root.iterdir())}


def assert_invalid(root: pathlib.Path, ref: object) -> None:
    with pytest.raises(ValueError) as info:
        StagingArtifactSource(root).open(ref)  # type: ignore[arg-type]
    assert str(info.value) == 'INVALID_ARTIFACT_REF'


def test_signature_matches_artifact_source_port() -> None:
    port_params = list(inspect.signature(ArtifactSourcePort.open).parameters)
    impl_params = list(inspect.signature(StagingArtifactSource.open).parameters)
    assert port_params == impl_params == ['self', 'artifact_version_id']


def test_open_returns_exact_bytes_and_sha256(staging: pathlib.Path) -> None:
    with StagingArtifactSource(staging).open(ARTIFACT_ID) as stream:
        data = stream.read()
    assert data == PAYLOAD
    assert hashlib.sha256(data).hexdigest() == hashlib.sha256(PAYLOAD).hexdigest()


def test_stream_supports_size_probe_then_rewind(staging: pathlib.Path) -> None:
    with StagingArtifactSource(staging).open(ARTIFACT_ID) as stream:
        assert stream.seekable()
        stream.seek(0, 2)
        assert stream.tell() == len(PAYLOAD)
        stream.seek(0)
        assert stream.read(16) == PAYLOAD[:16]


def test_stream_is_read_only(staging: pathlib.Path) -> None:
    with StagingArtifactSource(staging).open(ARTIFACT_ID) as stream:
        assert stream.mode == 'rb' and not stream.writable()
        with pytest.raises(OSError):
            stream.write(b'x')
    assert (staging / ARTIFACT_ID).read_bytes() == PAYLOAD


@pytest.mark.parametrize('artifact_id', ['a', 'Z', '0', 'a.b', 'a_b', 'a-b', 'a..b'])
def test_accepts_ids_matching_the_pattern(staging: pathlib.Path, artifact_id: str) -> None:
    (staging / artifact_id).write_bytes(artifact_id.encode('ascii'))
    with StagingArtifactSource(staging).open(artifact_id) as stream:
        assert stream.read() == artifact_id.encode('ascii')


def test_accepts_id_of_exactly_128_chars(staging: pathlib.Path) -> None:
    artifact_id = 'a' * 128
    try:
        (staging / artifact_id).write_bytes(b'x')
    except OSError:
        pytest.skip('host path limit rejects a 128-character file name')
    with StagingArtifactSource(staging).open(artifact_id) as stream:
        assert stream.read() == b'x'

BAD_IDS = [
    '..', '.', '../x', '..' + BS + 'x', 'a/b', 'a' + BS + 'b', '/etc/passwd', 'C:x', 'C:' + BS + 'x', 'C:/x',
    '', ' ', 'a b', 'a' * 129, 'a' + chr(0) + 'b', 'a' + chr(31) + 'b', 'a' + chr(127) + 'b',
    'a' + chr(10) + 'b', 'a' + chr(10), 'a' + chr(13), 'a' + chr(9) + 'b',
    '.hidden', '-lead', '_lead', chr(233), 'a:b', 'a*b', 'a?b',
]


@pytest.mark.parametrize('artifact_id', BAD_IDS)
def test_rejects_ids_outside_the_pattern(staging: pathlib.Path, artifact_id: str) -> None:
    before = snapshot(staging)
    assert_invalid(staging, artifact_id)
    assert snapshot(staging) == before


@pytest.mark.parametrize('artifact_id', [None, 1, b'a', pathlib.PurePath('a')])
def test_rejects_non_string_ids(staging: pathlib.Path, artifact_id: object) -> None:
    assert_invalid(staging, artifact_id)


def test_rejects_absolute_path_to_existing_file(staging: pathlib.Path, tmp_path: pathlib.Path) -> None:
    outside = tmp_path / 'outside.bin'
    outside.write_bytes(b'secret')
    for ref in (str(outside), outside.as_posix(), str(staging / ARTIFACT_ID)):
        assert_invalid(staging, ref)
    assert outside.read_bytes() == b'secret'


def test_rejects_traversal_to_existing_outside_file(staging: pathlib.Path, tmp_path: pathlib.Path) -> None:
    outside = tmp_path / 'outside.bin'
    outside.write_bytes(b'secret')
    for ref in ('../outside.bin', '..' + BS + 'outside.bin', 'staging/../outside.bin'):
        assert_invalid(staging, ref)
    assert outside.read_bytes() == b'secret'

def test_rejects_symlink_pointing_outside_staging(staging: pathlib.Path, tmp_path: pathlib.Path) -> None:
    outside = tmp_path / 'outside.bin'
    outside.write_bytes(b'secret')
    try:
        (staging / 'link.bin').symlink_to(outside)
    except OSError:
        pytest.skip('host forbids creating symlinks')
    assert_invalid(staging, 'link.bin')
    assert outside.read_bytes() == b'secret'


def test_missing_file_raises_file_not_found(staging: pathlib.Path) -> None:
    with pytest.raises(FileNotFoundError):
        StagingArtifactSource(staging).open('missing.bin')


def test_missing_staging_root_raises_file_not_found(tmp_path: pathlib.Path) -> None:
    with pytest.raises(FileNotFoundError):
        StagingArtifactSource(tmp_path / 'absent').open(ARTIFACT_ID)


def test_directory_instead_of_file_is_invalid(staging: pathlib.Path) -> None:
    (staging / 'adir').mkdir()
    assert_invalid(staging, 'adir')


@pytest.mark.parametrize('root', [pathlib.Path('staging'), pathlib.Path('.'), pathlib.Path('..') / 'staging', 'staging', None])
def test_staging_root_must_be_an_absolute_path(root: object) -> None:
    with pytest.raises(ValueError):
        StagingArtifactSource(root)  # type: ignore[arg-type]


def test_source_is_independent_and_read_only() -> None:
    raw = SOURCE.read_text(encoding='utf-8')
    text = raw.lower()
    for banned in ('controlplane.api', 'from src.', 'mock', 'fake', 'os.environ', 'getenv', 'resolve_under_root', 'unlink', 'rmtree', '.write', '.mkdir', '.touch', '.rename', "'w'", "'wb'", "'ab'", "'r+b'", 'subprocess'):
        assert banned not in text, banned
    for required in ('stagingartifactsource', 'invalid_artifact_ref', 'fullmatch', '.resolve()', "'rb'"):
        assert required in text, required
    imported: set[str] = set()
    for node in ast.walk(ast.parse(raw)):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split('.')[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or '').split('.')[0])
    assert imported <= {'__future__', 're', 'pathlib', 'typing'}, imported
