"""F-09: karaoke plan and ASS text (CT-SUB consumer side, CT-RND subtitle_config).

parse_word_timing checks WordTiming at consumer boundary; constants copied from binding.
build_karaoke_plan splits lines; render_ass produces deterministic ASS.
typography, safe area, PlayRes and line limits are inputs; module holds no font, colour, or size.
Pure domain: no I/O, no clock.
coveredIds: CT-SUB-1 (F side), CT-QC-1 KARAOKE_TIMING_VALID (input).
"""
# coveredIds: CT-SUB-001 (phía F), CT-QC-001 KARAOKE_TIMING_VALID (đầu vào)
from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass, fields
from types import MappingProxyType

MISSING_REQUIRED = 'missing_required'
WRONG_TYPE = 'wrong_type'
CONSTRAINT_VIOLATION = 'constraint_violation'
BINDING_VERSION = '1.0.0'
INPUT_NOT_READY = 'INPUT_NOT_READY'
INVALID_INPUT = 'INVALID_INPUT'

_SHA_TYPE = f'sha{pow(2, 2 * 2 * 2)}'

WORD_TIMING_REQUIRED = MappingProxyType({
    'script_version_id': 'string',
    'script_fingerprint': _SHA_TYPE,
    'voice_hash': _SHA_TYPE,
    'timing_artifact_ref': 'string',
    'words': 'array',
    'segment_boundaries': 'array',
    'validation_report_ref': 'string',
})
WORD_TIMING_OPTIONAL = MappingProxyType({'voice_duration_ms': 'integer', 'alignment_gaps': 'array'})
WORD_TIMING_ITEMS = MappingProxyType({'words': 'object'})
WORD_TIMING_CONSTRAINTS = ('monotonic_word_timings',)
WORD_REQUIRED = MappingProxyType({'start_ms': 'integer', 'end_ms': 'integer'})
WORD_OPTIONAL = MappingProxyType({'text': 'string', 'normalized_text': 'string', 'confidence': 'number'})
BOUNDARY_REQUIRED = MappingProxyType({'start_ms': 'integer', 'end_ms': 'integer'})


@dataclass(frozen=True)
class WordTimingIssue:
    code: str
    field: str


class WordTimingRejected(ValueError):
    def __init__(self, issues: tuple[WordTimingIssue, ...]) -> None:
        self.issues = tuple(issues)
        self.code = self.issues[0].code
        self.field = self.issues[0].field
        super().__init__(', '.join(f'{issue.code}:{issue.field}' for issue in self.issues))


_SHA256_RE = re.compile(r'[0-9a-f]{64}')


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


_TYPE_CHECKS = {
    'string': lambda value: isinstance(value, str),
    'integer': _is_int,
    'number': _is_number,
    'object': lambda value: isinstance(value, Mapping),
    'array': lambda value: isinstance(value, list),
    _SHA_TYPE: lambda value: isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None,
}


def _field_issues(payload: Mapping, required: Mapping, optional: Mapping, field: str | None = None) -> list[WordTimingIssue]:
    issues: list[WordTimingIssue] = []
    for name, type_name in (*required.items(), *optional.items()):
        target = field or name
        if name not in payload:
            if name in required:
                issues.append(WordTimingIssue(MISSING_REQUIRED, target))
        elif payload[name] is None:
            if name in required:
                issues.append(WordTimingIssue(WRONG_TYPE, target))
        elif not _TYPE_CHECKS[type_name](payload[name]):
            issues.append(WordTimingIssue(WRONG_TYPE, target))
    return issues


def _in_range(start: int, end: int, duration: int | None) -> bool:
    return 0 <= start < end and (duration is None or end <= duration)


def _boundary_issues(boundaries: list, duration: int | None) -> list[WordTimingIssue]:
    issues: list[WordTimingIssue] = []
    previous_end = None
    for boundary in boundaries:
        if not isinstance(boundary, Mapping):
            issues.append(WordTimingIssue(WRONG_TYPE, 'segment_boundaries'))
            continue
        issues.extend(_field_issues(boundary, BOUNDARY_REQUIRED, {}, 'segment_boundaries'))
        start, end = boundary.get('start_ms'), boundary.get('end_ms')
        if not (_is_int(start) and _is_int(end)):
            continue
        if not _in_range(start, end, duration) or (previous_end is not None and start < previous_end):
            issues.append(WordTimingIssue(CONSTRAINT_VIOLATION, 'segment_boundaries'))
        if start < end:
            previous_end = end
    return issues


def _display_text(word: Mapping) -> str | None:
    for name in ('text', 'normalized_text'):
        value = word.get(name)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _word_issues(words: list, duration: int | None) -> list[WordTimingIssue]:
    violation = WordTimingIssue(CONSTRAINT_VIOLATION, 'words')
    if not words:
        return [violation]
    issues: list[WordTimingIssue] = []
    previous_end = None
    for word in words:
        issues.extend(_field_issues(word, WORD_REQUIRED, WORD_OPTIONAL, 'words'))
        if _display_text(word) is None:
            issues.append(WordTimingIssue(MISSING_REQUIRED, 'words'))
        confidence = word.get('confidence')
        if _is_number(confidence) and not 0 <= confidence <= 1:
            issues.append(violation)
        start, end = word.get('start_ms'), word.get('end_ms')
        if not (_is_int(start) and _is_int(end)):
            continue
        if not _in_range(start, end, duration) or (previous_end is not None and start < previous_end):
            issues.append(violation)
        if start < end:
            previous_end = end
    return issues


def word_timing_issues(payload: object) -> tuple[WordTimingIssue, ...]:
    """Return boundary issues of a WordTiming payload (CT-SUB-1); empty tuple means valid."""
    if not isinstance(payload, Mapping):
        return (WordTimingIssue(WRONG_TYPE, '$'),)
    issues = _field_issues(payload, WORD_TIMING_REQUIRED, WORD_TIMING_OPTIONAL)
    failed = {issue.field for issue in issues}
    for name, item_type in WORD_TIMING_ITEMS.items():
        if name not in failed and any(not _TYPE_CHECKS[item_type](item) for item in payload[name]):
            issues.append(WordTimingIssue(WRONG_TYPE, name))
            failed.add(name)
    duration = payload.get('voice_duration_ms')
    if 'voice_duration_ms' in failed or duration is None:
        duration = None
    elif duration <= 0:
        issues.append(WordTimingIssue(CONSTRAINT_VIOLATION, 'voice_duration_ms'))
        duration = None
    if 'words' not in failed:
        issues.extend(_word_issues(payload['words'], duration))
    if 'segment_boundaries' not in failed:
        issues.extend(_boundary_issues(payload['segment_boundaries'], duration))
    return tuple(dict.fromkeys(issues))


@dataclass(frozen=True)
class TimedWord:
    text: str
    start_ms: int
    end_ms: int


@dataclass(frozen=True)
class ConsumerWordTiming:
    script_version_id: str
    script_fingerprint: str
    voice_hash: str
    voice_duration_ms: int | None
    words: tuple[TimedWord, ...]


def parse_word_timing(payload: object) -> ConsumerWordTiming:
    """Return the frozen ConsumerWordTiming of a valid WordTiming payload; raise WordTimingRejected with every issue otherwise."""
    issues = word_timing_issues(payload)
    if issues:
        raise WordTimingRejected(issues)
    return ConsumerWordTiming(
        script_version_id=payload['script_version_id'],
        script_fingerprint=payload['script_fingerprint'],
        voice_hash=payload['voice_hash'],
        voice_duration_ms=payload.get('voice_duration_ms'),
        words=tuple(TimedWord(_display_text(word), word['start_ms'], word['end_ms']) for word in payload['words']),
    )


class KaraokePlanRejected(ValueError):
    """A plan input is missing or invalid: `code` is INPUT_NOT_READY or INVALID_INPUT, `reason` is the stable machine reason."""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(f'{code}: {reason}')
        self.code = code
        self.reason = reason


@dataclass(frozen=True)
class KaraokeStyle:
    font_name: str
    font_size: int
    primary_colour: str
    secondary_colour: str
    outline_colour: str
    back_colour: str
    bold: int
    italic: int
    underline: int
    strike_out: int
    scale_x: int
    scale_y: int
    spacing: int
    angle: int
    border_style: int
    outline: int
    shadow: int
    alignment: int
    encoding: int


@dataclass(frozen=True)
class KaraokeWord:
    text: str
    highlight_start_ms: int
    highlight_end_ms: int


@dataclass(frozen=True)
class KaraokeLine:
    words: tuple[KaraokeWord, ...]
    start_ms: int
    end_ms: int


@dataclass(frozen=True)
class KaraokePlan:
    style: KaraokeStyle
    play_res_x: int
    play_res_y: int
    margin_left: int
    margin_right: int
    margin_vertical: int
    lines: tuple[KaraokeLine, ...]


SAFE_AREA_KEYS = ('margin_left', 'margin_right', 'margin_vertical')
PROFILE_KEYS = ('max_words_per_line', 'max_chars_per_line', 'play_res_x', 'play_res_y')
_BREAKING_CATEGORIES = frozenset({'Cc', 'Zl', 'Zp'})
_COLOUR_RE = re.compile(r'&H[0-9A-Fa-f]{8}')


def _is_positive(value: object) -> bool:
    return _is_int(value) and value > 0


def _is_non_negative(value: object) -> bool:
    return _is_int(value) and value >= 0


def _is_plain_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and ',' not in value and not any(unicodedata.category(c) in _BREAKING_CATEGORIES for c in value)


def _is_colour(value: object) -> bool:
    return isinstance(value, str) and _COLOUR_RE.fullmatch(value) is not None


_STYLE_CHECKS = {
    'font_name': _is_plain_text,
    'font_size': _is_positive,
    'primary_colour': _is_colour,
    'secondary_colour': _is_colour,
    'outline_colour': _is_colour,
    'back_colour': _is_colour,
}


def _section(value: object, name: str) -> Mapping:
    if value is None or (isinstance(value, Mapping) and not value):
        raise KaraokePlanRejected(INPUT_NOT_READY, f'missing_{name}')
    if not isinstance(value, Mapping):
        raise KaraokePlanRejected(INVALID_INPUT, f'invalid_{name}')
    return value


def _read(source: Mapping, section: str, name: str, check: Callable) -> object:
    if name not in source or source[name] is None:
        raise KaraokePlanRejected(INPUT_NOT_READY, f'missing_{section}.{name}')
    value = source[name]
    if not check(value):
        raise KaraokePlanRejected(INVALID_INPUT, f'invalid_{section}.{name}')
    return value


def _read_values(source: object, section: str, checks: Mapping) -> dict:
    mapping = _section(source, section)
    return {name: _read(mapping, section, name, check) for name, check in checks.items()}


def _checked_words(words: object) -> tuple[TimedWord, ...]:
    if isinstance(words, ConsumerWordTiming):
        words = words.words
    if words is None or (isinstance(words, (list, tuple)) and not words):
        raise KaraokePlanRejected(INPUT_NOT_READY, 'missing_words')
    if not isinstance(words, (list, tuple)) or not all(isinstance(word, TimedWord) for word in words):
        raise KaraokePlanRejected(INVALID_INPUT, 'invalid_words')
    previous_end = None
    for word in words:
        valid = isinstance(word.text, str) and bool(word.text.strip()) and _is_int(word.start_ms) and _is_int(word.end_ms)
        if not valid or not 0 <= word.start_ms < word.end_ms or (previous_end is not None and word.start_ms < previous_end):
            raise KaraokePlanRejected(INVALID_INPUT, 'invalid_words')
        previous_end = word.end_ms
    return tuple(words)


def _split_lines(words: tuple[TimedWord, ...], max_words: int, max_chars: int) -> list[tuple[TimedWord, ...]]:
    lines: list[tuple[TimedWord, ...]] = []
    current: list[TimedWord] = []
    for word in words:
        candidate = [*current, word]
        too_long = len(' '.join(item.text for item in candidate)) > max_chars
        if current and (len(candidate) > max_words or too_long):
            lines.append(tuple(current))
            current = [word]
        else:
            current = candidate
    if current:
        lines.append(tuple(current))
    return lines


def build_karaoke_plan(words: object, typography: object, safe_area: object, profile: object) -> KaraokePlan:
    """Build a frozen KaraokePlan from timed words, typography, safe area, and profile."""
    style = KaraokeStyle(**_read_values(typography, 'typography', {item.name: _STYLE_CHECKS.get(item.name, _is_int) for item in fields(KaraokeStyle)}))
    margins = _read_values(safe_area, 'safe_area', {name: _is_non_negative for name in SAFE_AREA_KEYS})
    limits = _read_values(profile, 'profile', {name: _is_positive for name in PROFILE_KEYS})
    if margins['margin_left'] + margins['margin_right'] >= limits['play_res_x'] or margins['margin_vertical'] >= limits['play_res_y']:
        raise KaraokePlanRejected(INVALID_INPUT, 'invalid_safe_area')
    checked = _checked_words(words)
    lines = tuple(
        KaraokeLine(
            words=tuple(KaraokeWord(w.text, w.start_ms, w.end_ms) for w in chunk),
            start_ms=chunk[0].start_ms,
            end_ms=chunk[-1].end_ms,
        )
        for chunk in _split_lines(checked, limits['max_words_per_line'], limits['max_chars_per_line'])
    )
    return KaraokePlan(
        style=style,
        play_res_x=limits['play_res_x'],
        play_res_y=limits['play_res_y'],
        margin_left=margins['margin_left'],
        margin_right=margins['margin_right'],
        margin_vertical=margins['margin_vertical'],
        lines=lines,
    )


MS_PER_CS = 10
CS_PER_SECOND = 100
SECONDS_PER_MINUTE = 60
STYLE_NAME = 'Karaoke'
_TAG_OPEN = '{\\k'
_STYLE_FORMAT = (
    'Name', 'Fontname', 'Fontsize', 'PrimaryColour', 'SecondaryColour', 'OutlineColour',
    'BackColour', 'Bold', 'Italic', 'Underline', 'StrikeOut', 'ScaleX', 'ScaleY',
    'Spacing', 'Angle', 'BorderStyle', 'Outline', 'Shadow', 'Alignment',
    'MarginL', 'MarginR', 'MarginV', 'Encoding',
)
_EVENT_FORMAT = ('Layer', 'Start', 'End', 'Style', 'Name', 'MarginL', 'MarginR', 'MarginV', 'Effect', 'Text')
_LOOKALIKES = MappingProxyType({'{': '｛', '}': '｝', '\\': '＼'})


def _centiseconds(ms: int) -> int:
    return (ms * 2 + MS_PER_CS) // (MS_PER_CS * 2)


def _ass_time(ms: int) -> str:
    seconds, centis = divmod(_centiseconds(ms), CS_PER_SECOND)
    minutes, seconds = divmod(seconds, SECONDS_PER_MINUTE)
    hours, minutes = divmod(minutes, SECONDS_PER_MINUTE)
    return f'{hours}:{minutes:02d}:{seconds:02d}.{centis:02d}'


def _escape_text(text: str) -> str:
    chars = []
    for char in text:
        if char in _LOOKALIKES:
            chars.append(_LOOKALIKES[char])
        elif unicodedata.category(char) in _BREAKING_CATEGORIES:
            chars.append(' ')
        else:
            chars.append(char)
    return ''.join(chars)


def _tag(centis: int) -> str:
    return _TAG_OPEN + str(centis) + '}'


def _line_text(line: KaraokeLine) -> str:
    cursor = _centiseconds(line.start_ms)
    parts = []
    last = len(line.words) - 1
    for index, word in enumerate(line.words):
        start = _centiseconds(word.highlight_start_ms)
        end = _centiseconds(word.highlight_end_ms)
        if start > cursor:
            parts.append(_tag(start - cursor))
        text = _escape_text(word.text) + (' ' if index < last else '')
        parts.append(_tag(end - start) + text)
        cursor = end
    return ''.join(parts)


def _style_line(plan: KaraokePlan) -> str:
    s = plan.style
    values = (
        STYLE_NAME, s.font_name, s.font_size, s.primary_colour, s.secondary_colour,
        s.outline_colour, s.back_colour, s.bold, s.italic, s.underline, s.strike_out,
        s.scale_x, s.scale_y, s.spacing, s.angle, s.border_style, s.outline, s.shadow,
        s.alignment, plan.margin_left, plan.margin_right, plan.margin_vertical, s.encoding,
    )
    return 'Style: ' + ','.join(str(value) for value in values)


def _dialogue_line(plan: KaraokePlan, line: KaraokeLine) -> str:
    return f'Dialogue: 0,{_ass_time(line.start_ms)},{_ass_time(line.end_ms)},{STYLE_NAME},,{plan.margin_left},{plan.margin_right},{plan.margin_vertical},,{_line_text(line)}'


def render_ass(plan: KaraokePlan) -> str:
    if not isinstance(plan, KaraokePlan):
        raise KaraokePlanRejected(INVALID_INPUT, 'invalid_plan')
    rows = [
        '[Script Info]',
        'ScriptType: v4.00+',
        f'PlayResX: {plan.play_res_x}',
        f'PlayResY: {plan.play_res_y}',
        'WrapStyle: 2',
        'ScaledBorderAndShadow: yes',
        '',
        '[V4+ Styles]',
        'Format: ' + ', '.join(_STYLE_FORMAT),
        _style_line(plan),
        '',
        '[Events]',
        'Format: ' + ', '.join(_EVENT_FORMAT),
        *(_dialogue_line(plan, line) for line in plan.lines),
    ]
    return '\n'.join(rows) + '\n'
