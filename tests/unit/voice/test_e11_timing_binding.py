"""E-11: TimingBinding, kiểm binding và invalidation downstream (CT-SUB-001 bất biến 2 và 3).

coveredIds: TST-MEDIA-INV-007 (mức domain), CT-SUB-001 bất biến 2 và 3
"""
import ast
import copy
import dataclasses
import json
import pathlib

import pytest

from voice.domain.timing_binding import (
    SCRIPT_CHANGED, TIMING_BINDING_INVALID, VOICE_ARTIFACT_REVISION_CHANGED, VOICE_CHANGED,
    DownstreamChange, InvalidationResult, StaleRecord, TimingBinding, TimingBindingCheck, TimingBindingError,
    check_timing_binding, invalidate_downstream, require_valid_timing,
)
from voice.domain.voice_track import VoiceTrack
from voice.domain.word_timing import validate_word_timing

ROOT = pathlib.Path(__file__).resolve().parents[3]
FIXTURE_PATH = ROOT / 'tests' / 'fixtures' / 'contracts' / 'd-e-f-voice-timing' / 'payloads.json'
MODULE_PATH = ROOT / 'src' / 'voice' / 'domain' / 'timing_binding.py'
OLD_SCRIPT = '0123456789abcdef' * 4
NEW_SCRIPT = 'fedcba9876543210' * 4
OLD_VOICE = 'a' * 64
NEW_VOICE = 'b' * 64


def _fixture(entity: str) -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))['entities'][entity]['valid'][0]


def _timing(script: str = OLD_SCRIPT, voice: str = OLD_VOICE, ref: str = 'timing-1') -> TimingBinding:
    return TimingBinding(script_version_id='script-v1', script_fingerprint=script, voice_hash=voice, timing_artifact_ref=ref)


def _track(script: str = OLD_SCRIPT, voice: str = OLD_VOICE, ref: str = 'voice-1', revision: str = 'tts-v1') -> VoiceTrack:
    payload = copy.deepcopy(_fixture('VoiceTrackResult'))
    payload.update(voice_artifact_ref=ref, script_fingerprint=script, voice_hash=voice, provider_model_voice_revision=revision)
    return VoiceTrack.from_payload(payload)


def test_timing_binding_is_frozen_and_validates_fields() -> None:
    timing = _timing()
    with pytest.raises(dataclasses.FrozenInstanceError):
        timing.voice_hash = NEW_VOICE
    for name, bad in (('script_fingerprint', 'ABC'), ('voice_hash', None), ('script_version_id', 5), ('timing_artifact_ref', None)):
        with pytest.raises(ValueError):
            dataclasses.replace(timing, **{name: bad})


def test_from_word_timing_copies_binding_fields_of_fixture_record() -> None:
    record = validate_word_timing(_fixture('WordTiming'))
    timing = TimingBinding.from_word_timing(record)
    assert timing.script_version_id == record.script_version_id
    assert timing.script_fingerprint == record.script_fingerprint
    assert timing.voice_hash == record.voice_hash
    assert timing.timing_artifact_ref == '00000000-0000-4000-8000-000000000036'


def test_matching_script_and_voice_is_valid() -> None:
    assert check_timing_binding(_timing(), OLD_SCRIPT, OLD_VOICE) == TimingBindingCheck(True, ())
    assert require_valid_timing(_timing(), OLD_SCRIPT, OLD_VOICE) == _timing()


@pytest.mark.parametrize(('script', 'voice', 'reasons'), [
    (NEW_SCRIPT, OLD_VOICE, (SCRIPT_CHANGED,)),
    (OLD_SCRIPT, NEW_VOICE, (VOICE_CHANGED,)),
    (NEW_SCRIPT, NEW_VOICE, (SCRIPT_CHANGED, VOICE_CHANGED)),
])
def test_changed_script_or_voice_makes_old_timing_invalid(script: str, voice: str, reasons: tuple) -> None:
    timing = _timing()
    assert check_timing_binding(timing, script, voice) == TimingBindingCheck(False, reasons)
    with pytest.raises(TimingBindingError) as caught:
        require_valid_timing(timing, script, voice)
    assert caught.value.reasons == reasons
    assert caught.value.code == TIMING_BINDING_INVALID
    assert caught.value.timing_artifact_ref == 'timing-1'
    assert timing == _timing()


def test_check_result_is_frozen_and_bad_inputs_are_never_valid() -> None:
    check = check_timing_binding(_timing(), OLD_SCRIPT, OLD_VOICE)
    with pytest.raises(dataclasses.FrozenInstanceError):
        check.valid = False
    for script, voice in ((None, OLD_VOICE), (OLD_SCRIPT, None), ('ABC', OLD_VOICE), (OLD_SCRIPT, 5)):
        with pytest.raises(ValueError):
            check_timing_binding(_timing(), script, voice)
        with pytest.raises(ValueError):
            require_valid_timing(_timing(), script, voice)
    with pytest.raises(TypeError):
        check_timing_binding({'script_fingerprint': OLD_SCRIPT}, OLD_SCRIPT, OLD_VOICE)


def test_script_change_makes_voice_track_and_timing_stale() -> None:
    tracks = (_track(ref='voice-1'), _track(script=NEW_SCRIPT, ref='voice-2'))
    timings = (_timing(ref='timing-1'), _timing(script=NEW_SCRIPT, ref='timing-2'))
    change = DownstreamChange(kind=SCRIPT_CHANGED, old_script_fingerprint=OLD_SCRIPT)
    result = invalidate_downstream(change, tracks, timings)
    assert result.change == change
    assert result.stale_voice_tracks == (StaleRecord('voice-1', SCRIPT_CHANGED),)
    assert result.stale_timings == (StaleRecord('timing-1', SCRIPT_CHANGED),)


def test_voice_change_makes_only_timing_stale() -> None:
    timings = (_timing(ref='timing-1'), _timing(voice=NEW_VOICE, ref='timing-2'))
    change = DownstreamChange(kind=VOICE_CHANGED, old_voice_hash=OLD_VOICE)
    result = invalidate_downstream(change, (_track(),), timings)
    assert result.stale_voice_tracks == ()
    assert result.stale_timings == (StaleRecord('timing-1', VOICE_CHANGED),)


def test_voice_artifact_revision_change_makes_only_timing_of_that_artifact_stale() -> None:
    tracks = (_track(ref='voice-1', voice=OLD_VOICE), _track(ref='voice-2', voice=NEW_VOICE))
    timings = (_timing(voice=OLD_VOICE, ref='timing-1'), _timing(voice=NEW_VOICE, ref='timing-2'))
    change = DownstreamChange(kind=VOICE_ARTIFACT_REVISION_CHANGED, voice_artifact_ref='voice-1', old_voice_revision='tts-v1')
    result = invalidate_downstream(change, tracks, timings)
    assert result.stale_voice_tracks == ()
    assert result.stale_timings == (StaleRecord('timing-1', VOICE_ARTIFACT_REVISION_CHANGED),)
    other = DownstreamChange(kind=VOICE_ARTIFACT_REVISION_CHANGED, voice_artifact_ref='voice-1', old_voice_revision='tts-v0')
    assert invalidate_downstream(other, tracks, timings) == InvalidationResult(other, (), ())


def test_unaffected_records_give_empty_result() -> None:
    change = DownstreamChange(kind=SCRIPT_CHANGED, old_script_fingerprint=NEW_SCRIPT)
    assert invalidate_downstream(change, (_track(),), (_timing(),)) == InvalidationResult(change, (), ())


def test_invalidation_does_not_mutate_or_delete_old_records() -> None:
    tracks, timings = [_track()], [_timing()]
    change = DownstreamChange(kind=SCRIPT_CHANGED, old_script_fingerprint=OLD_SCRIPT)
    result = invalidate_downstream(change, tracks, timings)
    assert tracks == [_track()] and timings == [_timing()]
    assert len(result.stale_voice_tracks) == 1 and len(result.stale_timings) == 1
    assert all(isinstance(item, StaleRecord) for item in (*result.stale_voice_tracks, *result.stale_timings))
    assert isinstance(result.stale_voice_tracks, tuple) and isinstance(result.stale_timings, tuple)
    for frozen in (result, result.stale_timings[0], change):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(frozen, 'change' if frozen is result else 'kind' if frozen is change else 'ref', None)


def test_replacement_after_invalidation_is_a_new_record() -> None:
    old_timing, old_track = _timing(ref='timing-1'), _track(ref='voice-1')
    change = DownstreamChange(kind=SCRIPT_CHANGED, old_script_fingerprint=OLD_SCRIPT)
    assert invalidate_downstream(change, [old_track], [old_timing]).stale_timings
    new_timing = _timing(script=NEW_SCRIPT, ref='timing-2')
    new_track = _track(script=NEW_SCRIPT, ref='voice-2')
    assert new_timing is not old_timing and new_track is not old_track
    assert (old_timing.script_fingerprint, old_timing.timing_artifact_ref) == (OLD_SCRIPT, 'timing-1')
    assert not check_timing_binding(old_timing, NEW_SCRIPT, OLD_VOICE).valid
    assert check_timing_binding(new_timing, NEW_SCRIPT, OLD_VOICE).valid
    assert invalidate_downstream(change, [new_track], [new_timing]) == InvalidationResult(change, (), ())


@pytest.mark.parametrize('kwargs', [
    {'kind': 'other'},
    {'kind': SCRIPT_CHANGED},
    {'kind': SCRIPT_CHANGED, 'old_script_fingerprint': 'ABC'},
    {'kind': SCRIPT_CHANGED, 'old_script_fingerprint': OLD_SCRIPT, 'old_voice_hash': OLD_VOICE},
    {'kind': VOICE_CHANGED, 'old_voice_hash': None},
    {'kind': VOICE_ARTIFACT_REVISION_CHANGED, 'voice_artifact_ref': 'voice-1'},
])
def test_downstream_change_rejects_incomplete_or_mixed_input(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        DownstreamChange(**kwargs)


def test_invalidate_downstream_rejects_wrong_types() -> None:
    change = DownstreamChange(kind=VOICE_CHANGED, old_voice_hash=OLD_VOICE)
    with pytest.raises(TypeError):
        invalidate_downstream({'kind': VOICE_CHANGED}, [], [])
    with pytest.raises(TypeError):
        invalidate_downstream(change, [{'voice_artifact_ref': 'voice-1'}], [])
    with pytest.raises(TypeError):
        invalidate_downstream(change, [], [{'timing_artifact_ref': 'timing-1'}])


def test_module_imports_only_allowed_modules() -> None:
    allowed = {'__future__', 'collections.abc', 'dataclasses', 'types', 'voice.domain.voice_track', 'voice.domain.word_timing'}
    imported = set()
    for node in ast.walk(ast.parse(MODULE_PATH.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or '')
    assert imported <= allowed
