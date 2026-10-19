"""A-09: command quản lý nguồn (RegisterSource, UpdateSourceMetadata, RemoveSource, RestoreSource).

coveredIds: A-RULE-001, A-RULE-002, A-RULE-003, A-RULE-014
"""
import ast
import dataclasses
import datetime
import itertools
import pathlib
import unittest

from controlplane.domain.concurrency import RevisionConflictError
from controlplane.domain.events import DomainEvent
from controlplane.domain.statemachine import ForbiddenTransitionError

from source_ingestion.adapters.memory import InMemoryUnitOfWork
from source_ingestion.application.source_commands import (
    COMMAND_REGISTER,
    COMMAND_UPDATE,
    COMMAND_REMOVE,
    COMMAND_RESTORE,
    EVENT_REGISTERED,
    EVENT_UPDATED,
    EVENT_REMOVED,
    EVENT_RESTORED,
    CommandResult,
    IdempotencyConflictError,
    SourceAlreadyRegisteredError,
    SourceCommandHandler,
    SourceNotFoundError,
    TombstoneConflictError,
)
from source_ingestion.domain.locator import (
    LocatorError,
    UnsafeDestinationError,
    UnsupportedSchemeError,
)
from source_ingestion.domain.source import (
    RESTORE_POLICY_DISALLOWED,
    SourcePolicy,
    SourceStatus,
)
from source_ingestion.domain.source_candidate import IdentityMatchKind
from source_ingestion.ports.repositories import PackageRecord

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'source_ingestion' / 'application' / 'source_commands.py'
AT = datetime.datetime(2026, 10, 18, tzinfo=datetime.timezone.utc)
LOCATOR = 'https://example.test/feed'
POLICY = SourcePolicy(
    policy_revision='policy-r1',
    source_kinds=frozenset({'rss_feed'}),
    tiers=frozenset({'tier-1', 'tier-2'}),
    admin_metadata_keys=frozenset({'owner'}),
)


class Boom(Exception):
    pass


class CommandTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.uow = InMemoryUnitOfWork()
        self.policy = [POLICY]
        ids = itertools.count(1)
        self.handler = SourceCommandHandler(
            uow=self.uow,
            policy_provider=lambda workspace_id: self.policy[0],
            resolver=lambda host: ['8.8.8.8'],
            recovery_epoch='epoch-0001',
            clock=lambda: AT,
            new_id=lambda: f'id-{next(ids)}',
        )

    def register(
        self,
        *,
        key: str = 'k-1',
        ws: str = 'ws-1',
        locator: str = LOCATOR,
        name: str = 'Feed',
        source_kind: str = 'rss_feed',
        tier: str = 'tier-1',
        topics: tuple[str, ...] = ('news',),
        notes: str = '',
        collection_enabled: bool = True,
        admin_metadata: dict[str, str] | None = None,
        **overrides: object,
    ) -> CommandResult:
        kwargs: dict[str, object] = {
            'workspace_id': ws,
            'idempotency_key': key,
            'actor': 'tester',
            'correlation_id': 'corr-1',
            'locator': locator,
            'name': name,
            'source_kind': source_kind,
            'tier': tier,
            'topics': topics,
            'notes': notes,
            'collection_enabled': collection_enabled,
            'admin_metadata': {} if admin_metadata is None else admin_metadata,
        }
        kwargs.update(overrides)
        result = self.handler.register_source(**kwargs)
        self.assertIsInstance(result, CommandResult)
        return result

    def update(
        self,
        source_id: str,
        expected_revision: object,
        *,
        key: str = 'k-1',
        ws: str = 'ws-1',
        **overrides: object,
    ) -> CommandResult:
        kwargs: dict[str, object] = {
            'workspace_id': ws,
            'idempotency_key': key,
            'actor': 'tester',
            'correlation_id': 'corr-1',
            'source_id': source_id,
            'expected_revision': expected_revision,
        }
        kwargs.update(overrides)
        result = self.handler.update_source_metadata(**kwargs)
        self.assertIsInstance(result, CommandResult)
        return result

    def remove(
        self,
        source_id: str,
        expected_revision: object,
        *,
        key: str = 'k-1',
        ws: str = 'ws-1',
        reason: str | None = None,
        **overrides: object,
    ) -> CommandResult:
        kwargs: dict[str, object] = {
            'workspace_id': ws,
            'idempotency_key': key,
            'actor': 'tester',
            'correlation_id': 'corr-1',
            'source_id': source_id,
            'expected_revision': expected_revision,
            'reason': reason,
        }
        kwargs.update(overrides)
        result = self.handler.remove_source(**kwargs)
        self.assertIsInstance(result, CommandResult)
        return result

    def restore(
        self,
        source_id: str,
        expected_revision: object,
        *,
        key: str = 'k-1',
        ws: str = 'ws-1',
        **overrides: object,
    ) -> CommandResult:
        kwargs: dict[str, object] = {
            'workspace_id': ws,
            'idempotency_key': key,
            'actor': 'tester',
            'correlation_id': 'corr-1',
            'source_id': source_id,
            'expected_revision': expected_revision,
        }
        kwargs.update(overrides)
        result = self.handler.restore_source(**kwargs)
        self.assertIsInstance(result, CommandResult)
        return result

    def stored(self, source_id: str, ws: str = 'ws-1'):
        return self.uow.sources.get(ws, source_id)


class RegisterSourceTests(CommandTestCase):
    def test_register_commits_source_receipt_and_event_together(self) -> None:
        res = self.register(locator='HTTPS://Example.Test:443/feed#frag')
        self.assertFalse(res.replayed)
        source_id = res.receipt.aggregate_ref
        source = self.stored(source_id)
        self.assertIsNotNone(source)
        self.assertEqual(source.canonical_locator, 'https://example.test/feed')
        self.assertEqual(source.revision, 1)
        self.assertEqual(source.status, SourceStatus.ACTIVE)
        receipt = res.receipt
        self.assertEqual(receipt.workspace_id, 'ws-1')
        self.assertEqual(receipt.idempotency_key, 'k-1')
        self.assertEqual(receipt.aggregate_revision, 1)
        self.assertEqual(len(receipt.request_hash), 64)
        self.assertEqual(receipt, self.uow.receipts.get('ws-1', 'k-1'))
        records = self.uow.outbox.records()
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.event_type, EVENT_REGISTERED)
        self.assertEqual(record.aggregate_id, source_id)
        self.assertTrue(bool(record.deduplication_id))
        envelope = record.payload
        self.assertEqual(envelope['event_name'], EVENT_REGISTERED)
        self.assertEqual(envelope['aggregate_type'], 'Source')
        self.assertEqual(envelope['aggregate_id'], source_id)
        self.assertEqual(envelope['aggregate_revision'], 1)
        self.assertEqual(envelope['producer'], 'A')
        self.assertEqual(envelope['schema_version'], '1.0.0')
        self.assertEqual(envelope['recovery_epoch'], 'epoch-0001')
        self.assertEqual(envelope['sensitivity'], 'internal')
        self.assertEqual(envelope['workspace_id'], 'ws-1')
        self.assertEqual(envelope['payload']['source_id'], source_id)
        self.assertEqual(set(envelope), {f.name for f in dataclasses.fields(DomainEvent)})
        self.assertFalse(self.uow.active)

    def test_same_key_and_payload_returns_original_receipt(self) -> None:
        first = self.register()
        second = self.register()
        self.assertTrue(second.replayed)
        self.assertEqual(second.receipt, first.receipt)
        self.assertEqual(len(self.uow.sources.list_sources('ws-1')), 1)
        self.assertEqual(len(self.uow.outbox.records()), 1)

    def test_same_key_with_different_payload_is_idempotency_conflict(self) -> None:
        first = self.register()
        with self.assertRaises(IdempotencyConflictError) as ctx:
            self.register(name='Other')
        self.assertEqual(ctx.exception.code, 'IDEMPOTENCY_CONFLICT')
        stored = self.stored(first.receipt.aggregate_ref)
        self.assertIsNotNone(stored)
        self.assertEqual(stored.name, 'Feed')
        self.assertEqual(len(self.uow.sources.list_sources('ws-1')), 1)
        self.assertEqual(len(self.uow.outbox.records()), 1)
        with self.assertRaises(IdempotencyConflictError) as ctx:
            self.remove(first.receipt.aggregate_ref, 1, key='k-1')
        self.assertEqual(ctx.exception.code, 'IDEMPOTENCY_CONFLICT')

    def test_same_locator_with_new_key_conflicts_with_existing_source(self) -> None:
        first = self.register()
        with self.assertRaises(SourceAlreadyRegisteredError) as ctx:
            self.register(key='k-2')
        self.assertEqual(ctx.exception.source_ref, first.receipt.aggregate_ref)
        self.assertEqual(len(self.uow.sources.list_sources('ws-1')), 1)
        self.assertEqual(len(self.uow.outbox.records()), 1)
        self.assertIsNone(self.uow.receipts.get('ws-1', 'k-2'))

    def test_atomic_rollback_when_outbox_write_fails(self) -> None:
        def fail_outbox(*args: object, **kwargs: object) -> None:
            raise Boom('outbox failed')

        self.uow.outbox.append_event = fail_outbox
        with self.assertRaises(Boom):
            self.register()
        self.assertEqual(self.uow.sources.list_sources('ws-1'), ())
        self.assertIsNone(self.uow.receipts.get('ws-1', 'k-1'))
        self.assertEqual(self.uow.outbox.records(), ())
        self.assertFalse(self.uow.active)

    def test_same_key_in_other_workspace_is_independent(self) -> None:
        a = self.register(ws='ws-1')
        b = self.register(ws='ws-2')
        self.assertNotEqual(a.receipt.aggregate_ref, b.receipt.aggregate_ref)
        self.assertIsNone(self.stored(a.receipt.aggregate_ref, ws='ws-2'))
        self.assertEqual(len(self.uow.sources.list_sources('ws-2')), 1)


class RegisterRejectionTests(CommandTestCase):
    def test_unsafe_locators_are_rejected_without_creating_source(self) -> None:
        table = (
            ('http://127.0.0.1/feed', UnsafeDestinationError),
            ('http://169.254.169.254/latest/meta', UnsafeDestinationError),
            ('http://localhost/feed', UnsafeDestinationError),
            ('http://10.0.0.5/feed', UnsafeDestinationError),
            ('ftp://example.test/feed', UnsupportedSchemeError),
            ('https://user:pw@example.test/feed', LocatorError),
        )
        for bad_locator, exc_type in table:
            with self.subTest(locator=bad_locator):
                with self.assertRaises(exc_type) as ctx:
                    self.register(locator=bad_locator)
                exc_str = str(ctx.exception)
                self.assertNotIn(bad_locator, exc_str)
                self.assertNotIn('pw', exc_str)
        self.assertEqual(self.uow.sources.list_sources('ws-1'), ())
        self.assertIsNone(self.uow.receipts.get('ws-1', 'k-1'))
        self.assertEqual(self.uow.outbox.records(), ())

        ids = itertools.count(100)
        custom_handler = SourceCommandHandler(
            uow=self.uow,
            policy_provider=lambda workspace_id: self.policy[0],
            resolver=lambda host: ['10.1.2.3'],
            recovery_epoch='epoch-0001',
            clock=lambda: AT,
            new_id=lambda: f'id-{next(ids)}',
        )
        with self.assertRaises(UnsafeDestinationError) as ctx:
            custom_handler.register_source(
                workspace_id='ws-1',
                idempotency_key='k-custom',
                actor='tester',
                correlation_id='corr-1',
                locator=LOCATOR,
                name='Feed',
                source_kind='rss_feed',
                tier='tier-1',
                topics=('news',),
                notes='',
                collection_enabled=True,
                admin_metadata={},
            )
        self.assertEqual(self.uow.sources.list_sources('ws-1'), ())

    def test_locator_matching_tombstone_conflicts_with_removed_source_ref(self) -> None:
        first = self.register()
        sid = first.receipt.aggregate_ref
        self.remove(sid, 1, key='k-rm')
        with self.assertRaises(TombstoneConflictError) as ctx:
            self.register(key='k-2', locator='https://EXAMPLE.test:443/feed#again')
        self.assertEqual(ctx.exception.source_ref, sid)
        self.assertEqual(ctx.exception.code, 'SOURCE_TOMBSTONED')
        stored = self.stored(sid)
        self.assertIsNotNone(stored)
        self.assertEqual(stored.status, SourceStatus.REMOVED_TOMBSTONE)
        self.assertEqual(len(self.uow.outbox.records()), 2)
        self.assertIsNone(self.uow.receipts.get('ws-1', 'k-2'))

    def test_policy_violations_are_rejected_without_side_effects(self) -> None:
        with self.assertRaises(ValueError):
            self.register(source_kind='unknown')
        with self.assertRaises(ValueError):
            self.register(tier='tier-9')
        with self.assertRaises(ValueError):
            self.register(topics=())
        with self.assertRaises(ValueError):
            self.register(admin_metadata={'bad_key': 'x'})
        self.assertEqual(self.uow.sources.list_sources('ws-1'), ())
        self.assertIsNone(self.uow.receipts.get('ws-1', 'k-1'))
        self.assertEqual(self.uow.outbox.records(), ())

    def test_blank_idempotency_key_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.register(key='  ')
        self.assertEqual(self.uow.sources.list_sources('ws-1'), ())
        self.assertIsNone(self.uow.receipts.get('ws-1', 'k-1'))
        self.assertEqual(self.uow.outbox.records(), ())


class UpdateSourceMetadataTests(CommandTestCase):
    def test_update_writes_new_revision_receipt_and_event(self) -> None:
        first = self.register()
        sid = first.receipt.aggregate_ref
        res = self.update(sid, 1, key='k-up', tier='tier-2', notes='new', topics=('news', 'tech'))
        source = self.stored(sid)
        self.assertIsNotNone(source)
        self.assertEqual(source.revision, 2)
        self.assertEqual(source.tier, 'tier-2')
        self.assertEqual(source.notes, 'new')
        self.assertEqual(source.topics, frozenset({'news', 'tech'}))
        self.assertEqual(res.receipt.aggregate_revision, 2)
        self.assertEqual(res.receipt.aggregate_ref, sid)
        records = self.uow.outbox.records()
        self.assertEqual(len(records), 2)
        envelope = records[-1].payload
        self.assertEqual(records[-1].event_type, EVENT_UPDATED)
        self.assertEqual(envelope['aggregate_revision'], 2)
        self.assertEqual(envelope['payload']['revision'], 2)
        self.assertEqual(envelope['payload']['changed_fields'], ['notes', 'tier', 'topics'])

    def test_update_replay_returns_old_receipt_after_revision_moved(self) -> None:
        first = self.register()
        sid = first.receipt.aggregate_ref
        res1 = self.update(sid, 1, key='k-up', notes='n1')
        res2 = self.update(sid, 1, key='k-up', notes='n1')
        self.assertTrue(res2.replayed)
        self.assertEqual(res2.receipt, res1.receipt)
        source = self.stored(sid)
        self.assertIsNotNone(source)
        self.assertEqual(source.revision, 2)
        self.assertEqual(len(self.uow.outbox.records()), 2)

    def test_second_tab_with_stale_revision_cannot_overwrite(self) -> None:
        first = self.register()
        sid = first.receipt.aggregate_ref
        self.update(sid, 1, key='k-a', notes='tab-a')
        with self.assertRaises(RevisionConflictError) as ctx:
            self.update(sid, 1, key='k-b', notes='tab-b')
        self.assertEqual(ctx.exception.current_revision, 2)
        source = self.stored(sid)
        self.assertIsNotNone(source)
        self.assertEqual(source.notes, 'tab-a')
        self.assertEqual(source.revision, 2)
        self.assertIsNone(self.uow.receipts.get('ws-1', 'k-b'))
        self.assertEqual(len(self.uow.outbox.records()), 2)

    def test_update_rejects_empty_change_and_non_int_revision(self) -> None:
        first = self.register()
        sid = first.receipt.aggregate_ref
        with self.assertRaises(ValueError):
            self.update(sid, 1, key='k-x')
        with self.assertRaises(ValueError):
            self.update(sid, True, key='k-y', notes='x')
        source = self.stored(sid)
        self.assertIsNotNone(source)
        self.assertEqual(source.revision, 1)
        self.assertEqual(len(self.uow.outbox.records()), 1)

    def test_other_workspace_cannot_see_or_change_source(self) -> None:
        first = self.register(ws='ws-1')
        sid = first.receipt.aggregate_ref
        with self.assertRaises(SourceNotFoundError):
            self.update(sid, 1, ws='ws-2', notes='x')
        with self.assertRaises(SourceNotFoundError):
            self.remove(sid, 1, ws='ws-2')
        with self.assertRaises(SourceNotFoundError):
            self.restore(sid, 1, ws='ws-2')
        self.assertIsNone(self.stored(sid, ws='ws-2'))
        self.assertEqual(self.uow.sources.list_sources('ws-2'), ())
        source = self.stored(sid, ws='ws-1')
        self.assertIsNotNone(source)
        self.assertEqual(source.revision, 1)
        self.assertEqual(len(self.uow.outbox.records()), 1)

    def test_update_of_tombstone_is_forbidden(self) -> None:
        first = self.register()
        sid = first.receipt.aggregate_ref
        self.remove(sid, 1, key='k-rm')
        with self.assertRaises(ForbiddenTransitionError):
            self.update(sid, 2, key='k-up', notes='x')
        source = self.stored(sid)
        self.assertIsNotNone(source)
        self.assertEqual(source.revision, 2)

    def test_collection_enabled_toggles_status(self) -> None:
        first = self.register()
        sid = first.receipt.aggregate_ref
        res1 = self.update(sid, 1, key='k-off', collection_enabled=False)
        source1 = self.stored(sid)
        self.assertIsNotNone(source1)
        self.assertEqual(source1.status, SourceStatus.DISABLED)
        envelope1 = self.uow.outbox.records()[-1].payload
        self.assertEqual(envelope1['payload']['changed_fields'], ['status'])
        res2 = self.update(sid, 2, key='k-on', collection_enabled=True)
        source2 = self.stored(sid)
        self.assertIsNotNone(source2)
        self.assertEqual(source2.status, SourceStatus.ACTIVE)

    def test_update_rolls_back_when_outbox_write_fails(self) -> None:
        first = self.register()
        sid = first.receipt.aggregate_ref

        def fail_outbox(*args: object, **kwargs: object) -> None:
            raise Boom('outbox failed')

        self.uow.outbox.append_event = fail_outbox
        with self.assertRaises(Boom):
            self.update(sid, 1, key='k-up', notes='x')
        source = self.stored(sid)
        self.assertIsNotNone(source)
        self.assertEqual(source.revision, 1)
        self.assertEqual(source.notes, '')
        self.assertIsNone(self.uow.receipts.get('ws-1', 'k-up'))


class RemoveRestoreTests(CommandTestCase):
    def test_remove_tombstones_source_and_keeps_stored_package(self) -> None:
        first = self.register()
        sid = first.receipt.aggregate_ref
        source = self.stored(sid)
        self.assertIsNotNone(source)
        canonical = source.canonical_locator
        with self.uow:
            self.uow.packages.add(PackageRecord(sid, canonical, 'fp-1', 'run-1', {'title': 't'}))
            self.uow.commit()
        res = self.remove(sid, 1, key='k-rm', reason='no longer trusted')
        updated = self.stored(sid)
        self.assertIsNotNone(updated)
        self.assertEqual(updated.status, SourceStatus.REMOVED_TOMBSTONE)
        self.assertEqual(updated.previous_status, SourceStatus.ACTIVE)
        self.assertEqual(updated.revision, 2)
        self.assertEqual(res.receipt.aggregate_revision, 2)
        self.assertIsNotNone(self.uow.packages.get(sid, canonical, 'fp-1'))
        self.assertEqual(len(self.uow.packages.list_by_run('run-1')), 1)
        self.assertIn(sid, [s.source_id for s in self.uow.sources.list_sources('ws-1')])
        identity = self.uow.sources.resolve_identity('ws-1', canonical)
        self.assertEqual(identity.kind, IdentityMatchKind.TOMBSTONE)
        self.assertEqual(identity.ref, sid)
        record = self.uow.outbox.records()[-1]
        self.assertEqual(record.event_type, EVENT_REMOVED)
        envelope = record.payload
        self.assertEqual(envelope['payload']['previous_status'], 'ACTIVE')
        self.assertEqual(envelope['payload']['status'], 'REMOVED_TOMBSTONE')
        self.assertNotIn('no longer trusted', repr(self.uow.outbox.records()))

    def test_remove_replay_double_remove_and_stale_revision(self) -> None:
        first = self.register()
        sid = first.receipt.aggregate_ref
        res1 = self.remove(sid, 1, key='k-rm')
        res2 = self.remove(sid, 1, key='k-rm')
        self.assertTrue(res2.replayed)
        self.assertEqual(len(self.uow.outbox.records()), 2)
        with self.assertRaises(ForbiddenTransitionError):
            self.remove(sid, 2, key='k-rm2')
        second = self.register(key='k-2', locator='https://example.test/other')
        sid2 = second.receipt.aggregate_ref
        with self.assertRaises(RevisionConflictError) as ctx:
            self.remove(sid2, 5, key='k-bad')
        self.assertEqual(ctx.exception.current_revision, 1)

    def test_restore_returns_previous_status_and_emits_event(self) -> None:
        first = self.register()
        sid = first.receipt.aggregate_ref
        self.remove(sid, 1, key='k-rm')
        res = self.restore(sid, 2, key='k-rs')
        source = self.stored(sid)
        self.assertIsNotNone(source)
        self.assertEqual(source.status, SourceStatus.ACTIVE)
        self.assertIsNone(source.previous_status)
        self.assertEqual(source.revision, 3)
        self.assertEqual(res.receipt.aggregate_revision, 3)
        record = self.uow.outbox.records()[-1]
        self.assertEqual(record.event_type, EVENT_RESTORED)
        envelope = record.payload
        self.assertEqual(envelope['payload']['status'], 'ACTIVE')
        self.assertIsNone(envelope['payload']['status_reason'])
        res2 = self.restore(sid, 2, key='k-rs')
        self.assertTrue(res2.replayed)
        self.assertEqual(len(self.uow.outbox.records()), 3)

    def test_restore_under_policy_that_no_longer_allows_source_is_disabled(self) -> None:
        first = self.register()
        sid = first.receipt.aggregate_ref
        self.remove(sid, 1, key='k-rm')
        self.policy[0] = SourcePolicy('policy-r2', frozenset({'rss_feed'}), frozenset({'tier-2'}), frozenset())
        self.restore(sid, 2, key='k-rs')
        source = self.stored(sid)
        self.assertIsNotNone(source)
        self.assertEqual(source.status, SourceStatus.DISABLED)
        self.assertEqual(source.status_reason, RESTORE_POLICY_DISALLOWED)
        envelope = self.uow.outbox.records()[-1].payload
        self.assertEqual(envelope['payload']['status_reason'], RESTORE_POLICY_DISALLOWED)
        self.assertEqual(envelope['payload']['policy_revision'], 'policy-r2')

    def test_restore_of_active_source_is_forbidden(self) -> None:
        first = self.register()
        sid = first.receipt.aggregate_ref
        with self.assertRaises(ForbiddenTransitionError):
            self.restore(sid, 1, key='k-rs')
        source = self.stored(sid)
        self.assertIsNotNone(source)
        self.assertEqual(source.revision, 1)

    def test_restored_source_keeps_locator_identity(self) -> None:
        first = self.register()
        sid = first.receipt.aggregate_ref
        self.remove(sid, 1, key='k-rm')
        self.restore(sid, 2, key='k-rs')
        with self.assertRaises(SourceAlreadyRegisteredError) as ctx:
            self.register(key='k-2')
        self.assertEqual(ctx.exception.source_ref, sid)


class EventSafetyTests(CommandTestCase):
    def test_events_and_receipts_never_contain_locator_or_secret(self) -> None:
        secret_locator = 'https://example.test/feed?token=abc123&secret=xyz789'
        reg = self.register(locator=secret_locator, notes='api token: abc123')
        sid = reg.receipt.aggregate_ref
        self.update(sid, 1, key='k-up', notes='secret=xyz789')
        self.remove(sid, 2, key='k-rm', reason='token=abc123')
        self.restore(sid, 3, key='k-rs')
        text = repr(self.uow.outbox.records()) + repr(self.uow.receipts.get('ws-1', 'k-1')) + repr(self.uow.receipts.get('ws-1', 'k-rs'))
        for secret in ('abc123', 'xyz789', 'token', 'secret', 'example.test'):
            with self.subTest(secret=secret):
                self.assertNotIn(secret, text)
        records = self.uow.outbox.records()
        self.assertEqual(len(records), 4)
        self.assertEqual([r.event_type for r in records], [EVENT_REGISTERED, EVENT_UPDATED, EVENT_REMOVED, EVENT_RESTORED])

    def test_register_event_payload_has_identifiers_only(self) -> None:
        self.register()
        envelope = self.uow.outbox.records()[-1].payload
        self.assertEqual(set(envelope['payload']), {'source_id', 'revision', 'status', 'source_kind', 'tier', 'policy_revision'})

    def test_module_reuses_controlplane_types_and_respects_layers(self) -> None:
        tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'))
        class_names = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
        forbidden = {'IUnitOfWork', 'IOutboxWriter', 'IRepository', 'DomainEvent', 'SecretHandle', 'ExecutionGrant', 'CommandReceipt'}
        self.assertEqual(class_names & forbidden, set())

        has_domain_event = any(
            isinstance(node, ast.ImportFrom)
            and node.module == 'controlplane.domain.events'
            and any(alias.name == 'DomainEvent' for alias in node.names)
            for node in ast.walk(tree)
        )
        self.assertTrue(has_domain_event)

        forbidden_prefixes = ('src.', 'psycopg', 'controlplane.infrastructure', 'source_ingestion.adapters')
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotEqual(alias.name, 'src')
                    for p in forbidden_prefixes:
                        self.assertFalse(alias.name.startswith(p))
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                mod = node.module or ''
                self.assertNotEqual(mod, 'src')
                for p in forbidden_prefixes:
                    self.assertFalse(mod.startswith(p))

    def test_command_and_event_names_are_stable(self) -> None:
        self.assertEqual(
            (COMMAND_REGISTER, COMMAND_UPDATE, COMMAND_REMOVE, COMMAND_RESTORE),
            ('RegisterSource', 'UpdateSourceMetadata', 'RemoveSource', 'RestoreSource'),
        )
        self.assertEqual(
            (EVENT_REGISTERED, EVENT_UPDATED, EVENT_REMOVED, EVENT_RESTORED),
            ('SourceRegistered', 'SourceMetadataUpdated', 'SourceRemoved', 'SourceRestored'),
        )
