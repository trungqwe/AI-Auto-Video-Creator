"""I-10: kiểm thử đối soát storage reconciliation (CT-STO-009, INV-016)."""
from __future__ import annotations

import copy
import dataclasses
import json
import pathlib
import types
import unittest

from controlplane.application.storage_meta.reconciliation import (
    CloudLocationRecord,
    CloudObjectObservation,
    CompletionRecord,
    JournalEntry,
    ReconcileAction,
    ReconcileCode,
    ReconcileFinding,
    ReconcileSnapshot,
    VersionRecord,
    reconcile,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'g-c-i-completion' / 'payloads.json'
ENTITIES = json.loads(FIXTURE.read_text(encoding='utf-8'))
LEDGER = ENTITIES['entities']['CompletionLedgerEntry']['valid'][0]
REQUEST = ENTITIES['entities']['CommitVideoCompletionRequest']['valid'][0]

JOB = LEDGER['video_job_id']
VERSION = LEDGER['output_artifact_version_id']
SHA = LEDGER['output_sha256']
LOCATION = LEDGER['cloud_location_ref']
EPOCH = REQUEST['recovery_epoch']
GEN = REQUEST['execution_generation']
OTHER_SHA = 'f' * 64
SIZE = 4096
PROVIDER_REF = 'drive://obj/out-1'
ORPHAN_REF = 'drive://obj/orphan'
OP_KEY = 'op-1'
OLD_EPOCH = 'epoch-0000'
C = ReconcileCode
REISSUE = ReconcileAction.REISSUE_UNDER_NEW_EPOCH

copy._deepcopy_dispatch[types.MappingProxyType] = (
    lambda x, memo: types.MappingProxyType(copy.deepcopy(dict(x), memo))
)


def F(code: ReconcileCode, ref: str, action: ReconcileAction | None = None) -> ReconcileFinding:
    return ReconcileFinding(code, ref, action)


def base(**overrides) -> ReconcileSnapshot:
    snapshot = ReconcileSnapshot(
        current_recovery_epoch=EPOCH,
        versions=(VersionRecord(VERSION, SHA, SIZE),),
        cloud_locations=(CloudLocationRecord(LOCATION, VERSION, PROVIDER_REF),),
        cloud_objects=(CloudObjectObservation(PROVIDER_REF, SHA, SIZE),),
        journal_entries=(JournalEntry(OP_KEY, VERSION, GEN, EPOCH),),
        stage_generations=types.MappingProxyType({OP_KEY: GEN}),
        completions=(CompletionRecord(JOB, VERSION, SHA, LOCATION),),
    )
    return dataclasses.replace(snapshot, **overrides)


def _make_all_discrepancies_snapshot() -> ReconcileSnapshot:
    return ReconcileSnapshot(
        current_recovery_epoch=EPOCH,
        versions=(
            VersionRecord('v-missing', 'sha-missing', 100),
            VersionRecord('v-mismatch', 'sha-mismatch-expected', 200),
            VersionRecord('v-dup', 'sha-dup', 300),
        ),
        cloud_locations=(
            CloudLocationRecord('loc-missing', 'v-missing', 'drive://obj/missing'),
            CloudLocationRecord('loc-mismatch', 'v-mismatch', 'drive://obj/mismatch'),
            CloudLocationRecord('loc-dup-10', 'v-dup', 'drive://obj/dup-10'),
        ),
        cloud_objects=(
            CloudObjectObservation('drive://obj/mismatch', 'sha-mismatch-actual', 200),
            CloudObjectObservation('drive://obj/orphan-10', 'sha-orphan', 400),
            CloudObjectObservation('drive://obj/dup-10', 'sha-dup', 300),
            CloudObjectObservation('drive://obj/dup-10', 'sha-dup', 300),
        ),
        journal_entries=(
            JournalEntry('op-gen-mismatch', 'v-gen', 1, EPOCH),
            JournalEntry('op-stale', 'v-stale', 1, OLD_EPOCH),
        ),
        stage_generations=types.MappingProxyType({'op-gen-mismatch': 2}),
        completions=(
            CompletionRecord('job-unverified', 'v-comp', 'sha-comp', 'loc-nonexistent'),
        ),
    )


class ReconcileTests(unittest.TestCase):
    def test_consistent_snapshot_returns_empty_tuple(self):
        self.assertEqual(reconcile(base()), ())

    def test_cloud_object_missing(self):
        result = reconcile(base(cloud_objects=()))
        self.assertEqual(
            result,
            (
                F(C.CLOUD_OBJECT_MISSING, LOCATION),
                F(C.COMPLETION_WITHOUT_VERIFIED_OUTPUT, JOB),
            ),
        )
        with self.subTest('completions empty'):
            self.assertEqual(
                reconcile(base(cloud_objects=(), completions=())),
                (F(C.CLOUD_OBJECT_MISSING, LOCATION),),
            )

    def test_hash_mismatch(self):
        result = reconcile(
            base(cloud_objects=(CloudObjectObservation(PROVIDER_REF, OTHER_SHA, SIZE),))
        )
        self.assertEqual(
            result,
            (
                F(C.COMPLETION_WITHOUT_VERIFIED_OUTPUT, JOB),
                F(C.HASH_MISMATCH, LOCATION),
            ),
        )
        with self.subTest('completions empty'):
            self.assertEqual(
                reconcile(
                    base(
                        cloud_objects=(CloudObjectObservation(PROVIDER_REF, OTHER_SHA, SIZE),),
                        completions=(),
                    )
                ),
                (F(C.HASH_MISMATCH, LOCATION),),
            )
        with self.subTest('size mismatch and completions empty'):
            self.assertEqual(
                reconcile(
                    base(
                        cloud_objects=(CloudObjectObservation(PROVIDER_REF, SHA, SIZE + 1),),
                        completions=(),
                    )
                ),
                (F(C.HASH_MISMATCH, LOCATION),),
            )

    def test_orphan_provider_object(self):
        obs = (
            CloudObjectObservation(PROVIDER_REF, SHA, SIZE),
            CloudObjectObservation(ORPHAN_REF, SHA, SIZE),
        )
        self.assertEqual(
            reconcile(base(cloud_objects=obs)),
            (F(C.ORPHAN_PROVIDER_OBJECT, ORPHAN_REF),),
        )

    def test_duplicate_provider_object_is_reported_not_deleted(self):
        locs = (
            CloudLocationRecord(LOCATION, VERSION, PROVIDER_REF),
            CloudLocationRecord('loc-dup', VERSION, PROVIDER_REF),
        )
        self.assertEqual(
            reconcile(base(cloud_locations=locs)),
            (F(C.DUPLICATE_PROVIDER_OBJECT, PROVIDER_REF),),
        )
        with self.subTest('duplicate observations'):
            obs = (
                CloudObjectObservation(PROVIDER_REF, SHA, SIZE),
                CloudObjectObservation(PROVIDER_REF, SHA, SIZE),
            )
            self.assertEqual(
                reconcile(base(cloud_objects=obs)),
                (F(C.DUPLICATE_PROVIDER_OBJECT, PROVIDER_REF),),
            )
        snapshot = base(cloud_locations=locs)
        before = copy.deepcopy(snapshot)
        result = reconcile(snapshot)
        for finding in result:
            self.assertIsNone(finding.action)
        self.assertEqual(snapshot, before)

    def test_journal_generation_mismatch(self):
        self.assertEqual(
            reconcile(base(stage_generations=types.MappingProxyType({OP_KEY: GEN + 1}))),
            (F(C.JOURNAL_GENERATION_MISMATCH, OP_KEY),),
        )
        with self.subTest('stage_generations empty'):
            self.assertEqual(
                reconcile(base(stage_generations=types.MappingProxyType({}))),
                (F(C.JOURNAL_GENERATION_MISMATCH, OP_KEY),),
            )

    def test_stale_epoch_entry_same_generation_is_stale(self):
        entries = (JournalEntry(OP_KEY, VERSION, GEN, OLD_EPOCH),)
        self.assertEqual(
            reconcile(base(journal_entries=entries)),
            (F(C.STALE_EPOCH_ENTRY, OP_KEY, REISSUE),),
        )

    def test_stale_epoch_entry_other_generation_is_only_stale(self):
        entries = (JournalEntry(OP_KEY, VERSION, GEN + 5, OLD_EPOCH),)
        self.assertEqual(
            reconcile(base(journal_entries=entries)),
            (F(C.STALE_EPOCH_ENTRY, OP_KEY, REISSUE),),
        )

    def test_completion_without_verified_output(self):
        cases = [
            (
                'missing location',
                {'completions': (CompletionRecord(JOB, VERSION, SHA, 'missing-loc'),)},
            ),
            (
                'different hash',
                {'completions': (CompletionRecord(JOB, VERSION, OTHER_SHA, LOCATION),)},
            ),
            (
                'different version',
                {'completions': (CompletionRecord(JOB, 'other-version', SHA, LOCATION),)},
            ),
            (
                'missing version in snapshot',
                {'versions': ()},
            ),
            (
                'location points to other version',
                {
                    'cloud_locations': (CloudLocationRecord(LOCATION, 'other-version', PROVIDER_REF),),
                    'versions': (
                        VersionRecord(VERSION, SHA, SIZE),
                        VersionRecord('other-version', SHA, SIZE),
                    ),
                },
            ),
        ]
        for name, overrides in cases:
            with self.subTest(name):
                self.assertEqual(
                    reconcile(base(**overrides)),
                    (F(C.COMPLETION_WITHOUT_VERIFIED_OUTPUT, JOB),),
                )

    def test_only_stale_finding_carries_reissue_action(self):
        snapshot = _make_all_discrepancies_snapshot()
        result = reconcile(snapshot)
        self.assertEqual({f.code for f in result}, set(ReconcileCode))
        for finding in result:
            if finding.code == C.STALE_EPOCH_ENTRY:
                self.assertEqual(finding.action, REISSUE)
            else:
                self.assertIsNone(finding.action)

    def test_result_is_sorted_and_input_order_independent(self):
        snapshot = _make_all_discrepancies_snapshot()
        result = reconcile(snapshot)
        self.assertEqual(
            result,
            tuple(sorted(result, key=lambda f: (f.code.value, f.ref))),
        )
        reversed_snapshot = dataclasses.replace(
            snapshot,
            versions=tuple(reversed(snapshot.versions)),
            cloud_locations=tuple(reversed(snapshot.cloud_locations)),
            cloud_objects=tuple(reversed(snapshot.cloud_objects)),
            journal_entries=tuple(reversed(snapshot.journal_entries)),
            completions=tuple(reversed(snapshot.completions)),
        )
        self.assertEqual(reconcile(reversed_snapshot), result)

    def test_pure_and_deterministic(self):
        snapshot = base(cloud_objects=())
        before = copy.deepcopy(snapshot)
        r1 = reconcile(snapshot)
        r2 = reconcile(snapshot)
        self.assertEqual(r1, r2)
        self.assertEqual(snapshot, before)
        self.assertIsInstance(r1, tuple)
        self.assertTrue(r1)

    def test_finding_is_frozen(self):
        finding = F(C.CLOUD_OBJECT_MISSING, 'loc-1')
        with self.assertRaises(dataclasses.FrozenInstanceError):
            finding.code = C.HASH_MISMATCH  # type: ignore[misc]
