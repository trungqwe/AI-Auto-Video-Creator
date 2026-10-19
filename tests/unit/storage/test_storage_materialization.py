"""I-07: admission materialize, working set và release input cho render (CT-STO-004, INV-008)."""
import dataclasses
import json
import unittest
from pathlib import Path

from controlplane.application.storage_meta.materialization import (
    ActiveVideoSet,
    AdmissionDecision,
    AdmissionStatus,
    MaterializationRequest,
    RenderInputNotVerifiedError,
    WorkingSetPolicy,
    admit_materialization,
    release_for_render,
)
from controlplane.domain.statemachine import ArtifactLocationState
from controlplane.domain.storage_meta import ArtifactLocation

State = ArtifactLocationState
GIB = 1024 ** 3
POLICY = WorkingSetPolicy(max_bytes=10 * GIB, policy_revision='ws-policy-test-1')
SET_LIMIT = 'MAX_VIDEO_SETS_REACHED'
BYTE_LIMIT = 'MAX_BYTES_EXCEEDED'


def sets(count, expected_bytes=GIB):
    return [ActiveVideoSet(f'set-{index}', expected_bytes) for index in range(count)]


def request(expected_bytes=GIB, is_prefetch=False):
    return MaterializationRequest('set-new', expected_bytes, is_prefetch)


class WorkingSetPolicyTests(unittest.TestCase):
    def test_max_bytes_is_required_and_default_sets_is_five(self):
        with self.assertRaises(TypeError):
            WorkingSetPolicy(policy_revision='r1')
        self.assertEqual(WorkingSetPolicy(max_bytes=1, policy_revision='r1').max_video_sets, 5)

    def test_invalid_values_raise_value_error(self):
        cases = ({'max_bytes': 0}, {'max_bytes': -1}, {'max_bytes': True}, {'max_bytes': '1'}, {'max_video_sets': 0}, {'max_video_sets': True}, {'policy_revision': ''}, {'policy_revision': '  '})
        for overrides in cases:
            with self.subTest(overrides=overrides):
                values = {'max_bytes': 1, 'policy_revision': 'r1', **overrides}
                with self.assertRaises(ValueError):
                    WorkingSetPolicy(**values)

    def test_policy_is_frozen(self):
        with self.assertRaises(dataclasses.FrozenInstanceError):
            POLICY.max_bytes = 1

    def test_request_and_active_set_reject_invalid_bytes(self):
        for value in (-1, True, '1', None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    MaterializationRequest('set-new', value)
                with self.assertRaises(ValueError):
                    ActiveVideoSet('set-0', value)
                with self.assertRaises(ValueError):
                    ActiveVideoSet('set-0', 1, unsynced_output_bytes=value)


class AdmitMaterializationTests(unittest.TestCase):
    def assert_decision(self, decision, status, reason):
        self.assertIsInstance(decision, AdmissionDecision)
        self.assertIs(decision.status, status)
        self.assertEqual(decision.reason, reason)

    def test_fifth_set_is_admitted(self):
        self.assert_decision(admit_materialization(POLICY, sets(4), request()), AdmissionStatus.ADMITTED, None)

    def test_sixth_set_is_deferred(self):
        self.assert_decision(admit_materialization(POLICY, sets(5), request()), AdmissionStatus.DEFERRED, SET_LIMIT)

    def test_custom_max_video_sets_is_honoured(self):
        policy = WorkingSetPolicy(max_bytes=10 * GIB, policy_revision='r1', max_video_sets=2)
        self.assert_decision(admit_materialization(policy, sets(2), request()), AdmissionStatus.DEFERRED, SET_LIMIT)
        self.assert_decision(admit_materialization(policy, sets(1), request()), AdmissionStatus.ADMITTED, None)

    def test_byte_overflow_is_deferred_and_exact_fit_is_admitted(self):
        active = sets(2, 4 * GIB)
        self.assert_decision(admit_materialization(POLICY, active, request(3 * GIB)), AdmissionStatus.DEFERRED, BYTE_LIMIT)
        self.assert_decision(admit_materialization(POLICY, active, request(2 * GIB)), AdmissionStatus.ADMITTED, None)

    def test_set_limit_has_priority_when_both_limits_are_hit(self):
        self.assert_decision(admit_materialization(POLICY, sets(5, 3 * GIB), request()), AdmissionStatus.DEFERRED, SET_LIMIT)

    def test_unsynced_output_counts_toward_set_limit(self):
        pending = ActiveVideoSet('set-out', GIB, inputs_materialized=False, unsynced_output_bytes=GIB // 2)
        self.assert_decision(admit_materialization(POLICY, sets(4) + [pending], request()), AdmissionStatus.DEFERRED, SET_LIMIT)

    def test_released_set_without_unsynced_output_is_not_counted(self):
        released = ActiveVideoSet('set-done', GIB, inputs_materialized=False, unsynced_output_bytes=0)
        self.assert_decision(admit_materialization(POLICY, sets(4) + [released], request()), AdmissionStatus.ADMITTED, None)

    def test_unsynced_output_bytes_count_toward_byte_limit(self):
        pending = ActiveVideoSet('set-out', GIB, inputs_materialized=False, unsynced_output_bytes=9 * GIB)
        self.assert_decision(admit_materialization(POLICY, [pending], request(2 * GIB)), AdmissionStatus.DEFERRED, BYTE_LIMIT)
        self.assert_decision(admit_materialization(POLICY, [pending], request(GIB)), AdmissionStatus.ADMITTED, None)

    def test_prefetch_is_deferred_when_full(self):
        self.assert_decision(admit_materialization(POLICY, sets(5), request(is_prefetch=True)), AdmissionStatus.DEFERRED, SET_LIMIT)
        self.assert_decision(admit_materialization(POLICY, sets(2, 4 * GIB), request(3 * GIB, is_prefetch=True)), AdmissionStatus.DEFERRED, BYTE_LIMIT)
        pending = ActiveVideoSet('set-out', GIB, inputs_materialized=False, unsynced_output_bytes=GIB)
        self.assert_decision(admit_materialization(POLICY, sets(4) + [pending], request(is_prefetch=True)), AdmissionStatus.DEFERRED, SET_LIMIT)

    def test_prefetch_is_admitted_only_when_both_limits_hold_after_admission(self):
        self.assert_decision(admit_materialization(POLICY, sets(4), request(is_prefetch=True)), AdmissionStatus.ADMITTED, None)
        self.assert_decision(admit_materialization(POLICY, sets(4, 2 * GIB), request(2 * GIB, is_prefetch=True)), AdmissionStatus.ADMITTED, None)
        self.assert_decision(admit_materialization(POLICY, sets(4, 2 * GIB), request(2 * GIB + 1, is_prefetch=True)), AdmissionStatus.DEFERRED, BYTE_LIMIT)

    def test_decision_is_frozen(self):
        decision = admit_materialization(POLICY, [], request())
        with self.assertRaises(dataclasses.FrozenInstanceError):
            decision.reason = 'x'


def load_input_artifacts():
    path = Path(__file__).resolve().parents[2] / 'fixtures' / 'contracts' / 'f-render-package' / 'payloads.json'
    payload = json.loads(path.read_text(encoding='utf-8'))
    return payload['entities']['RenderPackage']['valid'][0]['input_artifacts']


def make_location(item, **overrides):
    fields = {
        'workspace_id': 'ws-1', 'location_id': 'loc-1', 'artifact_version_id': item['artifact_version_id'],
        'backend_ref': 'local', 'provider_namespace_ref': 'ns', 'provider_object_ref': 'obj', 'logical_locator': 'staging/obj',
        'observed_hash': item['sha256'], 'observed_size_bytes': item['size_bytes'], 'provider_metadata_revision': None,
        'verification_evidence_ref': 'evidence://verify/1', 'state': State.VERIFIED, 'revision': 1,
        'created_at': '2026-10-19T00:00:00Z', 'updated_at': '2026-10-19T00:00:00Z',
    }
    fields.update(overrides)
    return ArtifactLocation(**fields)


class ReleaseForRenderTests(unittest.TestCase):
    def setUp(self):
        self.items = load_input_artifacts()
        self.item = self.items[0]
        self.version_id = self.item['artifact_version_id']

    def assert_rejected(self, items, locations, version_id):
        with self.assertRaises(RenderInputNotVerifiedError) as caught:
            release_for_render(items, locations)
        self.assertEqual(caught.exception.artifact_version_id, version_id)
        self.assertIn(version_id, str(caught.exception))

    def test_fixture_has_one_input_artifact(self):
        self.assertEqual(len(self.items), 1)

    def test_verified_matching_location_is_released(self):
        location = make_location(self.item)
        self.assertEqual(release_for_render(self.items, {self.version_id: location}), [location])

    def test_empty_input_releases_nothing(self):
        self.assertEqual(release_for_render([], {}), [])

    def test_every_non_verified_state_is_rejected(self):
        for state in State:
            if state is State.VERIFIED:
                continue
            with self.subTest(state=state):
                self.assert_rejected(self.items, {self.version_id: make_location(self.item, state=state)}, self.version_id)

    def test_wrong_or_missing_observed_hash_is_rejected(self):
        for observed in ('f' * 64, None):
            with self.subTest(observed_hash=observed):
                self.assert_rejected(self.items, {self.version_id: make_location(self.item, observed_hash=observed)}, self.version_id)

    def test_wrong_or_missing_observed_size_is_rejected(self):
        for observed in (self.item['size_bytes'] + 1, None):
            with self.subTest(observed_size_bytes=observed):
                self.assert_rejected(self.items, {self.version_id: make_location(self.item, observed_size_bytes=observed)}, self.version_id)

    def test_missing_location_is_rejected(self):
        self.assert_rejected(self.items, {}, self.version_id)

    def test_location_bound_to_other_artifact_version_is_rejected(self):
        other = make_location(self.item, artifact_version_id='00000000-0000-4000-8000-0000000000aa')
        self.assert_rejected(self.items, {self.version_id: other}, self.version_id)

    def test_one_unverified_input_blocks_whole_release_and_is_named(self):
        second = dict(self.item, artifact_version_id='00000000-0000-4000-8000-0000000000bb')
        locations = {
            self.version_id: make_location(self.item),
            second['artifact_version_id']: make_location(second, state=State.AVAILABLE_UNVERIFIED),
        }
        self.assert_rejected([self.item, second], locations, second['artifact_version_id'])

    def test_malformed_input_item_is_rejected(self):
        broken = {'artifact_version_id': self.version_id, 'sha256': self.item['sha256']}
        self.assert_rejected([broken], {self.version_id: make_location(self.item)}, self.version_id)
