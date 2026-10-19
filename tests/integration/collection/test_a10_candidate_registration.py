"""A-10: ??ng k? SourceCandidate v? race register/remove (CT-SRC-003A, CT-STATE-002A).

coveredIds: TST-SRC-RACE-001..004 (TST-SRC-RACE-001, TST-SRC-RACE-002, TST-SRC-RACE-003, TST-SRC-RACE-004), TST-INT-INV-015, A-RULE-002
"""
import ast
import dataclasses
import datetime
import itertools
import pathlib
import unittest

from controlplane.domain.events import DomainEvent

from source_ingestion.adapters.memory import InMemoryUnitOfWork
from source_ingestion.application.candidate_registration import (
    AUTO_REGISTRATION_NOT_READY,
    AUTO_REGISTRATION_READY,
    EVENT_DISCOVERED,
    EVENT_RESOLVED,
    CandidateCommandResult,
    CandidateNotFoundError,
    CandidateRegistrationHandler,
    PolicyRevisionMismatchError,
)
from source_ingestion.application.source_commands import (
    EVENT_REGISTERED,
    IdempotencyConflictError,
    SourceAlreadyRegisteredError,
    SourceCommandHandler,
)
from source_ingestion.domain.locator import LocatorError
from source_ingestion.domain.source import SourcePolicy, SourceStatus
from source_ingestion.domain.source_candidate import (
    CandidateStatus as S,
    CandidateTransitionError,
    IdentityMatchKind,
    RegistrationPolicy,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'source_ingestion' / 'application' / 'candidate_registration.py'
AT = datetime.datetime(2026, 10, 19, tzinfo=datetime.timezone.utc)
LOCATOR = 'https://news.example.com/feed'
FULL = RegistrationPolicy(
    revision='tier-r1', auto_registration_enabled=True, permitted=True,
    source_kind='news_site', topics=('economy',), tier='TIER_2',
)
SOURCE_POLICY = SourcePolicy('src-r1', frozenset({'news_site'}), frozenset({'TIER_2'}), frozenset())


class Boom(Exception):
    pass


class CandidateTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.uow = InMemoryUnitOfWork()
        self.policy = [FULL]
        ids = itertools.count(1)
        new_id = lambda: f'id-{next(ids)}'
        self.handler = CandidateRegistrationHandler(
            uow=self.uow, resolver=lambda host: ['8.8.8.8'], recovery_epoch='epoch-0001',
            policy_provider=lambda ws: self.policy[0], clock=lambda: AT, new_id=new_id,
        )
        self.sources = SourceCommandHandler(
            uow=self.uow, policy_provider=lambda ws: SOURCE_POLICY, resolver=lambda host: ['8.8.8.8'],
            recovery_epoch='epoch-0001', clock=lambda: AT, new_id=new_id,
        )

    def evaluate(self, *, key='e-1', ws='ws-1', locator=LOCATOR, evidence='doc-42', policy_revision='tier-r1', **overrides):
        kwargs = dict(
            workspace_id=ws, idempotency_key=key, actor='discovery', correlation_id='corr-1',
            observed_locator=locator, discovery_method='outlink', discovery_evidence=evidence,
            policy_revision=policy_revision, source_kind_candidates=('news_site',), topic_candidates=('economy',),
        )
        kwargs.update(overrides)
        result = self.handler.evaluate_source_candidate(**kwargs)
        self.assertIsInstance(result, CandidateCommandResult)
        return result

    def register(self, candidate_id, expected_revision, *, key='r-1', ws='ws-1', policy_revision='tier-r1', **overrides):
        kwargs = dict(
            workspace_id=ws, idempotency_key=key, actor='registrar', correlation_id='corr-1',
            candidate_id=candidate_id, expected_revision=expected_revision, policy_revision=policy_revision,
        )
        kwargs.update(overrides)
        result = self.handler.register_source_candidate(**kwargs)
        self.assertIsInstance(result, CandidateCommandResult)
        return result

    def ready(self, *, key='e-1', locator=LOCATOR):
        res = self.evaluate(key=key, locator=locator)
        self.assertEqual(res.code, 'READY_FOR_REGISTRATION')
        return res

    def add_source(self, *, key='s-1', locator=LOCATOR, enabled=True) -> str:
        res = self.sources.register_source(
            workspace_id='ws-1', idempotency_key=key, actor='admin', correlation_id='corr-2', locator=locator,
            name='Feed', source_kind='news_site', tier='TIER_2', topics=('economy',), collection_enabled=enabled,
        )
        return res.receipt.aggregate_ref

    def remove_source(self, source_id, revision, *, key='s-rm') -> None:
        self.sources.remove_source(
            workspace_id='ws-1', idempotency_key=key, actor='admin', correlation_id='corr-2',
            source_id=source_id, expected_revision=revision,
        )

    def events(self) -> list:
        return [r.event_type for r in self.uow.outbox.records()]

    def candidate(self, candidate_id, ws='ws-1'):
        return self.uow.candidates.get(ws, candidate_id)


class EvaluateTests(CandidateTestCase):
    def test_new_locator_becomes_ready_with_receipt_and_discovered_event(self) -> None:
        res = self.evaluate(locator='HTTPS://News.Example.com:443/feed#top')
        cand = self.candidate(res.candidate.candidate_id)
        self.assertEqual((res.code, res.replayed, res.current_revision), ('READY_FOR_REGISTRATION', False, 3))
        self.assertEqual((cand.status, cand.revision, cand.canonical_locator), (S.READY_FOR_REGISTRATION, 3, LOCATOR))
        self.assertEqual((cand.source_kind, cand.tier, cand.topics), (None, None, ()))
        self.assertEqual(res.receipt, self.uow.receipts.get('ws-1', 'e-1'))
        self.assertEqual((res.receipt.aggregate_ref, res.receipt.aggregate_revision), (cand.candidate_id, 3))
        self.assertEqual(self.events(), [EVENT_DISCOVERED])
        self.assertEqual(self.uow.sources.list_sources('ws-1'), ())
        self.assertFalse(self.uow.active)

    def test_existing_source_resolves_to_matched_existing(self) -> None:
        for i, enabled in enumerate((True, False)):
            locator = f'https://s{i}.example.com/feed'
            with self.subTest(enabled=enabled):
                sid = self.add_source(key=f's-{i}', locator=locator, enabled=enabled)
                res = self.evaluate(key=f'e-{i}', locator=locator)
                self.assertEqual((res.code, res.source_ref, res.tombstone_ref), ('MATCHED_EXISTING', sid, None))
                self.assertEqual(self.events()[-2:], [EVENT_DISCOVERED, EVENT_RESOLVED])
        self.assertEqual(len(self.uow.sources.list_sources('ws-1')), 2)

    def test_inv_015_rediscovery_of_removed_source_is_blocked(self) -> None:
        sid = self.add_source()
        self.remove_source(sid, 1)
        res = self.evaluate(key='e-2', locator='https://NEWS.example.com:443/feed#again')
        self.assertEqual((res.code, res.tombstone_ref, res.source_ref), ('BLOCKED_TOMBSTONE', sid, None))
        self.assertEqual([s.status for s in self.uow.sources.list_sources('ws-1')], [SourceStatus.REMOVED_TOMBSTONE])
        self.assertEqual(self.events()[-2:], [EVENT_DISCOVERED, EVENT_RESOLVED])
        resolved = self.uow.outbox.records()[-1].payload['payload']
        self.assertEqual((resolved['disposition'], resolved['tombstone_ref']), ('BLOCKED_TOMBSTONE', sid))

    def test_replay_returns_same_receipt_and_changed_payload_conflicts(self) -> None:
        first = self.evaluate()
        again = self.evaluate()
        self.assertTrue(again.replayed)
        self.assertEqual(again.receipt, first.receipt)
        self.assertEqual(again.candidate.candidate_id, first.candidate.candidate_id)
        self.assertEqual(len(self.uow.candidates.find_by_canonical_locator('ws-1', LOCATOR)), 1)
        self.assertEqual(self.events(), [EVENT_DISCOVERED])
        with self.assertRaises(IdempotencyConflictError):
            self.evaluate(evidence='doc-43')

    def test_bad_input_and_policy_revision_mismatch_leave_no_state(self) -> None:
        for bad in ('http://127.0.0.1/feed', 'ftp://news.example.com/feed'):
            with self.subTest(locator=bad):
                with self.assertRaises(LocatorError):
                    self.evaluate(key='e-bad', locator=bad)
        self.policy[0] = dataclasses.replace(FULL, revision='tier-r2')
        with self.assertRaises(PolicyRevisionMismatchError):
            self.evaluate(key='e-pol')
        self.assertEqual(self.uow.candidates.find_by_canonical_locator('ws-1', LOCATOR), ())
        self.assertIsNone(self.uow.receipts.get('ws-1', 'e-bad'))
        self.assertIsNone(self.uow.receipts.get('ws-1', 'e-pol'))
        self.assertEqual(self.uow.outbox.records(), ())


class RaceExistingSourceTests(CandidateTestCase):
    def test_race_001_source_registered_first_matches_existing(self) -> None:
        for i, enabled in enumerate((True, False)):
            locator = f'https://s{i}.example.com/feed'
            with self.subTest(enabled=enabled):
                ready = self.ready(key=f'e-{i}', locator=locator).candidate
                sid = self.add_source(key=f's-{i}', locator=locator, enabled=enabled)
                res = self.register(ready.candidate_id, ready.revision, key=f'r-{i}')
                self.assertEqual((res.code, res.source_ref, res.tombstone_ref), ('MATCHED_EXISTING', sid, None))
                self.assertEqual(res.current_revision, ready.revision + 1)
                self.assertEqual(self.candidate(ready.candidate_id).matched_source_ref, sid)
                self.assertEqual(res.receipt, self.uow.receipts.get('ws-1', f'r-{i}'))
                self.assertEqual(self.events()[-1], EVENT_RESOLVED)
        self.assertEqual(len(self.uow.sources.list_sources('ws-1')), 2)

    def test_two_ready_candidates_for_same_locator_create_one_source(self) -> None:
        first = self.ready(key='e-1').candidate
        second = self.ready(key='e-2').candidate
        a = self.register(first.candidate_id, first.revision, key='r-1')
        b = self.register(second.candidate_id, second.revision, key='r-2')
        self.assertEqual((a.code, b.code), ('REGISTERED', 'MATCHED_EXISTING'))
        self.assertEqual(b.source_ref, a.source_ref)
        self.assertEqual(len(self.uow.sources.list_sources('ws-1')), 1)


class RaceRemoveTests(CandidateTestCase):
    def test_race_002_register_wins_then_remove_keeps_tombstone(self) -> None:
        ready = self.ready().candidate
        res = self.register(ready.candidate_id, ready.revision)
        sid = res.source_ref
        self.assertEqual(res.code, 'REGISTERED')
        self.assertEqual(self.uow.sources.get('ws-1', sid).status, SourceStatus.ACTIVE)
        with self.assertRaises(SourceAlreadyRegisteredError) as ctx:
            self.add_source(key='s-dup')
        self.assertEqual(ctx.exception.source_ref, sid)
        self.remove_source(sid, 1)
        self.assertEqual(self.uow.sources.resolve_identity('ws-1', LOCATOR).kind, IdentityMatchKind.TOMBSTONE)
        self.assertEqual(self.candidate(ready.candidate_id).status, S.REGISTERED)
        blocked = self.evaluate(key='e-2')
        self.assertEqual((blocked.code, blocked.tombstone_ref), ('BLOCKED_TOMBSTONE', sid))
        self.assertEqual(len(self.uow.sources.list_sources('ws-1')), 1)

    def test_race_002_remove_wins_blocks_registration_and_terminal_stays_closed(self) -> None:
        ready = self.ready().candidate
        sid = self.add_source()
        self.remove_source(sid, 1)
        res = self.register(ready.candidate_id, ready.revision)
        self.assertEqual((res.code, res.tombstone_ref, res.source_ref), ('BLOCKED_TOMBSTONE', sid, None))
        self.assertEqual(self.uow.sources.get('ws-1', sid).status, SourceStatus.REMOVED_TOMBSTONE)
        self.sources.restore_source(
            workspace_id='ws-1', idempotency_key='s-rs', actor='admin', correlation_id='corr-2',
            source_id=sid, expected_revision=2,
        )
        with self.assertRaises(CandidateTransitionError):
            self.register(ready.candidate_id, res.current_revision, key='r-2')
        self.assertEqual(self.candidate(ready.candidate_id).status, S.BLOCKED_TOMBSTONE)
        self.assertEqual(len(self.uow.sources.list_sources('ws-1')), 1)


class PolicyWaitingTests(CandidateTestCase):
    def test_race_003_missing_policy_waits_without_receipt_or_resolved(self) -> None:
        ready = self.ready().candidate
        self.policy[0] = None
        before = self.events()
        res = self.register(ready.candidate_id, ready.revision)
        self.assertEqual((res.code, res.receipt, res.replayed), ('WAITING_POLICY', None, False))
        cand = self.candidate(ready.candidate_id)
        self.assertEqual((cand.status, cand.revision), (S.READY_FOR_REGISTRATION, ready.revision))
        self.assertEqual(self.events(), before)
        self.assertEqual(self.uow.sources.list_sources('ws-1'), ())
        self.assertIsNone(self.uow.receipts.get('ws-1', 'r-1'))
        self.policy[0] = FULL
        self.assertEqual(self.register(ready.candidate_id, ready.revision).code, 'REGISTERED')

    def test_race_003_incomplete_policies_never_register(self) -> None:
        ready = self.ready().candidate
        table = (
            ('disabled', dataclasses.replace(FULL, auto_registration_enabled=False)),
            ('no_tier', dataclasses.replace(FULL, tier=None)),
            ('no_kind', dataclasses.replace(FULL, source_kind=None)),
            ('no_topics', dataclasses.replace(FULL, topics=())),
        )
        for name, policy in table:
            with self.subTest(policy=name):
                self.policy[0] = policy
                self.assertEqual(self.handler.readiness('ws-1'), AUTO_REGISTRATION_NOT_READY)
                res = self.register(ready.candidate_id, ready.revision, key=f'r-{name}')
                self.assertEqual(res.code, 'WAITING_POLICY')
        self.assertEqual(self.uow.sources.list_sources('ws-1'), ())
        self.assertNotIn(EVENT_RESOLVED, self.events())
        self.assertEqual(self.candidate(ready.candidate_id).status, S.READY_FOR_REGISTRATION)

    def test_race_003_forbidding_policy_rejects_without_source(self) -> None:
        ready = self.ready().candidate
        self.policy[0] = dataclasses.replace(FULL, permitted=False, reason='token=abc123 internal note')
        res = self.register(ready.candidate_id, ready.revision)
        self.assertEqual(res.code, 'REJECTED')
        self.assertEqual(self.candidate(ready.candidate_id).status, S.REJECTED)
        self.assertEqual(self.uow.sources.list_sources('ws-1'), ())
        payload = self.uow.outbox.records()[-1].payload['payload']
        self.assertEqual((self.events()[-1], payload['disposition'], payload['reason']), (EVENT_RESOLVED, 'REJECTED', 'POLICY_FORBIDS'))
        self.assertNotIn('abc123', repr(self.uow.outbox.records()))


class PolicyRevisionTests(CandidateTestCase):
    def test_race_003_stale_revision_conflict_changes_nothing(self) -> None:
        ready = self.ready().candidate
        before = self.events()
        res = self.register(ready.candidate_id, ready.revision - 1)
        self.assertEqual((res.code, res.current_revision, res.receipt), ('REVISION_CONFLICT', ready.revision, None))
        self.assertEqual(self.candidate(ready.candidate_id), ready)
        self.assertEqual(self.events(), before)
        self.assertEqual(self.uow.sources.list_sources('ws-1'), ())
        self.assertIsNone(self.uow.receipts.get('ws-1', 'r-1'))

    def test_changed_policy_revision_is_not_silently_replaced(self) -> None:
        ready = self.ready().candidate
        self.policy[0] = dataclasses.replace(FULL, revision='tier-r2')
        with self.assertRaises(PolicyRevisionMismatchError):
            self.register(ready.candidate_id, ready.revision, policy_revision='tier-r1')
        self.assertEqual(self.candidate(ready.candidate_id), ready)
        self.assertEqual(self.uow.sources.list_sources('ws-1'), ())
        res = self.register(ready.candidate_id, ready.revision, key='r-2', policy_revision='tier-r2')
        self.assertEqual(res.code, 'REGISTERED')
        self.assertEqual(self.candidate(ready.candidate_id).policy_revision, 'tier-r2')

    def test_registered_source_uses_policy_classification(self) -> None:
        ready = self.ready().candidate
        res = self.register(ready.candidate_id, ready.revision)
        source = self.uow.sources.get('ws-1', res.source_ref)
        self.assertEqual(
            (source.source_kind, source.tier, source.topics, source.policy_revision, source.status),
            ('news_site', 'TIER_2', frozenset({'economy'}), 'tier-r1', SourceStatus.ACTIVE),
        )
        cand = self.candidate(ready.candidate_id)
        self.assertEqual((cand.status, cand.tier, cand.registered_source_ref), (S.REGISTERED, 'TIER_2', source.source_id))
        self.assertEqual(self.events(), [EVENT_DISCOVERED, EVENT_REGISTERED, EVENT_RESOLVED])

    def test_production_default_keeps_auto_registration_not_ready(self) -> None:
        ids = itertools.count(100)
        prod = CandidateRegistrationHandler(
            uow=self.uow, resolver=lambda host: ['8.8.8.8'], recovery_epoch='epoch-0001',
            clock=lambda: AT, new_id=lambda: f'p-{next(ids)}',
        )
        self.assertEqual(
            (prod.readiness('ws-1'), self.handler.readiness('ws-1')),
            (AUTO_REGISTRATION_NOT_READY, AUTO_REGISTRATION_READY),
        )
        ready = prod.evaluate_source_candidate(
            workspace_id='ws-1', idempotency_key='p-e', actor='discovery', correlation_id='corr-1',
            observed_locator=LOCATOR, discovery_method='outlink', discovery_evidence='doc-42', policy_revision='tier-r1',
        )
        res = prod.register_source_candidate(
            workspace_id='ws-1', idempotency_key='p-r', actor='registrar', correlation_id='corr-1',
            candidate_id=ready.candidate.candidate_id, expected_revision=ready.current_revision, policy_revision='tier-r1',
        )
        self.assertEqual((res.code, res.receipt), ('WAITING_POLICY', None))
        self.assertEqual(self.uow.sources.list_sources('ws-1'), ())
        self.assertNotIn(EVENT_RESOLVED, self.events())


class ReplayAtomicityTests(CandidateTestCase):
    def test_race_004_lost_ack_retry_returns_committed_receipt(self) -> None:
        ready = self.ready().candidate
        first = self.register(ready.candidate_id, ready.revision)
        events_after = self.events()
        retry = self.register(ready.candidate_id, ready.revision)
        self.assertTrue(retry.replayed)
        self.assertEqual((retry.receipt, retry.code, retry.source_ref), (first.receipt, 'REGISTERED', first.source_ref))
        self.assertEqual(len(self.uow.sources.list_sources('ws-1')), 1)
        self.assertEqual(self.events(), events_after)
        with self.assertRaises(IdempotencyConflictError) as ctx:
            self.register(ready.candidate_id, ready.revision + 1)
        self.assertEqual(ctx.exception.code, 'IDEMPOTENCY_CONFLICT')
        with self.assertRaises(CandidateTransitionError):
            self.register(ready.candidate_id, first.current_revision, key='r-2')
        self.assertEqual(len(self.uow.sources.list_sources('ws-1')), 1)
        self.assertEqual(self.events(), events_after)

    def test_unknown_or_other_workspace_candidate_is_not_found(self) -> None:
        ready = self.ready().candidate
        with self.assertRaises(CandidateNotFoundError):
            self.register(ready.candidate_id, ready.revision, ws='ws-2')
        with self.assertRaises(CandidateNotFoundError):
            self.register('missing', 1, key='r-9')
        self.assertEqual(self.candidate(ready.candidate_id), ready)

    def test_outbox_failure_rolls_back_candidate_source_and_receipt(self) -> None:
        ready = self.ready().candidate
        real = self.uow.outbox.append_event

        def failing(event_type, *args, **kwargs):
            if event_type == EVENT_RESOLVED:
                raise Boom('outbox failed')
            return real(event_type, *args, **kwargs)

        self.uow.outbox.append_event = failing
        with self.assertRaises(Boom):
            self.register(ready.candidate_id, ready.revision)
        self.assertEqual(self.candidate(ready.candidate_id), ready)
        self.assertEqual(self.uow.sources.list_sources('ws-1'), ())
        self.assertIsNone(self.uow.receipts.get('ws-1', 'r-1'))
        self.assertEqual(self.events(), [EVENT_DISCOVERED])
        self.assertFalse(self.uow.active)

    def test_identity_is_rechecked_inside_the_registration_uow(self) -> None:
        ready = self.ready().candidate
        seen = []
        real = self.uow.sources.resolve_identity

        def spy(workspace_id, canonical_locator):
            seen.append(self.uow.active)
            return real(workspace_id, canonical_locator)

        self.uow.sources.resolve_identity = spy
        self.register(ready.candidate_id, ready.revision)
        self.assertEqual(seen, [True])


class SafetyAndLayerTests(CandidateTestCase):
    def test_events_carry_only_refs_revision_disposition_and_reason(self) -> None:
        res = self.evaluate(locator='https://news.example.com/feed?token=abc123', evidence='EVIDENCE-MARK secret=xyz789')
        self.register(res.candidate.candidate_id, res.current_revision)
        records = self.uow.outbox.records()
        self.assertEqual([r.event_type for r in records], [EVENT_DISCOVERED, EVENT_REGISTERED, EVENT_RESOLVED])
        discovered, _registered, resolved = (r.payload['payload'] for r in records)
        self.assertEqual(set(discovered), {'candidate_id', 'revision', 'disposition', 'reason'})
        self.assertEqual(set(resolved), {'candidate_id', 'revision', 'disposition', 'reason', 'source_ref'})
        self.assertEqual((discovered['revision'], discovered['disposition']), (1, 'DISCOVERED'))
        self.assertEqual((resolved['revision'], resolved['disposition'], resolved['reason']), (4, 'REGISTERED', 'REGISTERED_BY_POLICY'))
        envelope = records[2].payload
        self.assertEqual(set(envelope), {f.name for f in dataclasses.fields(DomainEvent)})
        self.assertEqual((envelope['aggregate_type'], envelope['producer'], envelope['aggregate_revision']), ('SourceCandidate', 'A', 4))
        self.assertEqual(len({r.deduplication_id for r in records}), 3)
        text = repr(records) + repr(self.uow.receipts.get('ws-1', 'e-1')) + repr(self.uow.receipts.get('ws-1', 'r-1'))
        for marker in ('abc123', 'xyz789', 'EVIDENCE-MARK', 'example.com'):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, text)

    def test_module_reuses_controlplane_types_and_respects_layers(self) -> None:
        source = MODULE_PATH.read_text(encoding='utf-8')
        tree = ast.parse(source)
        class_names = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
        forbidden = {'IUnitOfWork', 'IOutboxWriter', 'IRepository', 'DomainEvent', 'SecretHandle', 'ExecutionGrant', 'CommandReceipt'}
        self.assertEqual(class_names & forbidden, set())
        self.assertTrue(any(
            isinstance(n, ast.ImportFrom) and n.module == 'controlplane.domain.events'
            and any(a.name == 'DomainEvent' for a in n.names) for n in ast.walk(tree)
        ))
        prefixes = ('src.', 'psycopg', 'controlplane.infrastructure', 'source_ingestion.adapters')
        for n in ast.walk(tree):
            names = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module or ''] if isinstance(n, ast.ImportFrom) and n.level == 0 else []
            for name in names:
                self.assertNotEqual(name, 'src')
                self.assertFalse(name.startswith(prefixes))
        self.assertNotIn('TIER_', source)
        self.assertNotIn("'news_site'", source)

    def test_docstring_declares_covered_ids(self) -> None:
        doc = ast.get_docstring(ast.parse(pathlib.Path(__file__).read_text(encoding='utf-8'))) or ''
        for covered in ('TST-SRC-RACE-001..004', 'TST-INT-INV-015', 'A-RULE-002'):
            self.assertIn(covered, doc)
