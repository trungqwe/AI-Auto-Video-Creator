"""I-04: upload idempotent lên cloud và reconcile OUTCOME_UNKNOWN (CT-STO-003 bước 1-3, ADR-0006)."""
import dataclasses
import unittest
from unittest import mock

from controlplane.application.storage_meta import cloud_persist
from controlplane.application.storage_meta.cloud_persist import (
    ObjectAlreadyExistsError,
    PersistArtifactToCloud,
    PersistResult,
    UploadReceipt,
    UploadReceiptState,
)
from controlplane.domain.statemachine import ArtifactLocationState
from controlplane.domain.storage_meta.verification import IntegrityObservation

State = ArtifactLocationState
SHA = 'a' * 64
OTHER_SHA = 'b' * 64
SIZE = 2048
KEY = 'op-1'
VERSION = 'av-1'
NAMESPACE = 'ns://media'
GRANT = 'grant://exec/1'
VERIFIED_RESULT = PersistResult(KEY, 'obj-1', State.VERIFIED, 'evidence://lookup/obj-1')
HAPPY_CALLS = ['reserve', 'save:PREPARED', 'upload:obj-1', 'lookup:obj-1', 'save:VERIFIED']


class FakeCloud:
    def __init__(self, calls):
        self.calls = calls
        self.objects = {}
        self.reserved = 0
        self.timeout_after_store = False
        self.timeout_before_store = False
        self.lookup_timeout = False
        self.hide_hash = False

    def reserve_object_id(self, namespace_ref):
        self.calls.append('reserve')
        self.reserved += 1
        return f'obj-{self.reserved}'

    def upload(self, object_id, artifact_version_id, content_sha256, size_bytes):
        self.calls.append(f'upload:{object_id}')
        if self.timeout_before_store:
            raise TimeoutError('timed out before store')
        if object_id in self.objects:
            raise ObjectAlreadyExistsError(object_id)
        self.objects[object_id] = (content_sha256, size_bytes)
        if self.timeout_after_store:
            raise TimeoutError('timed out after store')

    def lookup(self, object_id):
        self.calls.append(f'lookup:{object_id}')
        if self.lookup_timeout:
            raise TimeoutError('lookup timed out')
        stored = self.objects.get(object_id)
        if stored is None:
            return IntegrityObservation(False, None, None, None)
        sha = None if self.hide_hash else stored[0]
        return IntegrityObservation(True, sha, stored[1], f'evidence://lookup/{object_id}')


class FakeReceipts:
    def __init__(self, calls):
        self.calls = calls
        self.saved = []
        self.store = {}

    def get(self, operation_key):
        return self.store.get(operation_key)

    def save(self, receipt):
        self.calls.append(f'save:{receipt.state.value}')
        self.saved.append(receipt)
        self.store[receipt.operation_key] = receipt


class CloudPersistCase(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.cloud = FakeCloud(self.calls)
        self.receipts = FakeReceipts(self.calls)
        self.use_case = PersistArtifactToCloud(self.cloud, self.receipts)

    def execute(self, **overrides):
        args = {'artifact_version_id': VERSION, 'content_sha256': SHA, 'size_bytes': SIZE, 'source_verified': True, 'namespace_ref': NAMESPACE, 'operation_key': KEY, 'grant_ref': GRANT}
        args.update(overrides)
        return self.use_case.execute(**args)


class GuardTests(CloudPersistCase):
    def test_unverified_source_is_rejected(self):
        for value in (False, None):
            with self.subTest(source_verified=value):
                with self.assertRaises(PermissionError):
                    self.execute(source_verified=value)
        self.assertEqual(self.calls, [])

    def test_empty_grant_is_rejected(self):
        for value in ('', '   ', None):
            with self.subTest(grant_ref=value):
                with self.assertRaises(PermissionError):
                    self.execute(grant_ref=value)
        self.assertEqual(self.calls, [])

    def test_invalid_input_is_rejected_before_any_side_effect(self):
        for overrides in ({'content_sha256': 'A' * 64}, {'content_sha256': 'abc'}, {'size_bytes': -1}, {'size_bytes': True}, {'operation_key': ''}, {'artifact_version_id': ' '}, {'namespace_ref': ''}):
            with self.subTest(overrides=overrides):
                with self.assertRaises(ValueError):
                    self.execute(**overrides)
        self.assertEqual(self.calls, [])


class OrderingAndIdempotencyTests(CloudPersistCase):
    def test_receipt_prepared_is_saved_before_upload(self):
        self.execute()
        self.assertEqual(self.calls, HAPPY_CALLS)
        self.assertEqual(self.receipts.saved[0], UploadReceipt(KEY, VERSION, SHA, SIZE, 'obj-1'))

    def test_verified_result_carries_lookup_evidence(self):
        self.assertEqual(self.execute(), VERIFIED_RESULT)
        self.assertEqual(self.receipts.get(KEY).verification_evidence_ref, 'evidence://lookup/obj-1')

    def test_retry_after_verified_does_not_upload_again(self):
        first = self.execute()
        self.calls.clear()
        self.assertEqual(self.execute(), first)
        self.assertEqual(self.calls, [])
        self.assertEqual(list(self.cloud.objects), ['obj-1'])

    def test_retry_same_key_reuses_object_id_after_timeout(self):
        self.cloud.timeout_after_store = True
        first = self.execute()
        self.assertIs(first.state, State.OUTCOME_UNKNOWN)
        self.cloud.timeout_after_store = False
        second = self.execute()
        self.assertEqual(second, VERIFIED_RESULT)
        self.assertEqual(first.object_id, second.object_id)
        self.assertEqual(self.cloud.reserved, 1)
        self.assertEqual(list(self.cloud.objects), ['obj-1'])

    def test_same_key_different_content_raises_value_error(self):
        self.execute()
        self.calls.clear()
        for overrides in ({'content_sha256': OTHER_SHA}, {'size_bytes': SIZE + 1}, {'artifact_version_id': 'av-2'}):
            with self.subTest(overrides=overrides):
                with self.assertRaises(ValueError):
                    self.execute(**overrides)
        self.assertEqual(self.calls, [])

    def test_different_keys_get_different_objects(self):
        self.execute()
        self.execute(operation_key='op-2')
        self.assertEqual(sorted(self.cloud.objects), ['obj-1', 'obj-2'])


class TimeoutTests(CloudPersistCase):
    def test_timeout_marks_receipt_outcome_unknown_without_new_id(self):
        self.cloud.timeout_after_store = True
        result = self.execute()
        self.assertEqual(result, PersistResult(KEY, 'obj-1', State.OUTCOME_UNKNOWN, None))
        self.assertEqual(self.calls, ['reserve', 'save:PREPARED', 'upload:obj-1', 'save:OUTCOME_UNKNOWN'])
        self.assertIs(self.receipts.get(KEY).state, UploadReceiptState.OUTCOME_UNKNOWN)
        self.assertEqual(self.cloud.reserved, 1)

    def test_reconcile_after_timeout_finds_exactly_one_object(self):
        self.cloud.timeout_after_store = True
        self.execute()
        self.calls.clear()
        self.assertEqual(self.use_case.reconcile(KEY), VERIFIED_RESULT)
        self.assertEqual(self.calls, ['lookup:obj-1', 'save:VERIFIED'])
        self.assertEqual(list(self.cloud.objects), ['obj-1'])
        self.assertEqual(self.cloud.reserved, 1)

    def test_upload_that_never_landed_reconciles_to_missing_then_retry_reuses_id(self):
        self.cloud.timeout_before_store = True
        self.execute()
        missing = self.use_case.reconcile(KEY)
        self.assertEqual(missing, PersistResult(KEY, 'obj-1', State.MISSING, None))
        self.assertIs(self.receipts.get(KEY).state, UploadReceiptState.MISSING)
        self.cloud.timeout_before_store = False
        self.assertEqual(self.execute(), VERIFIED_RESULT)
        self.assertEqual(self.cloud.reserved, 1)
        self.assertEqual(self.cloud.objects, {'obj-1': (SHA, SIZE)})

    def test_lookup_timeout_keeps_outcome_unknown(self):
        self.cloud.lookup_timeout = True
        result = self.execute()
        self.assertEqual(result, PersistResult(KEY, 'obj-1', State.OUTCOME_UNKNOWN, None))
        self.assertIs(self.receipts.get(KEY).state, UploadReceiptState.OUTCOME_UNKNOWN)


class VerifyTests(CloudPersistCase):
    def test_already_exists_with_matching_object_is_verified_without_new_object(self):
        self.cloud.objects['obj-1'] = (SHA, SIZE)
        self.assertEqual(self.execute(), VERIFIED_RESULT)
        self.assertEqual(self.calls, HAPPY_CALLS)
        self.assertEqual(list(self.cloud.objects), ['obj-1'])
        self.assertEqual(self.cloud.reserved, 1)

    def test_already_exists_with_other_content_is_corrupt_and_not_overwritten(self):
        self.cloud.objects['obj-1'] = (OTHER_SHA, SIZE)
        result = self.execute()
        self.assertEqual(result, PersistResult(KEY, 'obj-1', State.CORRUPT, None))
        self.assertEqual(self.cloud.objects, {'obj-1': (OTHER_SHA, SIZE)})

    def test_lookup_without_hash_is_not_verified(self):
        self.cloud.hide_hash = True
        result = self.execute()
        self.assertEqual(result, PersistResult(KEY, 'obj-1', State.OUTCOME_UNKNOWN, None))
        self.assertIs(self.receipts.get(KEY).state, UploadReceiptState.OUTCOME_UNKNOWN)

    def test_decision_uses_evaluate_integrity_from_i03(self):
        with mock.patch.object(cloud_persist, 'evaluate_integrity', wraps=cloud_persist.evaluate_integrity) as spy:
            self.execute()
        spy.assert_any_call(SHA, SIZE, IntegrityObservation(True, SHA, SIZE, 'evidence://lookup/obj-1'))

    def test_only_verified_observation_carries_evidence(self):
        ev = 'evidence://x'
        cases = (
            ('absent', IntegrityObservation(False, None, None, None), State.MISSING),
            ('no hash', IntegrityObservation(True, None, SIZE, ev), State.OUTCOME_UNKNOWN),
            ('presence unknown', IntegrityObservation(None, None, None, None), State.OUTCOME_UNKNOWN),
            ('blank evidence', IntegrityObservation(True, SHA, SIZE, ' '), State.OUTCOME_UNKNOWN),
            ('hash mismatch', IntegrityObservation(True, OTHER_SHA, SIZE, ev), State.CORRUPT),
            ('size mismatch', IntegrityObservation(True, SHA, SIZE + 1, ev), State.CORRUPT),
        )
        for index, (name, observation, expected) in enumerate(cases):
            with self.subTest(case=name):
                key = f'op-table-{index}'
                with mock.patch.object(self.cloud, 'lookup', return_value=observation) as lookup:
                    result = self.execute(operation_key=key)
                lookup.assert_called_once_with(result.object_id)
                self.assertIs(result.state, expected)
                self.assertIsNone(result.verification_evidence_ref)
                self.assertIs(self.receipts.get(key).state, UploadReceiptState(expected.value))
                self.assertIsNone(self.receipts.get(key).verification_evidence_ref)


class ReconcileTests(CloudPersistCase):
    def test_unknown_operation_key_raises_lookup_error(self):
        with self.assertRaises(LookupError):
            self.use_case.reconcile('op-missing')
        self.assertEqual(self.calls, [])

    def test_reconcile_looks_up_stored_object_id_only(self):
        self.receipts.save(UploadReceipt(KEY, VERSION, SHA, SIZE, 'obj-9', UploadReceiptState.OUTCOME_UNKNOWN))
        self.cloud.objects['obj-9'] = (SHA, SIZE)
        self.calls.clear()
        result = self.use_case.reconcile(KEY)
        self.assertEqual(result, PersistResult(KEY, 'obj-9', State.VERIFIED, 'evidence://lookup/obj-9'))
        self.assertEqual(self.calls, ['lookup:obj-9', 'save:VERIFIED'])
        self.assertEqual(self.cloud.reserved, 0)

    def test_reconcile_object_gone_marks_missing(self):
        self.receipts.save(UploadReceipt(KEY, VERSION, SHA, SIZE, 'obj-9', UploadReceiptState.OUTCOME_UNKNOWN))
        result = self.use_case.reconcile(KEY)
        self.assertEqual(result, PersistResult(KEY, 'obj-9', State.MISSING, None))
        self.assertIs(self.receipts.get(KEY).state, UploadReceiptState.MISSING)

    def test_receipt_and_result_are_frozen(self):
        with self.assertRaises(dataclasses.FrozenInstanceError):
            UploadReceipt(KEY, VERSION, SHA, SIZE, 'obj-1').state = UploadReceiptState.VERIFIED
        with self.assertRaises(dataclasses.FrozenInstanceError):
            VERIFIED_RESULT.state = State.MISSING
