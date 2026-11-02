"""E-16-FIX3: a slightly short re-read take gets up to 1.5 s of trailing digital silence (CT-TTS-001).

coveredIds: CT-TTS-001
"""

from __future__ import annotations

import importlib.util
import pathlib
import struct

import pytest
from voice.application import voice_pipeline as vp
from voice.domain.tail_pad import TAIL_PAD_MARGIN_MS, TAIL_PAD_MAX_MS, pad_wav_tail, plan_tail_pad

_SOURCE = pathlib.Path(__file__).with_name('test_e16_voice_timing_pipeline.py')
_spec = importlib.util.spec_from_file_location('e16_voice_timing_pipeline_base', _SOURCE)
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)

Rig, _ScaleEngine, _voice_cmd, _after, _wav, _wav_duration_ms = (
    base.Rig, base._ScaleEngine, base._voice_cmd, base._after, base._wav, base._wav_duration_ms,
)
RANGE, FIT = base.RANGE, base.FIT


def test_plan_tail_pad_only_for_a_short_shortfall():
    assert (TAIL_PAD_MAX_MS, TAIL_PAD_MARGIN_MS) == (1500, 100)
    assert plan_tail_pad(60715, RANGE) == 385
    assert plan_tail_pad(60501, RANGE) == 599
    assert plan_tail_pad(59500, RANGE) == 1500
    assert plan_tail_pad(59600, RANGE) == 1500
    assert plan_tail_pad(61000, RANGE) is None
    assert plan_tail_pad(65000, RANGE) is None
    assert plan_tail_pad(75000, RANGE) is None
    assert plan_tail_pad(59499, RANGE) is None


def test_pad_wav_tail_appends_zero_samples_and_rewrites_sizes():
    wav = _wav(1000)
    padded = pad_wav_tail(wav, 500)
    extra = 2 * (16000 * 500 // 1000)
    assert len(padded) == len(wav) + extra
    assert padded[len(wav):] == bytes(extra)
    assert struct.unpack_from('<I', padded, 4)[0] == len(padded) - 8
    assert struct.unpack_from('<I', padded, 40)[0] == 2 * 16000 + extra
    assert _wav_duration_ms(padded) == 1500
    for bad in (0, -1, TAIL_PAD_MAX_MS + 1):
        with pytest.raises(ValueError):
            pad_wav_tail(wav, bad)
    with pytest.raises(ValueError):
        pad_wav_tail(b'not a wav at all', 100)
    float_fmt = bytearray(wav)
    struct.pack_into('<H', float_fmt, 20, 3)
    with pytest.raises(ValueError):
        pad_wav_tail(bytes(float_fmt), 100)
    with pytest.raises(ValueError):
        pad_wav_tail(wav + b'LIST' + struct.pack('<I', 0), 100)


def test_short_reread_gets_trailing_silence_and_passes():
    engine = _ScaleEngine(55000)
    rig = Rig(engine=engine)
    voice = rig.pipeline.create_voice_track(_voice_cmd(duration=RANGE, speed_fit=FIT)).voice_track
    reread = _after(55000, 0.85)
    assert engine.scales == [1.0, 0.85]
    assert voice.actual_duration_ms == 61100
    assert voice.usage_metrics['tail_pad_ms'] == 1480
    assert voice.usage_metrics['reread_duration_ms'] == reread
    assert voice.usage_metrics['first_take_duration_ms'] == 55000
    assert voice.warnings == ('speed_fit_applied', 'tail_pad_applied')
    invocations = [item.record for item in rig.revs('tts_invocation')]
    assert [r.validation_result for r in invocations] == ['failed', 'passed']
    assert invocations[1].usage_metrics['measured_duration_ms'] == reread


def test_shortfall_over_the_cap_is_still_rejected():
    engine = _ScaleEngine(50000)
    rig = Rig(engine=engine)
    with pytest.raises(vp.VoiceDurationRejected) as info:
        rig.pipeline.create_voice_track(_voice_cmd(duration=RANGE, speed_fit=FIT))
    assert info.value.finding.actual_duration_ms == _after(50000, 0.85)
    assert engine.scales == [1.0, 0.85]
    assert rig.revs('voice') == ()


def test_first_take_and_long_reread_are_never_padded():
    short_no_fit = _ScaleEngine(60000)
    rig = Rig(engine=short_no_fit)
    with pytest.raises(vp.VoiceDurationRejected):
        rig.pipeline.create_voice_track(_voice_cmd(duration=RANGE))
    assert short_no_fit.scales == [1.0]
    long_engine = _ScaleEngine(90000)
    rig = Rig(engine=long_engine)
    with pytest.raises(vp.VoiceDurationRejected) as info:
        rig.pipeline.create_voice_track(_voice_cmd(duration=RANGE, speed_fit=FIT))
    assert info.value.finding.actual_duration_ms == _after(90000, 1.15)
    assert long_engine.scales == [1.0, 1.15]
    in_range = _ScaleEngine(65500)
    voice = Rig(engine=in_range).pipeline.create_voice_track(_voice_cmd(duration=RANGE, speed_fit=FIT)).voice_track
    assert voice.warnings == ()
    assert 'tail_pad_ms' not in voice.usage_metrics
