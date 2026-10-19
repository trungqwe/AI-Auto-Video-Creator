"""F-02: RenderPresetRevision, preset_fingerprint and PresetCatalog (CT-RND-001).

coveredIds: CT-RND-001, docs/10-test-strategy.md section 12.6
"""
import ast
import dataclasses
import pathlib
import re
import unittest
from unittest import mock

from controlplane.application.idempotency.canonicalization import request_hash
from render.domain.preset import (
    INPUT_FIELDS,
    PresetCatalog,
    PresetNotFoundError,
    PresetValidationError,
    RenderPresetRevision,
    build_preset_revision,
    completeness_issue,
    compute_preset_fingerprint,
    is_complete,
    resolve_preset,
    verify_preset_fingerprint,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
PRESET_SOURCE = ROOT / 'src' / 'render' / 'domain' / 'preset.py'
SECTIONS = (
    'visual_rhythm', 'layout_rules', 'thumbnail_overlay_style', 'typography_karaoke_style',
    'hook_treatment', 'mix_rules', 'color_effect_rules', 'fallback_constraints', 'compatibility_requirements',
)
TEXT = ('preset_key', 'output_profile_ref')
NAMES = ('preset_key', 'revision', *SECTIONS, 'output_profile_ref')
ZERO = '0' * 64


# GIẢ ĐỊNH: fixture-preset-1..5 là dữ liệu test-only, không phải tên hay style preset thật (ROADMAP-OPEN-009).
def section_payload(index, name):
    return {'fixture_marker': f'{name}-{index}', 'fixture_items': [index, {'inner': index}], 'fixture_flag': True}


def preset_payload(index, revision=1):
    payload = {name: section_payload(index, name) for name in SECTIONS}
    payload.update(preset_key=f'fixture-preset-{index}', revision=revision, output_profile_ref=f'fixture-profile-{index}')
    return payload


def make_preset(index, revision=1, **overrides):
    return build_preset_revision(preset_payload(index, revision) | overrides)


def make_catalog(count):
    catalog = PresetCatalog()
    for index in range(1, count + 1):
        catalog = catalog.add_revision(make_preset(index))
    return catalog


class PresetTestCase(unittest.TestCase):
    def assertRejected(self, code, field, func, *args, **kwargs):
        with self.assertRaises(PresetValidationError) as caught:
            func(*args, **kwargs)
        self.assertEqual((caught.exception.code, caught.exception.field), (code, field))


class RevisionValueTests(PresetTestCase):
    def test_build_sets_all_thirteen_fields(self):
        preset = make_preset(1)
        self.assertEqual(set(INPUT_FIELDS), set(NAMES))
        self.assertEqual({f.name for f in dataclasses.fields(preset)}, {*NAMES, 'preset_fingerprint'})
        self.assertEqual((preset.preset_key, preset.revision), ('fixture-preset-1', 1))
        self.assertRegex(preset.preset_fingerprint, r'[0-9a-f]{64}')
        verify_preset_fingerprint(preset)

    def test_preset_is_frozen_and_deeply_read_only(self):
        preset = make_preset(1)
        for name, value in (('revision', 2), ('preset_key', 'x'), ('preset_fingerprint', ZERO), ('visual_rhythm', {})):
            with self.subTest(name=name), self.assertRaises(dataclasses.FrozenInstanceError):
                setattr(preset, name, value)
        with self.assertRaises(TypeError):
            preset.visual_rhythm['fixture_marker'] = 'x'
        items = preset.visual_rhythm['fixture_items']
        self.assertIsInstance(items, tuple)
        with self.assertRaises(TypeError):
            items[1]['inner'] = 9
        verify_preset_fingerprint(preset)

    def test_later_change_to_source_payload_does_not_change_preset(self):
        payload = preset_payload(1)
        preset = build_preset_revision(payload)
        payload['visual_rhythm']['fixture_marker'] = 'changed'
        payload['visual_rhythm']['fixture_items'].append(3)
        self.assertEqual(preset.visual_rhythm['fixture_marker'], 'visual_rhythm-1')
        self.assertEqual(len(preset.visual_rhythm['fixture_items']), 2)
        verify_preset_fingerprint(preset)

    def test_equality_and_hash(self):
        self.assertEqual(make_preset(1), make_preset(1))
        self.assertEqual(hash(make_preset(1)), hash(make_preset(1)))
        self.assertNotEqual(make_preset(1), make_preset(2))
        self.assertNotEqual(make_preset(1), make_preset(1, 2))
        self.assertEqual(len({make_preset(1), make_preset(1), make_preset(2)}), 2)


class RevisionValidationTests(PresetTestCase):
    def test_revision_must_be_integer_at_least_one(self):
        for good in (1, 2, 10):
            self.assertEqual(make_preset(1, good).revision, good)
        cases = ((0, 'invalid_value'), (-1, 'invalid_value'), (True, 'wrong_type'), (False, 'wrong_type'), ('1', 'wrong_type'), (1.0, 'wrong_type'), (None, 'missing_required'))
        for bad, code in cases:
            with self.subTest(bad=bad):
                self.assertRejected(code, 'revision', make_preset, 1, bad)

    def test_missing_part_is_rejected_with_field(self):
        for name in NAMES:
            absent = preset_payload(1)
            del absent[name]
            with self.subTest(name=name, case='absent'):
                self.assertRejected('missing_required', name, build_preset_revision, absent)
            blanks = [None] if name == 'revision' else [None, {} if name in SECTIONS else ' ']
            for blank in blanks:
                with self.subTest(name=name, blank=blank):
                    self.assertRejected('missing_required', name, build_preset_revision, preset_payload(1) | {name: blank})

    def test_wrong_typed_or_unusable_part_is_rejected(self):
        cases = (
            ('visual_rhythm', ['x'], 'wrong_type'), ('layout_rules', 'x', 'wrong_type'), ('mix_rules', {1: 'x'}, 'wrong_type'),
            ('hook_treatment', {'a': {'x', 'y'}}, 'wrong_type'), ('color_effect_rules', {'a': float('nan')}, 'invalid_value'),
            ('preset_key', 5, 'wrong_type'), ('output_profile_ref', 5, 'wrong_type'),
        )
        for name, value, code in cases:
            with self.subTest(name=name):
                self.assertRejected(code, name, build_preset_revision, preset_payload(1) | {name: value})
        self.assertRejected('wrong_type', 'payload', build_preset_revision, ['x'])

    def test_from_payload_requires_all_thirteen_fields_and_matching_fingerprint(self):
        preset = make_preset(1)
        data = {f.name: getattr(preset, f.name) for f in dataclasses.fields(preset)}
        self.assertEqual(RenderPresetRevision.from_payload(data), preset)
        load = RenderPresetRevision.from_payload
        self.assertRejected('missing_required', 'preset_fingerprint', load, {k: v for k, v in data.items() if k != 'preset_fingerprint'})
        self.assertRejected('missing_required', 'layout_rules', load, {k: v for k, v in data.items() if k != 'layout_rules'})
        self.assertRejected('invalid_value', 'preset_fingerprint', load, data | {'preset_fingerprint': 'abc'})
        self.assertRejected('preset_fingerprint_mismatch', 'preset_fingerprint', load, data | {'preset_fingerprint': ZERO})
        self.assertRejected('wrong_type', 'payload', load, ['x'])


def reorder(value):
    if isinstance(value, dict):
        return {key: reorder(item) for key, item in reversed(list(value.items()))}
    if isinstance(value, list):
        return [reorder(item) for item in value]
    return value


class FingerprintTests(PresetTestCase):
    def test_fingerprint_is_request_hash_of_every_other_field(self):
        payload = preset_payload(1)
        self.assertEqual(set(payload), set(NAMES))
        self.assertEqual(make_preset(1).preset_fingerprint, request_hash(payload))

    def test_fingerprint_delegates_to_request_hash_without_own_field(self):
        with mock.patch('render.domain.preset.request_hash', return_value='f' * 64) as patched:
            preset = make_preset(1)
        self.assertEqual(preset.preset_fingerprint, 'f' * 64)
        self.assertEqual(set(patched.call_args.args[0]), set(NAMES))

    def test_key_order_does_not_change_fingerprint(self):
        reordered = build_preset_revision(reorder(preset_payload(1)))
        self.assertEqual(reordered.preset_fingerprint, make_preset(1).preset_fingerprint)

    def test_changing_any_field_changes_fingerprint(self):
        seen = {make_preset(1).preset_fingerprint}
        for name in NAMES:
            payload = preset_payload(1)
            if name == 'revision':
                payload[name] = 2
            elif name in TEXT:
                payload[name] += '-changed'
            else:
                payload[name] = payload[name] | {'fixture_flag': False}
            seen.add(build_preset_revision(payload).preset_fingerprint)
        self.assertEqual(len(seen), len(NAMES) + 1)
        for nested in ({'fixture_items': [1, {'inner': 9}]}, {'fixture_extra': 1}):
            payload = preset_payload(1)
            payload['mix_rules'] = payload['mix_rules'] | nested
            self.assertNotIn(build_preset_revision(payload).preset_fingerprint, seen)

    def test_builder_ignores_supplied_fingerprint_key(self):
        self.assertEqual(build_preset_revision(preset_payload(1) | {'preset_fingerprint': ZERO}), make_preset(1))

    def test_compute_accepts_object_and_mapping(self):
        preset = make_preset(1)
        self.assertEqual(compute_preset_fingerprint(preset), preset.preset_fingerprint)
        self.assertEqual(compute_preset_fingerprint(preset_payload(1)), preset.preset_fingerprint)
        partial = {k: v for k, v in preset_payload(1).items() if k != 'revision'}
        self.assertRejected('missing_required', 'revision', compute_preset_fingerprint, partial)

    def test_verify_raises_when_any_part_changes_after_fingerprint(self):
        preset = make_preset(1)
        changes = (('visual_rhythm', {'fixture_marker': 'other'}), ('revision', 2), ('output_profile_ref', 'other'), ('preset_fingerprint', ZERO))
        for name, value in changes:
            with self.subTest(name=name):
                changed = dataclasses.replace(preset, **{name: value})
                self.assertRejected('preset_fingerprint_mismatch', 'preset_fingerprint', verify_preset_fingerprint, changed)

    def test_value_the_canonicalizer_rejects_is_a_validation_error(self):
        payload = preset_payload(1) | {'hook_treatment': {'fixture_big': 2 ** 60}}
        self.assertRejected('invalid_value', 'preset_fingerprint', build_preset_revision, payload)


class CatalogAddTests(PresetTestCase):
    def test_add_revision_returns_new_catalog_and_keeps_old(self):
        empty = PresetCatalog()
        first = make_preset(1)
        grown = empty.add_revision(first)
        self.assertIsNot(grown, empty)
        self.assertEqual((empty.revisions, grown.revisions), ((), (first,)))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            grown.revisions = ()

    def test_new_revision_keeps_older_and_conflict_never_overwrites(self):
        first, second = make_preset(1), make_preset(1, 2)
        catalog = PresetCatalog().add_revision(first).add_revision(second)
        self.assertEqual(catalog.revisions, (first, second))
        self.assertEqual(catalog.add_revision(first), catalog)
        conflict = make_preset(1, 1, hook_treatment={'fixture_marker': 'conflict'})
        self.assertRejected('duplicate_revision', 'revision', catalog.add_revision, conflict)
        self.assertEqual(resolve_preset(catalog, 'fixture-preset-1', 1), first)
        self.assertRejected('duplicate_revision', 'revisions', PresetCatalog, revisions=(first, conflict))

    def test_add_revision_rejects_tampered_or_foreign_values(self):
        tampered = dataclasses.replace(make_preset(1), mix_rules={'fixture_marker': 'other'})
        self.assertRejected('preset_fingerprint_mismatch', 'preset_fingerprint', PresetCatalog().add_revision, tampered)
        self.assertRejected('wrong_type', 'preset', PresetCatalog().add_revision, {'preset_key': 'fixture-preset-1'})

    def test_is_complete_only_for_exactly_five_distinct_keys(self):
        for count, expected in ((0, False), (4, False), (5, True), (6, False)):
            catalog = make_catalog(count)
            with self.subTest(count=count):
                self.assertIs(is_complete(catalog), expected)
                self.assertEqual(completeness_issue(catalog), None if expected else 'preset_count_not_five')
        many = make_catalog(5).add_revision(make_preset(1, 2)).add_revision(make_preset(2, 2))
        self.assertEqual((len(many.revisions), is_complete(many)), (7, True))
        same_key = PresetCatalog()
        for revision in range(1, 6):
            same_key = same_key.add_revision(make_preset(1, revision))
        self.assertEqual((len(same_key.revisions), is_complete(same_key)), (5, False))
        self.assertEqual(completeness_issue(same_key), 'preset_count_not_five')


class CatalogResolveTests(PresetTestCase):
    def test_resolve_defaults_to_highest_revision_and_ignores_insertion_order(self):
        ordered = PresetCatalog()
        shuffled = PresetCatalog()
        for revision in (1, 2, 3):
            ordered = ordered.add_revision(make_preset(1, revision))
        for revision in (3, 1, 2):
            shuffled = shuffled.add_revision(make_preset(1, revision))
        self.assertEqual(ordered, shuffled)
        for catalog in (ordered, shuffled):
            self.assertEqual(resolve_preset(catalog, 'fixture-preset-1').revision, 3)
            self.assertEqual(resolve_preset(catalog, 'fixture-preset-1', 2), make_preset(1, 2))
            self.assertEqual(resolve_preset(catalog, 'fixture-preset-1'), resolve_preset(catalog, 'fixture-preset-1'))

    def test_resolve_each_of_five_fixture_presets(self):
        catalog = make_catalog(5)
        for index in range(1, 6):
            self.assertEqual(resolve_preset(catalog, f'fixture-preset-{index}', 1), make_preset(index))

    def test_resolve_missing_preset_or_revision_raises_not_found(self):
        catalog = make_catalog(2)
        self.assertTrue(issubclass(PresetNotFoundError, LookupError))
        for key, revision in (('fixture-preset-9', None), ('fixture-preset-1', 9), ('', None)):
            with self.subTest(key=key, revision=revision):
                with self.assertRaises(PresetNotFoundError) as caught:
                    resolve_preset(catalog, key, revision)
                self.assertEqual(caught.exception.code, 'preset_not_found')
        with self.assertRaises(PresetNotFoundError):
            resolve_preset(PresetCatalog(), 'fixture-preset-1')

    def test_resolve_rejects_invalid_revision_argument(self):
        catalog = make_catalog(1)
        for bad, code in ((0, 'invalid_value'), (True, 'wrong_type'), ('1', 'wrong_type')):
            with self.subTest(bad=bad):
                self.assertRejected(code, 'revision', resolve_preset, catalog, 'fixture-preset-1', bad)


class NoHardcodedContentTests(unittest.TestCase):
    def setUp(self):
        self.tree = ast.parse(PRESET_SOURCE.read_text(encoding='utf-8'))

    def test_module_has_no_preset_name_style_or_resolution_literals(self):
        constants = [node.value for node in ast.walk(self.tree) if isinstance(node, ast.Constant)]
        numbers = {v for v in constants if isinstance(v, (int, float)) and not isinstance(v, bool)}
        self.assertLessEqual(numbers, {0, 1, 5})
        texts = [v for v in constants if isinstance(v, str)]
        self.assertEqual([t for t in texts if re.search(r'[0-9]+ *[x*] *[0-9]+', t)], [])
        self.assertEqual([t for t in texts if 'fixture' in t.lower()], [])

    def test_fingerprint_comes_from_the_shared_canonicalizer(self):
        imported = {(n.module, a.name) for n in ast.walk(self.tree) if isinstance(n, ast.ImportFrom) for a in n.names}
        self.assertIn(('controlplane.application.idempotency.canonicalization', 'request_hash'), imported)
        modules = {a.name for n in ast.walk(self.tree) if isinstance(n, ast.Import) for a in n.names}
        modules |= {n.module for n in ast.walk(self.tree) if isinstance(n, ast.ImportFrom)}
        self.assertFalse({'hashlib', 'json'} & modules)
