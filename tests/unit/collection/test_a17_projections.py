"""A-17: read-only Source/Run query projections.

coveredIds: A-RULE-014
"""
import ast
import contextlib
import dataclasses
import inspect
import pathlib
import socket
import unittest
from datetime import UTC, date, datetime, timedelta
from unittest import mock

from source_ingestion.adapters.memory import InMemoryUnitOfWork
from source_ingestion.domain.collection_run import (
    AttemptOutcome,
    CollectionPurpose,
    RetryPolicy,
    RunStatus,
    record_attempt_outcome,
    record_committed_packages,
    schedule_run,
    start_run,
)
from source_ingestion.domain.source import (
    SourcePolicy,
    SourceStatus,
    disable_source,
    register_source,
    remove_source,
    update_source_metadata,
)
from source_ingestion.ports.repositories import PackageRecord
from source_ingestion.projections import source_queries as queries_module
from source_ingestion.projections.source_queries import (
    AttemptView,
    SourceHealth,
    SourceListFilter,
    SourceQueryService,
    redact_headers,
    redact_locator,
)

MODULE_FILE = pathlib.Path(queries_module.__file__).resolve()
T0 = datetime(2026, 10, 19, 6, 0, tzinfo=UTC)
POLICY = SourcePolicy(
    policy_revision='policy-r1',
    source_kinds=frozenset({'rss_feed', 'html_page'}),
    tiers=frozenset({'T1', 'T2'}),
    admin_metadata_keys=frozenset({'owner'}),
)
RETRY = RetryPolicy(revision='retry-r1', max_attempts=3)
OK = AttemptOutcome.SUCCEEDED
FINAL = AttemptOutcome.FAILED_FINAL
RETRYABLE = AttemptOutcome.FAILED_RETRYABLE


def make_source(source_id, *, workspace_id='ws-1', tier='T1', kind='rss_feed', topics=('tech',)):
    return register_source(
        source_id=source_id, workspace_id=workspace_id,
        canonical_locator=f'https://example.test/{workspace_id}/{source_id}',
        name=f'name-{source_id}', source_kind=kind, tier=tier, topics=topics, notes='note',
        collection_enabled=True, admin_metadata={}, actor='user-a', at=T0, policy=POLICY,
    )


def make_run(source_id, run_id, day, outcome=None, *, workspace_id='ws-1',
             purpose=CollectionPurpose.PERIODIC, packages=0):
    run = schedule_run(
        run_id=run_id, workspace_id=workspace_id, source_id=source_id,
        business_date=date(2026, 10, day), purpose=purpose, retry_policy=RETRY,
    )
    if outcome is None:
        return run
    run = start_run(run, source_active=True, checkpoint_ref='cp-1')
    if packages:
        run = record_committed_packages(run, packages)
    return record_attempt_outcome(
        run, outcome, source_active=True, deadline_passed=False, checkpoint_ref='cp-2'
    )


def build_store(sources=(), runs=(), packages=()):
    uow = InMemoryUnitOfWork()
    with uow:
        for source in sources:
            uow.sources.add(source)
        for run in runs:
            uow.runs.add(run)
        for record in packages:
            uow.packages.add(record)
        uow.commit()
    return uow


READ_METHODS = frozenset({'get', 'list_sources', 'list_by_source', 'list_by_run', 'list_revisions'})


class ReadOnly:
    """Proxy that fails on any repository method outside the read allowlist."""

    def __init__(self, inner):
        self._inner = inner
        self.calls = []

    def __getattr__(self, name):
        if name not in READ_METHODS:
            raise AssertionError(f'non-read repository access: {name}')
        self.calls.append(name)
        return getattr(self._inner, name)


class FakeRevisions:
    """Returns every snapshot it holds, whatever the arguments."""

    def __init__(self, snapshots=()):
        self._snapshots = tuple(snapshots)

    def list_revisions(self, workspace_id, source_id):
        return self._snapshots


def make_service(uow, snapshots=()):
    return SourceQueryService(
        ReadOnly(uow.sources), ReadOnly(uow.runs), ReadOnly(uow.packages), FakeRevisions(snapshots)
    )


def ids(items):
    return [item.source_id for item in items]


def dirty_payload(source_id='s-a', run_id='r-1', document_id='doc-1', fetched_at='2026-10-19T06:00:00Z'):
    return {
        'collected_document_id': document_id, 'source_id': source_id, 'source_revision': 1,
        'collection_run_id': run_id,
        'requested_url': 'https://user:pw@example.test/feed?token=SECRET1#frag',
        'final_url': 'https://example.test/final?api_key=SECRET2',
        'fetched_at': fetched_at,
        'http_observation': {
            'status': 200, 'media_type': 'text/html', 'size_bytes': 10,
            'redirect_chain': ['https://example.test/a?sig=SECRET3', 'https://example.test/final?api_key=SECRET2'],
            'safe_headers': [
                ['content-type', 'text/html'], ['Cookie', 'sid=SECRET4'], ['set-cookie', 'sid=SECRET5'],
                ['Authorization', 'Bearer SECRET6'], ['x-api-key', 'SECRET7'],
                ['link', '<https://example.test/n?token=SECRET8>; rel=next'],
            ],
            'fetch_policy_revision': 'fetch-r1', 'request_headers': {'Cookie': 'sid=SECRET9'},
        },
        'extraction_disposition': 'SUCCESS', 'extractor_version': 'ex-1',
        'provenance_chain': [
            {'step': 'redirect_hop', 'url': 'https://example.test/a?sig=SECRET3', 'hop': 0, 'cookie': 'SECRET10'},
            {'step': 'extraction', 'extractor_version': 'ex-1', 'fetch_policy_revision': 'fetch-r1'},
        ],
        'warnings': ['html_parse_error', 'Cookie: sid=SECRET11'],
        'extracted_content_candidate': {'title': 't', 'text': 'body SECRET12'},
        'request_headers': {'Cookie': 'sid=SECRET13'},
    }


def filter_store():
    sources = [
        make_source('s-a', tier='T1', kind='rss_feed', topics=('tech', 'ai')),
        make_source('s-b', tier='T2', kind='html_page', topics=('tech',)),
        disable_source(make_source('s-c', tier='T1', topics=('sport',)), expected_revision=1, actor='user-a', at=T0),
        remove_source(make_source('s-d', tier='T2', topics=('ai',)), expected_revision=1, actor='user-a', at=T0, reason='dup'),
    ]
    runs = [
        make_run('s-a', 'r-a', 1, OK),
        make_run('s-b', 'r-b', 1, FINAL),
        make_run('s-c', 'r-c', 1, FINAL, packages=2),
    ]
    return build_store(sources, runs)


class SourceFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = make_service(filter_store())

    def listed(self, **criteria):
        return ids(self.service.list_sources('ws-1', SourceListFilter(**criteria)))

    def test_no_filter_lists_every_status_sorted_by_source_id(self) -> None:
        self.assertEqual(ids(self.service.list_sources('ws-1')), ['s-a', 's-b', 's-c', 's-d'])

    def test_filter_by_each_field(self) -> None:
        cases = [
            ({'tier': 'T1'}, ['s-a', 's-c']),
            ({'topic': 'ai'}, ['s-a', 's-d']),
            ({'status': SourceStatus.DISABLED}, ['s-c']),
            ({'status': SourceStatus.REMOVED_TOMBSTONE}, ['s-d']),
            ({'source_kind': 'html_page'}, ['s-b']),
            ({'health': SourceHealth.HEALTHY}, ['s-a']),
            ({'health': SourceHealth.FAILING}, ['s-b']),
            ({'health': SourceHealth.DEGRADED}, ['s-c']),
            ({'health': SourceHealth.UNKNOWN}, ['s-d']),
        ]
        for criteria, expected in cases:
            with self.subTest(criteria=criteria):
                self.assertEqual(self.listed(**criteria), expected)

    def test_filters_combine_with_and(self) -> None:
        self.assertEqual(self.listed(tier='T1', topic='tech'), ['s-a'])
        self.assertEqual(self.listed(tier='T2', status=SourceStatus.ACTIVE), ['s-b'])
        self.assertEqual(self.listed(topic='missing'), [])

    def test_summary_fields(self) -> None:
        summary = self.service.list_sources('ws-1')[0]
        self.assertEqual((summary.tier, summary.topics, summary.source_kind), ('T1', ('ai', 'tech'), 'rss_feed'))
        self.assertEqual((summary.health, summary.status, summary.revision), (SourceHealth.HEALTHY, SourceStatus.ACTIVE, 1))
        self.assertIsNotNone(summary.last_collection)
        self.assertEqual(summary.last_collection.run_id, 'r-a')

    def test_detail_has_metadata_and_counters(self) -> None:
        detail = self.service.get_source('ws-1', 's-a')
        self.assertIsNotNone(detail)
        self.assertEqual((detail.notes, detail.policy_revision, detail.created_by), ('note', 'policy-r1', 'user-a'))
        self.assertEqual((detail.counters.run_count, detail.counters.attempt_count), (1, 1))

    def test_invalid_filter_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            SourceListFilter(tier='')
        with self.assertRaises(TypeError):
            SourceListFilter(status='ACTIVE')
        with self.assertRaises(TypeError):
            SourceListFilter(health='HEALTHY')
        with self.assertRaises(TypeError):
            self.service.list_sources('ws-1', {'tier': 'T1'})


class LeakyRuns:
    """Run repository that ignores workspace and source arguments."""

    def __init__(self, runs):
        self._runs = tuple(runs)

    def list_by_source(self, workspace_id, source_id):
        return self._runs

    def get(self, run_id):
        return next((run for run in self._runs if run.run_id == run_id), None)


def two_workspace_store():
    sources = [make_source('s-a'), make_source('s-x', workspace_id='ws-2')]
    runs = [make_run('s-a', 'r-a', 1, OK), make_run('s-x', 'r-x', 1, OK, workspace_id='ws-2')]
    packages = [PackageRecord('s-x', 'https://example.test/ws-2/s-x', 'fp-x', 'r-x', dirty_payload('s-x', 'r-x'))]
    return build_store(sources, runs, packages)


class WorkspaceIsolationTests(unittest.TestCase):
    """Counterexample: a query returns a source or run of another workspace."""

    def setUp(self) -> None:
        self.uow = two_workspace_store()
        self.service = make_service(self.uow)

    def test_list_is_scoped_to_the_workspace(self) -> None:
        self.assertEqual(ids(self.service.list_sources('ws-1')), ['s-a'])
        self.assertEqual(ids(self.service.list_sources('ws-2')), ['s-x'])
        self.assertEqual(self.service.list_sources('ws-3'), ())

    def test_other_workspace_records_are_not_found(self) -> None:
        s = self.service
        self.assertIsNone(s.get_source('ws-1', 's-x'))
        self.assertIsNone(s.get_source('ws-2', 's-a'))
        self.assertIsNone(s.list_source_revisions('ws-1', 's-x'))
        self.assertIsNone(s.list_runs('ws-1', 's-x'))
        self.assertIsNone(s.get_package_trace('ws-1', 's-x', 'r-x'))
        self.assertIsNone(s.get_package_trace('ws-1', 's-a', 'r-x'))
        self.assertIsNotNone(s.get_package_trace('ws-2', 's-x', 'r-x'))

    def test_service_filters_rows_a_leaky_repository_returns(self) -> None:
        foreign = make_run('s-a', 'r-foreign', 2, OK, workspace_id='ws-2')
        other_source = make_run('s-x', 'r-other', 3, OK)
        own = make_run('s-a', 'r-own', 1, OK)
        service = SourceQueryService(
            ReadOnly(self.uow.sources), LeakyRuns([foreign, other_source, own]),
            ReadOnly(self.uow.packages), FakeRevisions(),
        )
        views = service.list_runs('ws-1', 's-a')
        self.assertIsNotNone(views)
        self.assertEqual([view.run_id for view in views], ['r-own'])
        self.assertIsNone(service.get_package_trace('ws-1', 's-a', 'r-foreign'))
        self.assertIsNone(service.get_package_trace('ws-1', 's-a', 'r-other'))

    def test_foreign_revision_snapshots_are_dropped(self) -> None:
        snapshots = [make_source('s-a', workspace_id='ws-2'), make_source('s-x'), make_source('s-a')]
        views = make_service(self.uow, snapshots).list_source_revisions('ws-1', 's-a')
        self.assertIsNotNone(views)
        self.assertEqual(len(views), 1)

    def test_blank_identifiers_are_rejected(self) -> None:
        calls = (
            lambda: self.service.list_sources(''),
            lambda: self.service.get_source('ws-1', ' '),
            lambda: self.service.list_runs('', 's-a'),
            lambda: self.service.get_package_trace('ws-1', 's-a', ''),
        )
        for call in calls:
            with self.subTest(call=call), self.assertRaises(ValueError):
                call()


def history_store():
    runs = [
        make_run('s-a', 'r1', 1, OK, packages=3),
        make_run('s-a', 'r2', 2, RETRYABLE),
        make_run('s-a', 'r3', 3, FINAL, purpose=CollectionPurpose.SOURCE_TEST),
        make_run('s-a', 'r4', 4, FINAL, purpose=CollectionPurpose.SUPPLEMENTAL, packages=2),
        make_run('s-a', 'r5', 5),
    ]
    return build_store([make_source('s-a')], runs)


class RunHistoryHealthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = make_service(history_store())

    def runs(self):
        views = self.service.list_runs('ws-1', 's-a')
        self.assertIsNotNone(views)
        return {view.run_id: view for view in views}

    def test_run_history_is_ordered_by_business_date(self) -> None:
        self.assertEqual(list(self.runs()), ['r1', 'r2', 'r3', 'r4', 'r5'])

    def test_attempts_outcomes_and_terminal_reason(self) -> None:
        runs = self.runs()
        self.assertEqual(runs['r1'].attempts, (AttemptView(1, OK),))
        self.assertEqual((runs['r1'].status, runs['r1'].committed_package_count), (RunStatus.COMPLETED, 3))
        self.assertEqual(runs['r1'].terminal_reason, 'ALL_WORK_DONE')
        self.assertEqual((runs['r2'].status, runs['r2'].terminal_reason), (RunStatus.WAITING_RETRY, None))
        self.assertEqual((runs['r3'].status, runs['r3'].terminal_reason), (RunStatus.FAILED_FINAL, 'FINAL_ERROR'))
        self.assertEqual(runs['r4'].status, RunStatus.COMPLETED_PARTIAL)
        self.assertEqual((runs['r5'].status, runs['r5'].attempts), (RunStatus.SCHEDULED, ()))
        self.assertEqual((runs['r1'].retry_policy_revision, runs['r1'].max_attempts), ('retry-r1', 3))

    def test_counters_and_last_collection_in_detail(self) -> None:
        detail = self.service.get_source('ws-1', 's-a')
        self.assertIsNotNone(detail)
        c = detail.counters
        self.assertEqual((c.run_count, c.attempt_count, c.committed_package_count), (5, 4, 5))
        self.assertEqual(
            (c.completed_count, c.completed_partial_count, c.failed_final_count, c.in_progress_count),
            (1, 1, 1, 2),
        )
        last = detail.summary.last_collection
        self.assertIsNotNone(last)
        self.assertEqual(
            (last.run_id, last.purpose, last.status),
            ('r4', CollectionPurpose.SUPPLEMENTAL, RunStatus.COMPLETED_PARTIAL),
        )
        self.assertEqual(detail.summary.health, SourceHealth.DEGRADED)

    def test_health_follows_latest_terminal_run_not_insertion_order(self) -> None:
        cases = {
            'no_runs': ([], SourceHealth.UNKNOWN),
            'in_progress_only': ([make_run('s-a', 'r1', 1, RETRYABLE)], SourceHealth.UNKNOWN),
            'recovered': ([make_run('s-a', 'r1', 1, FINAL), make_run('s-a', 'r2', 2, OK)], SourceHealth.HEALTHY),
            'failing': ([make_run('s-a', 'r2', 2, FINAL), make_run('s-a', 'r1', 1, OK)], SourceHealth.FAILING),
        }
        for name, (runs, expected) in cases.items():
            with self.subTest(case=name):
                detail = make_service(build_store([make_source('s-a')], runs)).get_source('ws-1', 's-a')
                self.assertIsNotNone(detail)
                self.assertEqual(detail.summary.health, expected)
                if expected is SourceHealth.UNKNOWN:
                    self.assertIsNone(detail.summary.last_collection)

    def test_views_are_immutable(self) -> None:
        detail = self.service.get_source('ws-1', 's-a')
        self.assertIsNotNone(detail)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            detail.summary.tier = 'T2'


class RevisionHistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        v1 = make_source('s-a')
        v2 = update_source_metadata(
            v1, expected_revision=1, actor='user-b', at=T0 + timedelta(hours=1), policy=POLICY,
            tier='T2', topics=('ai',),
        )
        v3 = disable_source(v2, expected_revision=2, actor='user-c', at=T0 + timedelta(hours=2), reason='noisy')
        self.service = make_service(build_store([v3]), [v3, v1, v2])

    def test_history_is_ordered_by_revision(self) -> None:
        views = self.service.list_source_revisions('ws-1', 's-a')
        self.assertIsNotNone(views)
        self.assertEqual([v.revision for v in views], [1, 2, 3])
        self.assertEqual([v.tier for v in views], ['T1', 'T2', 'T2'])
        self.assertEqual([v.topics for v in views], [('tech',), ('ai',), ('ai',)])
        self.assertEqual(
            [v.status for v in views], [SourceStatus.ACTIVE, SourceStatus.ACTIVE, SourceStatus.DISABLED]
        )
        self.assertEqual([v.updated_by for v in views], ['user-a', 'user-b', 'user-c'])
        self.assertEqual(views[2].status_reason, 'noisy')
        self.assertEqual(views[1].updated_at, T0 + timedelta(hours=1))

    def test_unknown_source_has_no_history(self) -> None:
        self.assertIsNone(self.service.list_source_revisions('ws-1', 's-none'))

    def test_detail_shows_current_revision(self) -> None:
        detail = self.service.get_source('ws-1', 's-a')
        self.assertIsNotNone(detail)
        self.assertEqual(
            (detail.summary.revision, detail.summary.status, detail.summary.tier),
            (3, SourceStatus.DISABLED, 'T2'),
        )
        self.assertEqual((detail.created_by, detail.updated_by), ('user-a', 'user-c'))


def trace_store(extra_packages=()):
    packages = [PackageRecord('s-a', 'https://example.test/ws-1/s-a', 'fp-1', 'r-1', dirty_payload()), *extra_packages]
    sources = [make_source('s-a'), make_source('s-b')]
    return build_store(sources, [make_run('s-a', 'r-1', 1, OK, packages=1)], packages)


class TraceRedactionTests(unittest.TestCase):
    """Counterexample: a trace carries Cookie, credentials or URL secrets."""

    def trace(self, extra=()):
        trace = make_service(trace_store(extra)).get_package_trace('ws-1', 's-a', 'r-1')
        self.assertIsNotNone(trace)
        return trace

    def test_trace_has_no_secret_or_sensitive_header(self) -> None:
        text = repr(self.trace()).lower()
        for needle in ('secret', 'cookie', 'authorization', 'x-api-key', 'pw@', 'bearer', 'frag', 'body'):
            with self.subTest(needle=needle):
                self.assertNotIn(needle, text)

    def test_urls_lose_userinfo_query_and_fragment(self) -> None:
        package = self.trace().packages[0]
        self.assertEqual(package.requested_url, 'https://example.test/feed')
        self.assertEqual(package.final_url, 'https://example.test/final')
        self.assertEqual(package.redirect_chain, ('https://example.test/a', 'https://example.test/final'))
        self.assertEqual((package.provenance[0].url, package.provenance[0].hop), ('https://example.test/a', 0))

    def test_safe_headers_keep_only_non_sensitive_values(self) -> None:
        package = self.trace().packages[0]
        self.assertEqual(
            package.safe_headers,
            (('content-type', 'text/html'), ('link', '<https://example.test/n>; rel=next')),
        )

    def test_trace_exposes_allowlisted_fields_only(self) -> None:
        package = self.trace().packages[0]
        self.assertEqual((package.http_status, package.media_type, package.size_bytes), (200, 'text/html', 10))
        self.assertEqual(
            (package.extraction_disposition, package.extractor_version, package.fetch_policy_revision),
            ('SUCCESS', 'ex-1', 'fetch-r1'),
        )
        self.assertEqual(package.warnings, ('html_parse_error', '[redacted]'))
        names = {field.name for field in dataclasses.fields(package)}
        self.assertFalse({'extracted_content_candidate', 'request_headers', 'text'} & names)

    def test_only_packages_of_the_run_and_source_are_traced(self) -> None:
        other_source = PackageRecord('s-b', 'https://example.test/ws-1/s-b', 'fp-b', 'r-1', dirty_payload('s-b', 'r-1', 'doc-b'))
        other_run = PackageRecord('s-a', 'https://example.test/ws-1/s-a', 'fp-2', 'r-2', dirty_payload('s-a', 'r-2', 'doc-2'))
        trace = self.trace([other_source, other_run])
        self.assertEqual([p.collected_document_id for p in trace.packages], ['doc-1'])

    def test_packages_are_ordered_by_fetch_time(self) -> None:
        later = PackageRecord(
            's-a', 'https://example.test/ws-1/s-a', 'fp-3', 'r-1',
            dirty_payload(document_id='doc-0', fetched_at='2026-10-19T07:00:00Z'),
        )
        trace = self.trace([later])
        self.assertEqual([p.collected_document_id for p in trace.packages], ['doc-1', 'doc-0'])

    def test_sparse_payload_does_not_raise(self) -> None:
        sparse = PackageRecord('s-a', 'https://example.test/ws-1/s-a', 'fp-4', 'r-1', {})
        package = self.trace([sparse]).packages[0]
        self.assertIsNone(package.collected_document_id)
        self.assertEqual((package.redirect_chain, package.safe_headers, package.provenance, package.warnings), ((), (), (), ()))

    def test_run_without_packages_has_empty_trace(self) -> None:
        service = make_service(build_store([make_source('s-a')], [make_run('s-a', 'r-1', 1, OK)]))
        trace = service.get_package_trace('ws-1', 's-a', 'r-1')
        self.assertIsNotNone(trace)
        self.assertEqual((trace.run_id, trace.source_id, trace.packages), ('r-1', 's-a', ()))


class RedactHelperTests(unittest.TestCase):
    def test_redact_locator(self) -> None:
        self.assertEqual(redact_locator('https://h.test:8080/p?q=1#f'), 'https://h.test:8080/p')
        self.assertEqual(redact_locator('https://u:p@h.test/p'), 'https://h.test/p')
        for value in (None, 7, 'not a url', ''):
            with self.subTest(value=value):
                self.assertEqual(redact_locator(value), '[redacted]')

    def test_redact_headers(self) -> None:
        self.assertEqual(redact_headers('x'), ())
        headers = [['Content-Type', 'a'], ['Cookie', 'b'], ('x',), ['y', 3], 'zz', ('ETag', 'e')]
        self.assertEqual(redact_headers(headers), (('content-type', 'a'), ('etag', 'e')))


class CountingAdapter:
    """Fake SourceAdapter; any call would be a fetch side effect a query must never cause."""

    def __init__(self):
        self.calls = 0

    def probe(self, *args, **kwargs):
        self.calls += 1

    def list_candidates(self, *args, **kwargs):
        self.calls += 1

    def fetch_document(self, *args, **kwargs):
        self.calls += 1

    def extract_candidate(self, *args, **kwargs):
        self.calls += 1

    def resume_from_checkpoint(self, *args, **kwargs):
        self.calls += 1

    def supplemental_search(self, *args, **kwargs):
        self.calls += 1


PUBLIC_QUERIES = ('get_package_trace', 'get_source', 'list_runs', 'list_source_revisions', 'list_sources')
FORBIDDEN_MODULES = (
    'source_ingestion.adapters', 'source_ingestion.ports.source_adapter', 'socket', 'http',
    'urllib.request', 'urllib3', 'requests', 'httpx', 'subprocess', 'asyncio',
)
FORBIDDEN_CALLS = frozenset({
    'fetch', 'fetch_document', 'probe', 'list_candidates', 'extract_candidate', 'urlopen',
    'create_connection', 'getaddrinfo',
})


def blocked_network():
    return [
        mock.patch.object(socket, name, side_effect=AssertionError(f'network access: {name}'))
        for name in ('getaddrinfo', 'create_connection', 'gethostbyname', 'gethostbyname_ex')
    ]


def snapshot(uow):
    return tuple(dict(table._rows) for table in uow._tables)


class NoFetchReadOnlyTests(unittest.TestCase):
    """Counterexample: a query triggers a fetch or mutates state."""

    def test_every_public_query_runs_without_adapter_network_or_writes(self) -> None:
        adapter = CountingAdapter()
        uow = two_workspace_store()
        before = snapshot(uow)
        proxies = [ReadOnly(uow.sources), ReadOnly(uow.runs), ReadOnly(uow.packages)]
        service = SourceQueryService(*proxies, FakeRevisions([make_source('s-a')]))
        with contextlib.ExitStack() as stack:
            for patcher in blocked_network():
                stack.enter_context(patcher)
            service.list_sources('ws-1')
            service.list_sources('ws-1', SourceListFilter(health=SourceHealth.UNKNOWN))
            service.get_source('ws-1', 's-a')
            service.list_source_revisions('ws-1', 's-a')
            service.list_runs('ws-1', 's-a')
            self.assertIsNotNone(service.get_package_trace('ws-2', 's-x', 'r-x'))
        used = {name for proxy in proxies for name in proxy.calls}
        self.assertTrue(used)
        self.assertLessEqual(used, READ_METHODS)
        self.assertEqual(adapter.calls, 0)
        self.assertEqual(snapshot(uow), before)

    def test_read_only_guard_rejects_writes(self) -> None:
        guard = ReadOnly(two_workspace_store().sources)
        with self.assertRaises(AssertionError):
            guard.add(make_source('s-new'))

    def test_constructor_takes_no_adapter_or_transport(self) -> None:
        params = list(inspect.signature(SourceQueryService.__init__).parameters)
        self.assertEqual(params, ['self', 'sources', 'runs', 'packages', 'revisions'])
        public = sorted(n for n, v in vars(SourceQueryService).items() if not n.startswith('_') and callable(v))
        self.assertEqual(public, list(PUBLIC_QUERIES))

    def test_module_imports_no_adapter_or_network_code(self) -> None:
        tree = ast.parse(MODULE_FILE.read_text(encoding='utf-8'))
        imported = []
        called = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported += [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or '')
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                called.add(node.func.attr)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                called.add(node.func.id)
        bad = [name for name in imported if any(name == p or name.startswith(p + '.') for p in FORBIDDEN_MODULES)]
        self.assertEqual(bad, [])
        self.assertEqual(sorted(called & FORBIDDEN_CALLS), [])
