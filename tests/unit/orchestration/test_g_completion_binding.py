"""G-02: CommitVideoCompletionRequest and CompletionLedgerEntry validators (CT-ORC-008, CT-ORC-009).

coveredIds: CT-ORC-008, CT-ORC-009, BINDING-G-C-I-COMPLETION 1.0.0
"""
import ast
import copy
import json
import pathlib
import unittest

from controlplane.domain.orchestration.completion_binding import (
    BINDING_VERSION,
    COMMIT_REQUEST_FIELDS,
    LEDGER_ENTRY_FIELDS,
    MISSING_REQUIRED,
    WRONG_TYPE,
    validate_commit_request,
    validate_ledger_entry,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_SOURCE = ROOT / 'src' / 'controlplane' / 'domain' / 'orchestration' / 'completion_binding.py'
BINDING = json.loads((ROOT / 'docs' / 'parallel-delivery' / 'bindings' / 'g-c-i-completion.json').read_text(encoding='utf-8'))
FIXTURE = json.loads((ROOT / 'tests' / 'fixtures' / 'contracts' / 'g-c-i-completion' / 'payloads.json').read_text(encoding='utf-8'))
REQUEST = 'CommitVideoCompletionRequest'
LEDGER = 'CompletionLedgerEntry'
ENTITIES = (
    (REQUEST, validate_commit_request, COMMIT_REQUEST_FIELDS),
    (LEDGER, validate_ledger_entry, LEDGER_ENTRY_FIELDS),
)


def error(code, field):
    return {'code': code, 'field': field}


def valid_payload(name):
    return copy.deepcopy(FIXTURE['entities'][name]['valid'][0])


class FixtureTests(unittest.TestCase):
    def test_fixture_is_not_vacuous(self):
        for name, _, _ in ENTITIES:
            self.assertGreaterEqual(len(FIXTURE['entities'][name]['valid']), 1)
            self.assertGreaterEqual(len(FIXTURE['entities'][name]['invalid']), 1)

    def test_valid_payloads_return_empty_list(self):
        for name, validate, _ in ENTITIES:
            for index, payload in enumerate(FIXTURE['entities'][name]['valid']):
                with self.subTest(entity=name, index=index):
                    self.assertEqual(validate(payload), [])

    def test_invalid_payloads_return_exactly_expected_error(self):
        for name, validate, _ in ENTITIES:
            for case in FIXTURE['entities'][name]['invalid']:
                with self.subTest(entity=name, case=case['case']):
                    self.assertEqual(validate(case['payload']), [case['expected_error']])


class BindingDriftTests(unittest.TestCase):
    def test_field_specs_match_binding_manifest_in_order(self):
        self.assertEqual(BINDING['binding_version'], BINDING_VERSION)
        entities = {entity['name']: entity for entity in BINDING['entities']}
        for name, _, specs in ENTITIES:
            with self.subTest(entity=name):
                expected = [(f['name'], f['type'], f['required']) for f in entities[name]['fields']]
                self.assertEqual([(s.name, s.type, s.required) for s in specs], expected)


BAD_HASHES = (
    '0123456789ABCDEF' * 4,
    'A' + 'a' * 63,
    'a' * 63,
    'a' * 65,
    'g' * 64,
    'a' * 64 + '\n',
    ' ' + 'a' * 63,
    'sha256:' + 'a' * 64,
    '',
    123,
    None,
    True,
    ['a' * 64],
)


class ShapeTests(unittest.TestCase):
    def test_non_mapping_payload_is_wrong_type_at_root(self):
        for name, validate, _ in ENTITIES:
            for payload in (None, [], 'text', 1, True):
                with self.subTest(entity=name, payload=payload):
                    self.assertEqual(validate(payload), [error(WRONG_TYPE, '$')])

    def test_unknown_fields_are_ignored(self):
        for name, validate, _ in ENTITIES:
            payload = valid_payload(name) | {'future_optional': 1, 'nested_extra': {'a': [1]}}
            with self.subTest(entity=name):
                self.assertEqual(validate(payload), [])

    def test_payload_is_not_mutated(self):
        for name, validate, _ in ENTITIES:
            payload = valid_payload(name)
            payload['output_sha256'] = payload['output_sha256'].upper()
            before = copy.deepcopy(payload)
            with self.subTest(entity=name):
                self.assertEqual(validate(payload), [error(WRONG_TYPE, 'output_sha256')])
                self.assertEqual(payload, before)

    def test_all_errors_are_reported_in_binding_order(self):
        for name, validate, _ in ENTITIES:
            payload = valid_payload(name)
            del payload['video_job_id']
            payload['output_sha256'] = 'not-a-hash'
            with self.subTest(entity=name):
                self.assertEqual(
                    validate(payload),
                    [error(MISSING_REQUIRED, 'video_job_id'), error(WRONG_TYPE, 'output_sha256')],
                )


class Sha256Tests(unittest.TestCase):
    def test_bad_hashes_are_wrong_type_including_uppercase(self):
        for name, validate, _ in ENTITIES:
            for value in BAD_HASHES:
                payload = valid_payload(name)
                payload['output_sha256'] = value
                with self.subTest(entity=name, value=value):
                    self.assertEqual(validate(payload), [error(WRONG_TYPE, 'output_sha256')])

    def test_lowercase_hex_hashes_are_accepted(self):
        for name, validate, _ in ENTITIES:
            for value in ('a' * 64, '0' * 64):
                payload = valid_payload(name)
                payload['output_sha256'] = value
                with self.subTest(entity=name, value=value):
                    self.assertEqual(validate(payload), [])


INTEGER_FIELDS = ('expected_variant_registry_revision', 'execution_generation')
BAD_INTEGERS = (True, False, '12', 12.0, 1.5, None, [], {})


class RequiredFieldTests(unittest.TestCase):
    def test_every_missing_field_is_missing_required(self):
        for name, validate, specs in ENTITIES:
            for spec in specs:
                payload = valid_payload(name)
                del payload[spec.name]
                with self.subTest(entity=name, field=spec.name):
                    self.assertEqual(validate(payload), [error(MISSING_REQUIRED, spec.name)])

    def test_every_null_field_is_wrong_type(self):
        for name, validate, specs in ENTITIES:
            for spec in specs:
                payload = valid_payload(name)
                payload[spec.name] = None
                with self.subTest(entity=name, field=spec.name):
                    self.assertEqual(validate(payload), [error(WRONG_TYPE, spec.name)])

    def test_string_fields_reject_non_strings(self):
        for name, validate, specs in ENTITIES:
            for spec in specs:
                if spec.type != 'string':
                    continue
                for value in (1, True, [], {}):
                    payload = valid_payload(name)
                    payload[spec.name] = value
                    with self.subTest(entity=name, field=spec.name, value=value):
                        self.assertEqual(validate(payload), [error(WRONG_TYPE, spec.name)])

    def test_cloud_location_verification_ref_is_required_only_by_request(self):
        request = valid_payload(REQUEST)
        del request['cloud_location_verification_ref']
        self.assertEqual(validate_commit_request(request), [error(MISSING_REQUIRED, 'cloud_location_verification_ref')])
        ledger = valid_payload(LEDGER)
        self.assertNotIn('cloud_location_verification_ref', ledger)
        self.assertEqual(validate_ledger_entry(ledger), [])

    def test_cleanup_policy_ref_is_required_only_by_ledger(self):
        ledger = valid_payload(LEDGER)
        del ledger['cleanup_policy_ref']
        self.assertEqual(validate_ledger_entry(ledger), [error(MISSING_REQUIRED, 'cleanup_policy_ref')])
        request = valid_payload(REQUEST)
        self.assertNotIn('cleanup_policy_ref', request)
        self.assertEqual(validate_commit_request(request), [])


class IntegerTests(unittest.TestCase):
    def test_integer_fields_reject_bool_string_float_and_null(self):
        for field in INTEGER_FIELDS:
            for value in BAD_INTEGERS:
                payload = valid_payload(REQUEST)
                payload[field] = value
                with self.subTest(field=field, value=value):
                    self.assertEqual(validate_commit_request(payload), [error(WRONG_TYPE, field)])

    def test_integer_fields_accept_integers(self):
        for field in INTEGER_FIELDS:
            for value in (1, 12):
                payload = valid_payload(REQUEST)
                payload[field] = value
                with self.subTest(field=field, value=value):
                    self.assertEqual(validate_commit_request(payload), [])


GOOD_DATETIMES = (
    '2026-10-18T08:00:00Z',
    '2026-10-18T08:00:00.123+07:00',
    '2026-10-18T08:00:00.123456789-05:30',
    '2026-10-18T23:59:60Z',
    '2024-02-29T00:00:00Z',
)
BAD_DATETIMES = (
    'not-a-date',
    '',
    '2026-10-18',
    '2026-10-18T08:00:00',
    '2026-10-18 08:00:00Z',
    '2026-10-18T08:00Z',
    '2026-10-18T08:00:00.Z',
    '2026-13-18T08:00:00Z',
    '2026-02-30T08:00:00Z',
    '2025-02-29T00:00:00Z',
    '2026-10-18T24:00:00Z',
    '2026-10-18T08:60:00Z',
    '2026-10-18T08:00:61Z',
    '2026-10-18T08:00:00+24:00',
    '2026-10-18T08:00:00+07:60',
    '2026-10-18T08:00:00Z\n',
    1760774400,
    None,
    True,
)


class DatetimeTests(unittest.TestCase):
    def test_rfc3339_timestamps_are_accepted(self):
        for value in GOOD_DATETIMES:
            payload = valid_payload(LEDGER)
            payload['completed_at'] = value
            with self.subTest(value=value):
                self.assertEqual(validate_ledger_entry(payload), [])

    def test_non_rfc3339_values_are_wrong_type(self):
        for value in BAD_DATETIMES:
            payload = valid_payload(LEDGER)
            payload['completed_at'] = value
            with self.subTest(value=value):
                self.assertEqual(validate_ledger_entry(payload), [error(WRONG_TYPE, 'completed_at')])


class ContainerTests(unittest.TestCase):
    def test_media_usage_manifest_must_be_array(self):
        for name, validate, _ in ENTITIES:
            for value in ({}, 'x', 1, True, None):
                payload = valid_payload(name)
                payload['media_usage_manifest'] = value
                with self.subTest(entity=name, value=value):
                    self.assertEqual(validate(payload), [error(WRONG_TYPE, 'media_usage_manifest')])
            for value in ([], [{'media_asset_id': 'x', 'role': 'illustration'}]):
                payload = valid_payload(name)
                payload['media_usage_manifest'] = value
                with self.subTest(entity=name, value=value):
                    self.assertEqual(validate(payload), [])

    def test_ledger_object_fields_must_be_objects(self):
        for field in ('output_naming_metadata', 'cost_usage_summary'):
            for value in ([], 'x', 1, True, None):
                payload = valid_payload(LEDGER)
                payload[field] = value
                with self.subTest(field=field, value=value):
                    self.assertEqual(validate_ledger_entry(payload), [error(WRONG_TYPE, field)])
            for value in ({}, {'k': 1}):
                payload = valid_payload(LEDGER)
                payload[field] = value
                with self.subTest(field=field, value=value):
                    self.assertEqual(validate_ledger_entry(payload), [])


class PurityTests(unittest.TestCase):
    def test_module_has_no_io_or_clock(self):
        tree = ast.parse(MODULE_SOURCE.read_text(encoding='utf-8'))
        roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split('.')[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                roots.add(node.module.split('.')[0])
        self.assertLessEqual(roots, {'__future__', 'collections', 'dataclasses', 'datetime', 're'})
        attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        self.assertEqual(attributes & {'now', 'utcnow', 'today', 'open', 'read_text'}, set())
