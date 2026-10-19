"""D-12: OutputMetadata value object and filename-safe representation through a D-local port.

coveredIds: CT-AI-009
"""
import ast
import dataclasses
import pathlib
import unittest

from creative.domain.output_metadata import (
    FilenameSafeRepresentation,
    FilenameSanitizerPort,
    OutputMetadata,
    OutputMetadataError,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'src' / 'creative' / 'domain' / 'output_metadata.py'
TITLE = 'Breaking: City Opens New Metro Line?'
CAPTION = 'The new line cuts commutes by 20 minutes: what riders say.'
HASHTAGS = ('#Metro', '#CityNews', '#Transit')


def make_metadata(**overrides: object) -> OutputMetadata:
    fields: dict[str, object] = {
        'title': TITLE,
        'caption': CAPTION,
        'hashtags': HASHTAGS,
        'language': 'en',
        'source_job_ref': 'job-001',
        'source_output_refs': ('variant-validation-001',),
        'metadata_revision': 1,
    }
    fields.update(overrides)
    return OutputMetadata(**fields)


class FakeFilenameSanitizer:
    """Test double for the storage-contract sanitizer of capability I (no binding yet)."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def sanitize(self, value: str) -> str:
        self.calls.append(value)
        return 'safe_' + value.replace(' ', '_').replace(':', '').replace('?', '').replace('#', '')


class OutputMetadataFieldTests(unittest.TestCase):
    def test_valid_metadata_keeps_every_field(self) -> None:
        metadata = make_metadata()
        self.assertEqual(metadata.title, TITLE)
        self.assertEqual(metadata.caption, CAPTION)
        self.assertEqual(metadata.hashtags, HASHTAGS)
        self.assertEqual(metadata.language, 'en')
        self.assertEqual(metadata.source_job_ref, 'job-001')
        self.assertEqual(metadata.source_output_refs, ('variant-validation-001',))
        self.assertEqual(metadata.metadata_revision, 1)
        self.assertIsNone(metadata.filename_safe)

    def test_metadata_is_frozen(self) -> None:
        metadata = make_metadata()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            metadata.title = 'Other'  # type: ignore[misc]

    def test_hashtag_count_must_be_three_or_four(self) -> None:
        for count in (0, 1, 2, 5, 6):
            with self.subTest(count=count):
                with self.assertRaises(OutputMetadataError):
                    make_metadata(hashtags=tuple(f'#Tag{i}' for i in range(count)))
        for count in (3, 4):
            with self.subTest(count=count):
                metadata = make_metadata(hashtags=tuple(f'#Tag{i}' for i in range(count)))
                self.assertEqual(len(metadata.hashtags), count)

    def test_hashtags_must_be_a_tuple(self) -> None:
        with self.assertRaises(OutputMetadataError):
            make_metadata(hashtags=['#Metro', '#CityNews', '#Transit'])

    def test_hashtag_shape_is_validated(self) -> None:
        for bad in ('Metro', '#', '', '#Two Words', '#a#b', 7):
            with self.subTest(bad=bad):
                with self.assertRaises(OutputMetadataError):
                    make_metadata(hashtags=(bad, '#CityNews', '#Transit'))

    def test_duplicate_hashtags_ignoring_case_are_rejected(self) -> None:
        with self.assertRaises(OutputMetadataError):
            make_metadata(hashtags=('#Metro', '#metro', '#Transit'))

    def test_language_must_be_english(self) -> None:
        self.assertEqual(make_metadata(language='en').language, 'en')
        for bad in ('vi', 'fr', ''):
            with self.subTest(language=bad):
                with self.assertRaises(OutputMetadataError):
                    make_metadata(language=bad)

    def test_title_and_caption_must_be_non_blank_strings(self) -> None:
        for field in ('title', 'caption'):
            for bad in ('', '   ', None):
                with self.subTest(field=field, bad=bad):
                    with self.assertRaises(OutputMetadataError):
                        make_metadata(**{field: bad})

    def test_source_refs_are_required(self) -> None:
        cases = (
            {'source_job_ref': ''},
            {'source_output_refs': ()},
            {'source_output_refs': ['variant-validation-001']},
            {'source_output_refs': ('',)},
        )
        for override in cases:
            with self.subTest(override=override):
                with self.assertRaises(OutputMetadataError):
                    make_metadata(**override)

    def test_metadata_revision_must_be_positive_int(self) -> None:
        for bad in (0, -1, True, '1', 1.0):
            with self.subTest(revision=bad):
                with self.assertRaises(OutputMetadataError):
                    make_metadata(metadata_revision=bad)
        self.assertEqual(make_metadata(metadata_revision=2).metadata_revision, 2)


class FixedFilenameSanitizer:
    """Returns one canned value so tests can prove D passes the port output through verbatim."""

    def __init__(self, result: object) -> None:
        self.result = result

    def sanitize(self, value: str) -> str:
        return self.result  # type: ignore[return-value]


class FilenameSafeRepresentationTests(unittest.TestCase):
    def test_fake_satisfies_port(self) -> None:
        self.assertIsInstance(FakeFilenameSanitizer(), FilenameSanitizerPort)

    def test_filename_safe_comes_only_from_port(self) -> None:
        fake = FakeFilenameSanitizer()
        result = make_metadata().with_filename_safe(fake)
        self.assertEqual(fake.calls, [TITLE, CAPTION, *HASHTAGS])
        self.assertIsNotNone(result.filename_safe)
        self.assertEqual(
            result.filename_safe,
            FilenameSafeRepresentation(
                title='safe_Breaking_City_Opens_New_Metro_Line',
                caption='safe_The_new_line_cuts_commutes_by_20_minutes_what_riders_say.',
                hashtags=('safe_Metro', 'safe_CityNews', 'safe_Transit'),
            ),
        )

    def test_port_output_is_not_post_processed_by_d(self) -> None:
        raw = ' Mixed.Case Name. '
        result = make_metadata().with_filename_safe(FixedFilenameSanitizer(raw))
        self.assertIsNotNone(result.filename_safe)
        self.assertEqual(result.filename_safe.title, raw)
        self.assertEqual(result.filename_safe.caption, raw)
        self.assertEqual(result.filename_safe.hashtags, (raw, raw, raw))

    def test_display_representation_is_unchanged_after_sanitize(self) -> None:
        original = make_metadata()
        result = original.with_filename_safe(FakeFilenameSanitizer())
        self.assertIsNot(result, original)
        self.assertIsNone(original.filename_safe)
        self.assertIsNotNone(result.filename_safe)
        self.assertNotEqual(result.filename_safe.title, TITLE)
        for metadata in (original, result):
            self.assertEqual(metadata.title, TITLE)
            self.assertEqual(metadata.caption, CAPTION)
            self.assertEqual(metadata.hashtags, HASHTAGS)
            self.assertEqual(metadata.metadata_revision, 1)

    def test_without_port_there_is_no_filename_safe_representation(self) -> None:
        self.assertIsNone(make_metadata().filename_safe)

    def test_invalid_port_output_is_rejected(self) -> None:
        for bad in ('', None, 42):
            with self.subTest(result=bad):
                with self.assertRaises(OutputMetadataError):
                    make_metadata().with_filename_safe(FixedFilenameSanitizer(bad))

    def test_filename_safe_representation_validates_fields(self) -> None:
        valid = {'title': 'a', 'caption': 'b', 'hashtags': ('c',)}
        FilenameSafeRepresentation(**valid)
        for override in ({'title': ''}, {'caption': ''}, {'hashtags': ['c']}, {'hashtags': ('',)}):
            with self.subTest(override=override):
                with self.assertRaises(OutputMetadataError):
                    FilenameSafeRepresentation(**{**valid, **override})

    def test_metadata_rejects_non_representation_filename_safe(self) -> None:
        with self.assertRaises(OutputMetadataError):
            make_metadata(filename_safe='safe_name')

    def test_module_defines_no_filename_rules_of_its_own(self) -> None:
        tree = ast.parse(MODULE_PATH.read_text(encoding='utf-8'), filename=str(MODULE_PATH))
        imported: set[str] = set()
        attributes: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.Attribute):
                attributes.add(node.attr)
        self.assertEqual(imported, {'dataclasses', 'typing'})
        self.assertEqual(attributes & {'translate', 'maketrans', 'replace', 'sub', 'normalize', 'encode'}, set())
