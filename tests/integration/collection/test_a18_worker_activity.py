"""A-18: the worker activity handler runs CollectSource for an ActivityRequest with GrantClaims (YC-HT-G-10) (CT-WF-003, CT-WF-006).

coveredIds: A-RULE-014, A-RULE-016
"""
from __future__ import annotations

import ast
import dataclasses
import datetime
import pathlib
import socket

import pytest

from controlplane.domain.orchestration.fencing import GrantClaims

from source_ingestion.adapters.memory import InMemoryUnitOfWork
from source_ingestion.adapters.secure_fetch import fetch_problem
from source_ingestion.adapters.stdlib_html_extractor import StdlibHtmlExtractor
from source_ingestion.domain.collection_run import RetryPolicy
from source_ingestion.domain.package import ExtractionPolicy
from source_ingestion.domain.source import SourcePolicy, register_source
from source_ingestion.ports.source_adapter import CandidateListing, FetchedDocument, FetchObservation
from source_ingestion.worker import activity_handler as ah
from source_ingestion.worker.activity_handler import (
    ActivityRequestError,
    CollectActivityDeps,
    handle_collect_source_activity,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'source_ingestion' / 'worker' / 'activity_handler.py'
WORKSPACE = 'ws-1'
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
GRANT = GrantClaims('op-1', 'stage-1', 3, '1', 'lease-1', '2026-10-18T07:00:00Z', '2026-10-18T09:00:00Z', 'CollectSource', 'fp-1')
OLD_GENERATION = dataclasses.replace(GRANT, execution_generation=2)
OLD_EPOCH = dataclasses.replace(GRANT, recovery_epoch='0')
RUN_ID = 'run:op-key-1'


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
    """Fixture adapter: in-memory listing and documents, never opens a socket."""

    def __init__(self, locators, *, listing_result=None, behaviors=None):
        self.locators = tuple(locators)
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
        return CandidateListing(self.locators, 'cursor-1', True)

    def fetch_document(self, locator):
        self.fetch_calls.append(locator)
        behavior = self.behaviors.get(locator)
        if isinstance(behavior, BaseException):
            raise behavior
        if behavior is not None:
            return behavior
        return document(locator, html_of(int(locator.rsplit('/', 1)[1])))


def make_source(unit, source_id='src-1') -> None:
    source = register_source(
        source_id=source_id, workspace_id=WORKSPACE,
        canonical_locator=f'https://news.example.test/feed/{source_id}',
        name=f'Nguồn {source_id}', source_kind='rss_feed', tier='tier-1', topics=['kinh-te'], notes='',
        collection_enabled=True, admin_metadata={}, actor='tester', at=NOW, policy=SOURCE_POLICY,
    )
    with unit:
        unit.sources.add(source)
        unit.commit()


def request_of(operation_key='op-key-1', source_id='src-1', day='2026-10-18') -> dict:
    return {
        'workflow_id': 'wf-1', 'workflow_run_id': 'wfr-1', 'stage_run_id': 'stage-1',
        'activity_name': 'CollectSource', 'activity_version': '1',
        'input_refs': [
            {'ref_type': 'collection_source', 'ref_id': source_id},
            {'ref_type': 'business_date', 'ref_id': day},
        ],
        'operation_key': operation_key, 'capability_requirements': {'adapter': 'rss_feed'},
        'retry_policy_ref': 'retry-r1',
    }


def clock() -> datetime.datetime:
    return NOW


class FakeClaimsCurrencyPort:
    def __init__(self, current=()):
        self._current = frozenset(current)

    def is_grant_current(self, grant):
        return isinstance(grant, GrantClaims) and grant in self._current


def make_deps(unit, adapter, current=(GRANT,)) -> CollectActivityDeps:
    return CollectActivityDeps(
        uow=unit, grants=FakeClaimsCurrencyPort(current), adapter_for=lambda source_id: adapter,
        extractor=StdlibHtmlExtractor(), retry_policy=RETRY, adapter_revision='adapter-r1',
        workspace_id=WORKSPACE, extraction_policy=EXTRACTION,
    )


def handle(deps, request=None, grant=GRANT):
    return handle_collect_source_activity(request if request is not None else request_of(), grant, deps, clock)


@pytest.fixture
def unit() -> InMemoryUnitOfWork:
    value = InMemoryUnitOfWork()
    make_source(value)
    return value


def test_current_grant_collects_and_returns_a_succeeded_activity_result(unit):
    result = handle(make_deps(unit, FakeAdapter([locator_of(1), locator_of(2)])))
    assert result['disposition'] == 'succeeded'
    assert (result['stage_run_id'], result['grant_id']) == ('stage-1', 'op-1')
    assert (result['execution_generation'], result['recovery_epoch']) == (3, '1')
    assert result['completed_at'] == '2026-10-18T08:00:00Z'
    assert result['metrics'] == {
        'urls_seen': 2, 'fetched': 2, 'skipped': 0, 'failed': 0, 'packages_committed': 2, 'replayed': False,
    }
    assert result['warnings'] == []
    assert 'problem' not in result
    records = unit.packages.list_by_run(RUN_ID)
    assert len(records) == 2
    assert result['output_refs'] == [
        {'ref_type': 'collection_run', 'ref_id': RUN_ID},
        *({'ref_type': 'collected_document', 'ref_id': str(r.payload['collected_document_id'])} for r in records),
    ]
    assert unit.checkpoints.get_latest('src-1').execution_generation == 3


@pytest.mark.parametrize('stale', [OLD_GENERATION, OLD_EPOCH], ids=['old_generation', 'old_recovery_epoch'])
def test_stale_grant_is_rejected_without_any_commit(unit, stale):
    adapter = FakeAdapter([locator_of(1)])
    deps = make_deps(unit, adapter)
    result = handle(deps, grant=stale)
    assert result['disposition'] == 'stale'
    assert result['problem']['code'] == 'STALE_GRANT'
    assert result['problem']['retryable'] is False
    assert result['output_refs'] == []
    assert (result['execution_generation'], result['recovery_epoch']) == (
        stale.execution_generation, str(stale.recovery_epoch),
    )
    assert adapter.cursors_seen == [] and adapter.fetch_calls == []
    assert unit.runs.list_by_source(WORKSPACE, 'src-1') == ()
    assert unit.packages.list_by_run(RUN_ID) == ()
    assert unit.checkpoints.get_latest('src-1') is None
    assert unit.outbox.records() == ()
    assert deps.results.get(WORKSPACE, 'op-key-1') is None


def test_old_generation_checkpoint_write_is_rejected_even_if_the_grant_port_wrongly_accepts_it(unit):
    first = handle(make_deps(unit, FakeAdapter([locator_of(1), locator_of(2)])))
    assert first['disposition'] == 'succeeded'
    before = unit.checkpoints.get_latest('src-1')
    deps = make_deps(unit, FakeAdapter([locator_of(1), locator_of(3)]), current=(GRANT, OLD_GENERATION))
    result = handle(deps, request_of(operation_key='op-key-2', day='2026-10-19'), OLD_GENERATION)
    assert result['disposition'] != 'succeeded'
    assert unit.checkpoints.get_latest('src-1') == before
    assert unit.packages.list_by_run('run:op-key-2') == ()
    assert deps.results.get(WORKSPACE, 'op-key-2') is None


def test_same_operation_key_returns_the_stored_result_without_collecting_again(unit):
    adapter = FakeAdapter([locator_of(1), locator_of(2)])
    deps = make_deps(unit, adapter)
    first = handle(deps)
    outbox_size = len(unit.outbox.records())
    second = handle(deps)
    assert second == first
    assert adapter.cursors_seen == [None]
    assert len(adapter.fetch_calls) == 2
    assert len(unit.outbox.records()) == outbox_size
    second['metrics']['fetched'] = 99
    assert handle(deps) == first


def test_stale_grant_does_not_receive_the_stored_result_of_a_newer_generation(unit):
    deps = make_deps(unit, FakeAdapter([locator_of(1)]))
    assert handle(deps)['disposition'] == 'succeeded'
    result = handle(deps, grant=OLD_GENERATION)
    assert result['disposition'] == 'stale'
    assert result['output_refs'] == []


def test_same_operation_key_with_different_input_refs_is_a_conflict(unit):
    deps = make_deps(unit, FakeAdapter([locator_of(1)]))
    first = handle(deps)
    conflict = handle(deps, request_of(source_id='src-2'))
    assert conflict['disposition'] == 'failed'
    assert conflict['problem']['code'] == 'OPERATION_KEY_CONFLICT'
    assert conflict['output_refs'] == []
    assert handle(deps) == first


def test_waiting_result_is_not_stored_and_the_same_key_can_retry(unit):
    adapter = FakeAdapter([locator_of(1)], listing_result=fetch_problem('UPSTREAM_ERROR', 'corr-1', status=503))
    deps = make_deps(unit, adapter)
    first = handle(deps)
    assert first['disposition'] == 'waiting'
    assert first['problem']['code'] == 'UPSTREAM_ERROR'
    assert first['problem']['retryable'] is True
    assert deps.results.get(WORKSPACE, 'op-key-1') is None
    adapter.listing_result = None
    second = handle(deps)
    assert second['disposition'] == 'succeeded'
    assert second['metrics']['packages_committed'] == 1
    assert deps.results.get(WORKSPACE, 'op-key-1') is not None


def test_item_failure_is_a_warning_and_the_partial_run_is_succeeded(unit):
    bad = locator_of(2)
    adapter = FakeAdapter(
        [locator_of(1), bad, locator_of(3)],
        behaviors={bad: fetch_problem('UPSTREAM_ERROR', 'corr-1', status=503)},
    )
    result = handle(make_deps(unit, adapter))
    assert result['disposition'] == 'succeeded'
    assert result['warnings'] == [f'UPSTREAM_ERROR:{bad}']
    assert (result['metrics']['failed'], result['metrics']['packages_committed']) == (1, 2)
    assert 'problem' not in result


def test_failed_final_run_returns_a_failed_result_with_a_standard_problem(unit):
    deps = make_deps(unit, FakeAdapter([]))
    result = handle(deps, request_of(source_id='src-9'))
    assert result['disposition'] == 'failed'
    assert result['problem']['code'] == 'SOURCE_NOT_FOUND'
    assert result['problem']['retryable'] is False
    assert isinstance(result['problem']['message'], str) and result['problem']['message']
    assert deps.results.get(WORKSPACE, 'op-key-1') is None


def test_result_never_contains_a_secret_from_adapter_errors(unit):
    leaky = locator_of(2) + f'?token={SECRET}'
    adapter = FakeAdapter(
        [locator_of(1), leaky],
        behaviors={leaky: RuntimeError(f'proxy rejected Bearer {SECRET} password: {SECRET}')},
    )
    result = handle(make_deps(unit, adapter))
    assert result['disposition'] == 'succeeded'
    assert result['warnings'] == [f'ADAPTER_EXCEPTION:{locator_of(2)}']
    assert SECRET not in repr(result)
    boom = RuntimeError(
        f'connect failed token={SECRET} Bearer abc.def.ghi https://news.example.test/feed?api_key={SECRET}'
    )
    other = InMemoryUnitOfWork()
    make_source(other)
    failed = handle(make_deps(other, FakeAdapter([], listing_result=boom)))
    assert failed['disposition'] == 'failed'
    assert failed['problem']['code'] == 'ADAPTER_EXCEPTION'
    dump = repr(failed)
    assert SECRET not in dump and 'abc.def.ghi' not in dump and 'api_key' not in dump


def test_exception_escaping_collect_source_becomes_a_redacted_failed_result(unit, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError(f'database password={SECRET} lost')

    monkeypatch.setattr(ah, 'collect_source', boom)
    deps = make_deps(unit, FakeAdapter([locator_of(1)]))
    result = handle(deps)
    assert result['disposition'] == 'failed'
    assert result['problem']['code'] == 'COLLECTION_ABORTED'
    assert result['problem']['retryable'] is True
    assert SECRET not in repr(result)
    assert deps.results.get(WORKSPACE, 'op-key-1') is None


INVALID_REQUESTS = (
    ('missing_operation_key', lambda r: r.pop('operation_key'), ('missing_required', 'operation_key')),
    ('secret_in_payload', lambda r: r.update(secret_value=SECRET), ('forbidden_field', 'secret_value')),
    ('wrong_activity_name', lambda r: r.update(activity_name='Other'), ('invalid_value', 'activity_name')),
    ('one_input_ref', lambda r: r.update(input_refs=r['input_refs'][:1]), ('invalid_value', 'input_refs')),
    ('bad_business_date', lambda r: r['input_refs'][1].update(ref_id='18/10/2026'), ('invalid_value', 'input_refs')),
    ('input_refs_as_string', lambda r: r.update(input_refs='ref-1'), ('wrong_type', 'input_refs')),
    ('other_stage_run', lambda r: r.update(stage_run_id='stage-2'), ('invalid_value', 'execution_grant.stage_run_id')),
)
INVALID_GRANTS = (
    ('not_an_execution_grant', {'workspace_id': WORKSPACE}, ('wrong_type', 'execution_grant')),
    ('negative_generation', dataclasses.replace(GRANT, execution_generation=-1),
     ('invalid_value', 'execution_grant.execution_generation')),
    ('blank_grant_id', dataclasses.replace(GRANT, grant_id=' '), ('invalid_value', 'execution_grant.grant_id')),
    ('missing_execution_grant', None, ('wrong_type', 'execution_grant')),
    ('recovery_epoch_as_int', dataclasses.replace(GRANT, recovery_epoch=1), ('invalid_value', 'execution_grant.recovery_epoch')),
)


@pytest.mark.parametrize(('mutate', 'issue'), [case[1:] for case in INVALID_REQUESTS], ids=[case[0] for case in INVALID_REQUESTS])
def test_invalid_request_raises_before_any_lookup_or_write(unit, mutate, issue):
    adapter = FakeAdapter([locator_of(1)])
    request = request_of()
    mutate(request)
    with pytest.raises(ActivityRequestError) as raised:
        handle(make_deps(unit, adapter), request)
    assert raised.value.code == 'VALIDATION_ERROR'
    assert issue in raised.value.issues
    assert SECRET not in repr(raised.value)
    assert adapter.cursors_seen == []
    assert unit.runs.list_by_source(WORKSPACE, 'src-1') == ()
    assert unit.outbox.records() == ()


@pytest.mark.parametrize(('grant', 'issue'), [case[1:] for case in INVALID_GRANTS], ids=[case[0] for case in INVALID_GRANTS])
def test_invalid_grant_raises_validation_error(unit, grant, issue):
    adapter = FakeAdapter([locator_of(1)])
    with pytest.raises(ActivityRequestError) as raised:
        handle(make_deps(unit, adapter), grant=grant)
    assert raised.value.code == 'VALIDATION_ERROR'
    assert issue in raised.value.issues
    assert adapter.cursors_seen == []
    assert adapter.fetch_calls == []
    assert unit.runs.list_by_source(WORKSPACE, 'src-1') == ()
    assert unit.outbox.records() == ()


def imported_modules(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding='utf-8'))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def test_handler_uses_controlplane_grant_claims_and_defines_no_grant_class():
    assert ah.GrantClaims is GrantClaims
    assert not hasattr(ah, 'ExecutionGrant')
    defined = [name for name, value in vars(ah).items() if isinstance(value, type) and value.__module__ == ah.__name__]
    assert [name for name in defined if 'Grant' in name] == []


def test_collect_source_does_not_run_without_execution_grant(unit, monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError('collect_source must not run')

    monkeypatch.setattr(ah, 'collect_source', boom)
    adapter = FakeAdapter([locator_of(1)])
    deps = make_deps(unit, adapter)
    with pytest.raises(ActivityRequestError) as raised:
        handle(deps, grant=None)
    assert raised.value.code == 'VALIDATION_ERROR'
    assert ('wrong_type', 'execution_grant') in raised.value.issues
    assert adapter.cursors_seen == []
    assert adapter.fetch_calls == []
    assert deps.results.get(WORKSPACE, 'op-key-1') is None


def test_deps_require_a_workspace_id(unit):
    with pytest.raises(ValueError):
        dataclasses.replace(make_deps(unit, FakeAdapter([])), workspace_id=' ')


def test_handler_imports_no_workflow_runtime_ui_render_voice_or_desktop_code():
    banned_parts = {'temporalio', 'ui', 'render', 'voice', 'desktop'}
    banned = sorted(name for name in imported_modules(MODULE_PATH) if banned_parts & set(name.split('.')))
    assert banned == []


def test_handler_imports_only_stdlib_domain_ports_and_application():
    stdlib = {'__future__', 'copy', 'datetime', 're', 'collections.abc', 'dataclasses', 'types', 'typing'}
    allowed = (
        'controlplane.domain', 'source_ingestion.application', 'source_ingestion.domain', 'source_ingestion.ports',
    )
    unexpected = sorted(name for name in imported_modules(MODULE_PATH) if name not in stdlib and not name.startswith(allowed))
    assert unexpected == []


def test_handler_registers_no_workflow_or_activity_through_decorators():
    tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
    functions = (ast.FunctionDef, ast.AsyncFunctionDef)
    assert [node.name for node in ast.walk(tree) if isinstance(node, functions) and node.decorator_list] == []


def test_module_docstring_lists_the_covered_rule_ids():
    docstring = ast.get_docstring(ast.parse(pathlib.Path(__file__).read_text(encoding='utf-8')))
    assert 'coveredIds: A-RULE-014, A-RULE-016' in docstring


def test_network_is_blocked_for_the_whole_suite():
    for name in NETWORK_FUNCTIONS:
        with pytest.raises(AssertionError):
            getattr(socket, name)('example.test', 80)
