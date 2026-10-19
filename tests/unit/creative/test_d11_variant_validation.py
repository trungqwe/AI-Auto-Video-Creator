"""D-11: VariantValidation (CT-AI-008, CT-ORC-012 phía D).

coveredIds: CT-AI-008, TST-AI-INV-013, TST-AI-INV-014, TST-WF-VAR-004
"""
from __future__ import annotations

import ast
import dataclasses
import hashlib
import inspect
import json
import pathlib
import re
from types import MappingProxyType

import pytest
from controlplane.application.idempotency import canonicalization
from controlplane.domain import orchestration
from controlplane.domain.orchestration import ReservationState, VariantReservation
from creative.domain import variant as module
from creative.domain.asset_selection import CreativeAssetSelection, FallbackCandidate, SceneAssignment
from creative.domain.production_plan import build_production_plan
from creative.domain.ref_resolver import ResourceRef
from creative.domain.script import ScriptSegment, ScriptVersion
from creative.domain.variant import (
    CONTEXT_MISMATCH,
    DISTINCT_FACTORS,
    INPUT_NOT_READY,
    INVALID_INPUT,
    PHASE_OUTPUT,
    PHASE_PLAN,
    REASON_EXACT_DUPLICATE,
    REASON_NO_DISTINCT_FACTOR,
    REASON_SAME_RUN_ANGLE_DUPLICATE,
    REASON_VALID,
    CompletedVariant,
    SameRunVariant,
    VariantFingerprint,
    VariantRejected,
    build_variant_fingerprint,
    validate_variant,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
MODULE_SOURCE = ROOT / 'src' / 'creative' / 'domain' / 'variant.py'
WS = 'ws-1'
ANGLE_A = 'angle-fp-a'
ANGLE_B = 'angle-fp-b'
H1 = hashlib.sha256(b'output-1').hexdigest()
H2 = hashlib.sha256(b'output-2').hexdigest()


def _script(script_id='sv-1', texts=('Hello world', 'Second scene'), scene_intents=('scene 1', 'scene 2')):
    segments = tuple(
        ScriptSegment(
            segment_id=f's{i}', order=i, text=text, claim_mode='transition', scene_intent=scene_intents[i],
            source_refs=(), disclosure=None, word_count=len(text.split()), estimated_seconds=len(text.split()) / 2.0,
        )
        for i, text in enumerate(texts)
    )
    return ScriptVersion(
        script_version_id=script_id, language='en', hook_intent='hook', thumbnail_transition='fade', segments=segments,
        pronunciation_hints=(), speech_rate=2.0, estimated_duration_seconds=sum(s.estimated_seconds for s in segments),
    )


def _selection(script_id='sv-1', snapshot_ref='snap-1', angle_ref='angle-1', visual_hook='vh-1', rationale='overall'):
    base = CreativeAssetSelection(
        snapshot_ref=snapshot_ref, script_ref=script_id, angle_ref=angle_ref, safety_policy_revision='safety-r1',
        music_sfx_policy_revision='ms-r1', preset_registry_revision='preset-reg-r1',
        visual_hook=ResourceRef(WS, 'visual_hook', visual_hook, 'vh-r1'), audio_hook=ResourceRef(WS, 'audio_hook', 'ah-1', 'ah-r1'),
        thumbnail=ResourceRef(WS, 'thumbnail', 'th-1', 'th-r1'), thumbnail_overlay_intent='title card',
        assignments=(
            SceneAssignment(order=0, scene_id='sc-1', media_asset_id='m-1', rendition_ref='rend-1', artifact_version_ref='av-1', rationale='r1'),
            SceneAssignment(order=1, scene_id='sc-2', media_asset_id='m-2', rendition_ref='rend-2', artifact_version_ref='av-2', rationale='r2'),
        ),
        music_intents=(MappingProxyType({'cue': 'intro_pad', 'description': 'soft pad'}), MappingProxyType({'cue': 'outro_pad', 'description': 'calm pad'})),
        sfx_intents=(MappingProxyType({'cue': 'whoosh', 'description': 'short whoosh'}), MappingProxyType({'cue': 'ding', 'description': 'short ding'})),
        fallback_candidates=(FallbackCandidate(media_asset_id='m-3', rendition_ref='rend-3', artifact_version_ref='av-3', total_score=0.5),),
        rationale=rationale, score_components=MappingProxyType({}),
    )
    return dataclasses.replace(base, selection_fingerprint=base.compute_fingerprint())


def _visual(asset, start, end):
    return {'media_asset_id': asset, 'start_ms': start, 'end_ms': end, 'crop_intent': 'center on subject', 'overlay_intent': 'lower third', 'effect_intent': 'slow push-in'}


def _raw():
    return {
        'timeline': {'segments': [
            {'scene_id': 'sc-1', 'start_ms': 0, 'end_ms': 8000, 'transition_intent': 'hard cut', 'visuals': [_visual('m-1', 0, 8000)]},
            {'scene_id': 'sc-2', 'start_ms': 8000, 'end_ms': 20000, 'transition_intent': 'cross dissolve', 'visuals': [_visual('m-2', 8000, 12000), _visual('m-1', 12000, 20000)]},
        ]},
        'hook_placement': {'hook_time_range': {'start_ms': 0, 'end_ms': 5000}, 'thumbnail_time_range': {'start_ms': 1200, 'end_ms': 2400}},
        'voice_profile_intent': {'direction': 'warm and confident', 'pace': 'steady', 'emotion': 'curious'},
        'music_cues': [{'cue': 'intro_pad', 'start_ms': 0, 'end_ms': 20000}],
        'sfx_cues': [{'cue': 'whoosh', 'start_ms': 7800, 'end_ms': 8200}],
        'subtitle_style_intent': {'style': 'bold white captions', 'karaoke': True, 'highlight_intent': 'active word turns yellow'},
        'allowed_fallbacks': [
            {'rule_id': 'fb-1', 'kind': 'replace_asset', 'scene_id': 'sc-2', 'replacement_media_asset_id': 'm-3'},
            {'rule_id': 'fb-2', 'kind': 'simplify_transition', 'scene_id': 'sc-1'},
        ],
        'output_metadata_requirement': 'english title, caption and 3-4 hashtags (CT-AI-009)',
    }


def _plan(raw=None, *, script=None, selection=None, plan_id='plan-1', preset='preset-rev-1'):
    script = script or _script()
    selection = selection or _selection(script_id=script.script_version_id)
    return build_production_plan(raw or _raw(), production_plan_id=plan_id, script=script, selection=selection, preset_revision_ref=preset)


def _fingerprint(raw=None, *, script=None, selection=None, angle=ANGLE_A, plan_id='plan-1', preset='preset-rev-1'):
    script = script or _script()
    selection = selection or _selection(script_id=script.script_version_id)
    plan = _plan(raw, script=script, selection=selection, plan_id=plan_id, preset=preset)
    return build_variant_fingerprint(script=script, plan=plan, selection=selection, angle_distinction_fingerprint=angle)


def _sha(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _fp(tag, **overrides):
    # Yếu tố không bị override lấy theo tag; override bằng đúng tag của fingerprint khác cho cùng giá trị yếu tố đó.
    factors = {name: _sha(f'{overrides.get(name, tag)}:{name}') for name in DISTINCT_FACTORS}
    return VariantFingerprint(factors=factors, fingerprint=_sha(f'{tag}|{sorted(overrides.items())}'))


def _reservation(reservation_id, fingerprint, *, job='job-2', state=ReservationState.ACTIVE):
    return VariantReservation(
        reservation_id=reservation_id, workspace_id=WS, job_id=job, fingerprint=fingerprint.fingerprint, snapshot_scope='scope-1',
        validation_ref='val-1', variation_policy_revision='vp-1', committed_registry_revision=7, state=state,
    )


def _completed(ref, fingerprint):
    return CompletedVariant(ref_id=ref, fingerprint=fingerprint)


def _sibling(ref, fingerprint):
    return SameRunVariant(ref_id=ref, fingerprint=fingerprint)


def _validate(**overrides):
    kwargs = {
        'candidate': _fp('base'), 'completed': (), 'active_reservations': (), 'registry_revision': 7, 'same_run': (),
        'variation_policy_revision': 'vp-1', 'phase': PHASE_PLAN, 'own_reservation_id': None, 'output_hash': None,
    }
    kwargs.update(overrides)
    return validate_variant(**kwargs)


def _rejected(call):
    with pytest.raises(VariantRejected) as info:
        call()
    return (info.value.code, info.value.reason, info.value.field)


def _module_tree():
    return ast.parse(MODULE_SOURCE.read_text(encoding='utf-8'))


def test_module_and_test_docstrings_declare_covered_ids():
    for file_path in (pathlib.Path(__file__), MODULE_SOURCE):
        doc = ast.get_docstring(ast.parse(file_path.read_text(encoding='utf-8')))
        assert doc is not None
        assert 'coveredIds: CT-AI-008, TST-AI-INV-013, TST-AI-INV-014, TST-WF-VAR-004' in doc.splitlines()


def test_module_imports_stay_inside_allowlist_and_reuse_controlplane_reservation():
    allowed = {
        '__future__', 're', 'collections.abc', 'dataclasses', 'types',
        'controlplane.application.idempotency.canonicalization', 'controlplane.domain.orchestration',
        'creative.domain.angles', 'creative.domain.asset_selection', 'creative.domain.production_plan', 'creative.domain.script',
    }
    for node in ast.walk(_module_tree()):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name in allowed
        elif isinstance(node, ast.ImportFrom):
            assert '.' * node.level + (node.module or '') in allowed
    assert module.request_hash is canonicalization.request_hash
    assert module.VariantReservation is orchestration.VariantReservation
    assert module.VariantReservation is VariantReservation


def test_module_creates_no_reservation_calls_no_ai_and_takes_no_seed():
    for node in ast.walk(_module_tree()):
        if isinstance(node, ast.ClassDef):
            assert 'reservation' not in node.name.lower()
        elif isinstance(node, ast.FunctionDef):
            assert not any(word in node.name.lower() for word in ('reserve', 'release', 'invoke', 'seed'))
        elif isinstance(node, ast.Name):
            assert not any(word in node.id.lower() for word in ('seed', 'random', 'uuid'))
        elif isinstance(node, ast.arg):
            assert 'seed' not in node.arg.lower()
    assert set(inspect.signature(build_variant_fingerprint).parameters) == {'script', 'plan', 'selection', 'angle_distinction_fingerprint'}
    assert set(inspect.signature(validate_variant).parameters) == {
        'candidate', 'completed', 'active_reservations', 'registry_revision', 'same_run',
        'variation_policy_revision', 'phase', 'own_reservation_id', 'output_hash',
    }


def _factor_case(factor):
    raw, kwargs = _raw(), {}
    if factor == 'voice':
        raw['voice_profile_intent']['emotion'] = 'urgent'
    elif factor == 'sound':
        raw['sfx_cues'][0]['cue'] = 'ding'
    elif factor == 'hook':
        kwargs['selection'] = _selection(visual_hook='vh-2')
    elif factor == 'media':
        raw['timeline']['segments'][1]['visuals'] = [_visual('m-1', 8000, 12000), _visual('m-2', 12000, 20000)]
    elif factor == 'effects':
        raw['timeline']['segments'][0]['visuals'][0]['effect_intent'] = 'whip pan'
    elif factor == 'content':
        kwargs['script'] = _script(texts=('Hello world', 'Different words'))
    elif factor == 'narration_style':
        kwargs['script'] = _script(scene_intents=('scene 1', 'scene 9'))
    elif factor == 'background_music':
        raw['music_cues'][0]['cue'] = 'outro_pad'
    else:
        assert factor == 'angle'
        kwargs['angle'] = ANGLE_B
    return raw, kwargs


@pytest.mark.parametrize('factor', DISTINCT_FACTORS)
def test_each_real_content_change_moves_only_its_factor(factor):
    base = _fingerprint()
    raw, kwargs = _factor_case(factor)
    changed = _fingerprint(raw, **kwargs)
    moved = tuple(name for name in DISTINCT_FACTORS if changed.factors[name] != base.factors[name])
    assert moved == (factor,)
    assert changed.fingerprint != base.fingerprint


def test_fingerprint_ignores_ids_revisions_and_rationale():
    base = _fingerprint()
    selection = _selection(script_id='sv-77', snapshot_ref='snap-9', angle_ref='angle-9', rationale='another rationale')
    other = _fingerprint(script=_script(script_id='sv-77'), selection=selection, plan_id='plan-9', preset='preset-rev-9')
    assert dict(other.factors) == dict(base.factors)
    assert other.fingerprint == base.fingerprint


def test_factors_ignore_case_and_whitespace_only_text_changes():
    base = _fingerprint()
    changed = _fingerprint(script=_script(texts=('  HELLO   world ', 'Second  scene')))
    assert dict(changed.factors) == dict(base.factors)


def test_plan_detail_outside_factors_changes_only_the_exact_fingerprint():
    raw = _raw()
    raw['allowed_fallbacks'][1]['kind'] = 'drop_overlay_effect'
    base, changed = _fingerprint(), _fingerprint(raw)
    assert dict(changed.factors) == dict(base.factors)
    assert changed.fingerprint != base.fingerprint


def test_fingerprint_shape_is_deterministic_and_immutable():
    fp = _fingerprint()
    assert tuple(fp.factors) == DISTINCT_FACTORS
    for value in (*fp.factors.values(), fp.fingerprint):
        assert re.fullmatch(r'[0-9a-f]{64}', value)
    assert fp.to_payload() == {'factors': dict(fp.factors), 'fingerprint': fp.fingerprint}
    json.dumps(fp.to_payload())
    assert _fingerprint().fingerprint == fp.fingerprint
    with pytest.raises(dataclasses.FrozenInstanceError):
        fp.fingerprint = 'x'
    with pytest.raises(TypeError):
        fp.factors['voice'] = 'x'


def _build(**overrides):
    script, selection = _script(), _selection()
    kwargs = {'script': script, 'plan': _plan(script=script, selection=selection), 'selection': selection, 'angle_distinction_fingerprint': ANGLE_A}
    kwargs.update(overrides)
    return build_variant_fingerprint(**kwargs)


_ANGLE_MISSING = (INPUT_NOT_READY, 'missing_angle_distinction_fingerprint', 'angle_distinction_fingerprint')


@pytest.mark.parametrize(
    'overrides, expected',
    [
        ({'script': None}, (INPUT_NOT_READY, 'missing_script_version', 'script')),
        ({'plan': None}, (INPUT_NOT_READY, 'missing_production_plan', 'plan')),
        ({'selection': None}, (INPUT_NOT_READY, 'missing_asset_selection', 'selection')),
        ({'angle_distinction_fingerprint': ''}, _ANGLE_MISSING),
        ({'angle_distinction_fingerprint': None}, _ANGLE_MISSING),
        ({'script': _script(script_id='sv-2')}, (CONTEXT_MISMATCH, 'script_mismatch', 'plan.script_version_id')),
        ({'script': _script(texts=('Other', 'words'))}, (CONTEXT_MISMATCH, 'script_mismatch', 'plan.script_version_id')),
        ({'selection': _selection(snapshot_ref='snap-2')}, (CONTEXT_MISMATCH, 'selection_mismatch', 'plan.selection_fingerprint')),
    ],
)
def test_builder_rejects_missing_or_mismatched_inputs(overrides, expected):
    assert _rejected(lambda: _build(**overrides)) == expected


def test_builder_accepts_matching_inputs():
    assert _build().fingerprint == _fingerprint().fingerprint


def test_variant_fingerprint_and_priors_reject_malformed_values():
    good = _fp('x')
    factors = dict(good.factors)
    assert _rejected(lambda: VariantFingerprint(factors={'voice': factors['voice']}, fingerprint=good.fingerprint)) == (INVALID_INPUT, 'factors_mismatch', 'factors')
    assert _rejected(lambda: VariantFingerprint(factors={**factors, 'voice': 'not-a-hash'}, fingerprint=good.fingerprint)) == (INVALID_INPUT, 'invalid_sha256', 'factors.voice')
    assert _rejected(lambda: VariantFingerprint(factors=factors, fingerprint='ABC')) == (INVALID_INPUT, 'invalid_sha256', 'fingerprint')
    assert _rejected(lambda: CompletedVariant(ref_id='', fingerprint=good)) == (INPUT_NOT_READY, 'missing_ref_id', 'ref_id')
    assert _rejected(lambda: SameRunVariant(ref_id='v-1', fingerprint='x')) == (INVALID_INPUT, 'wrong_type', 'fingerprint')


def test_same_run_distinct_angles_are_valid():
    siblings = (_sibling('v-2', _fp('c', angle='a2')), _sibling('v-3', _fp('c', angle='a3')))
    result = _validate(candidate=_fp('c'), same_run=siblings)
    assert (result.valid, result.same_run_angle_distinct, result.exact_duplicate) == (True, True, False)
    assert result.reason_codes == (REASON_VALID,)


def test_same_run_same_angle_is_invalid_even_when_everything_else_differs():
    result = _validate(candidate=_fp('c'), same_run=(_sibling('v-2', _fp('zzz', angle='c')),))
    assert (result.valid, result.same_run_angle_distinct, result.exact_duplicate) == (False, False, False)
    assert result.reason_codes == (REASON_SAME_RUN_ANGLE_DUPLICATE,)


def test_same_run_effect_only_change_is_not_a_different_angle():
    result = _validate(candidate=_fp('c'), same_run=(_sibling('v-2', _fp('c', effects='fx2')),))
    assert (result.valid, result.same_run_angle_distinct) == (False, False)


def test_cross_run_one_real_factor_difference_is_valid():
    result = _validate(candidate=_fp('c'), completed=(_completed('h-1', _fp('c', voice='old')),))
    assert (result.valid, result.same_run_angle_distinct, result.exact_duplicate) == (True, True, False)
    assert result.distinct_factors == ('voice',)
    assert result.nearest_prior_refs == ('h-1',)
    assert result.reason_codes == (REASON_VALID,)


def test_cross_run_exact_duplicate_is_invalid():
    result = _validate(candidate=_fp('c'), completed=(_completed('h-1', _fp('c')),))
    assert (result.valid, result.exact_duplicate) == (False, True)
    assert result.distinct_factors == ()
    assert result.nearest_prior_refs == ('h-1',)
    assert result.reason_codes == (REASON_EXACT_DUPLICATE, REASON_NO_DISTINCT_FACTOR)


def test_cross_run_without_distinct_factor_is_invalid_even_when_not_exact():
    candidate = _fp('c')
    prior = dataclasses.replace(candidate, fingerprint=_sha('timing-only'))
    result = _validate(candidate=candidate, completed=(_completed('h-1', prior),))
    assert (result.valid, result.exact_duplicate, result.distinct_factors) == (False, False, ())
    assert result.reason_codes == (REASON_NO_DISTINCT_FACTOR,)


def test_nearest_prior_refs_use_fewest_differing_factors_with_sorted_ties():
    far = _completed('h-far', _fp('c', voice='x', sound='x', hook='x'))
    near_b = _completed('h-b', _fp('c', media='y'))
    near_a = _completed('h-a', _fp('c', effects='y'))
    result = _validate(candidate=_fp('c'), completed=(far, near_b, near_a))
    assert result.valid is True
    assert result.nearest_prior_refs == ('h-a', 'h-b')
    assert result.distinct_factors == ('effects',)


def test_no_history_is_valid_and_every_factor_counts_as_distinct():
    result = _validate(candidate=_fp('c'))
    assert result.valid is True
    assert result.distinct_factors == DISTINCT_FACTORS
    assert result.nearest_prior_refs == ()


def test_variants_that_differ_only_by_ids_are_duplicates():
    selection = _selection(script_id='sv-77', snapshot_ref='snap-9', angle_ref='angle-9', rationale='x')
    prior = _fingerprint(script=_script(script_id='sv-77'), selection=selection, plan_id='plan-9', preset='preset-rev-9')
    result = _validate(candidate=_fingerprint(), completed=(_completed('h-1', prior),))
    assert (result.valid, result.exact_duplicate) == (False, True)


@dataclasses.dataclass(frozen=True)
class _FakeReservation:
    # Cùng tên trường nhưng không phải VariantReservation của G.
    reservation_id: str
    fingerprint: str
    state: ReservationState = ReservationState.ACTIVE
    committed_registry_revision: int = 7


def test_other_job_reservation_with_same_fingerprint_blocks():
    candidate = _fp('c')
    result = _validate(candidate=candidate, active_reservations=(_reservation('r-2', candidate),), own_reservation_id='r-1')
    assert (result.valid, result.exact_duplicate) == (False, True)
    assert result.nearest_prior_refs == ('r-2',)
    assert result.reason_codes == (REASON_EXACT_DUPLICATE,)


def test_own_reservation_is_excluded_but_other_jobs_are_still_counted():
    candidate = _fp('c')
    own = _reservation('r-1', candidate, job='job-1')
    other = _reservation('r-2', candidate, job='job-2')
    assert _validate(candidate=candidate, active_reservations=(own,), own_reservation_id='r-1').valid is True
    blocked = _validate(candidate=candidate, active_reservations=(own, other), own_reservation_id='r-1')
    assert (blocked.valid, blocked.exact_duplicate) == (False, True)
    assert blocked.nearest_prior_refs == ('r-2',)


def test_without_own_reservation_id_every_reservation_counts():
    candidate = _fp('c')
    result = _validate(candidate=candidate, active_reservations=(_reservation('r-1', candidate, job='job-1'),), own_reservation_id=None)
    assert result.valid is False


def test_other_job_reservation_with_different_fingerprint_does_not_block():
    result = _validate(candidate=_fp('c'), active_reservations=(_reservation('r-2', _fp('d')),))
    assert result.valid is True
    assert result.nearest_prior_refs == ()


def test_reservation_must_be_the_controlplane_type():
    fake = _FakeReservation(reservation_id='r-2', fingerprint=_fp('c').fingerprint)
    assert _rejected(lambda: _validate(candidate=_fp('c'), active_reservations=(fake,))) == (INVALID_INPUT, 'wrong_type', 'active_reservations[0]')


def test_non_active_other_job_reservation_is_rejected_fail_closed():
    released = _reservation('r-2', _fp('c'), state=ReservationState.RELEASED)
    assert _rejected(lambda: _validate(candidate=_fp('c'), active_reservations=(released,))) == (INVALID_INPUT, 'reservation_not_active', 'active_reservations[0]')


def test_input_hashes_cover_inputs_and_ignore_order_and_own_reservation():
    candidate = _fp('c')
    h1, h2 = _completed('h-1', _fp('c', voice='a')), _completed('h-2', _fp('c', sound='b'))
    r2, own = _reservation('r-2', _fp('d')), _reservation('r-1', _fp('e'), job='job-1')
    base = _validate(candidate=candidate, completed=(h1, h2), active_reservations=(r2, own), own_reservation_id='r-1')
    assert set(base.input_hashes) == {'candidate', 'completed_history', 'active_reservations', 'same_run'}
    assert all(re.fullmatch(r'[0-9a-f]{64}', value) for value in base.input_hashes.values())
    reordered = _validate(candidate=candidate, completed=(h2, h1), active_reservations=(own, r2), own_reservation_id='r-1')
    assert dict(reordered.input_hashes) == dict(base.input_hashes)
    without_own = _validate(candidate=candidate, completed=(h1, h2), active_reservations=(r2,), own_reservation_id='r-1')
    assert without_own.input_hashes['active_reservations'] == base.input_hashes['active_reservations']
    more = _validate(candidate=candidate, completed=(h1, h2), active_reservations=(r2, _reservation('r-3', _fp('f'))), own_reservation_id='r-1')
    assert more.input_hashes['active_reservations'] != base.input_hashes['active_reservations']
    assert more.input_hashes['completed_history'] == base.input_hashes['completed_history']


def test_output_phase_requires_exact_output_hash():
    assert _rejected(lambda: _validate(phase=PHASE_OUTPUT)) == (INPUT_NOT_READY, 'missing_output_hash', 'output_hash')
    assert _rejected(lambda: _validate(phase=PHASE_OUTPUT, output_hash='abc')) == (INVALID_INPUT, 'invalid_sha256', 'output_hash')
    assert _rejected(lambda: _validate(phase=PHASE_PLAN, output_hash=H1)) == (INVALID_INPUT, 'output_hash_not_allowed_in_plan_phase', 'output_hash')
    result = _validate(phase=PHASE_OUTPUT, output_hash=H1)
    assert (result.phase, result.output_hash, result.input_hashes['output']) == (PHASE_OUTPUT, H1, H1)
    assert 'output' not in _validate().input_hashes


def test_plan_phase_result_cannot_confirm_output():
    plan_result = _validate(phase=PHASE_PLAN)
    assert plan_result.is_current_for(registry_revision=7, phase=PHASE_PLAN) is True
    assert plan_result.is_current_for(registry_revision=7, phase=PHASE_OUTPUT, output_hash=H1) is False
    assert plan_result.is_current_for(registry_revision=7, phase=PHASE_OUTPUT) is False
    out = _validate(phase=PHASE_OUTPUT, output_hash=H1)
    assert out.is_current_for(registry_revision=7, phase=PHASE_OUTPUT, output_hash=H1) is True
    assert out.is_current_for(registry_revision=7, phase=PHASE_OUTPUT, output_hash=H2) is False
    assert out.is_current_for(registry_revision=7, phase=PHASE_OUTPUT) is False
    assert out.is_current_for(registry_revision=7, phase=PHASE_PLAN) is False


def test_new_registry_revision_makes_old_result_stale():
    for result in (_validate(), _validate(phase=PHASE_OUTPUT, output_hash=H1)):
        kwargs = {'phase': result.phase, 'output_hash': result.output_hash}
        assert result.is_current_for(registry_revision=7, **kwargs) is True
        assert result.is_current_for(registry_revision=8, **kwargs) is False
    fresh = _validate(registry_revision=8)
    assert fresh.registry_revision == 8
    assert fresh.validation_hash != _validate().validation_hash


def test_result_records_inputs_and_is_immutable():
    result = _validate(own_reservation_id='r-1')
    assert (result.registry_revision, result.phase, result.variation_policy_revision, result.own_reservation_id) == (7, PHASE_PLAN, 'vp-1', 'r-1')
    assert re.fullmatch(r'[0-9a-f]{64}', result.validation_hash)
    assert result.validation_hash == _validate(own_reservation_id='r-1').validation_hash
    payload = result.to_payload()
    json.dumps(payload)
    assert set(payload) == {
        'valid', 'same_run_angle_distinct', 'exact_duplicate', 'distinct_factors', 'nearest_prior_refs', 'reason_codes',
        'input_hashes', 'registry_revision', 'phase', 'variation_policy_revision', 'own_reservation_id', 'output_hash',
    }
    assert type(payload['distinct_factors']) is list
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.valid = False
    with pytest.raises(TypeError):
        result.input_hashes['candidate'] = 'x'


_DUP_REF = (INVALID_INPUT, 'duplicate_ref')
_REVISION = (INPUT_NOT_READY, 'missing_registry_revision', 'registry_revision')
_POLICY = (INPUT_NOT_READY, 'missing_variation_policy_revision', 'variation_policy_revision')


@pytest.mark.parametrize(
    'overrides, expected',
    [
        ({'candidate': None}, (INVALID_INPUT, 'wrong_type', 'candidate')),
        ({'completed': ('x',)}, (INVALID_INPUT, 'wrong_type', 'completed[0]')),
        ({'completed': 'x'}, (INVALID_INPUT, 'wrong_type', 'completed')),
        ({'same_run': (_fp('a'),)}, (INVALID_INPUT, 'wrong_type', 'same_run[0]')),
        ({'active_reservations': None}, (INVALID_INPUT, 'wrong_type', 'active_reservations')),
        ({'registry_revision': -1}, _REVISION),
        ({'registry_revision': True}, _REVISION),
        ({'registry_revision': '7'}, _REVISION),
        ({'variation_policy_revision': ''}, _POLICY),
        ({'variation_policy_revision': None}, _POLICY),
        ({'phase': 'draft'}, (INVALID_INPUT, 'unknown_phase', 'phase')),
        ({'own_reservation_id': ''}, (INPUT_NOT_READY, 'missing_own_reservation_id', 'own_reservation_id')),
        ({'completed': (_completed('h-1', _fp('a')), _completed('h-1', _fp('b')))}, (*_DUP_REF, 'completed')),
        ({'same_run': (_sibling('v-1', _fp('a')), _sibling('v-1', _fp('b')))}, (*_DUP_REF, 'same_run')),
        ({'active_reservations': (_reservation('r-2', _fp('a')), _reservation('r-2', _fp('b')))}, (*_DUP_REF, 'active_reservations')),
    ],
)
def test_validate_variant_rejects_bad_inputs(overrides, expected):
    assert _rejected(lambda: _validate(**overrides)) == expected


def test_validation_does_not_mutate_inputs_or_touch_reservations():
    completed = [_completed('h-1', _fp('c', voice='a'))]
    reservations = [_reservation('r-2', _fp('d'))]
    same_run = [_sibling('v-2', _fp('c', angle='a2'))]
    snapshot = (list(completed), list(reservations), list(same_run))
    _validate(candidate=_fp('c'), completed=completed, active_reservations=reservations, same_run=same_run)
    assert (completed, reservations, same_run) == snapshot
    assert reservations[0].state is ReservationState.ACTIVE
