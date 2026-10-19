"""D-06: StoryAngle và StoryAngleSet 1-3 góc khác nhau (CT-AI-003, TST-AI-INV-013 mức góc kể).

coveredIds: CT-AI-003, TST-AI-INV-013
"""
import ast
import dataclasses
import hashlib
import json
import pathlib
import unicodedata

import pytest

from controlplane.application.idempotency import canonicalization
from creative.domain import angles as module
from creative.domain import ref_resolver
from creative.domain.angles import (
    EXCLUDED_LATEST_SCRIPT, GENERATION_INITIAL, GENERATION_NEW_SET, INITIAL_SET_NOT_EXHAUSTED, INPUT_NOT_READY,
    INSUFFICIENT_DISTINCT_ANGLES, REQUESTED_COUNT_OUT_OF_RANGE, SAME_RUN_ANGLE_DUPLICATE, AngleHistoryEntry,
    AngleSetRejected, ExcludedAngle, StoryAngle, StoryAngleSet, build_story_angle_set, compute_distinction_fingerprint,
    normalize_text,
)
from creative.domain.ref_resolver import ResourceRef

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_SOURCE = ROOT / 'src' / 'creative' / 'domain' / 'angles.py'
WS = 'ws-1'
REF = ResourceRef(WS, 'article_revision', 'art-1', 'rev-1')
VARIATION = 'variation-v1'
BASES = {
    'a': dict(narrative_question='Why did the bridge close?', focus_entities=['Bridge A'], timeframe='2026-03'),
    'b': dict(narrative_question='Who pays for the repair?', focus_entities=['City Council'], timeframe='2026-04'),
    'c': dict(narrative_question='What happens to commuters next?', focus_entities=['Commuters'], timeframe='2026-05'),
    'd': dict(narrative_question='Could the bridge reopen early?', focus_entities=['Bridge A', 'Contractor'], timeframe='2026-06'),
}


def _fields(**overrides: object) -> dict:
    values = dict(
        angle_id='angle-1', title='Title one', summary='Summary one',
        narrative_question='Why did the bridge close?', focus_entities=['City Council', 'Bridge A'], timeframe='2026-03',
        evidence_refs=[REF], planned_inference_elements=['likely cause'], planned_creative_elements=['map overlay'],
        suitability='high', risk_flags=['unconfirmed_cause'],
    )
    values.update(overrides)
    return values


def _angle(angle_id: str = 'angle-1', **overrides: object) -> StoryAngle:
    return StoryAngle(**_fields(angle_id=angle_id, **overrides))


def _basis_angle(key: str, angle_id: str, **overrides: object) -> StoryAngle:
    return _angle(angle_id, **{**BASES[key], **overrides})


def _three() -> list[StoryAngle]:
    return [_basis_angle('a', 'angle-a'), _basis_angle('b', 'angle-b'), _basis_angle('c', 'angle-c')]


def _entry(script_id: str, sequence: int, angle: StoryAngle) -> AngleHistoryEntry:
    return AngleHistoryEntry(script_id=script_id, sequence=sequence, distinction_fingerprint=angle.distinction_fingerprint)


def _build(**overrides: object) -> StoryAngleSet:
    values = dict(
        set_id='set-1', analysis_id='analysis-1', analysis_revision=1, requested_count=3,
        candidates=_three(), variation_policy_revision=VARIATION,
    )
    values.update(overrides)
    return build_story_angle_set(**values)


def _expected_fingerprint(question: str, entities: list[str], timeframe: str) -> str:
    basis = {'narrative_question': question, 'focus_entities': entities, 'timeframe': timeframe}
    return hashlib.sha256(json.dumps(basis, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')).hexdigest()


def test_test_module_declares_covered_ids() -> None:
    doc = ast.get_docstring(ast.parse(pathlib.Path(__file__).read_text(encoding='utf-8')))
    assert 'coveredIds: CT-AI-003, TST-AI-INV-013' in (doc or '').splitlines()


def test_story_angle_has_exactly_the_contract_fields() -> None:
    names = {f.name for f in dataclasses.fields(StoryAngle)}
    assert names == {
        'angle_id', 'title', 'summary', 'narrative_question', 'focus_entities', 'timeframe', 'evidence_refs',
        'planned_inference_elements', 'planned_creative_elements', 'distinction_fingerprint', 'suitability', 'risk_flags',
    }
    angle = _angle()
    assert angle.focus_entities == ('City Council', 'Bridge A')
    assert angle.evidence_refs == (REF,)
    assert angle.risk_flags == ('unconfirmed_cause',)
    assert len(angle.distinction_fingerprint) == 64
    assert set(angle.distinction_fingerprint) <= set('0123456789abcdef')


def test_fingerprint_is_sha256_over_normalized_question_entities_timeframe() -> None:
    angle = _angle(narrative_question='  Why DID the   bridge close? ', focus_entities=['City Council', 'Bridge A', 'bridge a'], timeframe=' 2026-03 ')
    expected = _expected_fingerprint('why did the bridge close?', ['bridge a', 'city council'], '2026-03')
    assert angle.distinction_fingerprint == expected
    assert compute_distinction_fingerprint('Why did the bridge close?', ['Bridge A', 'City Council'], '2026-03') == expected
    assert expected == canonicalization.request_hash(
        {'narrative_question': 'why did the bridge close?', 'focus_entities': ['bridge a', 'city council'], 'timeframe': '2026-03'})


def test_fingerprint_ignores_angle_id_title_summary_and_every_non_basis_field() -> None:
    first = _angle('angle-1')
    others = [
        _angle('angle-2', title='Other title', summary='Other summary'),
        _angle('angle-3', planned_creative_elements=['different style preset'], suitability='low', risk_flags=[]),
        _angle('angle-4', evidence_refs=[ResourceRef(WS, 'article_revision', 'art-2', 'rev-9')], planned_inference_elements=[]),
    ]
    assert {angle.distinction_fingerprint for angle in others} == {first.distinction_fingerprint}


@pytest.mark.parametrize('overrides', [
    {'narrative_question': 'Who pays for the repair?'},
    {'focus_entities': ['Bridge A', 'Contractor']},
    {'focus_entities': ['Bridge A']},
    {'timeframe': '2026-04'},
])
def test_fingerprint_changes_with_each_basis_field(overrides: dict) -> None:
    assert _angle(**overrides).distinction_fingerprint != _angle().distinction_fingerprint


def test_normalization_folds_case_whitespace_unicode_form_and_entity_order() -> None:
    composed = unicodedata.normalize('NFC', 'Hà Nội')
    decomposed = unicodedata.normalize('NFD', 'Hà Nội')
    assert composed != decomposed
    base = compute_distinction_fingerprint('Q?', [composed, 'B'], 'T')
    assert compute_distinction_fingerprint(' q? ', ['b', decomposed.upper(), 'B'], 't') == base
    assert normalize_text('  ＡB   c ') == 'ab c'


def test_diacritics_are_meaningful_and_not_stripped() -> None:
    assert compute_distinction_fingerprint('Q?', ['Ha Noi'], 'T') != compute_distinction_fingerprint('Q?', ['Hà Nội'], 'T')


@pytest.mark.parametrize(('overrides', 'error'), [
    ({'angle_id': ''}, ValueError), ({'title': '   '}, ValueError), ({'summary': None}, ValueError),
    ({'narrative_question': ''}, ValueError), ({'timeframe': ' '}, ValueError), ({'suitability': ''}, ValueError),
    ({'focus_entities': []}, ValueError), ({'focus_entities': 'Bridge A'}, ValueError), ({'focus_entities': ['']}, ValueError),
    ({'evidence_refs': []}, ValueError), ({'evidence_refs': [{'ref_id': 'x'}]}, TypeError), ({'evidence_refs': 'ref'}, TypeError),
    ({'planned_inference_elements': [1]}, ValueError), ({'planned_creative_elements': 'x'}, ValueError), ({'risk_flags': [None]}, ValueError),
])
def test_story_angle_rejects_malformed_fields(overrides: dict, error: type) -> None:
    with pytest.raises(error):
        _angle(**overrides)


def test_story_angle_is_frozen_and_isolated_from_input() -> None:
    entities = ['Bridge A']
    angle = _angle(focus_entities=entities)
    entities.append('Changed')
    assert angle.focus_entities == ('Bridge A',)
    for name in ('title', 'distinction_fingerprint', 'unknown_attribute'):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(angle, name, 'changed')
    with pytest.raises(TypeError):
        StoryAngle(**_fields(), distinction_fingerprint='forged')


def test_story_angle_to_payload_is_plain_json_data() -> None:
    payload = _angle().to_payload()
    assert payload['focus_entities'] == ['City Council', 'Bridge A']
    assert payload['evidence_refs'] == [{'workspace_id': WS, 'ref_type': 'article_revision', 'ref_id': 'art-1', 'revision_id': 'rev-1'}]
    assert payload['distinction_fingerprint'] == _angle().distinction_fingerprint
    assert set(payload) == {f.name for f in dataclasses.fields(StoryAngle)}
    json.dumps(payload)


@pytest.mark.parametrize('count', [0, 4, -1, 100, True, False, '3', None, 2.0])
def test_requested_count_outside_one_to_three_is_rejected(count: object) -> None:
    with pytest.raises(AngleSetRejected) as info:
        _build(requested_count=count)
    assert (info.value.code, info.value.field) == (REQUESTED_COUNT_OUT_OF_RANGE, 'requested_count')


@pytest.mark.parametrize('count', [1, 2, 3])
def test_requested_count_one_to_three_is_accepted(count: int) -> None:
    result = _build(requested_count=count)
    assert isinstance(result, StoryAngleSet)
    assert (result.requested_count, len(result.angles)) == (count, count)


def test_two_angles_with_same_fingerprint_in_one_set_are_rejected() -> None:
    twin = _angle('angle-9', title='Reworded title', summary='Reworded', planned_creative_elements=['other style'])
    with pytest.raises(AngleSetRejected) as info:
        _build(requested_count=2, candidates=[_angle('angle-1'), twin])
    assert (info.value.code, info.value.field) == (SAME_RUN_ANGLE_DUPLICATE, 'candidates[1]')


def test_three_angles_that_differ_only_in_title_style_and_id_are_rejected() -> None:
    candidates = [
        _angle(f'angle-{i}', title=f'Title {i}', summary=f'Summary {i}', planned_creative_elements=[f'style-{i}'])
        for i in range(3)
    ]
    with pytest.raises(AngleSetRejected) as info:
        _build(candidates=candidates)
    assert info.value.code == SAME_RUN_ANGLE_DUPLICATE


def test_angle_matching_latest_script_fingerprint_is_excluded_and_recorded() -> None:
    a, b, c = _three()
    b_twin = _basis_angle('b', 'angle-b2', title='Reworded title')
    result = _build(candidates=[a, b_twin, c], history=[_entry('script-1', 1, a), _entry('script-2', 2, b)])
    assert [angle.angle_id for angle in result.angles] == ['angle-a', 'angle-c']
    assert result.excluded == (
        ExcludedAngle(angle_id='angle-b2', distinction_fingerprint=b.distinction_fingerprint, reason=EXCLUDED_LATEST_SCRIPT),
    )


def test_latest_script_is_chosen_by_sequence_not_by_position() -> None:
    a, b, c = _three()
    for history in ([_entry('s1', 1, a), _entry('s2', 2, b)], [_entry('s2', 2, b), _entry('s1', 1, a)]):
        result = _build(candidates=[a, b, c], history=history)
        assert [angle.angle_id for angle in result.angles] == ['angle-a', 'angle-c']


def test_set_with_every_candidate_excluded_or_no_candidate_is_rejected() -> None:
    a, _, _ = _three()
    for candidates, history in (([a], [_entry('script-1', 1, a)]), ([], [])):
        with pytest.raises(AngleSetRejected) as info:
            _build(requested_count=1, candidates=candidates, history=history)
        assert (info.value.code, info.value.field) == (INSUFFICIENT_DISTINCT_ANGLES, 'candidates')


def test_set_is_truncated_to_requested_count_after_exclusion() -> None:
    a, b, c = _three()
    result = _build(requested_count=2, candidates=[a, b, c], history=[_entry('s1', 1, a)])
    assert [angle.angle_id for angle in result.angles] == ['angle-b', 'angle-c']
    assert [angle.angle_id for angle in _build(requested_count=1, candidates=[a, b, c]).angles] == ['angle-a']


def test_history_with_repeated_sequence_is_rejected() -> None:
    a, b, _ = _three()
    with pytest.raises(ValueError):
        _build(history=[_entry('s1', 1, a), _entry('s2', 1, b)])


@pytest.mark.parametrize('sequence', [0, -1, True, '1', None])
def test_history_entry_requires_positive_integer_sequence(sequence: object) -> None:
    with pytest.raises(ValueError):
        AngleHistoryEntry(script_id='s1', sequence=sequence, distinction_fingerprint='f' * 64)


def test_new_set_is_allowed_only_after_every_initial_angle_was_exploited() -> None:
    a, b, _ = _three()
    initial = [a.distinction_fingerprint, b.distinction_fingerprint]
    d = _basis_angle('d', 'angle-d')
    history = [_entry('s1', 1, a), _entry('s2', 2, b)]
    result = _build(requested_count=1, candidates=[d], history=history, initial_set_fingerprints=initial)
    assert result.generation == GENERATION_NEW_SET
    assert _build().generation == GENERATION_INITIAL
    with pytest.raises(AngleSetRejected) as info:
        _build(requested_count=1, candidates=[d], history=[_entry('s1', 1, a)], initial_set_fingerprints=initial)
    assert (info.value.code, info.value.field) == (INITIAL_SET_NOT_EXHAUSTED, 'initial_set_fingerprints')
    with pytest.raises(AngleSetRejected) as info:
        _build(requested_count=1, candidates=[b], history=history, initial_set_fingerprints=initial)
    assert info.value.code == INSUFFICIENT_DISTINCT_ANGLES


def test_set_records_variation_policy_revision() -> None:
    assert _build().variation_policy_revision == VARIATION
    assert _build(variation_policy_revision='variation-v2').variation_policy_revision == 'variation-v2'
    assert _build().to_payload()['variation_policy_revision'] == VARIATION


@pytest.mark.parametrize('revision', [None, '', '  ', 5])
def test_missing_variation_policy_revision_is_input_not_ready(revision: object) -> None:
    with pytest.raises(AngleSetRejected) as info:
        _build(variation_policy_revision=revision)
    assert (info.value.code, info.value.field) == (INPUT_NOT_READY, 'variation_policy_revision')


def test_set_is_frozen_isolated_from_input_and_serializable() -> None:
    candidates = _three()
    history = [_entry('s1', 1, candidates[0])]
    result = _build(candidates=candidates, history=history)
    payload = result.to_payload()
    candidates.clear()
    history.clear()
    assert result.to_payload() == payload
    assert isinstance(result.angles, tuple) and isinstance(result.excluded, tuple)
    assert [angle.angle_id for angle in result.angles] == ['angle-b', 'angle-c']
    assert [item['angle_id'] for item in payload['excluded']] == ['angle-a']
    json.dumps(payload)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.angles = ()


def test_malformed_inputs_are_rejected() -> None:
    with pytest.raises(TypeError):
        _build(candidates=[{'angle_id': 'x'}])
    with pytest.raises(TypeError):
        _build(candidates='angle')
    with pytest.raises(TypeError):
        _build(history=['script-1'])
    with pytest.raises(ValueError):
        _build(requested_count=2, candidates=[_angle('angle-1'), _basis_angle('b', 'angle-1')])
    for overrides in ({'set_id': ''}, {'analysis_id': ' '}, {'analysis_revision': 0}, {'analysis_revision': True}, {'initial_set_fingerprints': 'abc'}):
        with pytest.raises(ValueError):
            _build(**overrides)


ALLOWED_IMPORTS = {
    '__future__', 'unicodedata', 'collections.abc', 'dataclasses',
    'controlplane.application.idempotency.canonicalization', 'creative.domain.ref_resolver',
}


def test_module_imports_stay_inside_allowlist_and_reuse_request_hash() -> None:
    found: set[str] = set()
    for node in ast.walk(ast.parse(MODULE_SOURCE.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.add('.' * node.level + (node.module or ''))
    assert found <= ALLOWED_IMPORTS, found
    assert module.request_hash is canonicalization.request_hash
    assert module.ResourceRef is ref_resolver.ResourceRef
