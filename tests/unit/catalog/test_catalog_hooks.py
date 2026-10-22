"""C-05: visual and audio hook library with revision history (CT-HOOK-001, CT-HOOK-002)."""
import dataclasses
import inspect
import json
import pathlib
import re
import unittest
from datetime import datetime, timedelta, timezone

import catalog.application.hooks as hooks_app
import catalog.domain.hooks as hooks_domain
from catalog.application.hooks import HookHistory, import_hook, update_hook_metadata
from catalog.domain.hooks import HookKind, HookRevision
from catalog.domain.identity import ProvenanceRelation
from controlplane.domain.concurrency import RevisionConflictError

ROOT = pathlib.Path(__file__).resolve().parents[3]
FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'i-artifact-version' / 'payloads.json'
EXPECTED_FIELDS = {'hook_id', 'revision', 'kind', 'artifact_version_ref', 'tags', 'description', 'note', 'enabled', 'technical_metadata', 'provenance'}


def fixture_artifact_version_ref() -> str:
    data = json.loads(FIXTURE.read_text(encoding='utf-8'))
    return str(data['entities']['DeclareArtifactVersionResult']['valid'][0]['artifact_version_id'])


def import_sample(
    history: HookHistory,
    hook_id: str = 'hook-visual-1',
    kind: HookKind = HookKind.VISUAL_HOOK,
) -> HookRevision:
    return import_hook(
        history,
        hook_id=hook_id,
        kind=kind,
        artifact_version_ref=fixture_artifact_version_ref(),
        tags=('intro',),
        description='original description',
        note='original note',
        enabled=True,
        technical_metadata=(('duration_ms', '3000'),),
    )


class FakeClock:
    """Clock that advances one second per call, starting 2026-10-22T01:00:00.123456Z."""

    def __init__(self) -> None:
        self._moment = datetime(2026, 10, 22, 1, 0, 0, 123456, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        moment = self._moment
        self._moment += timedelta(seconds=1)
        return moment


class HookKindTests(unittest.TestCase):
    def test_value_set(self) -> None:
        self.assertEqual({k.value for k in HookKind}, {'visual_hook', 'audio_hook'})


class HookRevisionTests(unittest.TestCase):
    def test_fields_have_no_pairing_field(self) -> None:
        self.assertEqual({f.name for f in dataclasses.fields(HookRevision)}, EXPECTED_FIELDS)

    def test_revision_is_frozen(self) -> None:
        rev = import_sample(HookHistory())
        for name in sorted(EXPECTED_FIELDS):
            with self.subTest(field=name):
                with self.assertRaises(dataclasses.FrozenInstanceError):
                    setattr(rev, name, getattr(rev, name))

    def test_provenance_is_fixed_user_imported(self) -> None:
        rev = import_sample(HookHistory())
        self.assertIs(rev.provenance, ProvenanceRelation.USER_IMPORTED)
        with self.assertRaises(ValueError):
            dataclasses.replace(rev, provenance=ProvenanceRelation.HERO_IMAGE)

    def test_rejects_invalid_values(self) -> None:
        rev = import_sample(HookHistory())
        invalid_cases = (
            {'hook_id': ''},
            {'revision': 0},
            {'revision': True},
            {'kind': 'visual_hook'},
            {'artifact_version_ref': ''},
            {'tags': ['intro']},
            {'enabled': 'yes'},
            {'technical_metadata': (('duration_ms',),)},
        )
        for overrides in invalid_cases:
            with self.subTest(overrides=overrides):
                with self.assertRaises(ValueError):
                    dataclasses.replace(rev, **overrides)


class ImportHookTests(unittest.TestCase):
    def test_import_creates_revision_one_for_each_kind(self) -> None:
        for kind in HookKind:
            with self.subTest(kind=kind):
                history = HookHistory()
                rev = import_sample(history, f'hook-{kind.value}', kind)
                self.assertEqual(rev.revision, 1)
                self.assertEqual(rev.kind, kind)
                self.assertIs(rev.provenance, ProvenanceRelation.USER_IMPORTED)
                self.assertEqual(rev.artifact_version_ref, fixture_artifact_version_ref())
                self.assertIs(history.get(rev.hook_id, 1), rev)
                self.assertIs(history.latest(rev.hook_id), rev)

    def test_import_signature_has_no_provenance_revision_or_pairing(self) -> None:
        params = inspect.signature(import_hook).parameters
        self.assertNotIn('provenance', params)
        self.assertNotIn('revision', params)
        self.assertEqual([n for n in params if 'pair' in n], [])

    def test_import_existing_hook_id_is_rejected(self) -> None:
        history = HookHistory()
        first = import_sample(history)
        with self.assertRaises(RevisionConflictError) as ctx:
            import_sample(history)
        self.assertEqual(ctx.exception.current_revision, 1)
        self.assertIs(history.latest('hook-visual-1'), first)
        with self.assertRaises(KeyError):
            history.get('hook-visual-1', 2)


class UpdateHookMetadataTests(unittest.TestCase):
    HOOK = 'hook-visual-1'

    def test_update_appends_next_revision_and_keeps_old(self) -> None:
        history = HookHistory()
        first = import_sample(history)
        second = update_hook_metadata(
            history,
            self.HOOK,
            1,
            tags=('intro', 'breaking'),
            description='edited description',
            note='edited note',
            enabled=False,
        )
        self.assertEqual(second.revision, 2)
        self.assertEqual(
            (second.tags, second.description, second.note, second.enabled),
            (('intro', 'breaking'), 'edited description', 'edited note', False),
        )
        self.assertIs(history.get(self.HOOK, 1), first)
        self.assertEqual(
            (first.revision, first.tags, first.description, first.note, first.enabled),
            (1, ('intro',), 'original description', 'original note', True),
        )
        self.assertIs(history.latest(self.HOOK), second)
        for name in ('hook_id', 'kind', 'artifact_version_ref', 'technical_metadata', 'provenance'):
            with self.subTest(field=name):
                self.assertEqual(getattr(second, name), getattr(first, name))
        third = update_hook_metadata(history, self.HOOK, 2, enabled=True)
        self.assertEqual(third.revision, 3)
        self.assertIs(history.get(self.HOOK, 2), second)
        self.assertIs(history.get(self.HOOK, 1), first)

    def test_unspecified_fields_are_kept(self) -> None:
        history = HookHistory()
        first = import_sample(history)
        second = update_hook_metadata(history, self.HOOK, 1, enabled=False)
        self.assertEqual(second.revision, 2)
        self.assertEqual(
            (second.tags, second.description, second.note),
            (first.tags, first.description, first.note),
        )
        self.assertFalse(second.enabled)

    def test_stale_or_future_expected_revision_raises_revision_conflict(self) -> None:
        history = HookHistory()
        import_sample(history)
        second = update_hook_metadata(history, self.HOOK, 1, note='second note')
        for stale in (1, 3):
            with self.subTest(stale=stale):
                with self.assertRaises(RevisionConflictError) as ctx:
                    update_hook_metadata(history, self.HOOK, stale, note='lost')
                self.assertEqual(ctx.exception.current_revision, 2)
                self.assertIs(history.latest(self.HOOK), second)
                with self.assertRaises(KeyError):
                    history.get(self.HOOK, 3)

    def test_signature_has_no_kind_or_artifact_parameter(self) -> None:
        sig = inspect.signature(update_hook_metadata)
        self.assertEqual(
            list(sig.parameters),
            ['history', 'hook_id', 'expected_revision', 'tags', 'description', 'note', 'enabled'],
        )
        for name in ('tags', 'description', 'note', 'enabled'):
            self.assertEqual(sig.parameters[name].kind, inspect.Parameter.KEYWORD_ONLY)
            self.assertIsNone(sig.parameters[name].default)

    def test_update_rejects_kind_and_artifact_keywords(self) -> None:
        history = HookHistory()
        first = import_sample(history)
        for kwargs in ({'kind': HookKind.AUDIO_HOOK}, {'artifact_version_ref': 'other-artifact'}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(TypeError):
                    update_hook_metadata(history, self.HOOK, 1, **kwargs)
        self.assertIs(history.latest(self.HOOK), first)

    def test_unknown_hook_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            update_hook_metadata(HookHistory(), 'missing', 1, note='x')
        with self.assertRaises(KeyError):
            HookHistory().latest('missing')
        with self.assertRaises(KeyError):
            HookHistory().get('missing', 1)


class HookIndependenceTests(unittest.TestCase):
    def test_visual_and_audio_are_imported_updated_and_read_independently(self) -> None:
        history = HookHistory()
        visual = import_sample(history, 'hook-visual-1', HookKind.VISUAL_HOOK)
        audio = import_sample(history, 'hook-audio-1', HookKind.AUDIO_HOOK)
        audio2 = update_hook_metadata(history, 'hook-audio-1', 1, tags=('calm',))
        self.assertIs(history.latest('hook-visual-1'), visual)
        visual2 = update_hook_metadata(history, 'hook-visual-1', 1, enabled=False)
        self.assertIs(history.latest('hook-audio-1'), audio2)
        self.assertEqual((visual2.revision, audio2.revision), (2, 2))
        self.assertEqual((visual2.kind, audio2.kind), (HookKind.VISUAL_HOOK, HookKind.AUDIO_HOOK))
        self.assertIs(history.get('hook-audio-1', 1), audio)
        self.assertIs(history.get('hook-visual-1', 1), visual)

    def test_audio_hook_alone_needs_no_visual(self) -> None:
        history = HookHistory()
        audio = import_sample(history, 'hook-audio-only', HookKind.AUDIO_HOOK)
        updated = update_hook_metadata(history, 'hook-audio-only', 1, enabled=False)
        self.assertEqual(updated.revision, 2)
        self.assertIs(history.get('hook-audio-only', 1), audio)
        with self.assertRaises(KeyError):
            history.latest('hook-visual-1')


class RevisionErrorReuseTests(unittest.TestCase):
    def test_revision_conflict_is_controlplane_class(self) -> None:
        self.assertIs(hooks_app.RevisionConflictError, RevisionConflictError)

    def test_no_exception_class_defined_in_hook_modules(self) -> None:
        for module in (hooks_domain, hooks_app):
            with self.subTest(module=module.__name__):
                defined = [
                    cls.__name__
                    for _, cls in inspect.getmembers(module, inspect.isclass)
                    if cls.__module__ == module.__name__ and issubclass(cls, BaseException)
                ]
                self.assertEqual(defined, [])


class HookHeadListingTests(unittest.TestCase):
    def test_list_heads_is_empty_without_hooks(self) -> None:
        self.assertEqual(HookHistory().list_heads(), [])

    def test_head_of_unknown_hook_raises_key_error(self) -> None:
        history = HookHistory()
        with self.assertRaises(KeyError):
            history.head('missing')
        import_sample(history, 'hook-1')
        with self.assertRaises(KeyError):
            history.head('missing')

    def test_list_heads_returns_latest_revision_per_hook_sorted_by_hook_id(self) -> None:
        history = HookHistory(clock=FakeClock())
        visual = import_sample(history, 'hook-visual-1', HookKind.VISUAL_HOOK)
        audio = import_sample(history, 'hook-audio-1', HookKind.AUDIO_HOOK)
        visual2 = update_hook_metadata(history, 'hook-visual-1', 1, enabled=False)
        heads = history.list_heads()
        self.assertEqual([h.revision.hook_id for h in heads], ['hook-audio-1', 'hook-visual-1'])
        self.assertIs(heads[0].revision, audio)
        self.assertIs(heads[1].revision, visual2)
        self.assertIsNot(heads[1].revision, visual)
        self.assertEqual([h.updated_at for h in heads], ['2026-10-22T01:00:01.123456Z', '2026-10-22T01:00:02.123456Z'])
        for head in heads:
            self.assertIsInstance(head, hooks_domain.HookHead)
            self.assertEqual(history.head(head.revision.hook_id), head)
        self.assertEqual(history.list_heads(), heads)

    def test_failed_append_keeps_updated_at(self) -> None:
        history = HookHistory(clock=FakeClock())
        import_sample(history)
        with self.assertRaises(RevisionConflictError):
            import_sample(history)
        self.assertEqual(history.head('hook-visual-1').updated_at, '2026-10-22T01:00:00.123456Z')

    def test_clock_with_offset_is_converted_to_utc(self) -> None:
        clock = lambda: datetime(2026, 10, 22, 8, 30, 15, 250000, tzinfo=timezone(timedelta(hours=7)))
        history = HookHistory(clock=clock)
        import_sample(history)
        self.assertEqual(history.head('hook-visual-1').updated_at, '2026-10-22T01:30:15.250000Z')

    def test_naive_clock_is_rejected_and_nothing_is_stored(self) -> None:
        clock = lambda: datetime(2026, 10, 22, 1, 0, 0)
        history = HookHistory(clock=clock)
        with self.assertRaises(ValueError):
            import_sample(history)
        self.assertEqual(history.list_heads(), [])
        with self.assertRaises(KeyError):
            history.latest('hook-visual-1')

    def test_default_history_without_arguments_still_works(self) -> None:
        history = HookHistory()
        import_sample(history)
        update_hook_metadata(history, 'hook-visual-1', 1, note='n')
        head = history.head('hook-visual-1')
        assert re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z', head.updated_at)
        assert head.revision.revision == 2

    def test_hook_head_validates_and_is_frozen(self) -> None:
        rev = import_sample(HookHistory())
        valid = hooks_domain.HookHead(revision=rev, updated_at='2026-10-22T01:00:00.000000Z')
        self.assertIs(valid.revision, rev)
        self.assertEqual(valid.updated_at, '2026-10-22T01:00:00.000000Z')
        with self.assertRaises(ValueError):
            hooks_domain.HookHead(revision='x', updated_at='2026-10-22T01:00:00.000000Z')
        with self.assertRaises(ValueError):
            hooks_domain.HookHead(revision=rev, updated_at='')
        with self.assertRaises(ValueError):
            hooks_domain.HookHead(revision=rev, updated_at=5)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            setattr(valid, 'updated_at', '2026-10-22T02:00:00.000000Z')
        self.assertEqual([f.name for f in dataclasses.fields(hooks_domain.HookHead)], ['revision', 'updated_at'])
        self.assertEqual({f.name for f in dataclasses.fields(HookRevision)}, EXPECTED_FIELDS)
