"""C-09: MediaUsageRecorder ghi usage trong unit of work của G (phần C của TST-WF-INV-010, TST-WF-INV-017)."""
import ast
import dataclasses
import json
import pathlib
import unittest

from catalog.application.usage import MediaUsageRecorder
from catalog.ports.usage import MediaUsageRecord, UsageKind
from controlplane.domain.interfaces.uow import IUnitOfWork

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_FILE = ROOT / 'src' / 'catalog' / 'application' / 'usage.py'
PORT_FILE = ROOT / 'src' / 'catalog' / 'ports' / 'usage.py'
FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'g-c-i-completion' / 'payloads.json'
ENTITIES = json.loads(FIXTURE.read_text(encoding='utf-8'))['entities']
REQUEST = ENTITIES['CommitVideoCompletionRequest']['valid'][0]
COMPLETION_ID = ENTITIES['CompletionLedgerEntry']['valid'][0]['completion_id']
OTHER_ASSET = '00000000-0000-4000-8000-000000000021'


class FakeStore:
    def __init__(self) -> None:
        self.committed: list[MediaUsageRecord] = []


class FakeUnitOfWork(IUnitOfWork):
    """Staging fake: rows reach ``store`` only on commit; rollback drops staging."""

    def __init__(self, store: FakeStore) -> None:
        self.store = store
        self.staged: list[MediaUsageRecord] = []
        self.commit_calls = 0
        self.rollback_calls = 0

    def begin(self) -> None:
        pass

    def commit(self) -> None:
        self.commit_calls += 1
        self.store.committed.extend(self.staged)
        self.staged = []

    def rollback(self) -> None:
        self.rollback_calls += 1
        self.staged = []

    def __enter__(self) -> 'FakeUnitOfWork':
        self.begin()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is None:
            self.commit()
        else:
            self.rollback()


class FakeUsageRepository:
    def __init__(self, uow: FakeUnitOfWork) -> None:
        self.uow = uow

    def exists(self, completion_id, media_asset_id, role, usage_kind) -> bool:
        key = (completion_id, media_asset_id, role, usage_kind)
        rows = self.uow.store.committed + self.uow.staged
        return any((r.completion_id, r.media_asset_id, r.role, r.usage_kind) == key for r in rows)

    def add(self, record) -> None:
        self.uow.staged.append(record)


class RecordingFactory:
    def __init__(self) -> None:
        self.calls: list[IUnitOfWork] = []

    def __call__(self, uow):
        self.calls.append(uow)
        return FakeUsageRepository(uow)


def production_count(store: FakeStore) -> int:
    return sum(1 for r in store.committed if r.usage_kind is UsageKind.production)


def make_request(**overrides: object) -> dict:
    request = json.loads(json.dumps(REQUEST))
    request.update(overrides)
    return request


def make_record(usage_kind: UsageKind = UsageKind.technical, **overrides: object) -> MediaUsageRecord:
    fields = {
        'completion_id': COMPLETION_ID,
        'video_job_id': REQUEST['video_job_id'],
        'media_asset_id': REQUEST['media_usage_manifest'][0]['media_asset_id'],
        'role': REQUEST['media_usage_manifest'][0]['role'],
        'usage_kind': usage_kind,
    }
    fields.update(overrides)
    return MediaUsageRecord(**fields)


class RecorderTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.store = FakeStore()
        self.uow = FakeUnitOfWork(self.store)
        self.factory = RecordingFactory()
        self.recorder = MediaUsageRecorder(self.factory)

    def record(self, uow=None, completion_id=COMPLETION_ID, request=None) -> int:
        return self.recorder.record_production_usage(uow or self.uow, completion_id, request if request is not None else make_request())


class UnitOfWorkTests(RecorderTestCase):
    def test_usage_is_invisible_before_commit(self) -> None:
        added = self.record()
        self.assertEqual(added, len(REQUEST['media_usage_manifest']))
        self.assertEqual(self.store.committed, [])
        self.assertEqual(len(self.uow.staged), added)

    def test_usage_is_visible_after_commit(self) -> None:
        self.record()
        self.uow.commit()
        self.assertEqual(production_count(self.store), len(REQUEST['media_usage_manifest']))

    def test_rollback_leaves_no_production_usage(self) -> None:
        self.record()
        self.uow.rollback()
        self.assertEqual(production_count(self.store), 0)
        self.assertEqual(self.store.committed, [])
        self.assertEqual(self.uow.staged, [])

    def test_recorder_never_calls_commit_or_rollback(self) -> None:
        self.record()
        self.record()
        self.recorder.record_technical_usage(self.uow, make_record())
        with self.assertRaises(ValueError):
            self.record(request={})
        self.assertEqual((self.uow.commit_calls, self.uow.rollback_calls), (0, 0))

    def test_repository_comes_from_factory_with_same_uow(self) -> None:
        self.record()
        self.recorder.record_technical_usage(self.uow, make_record())
        self.assertEqual(len(self.factory.calls), 2)
        self.assertTrue(all(call is self.uow for call in self.factory.calls))


class ReplayTests(RecorderTestCase):
    def test_replay_after_commit_does_not_increase_count(self) -> None:
        first = self.record()
        self.uow.commit()
        second = self.record()
        self.uow.commit()
        self.assertEqual((first, second), (len(REQUEST['media_usage_manifest']), 0))
        self.assertEqual(production_count(self.store), first)

    def test_replay_inside_same_uow_before_commit_adds_nothing(self) -> None:
        self.record()
        self.assertEqual(self.record(), 0)
        self.assertEqual(len(self.uow.staged), len(REQUEST['media_usage_manifest']))

    def test_replay_from_new_uow_adds_nothing(self) -> None:
        self.record()
        self.uow.commit()
        retry_uow = FakeUnitOfWork(self.store)
        self.assertEqual(self.record(uow=retry_uow), 0)
        self.assertEqual(retry_uow.staged, [])

    def test_new_completion_id_counts_again(self) -> None:
        self.record()
        self.record(completion_id='completion-2')
        self.uow.commit()
        self.assertEqual(production_count(self.store), 2 * len(REQUEST['media_usage_manifest']))

    def test_valid_fixture_payload_writes_every_manifest_element(self) -> None:
        manifest = [
            dict(REQUEST['media_usage_manifest'][0]),
            {'media_asset_id': OTHER_ASSET, 'role': 'broll', 'rendition_ref': 'rendition-1',
             'artifact_version_ref': 'artifact-1', 'selection_rationale': 'fits scene 2'},
        ]
        self.assertEqual(self.record(request=make_request(media_usage_manifest=manifest)), 2)
        self.uow.commit()
        rows = {r.media_asset_id: r for r in self.store.committed}
        self.assertEqual(set(rows), {manifest[0]['media_asset_id'], OTHER_ASSET})
        self.assertTrue(all(r.usage_kind is UsageKind.production for r in rows.values()))
        self.assertTrue(all(r.completion_id == COMPLETION_ID and r.video_job_id == REQUEST['video_job_id'] for r in rows.values()))
        self.assertIsNone(rows[manifest[0]['media_asset_id']].rendition_ref)
        self.assertEqual(rows[OTHER_ASSET].role, 'broll')
        self.assertEqual(rows[OTHER_ASSET].rendition_ref, 'rendition-1')
        self.assertEqual(rows[OTHER_ASSET].artifact_version_ref, 'artifact-1')
        self.assertEqual(rows[OTHER_ASSET].selection_rationale, 'fits scene 2')

    def test_duplicate_element_inside_manifest_counts_once(self) -> None:
        element = dict(REQUEST['media_usage_manifest'][0])
        self.assertEqual(self.record(request=make_request(media_usage_manifest=[element, dict(element)])), 1)

    def test_empty_manifest_adds_nothing(self) -> None:
        self.assertEqual(self.record(request=make_request(media_usage_manifest=[])), 0)
        self.assertEqual(self.uow.staged, [])


class ValidationTests(RecorderTestCase):
    def assert_contract_error(self, request: dict, code: str, field: str) -> None:
        with self.assertRaises(ValueError) as ctx:
            self.record(request=request)
        self.assertEqual(ctx.exception.code, code)
        self.assertEqual(ctx.exception.field, field)
        self.assertEqual(self.uow.staged, [])

    def test_missing_required_top_level_fields(self) -> None:
        for field in ('video_job_id', 'media_usage_manifest'):
            with self.subTest(field=field):
                request = make_request()
                request.pop(field)
                self.assert_contract_error(request, 'missing_required', field)

    def test_manifest_element_missing_asset_or_role_stages_nothing(self) -> None:
        for field in ('media_asset_id', 'role'):
            with self.subTest(field=field):
                bad = {'media_asset_id': OTHER_ASSET, 'role': 'broll'}
                bad.pop(field)
                manifest = [dict(REQUEST['media_usage_manifest'][0]), bad]
                self.assert_contract_error(make_request(media_usage_manifest=manifest), 'missing_required', f'media_usage_manifest[1].{field}')

    def test_wrong_types_are_rejected(self) -> None:
        cases = (
            (make_request(video_job_id=7), 'video_job_id'),
            (make_request(media_usage_manifest={}), 'media_usage_manifest'),
            (make_request(media_usage_manifest=['x']), 'media_usage_manifest[0]'),
        )
        for request, field in cases:
            with self.subTest(field=field):
                self.assert_contract_error(request, 'wrong_type', field)

    def test_empty_video_job_id_is_invalid_value(self) -> None:
        self.assert_contract_error(make_request(video_job_id=''), 'invalid_value', 'video_job_id')


class TechnicalUsageTests(RecorderTestCase):
    def test_technical_usage_does_not_count_as_production(self) -> None:
        self.assertTrue(self.recorder.record_technical_usage(self.uow, make_record()))
        self.uow.commit()
        self.assertEqual(production_count(self.store), 0)
        self.assertEqual([r.usage_kind for r in self.store.committed], [UsageKind.technical])

    def test_technical_replay_adds_nothing(self) -> None:
        self.assertTrue(self.recorder.record_technical_usage(self.uow, make_record()))
        self.assertFalse(self.recorder.record_technical_usage(self.uow, make_record()))
        self.assertEqual(len(self.uow.staged), 1)

    def test_technical_and_production_are_separate_kinds(self) -> None:
        self.recorder.record_technical_usage(self.uow, make_record())
        self.assertEqual(self.record(), 1)
        self.uow.commit()
        self.assertEqual(production_count(self.store), 1)
        self.assertEqual(len(self.store.committed), 2)

    def test_production_kind_is_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            self.recorder.record_technical_usage(self.uow, make_record(UsageKind.production))
        self.assertEqual((ctx.exception.code, ctx.exception.field), ('invalid_value', 'usage_kind'))
        self.assertEqual(self.uow.staged, [])

    def test_non_record_is_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            self.recorder.record_technical_usage(self.uow, {'role': 'illustration'})
        self.assertEqual((ctx.exception.code, ctx.exception.field), ('wrong_type', 'record'))
        self.assertEqual(self.uow.staged, [])


class RecordTests(unittest.TestCase):
    def test_record_is_frozen(self) -> None:
        with self.assertRaises(dataclasses.FrozenInstanceError):
            make_record().role = 'other'

    def test_record_rejects_empty_required_fields(self) -> None:
        for field in ('completion_id', 'video_job_id', 'media_asset_id', 'role'):
            with self.subTest(field=field), self.assertRaises(ValueError):
                make_record(**{field: ''})

    def test_record_rejects_plain_string_usage_kind(self) -> None:
        with self.assertRaises(ValueError):
            make_record(usage_kind='technical')

    def test_optional_fields_default_to_none(self) -> None:
        record = make_record()
        self.assertEqual((record.rendition_ref, record.artifact_version_ref, record.selection_rationale), (None, None, None))


def imported_modules(path: pathlib.Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


class BoundaryTests(unittest.TestCase):
    def test_recorder_source_never_calls_begin_commit_or_rollback(self) -> None:
        tree = ast.parse(MODULE_FILE.read_text(encoding='utf-8'))
        called = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        self.assertEqual(called & {'begin', 'commit', 'rollback'}, set())

    def test_import_boundary(self) -> None:
        recorder_imports = imported_modules(MODULE_FILE)
        port_imports = imported_modules(PORT_FILE)
        self.assertEqual({m for m in recorder_imports if m.startswith('controlplane')}, {'controlplane.domain.interfaces.uow'})
        self.assertEqual({m for m in port_imports if m.startswith('controlplane')}, set())
        for module in recorder_imports | port_imports:
            self.assertFalse(module.startswith(('src.', 'psycopg')), module)
