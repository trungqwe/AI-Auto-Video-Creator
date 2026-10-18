"""C-06: media candidate query for D (CT-MED-005, BINDING-C-D-MEDIA-CANDIDATES)."""
import json
import pathlib
import unittest
from unittest import mock

from catalog.application import candidate_query
from catalog.application.candidate_query import (
    CandidateIndexEntry,
    ContractError,
    parse_media_candidate_query,
    query_media_candidates,
    validate_media_candidate,
)
from catalog.domain.identity import MediaKind
from catalog.domain.states import Availability

ROOT = pathlib.Path(__file__).resolve().parents[3]
FIXTURE = ROOT / 'tests' / 'fixtures' / 'contracts' / 'c-d-media-candidates' / 'payloads.json'
BINDING = ROOT / 'docs' / 'parallel-delivery' / 'bindings' / 'c-d-media-candidates.json'
ENTITIES = json.loads(FIXTURE.read_text(encoding='utf-8'))['entities']
BINDING_FIELDS = {
    entity['name']: {field['name'] for field in entity['fields']}
    for entity in json.loads(BINDING.read_text(encoding='utf-8'))['entities']
}


def valid_query(**overrides) -> dict:
    payload = json.loads(json.dumps(ENTITIES['MediaCandidateQuery']['valid'][0]))
    payload.update(overrides)
    return payload


def valid_candidate(**overrides) -> dict:
    payload = json.loads(json.dumps(ENTITIES['MediaCandidate']['valid'][0]))
    payload.update(overrides)
    return payload


def invalid_case(entity: str, name: str) -> dict:
    return next(case for case in ENTITIES[entity]['invalid'] if case['case'] == name)


def make_entry(media_asset_id: str, **overrides) -> CandidateIndexEntry:
    fields = {
        'media_asset_id': media_asset_id,
        'rendition_ref': f'{media_asset_id}-r',
        'artifact_version_ref': f'{media_asset_id}-v',
        'kind': MediaKind.IMAGE,
        'roles': ('illustration',),
        'entities': (),
        'topics': (),
        'scenes': (),
        'provenance': {'source': 'catalog'},
        'technical_fitness': {'resolution': '1080p'},
        'availability': Availability.AVAILABLE,
        'safety_rights_status': {'rights_cleared': True},
        'usage_refs': (),
    }
    fields.update(overrides)
    return CandidateIndexEntry(**fields)


def ids(candidates: list[dict]) -> list[str]:
    return [candidate['media_asset_id'] for candidate in candidates]


def error_of(func, payload) -> tuple[str, str] | None:
    try:
        func(payload)
    except ContractError as exc:
        return (exc.code, exc.field)
    return None


class QueryParseTests(unittest.TestCase):
    def test_contract_error_is_value_error_with_code_and_field(self) -> None:
        error = ContractError('wrong_type', 'limit')
        self.assertIsInstance(error, ValueError)
        self.assertEqual((error.code, error.field), ('wrong_type', 'limit'))

    def test_valid_fixture_queries_parse(self) -> None:
        for payload in ENTITIES['MediaCandidateQuery']['valid']:
            with self.subTest(payload=payload):
                self.assertEqual(parse_media_candidate_query(payload), payload)

    def test_invalid_fixture_queries_report_expected_error(self) -> None:
        for case in ENTITIES['MediaCandidateQuery']['invalid']:
            expected = (case['expected_error']['code'], case['expected_error']['field'])
            with self.subTest(case=case['case']):
                self.assertEqual(error_of(parse_media_candidate_query, case['payload']), expected)

    def test_unknown_query_fields_are_ignored(self) -> None:
        parsed = parse_media_candidate_query(valid_query(vendor_hint={'boost': 2}, debug=True))
        self.assertEqual(parsed, valid_query())

    def test_boolean_limit_is_wrong_type(self) -> None:
        self.assertEqual(error_of(parse_media_candidate_query, valid_query(limit=True)), ('wrong_type', 'limit'))

    def test_array_items_must_be_strings(self) -> None:
        for field in ('media_kinds', 'roles', 'excluded_usage_refs'):
            with self.subTest(field=field):
                self.assertEqual(
                    error_of(parse_media_candidate_query, valid_query(**{field: [1]})), ('wrong_type', field)
                )

    def test_non_positive_limit_is_invalid_value(self) -> None:
        for limit in (0, -1):
            with self.subTest(limit=limit):
                self.assertEqual(
                    error_of(parse_media_candidate_query, valid_query(limit=limit)), ('invalid_value', 'limit')
                )

    def test_malformed_page_cursor_is_invalid_value(self) -> None:
        for cursor in ('page:2', 'offset:-1', 'offset:abc', 'offset:01'):
            with self.subTest(cursor=cursor):
                self.assertEqual(
                    error_of(parse_media_candidate_query, valid_query(page_cursor=cursor)),
                    ('invalid_value', 'page_cursor'),
                )


class CandidateValidationTests(unittest.TestCase):
    def test_valid_fixture_candidates_pass(self) -> None:
        for payload in ENTITIES['MediaCandidate']['valid']:
            with self.subTest(payload=payload['media_asset_id']):
                self.assertEqual(validate_media_candidate(payload), payload)

    def test_invalid_fixture_candidates_report_expected_error(self) -> None:
        for case in ENTITIES['MediaCandidate']['invalid']:
            expected = (case['expected_error']['code'], case['expected_error']['field'])
            with self.subTest(case=case['case']):
                self.assertEqual(error_of(validate_media_candidate, case['payload']), expected)

    def test_empty_reason_codes_is_invalid_value(self) -> None:
        self.assertEqual(
            error_of(validate_media_candidate, valid_candidate(reason_codes=[])), ('invalid_value', 'reason_codes')
        )

    def test_component_outside_unit_interval_is_invalid_value(self) -> None:
        for components in ({'entity': 1.5}, {'topic': -0.1}):
            with self.subTest(components=components):
                payload = valid_candidate(semantic_match_components=components)
                self.assertEqual(
                    error_of(validate_media_candidate, payload), ('invalid_value', 'semantic_match_components')
                )

    def test_non_numeric_component_is_wrong_type(self) -> None:
        for components in ({'entity': 'high'}, {'entity': True}):
            with self.subTest(components=components):
                payload = valid_candidate(semantic_match_components=components)
                self.assertEqual(
                    error_of(validate_media_candidate, payload), ('wrong_type', 'semantic_match_components')
                )

    def test_aggregate_score_key_is_invalid_value(self) -> None:
        payload = valid_candidate(semantic_match_components={'entity': 0.9, 'total': 0.85})
        self.assertEqual(error_of(validate_media_candidate, payload), ('invalid_value', 'semantic_match_components'))

    def test_unknown_availability_is_enum_violation(self) -> None:
        self.assertEqual(
            error_of(validate_media_candidate, valid_candidate(availability='GONE')), ('enum_violation', 'availability')
        )


class QueryBehaviourTests(unittest.TestCase):
    def test_filters_by_media_kind_and_role(self) -> None:
        entries = [
            make_entry('img'),
            make_entry('clip', kind=MediaKind.CLIP),
            make_entry('audio', kind=MediaKind.AUDIO),
            make_entry('thumb', roles=('thumbnail',)),
        ]
        candidates, _ = query_media_candidates(valid_query(), entries)
        self.assertEqual(ids(candidates), ['img', 'clip'])

    def test_drops_not_usable_availability(self) -> None:
        entries = [make_entry(state.value, availability=state) for state in Availability]
        candidates, _ = query_media_candidates(valid_query(), entries)
        self.assertEqual(ids(candidates), ['AVAILABLE', 'UNAVAILABLE_SOURCE'])

    def test_unavailable_source_media_stays_queryable(self) -> None:
        entries = [make_entry('historic', availability=Availability.UNAVAILABLE_SOURCE)]
        candidates, _ = query_media_candidates(valid_query(), entries)
        self.assertEqual(ids(candidates), ['historic'])
        self.assertEqual(candidates[0]['availability'], 'UNAVAILABLE_SOURCE')
        self.assertIn('SOURCE_UNAVAILABLE', candidates[0]['reason_codes'])

    def test_excluded_usage_refs_drop_entries(self) -> None:
        entries = [
            make_entry('used', usage_refs=('job-1',)),
            make_entry('fresh', usage_refs=('job-2',)),
            make_entry('never'),
        ]
        candidates, _ = query_media_candidates(valid_query(excluded_usage_refs=['job-1']), entries)
        self.assertEqual(ids(candidates), ['fresh', 'never'])

    def test_components_split_entity_topic_scene_without_total(self) -> None:
        intent = {'goal': 'scene_intro', 'entities': ['a', 'b'], 'topics': ['t'], 'scenes': ['s']}
        entries = [make_entry('m', entities=('a', 'x'), topics=('t',))]
        candidates, _ = query_media_candidates(valid_query(scene_intent=intent), entries)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]['semantic_match_components'], {'entity': 0.5, 'topic': 1.0, 'scene': 0.0})
        self.assertEqual(set(candidates[0]), BINDING_FIELDS['MediaCandidate'])
        self.assertEqual(candidates[0]['reason_codes'], ['KIND_MATCH', 'ROLE_MATCH', 'ENTITY_MATCH', 'TOPIC_MATCH'])

    def test_intent_without_terms_scores_zero_and_keeps_reason_codes(self) -> None:
        candidates, _ = query_media_candidates(valid_query(), [make_entry('m', entities=('a',))])
        self.assertEqual(
            [c['semantic_match_components'] for c in candidates], [{'entity': 0.0, 'topic': 0.0, 'scene': 0.0}]
        )
        self.assertEqual([c['reason_codes'] for c in candidates], [['KIND_MATCH', 'ROLE_MATCH']])

    def test_every_candidate_goes_through_validate_media_candidate(self) -> None:
        entries = [make_entry('a'), make_entry('b', kind=MediaKind.CLIP)]
        with mock.patch.object(candidate_query, 'validate_media_candidate', wraps=validate_media_candidate) as spy:
            candidates, _ = query_media_candidates(valid_query(), entries)
        self.assertEqual(ids(candidates), ['a', 'b'])
        self.assertEqual([call.args[0] for call in spy.call_args_list], candidates)

    def test_limit_and_offset_cursor_paginate(self) -> None:
        entries = [make_entry(f'm{i}') for i in range(5)]
        first, cursor = query_media_candidates(valid_query(limit=2), entries)
        self.assertEqual((ids(first), cursor), (['m0', 'm1'], 'offset:2'))
        second, cursor = query_media_candidates(valid_query(limit=2, page_cursor=cursor), entries)
        self.assertEqual((ids(second), cursor), (['m2', 'm3'], 'offset:4'))
        last, cursor = query_media_candidates(valid_query(limit=2, page_cursor=cursor), entries)
        self.assertEqual((ids(last), cursor), (['m4'], None))

    def test_never_returns_more_than_limit(self) -> None:
        entries = [make_entry(f'm{i}') for i in range(30)]
        candidates, cursor = query_media_candidates(valid_query(), entries)
        self.assertEqual((len(candidates), cursor), (20, 'offset:20'))

    def test_keeps_index_order_instead_of_ranking(self) -> None:
        entries = [make_entry('weak'), make_entry('strong', entities=('a',))]
        candidates, _ = query_media_candidates(valid_query(scene_intent={'entities': ['a']}), entries)
        self.assertEqual(ids(candidates), ['weak', 'strong'])

    def test_recent_usage_summary_counts_usage_refs(self) -> None:
        candidates, _ = query_media_candidates(valid_query(), [make_entry('m', usage_refs=('job-1', 'job-2'))])
        self.assertEqual([c['recent_usage_summary'] for c in candidates], [{'times_used': 2}])

    def test_invalid_query_is_rejected_before_search(self) -> None:
        case = invalid_case('MediaCandidateQuery', 'missing_safety_policy_revision')
        expected = (case['expected_error']['code'], case['expected_error']['field'])
        self.assertEqual(error_of(lambda p: query_media_candidates(p, [make_entry('m')]), case['payload']), expected)