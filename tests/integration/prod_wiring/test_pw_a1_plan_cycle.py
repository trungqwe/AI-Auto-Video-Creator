"""PW-A1: nạp bảy nguồn seed và PlanCollectionCycle trên PostgreSQL thật, đồng hồ tiêm được, không gọi mạng.

coveredIds: PW-A1-01, CT-SRC-004, CONV-A-06, FR-COL-001
"""
from __future__ import annotations

import json
import pathlib
from datetime import date, datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from controlplane.application.orchestration.workflows.activities import (
    INVALID_ACTIVITY_REQUEST,
    MISSING_EXECUTION_GRANT,
    ActivityRejected,
)
from controlplane.domain.orchestration.activity_binding import validate_activity_result
from controlplane.infrastructure.db.uow import TransactionManager
from source_ingestion.application.plan_cycle import PlanCollectionCycle, plan_collection_cycle_handler
from source_ingestion.application.seed_sources import SeedSourcesError, seed_sources
from source_ingestion.application.source_commands import SourceCommandHandler
from source_ingestion.domain.source import SourcePolicy
from source_ingestion.persistence.unit_of_work import PostgresSourceIngestionUnitOfWork

ROOT = pathlib.Path(__file__).resolve().parents[3]
SOURCES_PATH = ROOT / 'tools' / 'launcher' / 'prod' / 'sources.json'
SOURCES = json.loads(SOURCES_PATH.read_text(encoding='utf-8'))['sources']
TIERS = ('tier_1', 'tier_2', 'tier_3')
POLICY = SourcePolicy(
    policy_revision='pw-a1',
    source_kinds=frozenset({'rss_feed'}),
    tiers=frozenset(TIERS),
    admin_metadata_keys=frozenset(),
)
CLAIMS = SimpleNamespace(stage_run_id='stage-1', grant_id='grant-1', execution_generation=1, recovery_epoch='epoch-1')
DAY1_MORNING = datetime(2026, 10, 27, 3, 0, tzinfo=timezone.utc)  # 10:00 ICT 27/10
DAY1_LATE = datetime(2026, 10, 27, 16, 30, tzinfo=timezone.utc)  # 23:30 ICT 27/10, cùng ngày
DAY2_EARLY = datetime(2026, 10, 27, 17, 30, tzinfo=timezone.utc)  # 00:30 ICT 28/10, sang ngày sau


class Resolver:
    def __call__(self, host: str) -> list[str]:
        return ['8.8.8.8']


class Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def manager(pw_database: Any):
    pool = TransactionManager(pw_database.dsn, pool_max_size=4)
    try:
        yield pool
    finally:
        pool.close()


def new_uow(manager: Any, db: Any) -> PostgresSourceIngestionUnitOfWork:
    return PostgresSourceIngestionUnitOfWork(manager, workspace_id=db.workspace_id)


def make_handler(manager: Any, db: Any) -> SourceCommandHandler:
    return SourceCommandHandler(
        uow=new_uow(manager, db),
        policy_provider=lambda workspace_id: POLICY,
        resolver=Resolver(),
        recovery_epoch='pw-a1',
    )


def seed(manager: Any, db: Any, path: pathlib.Path = SOURCES_PATH):
    return seed_sources(make_handler(manager, db), path, workspace_id=db.workspace_id)


def make_service(manager: Any, db: Any, clock: Any, tier_order: tuple[str, ...] = TIERS, uow_factory: Any = None):
    return PlanCollectionCycle(
        uow_factory=uow_factory or (lambda: new_uow(manager, db)),
        workspace_id=db.workspace_id,
        tier_order=tier_order,
        clock=clock,
    )


def scalar(db: Any, sql: str, params: tuple = ()) -> Any:
    with db.connect() as conn:
        return conn.execute(sql, params).fetchone()[0]


def count(db: Any, table: str) -> int:
    return scalar(db, 'SELECT count(*) FROM controlplane.' + table)


def stored_sources(manager: Any, db: Any):
    with new_uow(manager, db) as uow:
        return uow.sources.list_sources(db.workspace_id)


def ids_by_name(manager: Any, db: Any) -> dict[str, str]:
    return {s.name: s.source_id for s in stored_sources(manager, db)}


def ref_ids(outcome: dict[str, Any]) -> list[str]:
    assert {ref['ref_type'] for ref in outcome['output_refs']} <= {'collection_source'}
    return [ref['ref_id'] for ref in outcome['output_refs']]


def run(service: Any, key: str) -> dict[str, Any]:
    return service({'operation_key': key}, CLAIMS)


def test_seed_twice_leaves_exactly_seven_sources(manager, pw_database):
    first = seed(manager, pw_database)
    assert (first.registered, first.replayed, first.existing, first.tombstoned) == (7, 0, 0, 0)
    assert count(pw_database, 'cp_sources') == 7
    second = seed(manager, pw_database)
    assert (second.registered, second.replayed, second.existing, second.tombstoned) == (0, 7, 0, 0)
    assert count(pw_database, 'cp_sources') == 7
    assert count(pw_database, 'cp_source_identities') == 7
    stored = stored_sources(manager, pw_database)
    assert {s.name: (s.canonical_locator, s.tier) for s in stored} == {item['code']: (item['url'], item['tier']) for item in SOURCES}
    assert {s.status.value for s in stored} == {'ACTIVE'}


@pytest.mark.parametrize(
    'document',
    [
        {'sources': []},
        {'sources': [SOURCES[0], {**SOURCES[1], 'url': 'http://feeds.bbci.co.uk/news/technology/rss.xml'}]},
        {'sources': [SOURCES[1], SOURCES[2], {**SOURCES[3], 'code': SOURCES[1]['code']}]},
        {'sources': [SOURCES[0], {**SOURCES[1], 'enabled': 'yes'}]},
    ],
)
def test_seed_rejects_an_invalid_file_before_any_write(manager, pw_database, tmp_path, document):
    path = tmp_path / 'sources.json'
    path.write_text(json.dumps(document), encoding='utf-8')
    with pytest.raises(SeedSourcesError):
        seed(manager, pw_database, path)
    assert count(pw_database, 'cp_sources') == 0


def test_seed_counts_existing_and_tombstoned_sources_without_resurrecting(manager, pw_database):
    handler = make_handler(manager, pw_database)
    common = {'workspace_id': pw_database.workspace_id, 'actor': 'test', 'correlation_id': 'test', 'source_kind': 'rss_feed', 'tier': 'tier_1', 'topics': ['news']}
    by_code = {item['code']: item for item in SOURCES}
    handler.register_source(idempotency_key='other-bbc-world', locator=by_code['bbc-world']['url'], name='bbc-world', **common)
    tech = handler.register_source(idempotency_key='other-bbc-tech', locator=by_code['bbc-tech']['url'], name='bbc-tech', **common)
    handler.remove_source(
        workspace_id=pw_database.workspace_id,
        idempotency_key='remove-bbc-tech',
        actor='test',
        correlation_id='test',
        source_id=tech.receipt.aggregate_ref,
        expected_revision=1,
    )
    report = seed(manager, pw_database)
    assert (report.registered, report.replayed, report.existing, report.tombstoned) == (5, 0, 1, 1)
    assert count(pw_database, 'cp_sources') == 7
    status = scalar(pw_database, 'SELECT status FROM controlplane.cp_sources WHERE source_id = %s', (tech.receipt.aggregate_ref,))
    assert status == 'REMOVED_TOMBSTONE'


def test_first_cycle_returns_seven_refs_then_none_the_same_day_then_seven_the_next_day(manager, pw_database):
    seed(manager, pw_database)
    ids = set(ids_by_name(manager, pw_database).values())
    clock = Clock(DAY1_MORNING)
    service = make_service(manager, pw_database, clock)
    first = run(service, 'op-1')
    assert first['disposition'] == 'succeeded'
    assert len(ref_ids(first)) == 7 and set(ref_ids(first)) == ids
    assert first['metrics']['business_date'] == '2026-10-27'
    assert count(pw_database, 'cp_source_cycle_marks') == 7
    assert scalar(pw_database, 'SELECT min(created_at) FROM controlplane.cp_source_cycle_marks') == DAY1_MORNING
    clock.now = DAY1_LATE
    assert ref_ids(run(service, 'op-2')) == []
    assert count(pw_database, 'cp_source_cycle_marks') == 7
    clock.now = DAY2_EARLY
    third = run(service, 'op-3')
    assert len(ref_ids(third)) == 7 and set(ref_ids(third)) == ids
    assert third['metrics']['business_date'] == '2026-10-28'
    assert count(pw_database, 'cp_source_cycle_marks') == 14
    assert scalar(pw_database, 'SELECT min(cycle_day) FROM controlplane.cp_source_cycle_marks') == date(2026, 10, 27)
    assert scalar(pw_database, 'SELECT max(cycle_day) FROM controlplane.cp_source_cycle_marks') == date(2026, 10, 28)


def test_same_operation_key_replays_the_same_refs_and_other_keys_get_none(manager, pw_database):
    seed(manager, pw_database)
    service = make_service(manager, pw_database, Clock(DAY1_MORNING))
    first = ref_ids(run(service, 'op-1'))
    assert len(first) == 7
    assert ref_ids(run(service, 'op-1')) == first
    assert count(pw_database, 'cp_source_cycle_marks') == 7
    assert ref_ids(run(service, 'op-2')) == []
    assert count(pw_database, 'cp_source_cycle_marks') == 7


def test_disabled_sources_are_not_due(manager, pw_database):
    seed(manager, pw_database)
    ids = ids_by_name(manager, pw_database)
    make_handler(manager, pw_database).update_source_metadata(
        workspace_id=pw_database.workspace_id,
        idempotency_key='disable-npr',
        actor='test',
        correlation_id='test',
        source_id=ids['npr-news'],
        expected_revision=1,
        collection_enabled=False,
    )
    due = ref_ids(run(make_service(manager, pw_database, Clock(DAY1_MORNING)), 'op-1'))
    assert len(due) == 6 and ids['npr-news'] not in due
    assert count(pw_database, 'cp_source_cycle_marks') == 6


def test_tier_threshold_blocks_lower_tier_without_consuming_marks(manager, pw_database):
    seed(manager, pw_database)
    ars = ids_by_name(manager, pw_database)['ars-technica']
    clock = Clock(DAY1_MORNING)
    narrow = make_service(manager, pw_database, clock, tier_order=('tier_1',))
    first = ref_ids(run(narrow, 'op-1'))
    assert len(first) == 6 and ars not in first
    assert count(pw_database, 'cp_source_cycle_marks') == 6
    assert scalar(pw_database, 'SELECT count(*) FROM controlplane.cp_source_cycle_marks WHERE source_id = %s', (ars,)) == 0
    wide = make_service(manager, pw_database, clock, tier_order=('tier_1', 'tier_2'))
    assert ref_ids(run(wide, 'op-2')) == [ars]
    assert count(pw_database, 'cp_source_cycle_marks') == 7


def test_refs_are_ordered_by_tier_rank_then_source_id(manager, pw_database):
    seed(manager, pw_database)
    by_id = {s.source_id: s for s in stored_sources(manager, pw_database)}
    tier_1 = sorted(i for i, s in by_id.items() if s.tier == 'tier_1')
    tier_2 = sorted(i for i, s in by_id.items() if s.tier == 'tier_2')
    assert len(tier_1) == 6 and len(tier_2) == 1
    clock = Clock(DAY1_MORNING)
    assert ref_ids(run(make_service(manager, pw_database, clock), 'op-1')) == tier_1 + tier_2
    clock.now = DAY2_EARLY
    reordered = make_service(manager, pw_database, clock, tier_order=('tier_2', 'tier_1'))
    assert ref_ids(run(reordered, 'op-2')) == tier_2 + tier_1


class CommitFailed(RuntimeError):
    pass


class ProbedUow(PostgresSourceIngestionUnitOfWork):
    """Đo mark ngay trước commit: kết nối của UoW đã thấy mark, kết nối độc lập thì chưa."""

    def __init__(self, *args: Any, db: Any, fail_commit: bool = False, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.db = db
        self.fail_commit = fail_commit
        self.before_commit: list[tuple[int, int]] = []

    def commit(self) -> None:
        inside = self._active_connection().execute('SELECT count(*) FROM controlplane.cp_source_cycle_marks').fetchone()[0]
        self.before_commit.append((inside, count(self.db, 'cp_source_cycle_marks')))
        if self.fail_commit:
            raise CommitFailed('commit failed')
        super().commit()


def test_marks_are_written_in_the_plan_transaction_and_commit_with_it(manager, pw_database):
    seed(manager, pw_database)
    probed = ProbedUow(manager, db=pw_database, workspace_id=pw_database.workspace_id)
    service = make_service(manager, pw_database, Clock(DAY1_MORNING), uow_factory=lambda: probed)
    assert len(ref_ids(run(service, 'op-1'))) == 7
    assert probed.before_commit == [(7, 0)]
    assert count(pw_database, 'cp_source_cycle_marks') == 7


def test_a_failed_commit_leaves_no_mark_and_the_next_call_returns_all_sources(manager, pw_database):
    seed(manager, pw_database)
    clock = Clock(DAY1_MORNING)
    failing = ProbedUow(manager, db=pw_database, workspace_id=pw_database.workspace_id, fail_commit=True)
    with pytest.raises(CommitFailed):
        run(make_service(manager, pw_database, clock, uow_factory=lambda: failing), 'op-1')
    assert failing.before_commit == [(7, 0)]
    assert count(pw_database, 'cp_source_cycle_marks') == 0
    assert len(ref_ids(run(make_service(manager, pw_database, clock), 'op-2'))) == 7
    assert count(pw_database, 'cp_source_cycle_marks') == 7


def test_handler_builds_a_valid_activity_result_and_rejects_bad_requests(manager, pw_database):
    seed(manager, pw_database)
    clock = Clock(DAY1_MORNING)
    handler = plan_collection_cycle_handler(make_service(manager, pw_database, clock), clock)
    result = handler({'operation_key': 'op-1'}, CLAIMS)
    assert validate_activity_result(result) == []
    assert (result['disposition'], result['stage_run_id'], result['grant_id']) == ('succeeded', 'stage-1', 'grant-1')
    assert result['completed_at'] == '2026-10-27T03:00:00Z'
    assert len(result['output_refs']) == 7 and {ref['ref_type'] for ref in result['output_refs']} == {'collection_source'}
    assert result['metrics']['selected'] == 7
    with pytest.raises(ActivityRejected) as missing:
        handler({'operation_key': 'op-2'}, None)
    assert missing.value.code == MISSING_EXECUTION_GRANT
    for bad in ({}, {'operation_key': ' '}, {'operation_key': 3}):
        with pytest.raises(ActivityRejected) as invalid:
            handler(bad, CLAIMS)
        assert invalid.value.code == INVALID_ACTIVITY_REQUEST
    assert count(pw_database, 'cp_source_cycle_marks') == 7


def test_sources_follow_the_package_contract():
    folder = ROOT / 'src' / 'source_ingestion' / 'application'
    seed_text = (folder / 'seed_sources.py').read_text(encoding='utf-8')
    plan_text = (folder / 'plan_cycle.py').read_text(encoding='utf-8')
    for text in (seed_text, plan_text):
        assert 'from src.' not in text and 'import src.' not in text
        assert 'import psycopg' not in text and 'from psycopg' not in text
    assert 'register_source' in seed_text
    assert 'cp_source_cycle_marks' in plan_text
    assert plan_text.count('.commit()') == 1
    assert 'autocommit' not in plan_text and 'borrow_connection' not in plan_text
