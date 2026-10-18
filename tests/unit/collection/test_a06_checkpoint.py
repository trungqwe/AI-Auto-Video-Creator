"""A-06: CollectionCheckpoint advances only over durably committed items.

coveredIds: A-RULE-009
"""
import dataclasses
import unittest

from source_ingestion.domain.checkpoint import (
    AdapterCheckpointSemantics,
    CheckpointCompleteness,
    CheckpointRejected,
    CollectionCheckpoint,
    advance_checkpoint,
    compute_checkpoint_fingerprint,
    ensure_checkpoint_loadable,
    seal_checkpoint,
)

REQUIRED_FIELDS = frozenset({
    'checkpoint_version', 'revision', 'source_id', 'source_revision', 'adapter_type', 'adapter_revision',
    'cursor', 'item_ids', 'run_id', 'attempt_id', 'execution_generation', 'completeness', 'recorded_at',
    'fingerprint',
})
SEMANTICS_V1 = AdapterCheckpointSemantics(adapter_type='rss_feed', adapter_revision='adapter-r1', checkpoint_version=1)
SEMANTICS_V2 = AdapterCheckpointSemantics(adapter_type='rss_feed', adapter_revision='adapter-r2', checkpoint_version=2)


def base_fields(**overrides: object) -> dict[str, object]:
    fields: dict[str, object] = {
        'checkpoint_version': 1,
        'revision': 1,
        'source_id': 'src-1',
        'source_revision': 1,
        'adapter_type': 'rss_feed',
        'adapter_revision': 'adapter-r1',
        'cursor': 'cursor-0',
        'item_ids': (),
        'run_id': 'run-1',
        'attempt_id': 'attempt-1',
        'execution_generation': 1,
        'completeness': CheckpointCompleteness.PARTIAL,
        'recorded_at': '2026-10-18T00:00:00Z',
        'fingerprint': 'sha256:unsealed',
    }
    fields.update(overrides)
    return fields


def make_checkpoint(**overrides: object) -> CollectionCheckpoint:
    return seal_checkpoint(CollectionCheckpoint(**base_fields(**overrides)))


class CheckpointShapeTests(unittest.TestCase):
    def test_checkpoint_declares_required_fields(self) -> None:
        self.assertEqual({f.name for f in dataclasses.fields(CollectionCheckpoint)}, REQUIRED_FIELDS)

    def test_fingerprint_is_deterministic_sha256(self) -> None:
        first = make_checkpoint()
        self.assertEqual(first.fingerprint, make_checkpoint().fingerprint)
        self.assertEqual(first.fingerprint, compute_checkpoint_fingerprint(first))
        self.assertRegex(first.fingerprint, r'^sha256:[0-9a-f]{64}$')
        self.assertNotEqual(first.fingerprint, make_checkpoint(cursor='cursor-9').fingerprint)

    def test_invalid_construction_rejected(self) -> None:
        for overrides in (
            {'source_id': ''},
            {'cursor': ''},
            {'run_id': ''},
            {'fingerprint': ''},
            {'checkpoint_version': 0},
            {'revision': 0},
            {'execution_generation': -1},
            {'execution_generation': True},
            {'item_ids': ['i-1']},
            {'item_ids': ('',)},
            {'item_ids': ('i-1', 'i-1')},
            {'completeness': 'PARTIAL'},
        ):
            with self.subTest(overrides=overrides):
                with self.assertRaises(CheckpointRejected) as ctx:
                    CollectionCheckpoint(**base_fields(**overrides))
                self.assertEqual(ctx.exception.code, 'CHECKPOINT_INVALID')


class AdvanceDurabilityTests(unittest.TestCase):
    """Counterexample: checkpoint passes over an item whose unit of work has not committed."""

    def setUp(self) -> None:
        self.current = make_checkpoint()
        self.proposed = make_checkpoint(revision=2, cursor='cursor-2', item_ids=('i-1', 'i-2'))

    def test_advance_over_durable_items_returns_proposed(self) -> None:
        self.assertIs(advance_checkpoint(self.current, {'i-0', 'i-1', 'i-2'}, self.proposed), self.proposed)

    def test_advance_rejects_item_not_durably_committed(self) -> None:
        with self.assertRaises(CheckpointRejected) as ctx:
            advance_checkpoint(self.current, {'i-1'}, self.proposed)
        self.assertEqual(ctx.exception.code, 'CHECKPOINT_ITEM_NOT_DURABLE')
        self.assertIn('i-2', str(ctx.exception))
        self.assertEqual(self.current.cursor, 'cursor-0')

    def test_first_checkpoint_requires_durable_items(self) -> None:
        first = make_checkpoint(item_ids=('i-1',))
        with self.assertRaises(CheckpointRejected) as ctx:
            advance_checkpoint(None, set(), first)
        self.assertEqual(ctx.exception.code, 'CHECKPOINT_ITEM_NOT_DURABLE')
        self.assertIs(advance_checkpoint(None, ['i-1'], first), first)

    def test_durable_ids_must_be_a_collection(self) -> None:
        proposed = make_checkpoint(revision=2, item_ids=('i',))
        with self.assertRaises(CheckpointRejected) as ctx:
            advance_checkpoint(self.current, 'i-1', proposed)
        self.assertEqual(ctx.exception.code, 'CHECKPOINT_INVALID')

    def test_tampered_proposed_is_rejected(self) -> None:
        tampered = dataclasses.replace(self.proposed, cursor='cursor-99')
        with self.assertRaises(CheckpointRejected) as ctx:
            advance_checkpoint(self.current, {'i-1', 'i-2'}, tampered)
        self.assertEqual(ctx.exception.code, 'CHECKPOINT_FINGERPRINT_MISMATCH')


class SemanticsVersionTests(unittest.TestCase):
    """Counterexample: a checkpoint written under old cursor semantics is loaded by a new adapter."""

    def test_old_checkpoint_rejected_by_new_adapter_semantics(self) -> None:
        with self.assertRaises(CheckpointRejected) as ctx:
            ensure_checkpoint_loadable(make_checkpoint(), source_id='src-1', semantics=SEMANTICS_V2)
        self.assertEqual(ctx.exception.code, 'CHECKPOINT_VERSION_MISMATCH')

    def test_same_semantics_loads_across_adapter_revisions(self) -> None:
        stored = make_checkpoint()
        self.assertIs(ensure_checkpoint_loadable(stored, source_id='src-1', semantics=SEMANTICS_V1), stored)
        patched = AdapterCheckpointSemantics(adapter_type='rss_feed', adapter_revision='adapter-r3', checkpoint_version=1)
        self.assertIs(ensure_checkpoint_loadable(stored, source_id='src-1', semantics=patched), stored)

    def test_loader_rejects_other_source_adapter_or_tampering(self) -> None:
        stored = make_checkpoint()
        web = AdapterCheckpointSemantics(adapter_type='web_page', adapter_revision='adapter-r1', checkpoint_version=1)
        cases = (
            (stored, 'src-2', SEMANTICS_V1, 'CHECKPOINT_SOURCE_MISMATCH'),
            (stored, 'src-1', web, 'CHECKPOINT_ADAPTER_MISMATCH'),
            (dataclasses.replace(stored, cursor='cursor-x'), 'src-1', SEMANTICS_V1, 'CHECKPOINT_FINGERPRINT_MISMATCH'),
        )
        for checkpoint, source_id, semantics, code in cases:
            with self.subTest(code=code):
                with self.assertRaises(CheckpointRejected) as ctx:
                    ensure_checkpoint_loadable(checkpoint, source_id=source_id, semantics=semantics)
                self.assertEqual(ctx.exception.code, code)

    def test_advance_rejects_lineage_change(self) -> None:
        current = make_checkpoint()
        for overrides, code in (
            ({'checkpoint_version': 2, 'adapter_revision': 'adapter-r2'}, 'CHECKPOINT_VERSION_MISMATCH'),
            ({'adapter_type': 'web_page'}, 'CHECKPOINT_ADAPTER_MISMATCH'),
            ({'source_id': 'src-2'}, 'CHECKPOINT_SOURCE_MISMATCH'),
        ):
            proposed = make_checkpoint(revision=2, item_ids=('i-1',), **overrides)
            with self.subTest(code=code):
                with self.assertRaises(CheckpointRejected) as ctx:
                    advance_checkpoint(current, {'i-1'}, proposed)
                self.assertEqual(ctx.exception.code, code)


class GenerationFencingTests(unittest.TestCase):
    """Counterexample: a worker from an older execution generation pushes the checkpoint."""

    def setUp(self) -> None:
        self.current = make_checkpoint(revision=4, execution_generation=3, item_ids=('i-8',))

    def test_stale_generation_cannot_advance(self) -> None:
        stale = make_checkpoint(revision=5, execution_generation=2, cursor='cursor-9', item_ids=('i-9',))
        with self.assertRaises(CheckpointRejected) as ctx:
            advance_checkpoint(self.current, {'i-8', 'i-9'}, stale)
        self.assertEqual(ctx.exception.code, 'CHECKPOINT_STALE_GENERATION')

    def test_same_or_newer_generation_advances(self) -> None:
        for generation in (3, 4):
            proposed = make_checkpoint(revision=5, execution_generation=generation, item_ids=('i-9',))
            with self.subTest(generation=generation):
                self.assertIs(advance_checkpoint(self.current, {'i-9'}, proposed), proposed)

    def test_revision_must_follow_current(self) -> None:
        for revision in (4, 6):
            proposed = make_checkpoint(revision=revision, execution_generation=3, item_ids=('i-9',))
            with self.subTest(revision=revision):
                with self.assertRaises(CheckpointRejected) as ctx:
                    advance_checkpoint(self.current, {'i-9'}, proposed)
                self.assertEqual(ctx.exception.code, 'CHECKPOINT_REVISION_CONFLICT')
        first = make_checkpoint(revision=2)
        with self.assertRaises(CheckpointRejected) as ctx:
            advance_checkpoint(None, set(), first)
        self.assertEqual(ctx.exception.code, 'CHECKPOINT_REVISION_CONFLICT')
