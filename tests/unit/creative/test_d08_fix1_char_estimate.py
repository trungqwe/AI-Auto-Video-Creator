"""D-08-FIX1: ước lượng thời lượng kịch bản theo số ký tự không kể dấu cách (OI-CP7-11-Q3)."""
from __future__ import annotations

import importlib.util
import pathlib
from types import SimpleNamespace

import pytest

from controlplane.api.wiring.creative import creative_settings
from creative.domain.script import (
    DURATION_OUT_OF_RANGE,
    FIRST_READ_FAST_RATIO,
    FIRST_READ_SLOW_RATIO,
    SCRIPT_CHARS_PER_SECOND,
    LanguageVoicePolicy,
    ScriptRejected,
    TargetRange,
    build_script_version,
    count_chars,
)

_BASE_PATH = pathlib.Path(__file__).with_name('test_d08_script_version.py')
_SPEC = importlib.util.spec_from_file_location('d08_script_version_base', _BASE_PATH)
base = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(base)

CPS = SCRIPT_CHARS_PER_SECOND
RANGE = TargetRange(min_seconds=61, max_seconds=70)
CHARS_POLICY = LanguageVoicePolicy(language='en', speech_rate=2.0, chars_per_second=CPS)


def _raw_chars(total_chars: int) -> dict[str, object]:
    raw = base._raw()
    sizes = [total_chars // 5] * 4
    sizes.append(total_chars - sum(sizes))
    for seg, size in zip(raw['segments'], sizes):
        seg['text'] = 'x' * size
    return raw


def _build_chars(total_chars: int, policy: LanguageVoicePolicy = CHARS_POLICY, target_range: TargetRange = RANGE):
    return build_script_version(
        _raw_chars(total_chars),
        resolver=base._resolver(),
        language_policy=policy,
        target_range=target_range,
    )


def _rejection(total_chars: int) -> tuple[str, str, str]:
    with pytest.raises(ScriptRejected) as excinfo:
        _build_chars(total_chars)
    err = excinfo.value
    return (err.code, err.reason, err.field)


def test_constants_follow_the_measured_reads() -> None:
    assert SCRIPT_CHARS_PER_SECOND == 13.81
    assert FIRST_READ_SLOW_RATIO == 1.1087
    assert FIRST_READ_FAST_RATIO == 0.9226
    assert round(RANGE.min_seconds / FIRST_READ_SLOW_RATIO, 2) == 55.02
    assert round(RANGE.max_seconds / FIRST_READ_FAST_RATIO, 2) == 75.87
    assert count_chars('  ab \t c\n d  ') == 4
    assert count_chars('Xin chào  bạn') == 10


@pytest.mark.parametrize('seconds', [55.1, 61.0, 65.5, 70.0, 75.8])
def test_first_read_the_reread_can_pull_into_range_is_admitted(seconds: float) -> None:
    chars = round(seconds * CPS)
    version = _build_chars(chars)
    assert version.estimated_duration_seconds == pytest.approx(chars / CPS)
    assert version.estimated_duration_seconds == pytest.approx(seconds, abs=0.05)
    assert 55.02 <= version.estimated_duration_seconds <= 75.87
    assert sum(s.estimated_seconds for s in version.segments) == pytest.approx(version.estimated_duration_seconds)
    assert version.speech_rate == 2.0


@pytest.mark.parametrize(
    ('chars', 'reason'),
    [
        (739, 'below_target_range'),
        (714, 'below_target_range'),
        (759, 'below_target_range'),
        (1048, 'above_target_range'),
    ],
)
def test_first_read_out_of_reach_is_rejected(chars: int, reason: str) -> None:
    assert _rejection(chars) == (DURATION_OUT_OF_RANGE, reason, 'segments')


@pytest.mark.parametrize('chars', [760, 1047])
def test_admission_edges_are_55_02_and_75_87_seconds(chars: int) -> None:
    assert 55.02 <= _build_chars(chars).estimated_duration_seconds <= 75.87


def test_without_chars_per_second_the_word_rule_is_unchanged() -> None:
    policy = LanguageVoicePolicy(language='en', speech_rate=2.0)
    assert policy.chars_per_second is None
    for words in (122, 140):
        version = build_script_version(
            base._raw(words), resolver=base._resolver(), language_policy=policy, target_range=RANGE
        )
        assert version.estimated_duration_seconds == pytest.approx(words / 2.0)
        assert sum(s.estimated_seconds for s in version.segments) == pytest.approx(words / 2.0)
    for words, reason in ((110, 'below_target_range'), (121, 'below_target_range'), (141, 'above_target_range')):
        with pytest.raises(ScriptRejected) as excinfo:
            build_script_version(
                base._raw(words), resolver=base._resolver(), language_policy=policy, target_range=RANGE
            )
        err = excinfo.value
        assert (err.code, err.reason, err.field) == (DURATION_OUT_OF_RANGE, reason, 'segments')


@pytest.mark.parametrize('bad', [0, -1, True, float('nan'), float('inf'), '13.81'])
def test_chars_per_second_must_be_positive_finite(bad: object) -> None:
    with pytest.raises(ValueError):
        LanguageVoicePolicy(language='en', speech_rate=2.0, chars_per_second=bad)  # type: ignore[arg-type]


def test_production_settings_estimate_by_characters() -> None:
    profile = SimpleNamespace(
        revision=1,
        parameters={
            'voice.duration_range_ms': {'min': 61000, 'max': 70000},
            'voice.speech_rate_wpm': 136,
            'qc.required_language': 'en',
        },
    )
    settings = creative_settings(profile)
    policy = settings.language_policy
    assert policy.chars_per_second == SCRIPT_CHARS_PER_SECOND
    assert policy.speech_rate == pytest.approx(136 / 60.0)
    assert (settings.target_range.min_seconds, settings.target_range.max_seconds) == (61.0, 70.0)
    admitted = _build_chars(842, policy=policy, target_range=settings.target_range)
    assert admitted.estimated_duration_seconds == pytest.approx(842 / SCRIPT_CHARS_PER_SECOND)
    with pytest.raises(ScriptRejected) as excinfo:
        _build_chars(739, policy=policy, target_range=settings.target_range)
    err = excinfo.value
    assert (err.code, err.reason, err.field) == (DURATION_OUT_OF_RANGE, 'below_target_range', 'segments')
