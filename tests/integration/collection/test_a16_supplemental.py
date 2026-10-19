"""A-16: SUPPLEMENTAL collection per video keeps tombstone, periodic count and budget rules (CT-SRC-005).

coveredIds: A-RULE-002, A-RULE-005
"""
from __future__ import annotations

import ast
import datetime
import pathlib
import socket

import pytest
from controlplane.domain.orchestration import ExecutionGrant

from source_ingestion.adapters.memory import FakeActivityGrantPort, InMemoryUnitOfWork
from source_ingestion.adapters.secure_fetch import fetch_problem
from source_ingestion.adapters.stdlib_html_extractor import StdlibHtmlExtractor
from source_ingestion.application import collect_source as cs
from source_ingestion.application.collect_source import CollectSourceRequest, SourceCollectionJob
from source_ingestion.application.supplemental import (
    SupplementalBudget,
    SupplementalJob,
    SupplementalOutcome,
    SupplementalRequest,
    collect_supplemental,
)
from source_ingestion.domain.collection_run import (
    AttemptOutcome,
    CollectionPurpose,
    RetryPolicy,
    RunStatus,
    TerminalReason,
)
from source_ingestion.domain.package import ExtractionPolicy
from source_ingestion.domain.source import SourcePolicy, SourceStatus, register_source, remove_source
from source_ingestion.ports.source_adapter import (
    AdapterOperation,
    CandidateListing,
    CapabilityUnavailable,
    FetchedDocument,
    FetchObservation,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'source_ingestion' / 'application' / 'supplemental.py'
WORKSPACE = 'ws-1'
NOW = datetime.datetime(2026, 10, 18, 8, 0, 0, tzinfo=datetime.timezone.utc)
DEADLINE = NOW + datetime.timedelta(minutes=5)
NETWORK_FUNCTIONS = ('getaddrinfo', 'create_connection', 'gethostbyname', 'gethostbyname_ex')
SOURCE_POLICY = SourcePolicy(
    policy_revision='policy-r1',
    source_kinds=frozenset({'rss_feed'}),
    tiers=frozenset({'tier-1'}),
    admin_metadata_keys=frozenset(),
)
# Test-only policy fixtures; not approved production policies.
EXTRACTION = ExtractionPolicy(revision='extraction-policy-fixture-r1', title_required_by_source_kind={'rss_feed': False})
RETRY = RetryPolicy(revision='retry-r1', max_attempts=3)
GRANT = ExecutionGrant(WORKSPACE, 'op-1', 'job-1', 'stage-1', 1, 1)
INTENT = {'query': 'bridge at night', 'scene': 'scene-3'}


def locator_of(n: int) -> str:
    return f'https://news.example.test/a/{n}'


def html_of(n: int) -> str:
    return (
        f'<html lang="vi"><head><title>Bài {n}</title></head>'
        f'<body><article><p>Nội dung bài số {n}.</p>'
        f'<img src="https://cdn.example.test/img/{n}.jpg" alt="Ảnh {n}"></article></body></html>'
    )


def document(locator: str, html: str) -> FetchedDocument:
    body = html.encode('utf-8')
    observation = FetchObservation(
        locator, locator, (locator,), 200, 'text/html', len(body),
        (('content-type', 'text/html; charset=utf-8'),), 'fetch-policy-r1',
    )
    return FetchedDocument(observation, body)


class Clock:
    def __init__(self, now: datetime.datetime) -> None:
        self.now = now

    def __call__(self) -> datetime.datetime:
        return self.now


class FakeAdapter:
    """Fixture adapter: supplemental_search, periodic listing and documents in memory, never opens a socket."""

    def __init__(self, locators=(), *, search_result=None, behaviors=None, on_fetch=None):
        self.locators = tuple(locators)
        self.search_result = search_result
        self.behaviors = dict(behaviors or {})
        self.on_fetch = on_fetch
        self.search_calls = []
        self.fetch_calls = []

    def list_candidates(self, locator, cursor):
        return CandidateListing(self.locators, 'cursor-1', True)

    def supplemental_search(self, intent):
        self.search_calls.append(dict(intent))
        if self.search_result is not None:
            return self.search_result
        return CandidateListing(self.locators)

    def fetch_document(self, locator):
        self.fetch_calls.append(locator)
        if self.on_fetch is not None:
            self.on_fetch(len(self.fetch_calls))
        behavior = self.behaviors.get(locator)
        if behavior is not None:
            return behavior
        return document(locator, html_of(int(locator.rsplit('/', 1)[1])))


class EchoContentPort:
    """Fake of B (CT-CNT-001): echoes the document id with a fixed disposition, or raises `error`."""

    def __init__(self, disposition='NEW_ARTICLE', error=None):
        self.disposition = disposition
        self.error = error
        self.submitted = []

    def resolve_collected_document(self, package):
        self.submitted.append(dict(package))
        if self.error is not None:
            raise self.error
        return {
            'collected_document_id': package['collected_document_id'],
            'dedup_policy_revision': 'dedup-fixture-r1',
            'disposition': self.disposition,
        }


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _network_forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError('real DNS/network call in integration test')

    for name in NETWORK_FUNCTIONS:
        monkeypatch.setattr(socket, name, _network_forbidden)


@pytest.fixture
def uow() -> InMemoryUnitOfWork:
    unit = InMemoryUnitOfWork()
    make_source(unit)
    return unit


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


def tombstone(unit, source_id) -> None:
    source = unit.sources.get(WORKSPACE, source_id)
    removed = remove_source(source, expected_revision=source.revision, actor='tester', at=NOW, reason='user removed')
    with unit:
        unit.sources.save(removed)
        unit.commit()


def make_job(
    adapter, *, run_id='sup-1', source_id='src-1', job_id='job-1', max_fetches=5, deadline=DEADLINE,
    grant=GRANT, intent=INTENT,
) -> SupplementalJob:
    request = SupplementalRequest(
        workspace_id=WORKSPACE, source_id=source_id, run_id=run_id, job_id=job_id, scene_ref='scene-3',
        intent_ref='intent-1', intent=intent, budget=SupplementalBudget('budget-1', max_fetches, deadline),
        grant=grant, retry_policy=RETRY, extraction_policy=EXTRACTION,
    )
    return SupplementalJob(request, adapter, StdlibHtmlExtractor())


def run_sup(unit, job, *, port=None, grants=None, clock=None):
    return collect_supplemental(
        unit, job,
        grants=grants if grants is not None else FakeActivityGrantPort([GRANT]),
        content_port=port if port is not None else EchoContentPort(),
        clock=clock if clock is not None else (lambda: NOW),
    )


def periodic_job(adapter) -> SourceCollectionJob:
    request = CollectSourceRequest(
        workspace_id=WORKSPACE, source_id='src-1', business_date=NOW.date(), run_id='periodic-1',
        retry_policy=RETRY, adapter_revision='adapter-r1', extraction_policy=EXTRACTION,
    )
    return SourceCollectionJob(request, adapter, StdlibHtmlExtractor())


def events(unit, name):
    return [record for record in unit.outbox.records() if record.event_type == name]


def test_valid_request_collects_packages_and_media_with_provenance(uow):
    adapter = FakeAdapter([locator_of(1), locator_of(2)])
    result = run_sup(uow, make_job(adapter))
    assert result.outcome is SupplementalOutcome.FOUND
    assert result.reason is None
    assert result.status is RunStatus.COMPLETED
    assert (result.job_id, result.scene_ref, result.intent_ref, result.budget_ref) == (
        'job-1', 'scene-3', 'intent-1', 'budget-1')
    assert adapter.search_calls == [INTENT]
    assert adapter.fetch_calls == [locator_of(1), locator_of(2)]
    run = uow.runs.get('sup-1')
    assert run.purpose is CollectionPurpose.SUPPLEMENTAL
    assert run.committed_package_count == 2
    assert len(result.package_refs) == 2
    assert len(result.discoveries) == 2
    for discovery in result.discoveries:
        assert discovery.new_package is True
        assert discovery.package_ref in result.package_refs
        provenance = discovery.discovery['provenance']
        assert provenance['collection_run_id'] == 'sup-1'
        assert provenance['collected_document_id'] == discovery.package_ref
        assert provenance['source_id'] == 'src-1'
    assert {d.discovery['locator'] for d in result.discoveries} == {
        'https://cdn.example.test/img/1.jpg', 'https://cdn.example.test/img/2.jpg'}


def test_supplemental_never_creates_or_counts_a_periodic_run(uow):
    periodic = cs.collect_source(uow, periodic_job(FakeAdapter([locator_of(1)])), clock=lambda: NOW)
    assert periodic.status is RunStatus.COMPLETED
    periodic_run = uow.runs.get_periodic(WORKSPACE, 'src-1', NOW.date())
    checkpoint = uow.checkpoints.get_latest('src-1')
    started = len(events(uow, 'CollectionRunStarted'))
    completed = len(events(uow, 'CollectionRunCompleted'))
    result = run_sup(uow, make_job(FakeAdapter([locator_of(10)])))
    assert result.outcome is SupplementalOutcome.FOUND
    assert uow.runs.get_periodic(WORKSPACE, 'src-1', NOW.date()) == periodic_run
    purposes = sorted(run.purpose.value for run in uow.runs.list_by_source(WORKSPACE, 'src-1'))
    assert purposes == ['PERIODIC', 'SUPPLEMENTAL']
    assert uow.checkpoints.get_latest('src-1') == checkpoint
    assert len(events(uow, 'CollectionRunStarted')) == started
    assert len(events(uow, 'CollectionRunCompleted')) == completed
    assert uow.runs.get('periodic-1').committed_package_count == 1


def test_supplemental_alone_leaves_no_periodic_run_and_no_checkpoint(uow):
    run_sup(uow, make_job(FakeAdapter([locator_of(1)])))
    assert uow.runs.get_periodic(WORKSPACE, 'src-1', NOW.date()) is None
    assert [run.purpose for run in uow.runs.list_by_source(WORKSPACE, 'src-1')] == [CollectionPurpose.SUPPLEMENTAL]
    assert uow.checkpoints.get_latest('src-1') is None


def test_tombstoned_source_is_blocked_before_any_search_or_fetch(uow):
    tombstone(uow, 'src-1')
    adapter = FakeAdapter([locator_of(1)])
    result = run_sup(uow, make_job(adapter))
    assert result.outcome is SupplementalOutcome.BLOCKED
    assert result.reason == 'SOURCE_TOMBSTONED'
    assert [error.code for error in result.errors] == ['SOURCE_TOMBSTONED']
    assert result.run_id is None and result.status is None
    assert adapter.search_calls == [] and adapter.fetch_calls == []
    assert uow.runs.list_by_source(WORKSPACE, 'src-1') == ()
    assert uow.packages.list_by_run('sup-1') == ()
    assert uow.sources.get(WORKSPACE, 'src-1').status is SourceStatus.REMOVED_TOMBSTONE


def test_disabled_or_unknown_source_is_blocked(uow):
    make_source(uow, 'src-3', enabled=False)
    disabled = run_sup(uow, make_job(FakeAdapter([locator_of(1)]), source_id='src-3'))
    unknown = run_sup(uow, make_job(FakeAdapter([locator_of(1)]), source_id='src-404'))
    assert (disabled.outcome, disabled.reason) == (SupplementalOutcome.BLOCKED, 'SOURCE_INACTIVE')
    assert (unknown.outcome, unknown.reason) == (SupplementalOutcome.BLOCKED, 'SOURCE_NOT_FOUND')
    assert uow.runs.list_by_source(WORKSPACE, 'src-3') == ()


def test_source_tombstoned_during_run_stops_before_the_next_fetch(uow):
    adapter = FakeAdapter(
        [locator_of(1), locator_of(2)],
        on_fetch=lambda count: tombstone(uow, 'src-1') if count == 1 else None,
    )
    result = run_sup(uow, make_job(adapter))
    assert adapter.fetch_calls == [locator_of(1)]
    assert result.outcome is SupplementalOutcome.PARTIAL
    assert result.reason == 'SOURCE_TOMBSTONED'
    assert result.blocked == 1
    assert result.packages_committed == 1
    run = uow.runs.get('sup-1')
    assert run.status is RunStatus.COMPLETED_PARTIAL
    assert run.terminal_decision.reason is TerminalReason.SOURCE_INACTIVE


def test_discovered_locator_of_a_tombstoned_source_is_never_fetched(uow):
    make_source(uow, 'src-2')
    tombstone(uow, 'src-2')
    removed_locator = 'https://news.example.test/feed/src-2'
    adapter = FakeAdapter([removed_locator, locator_of(1)])
    result = run_sup(uow, make_job(adapter))
    assert adapter.fetch_calls == [locator_of(1)]
    assert result.outcome is SupplementalOutcome.FOUND
    assert result.blocked == 1
    assert [(error.code, error.locator) for error in result.errors] == [('SOURCE_TOMBSTONED', removed_locator)]
    after = uow.sources.get(WORKSPACE, 'src-2')
    assert after.status is SourceStatus.REMOVED_TOMBSTONE
    assert after.revision == 2
    assert len(uow.sources.list_sources(WORKSPACE)) == 2


def test_budget_exhausted_returns_partial_with_structured_reason(uow):
    adapter = FakeAdapter([locator_of(1), locator_of(2), locator_of(3)])
    result = run_sup(uow, make_job(adapter, max_fetches=2))
    assert adapter.fetch_calls == [locator_of(1), locator_of(2)]
    assert result.outcome is SupplementalOutcome.PARTIAL
    assert result.reason == 'BUDGET_EXHAUSTED'
    assert result.status is RunStatus.COMPLETED_PARTIAL
    assert result.urls_seen == 2 and result.packages_committed == 2
    assert uow.runs.get('sup-1').terminal_decision.reason is TerminalReason.RETRY_EXHAUSTED


def test_budget_exhausted_without_any_package_is_not_found_never_success(uow):
    unsupported = CapabilityUnavailable(AdapterOperation.FETCH_DOCUMENT, 'fake', '1', 'fetch not supported')
    locators = [locator_of(1), locator_of(2), locator_of(3)]
    adapter = FakeAdapter(locators, behaviors={locator: unsupported for locator in locators})
    result = run_sup(uow, make_job(adapter, max_fetches=2))
    assert len(adapter.fetch_calls) == 2
    assert result.outcome is SupplementalOutcome.NOT_FOUND
    assert result.outcome is not SupplementalOutcome.FOUND
    assert result.reason == 'BUDGET_EXHAUSTED'
    assert result.status is RunStatus.FAILED_FINAL
    assert result.package_refs == () and result.discoveries == ()
    assert [error.code for error in result.errors] == ['CAPABILITY_UNAVAILABLE', 'CAPABILITY_UNAVAILABLE']


def test_deadline_passed_before_search_is_not_found_without_any_call(uow):
    adapter = FakeAdapter([locator_of(1)])
    result = run_sup(uow, make_job(adapter, deadline=NOW), clock=Clock(NOW))
    assert result.outcome is SupplementalOutcome.NOT_FOUND
    assert result.reason == 'DEADLINE_EXCEEDED'
    assert result.status is RunStatus.FAILED_FINAL
    assert adapter.search_calls == [] and adapter.fetch_calls == []
    assert uow.runs.get('sup-1').purpose is CollectionPurpose.SUPPLEMENTAL


def test_deadline_reached_mid_run_returns_partial(uow):
    clock = Clock(NOW)
    adapter = FakeAdapter([locator_of(1), locator_of(2)], on_fetch=lambda count: setattr(clock, 'now', DEADLINE))
    result = run_sup(uow, make_job(adapter), clock=clock)
    assert adapter.fetch_calls == [locator_of(1)]
    assert result.outcome is SupplementalOutcome.PARTIAL
    assert result.reason == 'DEADLINE_EXCEEDED'
    assert result.status is RunStatus.COMPLETED_PARTIAL


def test_empty_search_result_is_not_found_with_reason(uow):
    result = run_sup(uow, make_job(FakeAdapter([])))
    assert result.outcome is SupplementalOutcome.NOT_FOUND
    assert result.reason == 'NO_CANDIDATES'
    assert result.status is RunStatus.COMPLETED
    assert result.package_refs == ()


def test_unsupported_search_capability_is_a_structured_failure(uow):
    unsupported = CapabilityUnavailable(AdapterOperation.SUPPLEMENTAL_SEARCH, 'fake', '1', 'search not supported')
    adapter = FakeAdapter([locator_of(1)], search_result=unsupported)
    result = run_sup(uow, make_job(adapter))
    assert result.outcome is SupplementalOutcome.FAILED
    assert result.reason == 'CAPABILITY_UNAVAILABLE'
    assert result.status is RunStatus.FAILED_FINAL
    assert [error.code for error in result.errors] == ['CAPABILITY_UNAVAILABLE']
    assert adapter.fetch_calls == []


def test_stale_or_foreign_grant_is_blocked_without_a_run(uow):
    adapter = FakeAdapter([locator_of(1)])
    stale = run_sup(uow, make_job(adapter), grants=FakeActivityGrantPort([]))
    other_job = ExecutionGrant(WORKSPACE, 'op-1', 'job-2', 'stage-1', 1, 1)
    foreign = run_sup(uow, make_job(adapter, grant=other_job), grants=FakeActivityGrantPort([other_job]))
    other_ws = ExecutionGrant('ws-2', 'op-1', 'job-1', 'stage-1', 1, 1)
    wrong_ws = run_sup(uow, make_job(adapter, grant=other_ws), grants=FakeActivityGrantPort([other_ws]))
    assert (stale.outcome, stale.reason) == (SupplementalOutcome.BLOCKED, 'GRANT_NOT_CURRENT')
    assert foreign.reason == 'GRANT_SCOPE_MISMATCH' and wrong_ws.reason == 'GRANT_SCOPE_MISMATCH'
    assert adapter.search_calls == []
    assert uow.runs.list_by_source(WORKSPACE, 'src-1') == ()


def test_new_packages_go_to_b_and_events_carry_supplemental_refs(uow):
    port = EchoContentPort()
    result = run_sup(uow, make_job(FakeAdapter([locator_of(1), locator_of(2)])), port=port)
    assert [p['collected_document_id'] for p in port.submitted] == list(result.package_refs)
    assert [r['disposition'] for r in result.resolutions] == ['NEW_ARTICLE', 'NEW_ARTICLE']
    available = events(uow, 'CollectedDocumentAvailable')
    assert len(available) == 2
    for event in available:
        assert event.payload['purpose'] == 'SUPPLEMENTAL'
        assert event.payload['collection_run_id'] == 'sup-1'
        assert (event.payload['job_id'], event.payload['scene_ref']) == ('job-1', 'scene-3')
    assert {record.event_type for record in uow.outbox.records()} == {'CollectedDocumentAvailable'}


def test_duplicate_article_is_skipped_but_keeps_media_provenance(uow):
    port = EchoContentPort()
    first = run_sup(uow, make_job(FakeAdapter([locator_of(1)])), port=port)
    second = run_sup(uow, make_job(FakeAdapter([locator_of(1)]), run_id='sup-2'), port=port)
    assert second.outcome is SupplementalOutcome.NOT_FOUND
    assert second.reason == 'NO_NEW_PACKAGES'
    assert second.skipped == 1 and second.packages_committed == 0 and second.package_refs == ()
    assert len(port.submitted) == 1
    assert [d.package_ref for d in second.discoveries] == list(first.package_refs)
    assert all(d.new_package is False for d in second.discoveries)
    assert second.discoveries[0].discovery['provenance']['collection_run_id'] == 'sup-1'


def test_handoff_b_failure_keeps_the_committed_package(uow):
    port = EchoContentPort(error=RuntimeError('B unavailable'))
    result = run_sup(uow, make_job(FakeAdapter([locator_of(1)])), port=port)
    assert [error.code for error in result.errors] == ['HANDOFF_B_FAILED']
    assert result.outcome is SupplementalOutcome.PARTIAL
    assert result.status is RunStatus.COMPLETED_PARTIAL
    assert len(result.package_refs) == 1 and result.resolutions == ()


def test_handoff_b_contract_violation_is_reported(uow):
    port = EchoContentPort(disposition='MAYBE')
    result = run_sup(uow, make_job(FakeAdapter([locator_of(1)])), port=port)
    assert [error.code for error in result.errors] == ['HANDOFF_B_CONTRACT_VIOLATION']
    assert result.resolutions == ()
    assert len(result.package_refs) == 1


def test_same_run_id_replays_stored_result_without_new_calls(uow):
    adapter = FakeAdapter([locator_of(1), locator_of(2), locator_of(3)])
    first = run_sup(uow, make_job(adapter, max_fetches=2))
    before = (len(adapter.search_calls), len(adapter.fetch_calls), len(uow.outbox.records()))
    second = run_sup(uow, make_job(adapter, max_fetches=2))
    assert first.replayed is False and second.replayed is True
    assert (second.outcome, second.reason, second.status) == (first.outcome, first.reason, first.status)
    assert second.package_refs == first.package_refs
    assert len(second.discoveries) == len(first.discoveries)
    assert before == (len(adapter.search_calls), len(adapter.fetch_calls), len(uow.outbox.records()))
    assert len(uow.runs.list_by_source(WORKSPACE, 'src-1')) == 1


def test_run_id_of_another_purpose_is_rejected(uow):
    cs.collect_source(uow, periodic_job(FakeAdapter([locator_of(1)])), clock=lambda: NOW)
    adapter = FakeAdapter([locator_of(2)])
    result = run_sup(uow, make_job(adapter, run_id='periodic-1'))
    assert (result.outcome, result.reason) == (SupplementalOutcome.BLOCKED, 'RUN_ID_CONFLICT')
    assert adapter.search_calls == []
    assert uow.runs.get('periodic-1').purpose is CollectionPurpose.PERIODIC


def test_retryable_search_problem_waits_then_resumes_the_same_supplemental_run(uow):
    flaky = FakeAdapter([locator_of(1)], search_result=fetch_problem('UPSTREAM_ERROR', 'corr-1', status=503))
    first = run_sup(uow, make_job(flaky))
    assert first.outcome is SupplementalOutcome.FAILED
    assert first.status is RunStatus.WAITING_RETRY
    assert first.reason == 'UPSTREAM_ERROR'
    flaky.search_result = None
    second = run_sup(uow, make_job(flaky))
    assert second.replayed is False and second.run_id == 'sup-1'
    assert second.status is RunStatus.COMPLETED and second.outcome is SupplementalOutcome.FOUND
    assert second.packages_committed == 1
    run = uow.runs.get('sup-1')
    assert [a.outcome for a in run.attempts] == [AttemptOutcome.FAILED_RETRYABLE, AttemptOutcome.SUCCEEDED]
    assert len(uow.runs.list_by_source(WORKSPACE, 'src-1')) == 1
    assert uow.runs.get_periodic(WORKSPACE, 'src-1', NOW.date()) is None


def test_resume_after_deadline_closes_the_run_as_not_found(uow):
    flaky = FakeAdapter([locator_of(1)], search_result=fetch_problem('UPSTREAM_ERROR', 'corr-1', status=503))
    run_sup(uow, make_job(flaky))
    late = run_sup(uow, make_job(flaky), clock=Clock(DEADLINE))
    assert late.outcome is SupplementalOutcome.NOT_FOUND
    assert late.reason == 'DEADLINE_EXCEEDED'
    assert late.status is RunStatus.FAILED_FINAL
    assert late.replayed is False
    assert len(flaky.search_calls) == 1


def test_request_validation_rejects_bad_budget_and_intent():
    for bad in (
        lambda: SupplementalBudget(' ', 1, DEADLINE),
        lambda: SupplementalBudget('b', 0, DEADLINE),
        lambda: SupplementalBudget('b', True, DEADLINE),
        lambda: SupplementalBudget('b', 1, DEADLINE.replace(tzinfo=None)),
        lambda: make_job(FakeAdapter([]), intent={}),
        lambda: make_job(FakeAdapter([]), intent={'query': ' '}),
    ):
        with pytest.raises(ValueError):
            bad()


def imported_names():
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    modules, names = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
            names.update(alias.name for alias in node.names)
    return modules, names


def test_module_imports_only_stdlib_domain_ports_and_application():
    modules, _ = imported_names()
    stdlib = {'__future__', 'dataclasses', 'datetime', 'enum', 'collections.abc'}
    allowed = ('source_ingestion.domain', 'source_ingestion.ports', 'source_ingestion.application', 'controlplane.domain')
    assert sorted(name for name in modules if name not in stdlib and not name.startswith(allowed)) == []


def test_handoff_c_is_not_wired_and_waits_for_ct_med_001():
    modules, names = imported_names()
    assert not any(name == 'catalog' or name.startswith('catalog.') for name in modules)
    assert 'ArtifactPort' not in names and 'ConfigPort' not in names
    assert 'CT-MED-001' in MODULE_PATH.read_text(encoding='utf-8')
