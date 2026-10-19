"""A-11: CollectSource collects one source and isolates failures between sources (CT-SRC-005).

coveredIds: A-RULE-004, A-RULE-008, A-RULE-012
"""
from __future__ import annotations

import ast
import datetime
import pathlib
import socket

import pytest

from source_ingestion.adapters.memory import InMemoryUnitOfWork
from source_ingestion.adapters.secure_fetch import fetch_problem
from source_ingestion.adapters.stdlib_html_extractor import StdlibHtmlExtractor
from source_ingestion.application import collect_source as cs
from source_ingestion.application.collect_source import CollectSourceRequest, SourceCollectionJob
from source_ingestion.domain.checkpoint import CheckpointCompleteness
from source_ingestion.domain.collection_run import RetryPolicy, RunStatus, TerminalReason
from source_ingestion.domain.package import ExtractionPolicy
from source_ingestion.domain.source import SourcePolicy, register_source
from source_ingestion.ports.source_adapter import (
    AdapterOperation,
    CandidateListing,
    CapabilityUnavailable,
    FetchedDocument,
    FetchObservation,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'source_ingestion' / 'application' / 'collect_source.py'
WORKSPACE = 'ws-1'
DAY_1 = datetime.date(2026, 10, 18)
DAY_2 = datetime.date(2026, 10, 19)
NOW = datetime.datetime(2026, 10, 18, 8, 0, 0, tzinfo=datetime.timezone.utc)
NETWORK_FUNCTIONS = ('getaddrinfo', 'create_connection', 'gethostbyname', 'gethostbyname_ex')
SECRET = 'hunter2-SECRET'
SOURCE_POLICY = SourcePolicy(
    policy_revision='policy-r1',
    source_kinds=frozenset({'rss_feed'}),
    tiers=frozenset({'tier-1'}),
    admin_metadata_keys=frozenset(),
)
# Test-only policy fixtures; not approved production policies.
EXTRACTION = ExtractionPolicy(revision='extraction-policy-fixture-r1', title_required_by_source_kind={'rss_feed': False})
RETRY = RetryPolicy(revision='retry-r1', max_attempts=3)


class Crash(BaseException):
    """Simulated process crash: not an Exception, so the collector must not swallow it."""


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _network_forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError('real DNS/network call in integration test')

    for name in NETWORK_FUNCTIONS:
        monkeypatch.setattr(socket, name, _network_forbidden)


def locator_of(n: int) -> str:
    return f'https://news.example.test/a/{n}'


def html_of(n: int) -> str:
    return (
        f'<html lang="vi"><head><title>Bài {n}</title></head>'
        f'<body><article><p>Nội dung bài số {n}.</p></article></body></html>'
    )


def document(locator: str, html: str) -> FetchedDocument:
    body = html.encode('utf-8')
    observation = FetchObservation(
        locator, locator, (locator,), 200, 'text/html', len(body),
        (('content-type', 'text/html; charset=utf-8'),), 'fetch-policy-r1',
    )
    return FetchedDocument(observation, body)


class FakeAdapter:
    """Fixture adapter: in-memory listing and documents, never opens a socket.

    `behaviors` maps a locator to a ProblemDetail/CapabilityUnavailable to return or to a
    BaseException instance to raise from fetch_document; `listing_result` replaces the listing.
    """

    def __init__(self, locators, *, listing_cursor='cursor-1', complete=True, listing_result=None, behaviors=None):
        self.locators = tuple(locators)
        self.listing_cursor = listing_cursor
        self.complete = complete
        self.listing_result = listing_result
        self.behaviors = dict(behaviors or {})
        self.cursors_seen = []
        self.fetch_calls = []

    def list_candidates(self, locator, cursor):
        self.cursors_seen.append(cursor)
        if isinstance(self.listing_result, BaseException):
            raise self.listing_result
        if self.listing_result is not None:
            return self.listing_result
        return CandidateListing(self.locators, self.listing_cursor, self.complete)

    def fetch_document(self, locator):
        self.fetch_calls.append(locator)
        behavior = self.behaviors.get(locator)
        if isinstance(behavior, BaseException):
            raise behavior
        if behavior is not None:
            return behavior
        return document(locator, html_of(int(locator.rsplit('/', 1)[1])))


def make_source(unit, source_id='src-1', *, enabled=True) -> None:
    source = register_source(
        source_id=source_id, workspace_id=WORKSPACE,
        canonical_locator=f'https://news.example.test/feed/{source_id}',
        name=f'Nguồn {source_id}', source_kind='rss_feed', tier='tier-1', topics=['kinh-te'], notes='',
        collection_enabled=enabled, admin_metadata={}, actor='tester', at=NOW, policy=SOURCE_POLICY,
    )
    with unit:
        unit.sources.add(source)
        unit.commit()


def make_job(adapter, source_id='src-1', run_id='run-1', business_date=DAY_1) -> SourceCollectionJob:
    request = CollectSourceRequest(
        workspace_id=WORKSPACE, source_id=source_id, business_date=business_date, run_id=run_id,
        retry_policy=RETRY, adapter_revision='adapter-r1', extraction_policy=EXTRACTION,
    )
    return SourceCollectionJob(request, adapter, StdlibHtmlExtractor())


def clock() -> datetime.datetime:
    return NOW


def run_once(unit, job):
    return cs.collect_source(unit, job, clock=clock)


def events(unit, name):
    return [record for record in unit.outbox.records() if record.event_type == name]


@pytest.fixture
def uow() -> InMemoryUnitOfWork:
    unit = InMemoryUnitOfWork()
    make_source(unit)
    return unit


def test_new_periodic_run_commits_each_item_in_its_own_uow(uow):
    adapter = FakeAdapter([locator_of(1), locator_of(2)])
    result = run_once(uow, make_job(adapter))
    assert result.status is RunStatus.COMPLETED
    assert (result.urls_seen, result.fetched, result.skipped, result.failed, result.packages_committed) == (2, 2, 0, 0, 2)
    assert result.replayed is False
    assert result.errors == ()
    run = uow.runs.get('run-1')
    assert run.status is RunStatus.COMPLETED
    assert run.committed_package_count == 2
    records = uow.packages.list_by_run('run-1')
    assert len(records) == 2
    assert result.package_refs == tuple(record.payload['collected_document_id'] for record in records)
    for record in records:
        assert record.payload['http_observation']['status'] == 200
        assert record.payload['collection_run_id'] == 'run-1'
    available = events(uow, 'CollectedDocumentAvailable')
    assert len(available) == 2
    assert {event.payload['collected_document_id'] for event in available} == set(result.package_refs)
    assert len(events(uow, 'CollectionRunStarted')) == 1
    assert len(events(uow, 'CollectionRunCompleted')) == 1
    checkpoint = uow.checkpoints.get_latest('src-1')
    assert checkpoint.revision == 3
    assert checkpoint.cursor == 'cursor-1'
    assert checkpoint.completeness is CheckpointCompleteness.COMPLETE
    assert result.cursor == 'cursor-1'
    assert adapter.cursors_seen == [None]


def test_rerun_same_business_date_reuses_run_and_emits_nothing(uow):
    first = run_once(uow, make_job(FakeAdapter([locator_of(1), locator_of(2)])))
    before = len(uow.outbox.records())
    adapter = FakeAdapter([locator_of(1), locator_of(2)])
    second = run_once(uow, make_job(adapter, run_id='run-other'))
    assert second.run_id == first.run_id == 'run-1'
    assert second.replayed is True
    assert second.status is RunStatus.COMPLETED
    assert second.package_refs == first.package_refs
    assert adapter.cursors_seen == []
    assert adapter.fetch_calls == []
    assert len(uow.outbox.records()) == before
    assert [run.run_id for run in uow.runs.list_by_source(WORKSPACE, 'src-1')] == ['run-1']
    assert len(uow.packages.list_by_run('run-1')) == 2


def test_crashed_run_resumes_without_replaying_committed_packages(uow):
    crashing = FakeAdapter([locator_of(1), locator_of(2)], behaviors={locator_of(2): Crash()})
    with pytest.raises(Crash):
        run_once(uow, make_job(crashing))
    assert not uow.active
    assert uow.runs.get('run-1').status is RunStatus.RUNNING
    assert uow.runs.get('run-1').committed_package_count == 1
    assert len(events(uow, 'CollectedDocumentAvailable')) == 1
    result = run_once(uow, make_job(FakeAdapter([locator_of(1), locator_of(2)]), run_id='run-2'))
    assert result.run_id == 'run-1'
    assert result.status is RunStatus.COMPLETED
    assert result.replayed is False
    assert (result.skipped, result.packages_committed) == (1, 1)
    assert len(result.package_refs) == 2
    assert len(events(uow, 'CollectedDocumentAvailable')) == 2
    assert len(events(uow, 'CollectionRunStarted')) == 1
    assert uow.runs.get('run-1').committed_package_count == 2
    assert len(uow.runs.list_by_source(WORKSPACE, 'src-1')) == 1


def test_item_failure_is_a_warning_and_run_is_partial(uow):
    bad = locator_of(2)
    adapter = FakeAdapter(
        [locator_of(1), bad, locator_of(3)],
        behaviors={bad: fetch_problem('UPSTREAM_ERROR', 'corr-1', status=503)},
    )
    result = run_once(uow, make_job(adapter))
    assert result.status is RunStatus.COMPLETED_PARTIAL
    assert (result.urls_seen, result.fetched, result.failed, result.packages_committed) == (3, 2, 1, 2)
    assert [(error.locator, error.code) for error in result.errors] == [(bad, 'UPSTREAM_ERROR')]
    run = uow.runs.get('run-1')
    assert run.status is RunStatus.COMPLETED_PARTIAL
    assert run.warnings == (f'UPSTREAM_ERROR:{bad}',)
    assert result.cursor is None
    checkpoint = uow.checkpoints.get_latest('src-1')
    assert checkpoint.cursor == cs.START_CURSOR
    assert len(checkpoint.item_ids) == 1
    assert len(events(uow, 'CollectionRunCompleted')) == 1
    assert events(uow, 'CollectionRunFailed') == []


def test_next_day_run_skips_committed_items_and_advances_cursor(uow):
    bad = locator_of(2)
    problem = fetch_problem('UPSTREAM_ERROR', 'corr-1', status=503)
    run_once(uow, make_job(FakeAdapter([locator_of(1), bad, locator_of(3)], behaviors={bad: problem})))
    before = len(events(uow, 'CollectedDocumentAvailable'))
    adapter = FakeAdapter([locator_of(1), bad, locator_of(3)])
    result = run_once(uow, make_job(adapter, run_id='run-2', business_date=DAY_2))
    assert result.run_id == 'run-2'
    assert result.status is RunStatus.COMPLETED
    assert (result.skipped, result.packages_committed, result.failed) == (2, 1, 0)
    assert adapter.cursors_seen == [None]
    assert result.cursor == 'cursor-1'
    assert len(events(uow, 'CollectedDocumentAvailable')) == before + 1
    assert sorted(run.run_id for run in uow.runs.list_by_source(WORKSPACE, 'src-1')) == ['run-1', 'run-2']


def test_run_without_any_committed_package_fails_final(uow):
    first, second = locator_of(1), locator_of(2)
    unsupported = CapabilityUnavailable(AdapterOperation.FETCH_DOCUMENT, 'fake', '1', 'fetch not supported')
    adapter = FakeAdapter(
        [first, second],
        behaviors={first: fetch_problem('HTTP_STATUS_REJECTED', 'corr-2', status=404), second: unsupported},
    )
    result = run_once(uow, make_job(adapter))
    assert result.status is RunStatus.FAILED_FINAL
    assert (result.packages_committed, result.failed) == (0, 2)
    assert [error.code for error in result.errors] == ['HTTP_STATUS_REJECTED', 'CAPABILITY_UNAVAILABLE']
    assert uow.packages.list_by_run('run-1') == ()
    assert events(uow, 'CollectedDocumentAvailable') == []
    assert len(events(uow, 'CollectionRunFailed')) == 1
    assert events(uow, 'CollectionRunCompleted') == []
    assert uow.checkpoints.get_latest('src-1') is None


def test_package_failing_layer_one_is_not_handed_off(uow, monkeypatch):
    real_build = cs.build_package

    def broken_build(document, extractor, context, **kwargs):
        package = real_build(document, extractor, context, **kwargs)
        if document.observation.requested_locator == locator_of(2):
            del package['source_id']
        return package

    monkeypatch.setattr(cs, 'build_package', broken_build)
    result = run_once(uow, make_job(FakeAdapter([locator_of(1), locator_of(2), locator_of(3)])))
    assert result.status is RunStatus.COMPLETED_PARTIAL
    assert result.failed == 1
    assert [error.code for error in result.errors] == ['VALIDATION_ERROR']
    records = uow.packages.list_by_run('run-1')
    assert [record.canonical_locator for record in records] == [locator_of(1), locator_of(3)]
    available = events(uow, 'CollectedDocumentAvailable')
    assert len(available) == 2
    assert {event.payload['collected_document_id'] for event in available} == set(result.package_refs)


def test_failed_item_unit_of_work_rolls_back_only_that_item(uow, monkeypatch):
    original = uow.outbox.append_event

    def fail_second(event_type, aggregate_id, payload, deduplication_id):
        if event_type == 'CollectedDocumentAvailable' and str(payload['canonical_locator']).endswith('/2'):
            raise RuntimeError(f'outbox down password={SECRET}')
        return original(event_type, aggregate_id, payload, deduplication_id)

    monkeypatch.setattr(uow.outbox, 'append_event', fail_second)
    result = run_once(uow, make_job(FakeAdapter([locator_of(1), locator_of(2), locator_of(3)])))
    assert result.status is RunStatus.COMPLETED_PARTIAL
    assert (result.failed, result.packages_committed) == (1, 2)
    assert [error.code for error in result.errors] == ['ITEM_COMMIT_FAILED']
    assert SECRET not in repr(result)
    records = uow.packages.list_by_run('run-1')
    assert [record.canonical_locator for record in records] == [locator_of(1), locator_of(3)]
    assert uow.runs.get('run-1').committed_package_count == 2
    assert len(events(uow, 'CollectedDocumentAvailable')) == 2
    checkpoint = uow.checkpoints.get_latest('src-1')
    assert checkpoint.revision == 2
    assert checkpoint.item_ids == (f'{locator_of(3)}|{records[1].observation_fingerprint}',)


def test_one_source_raising_does_not_stop_other_sources(uow):
    make_source(uow, 'src-2')
    make_source(uow, 'src-3')
    order = []

    class Recording(FakeAdapter):
        def __init__(self, name, locators, **kwargs):
            super().__init__(locators, **kwargs)
            self.name = name

        def list_candidates(self, locator, cursor):
            order.append(self.name)
            return super().list_candidates(locator, cursor)

    boom = RuntimeError(
        f'connect failed token={SECRET} Bearer abc.def.ghi https://news.example.test/feed?api_key={SECRET}'
    )
    jobs = [
        make_job(Recording('a', [locator_of(1)]), 'src-1', 'run-a'),
        make_job(Recording('b', [], listing_result=boom), 'src-2', 'run-b'),
        make_job(Recording('c', [locator_of(3)]), 'src-3', 'run-c'),
    ]
    results = cs.collect_sources(uow, jobs, clock=clock)
    assert order == ['a', 'b', 'c']
    assert [result.status for result in results] == [RunStatus.COMPLETED, RunStatus.FAILED_FINAL, RunStatus.COMPLETED]
    assert [result.packages_committed for result in results] == [1, 0, 1]
    assert [error.code for error in results[1].errors] == ['ADAPTER_EXCEPTION']
    assert uow.runs.get('run-b').status is RunStatus.FAILED_FINAL
    assert len(events(uow, 'CollectionRunFailed')) == 1
    dump = repr(results) + repr(uow.runs.get('run-b')) + repr(uow.outbox.records())
    assert SECRET not in dump
    assert 'abc.def.ghi' not in dump
    assert 'api_key' not in dump


def test_exception_escaping_a_source_is_contained_by_collect_sources(uow, monkeypatch):
    make_source(uow, 'src-2')
    original = cs.collect_source

    def flaky(unit, job, *, clock):
        if job.request.source_id == 'src-1':
            raise RuntimeError(f'database password={SECRET} lost')
        return original(unit, job, clock=clock)

    monkeypatch.setattr(cs, 'collect_source', flaky)
    jobs = [
        make_job(FakeAdapter([locator_of(1)]), 'src-1', 'run-a'),
        make_job(FakeAdapter([locator_of(2)]), 'src-2', 'run-b'),
    ]
    results = cs.collect_sources(uow, jobs, clock=clock)
    assert results[0].status is RunStatus.FAILED_FINAL
    assert [error.code for error in results[0].errors] == ['COLLECTION_ABORTED']
    assert SECRET not in repr(results[0])
    assert results[1].status is RunStatus.COMPLETED


def test_retryable_listing_problem_waits_then_same_run_resumes(uow):
    flaky = FakeAdapter([locator_of(1)], listing_result=fetch_problem('UPSTREAM_ERROR', 'corr-1', status=503))
    first = run_once(uow, make_job(flaky))
    assert first.status is RunStatus.WAITING_RETRY
    assert [error.code for error in first.errors] == ['UPSTREAM_ERROR']
    assert events(uow, 'CollectionRunCompleted') == []
    assert events(uow, 'CollectionRunFailed') == []
    second = run_once(uow, make_job(FakeAdapter([locator_of(1)]), run_id='run-2'))
    assert second.run_id == 'run-1'
    assert second.status is RunStatus.COMPLETED
    assert second.packages_committed == 1
    assert len(uow.runs.get('run-1').attempts) == 2


def test_unsupported_listing_capability_fails_final_without_retry(uow):
    unsupported = CapabilityUnavailable(AdapterOperation.LIST_CANDIDATES, 'fake', '1', 'listing not supported')
    result = run_once(uow, make_job(FakeAdapter([], listing_result=unsupported)))
    assert result.status is RunStatus.FAILED_FINAL
    assert [error.code for error in result.errors] == ['CAPABILITY_UNAVAILABLE']
    assert result.packages_committed == 0
    assert len(events(uow, 'CollectionRunFailed')) == 1


def test_inactive_source_fails_final_without_fetching():
    unit = InMemoryUnitOfWork()
    make_source(unit, enabled=False)
    adapter = FakeAdapter([locator_of(1)])
    result = run_once(unit, make_job(adapter))
    assert result.status is RunStatus.FAILED_FINAL
    assert adapter.cursors_seen == []
    assert adapter.fetch_calls == []
    assert unit.runs.get('run-1').terminal_decision.reason is TerminalReason.SOURCE_INACTIVE
    assert [error.code for error in result.errors] == ['SOURCE_INACTIVE']


def test_unknown_source_returns_failure_without_creating_a_run():
    unit = InMemoryUnitOfWork()
    result = run_once(unit, make_job(FakeAdapter([])))
    assert result.status is RunStatus.FAILED_FINAL
    assert [error.code for error in result.errors] == ['SOURCE_NOT_FOUND']
    assert unit.runs.list_by_source(WORKSPACE, 'src-1') == ()


def test_item_errors_are_redacted(uow):
    leaky = locator_of(2) + f'?token={SECRET}'
    adapter = FakeAdapter(
        [locator_of(1), leaky],
        behaviors={leaky: RuntimeError(f'proxy rejected Bearer {SECRET} password: {SECRET}')},
    )
    result = run_once(uow, make_job(adapter))
    assert result.status is RunStatus.COMPLETED_PARTIAL
    assert [error.code for error in result.errors] == ['ADAPTER_EXCEPTION']
    assert result.errors[0].locator == locator_of(2)
    assert SECRET not in repr(result) + repr(uow.runs.get('run-1').warnings)


def test_request_rejects_invalid_values():
    base = dict(
        workspace_id=WORKSPACE, source_id='src-1', business_date=DAY_1, run_id='run-1',
        retry_policy=RETRY, adapter_revision='adapter-r1',
    )
    CollectSourceRequest(**base)
    for override in (
        {'workspace_id': ''}, {'source_id': ' '}, {'run_id': ''}, {'adapter_revision': ''},
        {'business_date': NOW}, {'business_date': '2026-10-18'}, {'retry_policy': None},
        {'checkpoint_version': 0}, {'execution_generation': -1}, {'extraction_policy': 'x'},
    ):
        with pytest.raises(ValueError):
            CollectSourceRequest(**{**base, **override})


def test_network_is_blocked_for_the_whole_suite():
    for name in NETWORK_FUNCTIONS:
        with pytest.raises(AssertionError):
            getattr(socket, name)('example.test', 80)


def test_module_imports_only_stdlib_domain_ports_and_application():
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    stdlib = {'__future__', 'dataclasses', 'datetime', 're', 'collections.abc', 'typing', 'urllib.parse'}
    allowed = ('source_ingestion.domain', 'source_ingestion.ports', 'source_ingestion.application', 'controlplane.domain')
    assert sorted(name for name in imported if name not in stdlib and not name.startswith(allowed)) == []
