"""A-14: raw snapshot handoff to I through ArtifactPort.

coveredIds: A-RULE-015
"""
from __future__ import annotations

import ast
import dataclasses
from datetime import date, datetime, timezone
import hashlib
import pathlib
import socket
import sys

import pytest

from source_ingestion.adapters.memory import FakeArtifactPort
from source_ingestion.adapters.stdlib_html_extractor import StdlibHtmlExtractor
from source_ingestion.application.artifact_handoff import (
    HandoffError,
    HandoffStatus,
    RawSnapshotPolicy,
    ReconciliationPendingError,
    handoff_raw_snapshot,
    snapshot_operation_key,
)
from source_ingestion.application.package_builder import PackageContext, build_package
from source_ingestion.domain.collection_run import (
    AttemptOutcome,
    CollectionPurpose,
    ReconciliationResult,
    RetryPolicy,
    RunStatus,
    reconcile,
    resume_retry,
    schedule_run,
    start_run,
)
from source_ingestion.domain.package import validate_package_schema
from source_ingestion.ports.partners import ArtifactPort
from source_ingestion.ports.source_adapter import FetchedDocument, FetchObservation

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'source_ingestion' / 'application' / 'artifact_handoff.py'
SOURCE_ID = '00000000-0000-4000-8000-000000000002'
RUN_ID = '00000000-0000-4000-8000-000000000003'
FETCHED_AT = datetime(2026, 10, 18, 8, 0, 0, tzinfo=timezone.utc)
NETWORK_FUNCTIONS = ('getaddrinfo', 'create_connection', 'gethostbyname', 'gethostbyname_ex')
BODY = '<html lang="vi"><head><title>Tiêu đề</title></head><body><p>Nội dung bài viết</p></body></html>'.encode('utf-8')
# Test-only policy values; A has no defaults for them.
POLICY = RawSnapshotPolicy(
    'snapshot-policy-fixture-r1',
    'raw_snapshot_fixture',
    'retention-fixture-r7',
    'sensitivity-fixture',
    'storage-class-fixture',
)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _network_forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError('real DNS/network call in integration test')

    for name in NETWORK_FUNCTIONS:
        monkeypatch.setattr(socket, name, _network_forbidden)


def make_document(body: bytes = BODY) -> FetchedDocument:
    url = 'https://example.com/news/article-1'
    headers = (('content-type', 'text/html; charset=utf-8'),)
    observation = FetchObservation(url, url, (url,), 200, 'text/html', len(body), headers, 'fetch-policy-r1')
    return FetchedDocument(observation, body)


def scheduled_run(max_attempts: int = 3):
    return schedule_run(
        run_id=RUN_ID,
        workspace_id='workspace-1',
        source_id=SOURCE_ID,
        business_date=date(2026, 10, 18),
        purpose=CollectionPurpose.PERIODIC,
        retry_policy=RetryPolicy('retry-r1', max_attempts),
    )


def running_run(max_attempts: int = 3):
    return start_run(scheduled_run(max_attempts), source_active=True, checkpoint_ref='cp-0')


class RecordingArtifactPort:
    """Fake I: idempotent on (producer_operation_ref, content_sha256); can time out after creating the object."""

    def __init__(self, *, timeout_after_create: bool = False, extra: dict | None = None, version_id: str | None = None) -> None:
        self.requests: list[dict[str, object]] = []
        self._objects: dict[tuple[str, str], dict[str, str]] = {}
        self._timeout = timeout_after_create
        self._extra = dict(extra or {})
        self._version_id = version_id

    def declare_artifact_version(self, request):
        self.requests.append(dict(request))
        key = (request['producer_operation_ref'], request['content_sha256'])
        existing = key in self._objects
        if not existing:
            n = len(self._objects) + 1
            self._objects[key] = {'artifact_id': f'artifact-{n}', 'artifact_version_id': self._version_id or f'version-{n}'}
            if self._timeout:
                raise TimeoutError('declare timed out after object creation')
        return {
            **self._objects[key],
            'matched_existing': existing,
            'policy_decision': 'matched_existing' if existing else 'new_version',
            **self._extra,
        }


def test_declare_request_uses_hash_size_media_type_policy_and_operation_key() -> None:
    result = {'artifact_id': 'artifact-1', 'artifact_version_id': 'version-1', 'matched_existing': False, 'policy_decision': 'new_version', 'required_operation': 'upload'}
    port = FakeArtifactPort(result)
    assert isinstance(port, ArtifactPort)
    run = running_run()
    sha = hashlib.sha256(BODY).hexdigest()
    key = snapshot_operation_key(run.run_id, sha)
    handoff = handoff_raw_snapshot(make_document(), port=port, policy=POLICY, run=run, operation_key=key)
    assert port.requests == [{
        'artifact_kind': 'raw_snapshot_fixture',
        'owner_resource_ref': RUN_ID,
        'content_sha256': sha,
        'size_bytes': len(BODY),
        'media_type': 'text/html',
        'lineage_refs': [],
        'retention_class': 'retention-fixture-r7',
        'sensitivity_class': 'sensitivity-fixture',
        'intended_storage_class': 'storage-class-fixture',
        'producer_operation_ref': key,
    }]
    assert handoff.status is HandoffStatus.DECLARED
    assert handoff.raw_snapshot_ref == 'version-1'
    assert handoff.matched_existing is False
    assert handoff.run.status is RunStatus.RUNNING
    assert handoff.policy_revision == 'snapshot-policy-fixture-r1'


def test_success_ref_is_attached_to_collected_document_package() -> None:
    port = RecordingArtifactPort()
    handoff = handoff_raw_snapshot(make_document(), port=port, policy=POLICY, run=running_run(), operation_key='op-key-1')
    context = PackageContext(SOURCE_ID, 1, RUN_ID, FETCHED_AT, raw_snapshot_ref=handoff.raw_snapshot_ref)
    package = build_package(make_document(), StdlibHtmlExtractor(), context)
    assert package['raw_snapshot_ref'] == 'version-1'
    assert validate_package_schema(package) == ()


def test_same_operation_key_and_hash_returns_previous_result() -> None:
    port = RecordingArtifactPort()
    run = running_run()
    first = handoff_raw_snapshot(make_document(), port=port, policy=POLICY, run=run, operation_key='op-key-1')
    second = handoff_raw_snapshot(make_document(), port=port, policy=POLICY, run=run, operation_key='op-key-1')
    assert first.matched_existing is False
    assert second.matched_existing is True
    assert (second.artifact_id, second.raw_snapshot_ref) == (first.artifact_id, first.raw_snapshot_ref)
    assert second.content_sha256 == first.content_sha256


def test_operation_key_is_deterministic_per_run_and_hash() -> None:
    sha = hashlib.sha256(BODY).hexdigest()
    other = hashlib.sha256(BODY + b'x').hexdigest()
    assert snapshot_operation_key(RUN_ID, sha) == snapshot_operation_key(RUN_ID, sha)
    assert snapshot_operation_key(RUN_ID, sha) != snapshot_operation_key(RUN_ID, other)
    assert snapshot_operation_key(RUN_ID, sha) != snapshot_operation_key(SOURCE_ID, sha)


def test_a_keeps_no_storage_path() -> None:
    port = RecordingArtifactPort(extra={'storage_path': 'D:/storage/snap.html', 'local_path': 'C:/tmp/snap.html'})
    handoff = handoff_raw_snapshot(make_document(), port=port, policy=POLICY, run=running_run(), operation_key='op-key-1')
    assert not any('path' in field.name for field in dataclasses.fields(handoff))
    assert 'storage_path' not in repr(handoff)
    assert 'D:/storage' not in repr(handoff)
    assert handoff.raw_snapshot_ref == 'version-1'


@pytest.mark.parametrize('bad_ref', ['D:/storage/snap.html', 'C:' + chr(92) + 'tmp' + chr(92) + 'snap.html', '/var/snap.html', 'file:///snap.html'])
def test_path_like_artifact_reference_is_rejected(bad_ref: str) -> None:
    port = RecordingArtifactPort(version_id=bad_ref)
    with pytest.raises(HandoffError, match='STORAGE_PATH_REFERENCE'):
        handoff_raw_snapshot(make_document(), port=port, policy=POLICY, run=running_run(), operation_key='op-key-1')


def test_retention_comes_from_policy_not_from_a() -> None:
    assert all(
        field.default is dataclasses.MISSING and field.default_factory is dataclasses.MISSING
        for field in dataclasses.fields(RawSnapshotPolicy)
    )
    with pytest.raises(TypeError):
        RawSnapshotPolicy()
    with pytest.raises(HandoffError, match='INVALID_RAW_SNAPSHOT_POLICY'):
        RawSnapshotPolicy('r1', 'kind', '  ', 'sensitivity', 'storage-class')
    other = dataclasses.replace(POLICY, retention_class='retention-fixture-r9')
    port = RecordingArtifactPort()
    handoff_raw_snapshot(make_document(), port=port, policy=other, run=running_run(), operation_key='op-key-1')
    assert port.requests[0]['retention_class'] == 'retention-fixture-r9'
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    literals = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert not literals & {'per_video', 'per_article', 'permanent', 'forever', 'local_staging', 'internal'}


def test_timeout_after_object_creation_is_outcome_unknown_and_run_waits() -> None:
    """coveredIds: A-RULE-015 - timeout after the object exists leaves the outcome unknown."""
    port = RecordingArtifactPort(timeout_after_create=True)
    handoff = handoff_raw_snapshot(make_document(), port=port, policy=POLICY, run=running_run(), operation_key='op-key-1')
    assert handoff.status is HandoffStatus.OUTCOME_UNKNOWN
    assert handoff.run.status is RunStatus.WAITING_RECONCILIATION
    assert handoff.run.attempts[-1].outcome is AttemptOutcome.OUTCOME_UNKNOWN
    assert handoff.raw_snapshot_ref is None
    assert len(port.requests) == 1


def test_no_blind_retry_before_reconcile() -> None:
    port = RecordingArtifactPort(timeout_after_create=True)
    first = handoff_raw_snapshot(make_document(), port=port, policy=POLICY, run=running_run(), operation_key='op-key-1')
    with pytest.raises(ReconciliationPendingError, match='RECONCILIATION_PENDING'):
        handoff_raw_snapshot(make_document(), port=port, policy=POLICY, run=first.run, operation_key='op-key-1')
    assert len(port.requests) == 1


def test_retry_after_reconcile_reuses_operation_key_and_matches_existing() -> None:
    port = RecordingArtifactPort(timeout_after_create=True)
    first = handoff_raw_snapshot(make_document(), port=port, policy=POLICY, run=running_run(), operation_key='op-key-1')
    waiting_retry = reconcile(
        first.run, ReconciliationResult.RETRYABLE, evidence_ref='evidence-1',
        source_active=True, deadline_passed=False, checkpoint_ref='cp-1',
    )
    assert waiting_retry.status is RunStatus.WAITING_RETRY
    resumed = resume_retry(waiting_retry, source_active=True, deadline_passed=False, checkpoint_ref='cp-2')
    second = handoff_raw_snapshot(make_document(), port=port, policy=POLICY, run=resumed, operation_key='op-key-1')
    assert second.status is HandoffStatus.DECLARED
    assert second.matched_existing is True
    assert second.raw_snapshot_ref == 'version-1'
    assert [r['producer_operation_ref'] for r in port.requests] == ['op-key-1', 'op-key-1']
    assert len({r['content_sha256'] for r in port.requests}) == 1


def test_non_running_run_is_rejected_without_declaring() -> None:
    port = RecordingArtifactPort()
    with pytest.raises(HandoffError, match='RUN_NOT_RUNNING'):
        handoff_raw_snapshot(make_document(), port=port, policy=POLICY, run=scheduled_run(), operation_key='op-key-1')
    assert port.requests == []


def test_non_timeout_error_propagates_and_run_is_unchanged() -> None:
    class BrokenPort:
        def declare_artifact_version(self, request):
            raise RuntimeError('i unavailable')

    run = running_run()
    with pytest.raises(RuntimeError):
        handoff_raw_snapshot(make_document(), port=BrokenPort(), policy=POLICY, run=run, operation_key='op-key-1')
    assert run.status is RunStatus.RUNNING
    assert run.attempts == ()


@pytest.mark.parametrize('bad', [
    {},
    {'artifact_id': 'a', 'artifact_version_id': 'v', 'matched_existing': 'yes', 'policy_decision': 'new_version'},
    {'artifact_id': 'a', 'artifact_version_id': ' ', 'matched_existing': False, 'policy_decision': 'new_version'},
])
def test_invalid_port_result_is_rejected(bad: dict) -> None:
    class BadPort:
        def declare_artifact_version(self, request):
            return bad

    with pytest.raises(HandoffError, match='INVALID_ARTIFACT_RESULT'):
        handoff_raw_snapshot(make_document(), port=BadPort(), policy=POLICY, run=running_run(), operation_key='op-key-1')


def test_module_imports_only_stdlib_domain_and_ports() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or '')
    allowed = ('source_ingestion.domain', 'source_ingestion.ports')
    outside = {n for n in imported if n.split('.')[0] not in sys.stdlib_module_names and not n.startswith(allowed)}
    assert outside == set()