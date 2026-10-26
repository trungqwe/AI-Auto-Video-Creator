"""Recording fake adapters and the import guard for the prod_wiring tests (PW-H0).

This module lives under tests/ only: nothing under src/ may import it (see assert_no_support_import).
"""
from __future__ import annotations

import ast
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import psycopg

from render.ports.lease import GpuLease, GpuLeaseUnavailable

SUPPORT_MODULE = 'pw_support'


def database_exists(admin_dsn: str, name: str) -> bool:
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        return admin.execute('SELECT 1 FROM pg_database WHERE datname = %s', (name,)).fetchone() is not None


@dataclass(frozen=True)
class RecordedCall:
    method: str
    args: tuple[object, ...]
    kwargs: Mapping[str, object]


class RecordingFake:
    """Base of every fake: each public method calls _record first, so failed calls are counted too.

    results maps a method name to a value (or a callable invoked with the call arguments); errors maps a method name to an exception to raise.
    """

    def __init__(self, *, results: Mapping[str, object] | None = None, errors: Mapping[str, BaseException] | None = None) -> None:
        self.calls: list[RecordedCall] = []
        self._results = dict(results or {})
        self._errors = dict(errors or {})

    def _record(self, method: str, *args: object, **kwargs: object) -> object:
        self.calls.append(RecordedCall(method, args, dict(kwargs)))
        error = self._errors.get(method)
        if error is not None:
            raise error
        result = self._results.get(method)
        return result(*args, **kwargs) if callable(result) else result

    def calls_to(self, method: str | None = None) -> list[RecordedCall]:
        return [call for call in self.calls if method is None or call.method == method]

    def call_count(self, method: str | None = None) -> int:
        return len(self.calls_to(method))


class FakeRouter(RecordingFake):
    """Stands in for the provider route (resolve) and the routed AI invocation (invoke)."""

    def resolve(self, request: Mapping[str, object]) -> object:
        return self._record('resolve', request)

    def invoke(self, decision: object, envelope: object) -> object:
        return self._record('invoke', decision, envelope)

    @property
    def requests(self) -> list[object]:
        return [call.args[0] for call in self.calls_to('resolve')]


@dataclass(frozen=True)
class FakeDriveObject:
    name: str
    content: bytes
    mime_type: str


class FakeDrive(RecordingFake):
    """In-memory stand-in for Google Drive: no network; objects are keyed by generated ids."""

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.objects: dict[str, FakeDriveObject] = {}

    def upload(self, name: str, content: bytes, *, mime_type: str = 'application/octet-stream') -> str:
        self._record('upload', name, content, mime_type=mime_type)
        file_id = 'fake-drive-' + str(self.call_count('upload'))
        self.objects[file_id] = FakeDriveObject(name=name, content=content, mime_type=mime_type)
        return file_id

    def download(self, file_id: str) -> bytes:
        self._record('download', file_id)
        return self.objects[file_id].content

    def delete(self, file_id: str) -> None:
        self._record('delete', file_id)
        self.objects.pop(file_id, None)


class FakeKokoro(RecordingFake):
    """Stand-in for the Kokoro TTS engine (TtsEnginePort.synthesize)."""

    def synthesize(self, decision: object, script_text: object, request: Mapping[str, object]) -> object:
        return self._record('synthesize', decision, script_text, request)


class FakeAligner(RecordingFake):
    """Stand-in for the word aligner (AlignerPort.align)."""

    def align(self, request: object) -> object:
        return self._record('align', request)


class FakeGpu(RecordingFake):
    """Stand-in for the GPU lease (GpuLeasePort); capacity=None means unlimited slots."""

    def __init__(self, *, capacity: int | None = None, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.capacity = capacity
        self.held: dict[str, GpuLease] = {}

    def acquire(self, owner_ref: str) -> GpuLease:
        self._record('acquire', owner_ref)
        if self.capacity is not None and len(self.held) >= self.capacity:
            raise GpuLeaseUnavailable('no free slot for ' + owner_ref)
        lease = GpuLease(lease_id='fake-gpu-' + str(self.call_count('acquire')), owner_ref=owner_ref)
        self.held[lease.lease_id] = lease
        return lease

    def release(self, lease: GpuLease) -> None:
        self._record('release', lease)
        self.held.pop(lease.lease_id, None)


def _is_dynamic_import(call: ast.Call) -> bool:
    func = call.func
    name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ''
    if name not in {'__import__', 'import_module'} or not call.args:
        return False
    first = call.args[0]
    return isinstance(first, ast.Constant) and isinstance(first.value, str) and SUPPORT_MODULE in first.value.split('.')


def _support_import_lines(tree: ast.AST) -> list[int]:
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            hit = any(SUPPORT_MODULE in alias.name.split('.') for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            hit = SUPPORT_MODULE in (node.module or '').split('.') or any(alias.name == SUPPORT_MODULE for alias in node.names)
        elif isinstance(node, ast.Call):
            hit = _is_dynamic_import(node)
        else:
            continue
        if hit:
            lines.append(node.lineno)
    return lines


def assert_no_support_import(root: Path) -> None:
    """Fail closed unless every *.py under root parses and none of them imports pw_support (static, dotted, relative or dynamic)."""
    root = Path(root)
    if not root.is_dir():
        raise AssertionError('not a directory: ' + str(root))
    offenders: list[str] = []
    for path in sorted(root.rglob('*.py')):
        try:
            tree = ast.parse(path.read_bytes(), filename=str(path))
        except (SyntaxError, ValueError) as exc:
            offenders.append(str(path) + ': unparsable (' + str(exc) + ')')
            continue
        offenders.extend(str(path) + ':' + str(line) for line in _support_import_lines(tree))
    if offenders:
        raise AssertionError('pw_support must not be imported from production code: ' + '; '.join(offenders))
