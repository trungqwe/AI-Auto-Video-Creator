"""I-03: integrity verification policy for artifact locations (CT-STO-003 bước 4-5, CT-STATE-012)."""
import dataclasses
import unittest
from unittest import mock

from controlplane.domain.statemachine import ArtifactLocationState, ForbiddenTransitionError, TransitionResult
from controlplane.domain.storage_meta import verification
from controlplane.domain.storage_meta.verification import IntegrityObservation, apply_integrity_outcome, evaluate_integrity

State = ArtifactLocationState
EXPECTED_SHA256 = 'a' * 64
OTHER_SHA256 = 'b' * 64
EXPECTED_SIZE = 1024
EVIDENCE_REF = 'evidence://verify/1'
OUTCOMES = (State.VERIFIED, State.CORRUPT, State.MISSING, State.OUTCOME_UNKNOWN)


def make_observation(**overrides):
    fields = {'object_present': True, 'observed_sha256': EXPECTED_SHA256, 'observed_size_bytes': EXPECTED_SIZE, 'evidence_ref': EVIDENCE_REF}
    fields.update(overrides)
    return IntegrityObservation(**fields)


def evaluate(**overrides):
    return evaluate_integrity(EXPECTED_SHA256, EXPECTED_SIZE, make_observation(**overrides))


class EvaluateIntegrityTests(unittest.TestCase):
    def test_table(self):
        absent = {'object_present': False, 'observed_sha256': None, 'observed_size_bytes': None, 'evidence_ref': None}
        cases = (
            ('full match', {}, State.VERIFIED),
            ('size match only, no hash', {'observed_sha256': None}, State.OUTCOME_UNKNOWN),
            ('hash mismatch', {'observed_sha256': OTHER_SHA256}, State.CORRUPT),
            ('size mismatch', {'observed_size_bytes': EXPECTED_SIZE + 1}, State.CORRUPT),
            ('object absent', absent, State.MISSING),
            ('object absent with full fields', {'object_present': False}, State.MISSING),
            ('presence unknown', {'object_present': None}, State.OUTCOME_UNKNOWN),
            ('presence truthy non-bool', {'object_present': 1}, State.OUTCOME_UNKNOWN),
            ('evidence None', {'evidence_ref': None}, State.OUTCOME_UNKNOWN),
            ('evidence empty', {'evidence_ref': ''}, State.OUTCOME_UNKNOWN),
            ('evidence blank', {'evidence_ref': '   '}, State.OUTCOME_UNKNOWN),
            ('size missing', {'observed_size_bytes': None}, State.OUTCOME_UNKNOWN),
            ('hash uppercase is not valid evidence', {'observed_sha256': 'A' * 64}, State.OUTCOME_UNKNOWN),
            ('hash malformed', {'observed_sha256': 'abc'}, State.OUTCOME_UNKNOWN),
            ('size is bool', {'observed_size_bytes': True}, State.OUTCOME_UNKNOWN),
            ('size negative', {'observed_size_bytes': -1}, State.OUTCOME_UNKNOWN),
        )
        for name, overrides, expected in cases:
            with self.subTest(case=name):
                self.assertIs(evaluate(**overrides), expected)

    def test_only_all_four_signals_verify(self):
        for field in ('observed_sha256', 'observed_size_bytes', 'evidence_ref'):
            with self.subTest(missing=field):
                self.assertIsNot(evaluate(**{field: None}), State.VERIFIED)
        self.assertIsNot(evaluate(object_present=None), State.VERIFIED)
        self.assertIsNot(evaluate(object_present=False), State.VERIFIED)

    def test_upload_response_without_hash_is_never_verified(self):
        observation = IntegrityObservation(object_present=True, observed_sha256=None, observed_size_bytes=EXPECTED_SIZE, evidence_ref=EVIDENCE_REF)
        self.assertIs(evaluate_integrity(EXPECTED_SHA256, EXPECTED_SIZE, observation), State.OUTCOME_UNKNOWN)

    def test_observation_is_frozen_with_contract_fields(self):
        observation = make_observation()
        self.assertEqual([f.name for f in dataclasses.fields(observation)], ['object_present', 'observed_sha256', 'observed_size_bytes', 'evidence_ref'])
        with self.assertRaises(dataclasses.FrozenInstanceError):
            observation.object_present = False

    def test_invalid_expected_values_raise_value_error(self):
        for value in (None, '', 'A' * 64, 'a' * 63):
            with self.subTest(expected_sha256=value):
                with self.assertRaises(ValueError):
                    evaluate_integrity(value, EXPECTED_SIZE, make_observation())
        for value in (None, -1, True, '1'):
            with self.subTest(expected_size_bytes=value):
                with self.assertRaises(ValueError):
                    evaluate_integrity(EXPECTED_SHA256, value, make_observation())


class ApplyIntegrityOutcomeTests(unittest.TestCase):
    def test_recovery_edges_to_verified_are_forbidden(self):
        for state in (State.MISSING, State.CORRUPT, State.OUTCOME_UNKNOWN):
            with self.subTest(current_state=state):
                with self.assertRaises(ForbiddenTransitionError) as caught:
                    apply_integrity_outcome(state, 3, State.VERIFIED)
                self.assertIs(caught.exception.current_state, state)
                self.assertIs(caught.exception.requested_next_state, State.VERIFIED)

    def test_verifying_to_verified_is_admitted(self):
        result = apply_integrity_outcome(State.VERIFYING, 3, State.VERIFIED)
        self.assertEqual(result, TransitionResult(state=State.VERIFIED, revision=4))

    def test_edge_table_has_no_recovery_edge(self):
        for current in State:
            for outcome in OUTCOMES:
                allowed = current is State.VERIFYING or (current is State.VERIFIED and outcome is State.MISSING)
                with self.subTest(current=current, outcome=outcome):
                    if allowed:
                        self.assertEqual(apply_integrity_outcome(current, 7, outcome), TransitionResult(state=outcome, revision=8))
                    else:
                        with self.assertRaises(ForbiddenTransitionError):
                            apply_integrity_outcome(current, 7, outcome)

    def test_expected_revision_equals_current_revision(self):
        with mock.patch.object(verification, 'transition_artifact_location', wraps=verification.transition_artifact_location) as spy:
            apply_integrity_outcome(State.VERIFYING, 3, State.VERIFIED)
        spy.assert_called_once_with(current_state=State.VERIFYING, current_revision=3, expected_revision=3, requested_state=State.VERIFIED)

    def test_non_integrity_outcome_is_rejected(self):
        for outcome in State:
            if outcome in OUTCOMES:
                continue
            with self.subTest(outcome=outcome):
                with self.assertRaises(ValueError):
                    apply_integrity_outcome(State.VERIFIED, 1, outcome)

    def test_evaluated_outcome_flows_into_transition(self):
        for overrides, expected in (({}, State.VERIFIED), ({'object_present': False}, State.MISSING), ({'observed_sha256': OTHER_SHA256}, State.CORRUPT), ({'observed_sha256': None}, State.OUTCOME_UNKNOWN)):
            with self.subTest(expected=expected):
                result = apply_integrity_outcome(State.VERIFYING, 0, evaluate(**overrides))
                self.assertEqual(result, TransitionResult(state=expected, revision=1))
