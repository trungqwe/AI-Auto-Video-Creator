"""A-08: repository/partner ports and in-memory adapters.

coveredIds: A-RULE-004
"""
import ast
import dataclasses
import datetime
import json
import pathlib
import typing
import unittest

from controlplane.domain.concurrency import RevisionConflictError
from controlplane.domain.config_security import SecretHandle
from controlplane.domain.interfaces.outbox import IOutboxWriter
from controlplane.domain.interfaces.uow import IUnitOfWork
from controlplane.domain.orchestration import ExecutionGrant

from source_ingestion.adapters.memory import (
    FakeActivityGrantPort,
    FakeArtifactPort,
    FakeConfigPort,
    FakeContentHandoffPort,
    InMemoryOutboxWriter,
    InMemoryUnitOfWork,
    OutboxRecord,
    TransactionAlreadyActiveError,
    TransactionNotActiveError,
)
from source_ingestion.domain.checkpoint import (
    CheckpointCompleteness,
    CheckpointRejected,
    CollectionCheckpoint,
    seal_checkpoint,
)
from source_ingestion.domain.collection_run import (
    CollectionPurpose,
    DuplicatePeriodicRunError,
    RetryPolicy,
    RunStatus,
    schedule_run,
    start_run,
)
from source_ingestion.domain.package import PackageValidationError
from source_ingestion.domain.source import (
    SourcePolicy,
    SourceStatus,
    register_source,
    remove_source,
)
from source_ingestion.domain.source_candidate import (
    IdentityMatchKind,
    begin_validation,
    discover_candidate,
)
from source_ingestion.ports.partners import (
    ARTIFACT_BINDING_VERSION,
    ActivityGrantPort,
    ArtifactPort,
    ConfigPort,
    ContentHandoffPort,
    DECLARE_ARTIFACT_VERSION_REQUEST_FIELDS,
    DECLARE_ARTIFACT_VERSION_RESULT_FIELDS,
    PolicyRevisionRef,
)
from source_ingestion.ports.repositories import (
    CheckpointRepository,
    CollectionRunRepository,
    CommandReceipt,
    DuplicatePackageError,
    DuplicateReceiptError,
    DuplicateRecordError,
    DuplicateSourceIdentityError,
    PackageRecord,
    PackageRepository,
    ReceiptStore,
    RecordNotFoundError,
    SourceCandidateRepository,
    SourceRepository,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
I_BINDING = ROOT / 'docs' / 'parallel-delivery' / 'bindings' / 'i-artifact-version.json'
I_FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'i-artifact-version' / 'payloads.json'
AB_FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'a-b-collected-document' / 'payloads.json'
AT = datetime.datetime(2026, 10, 18, tzinfo=datetime.timezone.utc)
BUSINESS_DATE = datetime.date(2026, 10, 18)
LOCATOR = 'https://example.test/feed'
POLICY = SourcePolicy(
    policy_revision='policy-r1',
    source_kinds=frozenset({'rss_feed'}),
    tiers=frozenset({'tier-1'}),
    admin_metadata_keys=frozenset(),
)


class Boom(Exception):
    pass


def load_json(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def artifact_request() -> dict[str, object]:
    return load_json(I_FIXTURE)['entities']['DeclareArtifactVersionRequest']['valid'][0]


def artifact_result() -> dict[str, object]:
    return load_json(I_FIXTURE)['entities']['DeclareArtifactVersionResult']['valid'][0]


def package_payload() -> dict[str, object]:
    return load_json(AB_FIXTURE)['entities']['CollectedDocumentPackage']['valid'][0]


def resolution() -> dict[str, object]:
    return load_json(AB_FIXTURE)['entities']['CollectedDocumentResolution']['valid'][0]


def make_source(
    source_id: str = 'src-1',
    workspace_id: str = 'ws-1',
    canonical_locator: str = LOCATOR,
):
    return register_source(
        source_id=source_id,
        workspace_id=workspace_id,
        canonical_locator=canonical_locator,
        name='Feed',
        source_kind='rss_feed',
        tier='tier-1',
        topics=('news',),
        notes='',
        collection_enabled=True,
        admin_metadata={},
        actor='tester',
        at=AT,
        policy=POLICY,
    )


def make_candidate(candidate_id: str = 'cand-1', workspace_id: str = 'ws-1'):
    return discover_candidate(
        candidate_id=candidate_id,
        workspace_id=workspace_id,
        observed_locator=LOCATOR + '?utm=1',
        canonical_locator=LOCATOR,
        discovery_method='link',
        discovery_evidence='evidence-1',
        actor='tester',
        at=AT,
    )


def make_run(
    run_id: str = 'run-1',
    purpose: CollectionPurpose = CollectionPurpose.PERIODIC,
    retry_revision: str = 'retry-r1',
    source_id: str = 'src-1',
):
    return schedule_run(
        run_id=run_id,
        workspace_id='ws-1',
        source_id=source_id,
        business_date=BUSINESS_DATE,
        purpose=purpose,
        retry_policy=RetryPolicy(retry_revision, 3),
    )


def make_package(fingerprint: str = 'sha256:obs-1', run_id: str = 'run-1') -> PackageRecord:
    return PackageRecord('src-1', 'https://example.test/a', fingerprint, run_id, {'k': 'v'})


def make_checkpoint(revision: int, item_ids: list[str]) -> CollectionCheckpoint:
    return seal_checkpoint(
        CollectionCheckpoint(
            checkpoint_version=1,
            revision=revision,
            source_id='src-1',
            source_revision=1,
            adapter_type='rss_feed',
            adapter_revision='adapter-r1',
            cursor=f'cursor-{revision}',
            item_ids=tuple(item_ids),
            run_id='run-1',
            attempt_id='attempt-1',
            execution_generation=1,
            completeness=CheckpointCompleteness.PARTIAL,
            recorded_at='2026-10-18T00:00:00Z',
            fingerprint='sha256:unsealed',
        )
    )


def make_receipt(key: str = 'idem-1') -> CommandReceipt:
    return CommandReceipt('ws-1', key, 'sha256:req-1', 'src-1', 1)


def make_grant(generation: int = 1) -> ExecutionGrant:
    return ExecutionGrant('ws-1', 'op-1', 'job-1', 'stage-1', generation, 0)


def make_handle() -> SecretHandle:
    return SecretHandle(
        'sh-1',
        'ws-1',
        'provider-1',
        'account-1',
        'alias-1',
        'v1',
        'VALID',
        None,
        None,
        'audit-1',
    )


class InterfaceReuseTests(unittest.TestCase):
    def test_memory_adapters_reuse_controlplane_interfaces(self) -> None:
        self.assertTrue(issubclass(InMemoryUnitOfWork, IUnitOfWork))
        self.assertTrue(issubclass(InMemoryOutboxWriter, IOutboxWriter))
        self.assertIsInstance(InMemoryUnitOfWork().outbox, IOutboxWriter)

    def test_no_duplicate_interfaces_or_shared_types_defined(self) -> None:
        target_files = (
            ROOT / 'src' / 'source_ingestion' / 'ports' / 'repositories.py',
            ROOT / 'src' / 'source_ingestion' / 'ports' / 'partners.py',
            ROOT / 'src' / 'source_ingestion' / 'adapters' / 'memory.py',
        )
        for path in target_files:
            tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
            names = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
            self.assertTrue(
                names.isdisjoint({'IUnitOfWork', 'IOutboxWriter', 'IRepository', 'DomainEvent', 'SecretHandle', 'ExecutionGrant'}),
                f'{path.name} defined duplicate/shared types: {names & {"IUnitOfWork", "IOutboxWriter", "IRepository", "DomainEvent", "SecretHandle", "ExecutionGrant"}}'
            )

    def test_memory_adapters_satisfy_ports(self) -> None:
        uow = InMemoryUnitOfWork()
        self.assertIsInstance(uow.sources, SourceRepository)
        self.assertIsInstance(uow.candidates, SourceCandidateRepository)
        self.assertIsInstance(uow.runs, CollectionRunRepository)
        self.assertIsInstance(uow.packages, PackageRepository)
        self.assertIsInstance(uow.checkpoints, CheckpointRepository)
        self.assertIsInstance(uow.receipts, ReceiptStore)
        self.assertIsInstance(FakeArtifactPort(artifact_result()), ArtifactPort)
        self.assertIsInstance(FakeContentHandoffPort(resolution()), ContentHandoffPort)
        self.assertIsInstance(FakeConfigPort(), ConfigPort)
        self.assertIsInstance(FakeActivityGrantPort(), ActivityGrantPort)


class UnitOfWorkTests(unittest.TestCase):
    def test_rollback_discards_every_write(self) -> None:
        uow = InMemoryUnitOfWork()
        uow.begin()
        uow.sources.add(make_source())
        uow.candidates.add(make_candidate())
        uow.runs.add(make_run())
        uow.packages.add(make_package())
        uow.checkpoints.advance(make_checkpoint(1, ['item-1']), ['item-1'])
        uow.receipts.put(make_receipt())
        uow.outbox.append_event('SourceRegistered', 'src-1', {'source_id': 'src-1'}, 'dedup-1')

        self.assertIsNotNone(uow.sources.get('ws-1', 'src-1'))
        self.assertIsNotNone(uow.candidates.get('ws-1', 'cand-1'))
        self.assertIsNotNone(uow.runs.get('run-1'))
        self.assertIsNotNone(uow.runs.get_periodic('ws-1', 'src-1', BUSINESS_DATE))
        self.assertIsNotNone(uow.packages.get('src-1', 'https://example.test/a', 'sha256:obs-1'))
        self.assertIsNotNone(uow.checkpoints.get_latest('src-1'))
        self.assertIsNotNone(uow.receipts.get('ws-1', 'idem-1'))
        self.assertEqual(len(uow.outbox.records()), 1)

        uow.rollback()

        self.assertIsNone(uow.sources.get('ws-1', 'src-1'))
        self.assertIsNone(uow.candidates.get('ws-1', 'cand-1'))
        self.assertIsNone(uow.runs.get('run-1'))
        self.assertIsNone(uow.runs.get_periodic('ws-1', 'src-1', BUSINESS_DATE))
        self.assertIsNone(uow.packages.get('src-1', 'https://example.test/a', 'sha256:obs-1'))
        self.assertIsNone(uow.checkpoints.get_latest('src-1'))
        self.assertIsNone(uow.receipts.get('ws-1', 'idem-1'))
        self.assertEqual(uow.outbox.records(), ())
        self.assertIs(uow.sources.resolve_identity('ws-1', LOCATOR).kind, IdentityMatchKind.NONE)
        self.assertFalse(uow.active)

    def test_exception_inside_context_discards_source_and_outbox(self) -> None:
        uow = InMemoryUnitOfWork()
        with self.assertRaises(Boom):
            with uow:
                uow.sources.add(make_source())
                uow.outbox.append_event('SourceRegistered', 'src-1', {'source_id': 'src-1'}, 'dedup-1')
                self.assertIsNotNone(uow.sources.get('ws-1', 'src-1'))
                raise Boom()

        self.assertIsNone(uow.sources.get('ws-1', 'src-1'))
        self.assertEqual(uow.outbox.records(), ())

    def test_leaving_context_without_commit_rolls_back(self) -> None:
        uow = InMemoryUnitOfWork()
        with uow:
            uow.sources.add(make_source())
        self.assertIsNone(uow.sources.get('ws-1', 'src-1'))

    def test_commit_persists_and_later_rollback_restores_committed_state(self) -> None:
        uow = InMemoryUnitOfWork()
        with uow:
            uow.sources.add(make_source())
            uow.commit()

        with uow:
            source = uow.sources.get('ws-1', 'src-1')
            assert source is not None
            removed = remove_source(source, expected_revision=1, actor='tester', at=AT)
            uow.sources.save(removed)
            uow.outbox.append_event('SourceRemoved', 'src-1', {}, 'dedup-2')
            stored = uow.sources.get('ws-1', 'src-1')
            assert stored is not None
            self.assertEqual(stored.revision, 2)
            uow.rollback()

        restored = uow.sources.get('ws-1', 'src-1')
        assert restored is not None
        self.assertEqual(restored.revision, 1)
        self.assertIs(restored.status, SourceStatus.ACTIVE)
        self.assertEqual(uow.outbox.records(), ())

    def test_writes_outside_unit_of_work_are_rejected(self) -> None:
        uow = InMemoryUnitOfWork()
        with self.assertRaises(TransactionNotActiveError):
            uow.sources.add(make_source())
        with self.assertRaises(TransactionNotActiveError):
            uow.outbox.append_event('SourceRegistered', 'src-1', {}, 'dedup-1')
        with self.assertRaises(TransactionNotActiveError):
            uow.receipts.put(make_receipt())
        with self.assertRaises(TransactionNotActiveError):
            uow.commit()
        with self.assertRaises(TransactionNotActiveError):
            uow.rollback()

    def test_begin_twice_is_rejected(self) -> None:
        uow = InMemoryUnitOfWork()
        uow.begin()
        with self.assertRaises(TransactionAlreadyActiveError):
            uow.begin()
        uow.rollback()


class OutboxTests(unittest.TestCase):
    def test_append_dedups_by_deduplication_id(self) -> None:
        uow = InMemoryUnitOfWork()
        with uow:
            first = uow.outbox.append_event('SourceRegistered', 'src-1', {'source_id': 'src-1'}, 'dedup-1')
            second = uow.outbox.append_event('SourceRegistered', 'src-1', {'source_id': 'other'}, 'dedup-1')
            third = uow.outbox.append_event('SourceRegistered', 'src-1', {'source_id': 'src-1'}, 'dedup-2')
            uow.commit()

        self.assertEqual(first, second)
        self.assertNotEqual(first, third)
        self.assertEqual(len(uow.outbox.records()), 2)
        self.assertIsInstance(uow.outbox.records()[0], OutboxRecord)
        self.assertEqual(uow.outbox.records()[0].payload, {'source_id': 'src-1'})

    def test_payload_is_read_only_copy(self) -> None:
        uow = InMemoryUnitOfWork()
        payload = {'a': 1}
        with uow:
            uow.outbox.append_event('SourceRegistered', 'src-1', payload, 'dedup-1')
            uow.commit()

        payload['a'] = 2
        record = uow.outbox.records()[0]
        self.assertEqual(record.payload['a'], 1)
        with self.assertRaises(TypeError):
            record.payload['b'] = 1  # type: ignore[index]

    def test_rejects_blank_deduplication_id(self) -> None:
        uow = InMemoryUnitOfWork()
        with uow:
            with self.assertRaises(ValueError):
                uow.outbox.append_event('SourceRegistered', 'src-1', {'source_id': 'src-1'}, '  ')
            uow.rollback()


class SourceRepositoryTests(unittest.TestCase):
    def test_identity_lookup_includes_tombstone(self) -> None:
        uow = InMemoryUnitOfWork()
        with uow:
            uow.sources.add(make_source())
            uow.commit()

        match = uow.sources.resolve_identity('ws-1', LOCATOR)
        self.assertIs(match.kind, IdentityMatchKind.EXISTING_SOURCE)
        self.assertEqual(match.ref, 'src-1')

        with uow:
            source = uow.sources.get('ws-1', 'src-1')
            assert source is not None
            removed = remove_source(source, expected_revision=1, actor='tester', at=AT)
            uow.sources.save(removed)
            uow.commit()

        match2 = uow.sources.resolve_identity('ws-1', LOCATOR)
        self.assertIs(match2.kind, IdentityMatchKind.TOMBSTONE)
        self.assertEqual(match2.ref, 'src-1')

        with uow:
            with self.assertRaises(DuplicateSourceIdentityError):
                uow.sources.add(make_source(source_id='src-2'))
            uow.rollback()

    def test_identity_is_scoped_by_workspace(self) -> None:
        uow = InMemoryUnitOfWork()
        with uow:
            uow.sources.add(make_source())
            uow.commit()

        self.assertIs(uow.sources.resolve_identity('ws-2', LOCATOR).kind, IdentityMatchKind.NONE)
        self.assertIsNone(uow.sources.get('ws-2', 'src-1'))

        with uow:
            uow.sources.add(make_source(source_id='src-9', workspace_id='ws-2'))
            uow.commit()

        self.assertEqual(len(uow.sources.list_sources('ws-2')), 1)

    def test_save_guards_revision_key_and_existence(self) -> None:
        uow = InMemoryUnitOfWork()
        with uow:
            uow.sources.add(make_source())
            uow.commit()

        source = uow.sources.get('ws-1', 'src-1')
        assert source is not None

        with uow:
            with self.assertRaises(RevisionConflictError):
                uow.sources.save(source)
            with self.assertRaises(ValueError):
                uow.sources.save(dataclasses.replace(source, revision=2, canonical_locator='https://example.test/other'))
            with self.assertRaises(RecordNotFoundError):
                uow.sources.save(make_source(source_id='src-x'))
            uow.rollback()


class CandidateRepositoryTests(unittest.TestCase):
    def test_candidate_add_find_and_revision_guard(self) -> None:
        uow = InMemoryUnitOfWork()
        with uow:
            uow.candidates.add(make_candidate())
            with self.assertRaises(DuplicateRecordError):
                uow.candidates.add(make_candidate())
            uow.commit()

        self.assertEqual(len(uow.candidates.find_by_canonical_locator('ws-1', LOCATOR)), 1)
        self.assertIsNone(uow.candidates.get('ws-2', 'cand-1'))

        cand = uow.candidates.get('ws-1', 'cand-1')
        assert cand is not None
        decision = begin_validation(cand, expected_revision=1, actor='tester', at=AT)

        with uow:
            uow.candidates.save(decision.candidate)
            uow.commit()

        cand2 = uow.candidates.get('ws-1', 'cand-1')
        assert cand2 is not None
        self.assertEqual(cand2.revision, 2)

        with uow:
            with self.assertRaises(RevisionConflictError):
                uow.candidates.save(cand)
            uow.rollback()


class CollectionRunRepositoryTests(unittest.TestCase):
    def test_two_periodic_runs_with_same_key_cannot_coexist(self) -> None:
        uow = InMemoryUnitOfWork()
        with uow:
            uow.runs.add(make_run('run-1'))
            uow.commit()

        with uow:
            with self.assertRaises(DuplicatePeriodicRunError):
                uow.runs.add(make_run('run-2', retry_revision='retry-r2'))
            uow.rollback()

        self.assertEqual(len(uow.runs.list_by_source('ws-1', 'src-1')), 1)
        periodic = uow.runs.get_periodic('ws-1', 'src-1', BUSINESS_DATE)
        assert periodic is not None
        self.assertEqual(periodic.run_id, 'run-1')

    def test_periodic_key_excludes_policy_revision_and_other_purposes(self) -> None:
        uow = InMemoryUnitOfWork()
        with uow:
            uow.runs.add(make_run('run-1'))
            uow.commit()

        with uow:
            uow.runs.add(make_run('test-1', purpose=CollectionPurpose.SOURCE_TEST))
            uow.runs.add(make_run('test-2', purpose=CollectionPurpose.SOURCE_TEST))
            with self.assertRaises(DuplicateRecordError):
                uow.runs.add(make_run('run-1'))
            uow.commit()

        self.assertEqual(len(uow.runs.list_by_source('ws-1', 'src-1')), 3)

    def test_save_updates_state_but_not_key(self) -> None:
        uow = InMemoryUnitOfWork()
        with uow:
            uow.runs.add(make_run())
            uow.commit()

        run = uow.runs.get('run-1')
        assert run is not None
        started = start_run(run, source_active=True, checkpoint_ref='cp-1')

        with uow:
            uow.runs.save(started)
            uow.commit()

        saved = uow.runs.get('run-1')
        assert saved is not None
        self.assertIs(saved.status, RunStatus.RUNNING)

        with uow:
            with self.assertRaises(ValueError):
                uow.runs.save(dataclasses.replace(started, business_date=datetime.date(2026, 10, 19)))
            with self.assertRaises(RecordNotFoundError):
                uow.runs.save(make_run('missing'))
            uow.rollback()


class PackageRepositoryTests(unittest.TestCase):
    def test_package_unique_by_source_locator_and_fingerprint(self) -> None:
        uow = InMemoryUnitOfWork()
        with uow:
            uow.packages.add(make_package())
            with self.assertRaises(DuplicatePackageError):
                uow.packages.add(make_package(run_id='run-2'))
            uow.packages.add(make_package(fingerprint='sha256:obs-2'))
            uow.commit()

        record = uow.packages.get('src-1', 'https://example.test/a', 'sha256:obs-1')
        assert record is not None
        self.assertEqual(record.collection_run_id, 'run-1')
        self.assertEqual(len(uow.packages.list_by_run('run-1')), 2)
        self.assertEqual(make_package().identity, ('src-1', 'https://example.test/a', 'sha256:obs-1'))

    def test_package_record_validates_and_freezes_payload(self) -> None:
        with self.assertRaises(ValueError):
            PackageRecord('', 'https://example.test/a', 'sha256:x', 'run-1', {})
        record = make_package()
        with self.assertRaises(TypeError):
            record.payload['k'] = 'z'  # type: ignore[index]


class CheckpointRepositoryTests(unittest.TestCase):
    def test_checkpoint_advances_only_over_durable_items(self) -> None:
        uow = InMemoryUnitOfWork()
        with uow:
            uow.checkpoints.advance(make_checkpoint(1, ['item-1']), ['item-1'])
            uow.commit()

        with uow:
            with self.assertRaises(CheckpointRejected):
                uow.checkpoints.advance(make_checkpoint(2, ['item-2']), ['item-1'])
            uow.rollback()

        latest = uow.checkpoints.get_latest('src-1')
        assert latest is not None
        self.assertEqual(latest.revision, 1)

        with uow:
            uow.checkpoints.advance(make_checkpoint(2, ['item-2']), ['item-1', 'item-2'])
            uow.commit()

        latest2 = uow.checkpoints.get_latest('src-1')
        assert latest2 is not None
        self.assertEqual(latest2.revision, 2)


class ReceiptStoreTests(unittest.TestCase):
    def test_receipt_unique_per_workspace_and_key(self) -> None:
        uow = InMemoryUnitOfWork()
        with uow:
            uow.receipts.put(make_receipt())
            with self.assertRaises(DuplicateReceiptError):
                uow.receipts.put(make_receipt())
            uow.commit()

        self.assertEqual(uow.receipts.get('ws-1', 'idem-1'), make_receipt())
        self.assertIsNone(uow.receipts.get('ws-2', 'idem-1'))

    def test_receipt_validates_fields(self) -> None:
        with self.assertRaises(ValueError):
            CommandReceipt('ws-1', 'idem-1', 'sha256:req-1', 'src-1', 0)
        with self.assertRaises(ValueError):
            CommandReceipt('ws-1', '', 'sha256:req-1', 'src-1', 1)


class ArtifactPortTests(unittest.TestCase):
    def test_field_tables_match_binding(self) -> None:
        binding = load_json(I_BINDING)
        by_name = {
            e['name']: tuple((f['name'], f['type'], f['required']) for f in e['fields'])
            for e in binding['entities']
        }
        self.assertEqual(by_name['DeclareArtifactVersionRequest'], DECLARE_ARTIFACT_VERSION_REQUEST_FIELDS)
        self.assertEqual(by_name['DeclareArtifactVersionResult'], DECLARE_ARTIFACT_VERSION_RESULT_FIELDS)
        self.assertEqual(binding['binding_version'], ARTIFACT_BINDING_VERSION)

    def test_fake_returns_payload_matching_fixture(self) -> None:
        port = FakeArtifactPort(artifact_result())
        result = port.declare_artifact_version(artifact_request())
        self.assertEqual(result, artifact_result())
        self.assertEqual(port.requests, [artifact_request()])
        self.assertIs(type(result['matched_existing']), bool)

    def test_fake_rejects_fixture_invalid_payloads(self) -> None:
        port = FakeArtifactPort(artifact_result())
        fixture = load_json(I_FIXTURE)['entities']
        for case in fixture['DeclareArtifactVersionRequest']['invalid']:
            with self.subTest(case=case['case']):
                with self.assertRaises(ValueError) as ctx:
                    port.declare_artifact_version(case['payload'])
                self.assertEqual(str(ctx.exception), f"{case['expected_error']['code']}:{case['expected_error']['field']}")
        for case in fixture['DeclareArtifactVersionResult']['invalid']:
            with self.subTest(case=case['case']):
                with self.assertRaises(ValueError) as ctx:
                    FakeArtifactPort(case['payload'])
                self.assertEqual(str(ctx.exception), f"{case['expected_error']['code']}:{case['expected_error']['field']}")
        self.assertEqual(port.requests, [])


class ContentHandoffPortTests(unittest.TestCase):
    def test_fake_hands_off_layer1_valid_package_only(self) -> None:
        port = FakeContentHandoffPort(resolution())
        self.assertEqual(port.resolve_collected_document(package_payload()), resolution())
        bad = dict(package_payload())
        del bad['source_id']
        self.assertRaises(PackageValidationError, port.resolve_collected_document, bad)
        self.assertEqual(len(port.submitted), 1)


class ConfigPortTests(unittest.TestCase):
    def test_config_port_contract_returns_handle_not_raw_secret(self) -> None:
        hints = typing.get_type_hints(ConfigPort.get_credential_handle)
        self.assertEqual(set(typing.get_args(hints['return'])), {SecretHandle, type(None)})
        self.assertEqual(sorted(n for n in vars(ConfigPort) if not n.startswith('_')), ['get_credential_handle', 'get_policy_revision'])

    def test_fake_config_port_refuses_raw_secret(self) -> None:
        self.assertRaises(TypeError, FakeConfigPort, credential_handles={('ws-1', 'src-1'): 'sk-live-raw-secret'})

    def test_fake_config_port_returns_refs(self) -> None:
        ref = PolicyRevisionRef('ws-1', 'extraction', 'extraction-r1')
        port = FakeConfigPort(policies=[ref], credential_handles={('ws-1', 'src-1'): make_handle()})
        self.assertEqual(port.get_policy_revision('ws-1', 'extraction'), ref)
        self.assertIsNone(port.get_policy_revision('ws-1', 'missing'))
        handle = port.get_credential_handle('ws-1', 'src-1')
        self.assertEqual(handle, make_handle())
        self.assertIsInstance(handle, SecretHandle)
        self.assertIsNone(port.get_credential_handle('ws-1', 'src-2'))
        self.assertRaises(ValueError, PolicyRevisionRef, 'ws-1', 'extraction', '')


class ActivityGrantPortTests(unittest.TestCase):
    def test_fake_grant_port_checks_current_grant(self) -> None:
        port = FakeActivityGrantPort([make_grant(2)])
        self.assertTrue(port.is_grant_current(make_grant(2)))
        self.assertFalse(port.is_grant_current(make_grant(1)))
        self.assertRaises(TypeError, FakeActivityGrantPort, ['grant-1'])
