"""PW-A2: CollectSource và ResolveCollectedDocument với deps dựng theo từng lời gọi, trên PostgreSQL thật và nguồn feed loopback (không ra mạng ngoài).

coveredIds: PW-A2-01, CT-SRC-004, CT-SRC-005, CT-CNT-001
"""
from __future__ import annotations

import ast
import asyncio
import dataclasses
import http.server
import ipaddress
import pathlib
import threading
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

import pytest
from temporalio.exceptions import ApplicationError

from controlplane.api.wiring.workflow import build_temporal_registration, build_workflow_services, collect_source_handler
from controlplane.application.orchestration.workflows.activities import (
    INVALID_ACTIVITY_REQUEST,
    MISSING_EXECUTION_GRANT,
    ActivityRejected,
)
from controlplane.domain.orchestration.activity_binding import validate_activity_result
from controlplane.domain.orchestration.fencing import GrantClaims
from controlplane.infrastructure.db.uow import TransactionManager
from ingestion.application.production_deps import (
    DEFAULT_DEDUP_POLICY,
    PostgresSourceTierLookup,
    ResolveDepsFactory,
    resolve_activity_handler,
)
from ingestion.persistence.uow import PostgresIngestionUnitOfWork
from source_ingestion.adapters.real_http_transport import RealHttpTransport
from source_ingestion.adapters.secure_fetch import FetchPolicy, SecureFetcher
from source_ingestion.application.source_commands import SourceCommandHandler
from source_ingestion.domain.collection_run import RunStatus
from source_ingestion.domain.source import SourcePolicy
from source_ingestion.persistence.unit_of_work import PostgresSourceIngestionUnitOfWork
from source_ingestion.ports.source_adapter import CapabilityUnavailable
from source_ingestion.worker.activity_handler import ActivityRequestError as CollectRequestError
from source_ingestion.worker.production_deps import CollectDepsFactory, collect_source_activity_handler

ROOT = pathlib.Path(__file__).resolve().parents[3]
PUBLIC = '93.184.216.34'
LOOPBACK = ipaddress.ip_address('127.0.0.1')
HOST = 'news.example'
DAY1 = '2026-10-27'
DAY2 = '2026-10-28'
NOW = datetime(2026, 10, 27, 3, 0, tzinfo=timezone.utc)
POLICY = SourcePolicy(
    policy_revision='pw-a2',
    source_kinds=frozenset({'rss_feed', 'atom_feed'}),
    tiers=frozenset({'tier_1', 'tier_2', 'tier_3'}),
    admin_metadata_keys=frozenset(),
)
PARAGRAPHS = (
    'The harbour workers reached a comprehensive agreement following intensive negotiations that lasted throughout the previous evening and continued well into early Tuesday morning across the entire maritime terminal facility.',
    'Port operations resumed immediately as container traffic began moving steadily through the primary freight corridors, allowing long queues of waiting transport trucks to finally discharge their cargo safely.',
    'Union representatives praised the commitment of all participating delegates while management reiterated their collective dedication to establishing sustainable labor practices for every shift going forward.',
    'Economic analysts noted that the swift resolution prevented major supply chain bottlenecks from compounding ahead of the upcoming seasonal retail surge across international distribution hubs.',
)
EXTRA = 'A second round of talks scheduled for Friday will settle the remaining questions about overtime pay and safety inspections at the northern terminal.'

def article_html(title: str, extra: str = '') -> bytes:
    paragraphs = ''.join(f'<p>{text}</p>' for text in (*PARAGRAPHS, *((extra,) if extra else ())))
    return (
        f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><title>{title}</title></head>"
        f"<body><nav><a href='/'>Home</a></nav><article><h1>{title}</h1>{paragraphs}</article>"
        '<footer><p>Copyright 2026 News Example</p></footer></body></html>'
    ).encode('utf-8')


def rss(base: str, slug: str, title: str) -> bytes:
    return (
        "<?xml version='1.0' encoding='utf-8'?><rss version='2.0'><channel>"
        f'<title>Feed {slug}</title><link>{base}/feeds/{slug}.xml</link><description>Feed {slug}</description><language>en</language>'
        f'<item><title>{title}</title><link>{base}/articles/{slug}</link>'
        '<pubDate>Tue, 27 Oct 2026 02:00:00 GMT</pubDate>'
        f"<enclosure url='{base}/img/{slug}.jpg' type='image/jpeg' length='1000'/></item>"
        '</channel></rss>'
    ).encode('utf-8')


class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args: Any) -> None:
        pass

    def do_GET(self) -> None:
        path = self.path.split('?')[0]
        self.server.seen.append(path)
        location = self.server.redirects.get(path)
        status, content_type, body = (302, 'text/plain', b'') if location else self.server.routes.get(path, (404, 'text/plain', b'not found'))
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        if location:
            self.send_header('Location', location)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class Site(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self) -> None:
        super().__init__(('127.0.0.1', 0), _Handler)
        self.routes: dict[str, tuple[int, str, bytes]] = {}
        self.redirects: dict[str, str] = {}
        self.seen: list[str] = []

    @property
    def base(self) -> str:
        return f'http://{HOST}:{self.server_address[1]}'

    def serve_feed(self, slug: str, title: str, html: bytes) -> None:
        self.routes[f'/feeds/{slug}.xml'] = (200, 'application/rss+xml; charset=utf-8', rss(self.base, slug, title))
        self.routes[f'/articles/{slug}'] = (200, 'text/html; charset=utf-8', html)


@pytest.fixture
def site():
    server = Site()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(5)


@pytest.fixture
def manager(pw_database):
    pool = TransactionManager(pw_database.dsn, pool_max_size=4)
    try:
        yield pool
    finally:
        pool.close()


class LoopbackTransport:
    def __init__(self) -> None:
        self.inner = RealHttpTransport()

    def send(self, request: Any) -> Any:
        return self.inner.send(dataclasses.replace(request, addresses=(LOOPBACK,)))


class Grants:
    """ClaimsCurrencyPort: grant còn hiệu lực trừ khi stale=True; ghi lại grant_id đã hỏi."""

    def __init__(self, stale: bool = False) -> None:
        self.stale = stale
        self.calls: list[str] = []

    def is_grant_current(self, grant: GrantClaims) -> bool:
        self.calls.append(grant.grant_id)
        return not self.stale

def fetch_policy(types: set[str]) -> FetchPolicy:
    return FetchPolicy('pw-a2', 3, 200000, frozenset(types), 10.0)


FEED_POLICY = fetch_policy({'application/rss+xml', 'application/atom+xml'})
ARTICLE_POLICY = fetch_policy({'text/html'})


def claims(number: int = 1) -> GrantClaims:
    return GrantClaims(
        grant_id=f'grant-{number}',
        stage_run_id=f'stage-{number}',
        execution_generation=1,
        recovery_epoch='1',
        worker_lease_id='lease-1',
        issued_at='2026-10-27T03:00:00Z',
        expires_at='2026-10-27T04:00:00Z',
        allowed_operation='CollectSource',
        input_fingerprint='fp-1',
    )


def request(name: str, claim: GrantClaims, refs: list[dict[str, str]], key: str) -> dict[str, Any]:
    return {
        'workflow_id': 'wf-1',
        'workflow_run_id': 'run-1',
        'stage_run_id': claim.stage_run_id,
        'activity_name': name,
        'activity_version': '1',
        'input_refs': refs,
        'operation_key': key,
        'capability_requirements': {},
        'retry_policy_ref': 'retry-1',
        'execution_grant': asdict(claim),
    }


def collect(handler: Any, source_id: str, day: str, key: str, number: int = 1) -> dict[str, Any]:
    claim = claims(number)
    refs = [{'ref_type': 'collection_source', 'ref_id': source_id}, {'ref_type': 'business_date', 'ref_id': day}]
    return handler(request('CollectSource', claim, refs, key), claim)


def resolve(handler: Any, document_id: str, key: str, number: int = 1) -> dict[str, Any]:
    claim = claims(number)
    refs = [{'ref_type': 'collected_document', 'ref_id': document_id}]
    return handler(request('ResolveCollectedDocument', claim, refs, key), claim)


def document_ids(result: dict[str, Any]) -> list[str]:
    return [ref['ref_id'] for ref in result['output_refs'] if ref['ref_type'] == 'collected_document']


def scalar(db: Any, sql: str, params: tuple = ()) -> Any:
    with db.connect() as conn:
        return conn.execute(sql, params).fetchone()[0]


def count(db: Any, table: str) -> int:
    return scalar(db, 'SELECT count(*) FROM controlplane.' + table)


def package_payload(db: Any) -> dict[str, Any]:
    return scalar(db, 'SELECT payload FROM controlplane.cp_collected_document_packages ORDER BY created_at LIMIT 1')


def register(manager: Any, db: Any, locator: str, name: str, tier: str = 'tier_1', kind: str = 'rss_feed') -> str:
    handler = SourceCommandHandler(
        uow=PostgresSourceIngestionUnitOfWork(manager, workspace_id=db.workspace_id),
        policy_provider=lambda workspace_id: POLICY,
        resolver=lambda host: [PUBLIC],
        recovery_epoch='pw-a2',
    )
    outcome = handler.register_source(
        workspace_id=db.workspace_id,
        actor='pw-a2',
        correlation_id='pw-a2',
        idempotency_key='pw-a2:' + name,
        locator=locator,
        name=name,
        source_kind=kind,
        tier=tier,
        topics=['news'],
    )
    return outcome.receipt.aggregate_ref


def collect_factory(manager: Any, db: Any, factory_cls: type = CollectDepsFactory, grants: Any = None) -> CollectDepsFactory:
    return factory_cls(
        uow_factory=lambda: PostgresSourceIngestionUnitOfWork(manager, workspace_id=db.workspace_id),
        grants=grants if grants is not None else Grants(),
        workspace_id=db.workspace_id,
        fetcher=SecureFetcher(LoopbackTransport(), lambda host: [PUBLIC]),
        feed_policy=FEED_POLICY,
        article_policy=ARTICLE_POLICY,
    )


def resolve_factory(manager: Any, db: Any, **overrides: Any) -> ResolveDepsFactory:
    return ResolveDepsFactory(
        uow_factory=lambda: PostgresIngestionUnitOfWork(manager, workspace_id=db.workspace_id),
        connection_factory=manager.borrow_connection,
        workspace_id=db.workspace_id,
        **overrides,
    )

def test_collect_source_writes_a_collected_document_with_its_image(manager, pw_database, site):
    site.serve_feed('a', 'Port strike ends', article_html('Port strike ends'))
    source_id = register(manager, pw_database, site.base + '/feeds/a.xml', 'feed-a')
    handler = collect_source_activity_handler(collect_factory(manager, pw_database), lambda: NOW)
    result = collect(handler, source_id, DAY1, 'op-a-1')
    assert validate_activity_result(result) == []
    assert result['disposition'] == 'succeeded'
    assert result['metrics']['packages_committed'] == 1
    ids = document_ids(result)
    assert len(ids) == 1 and count(pw_database, 'cp_collected_document_packages') == 1
    package = package_payload(pw_database)
    assert (package['collected_document_id'], package['source_id']) == (ids[0], source_id)
    assert package['extraction_disposition'] == 'SUCCESS' and package['content_eligibility'] == 'candidate'
    assert 'harbour workers' in package['extracted_content_candidate']['text']
    media = {(item['role'], item['locator']) for item in package['media_discoveries']}
    assert ('enclosure', site.base + '/img/a.jpg') in media
    assert scalar(pw_database, 'SELECT status FROM controlplane.cp_collection_runs') == RunStatus.COMPLETED.value


def test_a_404_source_does_not_stop_the_next_source(manager, pw_database, site):
    site.serve_feed('good', 'Good news', article_html('Good news'))
    gone = register(manager, pw_database, site.base + '/feeds/gone.xml', 'feed-gone')
    good = register(manager, pw_database, site.base + '/feeds/good.xml', 'feed-good')
    handler = collect_source_activity_handler(collect_factory(manager, pw_database), lambda: NOW)
    failed = collect(handler, gone, DAY1, 'op-gone')
    assert validate_activity_result(failed) == []
    assert failed['disposition'] == 'failed'
    assert failed['problem']['code'] == 'HTTP_STATUS_REJECTED' and failed['problem']['retryable'] is False
    assert document_ids(failed) == []
    ok = collect(handler, good, DAY1, 'op-good', 2)
    assert ok['disposition'] == 'succeeded' and len(document_ids(ok)) == 1
    assert '/feeds/gone.xml' in site.seen and '/articles/good' in site.seen
    assert count(pw_database, 'cp_collected_document_packages') == 1


def test_deps_are_built_per_call_and_the_adapter_is_chosen_per_source(manager, pw_database):
    first_id = register(manager, pw_database, 'http://news.example/feeds/one.xml', 'feed-one')
    second_id = register(manager, pw_database, 'http://news.example/feeds/two.xml', 'feed-two')
    atom_id = register(manager, pw_database, 'http://news.example/feeds/three.xml', 'feed-three', kind='atom_feed')
    factory = collect_factory(manager, pw_database)
    one, two = factory.deps_for_call(), factory.deps_for_call()
    assert one is not two and one.uow is not two.uow and one.extractor is not two.extractor
    assert one.results is two.results
    adapter_one, adapter_two, adapter_atom = (one.adapter_for(item) for item in (first_id, second_id, atom_id))
    assert adapter_one.adapter is not adapter_two.adapter
    assert adapter_one.descriptor.adapter_id == adapter_two.descriptor.adapter_id == 'real-rss-feed'
    assert adapter_atom.descriptor.adapter_id == 'real-atom-feed'
    unknown = one.adapter_for('missing-source')
    assert isinstance(unknown.list_candidates('http://news.example/feeds/x.xml', None), CapabilityUnavailable)
    assert one.retry_policy.max_attempts == 3 and one.adapter_revision
    assert one.extraction_policy.title_required_by_source_kind['rss_feed'] is True

def test_same_business_date_reuses_the_periodic_run_and_the_next_day_starts_a_new_one(manager, pw_database, site):
    site.serve_feed('a', 'Port strike ends', article_html('Port strike ends'))
    source_id = register(manager, pw_database, site.base + '/feeds/a.xml', 'feed-a')
    made: list[Any] = []

    class Counting(CollectDepsFactory):
        def deps_for_call(self):
            deps = super().deps_for_call()
            made.append(deps)
            return deps

    handler = collect_source_activity_handler(collect_factory(manager, pw_database, factory_cls=Counting), lambda: NOW)
    first = collect(handler, source_id, DAY1, 'op-1')
    fetched = len(site.seen)
    again = collect(handler, source_id, DAY1, 'op-2', 2)
    assert again['disposition'] == 'succeeded' and again['metrics']['replayed'] is True
    assert document_ids(again) == document_ids(first) and len(site.seen) == fetched
    assert count(pw_database, 'cp_collection_runs') == 1
    next_day = collect(handler, source_id, DAY2, 'op-3', 3)
    assert next_day['disposition'] == 'succeeded'
    assert next_day['metrics']['skipped'] == 1 and next_day['metrics']['packages_committed'] == 0
    assert count(pw_database, 'cp_collection_runs') == 2 and count(pw_database, 'cp_collected_document_packages') == 1
    assert len(made) == 3 and len({id(item) for item in made}) == 3 and len({id(item.uow) for item in made}) == 3


def test_feed_image_survives_an_article_redirect(manager, pw_database, site):
    site.serve_feed('r', 'Moved story', article_html('Moved story'))
    site.routes['/articles/moved'] = site.routes.pop('/articles/r')
    site.redirects['/articles/r'] = '/articles/moved'
    source_id = register(manager, pw_database, site.base + '/feeds/r.xml', 'feed-r')
    handler = collect_source_activity_handler(collect_factory(manager, pw_database), lambda: NOW)
    result = collect(handler, source_id, DAY1, 'op-r')
    assert result['disposition'] == 'succeeded' and len(document_ids(result)) == 1
    package = package_payload(pw_database)
    assert package['requested_url'].endswith('/articles/r') and package['final_url'].endswith('/articles/moved')
    assert ('enclosure', site.base + '/img/r.jpg') in {(item['role'], item['locator']) for item in package['media_discoveries']}


def test_a_stale_grant_returns_a_stale_result_before_any_fetch(manager, pw_database, site):
    site.serve_feed('a', 'Port strike ends', article_html('Port strike ends'))
    source_id = register(manager, pw_database, site.base + '/feeds/a.xml', 'feed-a')
    grants = Grants(stale=True)
    handler = collect_source_activity_handler(collect_factory(manager, pw_database, grants=grants), lambda: NOW)
    result = collect(handler, source_id, DAY1, 'op-stale')
    assert result['disposition'] == 'stale' and result['problem']['code'] == 'STALE_GRANT'
    assert site.seen == [] and count(pw_database, 'cp_collected_document_packages') == 0
    assert grants.calls == ['grant-1']

PARAMETERS = {
    'workflow.start_to_close_seconds': {
        'control-workflows': 60,
        'cloud-io': 900,
        'cloud-ai': 240,
        'desktop-cpu': 600,
        'desktop-gpu': 900,
        'desktop-render': 1200,
    },
    'workflow.heartbeat_seconds': 30,
    'workflow.retry': {
        'initial_interval_seconds': 5,
        'backoff_coefficient': 2.0,
        'maximum_interval_seconds': 120,
        'maximum_attempts': 3,
    },
    'workflow.schedule': {'cloud_schedule_enabled': False},
    'ai.quota_wait_poll_seconds': 60,
    'meta.revision': 1,
}


def activity_function(handlers: dict[str, Any], name: str) -> Any:
    services = build_workflow_services(parameters=PARAMETERS, handlers=handlers, clock=lambda: NOW, timezone_approved=False)
    registration = build_temporal_registration(services, grant_issuer=lambda *args: None, capability_reader=lambda: {})
    for functions in registration.activities_by_queue.values():
        for function in functions:
            if getattr(function, '__temporal_activity_definition').name == name:
                return function
    raise AssertionError(name)


def test_request_errors_become_non_retryable_application_errors(manager, pw_database):
    handlers = {
        'CollectSource': collect_source_activity_handler(collect_factory(manager, pw_database), lambda: NOW),
        'ResolveCollectedDocument': resolve_activity_handler(resolve_factory(manager, pw_database), lambda: NOW),
    }
    for name in handlers:
        bad = request(name, claims(), [], 'op-bad-' + name)
        with pytest.raises(ApplicationError) as info:
            asyncio.run(activity_function(handlers, name)(bad))
        assert info.value.non_retryable is True
        assert str(info.value) == INVALID_ACTIVITY_REQUEST


def test_a_handler_without_the_wrapper_leaks_activity_request_error(manager, pw_database):
    raw = collect_source_handler(collect_factory(manager, pw_database).deps_for_call(), lambda: NOW)
    bad = request('CollectSource', claims(), [], 'op-bad')
    with pytest.raises(CollectRequestError):
        asyncio.run(activity_function({'CollectSource': raw}, 'CollectSource')(bad))


def test_missing_grant_and_bad_requests_map_to_distinct_rejection_codes(manager, pw_database):
    handlers = {
        'CollectSource': collect_source_activity_handler(collect_factory(manager, pw_database), lambda: NOW),
        'ResolveCollectedDocument': resolve_activity_handler(resolve_factory(manager, pw_database), lambda: NOW),
    }
    for name, handler in handlers.items():
        no_grant = {key: value for key, value in request(name, claims(), [], 'op-1').items() if key != 'execution_grant'}
        with pytest.raises(ActivityRejected) as missing:
            handler(no_grant, None)
        assert missing.value.code == MISSING_EXECUTION_GRANT
        with pytest.raises(ActivityRejected) as invalid:
            handler(request(name, claims(), [], 'op-2'), claims())
        assert invalid.value.code == INVALID_ACTIVITY_REQUEST
        assert invalid.value.issues and all(set(issue) == {'code', 'field'} for issue in invalid.value.issues)

def test_resolve_creates_an_article_then_a_new_revision(manager, pw_database, site):
    site.serve_feed('a', 'Port strike ends', article_html('Port strike ends'))
    source_id = register(manager, pw_database, site.base + '/feeds/a.xml', 'feed-a')
    collector = collect_source_activity_handler(collect_factory(manager, pw_database), lambda: NOW)
    resolver = resolve_activity_handler(resolve_factory(manager, pw_database), lambda: NOW)
    first_doc = document_ids(collect(collector, source_id, DAY1, 'op-1'))[0]
    first = resolve(resolver, first_doc, 'res-1')
    assert validate_activity_result(first) == [] and first['disposition'] == 'succeeded'
    revision = DEFAULT_DEDUP_POLICY['dedup_policy_revision']
    assert first['output_refs'] == [{'ref_type': 'collected_document_resolution', 'ref_id': f'{first_doc}:{revision}'}]
    assert count(pw_database, 'cp_articles') == 1 and count(pw_database, 'cp_article_revisions') == 1
    assert scalar(pw_database, 'SELECT payload FROM controlplane.cp_collected_document_resolutions')['disposition'] == 'NEW_ARTICLE'
    assert resolve(resolver, first_doc, 'res-1') == first
    assert count(pw_database, 'cp_articles') == 1 and count(pw_database, 'cp_article_revisions') == 1
    site.routes['/articles/a'] = (200, 'text/html; charset=utf-8', article_html('Port strike ends', EXTRA))
    second_doc = document_ids(collect(collector, source_id, DAY2, 'op-2', 2))[0]
    assert second_doc != first_doc
    second = resolve(resolver, second_doc, 'res-2', 2)
    assert second['disposition'] == 'succeeded'
    assert count(pw_database, 'cp_articles') == 1 and count(pw_database, 'cp_article_revisions') == 2
    sql = "SELECT count(*) FROM controlplane.cp_collected_document_resolutions WHERE payload->>'disposition' = 'NEW_REVISION'"
    assert scalar(pw_database, sql) == 1


def test_tier_lookup_reads_postgresql_and_the_better_tier_becomes_representative(manager, pw_database, site):
    html = article_html('Shared story')
    site.serve_feed('low', 'Shared story', html)
    site.serve_feed('high', 'Shared story', html)
    low = register(manager, pw_database, site.base + '/feeds/low.xml', 'feed-low', tier='tier_2')
    high = register(manager, pw_database, site.base + '/feeds/high.xml', 'feed-high', tier='tier_1')
    lookup = PostgresSourceTierLookup(manager.borrow_connection, pw_database.workspace_id)
    assert (lookup.tier_of(low), lookup.tier_of(high)) == (2, 1)
    with pytest.raises(LookupError):
        lookup.tier_of('missing-source')
    collector = collect_source_activity_handler(collect_factory(manager, pw_database), lambda: NOW)
    resolver = resolve_activity_handler(resolve_factory(manager, pw_database), lambda: NOW)
    low_doc = document_ids(collect(collector, low, DAY1, 'op-low'))[0]
    high_doc = document_ids(collect(collector, high, DAY1, 'op-high', 2))[0]
    assert resolve(resolver, low_doc, 'res-low')['disposition'] == 'succeeded'
    assert resolve(resolver, high_doc, 'res-high', 2)['disposition'] == 'succeeded'
    with pw_database.connect() as conn:
        rows = conn.execute("SELECT payload->>'collected_document_id', payload->>'disposition' FROM controlplane.cp_collected_document_resolutions").fetchall()
    assert dict(rows) == {low_doc: 'NEW_ARTICLE', high_doc: 'DUPLICATE_MEDIA_ONLY'}
    with PostgresIngestionUnitOfWork(manager, workspace_id=pw_database.workspace_id) as uow:
        articles = uow.articles.list_all()
    assert len(articles) == 1 and articles[0].representative_source_id == high

def test_package_loader_looks_up_by_collected_document_id(manager, pw_database, site):
    site.serve_feed('a', 'Port strike ends', article_html('Port strike ends'))
    source_id = register(manager, pw_database, site.base + '/feeds/a.xml', 'feed-a')
    collector = collect_source_activity_handler(collect_factory(manager, pw_database), lambda: NOW)
    doc_id = document_ids(collect(collector, source_id, DAY1, 'op-1'))[0]
    factory = resolve_factory(manager, pw_database)
    package = factory.package_loader()({'ref_type': 'collected_document', 'ref_id': doc_id})
    assert package['collected_document_id'] == doc_id and package['source_id'] == source_id
    for bad in ({'ref_type': 'collected_document', 'ref_id': 'missing-doc'}, {'ref_type': 'collection_run', 'ref_id': doc_id}):
        with pytest.raises(LookupError):
            factory.package_loader()(bad)
    failed = resolve(resolve_activity_handler(factory, lambda: NOW), 'missing-doc', 'res-missing')
    assert validate_activity_result(failed) == [] and failed['disposition'] == 'failed'
    assert failed['problem']['code'] == 'FAILED_FINAL' and failed['problem']['retryable'] is False


def test_dedup_policy_default_is_explicit_and_can_be_overridden(manager, pw_database, site):
    assert DEFAULT_DEDUP_POLICY['dedup_policy_revision'] == 'dedup-default-v1'
    assert (DEFAULT_DEDUP_POLICY['near_duplicate_jaccard'], DEFAULT_DEDUP_POLICY['shingle_size']) == (0.8, 3)
    site.serve_feed('a', 'Port strike ends', article_html('Port strike ends'))
    source_id = register(manager, pw_database, site.base + '/feeds/a.xml', 'feed-a')
    collector = collect_source_activity_handler(collect_factory(manager, pw_database), lambda: NOW)
    doc_id = document_ids(collect(collector, source_id, DAY1, 'op-1'))[0]
    override = {'dedup_policy_revision': 'dedup-pw-a2-v2', 'near_duplicate_jaccard': 0.9, 'shingle_size': 5}
    resolver = resolve_activity_handler(resolve_factory(manager, pw_database, dedup_policy=override), lambda: NOW)
    result = resolve(resolver, doc_id, 'res-1')
    assert result['output_refs'][0]['ref_id'] == f'{doc_id}:dedup-pw-a2-v2'
    sql = "SELECT payload->>'dedup_policy_revision' FROM controlplane.cp_collected_document_resolutions"
    assert scalar(pw_database, sql) == 'dedup-pw-a2-v2'


def test_production_deps_sources_follow_the_package_contract():
    for relative in ('src/source_ingestion/worker/production_deps.py', 'src/ingestion/application/production_deps.py'):
        text = (ROOT / relative).read_text(encoding='utf-8')
        lowered = text.lower()
        assert 'activityrequesterror' in lowered and 'activityrejected' in lowered
        assert 'fake' not in lowered and 'from src.' not in lowered and 'import src.' not in lowered
        assert 'import psycopg' not in lowered and 'from psycopg' not in lowered
        assert 'import temporalio' not in lowered and 'from temporalio' not in lowered
        module_calls = [ast.unparse(node.value) for node in ast.parse(text).body if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)]
        assert not any('ActivityDeps' in call for call in module_calls)
