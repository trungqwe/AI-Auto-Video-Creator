"""A-02: two-layer CollectedDocumentPackage validator (CT-SRC-006).

coveredIds: TST-COL-PKG-001..004 (TST-COL-PKG-001, TST-COL-PKG-002, TST-COL-PKG-003, TST-COL-PKG-004), A-RULE-010
"""
import copy
import json
import pathlib
import unittest

from source_ingestion.domain.package import (
    ELIGIBILITY_CANDIDATE,
    ELIGIBILITY_INCOMPLETE,
    ENUM_VIOLATION,
    INPUT_NOT_READY,
    MISSING_REQUIRED,
    PACKAGE_FIELDS,
    REASON_EMPTY_TEXT,
    REASON_MISSING_CONTENT,
    REASON_MISSING_POLICY,
    REASON_MISSING_SOURCE_KIND_POLICY,
    REASON_MISSING_TITLE,
    VALIDATION_ERROR,
    WRONG_TYPE,
    ContentAssessment,
    ExtractionPolicy,
    FieldSpec,
    PackageValidationError,
    SchemaError,
    assess_content_eligibility,
    validate_package_schema,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
BINDING_PATH = ROOT / 'docs' / 'parallel-delivery' / 'bindings' / 'a-b-collected-document.json'
FIXTURE_PATH = ROOT / 'tests' / 'fixtures' / 'contracts' / 'a-b-collected-document' / 'payloads.json'
ENTITY = 'CollectedDocumentPackage'
MISSING = object()
# Test-only policy fixture (MODULE-A-OPEN-005); not an approved production policy.
POLICY = ExtractionPolicy(
    revision='extraction-policy-fixture-r1',
    title_required_by_source_kind={'web_page': True, 'rss_feed': False},
)


def _binding_fields() -> list[dict]:
    binding = json.loads(BINDING_PATH.read_text(encoding='utf-8'))
    entities = {entity['name']: entity for entity in binding['entities']}
    return entities[ENTITY]['fields']


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))['entities'][ENTITY]


def _valid_payload() -> dict:
    return copy.deepcopy(_fixture()['valid'][0])


def _with(payload: dict, field: str, value: object) -> dict:
    if value is MISSING:
        payload.pop(field, None)
    else:
        payload[field] = value
    return payload


def _spec_as_binding(spec: FieldSpec) -> dict:
    entry = {'name': spec.name, 'type': spec.type, 'required': spec.required}
    if spec.enum is not None:
        entry['enum'] = list(spec.enum)
    if spec.items is not None:
        entry['items'] = spec.items
    return entry


def _field(fields: list[dict], name: str) -> dict:
    return next(f for f in fields if f['name'] == name)


class FieldSpecBindingTests(unittest.TestCase):
    def test_field_specs_match_binding_exactly(self) -> None:
        self.assertEqual([_spec_as_binding(spec) for spec in PACKAGE_FIELDS], _binding_fields())

    def test_drift_comparison_detects_mutated_binding(self) -> None:
        expected = [_spec_as_binding(spec) for spec in PACKAGE_FIELDS]
        self.assertTrue(expected, 'PACKAGE_FIELDS must not be empty')
        mutations = {
            'provenance_chain_optional': lambda fs: _field(fs, 'provenance_chain').update(required=False),
            'source_revision_as_string': lambda fs: _field(fs, 'source_revision').update(type='string'),
            'eligibility_enum_extended': lambda fs: _field(fs, 'content_eligibility')['enum'].append('complete'),
            'extraction_enum_locked': lambda fs: _field(fs, 'extraction_disposition').update(enum=['SUCCESS']),
            'media_items_dropped': lambda fs: _field(fs, 'media_discoveries').pop('items'),
            'warnings_removed': lambda fs: fs.remove(_field(fs, 'warnings')),
            'required_field_added': lambda fs: fs.append({'name': 'x_new', 'type': 'string', 'required': True}),
        }
        for name, mutate in mutations.items():
            with self.subTest(mutation=name):
                drifted = _binding_fields()
                mutate(drifted)
                self.assertNotEqual(expected, drifted)

    def test_extraction_disposition_has_no_enum_lock(self) -> None:
        specs = {spec.name: spec for spec in PACKAGE_FIELDS}
        self.assertIn('extraction_disposition', specs)
        self.assertIsNone(specs['extraction_disposition'].enum)
        for value in ('PARTIAL', 'adapter_specific_outcome', 'FAILED_PARSE'):
            with self.subTest(value=value):
                payload = _with(_valid_payload(), 'extraction_disposition', value)
                self.assertEqual(validate_package_schema(payload), ())


class SchemaLayerTests(unittest.TestCase):
    def test_fixture_cases_are_present(self) -> None:
        fixture = _fixture()
        self.assertGreaterEqual(len(fixture['valid']), 1)
        self.assertGreaterEqual(len(fixture['invalid']), 4)

    def test_fixture_valid_payloads_pass(self) -> None:
        for index, payload in enumerate(_fixture()['valid']):
            with self.subTest(index=index):
                self.assertEqual(validate_package_schema(payload), ())

    def test_fixture_invalid_payloads_fail_with_expected_error(self) -> None:
        for case in _fixture()['invalid']:
            with self.subTest(case=case['case']):
                expected = case['expected_error']
                self.assertEqual(
                    validate_package_schema(case['payload']),
                    (SchemaError(expected['code'], expected['field']),),
                )

    def test_each_missing_required_field_is_reported(self) -> None:
        required = [spec.name for spec in PACKAGE_FIELDS if spec.required]
        refs = {'collected_document_id', 'source_id', 'source_revision', 'collection_run_id', 'provenance_chain'}
        self.assertTrue(refs.issubset(required), f'required refs missing: {sorted(refs - set(required))}')
        for name in required:
            with self.subTest(field=name):
                payload = _with(_valid_payload(), name, MISSING)
                self.assertEqual(validate_package_schema(payload), (SchemaError(MISSING_REQUIRED, name),))

    def test_required_field_set_to_none_is_wrong_type(self) -> None:
        for name in ('collected_document_id', 'provenance_chain', 'fetched_at'):
            with self.subTest(field=name):
                payload = _with(_valid_payload(), name, None)
                self.assertEqual(validate_package_schema(payload), (SchemaError(WRONG_TYPE, name),))

    def test_integer_rejects_bool_string_and_float(self) -> None:
        for value in (True, False, '3', 1.0):
            with self.subTest(value=value):
                payload = _with(_valid_payload(), 'source_revision', value)
                self.assertEqual(validate_package_schema(payload), (SchemaError(WRONG_TYPE, 'source_revision'),))
        self.assertEqual(validate_package_schema(_with(_valid_payload(), 'source_revision', 7)), ())

    def test_content_eligibility_outside_enum_is_rejected(self) -> None:
        for value in ('complete', 'CANDIDATE', ''):
            with self.subTest(value=value):
                payload = _with(_valid_payload(), 'content_eligibility', value)
                self.assertEqual(validate_package_schema(payload), (SchemaError(ENUM_VIOLATION, 'content_eligibility'),))

    def test_datetime_requires_rfc3339(self) -> None:
        accepted = ('2026-10-18T08:00:00Z', '2026-10-18T08:00:00.123456+07:00', '2026-10-18T08:00:00-05:30')
        rejected = (
            'yesterday', '2026-10-18', '2026-10-18T08:00:00', '2026-13-01T08:00:00Z',
            '2026-10-18T25:00:00Z', '20261018T080000Z', '2026-10-18 08:00:00Z', 1760774400,
        )
        for name in ('fetched_at', 'published_at_candidate'):
            for value in accepted:
                with self.subTest(field=name, value=value):
                    self.assertEqual(validate_package_schema(_with(_valid_payload(), name, value)), ())
            for value in rejected:
                with self.subTest(field=name, value=value):
                    payload = _with(_valid_payload(), name, value)
                    self.assertEqual(validate_package_schema(payload), (SchemaError(WRONG_TYPE, name),))

    def test_array_fields_check_container_and_item_types(self) -> None:
        cases = (
            ('provenance_chain', ['final_fetch']),
            ('provenance_chain', {'step': 'final_fetch'}),
            ('media_discoveries', [1]),
            ('warnings', 'none'),
        )
        for name, value in cases:
            with self.subTest(field=name, value=value):
                payload = _with(_valid_payload(), name, value)
                self.assertEqual(validate_package_schema(payload), (SchemaError(WRONG_TYPE, name),))

    def test_extraction_disposition_rejects_blank_string(self) -> None:
        for value in ('', '   '):
            with self.subTest(value=value):
                payload = _with(_valid_payload(), 'extraction_disposition', value)
                self.assertEqual(validate_package_schema(payload), (SchemaError(WRONG_TYPE, 'extraction_disposition'),))

    def test_missing_conditional_fields_are_not_schema_errors(self) -> None:
        payload = _valid_payload()
        for name in ('published_at_candidate', 'canonical_url_candidate', 'raw_snapshot_ref', 'content_fingerprints'):
            _with(payload, name, MISSING)
        self.assertEqual(validate_package_schema(payload), ())

    def test_unknown_additive_field_is_tolerated(self) -> None:
        payload = _with(_valid_payload(), 'x_future_optional_field', 'additive')
        self.assertEqual(validate_package_schema(payload), ())

    def test_non_mapping_payload_is_wrong_type(self) -> None:
        for value in (None, [], 'payload'):
            with self.subTest(value=value):
                self.assertEqual(validate_package_schema(value), (SchemaError(WRONG_TYPE, '$'),))

    def test_repeated_invalid_payload_is_deterministic_and_not_mutated(self) -> None:
        payload = _with(_valid_payload(), 'provenance_chain', MISSING)
        snapshot = copy.deepcopy(payload)
        first = validate_package_schema(payload)
        second = validate_package_schema(payload)
        self.assertEqual(first, (SchemaError(MISSING_REQUIRED, 'provenance_chain'),))
        self.assertEqual(second, first)
        self.assertEqual(payload, snapshot)


class ContentLayerTests(unittest.TestCase):
    def test_valid_fixture_is_candidate_under_policy(self) -> None:
        for kind in ('web_page', 'rss_feed'):
            with self.subTest(source_kind=kind):
                self.assertEqual(
                    assess_content_eligibility(_valid_payload(), kind, POLICY),
                    ContentAssessment(ELIGIBILITY_CANDIDATE, None, POLICY.revision),
                )

    def test_missing_policy_is_input_not_ready_without_default(self) -> None:
        for title in ('Sample Title', MISSING):
            with self.subTest(title=repr(title)):
                payload = _valid_payload()
                _with(payload['extracted_content_candidate'], 'title', title)
                self.assertEqual(
                    assess_content_eligibility(payload, 'web_page', None),
                    ContentAssessment(INPUT_NOT_READY, REASON_MISSING_POLICY, None),
                )

    def test_source_kind_absent_from_policy_is_input_not_ready(self) -> None:
        self.assertEqual(
            assess_content_eligibility(_valid_payload(), 'social_post', POLICY),
            ContentAssessment(INPUT_NOT_READY, REASON_MISSING_SOURCE_KIND_POLICY, POLICY.revision),
        )

    def test_empty_main_text_is_incomplete_with_reason(self) -> None:
        for text in ('', '   \n', None, 42, MISSING):
            payload = _valid_payload()
            _with(payload['extracted_content_candidate'], 'text', text)
            self.assertEqual(validate_package_schema(payload), ())
            for kind in ('web_page', 'rss_feed'):
                with self.subTest(text=repr(text), source_kind=kind):
                    self.assertEqual(
                        assess_content_eligibility(payload, kind, POLICY),
                        ContentAssessment(ELIGIBILITY_INCOMPLETE, REASON_EMPTY_TEXT, POLICY.revision),
                    )

    def test_missing_extracted_content_is_incomplete(self) -> None:
        payload = _with(_valid_payload(), 'extracted_content_candidate', MISSING)
        self.assertEqual(validate_package_schema(payload), ())
        self.assertEqual(
            assess_content_eligibility(payload, 'rss_feed', POLICY),
            ContentAssessment(ELIGIBILITY_INCOMPLETE, REASON_MISSING_CONTENT, POLICY.revision),
        )

    def test_title_requirement_follows_source_kind_policy(self) -> None:
        inverse = ExtractionPolicy(revision='extraction-policy-fixture-r2', title_required_by_source_kind={'web_page': False})
        for title in (MISSING, '', '  ', None):
            payload = _valid_payload()
            _with(payload['extracted_content_candidate'], 'title', title)
            with self.subTest(title=repr(title)):
                self.assertEqual(
                    assess_content_eligibility(payload, 'web_page', POLICY),
                    ContentAssessment(ELIGIBILITY_INCOMPLETE, REASON_MISSING_TITLE, POLICY.revision),
                )
                self.assertEqual(
                    assess_content_eligibility(payload, 'rss_feed', POLICY),
                    ContentAssessment(ELIGIBILITY_CANDIDATE, None, POLICY.revision),
                )
                self.assertEqual(
                    assess_content_eligibility(payload, 'web_page', inverse),
                    ContentAssessment(ELIGIBILITY_CANDIDATE, None, inverse.revision),
                )

    def test_missing_published_at_candidate_stays_candidate(self) -> None:
        payload = _with(_valid_payload(), 'published_at_candidate', MISSING)
        self.assertEqual(validate_package_schema(payload), ())
        self.assertEqual(
            assess_content_eligibility(payload, 'web_page', POLICY),
            ContentAssessment(ELIGIBILITY_CANDIDATE, None, POLICY.revision),
        )

    def test_schema_invalid_package_raises_validation_error(self) -> None:
        for case in _fixture()['invalid']:
            expected = (SchemaError(case['expected_error']['code'], case['expected_error']['field']),)
            for policy in (POLICY, None):
                with self.subTest(case=case['case'], policy=policy is not None):
                    with self.assertRaises(PackageValidationError) as raised:
                        assess_content_eligibility(case['payload'], 'web_page', policy)
                    self.assertEqual(raised.exception.code, VALIDATION_ERROR)
                    self.assertEqual(raised.exception.errors, expected)

    def test_policy_requires_revision_and_boolean_title_rules(self) -> None:
        invalid = (
            ('', {'web_page': True}),
            ('   ', {'web_page': True}),
            (None, {'web_page': True}),
            ('r1', {'web_page': 'yes'}),
            ('r1', {'': True}),
        )
        for revision, rules in invalid:
            with self.subTest(revision=revision, rules=rules):
                with self.assertRaises(ValueError):
                    ExtractionPolicy(revision=revision, title_required_by_source_kind=rules)

    def test_policy_rules_are_copied(self) -> None:
        rules = {'web_page': True}
        policy = ExtractionPolicy(revision='extraction-policy-fixture-r3', title_required_by_source_kind=rules)
        rules['web_page'] = False
        self.assertIs(policy.title_required_by_source_kind['web_page'], True)
