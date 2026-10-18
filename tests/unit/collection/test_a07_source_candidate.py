"""A-07: SourceCandidate lifecycle (CT-SRC-003A, CT-STATE-002A).

coveredIds: A-RULE-002, TST-INT-INV-015 (mức domain)
"""
import dataclasses
import unittest
from datetime import datetime, timedelta, timezone

from source_ingestion.domain.source_candidate import (
    ALLOWED_TRANSITIONS,
    NO_MATCH,
    REVISION_CONFLICT,
    TERMINAL_STATUSES,
    WAITING_POLICY,
    CandidateStatus as S,
    CandidateTransitionError,
    IdentityMatch,
    IdentityMatchKind,
    RegistrationPolicy,
    begin_validation,
    complete_validation,
    discover_candidate,
    register_candidate,
    resolve_identity,
)

T0 = datetime(2026, 10, 18, 8, 0, tzinfo=timezone.utc)
T1 = T0 + timedelta(minutes=1)
LOCATOR = 'https://news.example.com/'
TOMBSTONE = IdentityMatch(IdentityMatchKind.TOMBSTONE, 'source-removed-1')
EXISTING = IdentityMatch(IdentityMatchKind.EXISTING_SOURCE, 'source-active-1')
FULL_POLICY = RegistrationPolicy(
    revision='tier-policy-r3', auto_registration_enabled=True, permitted=True,
    source_kind='news_site', topics=('economy',), tier='TIER_2',
)


def discovered(**overrides):
    fields = dict(
        candidate_id='cand-1', workspace_id='ws-1', observed_locator='HTTPS://News.Example.com/#top',
        canonical_locator=LOCATOR, discovery_method='outlink', discovery_evidence='doc-42',
        source_kind_candidates=('news_site',), topic_candidates=('economy',), actor='discovery-worker', at=T0,
    )
    fields.update(overrides)
    return discover_candidate(**fields)


def validating():
    c = discovered()
    return begin_validation(c, expected_revision=c.revision, actor='discovery-worker', at=T1).candidate


def ready():
    c = validating()
    return complete_validation(
        c, expected_revision=c.revision, identity=NO_MATCH, validation_passed=True, actor='discovery-worker', at=T1,
    ).candidate


def register(c, *, identity=NO_MATCH, policy=FULL_POLICY, expected_revision=None):
    revision = c.revision if expected_revision is None else expected_revision
    return register_candidate(
        c, expected_revision=revision, identity=identity, policy=policy,
        new_source_ref='source-new-1', actor='registrar', at=T1,
    )


def _begin(c):
    return begin_validation(c, expected_revision=c.revision, actor='discovery-worker', at=T1)


def _complete(c):
    return complete_validation(
        c, expected_revision=c.revision, identity=NO_MATCH, validation_passed=True, actor='discovery-worker', at=T1,
    )


class TransitionTableTests(unittest.TestCase):
    def test_table_matches_ct_state_002a(self) -> None:
        self.assertEqual(dict(ALLOWED_TRANSITIONS), {
            S.DISCOVERED: frozenset({S.VALIDATING}),
            S.VALIDATING: frozenset({S.READY_FOR_REGISTRATION, S.MATCHED_EXISTING, S.BLOCKED_TOMBSTONE, S.REJECTED}),
            S.READY_FOR_REGISTRATION: frozenset({S.REGISTERED, S.MATCHED_EXISTING, S.BLOCKED_TOMBSTONE, S.REJECTED}),
            S.MATCHED_EXISTING: frozenset(),
            S.BLOCKED_TOMBSTONE: frozenset(),
            S.REJECTED: frozenset(),
            S.REGISTERED: frozenset(),
        })
        self.assertEqual(
            TERMINAL_STATUSES, frozenset({S.MATCHED_EXISTING, S.BLOCKED_TOMBSTONE, S.REJECTED, S.REGISTERED}),
        )
        self.assertEqual((WAITING_POLICY, REVISION_CONFLICT), ('WAITING_POLICY', 'REVISION_CONFLICT'))

    def test_discovered_candidate_has_no_assigned_classification(self) -> None:
        c = discovered()
        self.assertEqual((c.status, c.revision, c.updated_by, c.updated_at), (S.DISCOVERED, 1, 'discovery-worker', T0))
        self.assertEqual((c.source_kind, c.topics, c.tier, c.policy_revision), (None, (), None, None))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            c.status = S.REGISTERED

    def test_rejects_invalid_inputs(self) -> None:
        for overrides in ({'candidate_id': ' '}, {'canonical_locator': ''}, {'discovery_method': ''},
                          {'actor': ''}, {'at': datetime(2026, 10, 18, 8, 0)}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                discovered(**overrides)
        for kind, ref in ((IdentityMatchKind.NONE, 'x'), (IdentityMatchKind.TOMBSTONE, None),
                          (IdentityMatchKind.EXISTING_SOURCE, ' ')):
            with self.subTest(kind=kind.value, ref=ref), self.assertRaises(ValueError):
                IdentityMatch(kind, ref)


class ValidationTests(unittest.TestCase):
    def test_discovered_moves_to_validating(self) -> None:
        c = discovered()
        d = begin_validation(c, expected_revision=1, actor='discovery-worker', at=T1)
        self.assertEqual(
            (d.code, d.candidate.status, d.candidate.revision, d.current_revision), ('VALIDATING', S.VALIDATING, 2, 2),
        )
        self.assertEqual(d.candidate.updated_at, T1)

    def test_validation_outcomes(self) -> None:
        cases = (
            (NO_MATCH, True, None, S.READY_FOR_REGISTRATION, None, None),
            (EXISTING, True, None, S.MATCHED_EXISTING, 'source-active-1', None),
            (TOMBSTONE, True, None, S.BLOCKED_TOMBSTONE, None, 'source-removed-1'),
            (NO_MATCH, False, 'ssrf_blocked', S.REJECTED, None, None),
        )
        for identity, passed, reason, expected, source_ref, tombstone_ref in cases:
            with self.subTest(expected=expected.value):
                c = validating()
                d = complete_validation(
                    c, expected_revision=c.revision, identity=identity, validation_passed=passed, reason=reason,
                    actor='discovery-worker', at=T1,
                )
                r = d.candidate
                self.assertEqual((d.code, r.status, r.revision), (expected.value, expected, c.revision + 1))
                self.assertEqual(
                    (r.matched_source_ref, r.matched_tombstone_ref, r.registered_source_ref),
                    (source_ref, tombstone_ref, None),
                )
                self.assertEqual((r.source_kind, r.topics, r.tier), (None, (), None))

    def test_tombstone_takes_precedence(self) -> None:
        c = validating()
        d = complete_validation(
            c, expected_revision=c.revision, identity=TOMBSTONE, validation_passed=False, reason='ssrf_blocked',
            actor='discovery-worker', at=T1,
        )
        self.assertEqual(d.candidate.status, S.BLOCKED_TOMBSTONE)
        both = resolve_identity(
            LOCATOR, tombstoned_refs={LOCATOR: 'source-removed-1'}, source_refs={LOCATOR: 'source-active-1'},
        )
        self.assertEqual(both, TOMBSTONE)
        self.assertEqual(resolve_identity(LOCATOR, tombstoned_refs={}, source_refs={LOCATOR: 'source-active-1'}), EXISTING)
        self.assertEqual(resolve_identity(LOCATOR, tombstoned_refs={}, source_refs={}), NO_MATCH)

    def test_rejection_requires_reason(self) -> None:
        c = validating()
        with self.assertRaises(ValueError):
            complete_validation(
                c, expected_revision=c.revision, identity=NO_MATCH, validation_passed=False,
                actor='discovery-worker', at=T1,
            )


class RegistrationTests(unittest.TestCase):
    def test_ready_registers_with_policy_classification(self) -> None:
        c = ready()
        d = register(c)
        r = d.candidate
        self.assertEqual(
            (d.code, r.status, r.revision, r.updated_by), ('REGISTERED', S.REGISTERED, c.revision + 1, 'registrar'),
        )
        self.assertEqual(
            (r.registered_source_ref, r.source_kind, r.topics, r.tier, r.policy_revision),
            ('source-new-1', 'news_site', ('economy',), 'TIER_2', 'tier-policy-r3'),
        )

    def test_ready_terminal_outcomes_do_not_register(self) -> None:
        forbidding = dataclasses.replace(FULL_POLICY, permitted=False, reason='domain_blocklisted')
        cases = (
            (EXISTING, FULL_POLICY, S.MATCHED_EXISTING),
            (TOMBSTONE, FULL_POLICY, S.BLOCKED_TOMBSTONE),
            (TOMBSTONE, None, S.BLOCKED_TOMBSTONE),
            (NO_MATCH, forbidding, S.REJECTED),
        )
        for identity, policy, expected in cases:
            with self.subTest(expected=expected.value, has_policy=policy is not None):
                c = ready()
                d = register(c, identity=identity, policy=policy)
                self.assertEqual(
                    (d.code, d.candidate.status, d.candidate.revision), (expected.value, expected, c.revision + 1),
                )
                self.assertEqual((d.candidate.registered_source_ref, d.candidate.tier), (None, None))

    def test_missing_policy_keeps_ready_with_waiting_policy(self) -> None:
        policies = {
            'missing': None,
            'auto_registration_disabled': dataclasses.replace(FULL_POLICY, auto_registration_enabled=False),
            'no_tier': dataclasses.replace(FULL_POLICY, tier=None),
            'no_source_kind': dataclasses.replace(FULL_POLICY, source_kind=None),
            'no_topic': dataclasses.replace(FULL_POLICY, topics=()),
        }
        for name, policy in policies.items():
            with self.subTest(policy=name):
                c = ready()
                d = register(c, policy=policy)
                self.assertEqual((d.code, d.current_revision), (WAITING_POLICY, c.revision))
                self.assertIs(d.candidate, c)
                self.assertEqual(c.status, S.READY_FOR_REGISTRATION)
                self.assertEqual((c.source_kind, c.topics, c.tier, c.registered_source_ref), (None, (), None, None))

    def test_inv015_removed_source_rediscovered_is_blocked_not_registered(self) -> None:
        tombstones = {LOCATOR: 'source-removed-1'}
        c = validating()
        identity = resolve_identity(c.canonical_locator, tombstoned_refs=tombstones, source_refs={})
        d = complete_validation(
            c, expected_revision=c.revision, identity=identity, validation_passed=True,
            actor='discovery-worker', at=T1,
        )
        self.assertEqual(d.candidate.status, S.BLOCKED_TOMBSTONE)
        r = ready()
        d = register(r, identity=resolve_identity(r.canonical_locator, tombstoned_refs=tombstones, source_refs={}))
        self.assertEqual(
            (d.code, d.candidate.status, d.candidate.matched_tombstone_ref),
            ('BLOCKED_TOMBSTONE', S.BLOCKED_TOMBSTONE, 'source-removed-1'),
        )
        self.assertIsNone(d.candidate.registered_source_ref)


class ConcurrencyAndTerminalTests(unittest.TestCase):
    def test_stale_expected_revision_returns_conflict_without_state_change(self) -> None:
        cases = (
            ('begin_validation', discovered(),
             lambda c: begin_validation(c, expected_revision=c.revision - 1, actor='w', at=T1)),
            ('complete_validation', validating(),
             lambda c: complete_validation(
                 c, expected_revision=c.revision - 1, identity=NO_MATCH, validation_passed=True, actor='w', at=T1,
             )),
            ('register_candidate', ready(), lambda c: register(c, expected_revision=c.revision - 1)),
        )
        for name, c, call in cases:
            with self.subTest(call=name):
                d = call(c)
                self.assertEqual((d.code, d.current_revision), (REVISION_CONFLICT, c.revision))
                self.assertIs(d.candidate, c)

    def test_terminal_candidates_are_not_reopened(self) -> None:
        calls = (
            ('begin_validation', _begin),
            ('complete_validation', _complete),
            ('register_candidate', register),
            ('register_without_policy', lambda c: register(c, policy=None)),
        )
        for status in sorted(TERMINAL_STATUSES, key=lambda s: s.value):
            terminal = dataclasses.replace(ready(), status=status)
            for name, call in calls:
                with self.subTest(status=status.value, call=name):
                    with self.assertRaises(CandidateTransitionError):
                        call(terminal)
                    self.assertEqual(terminal.status, status)

    def test_out_of_order_transitions_are_rejected(self) -> None:
        cases = (
            ('register_from_discovered', discovered(), register),
            ('register_from_validating', validating(), register),
            ('complete_from_discovered', discovered(), _complete),
            ('begin_from_ready', ready(), _begin),
        )
        for name, c, call in cases:
            with self.subTest(case=name), self.assertRaises(CandidateTransitionError):
                call(c)
