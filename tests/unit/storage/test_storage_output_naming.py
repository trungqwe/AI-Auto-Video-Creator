"""I-11: kiểm thử cấp phát folder và tên tệp output (CT-STO-011, D8-I-07, D8-I-08)."""
from __future__ import annotations

import ast
import dataclasses
import pathlib
import unicodedata
import unittest
from datetime import date

from controlplane.domain.storage_meta.output_naming import (
    HASH_REPLACEMENT,
    OutputName,
    allocate_output_filename,
    allocate_output_folder,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE = ROOT / 'src' / 'controlplane' / 'domain' / 'storage_meta' / 'output_naming.py'
TAGS = ('#one', '#two', '#three')
TAIL = ' #one #two #three'
TODAY = date(2026, 10, 19)
CLIP = chr(0x1F3AC)
VIET = 'Vi' + chr(0x1EC7) + 't'
ACUTE = chr(0x301)
BACKSLASH = chr(92)
RESERVED = ['CON', 'PRN', 'AUX', 'NUL'] + [f'{p}{n}' for p in ('COM', 'LPT') for n in range(1, 10)]


def make(title='Hello', tags=TAGS, ext='mp4', existing=(), supports_hash=True, limit=255):
    return allocate_output_filename(title, tags, ext, existing, supports_hash, limit)


def units(text):
    return len(text.encode('utf-16-le')) // 2


class OutputFolderTests(unittest.TestCase):
    def test_first_second_third_session(self):
        self.assertEqual(allocate_output_folder(TODAY, 0, True), '26-10-19')
        self.assertEqual(allocate_output_folder(TODAY, 1, True), '26-10-19 (1)')
        self.assertEqual(allocate_output_folder(TODAY, 2, True), '26-10-19 (2)')

    def test_session_without_completed_video_has_no_folder(self):
        for before in (0, 1, 5):
            with self.subTest(before=before):
                self.assertIsNone(allocate_output_folder(TODAY, before, False))

    def test_year_month_day_are_zero_padded(self):
        self.assertEqual(allocate_output_folder(date(2027, 1, 5), 0, True), '27-01-05')
        self.assertEqual(allocate_output_folder(date(2005, 3, 9), 1, True), '05-03-09 (1)')

    def test_negative_count_is_rejected(self):
        with self.assertRaises(ValueError):
            allocate_output_folder(TODAY, -1, True)

    def test_same_input_same_output(self):
        self.assertEqual(allocate_output_folder(TODAY, 2, True), allocate_output_folder(TODAY, 2, True))

    def test_module_does_not_read_system_clock(self):
        tree = ast.parse(MODULE.read_text(encoding='utf-8'))
        imported = set()
        attrs = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split('.')[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or '').split('.')[0])
            elif isinstance(node, ast.Attribute):
                attrs.add(node.attr)
        self.assertFalse(imported & {'time', 'random', 'secrets', 'os', 'uuid'})
        self.assertFalse(attrs & {'today', 'now', 'utcnow', 'time', 'random'})


class OutputFilenameSanitizeTests(unittest.TestCase):
    def test_plain_title(self):
        self.assertEqual(make(), OutputName('Hello' + TAIL + '.mp4', 1, 'Hello', TAGS, ()))

    def test_path_traversal_never_survives(self):
        cases = (('../etc/passwd', '.._etc_passwd'), ('..' + BACKSLASH + '..' + BACKSLASH + 'x', '.._.._x'))
        for title, expected in cases:
            with self.subTest(title=title):
                result = make(title)
                self.assertEqual(result.sanitized_filename, expected + TAIL + '.mp4')
                self.assertNotIn('/', result.sanitized_filename)
                self.assertNotIn(BACKSLASH, result.sanitized_filename)
                self.assertEqual(result.display_title, title)

    def test_forbidden_characters_become_underscore(self):
        title = 'a<b>c:d"e/f' + BACKSLASH + 'g|h?i*j'
        self.assertEqual(make(title).sanitized_filename, 'a_b_c_d_e_f_g_h_i_j' + TAIL + '.mp4')

    def test_control_characters_are_removed(self):
        title = 'a' + chr(0) + 'b' + chr(9) + 'c' + chr(10) + 'd' + chr(0x7F) + 'e'
        self.assertEqual(make(title).sanitized_filename, 'abcde' + TAIL + '.mp4')

    def test_trailing_dots_and_spaces_are_stripped(self):
        result = make(tags=('#one', '#two', '#three. . '))
        self.assertEqual(result.sanitized_filename, 'Hello #one #two #three.mp4')

    def test_reserved_names_get_underscore_suffix(self):
        for reserved in RESERVED:
            for title in (reserved, reserved.lower()):
                with self.subTest(title=title):
                    self.assertEqual(make(title).sanitized_filename, f'{title}_{TAIL}.mp4')
                    self.assertEqual(make(title, tags=('', '', '')).sanitized_filename, f'{title}_.mp4')
        self.assertEqual(make('CON.log').sanitized_filename, 'CON_.log' + TAIL + '.mp4')

    def test_non_reserved_lookalikes_are_untouched(self):
        for title in ('COM0', 'COM10', 'CONSOLE', 'LPT', 'CONN'):
            with self.subTest(title=title):
                self.assertEqual(make(title).sanitized_filename, title + TAIL + '.mp4')

    def test_empty_stem_falls_back_to_underscore(self):
        self.assertEqual(make('', tags=('', '', '')).sanitized_filename, '_.mp4')

    def test_emoji_is_kept(self):
        self.assertEqual(make(CLIP + ' Vlog').sanitized_filename, CLIP + ' Vlog' + TAIL + '.mp4')

    def test_vietnamese_is_nfc_but_display_keeps_original(self):
        decomposed = unicodedata.normalize('NFD', VIET + ' Nam')
        self.assertNotEqual(decomposed, VIET + ' Nam')
        result = make(decomposed)
        self.assertEqual(result.sanitized_filename, VIET + ' Nam' + TAIL + '.mp4')
        self.assertEqual(result.display_title, decomposed)

    def test_extension_is_sanitized(self):
        self.assertEqual(make(ext='.mp4').sanitized_filename, 'Hello' + TAIL + '.mp4')
        self.assertEqual(make(ext='m/p4').sanitized_filename, 'Hello' + TAIL + '.m_p4')
        self.assertEqual(make(ext='mp4. ').sanitized_filename, 'Hello' + TAIL + '.mp4')
        self.assertEqual(make(ext='').sanitized_filename, 'Hello' + TAIL)


class OutputFilenameRulesTests(unittest.TestCase):
    def test_hashtag_count_must_be_three_or_four(self):
        for count in (0, 1, 2, 5, 6):
            with self.subTest(count=count):
                with self.assertRaises(ValueError):
                    make(tags=tuple(f'#t{i}' for i in range(count)))
        with self.assertRaises(ValueError):
            make(tags='#abc')
        self.assertEqual(make(tags=('#a', '#b', '#c', '#d')).sanitized_filename, 'Hello #a #b #c #d.mp4')
        self.assertEqual(make(tags=('#a', '#b', '#c')).sanitized_filename, 'Hello #a #b #c.mp4')

    def test_hash_is_kept_when_supported(self):
        result = make()
        self.assertIn('#', result.sanitized_filename)
        self.assertEqual(result.hash_mapping, ())

    def test_hash_is_replaced_and_mapped_when_unsupported(self):
        result = make(supports_hash=False)
        expected = f'Hello {HASH_REPLACEMENT}one {HASH_REPLACEMENT}two {HASH_REPLACEMENT}three.mp4'
        self.assertEqual(result.sanitized_filename, expected)
        self.assertNotIn('#', result.sanitized_filename)
        self.assertEqual(result.hash_mapping, ((HASH_REPLACEMENT, '#'),))
        self.assertEqual(result.display_hashtags, TAGS)
        self.assertEqual(make(tags=('a', 'b', 'c'), supports_hash=False).hash_mapping, ())

    def test_display_metadata_keeps_original(self):
        title = '../CON ' + CLIP + ': ' + VIET + '.'
        result = make(title, tags=['#one', '#two', '#three'])
        self.assertEqual(result.display_title, title)
        self.assertEqual(result.display_hashtags, ('#one', '#two', '#three'))
        self.assertIsInstance(result.display_hashtags, tuple)

    def test_collision_appends_sequence_before_extension(self):
        base = 'Hello' + TAIL + '.mp4'
        second = 'Hello' + TAIL + ' (2).mp4'
        first = make(existing=(base,))
        self.assertEqual((first.sanitized_filename, first.collision_sequence), (second, 2))
        third = make(existing=(base, second))
        self.assertEqual((third.sanitized_filename, third.collision_sequence), ('Hello' + TAIL + ' (3).mp4', 3))
        free = make(existing=('other.mp4',))
        self.assertEqual((free.sanitized_filename, free.collision_sequence), (base, 1))

    def test_collision_ignores_case_and_normalization(self):
        self.assertEqual(make(existing=('HELLO #ONE #TWO #THREE.MP4',)).collision_sequence, 2)
        decomposed = unicodedata.normalize('NFD', VIET + TAIL + '.mp4')
        self.assertEqual(make(VIET, existing=(decomposed,)).collision_sequence, 2)

    def test_existing_names_accept_any_iterable_and_any_order(self):
        base = 'Hello' + TAIL + '.mp4'
        second = 'Hello' + TAIL + ' (2).mp4'
        existing = [second, base]
        expected = make(existing=(base, second))
        self.assertEqual(expected.collision_sequence, 3)
        self.assertEqual(make(existing=iter(existing)), expected)
        self.assertEqual(make(existing=set(existing)), expected)
        self.assertEqual(existing, [second, base])


class OutputFilenameLimitTests(unittest.TestCase):
    def test_truncation_respects_limit_and_strips_trailing_dot_or_space(self):
        self.assertEqual(make('abcdefghij', limit=12).sanitized_filename, 'abcdefgh.mp4')
        self.assertEqual(make('abc def', limit=8).sanitized_filename, 'abc.mp4')

    def test_truncation_never_splits_a_character(self):
        tags = ('#a', '#b', '#c')
        self.assertEqual(make(CLIP * 4, tags=tags, limit=8).sanitized_filename, CLIP * 2 + '.mp4')
        self.assertEqual(make(CLIP * 4, tags=tags, limit=7).sanitized_filename, CLIP + '.mp4')
        acute = 'abx' + ACUTE
        self.assertEqual(make(acute, tags=tags, limit=7).sanitized_filename, 'ab.mp4')
        self.assertEqual(make(acute, tags=tags, limit=8).sanitized_filename, acute + '.mp4')

    def test_truncation_cannot_recreate_reserved_name(self):
        result = make('CONSOLE', tags=('#a', '#b', '#c'), limit=7)
        self.assertEqual(result.sanitized_filename, 'CO.mp4')

    def test_limit_too_small_is_rejected(self):
        for limit in (0, 4):
            with self.subTest(limit=limit):
                with self.assertRaises(ValueError):
                    make('T', limit=limit)
        self.assertEqual(make('T', limit=5).sanitized_filename, 'T.mp4')

    def test_collision_suffix_fits_inside_limit(self):
        first = make('abcdefghij', limit=12)
        second = make('abcdefghij', existing=(first.sanitized_filename,), limit=12)
        self.assertEqual((second.sanitized_filename, second.collision_sequence), ('abcd (2).mp4', 2))

    def test_filename_never_exceeds_limit_for_any_limit(self):
        title = 'Vlog ' + CLIP + ' ' + VIET + ' CON. x'
        for limit in range(5, 41):
            with self.subTest(limit=limit):
                filename = make(title, limit=limit).sanitized_filename
                self.assertLessEqual(units(filename), limit)
                self.assertTrue(filename.endswith('.mp4'))
                self.assertFalse(filename[:-4].endswith((' ', '.')))

    def test_same_input_gives_same_output(self):
        args = (CLIP + ' ../CON ' + VIET, ['#a', '#b', '#c'], 'mp4', ['x.mp4'], False, 40)
        self.assertEqual(allocate_output_filename(*args), allocate_output_filename(*args))

    def test_output_name_is_immutable(self):
        result = make()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.sanitized_filename = 'other.mp4'
