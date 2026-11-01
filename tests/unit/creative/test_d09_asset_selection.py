"""D-09: chọn hook, media và âm thanh; validator binding c-d-media-candidates (CT-AI-006, CT-MED-005).

coveredIds: CT-AI-006, CT-MED-005
"""
import ast
import copy
import dataclasses
import hashlib
import json
import pathlib
import re

import pytest

from controlplane.application.idempotency import canonicalization
from creative.domain import asset_selection as module
from creative.domain import ref_resolver
from creative.domain.asset_selection import (
    BINDING_VERSION, CANDIDATE_BLOCKED, CANDIDATE_ITEMS, CANDIDATE_OPTIONAL, CANDIDATE_REQUIRED, HALLUCINATED_REF,
    INPUT_NOT_READY, INVALID_PROPOSAL, MISSING_REQUIRED, MISSING_REQUIRED_HOOK, QUERY_ITEMS, QUERY_OPTIONAL,
    QUERY_REQUIRED, WRONG_TYPE, CreativeAssetSelection, HookCandidate, MediaCandidate, MediaCandidateQuery,
    SafetyRightsPolicy, ScoringWeights, SelectionRejected, ThumbnailCandidate, build_media_candidate_query,
    matches_type, parse_media_candidate, select_creative_assets, validate_media_candidate,
    validate_media_candidate_query,
)
from creative.domain.ref_resolver import RefResolver, ResourceRef

ROOT = pathlib.Path(__file__).resolve().parents[3]
BINDING_PATH = ROOT / 'docs' / 'parallel-delivery' / 'bindings' / 'c-d-media-candidates.json'
FIXTURE_PATH = ROOT / 'tests' / 'fixtures' / 'contracts' / 'c-d-media-candidates' / 'payloads.json'
MODULE_SOURCE = ROOT / 'src' / 'creative' / 'domain' / 'asset_selection.py'
QUERY = 'MediaCandidateQuery'
CANDIDATE = 'MediaCandidate'
MISSING = object()
VALIDATORS = {QUERY: validate_media_candidate_query, CANDIDATE: validate_media_candidate}
TABLES = {QUERY: (QUERY_REQUIRED, QUERY_OPTIONAL, QUERY_ITEMS), CANDIDATE: (CANDIDATE_REQUIRED, CANDIDATE_OPTIONAL, CANDIDATE_ITEMS)}


def _binding() -> dict:
    return json.loads(BINDING_PATH.read_text(encoding='utf-8'))


def _binding_fields(entity: str) -> list[dict]:
    return next(item for item in _binding()['entities'] if item['name'] == entity)['fields']


def _fixture(entity: str) -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))['entities'][entity]


def _derive(fields: list[dict]) -> tuple[dict, ...]:
    return (
        {f['name']: f['type'] for f in fields if f['required']},
        {f['name']: f['type'] for f in fields if not f['required']},
        {f['name']: f['items'] for f in fields if 'items' in f},
    )


def _constants(entity: str) -> tuple[dict, ...]:
    return tuple(dict(table) for table in TABLES[entity])


def _field(fields: list[dict], name: str) -> dict:
    return next(f for f in fields if f['name'] == name)


def _issues(entity: str, payload: object) -> list[tuple[str, str]]:
    return [(issue.code, issue.field) for issue in VALIDATORS[entity](payload)]


@pytest.mark.parametrize('entity', [QUERY, CANDIDATE])
def test_constants_match_binding(entity: str) -> None:
    expected = _derive(_binding_fields(entity))
    assert expected[0], 'required table must not be empty'
    assert _constants(entity) == expected


def test_binding_version_matches_binding_and_fixture() -> None:
    fixture_version = json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))['binding_version']
    assert BINDING_VERSION == _binding()['binding_version'] == fixture_version


def test_binding_declares_no_enum_fields() -> None:
    assert [f['name'] for e in _binding()['entities'] for f in e['fields'] if 'enum' in f] == []


def test_drift_comparison_detects_mutated_binding() -> None:
    mutations = {
        'limit_optional': (QUERY, lambda fs: _field(fs, 'limit').update(required=False)),
        'limit_as_string': (QUERY, lambda fs: _field(fs, 'limit').update(type='string')),
        'roles_items_dropped': (QUERY, lambda fs: _field(fs, 'roles').pop('items')),
        'query_field_added': (QUERY, lambda fs: fs.append({'name': 'x_new', 'type': 'string', 'required': True})),
        'semantic_as_number': (CANDIDATE, lambda fs: _field(fs, 'semantic_match_components').update(type='number')),
        'reason_codes_optional': (CANDIDATE, lambda fs: _field(fs, 'reason_codes').update(required=False)),
        'candidate_field_added': (CANDIDATE, lambda fs: fs.append({'name': 'x_new', 'type': 'object', 'required': False})),
    }
    for name, (entity, mutate) in mutations.items():
        fields = _binding_fields(entity)
        mutate(fields)
        assert _derive(fields) != _constants(entity), name


INVALID_CASES = [(entity, case) for entity in (QUERY, CANDIDATE) for case in _fixture(entity)['invalid']]


@pytest.mark.parametrize('entity', [QUERY, CANDIDATE])
def test_fixture_valid_payloads_have_no_issues(entity: str) -> None:
    assert _fixture(entity)['valid']
    assert len(_fixture(entity)['invalid']) >= 2
    for payload in _fixture(entity)['valid']:
        assert _issues(entity, payload) == []


@pytest.mark.parametrize(('entity', 'case'), INVALID_CASES, ids=[f"{e}-{c['case']}" for e, c in INVALID_CASES])
def test_fixture_invalid_case_returns_expected_issue(entity: str, case: dict) -> None:
    expected = case['expected_error']
    assert _issues(entity, case['payload']) == [(expected['code'], expected['field'])]


def test_test_module_declares_covered_ids() -> None:
    doc = ast.get_docstring(ast.parse(pathlib.Path(__file__).read_text(encoding='utf-8')))
    assert 'coveredIds: CT-AI-006, CT-MED-005' in (doc or '').splitlines()


@pytest.mark.parametrize('entity', [QUERY, CANDIDATE])
def test_each_missing_required_field_is_reported(entity: str) -> None:
    assert TABLES[entity][0], 'required table must not be empty'
    for name in TABLES[entity][0]:
        payload = _fixture(entity)['valid'][0]
        del payload[name]
        assert _issues(entity, payload) == [(MISSING_REQUIRED, name)], name


@pytest.mark.parametrize(
    ('entity', 'field', 'value', 'code'),
    [
        (QUERY, 'limit', True, WRONG_TYPE),
        (QUERY, 'limit', 1.5, WRONG_TYPE),
        (QUERY, 'limit', None, WRONG_TYPE),
        (QUERY, 'media_kinds', [1], WRONG_TYPE),
        (QUERY, 'roles', 'illustration', WRONG_TYPE),
        (QUERY, 'scene_intent', [], WRONG_TYPE),
        (QUERY, 'production_snapshot_ref', 5, WRONG_TYPE),
        (QUERY, 'page_cursor', 5, WRONG_TYPE),
        (QUERY, 'excluded_usage_refs', 'x', WRONG_TYPE),
        (QUERY, 'technical_constraints', [], WRONG_TYPE),
        (QUERY, 'safety_policy_revision', MISSING, MISSING_REQUIRED),
        (CANDIDATE, 'availability', 5, WRONG_TYPE),
        (CANDIDATE, 'reason_codes', [1], WRONG_TYPE),
        (CANDIDATE, 'reason_codes', 'ENTITY_MATCH', WRONG_TYPE),
        (CANDIDATE, 'technical_fitness', None, WRONG_TYPE),
        (CANDIDATE, 'safety_rights_status', [], WRONG_TYPE),
        (CANDIDATE, 'provenance', 'catalog', WRONG_TYPE),
        (CANDIDATE, 'recent_usage_summary', 3, WRONG_TYPE),
        (CANDIDATE, 'media_asset_id', None, WRONG_TYPE),
    ],
)
def test_field_counterexamples_are_rejected(entity: str, field: str, value: object, code: str) -> None:
    payload = _fixture(entity)['valid'][0]
    if value is MISSING:
        del payload[field]
    else:
        payload[field] = value
    assert _issues(entity, payload) == [(code, field)]


@pytest.mark.parametrize('entity', [QUERY, CANDIDATE])
def test_unknown_field_is_ignored_and_non_mapping_is_wrong_type(entity: str) -> None:
    payload = _fixture(entity)['valid'][0]
    payload['x_future_optional_field'] = {'additive': True}
    assert _issues(entity, payload) == []
    for value in (None, [], 'payload'):
        assert _issues(entity, value) == [(WRONG_TYPE, '$')], value


def test_integer_type_rejects_bool() -> None:
    assert matches_type(1, 'integer') is True
    for value in (True, False, '1', 1.5, None):
        assert matches_type(value, 'integer') is False, value


def _query_inputs(**overrides: object) -> dict:
    inputs = _fixture(QUERY)['valid'][0]
    inputs.update(overrides)
    return inputs


def test_build_query_from_fixture_returns_frozen_query_equal_to_fixture_payload() -> None:
    valid = _fixture(QUERY)['valid'][0]
    query = build_media_candidate_query(**valid)
    assert isinstance(query, MediaCandidateQuery)
    assert MediaCandidateQuery.__dataclass_params__.frozen
    assert query.to_payload() == valid
    assert set(query.to_payload()) == set(QUERY_REQUIRED)
    assert validate_media_candidate_query(query.to_payload()) == []
    assert (query.limit, query.media_kinds) == (20, ('image', 'clip'))


def test_build_query_keeps_optional_fields_and_still_validates() -> None:
    query = build_media_candidate_query(**_query_inputs(
        technical_constraints={'min_height': 1080}, recency_diversity_preferences={'avoid_recent': True},
        excluded_usage_refs=['usage-1', 'usage-1', 'usage-2'], page_cursor='cursor-1'))
    payload = query.to_payload()
    assert payload['technical_constraints'] == {'min_height': 1080}
    assert payload['recency_diversity_preferences'] == {'avoid_recent': True}
    assert payload['excluded_usage_refs'] == ['usage-1', 'usage-2']
    assert payload['page_cursor'] == 'cursor-1'
    assert validate_media_candidate_query(payload) == []


@pytest.mark.parametrize(('overrides', 'reason'), [
    ({'safety_policy_revision': None}, 'missing_safety_policy_revision'),
    ({'safety_policy_revision': ''}, 'missing_safety_policy_revision'),
    ({'media_kinds': []}, 'missing_media_kinds'),
    ({'roles': []}, 'missing_roles'),
    ({'scene_intent': {}}, 'missing_scene_intent'),
])
def test_missing_query_inputs_are_input_not_ready(overrides: dict, reason: str) -> None:
    with pytest.raises(SelectionRejected) as excinfo:
        build_media_candidate_query(**_query_inputs(**overrides))
    assert (excinfo.value.code, excinfo.value.reason) == (INPUT_NOT_READY, reason)


@pytest.mark.parametrize('overrides', [
    {'limit': '20'}, {'limit': True}, {'limit': 0}, {'limit': 1.5}, {'production_snapshot_ref': ''},
    {'scene_intent': ['goal']}, {'media_kinds': 'image'}, {'roles': [1]}, {'excluded_usage_refs': [5]},
    {'page_cursor': ''}, {'technical_constraints': []}, {'safety_policy_revision': 5},
])
def test_malformed_query_arguments_raise_value_error(overrides: dict) -> None:
    with pytest.raises(ValueError):
        build_media_candidate_query(**_query_inputs(**overrides))


def test_query_is_immutable_and_isolated_from_input() -> None:
    inputs = _query_inputs()
    expected = build_media_candidate_query(**_query_inputs())
    built = build_media_candidate_query(**inputs)
    inputs['scene_intent']['goal'] = 'changed'
    inputs['media_kinds'].append('audio')
    assert built == expected
    for name in ('limit', 'safety_policy_revision', 'media_kinds', 'unknown_attribute'):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(built, name, 'changed')
    with pytest.raises(TypeError):
        built.scene_intent['goal'] = 'changed'


def test_candidate_valid_fixtures_parse_to_frozen_candidates() -> None:
    assert _fixture(CANDIDATE)['valid']
    for payload in _fixture(CANDIDATE)['valid']:
        candidate = parse_media_candidate(copy.deepcopy(payload))
        assert isinstance(candidate, MediaCandidate)
        assert MediaCandidate.__dataclass_params__.frozen
        assert candidate.to_payload() == payload
        assert candidate.reason_codes == ('ENTITY_MATCH',)


def test_candidate_invalid_fixtures_are_rejected_at_boundary() -> None:
    cases = _fixture(CANDIDATE)['invalid']
    assert cases
    for case in cases:
        with pytest.raises(ValueError):
            parse_media_candidate(case['payload'])


def test_candidate_is_immutable_and_isolated_from_input() -> None:
    payload = _fixture(CANDIDATE)['valid'][0]
    candidate = parse_media_candidate(payload)
    payload['semantic_match_components']['entity'] = 0.0
    payload['reason_codes'].append('X')
    assert candidate.to_payload() == _fixture(CANDIDATE)['valid'][0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        candidate.availability = 'RETIRED'
    with pytest.raises(TypeError):
        candidate.semantic_match_components['entity'] = 0.0


WS = 'ws-1'
POLICY = SafetyRightsPolicy(revision='safe-v1', allowed_availability=('AVAILABLE',), required_flags=('rights_cleared',), blocked_flags=('unsafe',))
WEIGHTS = ScoringWeights(semantic=0.6, technical=0.4, recent_usage_penalty=0.1)


def _media(asset_id: str, **overrides: object) -> MediaCandidate:
    payload = _fixture(CANDIDATE)['valid'][0]
    payload.update(media_asset_id=asset_id, rendition_ref=f'{asset_id}-rend', artifact_version_ref=f'{asset_id}-av')
    payload.update(overrides)
    return parse_media_candidate(payload)


def _hook(kind: str, hook_id: str, **overrides: object) -> HookCandidate:
    values = dict(
        hook_kind=kind, hook_id=hook_id, revision_id=f'{hook_id}-r1', availability='AVAILABLE',
        safety_rights_status={'rights_cleared': True}, semantic_match_components={'topic': 0.7},
        provenance={'source': 'user_imported'})
    values.update(overrides)
    return HookCandidate(**values)


def _thumb(thumb_id: str, **overrides: object) -> ThumbnailCandidate:
    values = dict(
        thumbnail_id=thumb_id, revision_id=f'{thumb_id}-r1', subject_refs=('entity-1',), crop_focus={'x': 0.5, 'y': 0.4},
        overlay_intent='question_mark', availability='AVAILABLE', safety_rights_status={'rights_cleared': True},
        semantic_match_components={'entity': 0.8}, provenance={'source': 'catalog'})
    values.update(overrides)
    return ThumbnailCandidate(**values)


def _ref(ref_type: str, ref_id: str, revision_id: str, workspace_id: str = WS) -> dict:
    return {'workspace_id': workspace_id, 'ref_type': ref_type, 'ref_id': ref_id, 'revision_id': revision_id}


def _scene(scene_id: str, asset_id: str, rationale: str = 'shot') -> dict:
    return {'scene_id': scene_id, 'ref': _ref('media_asset', asset_id, f'{asset_id}-av'), 'rationale': rationale}


def _proposal(**overrides: object) -> dict:
    proposal = {
        'visual_hook': _ref('visual_hook', 'vh-1', 'vh-1-r1'),
        'audio_hook': _ref('audio_hook', 'ah-1', 'ah-1-r1'),
        'thumbnail': _ref('thumbnail', 'th-1', 'th-1-r1'),
        'scenes': [_scene('s-1', 'm-2', 'opens on the entity'), _scene('s-2', 'm-1', 'context shot')],
        'music_intents': [{'cue': 'intro', 'description': 'tense low strings'}],
        'sfx_intents': [{'cue': 'hook_hit', 'description': 'short impact'}],
        'rationale': 'angle-focused selection',
    }
    proposal.update(overrides)
    return proposal


def _inputs(**overrides: object) -> dict:
    inputs = {
        'workspace_id': WS, 'snapshot_ref': 'snap-1', 'script_ref': 'script-1', 'angle_ref': 'angle-1',
        'media_candidates': [
            _media('m-1'),
            _media('m-2', semantic_match_components={'entity': 0.5, 'topic': 0.4}, technical_fitness={'resolution': '720p', 'score': 0.5}),
            _media('m-3', semantic_match_components={'entity': 0.7}, technical_fitness={'resolution': '1080p', 'score': 0.8}, recent_usage_summary={'times_used': 2}),
        ],
        'visual_hook_candidates': [_hook('visual_hook', 'vh-1'), _hook('visual_hook', 'vh-2')],
        'audio_hook_candidates': [_hook('audio_hook', 'ah-1')],
        'thumbnail_candidates': [_thumb('th-1')],
        'proposal': _proposal(),
        'safety_policy': POLICY, 'music_sfx_policy_revision': 'music-v1', 'preset_registry_revision': 'preset-v1',
        'weights': WEIGHTS,
    }
    inputs.update(overrides)
    return inputs


def _reject(**overrides: object) -> SelectionRejected:
    with pytest.raises(SelectionRejected) as excinfo:
        select_creative_assets(**_inputs(**overrides))
    return excinfo.value


def test_selection_returns_assignments_intents_fallbacks_rationale_scores_and_fingerprint() -> None:
    result = select_creative_assets(**_inputs())
    assert isinstance(result, CreativeAssetSelection)
    assert CreativeAssetSelection.__dataclass_params__.frozen
    got = [(a.order, a.scene_id, a.media_asset_id, a.rendition_ref, a.artifact_version_ref) for a in result.assignments]
    assert got == [(0, 's-1', 'm-2', 'm-2-rend', 'm-2-av'), (1, 's-2', 'm-1', 'm-1-rend', 'm-1-av')]
    assert [a.rationale for a in result.assignments] == ['opens on the entity', 'context shot']
    assert result.visual_hook == ResourceRef(WS, 'visual_hook', 'vh-1', 'vh-1-r1')
    assert result.audio_hook == ResourceRef(WS, 'audio_hook', 'ah-1', 'ah-1-r1')
    assert result.thumbnail == ResourceRef(WS, 'thumbnail', 'th-1', 'th-1-r1')
    assert result.thumbnail_overlay_intent == 'question_mark'
    assert [dict(i) for i in result.music_intents] == [{'cue': 'intro', 'description': 'tense low strings'}]
    assert [dict(i) for i in result.sfx_intents] == [{'cue': 'hook_hit', 'description': 'short impact'}]
    assert [f.media_asset_id for f in result.fallback_candidates] == ['m-3']
    assert result.fallback_candidates[0].total_score == pytest.approx(0.54)
    assert result.rationale == 'angle-focused selection'
    assert set(result.score_components) == {'m-1', 'm-2', 'm-3'}
    assert dict(result.score_components['m-1']) == pytest.approx({'semantic': 0.85, 'technical': 1.0, 'recent_usage': 0.0, 'total': 0.91})
    assert result.score_components['m-2']['total'] == pytest.approx(0.47)
    assert (result.safety_policy_revision, result.music_sfx_policy_revision) == ('safe-v1', 'music-v1')
    assert (result.preset_registry_revision, result.snapshot_ref) == ('preset-v1', 'snap-1')
    assert re.fullmatch('[0-9a-f]{64}', result.selection_fingerprint)
    assert result.to_payload()['selection_fingerprint'] == result.selection_fingerprint
    candidate_ids = {c.media_asset_id for c in _inputs()['media_candidates']}
    assert {a.media_asset_id for a in result.assignments} <= candidate_ids


def test_every_proposed_ref_goes_through_the_d03_resolver(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    class SpyResolver(RefResolver):
        def resolve(self, proposed):
            calls.append((proposed['ref_type'], proposed['ref_id']))
            return super().resolve(proposed)

    monkeypatch.setattr(module, 'RefResolver', SpyResolver)
    select_creative_assets(**_inputs())
    assert calls == [('visual_hook', 'vh-1'), ('audio_hook', 'ah-1'), ('thumbnail', 'th-1'), ('media_asset', 'm-2'), ('media_asset', 'm-1')]


BLOCKED_MEDIA = {
    'rights_not_cleared': {'safety_rights_status': {'rights_cleared': False}},
    'unsafe_flag': {'safety_rights_status': {'rights_cleared': True, 'unsafe': True}},
    'retired': {'availability': 'RETIRED'},
    'rights_missing': {'safety_rights_status': {}},
}


@pytest.mark.parametrize('overrides', list(BLOCKED_MEDIA.values()), ids=list(BLOCKED_MEDIA))
def test_blocked_media_candidate_is_excluded_everywhere(overrides: dict) -> None:
    inputs = _inputs()
    inputs['media_candidates'] = [*inputs['media_candidates'], _media('m-blocked', **overrides)]
    result = select_creative_assets(**inputs)
    assert 'm-blocked' not in result.score_components
    assert [f.media_asset_id for f in result.fallback_candidates] == ['m-3']
    assert 'm-blocked' not in json.dumps(result.to_payload())
    inputs['proposal'] = _proposal(scenes=[_scene('s-1', 'm-blocked')])
    with pytest.raises(SelectionRejected) as excinfo:
        select_creative_assets(**inputs)
    assert (excinfo.value.code, excinfo.value.field) == (CANDIDATE_BLOCKED, 'scenes[0].ref')


@pytest.mark.parametrize(('slot', 'name', 'blocked'), [
    ('visual_hook', 'visual_hook_candidates', _hook('visual_hook', 'vh-bad', safety_rights_status={'rights_cleared': False})),
    ('audio_hook', 'audio_hook_candidates', _hook('audio_hook', 'ah-bad', availability='RETIRED')),
    ('thumbnail', 'thumbnail_candidates', _thumb('th-bad', safety_rights_status={'rights_cleared': True, 'unsafe': True})),
])
def test_blocked_hook_or_thumbnail_cannot_be_selected(slot: str, name: str, blocked: object) -> None:
    inputs = _inputs()
    inputs[name] = [*inputs[name], blocked]
    ref_id = blocked.ref_id
    inputs['proposal'] = _proposal(**{slot: _ref(slot, ref_id, f'{ref_id}-r1')})
    with pytest.raises(SelectionRejected) as excinfo:
        select_creative_assets(**inputs)
    assert (excinfo.value.code, excinfo.value.field) == (CANDIDATE_BLOCKED, slot)


def test_policy_is_caller_input_not_hardcoded() -> None:
    relaxed = SafetyRightsPolicy(revision='relaxed-v1', allowed_availability=('AVAILABLE', 'RETIRED'), required_flags=(), blocked_flags=())
    inputs = _inputs(safety_policy=relaxed)
    inputs['media_candidates'] = [*inputs['media_candidates'], _media('m-4', safety_rights_status={'rights_cleared': False}), _media('m-5', availability='RETIRED')]
    result = select_creative_assets(**inputs)
    assert [f.media_asset_id for f in result.fallback_candidates] == ['m-4', 'm-5', 'm-3']
    assert result.safety_policy_revision == 'relaxed-v1'


FLAGGED = {'rights_cleared': True, 'needs_image_safety': True}


def test_fallback_candidates_exclude_unused_images_that_still_need_image_safety() -> None:
    inputs = _inputs()
    inputs['media_candidates'] = [*inputs['media_candidates'], _media('m-flagged', safety_rights_status=FLAGGED, semantic_match_components={'entity': 1.0, 'topic': 1.0})]
    result = select_creative_assets(**inputs)
    assert [f.media_asset_id for f in result.fallback_candidates] == ['m-3']
    assert 'm-flagged' in result.score_components


def test_fallback_candidates_keep_score_order_when_needs_image_safety_is_false() -> None:
    cleared = {'rights_cleared': True, 'needs_image_safety': False}
    inputs = _inputs()
    inputs['media_candidates'] = [*inputs['media_candidates'], _media('m-cleared', safety_rights_status=cleared, semantic_match_components={'entity': 1.0, 'topic': 1.0})]
    result = select_creative_assets(**inputs)
    totals = result.score_components
    assert totals['m-cleared']['total'] != totals['m-3']['total']
    expected = sorted(['m-3', 'm-cleared'], key=lambda item: (-totals[item]['total'], item))
    assert [f.media_asset_id for f in result.fallback_candidates] == expected


def test_an_image_that_needs_image_safety_can_still_be_chosen_for_a_scene() -> None:
    inputs = _inputs()
    inputs['media_candidates'] = [*inputs['media_candidates'], _media('m-flagged', safety_rights_status=FLAGGED)]
    inputs['proposal'] = _proposal(scenes=[_scene('s-1', 'm-flagged'), _scene('s-2', 'm-1')])
    result = select_creative_assets(**inputs)
    assert [a.media_asset_id for a in result.assignments] == ['m-flagged', 'm-1']
    assert 'm-flagged' not in [f.media_asset_id for f in result.fallback_candidates]


@pytest.mark.parametrize('slot', ['visual_hook', 'audio_hook', 'thumbnail'])
@pytest.mark.parametrize('absent', [True, False], ids=['absent', 'none'])
def test_missing_required_hook_is_rejected(slot: str, absent: bool) -> None:
    proposal = _proposal()
    if absent:
        del proposal[slot]
    else:
        proposal[slot] = None
    rejected = _reject(proposal=proposal)
    assert (rejected.code, rejected.reason, rejected.field) == (MISSING_REQUIRED_HOOK, slot, slot)


HALLUCINATIONS = [
    ('scene', _ref('media_asset', 'm-9', 'm-9-av'), 'unknown_ref'),
    ('scene', _ref('media_asset', 'm-1', 'm-1-av', workspace_id='ws-2'), 'workspace_mismatch'),
    ('scene', _ref('media_asset', 'm-1', 'm-1-old'), 'revision_mismatch'),
    ('scene', _ref('dedup_observation', 'm-1', 'm-1-av'), 'not_allowlisted'),
    ('scene', _ref('visual_hook', 'vh-1', 'vh-1-r1'), 'ref_type_mismatch'),
    ('scene', {}, 'unknown_ref'),
    ('visual_hook', _ref('visual_hook', 'vh-9', 'vh-9-r1'), 'unknown_ref'),
    ('visual_hook', _ref('media_asset', 'm-1', 'm-1-av'), 'ref_type_mismatch'),
    ('audio_hook', _ref('audio_hook', 'ah-1', 'ah-1-r1', workspace_id='ws-2'), 'workspace_mismatch'),
    ('thumbnail', _ref('thumbnail', 'th-1', 'th-old'), 'revision_mismatch'),
]


@pytest.mark.parametrize(('slot', 'proposed', 'reason'), HALLUCINATIONS, ids=[f'{h[0]}-{h[2]}-{i}' for i, h in enumerate(HALLUCINATIONS)])
def test_ref_outside_candidate_set_is_rejected_as_hallucinated(slot: str, proposed: dict, reason: str) -> None:
    proposal = _proposal()
    if slot == 'scene':
        proposal['scenes'][0]['ref'] = proposed
    else:
        proposal[slot] = proposed
    rejected = _reject(proposal=proposal)
    assert (rejected.code, rejected.reason) == (HALLUCINATED_REF, reason)


@pytest.mark.parametrize(('overrides', 'reason'), [
    ({'safety_policy': None}, 'missing_safety_policy'),
    ({'music_sfx_policy_revision': None}, 'missing_music_sfx_policy_revision'),
    ({'music_sfx_policy_revision': ''}, 'missing_music_sfx_policy_revision'),
    ({'preset_registry_revision': None}, 'missing_preset_registry_revision'),
    ({'weights': None}, 'missing_scoring_weights'),
])
def test_missing_policy_inputs_are_input_not_ready(overrides: dict, reason: str) -> None:
    rejected = _reject(**overrides)
    assert (rejected.code, rejected.reason) == (INPUT_NOT_READY, reason)


def test_policy_construction_requires_revision_and_availability() -> None:
    with pytest.raises(SelectionRejected) as excinfo:
        SafetyRightsPolicy(revision='', allowed_availability=('AVAILABLE',), required_flags=(), blocked_flags=())
    assert (excinfo.value.code, excinfo.value.reason) == (INPUT_NOT_READY, 'missing_safety_policy_revision')
    with pytest.raises(SelectionRejected) as excinfo:
        SafetyRightsPolicy(revision='safe-v1', allowed_availability=(), required_flags=(), blocked_flags=())
    assert (excinfo.value.code, excinfo.value.reason) == (INPUT_NOT_READY, 'missing_allowed_availability')
    with pytest.raises(ValueError):
        ScoringWeights(semantic=-1, technical=0.4, recent_usage_penalty=0.1)


INVALID_PROPOSALS = [
    (_proposal(scenes=[]), 'scenes_missing', 'scenes'),
    (_proposal(scenes='s-1'), 'scenes_missing', 'scenes'),
    (_proposal(scenes=['s-1']), 'not_a_mapping', 'scenes[0]'),
    (_proposal(scenes=[{'ref': _ref('media_asset', 'm-1', 'm-1-av'), 'rationale': 'x'}]), 'scene_id_missing', 'scenes[0].scene_id'),
    (_proposal(scenes=[_scene('s-1', 'm-1'), _scene('s-1', 'm-2')]), 'duplicate_scene_id', 'scenes[1].scene_id'),
    (_proposal(scenes=[{'scene_id': 's-1', 'ref': _ref('media_asset', 'm-1', 'm-1-av')}]), 'rationale_missing', 'scenes[0].rationale'),
    (_proposal(scenes=[{'scene_id': 's-1', 'rationale': 'x'}]), 'not_a_mapping', 'scenes[0].ref'),
    (_proposal(rationale=''), 'rationale_missing', 'rationale'),
    (_proposal(music_intents=None), 'music_intents_missing', 'music_intents'),
    (_proposal(sfx_intents='boom'), 'sfx_intents_missing', 'sfx_intents'),
    (_proposal(music_intents=[{'cue': 'intro'}]), 'cue_and_description_required', 'music_intents[0]'),
    (_proposal(sfx_intents=['x']), 'not_a_mapping', 'sfx_intents[0]'),
]


@pytest.mark.parametrize(('proposal', 'reason', 'field'), INVALID_PROPOSALS, ids=[p[1] + '-' + p[2] for p in INVALID_PROPOSALS])
def test_invalid_proposal_structure_is_rejected(proposal: dict, reason: str, field: str) -> None:
    rejected = _reject(proposal=proposal)
    assert (rejected.code, rejected.reason, rejected.field) == (INVALID_PROPOSAL, reason, field)


def test_non_mapping_proposal_is_rejected_and_intents_drop_unknown_keys() -> None:
    rejected = _reject(proposal=['x'])
    assert (rejected.code, rejected.reason) == (INVALID_PROPOSAL, 'proposal_not_mapping')
    noisy = _proposal(music_intents=[{'cue': 'a', 'description': 'b', 'tool_call': 'x', 'url': 'http://example.invalid'}])
    result = select_creative_assets(**_inputs(proposal=noisy))
    assert [dict(i) for i in result.music_intents] == [{'cue': 'a', 'description': 'b'}]


def _fingerprint(**overrides: object) -> str:
    return select_creative_assets(**_inputs(**overrides)).selection_fingerprint


def test_fingerprint_is_sha256_of_basis_and_stable_across_candidate_order() -> None:
    base = select_creative_assets(**_inputs())
    basis = base.fingerprint_basis()
    text = json.dumps(basis, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    assert base.selection_fingerprint == hashlib.sha256(text.encode('utf-8')).hexdigest()
    assert base.selection_fingerprint == canonicalization.request_hash(basis)
    assert 'rationale' not in basis and 'score_components' not in basis and 'selection_fingerprint' not in basis
    assert _fingerprint() == base.selection_fingerprint
    inputs = _inputs()
    for name in ('media_candidates', 'visual_hook_candidates'):
        inputs[name] = list(reversed(inputs[name]))
    reordered = select_creative_assets(**inputs)
    assert reordered.selection_fingerprint == base.selection_fingerprint
    assert reordered.to_payload() == base.to_payload()


def test_fingerprint_changes_with_each_selected_element() -> None:
    base = _fingerprint()
    variants = {
        'scene_order': _proposal(scenes=list(reversed(_proposal()['scenes']))),
        'media_pick': _proposal(scenes=[_scene('s-1', 'm-2'), _scene('s-2', 'm-3')]),
        'visual_hook': _proposal(visual_hook=_ref('visual_hook', 'vh-2', 'vh-2-r1')),
        'music_intent': _proposal(music_intents=[{'cue': 'intro', 'description': 'bright piano'}]),
        'sfx_intent': _proposal(sfx_intents=[]),
    }
    for name, proposal in variants.items():
        assert _fingerprint(proposal=proposal) != base, name
    for overrides in ({'preset_registry_revision': 'preset-v2'}, {'music_sfx_policy_revision': 'music-v2'}, {'snapshot_ref': 'snap-2'}, {'script_ref': 'script-2'}, {'angle_ref': 'angle-2'}):
        assert _fingerprint(**overrides) != base, overrides


def test_fingerprint_ignores_rationale_text() -> None:
    proposal = _proposal(rationale='different words')
    proposal['scenes'][0]['rationale'] = 'other words'
    assert _fingerprint(proposal=proposal) == _fingerprint()


def test_selection_is_immutable_and_isolated_from_input() -> None:
    inputs = _inputs()
    expected = select_creative_assets(**_inputs())
    result = select_creative_assets(**inputs)
    inputs['proposal']['music_intents'][0]['description'] = 'changed'
    inputs['proposal']['scenes'].clear()
    assert result == expected
    for name in ('selection_fingerprint', 'assignments', 'rationale', 'unknown_attribute'):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(result, name, 'changed')
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.assignments[0].scene_id = 'changed'
    with pytest.raises(TypeError):
        result.music_intents[0]['description'] = 'changed'
    with pytest.raises(TypeError):
        result.score_components['m-1']['total'] = 0.0
    with pytest.raises(TypeError):
        result.score_components['x'] = {}


def test_duplicate_candidates_and_wrong_candidate_types_are_rejected() -> None:
    with pytest.raises(ValueError):
        select_creative_assets(**_inputs(media_candidates=[_media('m-1'), _media('m-1')]))
    with pytest.raises(TypeError):
        select_creative_assets(**_inputs(media_candidates=[{'media_asset_id': 'm-1'}]))
    with pytest.raises(ValueError):
        select_creative_assets(**_inputs(visual_hook_candidates=[_hook('audio_hook', 'ah-9')]))


ALLOWED_IMPORTS = frozenset({
    '__future__', 'copy', 'dataclasses', 'math', 'collections.abc', 'types',
    'controlplane.application.idempotency.canonicalization', 'creative.domain.ref_resolver',
})


def test_module_imports_stay_inside_allowlist_and_reuse_d03_and_request_hash() -> None:
    found: set[str] = set()
    for node in ast.walk(ast.parse(MODULE_SOURCE.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.add('.' * node.level + (node.module or ''))
    assert found <= ALLOWED_IMPORTS, found
    assert module.request_hash is canonicalization.request_hash
    assert module.RefResolver is ref_resolver.RefResolver
    assert module.ResourceRef is ref_resolver.ResourceRef
