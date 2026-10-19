"""E-13: PrepareAudioBed validators (CT-AUD-001). Loudness numbers below are test-only fixtures.

coveredIds: CT-AUD-001
"""

from __future__ import annotations

import ast
import dataclasses
import math
import pathlib
import re
import pytest

from voice.domain.audio_bed import (
    AudioBedError,
    AudioBedRejected,
    AudioBedRequest,
    AudioBedResult,
    AudioCue,
    CONSTRAINT_VIOLATION,
    CueTiming,
    INPUT_NOT_READY,
    LOUDNESS_OUT_OF_TARGET,
    LoudnessConstraints,
    LoudnessFinding,
    LoudnessReport,
    MISSING_REQUIRED,
    PreparedRendition,
    SUBSTITUTION_NOT_ALLOWED,
    Substitution,
    WRONG_TYPE,
    build_audio_bed_result,
    detect_substitutions,
    validate_loudness_report,
)

MODULE_PATH = pathlib.Path(__file__).resolve().parents[3] / 'src' / 'voice' / 'domain' / 'audio_bed.py'


def _err(func, *args, **kwargs) -> tuple[str, str]:
    with pytest.raises(AudioBedError) as info:
        func(*args, **kwargs)
    return info.value.code, info.value.field


def _cue(**changes) -> AudioCue:
    defaults = {
        'kind': 'music',
        'start_ms': 0,
        'end_ms': 4000,
        'artifact_ref': 'artifact://music-a',
        'mood': 'calm',
    }
    defaults.update(changes)
    return AudioCue(**defaults)


def _constraints(**changes) -> LoudnessConstraints:
    defaults = {
        'min_lufs': -23.0,
        'max_lufs': -18.0,
        'max_true_peak_dbtp': -1.5,
    }
    defaults.update(changes)
    return LoudnessConstraints(**defaults)


def _report(**changes) -> LoudnessReport:
    defaults = {
        'integrated_lufs': -20.0,
        'true_peak_dbtp': -3.0,
    }
    defaults.update(changes)
    return LoudnessReport(**defaults)


def _request(**changes) -> AudioBedRequest:
    defaults = {
        'cues': (_cue(), _cue(kind='sfx', start_ms=1000, end_ms=1500, artifact_ref='artifact://sfx-a', mood=None)),
        'voice_artifact_ref': 'artifact://voice-1',
        'preset_audio_policy_revision': 'audio-policy-r1',
        'loudness_constraints': _constraints(),
        'mix_constraints': {'duck': 'fixture'},
        'fallback_allowed': False,
        'fallback_artifact_refs': (),
    }
    defaults.update(changes)
    return AudioBedRequest(**defaults)


def _renditions(request: AudioBedRequest) -> list[PreparedRendition]:
    return [
        PreparedRendition(
            cue_index=i,
            rendition_ref=f'rendition://{i}',
            source_artifact_ref=cue.artifact_ref,
            mood=cue.mood,
        )
        for i, cue in enumerate(request.cues)
    ]


def _build(request: AudioBedRequest, **changes) -> AudioBedResult:
    return build_audio_bed_result(
        request,
        renditions=changes.get('renditions', _renditions(request)),
        loudness_report=changes.get('loudness_report', _report()),
        provenance={'source': 'fixture'},
        risk_metadata={'risk': 'low'},
        warnings=changes.get('warnings', ()),
    )


# --- 1/4 Cue tests ---


def test_valid_cue_is_frozen() -> None:
    cue = _cue()
    with pytest.raises(dataclasses.FrozenInstanceError):
        cue.start_ms = 1  # type: ignore[misc]


@pytest.mark.parametrize(
    'changes,expected',
    [
        ({'start_ms': 1000, 'end_ms': 1000}, (CONSTRAINT_VIOLATION, 'end_ms')),
        ({'start_ms': 2000, 'end_ms': 1000}, (CONSTRAINT_VIOLATION, 'end_ms')),
        ({'start_ms': -1}, (CONSTRAINT_VIOLATION, 'start_ms')),
        ({'end_ms': -5}, (CONSTRAINT_VIOLATION, 'end_ms')),
        ({'start_ms': True}, (WRONG_TYPE, 'start_ms')),
        ({'end_ms': True}, (WRONG_TYPE, 'end_ms')),
        ({'start_ms': '0'}, (WRONG_TYPE, 'start_ms')),
        ({'start_ms': 0.0}, (WRONG_TYPE, 'start_ms')),
        ({'kind': 'voice'}, (CONSTRAINT_VIOLATION, 'kind')),
        ({'kind': 5}, (WRONG_TYPE, 'kind')),
        ({'kind': None}, (MISSING_REQUIRED, 'kind')),
        ({'artifact_ref': None}, (MISSING_REQUIRED, 'artifact_ref')),
        ({'artifact_ref': '  '}, (CONSTRAINT_VIOLATION, 'artifact_ref')),
        ({'artifact_ref': 5}, (WRONG_TYPE, 'artifact_ref')),
        ({'mood': 5}, (WRONG_TYPE, 'mood')),
    ],
    ids=[
        'start_equals_end',
        'start_greater_than_end',
        'start_negative',
        'end_negative',
        'start_bool',
        'end_bool',
        'start_str',
        'start_float',
        'kind_unknown',
        'kind_int',
        'kind_none',
        'artifact_ref_none',
        'artifact_ref_blank',
        'artifact_ref_int',
        'mood_int',
    ],
)
def test_invalid_cue_is_rejected(changes: dict, expected: tuple[str, str]) -> None:
    assert _err(_cue, **changes) == expected


# --- 2/4 Request / Constraints / Report tests ---


def test_valid_request_is_frozen_and_normalized() -> None:
    req = _request(
        cues=[_cue(), _cue(kind='sfx', artifact_ref='artifact://sfx-a', start_ms=10, end_ms=20)],
        fallback_artifact_refs=['artifact://music-b'],
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        req.fallback_allowed = True  # type: ignore[misc]
    assert isinstance(req.cues, tuple)
    assert isinstance(req.fallback_artifact_refs, tuple)


def test_request_does_not_alias_mix_constraints() -> None:
    mix = {'duck': 'fixture', 'level': 0.5}
    req = _request(mix_constraints=mix)
    mix['duck'] = 'mutated'
    assert req.mix_constraints['duck'] == 'fixture'
    with pytest.raises(TypeError):
        req.mix_constraints['x'] = 1  # type: ignore[index]

    req_none = _request(mix_constraints=None)
    assert req_none.mix_constraints is None


def test_request_allows_none_loudness_constraints() -> None:
    req = _request(loudness_constraints=None)
    assert req.loudness_constraints is None


@pytest.mark.parametrize(
    'changes,expected',
    [
        ({'cues': ()}, (CONSTRAINT_VIOLATION, 'cues')),
        ({'cues': [{'kind': 'music'}]}, (WRONG_TYPE, 'cues')),
        ({'cues': None}, (MISSING_REQUIRED, 'cues')),
        ({'cues': 'abc'}, (WRONG_TYPE, 'cues')),
        ({'voice_artifact_ref': None}, (MISSING_REQUIRED, 'voice_artifact_ref')),
        ({'voice_artifact_ref': ''}, (CONSTRAINT_VIOLATION, 'voice_artifact_ref')),
        ({'voice_artifact_ref': 7}, (WRONG_TYPE, 'voice_artifact_ref')),
        ({'preset_audio_policy_revision': None}, (MISSING_REQUIRED, 'preset_audio_policy_revision')),
        ({'preset_audio_policy_revision': ' '}, (CONSTRAINT_VIOLATION, 'preset_audio_policy_revision')),
        ({'loudness_constraints': {'min_lufs': -23.0}}, (WRONG_TYPE, 'loudness_constraints')),
        ({'mix_constraints': [1]}, (WRONG_TYPE, 'mix_constraints')),
        ({'fallback_allowed': 1}, (WRONG_TYPE, 'fallback_allowed')),
        ({'fallback_allowed': 'yes'}, (WRONG_TYPE, 'fallback_allowed')),
        ({'fallback_allowed': None}, (MISSING_REQUIRED, 'fallback_allowed')),
        ({'fallback_artifact_refs': [5]}, (WRONG_TYPE, 'fallback_artifact_refs')),
        ({'fallback_artifact_refs': ['']}, (CONSTRAINT_VIOLATION, 'fallback_artifact_refs')),
    ],
    ids=[
        'cues_empty',
        'cues_elements_not_audiocue',
        'cues_none',
        'cues_str',
        'voice_ref_none',
        'voice_ref_empty',
        'voice_ref_int',
        'preset_none',
        'preset_blank',
        'loudness_dict',
        'mix_list',
        'fallback_int',
        'fallback_str',
        'fallback_none',
        'fallback_refs_item_int',
        'fallback_refs_item_empty',
    ],
)
def test_invalid_request_is_rejected(changes: dict, expected: tuple[str, str]) -> None:
    assert _err(_request, **changes) == expected


@pytest.mark.parametrize(
    'changes,expected',
    [
        ({'min_lufs': True}, (WRONG_TYPE, 'min_lufs')),
        ({'max_lufs': '-18'}, (WRONG_TYPE, 'max_lufs')),
        ({'max_true_peak_dbtp': False}, (WRONG_TYPE, 'max_true_peak_dbtp')),
        ({'min_lufs': math.nan}, (CONSTRAINT_VIOLATION, 'min_lufs')),
        ({'max_lufs': math.inf}, (CONSTRAINT_VIOLATION, 'max_lufs')),
        ({'min_lufs': -10.0, 'max_lufs': -30.0}, (CONSTRAINT_VIOLATION, 'min_lufs')),
    ],
    ids=[
        'min_lufs_bool',
        'max_lufs_str',
        'true_peak_bool',
        'min_lufs_nan',
        'max_lufs_inf',
        'min_lufs_greater_than_max',
    ],
)
def test_invalid_constraints_are_rejected(changes: dict, expected: tuple[str, str]) -> None:
    assert _err(_constraints, **changes) == expected


def test_constraints_allow_none_bounds_at_construction() -> None:
    c = LoudnessConstraints(min_lufs=None, max_lufs=-18.0, max_true_peak_dbtp=-1.5)
    assert c.min_lufs is None
    assert c.max_lufs == -18.0
    assert c.max_true_peak_dbtp == -1.5


@pytest.mark.parametrize(
    'changes,expected',
    [
        ({'integrated_lufs': True}, (WRONG_TYPE, 'integrated_lufs')),
        ({'true_peak_dbtp': '-3'}, (WRONG_TYPE, 'true_peak_dbtp')),
        ({'integrated_lufs': None}, (MISSING_REQUIRED, 'integrated_lufs')),
        ({'true_peak_dbtp': math.nan}, (CONSTRAINT_VIOLATION, 'true_peak_dbtp')),
    ],
    ids=[
        'integrated_bool',
        'true_peak_str',
        'integrated_none',
        'true_peak_nan',
    ],
)
def test_invalid_report_is_rejected(changes: dict, expected: tuple[str, str]) -> None:
    assert _err(_report, **changes) == expected


# --- 3/4 Loudness tests ---


def test_missing_constraints_is_input_not_ready() -> None:
    with pytest.raises(AudioBedRejected) as info:
        validate_loudness_report(_report(), None)
    assert info.value.code == INPUT_NOT_READY
    assert info.value.reason == 'missing_loudness_constraints'

    for partial in (
        LoudnessConstraints(min_lufs=None, max_lufs=-18.0, max_true_peak_dbtp=-1.5),
        LoudnessConstraints(min_lufs=-23.0, max_lufs=None, max_true_peak_dbtp=-1.5),
        LoudnessConstraints(min_lufs=-23.0, max_lufs=-18.0, max_true_peak_dbtp=None),
    ):
        with pytest.raises(AudioBedRejected) as partial_info:
            validate_loudness_report(_report(), partial)
        assert partial_info.value.code == INPUT_NOT_READY
        assert partial_info.value.reason == 'missing_loudness_constraints'


def test_report_inside_target_has_no_findings() -> None:
    assert validate_loudness_report(_report(), _constraints()) == ()


def test_report_on_exact_boundaries_has_no_findings() -> None:
    c = _constraints(min_lufs=-23.0, max_lufs=-18.0, max_true_peak_dbtp=-1.5)
    assert validate_loudness_report(_report(integrated_lufs=-23.0, true_peak_dbtp=-1.5), c) == ()
    assert validate_loudness_report(_report(integrated_lufs=-18.0, true_peak_dbtp=-1.5), c) == ()


def test_integrated_below_min_is_out_of_target() -> None:
    rep_low = _report(integrated_lufs=-30.0)
    assert validate_loudness_report(rep_low, _constraints()) == (
        LoudnessFinding(LOUDNESS_OUT_OF_TARGET, 'integrated_lufs', -30.0),
    )

    rep_high = _report(integrated_lufs=-10.0)
    assert validate_loudness_report(rep_high, _constraints()) == (
        LoudnessFinding(LOUDNESS_OUT_OF_TARGET, 'integrated_lufs', -10.0),
    )


def test_true_peak_above_max_is_out_of_target() -> None:
    rep = _report(true_peak_dbtp=0.0)
    assert validate_loudness_report(rep, _constraints()) == (
        LoudnessFinding(LOUDNESS_OUT_OF_TARGET, 'true_peak_dbtp', 0.0),
    )


def test_both_measurements_out_of_target() -> None:
    rep = _report(integrated_lufs=-30.0, true_peak_dbtp=0.0)
    assert validate_loudness_report(rep, _constraints()) == (
        LoudnessFinding(LOUDNESS_OUT_OF_TARGET, 'integrated_lufs', -30.0),
        LoudnessFinding(LOUDNESS_OUT_OF_TARGET, 'true_peak_dbtp', 0.0),
    )


def test_target_comes_from_argument_not_code() -> None:
    rep = _report(integrated_lufs=-20.0)
    assert validate_loudness_report(rep, _constraints(min_lufs=-23.0, max_lufs=-18.0)) == ()

    custom_constraints = _constraints(min_lufs=-30.0, max_lufs=-25.0, max_true_peak_dbtp=-1.5)
    findings = validate_loudness_report(rep, custom_constraints)
    assert findings == (
        LoudnessFinding(LOUDNESS_OUT_OF_TARGET, 'integrated_lufs', -20.0),
    )

    assert _err(_constraints, min_lufs=-14.0, max_lufs=-16.0) == (CONSTRAINT_VIOLATION, 'min_lufs')


def test_validate_loudness_report_rejects_wrong_report_type() -> None:
    assert _err(validate_loudness_report, {'integrated_lufs': -20.0}, _constraints()) == (WRONG_TYPE, 'report')
    assert _err(validate_loudness_report, _report(), {'min_lufs': -23.0}) == (WRONG_TYPE, 'constraints')


# --- 4/4 Substitutions / Result / Static tests ---


def _swap(renditions: list[PreparedRendition], i: int, **changes) -> list[PreparedRendition]:
    copy_list = list(renditions)
    copy_list[i] = dataclasses.replace(copy_list[i], **changes)
    return copy_list


def test_matching_renditions_build_result() -> None:
    req = _request()
    res = _build(req)
    assert isinstance(res, AudioBedResult)
    assert res.substitutions == ()
    assert res.cue_timings == (CueTiming(0, 0, 4000), CueTiming(1, 1000, 1500))
    assert res.loudness_report == _report()
    assert res.provenance == {'source': 'fixture'}
    assert res.risk_metadata == {'risk': 'low'}
    assert res.warnings == ()

    with pytest.raises(dataclasses.FrozenInstanceError):
        res.warnings = ('mutated',)  # type: ignore[misc]

    with pytest.raises(TypeError):
        res.provenance['x'] = 1  # type: ignore[index]


def test_track_swap_without_fallback_is_rejected() -> None:
    req = _request(fallback_allowed=False, fallback_artifact_refs=('artifact://music-b',))
    rends = _swap(_renditions(req), 0, source_artifact_ref='artifact://music-b')

    assert _err(detect_substitutions, req, rends) == (SUBSTITUTION_NOT_ALLOWED, 'renditions')
    assert _err(_build, req, renditions=rends) == (SUBSTITUTION_NOT_ALLOWED, 'renditions')

    rends_mood = _swap(_renditions(req), 0, mood='tense')
    assert _err(detect_substitutions, req, rends_mood) == (SUBSTITUTION_NOT_ALLOWED, 'renditions')
    assert _err(_build, req, renditions=rends_mood) == (SUBSTITUTION_NOT_ALLOWED, 'renditions')


def test_substitution_recording_when_fallback_allowed() -> None:
    req = _request(fallback_allowed=True, fallback_artifact_refs=('artifact://music-b',))
    rends_track = _swap(_renditions(req), 0, source_artifact_ref='artifact://music-b')
    subs_track = detect_substitutions(req, rends_track)
    assert subs_track == (Substitution(0, 'track', 'artifact://music-a', 'artifact://music-b'),)
    res_track = _build(req, renditions=rends_track)
    assert res_track.substitutions == subs_track

    rends_mood = _swap(_renditions(req), 0, mood='tense')
    subs_mood = detect_substitutions(req, rends_mood)
    assert subs_mood == (Substitution(0, 'mood', 'calm', 'tense'),)

    rends_both = _swap(_renditions(req), 0, source_artifact_ref='artifact://music-b', mood='tense')
    subs_both = detect_substitutions(req, rends_both)
    assert subs_both == (
        Substitution(0, 'track', 'artifact://music-a', 'artifact://music-b'),
        Substitution(0, 'mood', 'calm', 'tense'),
    )

    rends_cross = _swap(_renditions(req), 1, source_artifact_ref='artifact://music-a')
    subs_cross = detect_substitutions(req, rends_cross)
    assert subs_cross == (
        Substitution(1, 'track', 'artifact://sfx-a', 'artifact://music-a'),
    )


def test_track_outside_given_refs_is_rejected_even_with_fallback() -> None:
    req = _request(fallback_allowed=True, fallback_artifact_refs=())
    rends = _swap(_renditions(req), 0, source_artifact_ref='artifact://music-new')
    assert _err(detect_substitutions, req, rends) == (SUBSTITUTION_NOT_ALLOWED, 'renditions')


def test_invalid_renditions_and_substitutions_structure_rejected() -> None:
    req = _request()
    base_rends = _renditions(req)

    rends_bad_index = _swap(base_rends, 0, cue_index=5)
    assert _err(detect_substitutions, req, rends_bad_index) == (CONSTRAINT_VIOLATION, 'renditions')

    rends_dup = [base_rends[0], base_rends[0]]
    assert _err(detect_substitutions, req, rends_dup) == (CONSTRAINT_VIOLATION, 'renditions')

    rends_missing = [base_rends[0]]
    assert _err(detect_substitutions, req, rends_missing) == (CONSTRAINT_VIOLATION, 'renditions')

    assert _err(PreparedRendition, cue_index=True, rendition_ref='r', source_artifact_ref='s') == (
        WRONG_TYPE,
        'cue_index',
    )
    assert _err(PreparedRendition, cue_index=-1, rendition_ref='r', source_artifact_ref='s') == (
        CONSTRAINT_VIOLATION,
        'cue_index',
    )
    assert _err(Substitution, 0, 'genre', 'a', 'b') == (CONSTRAINT_VIOLATION, 'change')
    assert _err(Substitution, True, 'track', 'a', 'b') == (WRONG_TYPE, 'cue_index')


def test_build_precedence_and_validation() -> None:
    req_no_constraints = _request(
        loudness_constraints=None,
        fallback_allowed=False,
    )
    rends_bad = _swap(_renditions(req_no_constraints), 0, source_artifact_ref='artifact://music-b')
    with pytest.raises(AudioBedRejected) as info:
        build_audio_bed_result(
            req_no_constraints,
            renditions=rends_bad,
            loudness_report=_report(),
            provenance={},
            risk_metadata={},
        )
    assert info.value.code == INPUT_NOT_READY

    req_valid = _request(fallback_allowed=False)
    rep_out_of_target = _report(integrated_lufs=-30.0)
    assert _err(
        build_audio_bed_result,
        req_valid,
        renditions=rends_bad,
        loudness_report=rep_out_of_target,
        provenance={},
        risk_metadata={},
    ) == (LOUDNESS_OUT_OF_TARGET, 'integrated_lufs')

    assert _err(
        build_audio_bed_result,
        {'cues': 1},
        renditions=[],
        loudness_report=_report(),
        provenance={},
        risk_metadata={},
    ) == (WRONG_TYPE, 'request')


def test_result_sources_are_within_given_refs() -> None:
    req = _request(fallback_allowed=True, fallback_artifact_refs=('artifact://music-b',))
    rends = _swap(_renditions(req), 0, source_artifact_ref='artifact://music-b')
    res = _build(req, renditions=rends)
    given_refs = {cue.artifact_ref for cue in req.cues} | set(req.fallback_artifact_refs)
    for r in res.renditions:
        assert r.source_artifact_ref in given_refs


def test_result_constructor_normalizes_and_validates() -> None:
    req = _request()
    res = AudioBedResult(
        renditions=list(_renditions(req)),
        cue_timings=[CueTiming(0, 0, 4000), CueTiming(1, 1000, 1500)],
        loudness_report=_report(),
        provenance={'source': 'fixture'},
        risk_metadata={'risk': 'low'},
        warnings=['w1'],
        substitutions=[],
    )
    assert isinstance(res.renditions, tuple)
    assert isinstance(res.cue_timings, tuple)
    assert isinstance(res.warnings, tuple)
    assert isinstance(res.substitutions, tuple)

    assert _err(
        AudioBedResult,
        renditions=_renditions(req),
        cue_timings=(CueTiming(0, 0, 4000),),
        loudness_report=_report(),
        provenance={},
        risk_metadata={},
        warnings=(),
        substitutions=[{'change': 'track'}],
    ) == (WRONG_TYPE, 'substitutions')

    assert _err(
        AudioBedResult,
        renditions=_renditions(req),
        cue_timings=(CueTiming(0, 0, 4000),),
        loudness_report=_report(),
        provenance={},
        risk_metadata={},
        warnings=[5],
        substitutions=(),
    ) == (WRONG_TYPE, 'warnings')


def test_module_has_no_hardcoded_loudness() -> None:
    content = MODULE_PATH.read_text(encoding='utf-8')
    assert not re.search(r'-\s*1[46]\b', content), 'Found hardcoded -14 or -16 LUFS'

    tree = ast.parse(content, filename=str(MODULE_PATH))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            assert node.value == 0, f'Found disallowed numeric constant {node.value!r} in domain module'
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_pkg = alias.name.split('.')[0]
                assert root_pkg in {'__future__', 'copy', 'math', 'dataclasses', 'types'}, f'Disallowed import {alias.name}'
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ''
            assert mod in {'__future__', 'copy', 'math', 'collections.abc', 'dataclasses', 'types'}, f'Disallowed import from {mod}'
