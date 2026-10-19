"""F-09: kế hoạch karaoke và văn bản ASS (CT-SUB-001 phía consumer).

coveredIds: CT-SUB-001 (phía F), CT-QC-001 KARAOKE_TIMING_VALID (đầu vào)
"""
import ast
import copy
import dataclasses
import json
import pathlib
import re

import pytest

from render.domain.karaoke_plan import (
    BINDING_VERSION, CONSTRAINT_VIOLATION, INPUT_NOT_READY, INVALID_INPUT, MISSING_REQUIRED, WORD_OPTIONAL,
    WORD_REQUIRED, WORD_TIMING_CONSTRAINTS, WORD_TIMING_ITEMS, WORD_TIMING_OPTIONAL, WORD_TIMING_REQUIRED, WRONG_TYPE,
    ConsumerWordTiming, KaraokePlan, KaraokePlanRejected, TimedWord, WordTimingRejected, build_karaoke_plan,
    parse_word_timing, render_ass, word_timing_issues,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
BINDING_PATH = ROOT / 'docs' / 'parallel-delivery' / 'bindings' / 'd-e-f-voice-timing.json'
FIXTURE_PATH = ROOT / 'tests' / 'fixtures' / 'contracts' / 'd-e-f-voice-timing' / 'payloads.json'
MODULE_PATH = ROOT / 'src' / 'render' / 'domain' / 'karaoke_plan.py'
ENTITY = 'WordTiming'
DELETE = object()
BS = chr(92)
NL = chr(10)
# Giá trị test-only (GIẢ ĐỊNH); mã nguồn không chứa font, màu hay kích thước.
TYPOGRAPHY = {
    'font_name': 'FixtureFont', 'font_size': 71, 'primary_colour': '&H0000FFFF', 'secondary_colour': '&H00FFFFFF',
    'outline_colour': '&H00000000', 'back_colour': '&H80000000', 'bold': -1, 'italic': 0, 'underline': 0,
    'strike_out': 0, 'scale_x': 100, 'scale_y': 100, 'spacing': 2, 'angle': 0, 'border_style': 1, 'outline': 3,
    'shadow': 1, 'alignment': 2, 'encoding': 1,
}
SAFE_AREA = {'margin_left': 48, 'margin_right': 52, 'margin_vertical': 160}
PROFILE = {'max_words_per_line': 3, 'max_chars_per_line': 20, 'play_res_x': 360, 'play_res_y': 640}
SECTIONS = {'typography': TYPOGRAPHY, 'safe_area': SAFE_AREA, 'profile': PROFILE}


def _binding_entity() -> dict:
    entities = json.loads(BINDING_PATH.read_text(encoding='utf-8'))['entities']
    return next(item for item in entities if item['name'] == ENTITY)


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))['entities'][ENTITY]


def _valid() -> dict:
    return copy.deepcopy(_fixture()['valid'][0])


def _issues(payload: object) -> list:
    return [(issue.code, issue.field) for issue in word_timing_issues(payload)]


def _word(start: object, end: object, **extra: object) -> dict:
    return {'start_ms': start, 'end_ms': end, 'text': 'w', 'normalized_text': 'w', **extra}


def _payload(**changes: object) -> dict:
    payload = _valid()
    for name, value in changes.items():
        if value is DELETE:
            payload.pop(name, None)
        else:
            payload[name] = value
    return payload


def _tw(index: int) -> TimedWord:
    return TimedWord(f'w{index}', index * 100, index * 100 + 100)


def _words(count: int) -> tuple:
    return tuple(_tw(index) for index in range(count))


def _inputs(**changes: object) -> dict:
    values = {'words': _words(2), 'typography': dict(TYPOGRAPHY), 'safe_area': dict(SAFE_AREA), 'profile': dict(PROFILE)}
    values.update(changes)
    return values


def _build(**changes: object) -> KaraokePlan:
    return build_karaoke_plan(**_inputs(**changes))


def _with(section: str, **changes: object) -> dict:
    values = dict(_inputs()[section])
    values.update(changes)
    return values


def _without(section: str, key: str) -> dict:
    values = dict(_inputs()[section])
    del values[key]
    return values


INVALID = _fixture()['invalid']


def test_constants_match_binding() -> None:
    fields = _binding_entity()['fields']
    required = {f['name']: f['type'] for f in fields if f['required']}
    optional = {f['name']: f['type'] for f in fields if not f['required']}
    items = {f['name']: f['items'] for f in fields if 'items' in f}
    assert (dict(WORD_TIMING_REQUIRED), dict(WORD_TIMING_OPTIONAL), dict(WORD_TIMING_ITEMS)) == (required, optional, items)
    assert BINDING_VERSION == json.loads(BINDING_PATH.read_text(encoding='utf-8'))['binding_version']
    assert list(WORD_TIMING_CONSTRAINTS) == _binding_entity()['constraints']
    assert dict(WORD_REQUIRED) == {'start_ms': 'integer', 'end_ms': 'integer'}
    assert WORD_OPTIONAL['confidence'] == 'number'
    assert set(WORD_REQUIRED) | set(WORD_OPTIONAL) == set(_valid()['words'][0])


def test_fixture_cases_and_codes_are_pinned() -> None:
    assert (MISSING_REQUIRED, WRONG_TYPE, CONSTRAINT_VIOLATION, INPUT_NOT_READY) == (
        'missing_required', 'wrong_type', 'constraint_violation', 'INPUT_NOT_READY')
    by_case = {c['case']: (c['expected_error']['code'], c['expected_error']['field']) for c in INVALID}
    assert by_case['words_out_of_order'] == ('constraint_violation', 'words')
    assert by_case['word_beyond_voice_duration'] == ('constraint_violation', 'words')
    assert by_case['missing_voice_hash'] == ('missing_required', 'voice_hash')
    assert _fixture()['valid']


def test_fixture_valid_payload_parses() -> None:
    payload = _valid()
    parsed = parse_word_timing(payload)
    assert isinstance(parsed, ConsumerWordTiming)
    assert (parsed.script_version_id, parsed.script_fingerprint, parsed.voice_hash) == (
        payload['script_version_id'], payload['script_fingerprint'], payload['voice_hash'])
    assert parsed.voice_duration_ms == 65000
    assert parsed.words == (TimedWord('Breaking', 0, 420), TimedWord('news', 420, 900))


@pytest.mark.parametrize('case', INVALID, ids=[case['case'] for case in INVALID])
def test_fixture_invalid_payload_reports_expected_error(case: dict) -> None:
    expected = (case['expected_error']['code'], case['expected_error']['field'])
    assert _issues(case['payload']) == [expected]
    with pytest.raises(WordTimingRejected) as caught:
        parse_word_timing(case['payload'])
    assert (caught.value.code, caught.value.field) == expected


@pytest.mark.parametrize('payload', [None, [], 'text', 5, ()])
def test_non_object_payload_is_wrong_type(payload: object) -> None:
    assert _issues(payload) == [(WRONG_TYPE, '$')]
    with pytest.raises(WordTimingRejected):
        parse_word_timing(payload)


@pytest.mark.parametrize('name', sorted(WORD_TIMING_REQUIRED))
def test_missing_required_field_is_reported(name: str) -> None:
    assert _issues(_payload(**{name: DELETE})) == [(MISSING_REQUIRED, name)]


def test_unknown_fields_are_ignored() -> None:
    payload = _payload(extra_top='x', binding_version='9.9.9')
    payload['words'][0]['extra_word'] = {'any': 1}
    assert _issues(payload) == []
    assert isinstance(parse_word_timing(payload), ConsumerWordTiming)


def test_all_issues_reported_once_and_payload_not_mutated() -> None:
    payload = _payload(voice_hash=DELETE, words=[_word(420, 900), _word(0, 420), _word(0, 420)])
    snapshot = copy.deepcopy(payload)
    expected = [(MISSING_REQUIRED, 'voice_hash'), (CONSTRAINT_VIOLATION, 'words')]
    assert _issues(payload) == expected
    with pytest.raises(WordTimingRejected) as caught:
        parse_word_timing(payload)
    assert [(i.code, i.field) for i in caught.value.issues] == expected
    assert (caught.value.code, caught.value.field) == expected[0]
    assert payload == snapshot


V = (CONSTRAINT_VIOLATION, 'words')
T = (WRONG_TYPE, 'words')
M = (MISSING_REQUIRED, 'words')
WORD_CASES = [
    pytest.param([_word(100, 100)], [V], id='end_equals_start'),
    pytest.param([_word(200, 100)], [V], id='end_before_start'),
    pytest.param([_word(-1, 100)], [V], id='negative_start'),
    pytest.param([_word(0, 500), _word(400, 900)], [V], id='overlap'),
    pytest.param([_word(0, 500), _word(0, 500)], [V], id='duplicate_span'),
    pytest.param([_word(0, 65001)], [V], id='end_beyond_duration'),
    pytest.param([], [V], id='empty_words'),
    pytest.param([_word(True, 420)], [T], id='start_bool'),
    pytest.param([_word(0, True)], [T], id='end_bool'),
    pytest.param([_word(0.0, 420)], [T], id='start_float'),
    pytest.param([_word(0, '420')], [T], id='end_text'),
    pytest.param([_word(0, 420, text=5)], [T], id='text_not_string'),
    pytest.param([{'end_ms': 420, 'text': 'w'}], [M], id='missing_start'),
    pytest.param([{'start_ms': 0, 'end_ms': 420}], [M], id='missing_text'),
    pytest.param([_word(0, 420, text=' ', normalized_text='')], [M], id='blank_text'),
    pytest.param(['news'], [T], id='item_not_object'),
    pytest.param(None, [T], id='words_null'),
]
VALID_WORD_CASES = [
    pytest.param([_word(0, 420), _word(420, 900)], id='touching'),
    pytest.param([_word(0, 420), _word(500, 900)], id='gap'),
    pytest.param([_word(0, 65000)], id='ends_at_duration'),
    pytest.param([_word(0, 1)], id='shortest'),
]


@pytest.mark.parametrize('words, expected', WORD_CASES)
def test_invalid_words_are_rejected(words: object, expected: list) -> None:
    payload = _payload(words=words)
    assert _issues(payload) == expected
    with pytest.raises(WordTimingRejected):
        parse_word_timing(payload)


@pytest.mark.parametrize('words', VALID_WORD_CASES)
def test_valid_words_parse(words: list) -> None:
    parsed = parse_word_timing(_payload(words=words))
    assert [(w.start_ms, w.end_ms) for w in parsed.words] == [(w['start_ms'], w['end_ms']) for w in words]


def test_text_falls_back_to_normalized_text() -> None:
    payload = _payload(words=[{'start_ms': 0, 'end_ms': 420, 'normalized_text': 'ok'}])
    assert parse_word_timing(payload).words == (TimedWord('ok', 0, 420),)


@pytest.mark.parametrize('duration', [DELETE, None])
def test_word_end_is_unbounded_without_voice_duration(duration: object) -> None:
    payload = _payload(words=[_word(0, 10**9)], segment_boundaries=[{'start_ms': 0, 'end_ms': 10**9}], voice_duration_ms=duration)
    assert parse_word_timing(payload).voice_duration_ms is None


def test_segment_boundaries_are_checked() -> None:
    boundaries = [{'start_ms': 500, 'end_ms': 900}, {'start_ms': 0, 'end_ms': 400}]
    assert _issues(_payload(segment_boundaries=boundaries)) == [(CONSTRAINT_VIOLATION, 'segment_boundaries')]


def _texts(plan: KaraokePlan) -> list:
    return [[word.text for word in line.words] for line in plan.lines]


def _spelled(*texts: str) -> tuple:
    return tuple(TimedWord(text, index * 100, index * 100 + 100) for index, text in enumerate(texts))


def test_plan_is_frozen_hashable_and_keeps_marks() -> None:
    plan = _build(words=_words(2))
    assert isinstance(plan, KaraokePlan)
    assert isinstance(plan.lines, tuple) and isinstance(plan.lines[0].words, tuple)
    assert [(w.text, w.highlight_start_ms, w.highlight_end_ms) for w in plan.lines[0].words] == [('w0', 0, 100), ('w1', 100, 200)]
    assert (plan.lines[0].start_ms, plan.lines[0].end_ms) == (0, 200)
    assert (plan.play_res_x, plan.play_res_y) == (PROFILE['play_res_x'], PROFILE['play_res_y'])
    assert hash(plan) == hash(_build(words=_words(2)))
    targets = ((plan, 'play_res_x'), (plan.lines[0], 'end_ms'), (plan.lines[0].words[0], 'text'), (plan.style, 'font_name'))
    for target, name in targets:
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(target, name, 1)


def test_lines_split_by_max_words_per_line() -> None:
    plan = _build(words=_words(7))
    assert _texts(plan) == [['w0', 'w1', 'w2'], ['w3', 'w4', 'w5'], ['w6']]
    assert [(line.start_ms, line.end_ms) for line in plan.lines] == [(0, 300), (300, 600), (600, 700)]


def test_lines_split_by_max_chars_per_line() -> None:
    profile = _with('profile', max_words_per_line=9, max_chars_per_line=5)
    plan = _build(words=_spelled('ab', 'cd', 'ef', 'gh'), profile=profile)
    assert _texts(plan) == [['ab', 'cd'], ['ef', 'gh']]


def test_word_longer_than_limit_stays_whole_on_its_own_line() -> None:
    profile = _with('profile', max_words_per_line=9, max_chars_per_line=5)
    plan = _build(words=_spelled('x', 'abcdefghij', 'y'), profile=profile)
    assert _texts(plan) == [['x'], ['abcdefghij'], ['y']]


def test_plan_accepts_parsed_word_timing() -> None:
    parsed = parse_word_timing(_valid())
    assert _texts(_build(words=parsed)) == [['Breaking', 'news']]
    assert _build(words=parsed) == _build(words=parsed.words)


def test_plan_does_not_alias_inputs_and_ignores_key_order() -> None:
    typography = dict(TYPOGRAPHY)
    plan = _build(typography=typography)
    typography['font_name'] = 'Changed'
    assert plan == _build()
    assert plan.style.font_name == TYPOGRAPHY['font_name']
    reordered = dict(reversed(list(TYPOGRAPHY.items())))
    assert _build(typography={**reordered, 'extra_key': 'ignored'}) == plan


def _rejected(code: str, reason: str, **changes: object) -> None:
    with pytest.raises(KaraokePlanRejected) as caught:
        _build(**changes)
    assert (caught.value.code, caught.value.reason) == (code, reason)


@pytest.mark.parametrize('section', sorted(SECTIONS))
def test_missing_section_is_input_not_ready(section: str) -> None:
    for value in (None, {}):
        _rejected(INPUT_NOT_READY, f'missing_{section}', **{section: value})


@pytest.mark.parametrize('section, key', [(s, k) for s in sorted(SECTIONS) for k in sorted(SECTIONS[s])])
def test_missing_key_is_input_not_ready(section: str, key: str) -> None:
    _rejected(INPUT_NOT_READY, f'missing_{section}.{key}', **{section: _without(section, key)})
    _rejected(INPUT_NOT_READY, f'missing_{section}.{key}', **{section: _with(section, **{key: None})})


@pytest.mark.parametrize('words', [None, (), []])
def test_missing_words_is_input_not_ready(words: object) -> None:
    _rejected(INPUT_NOT_READY, 'missing_words', words=words)


INVALID_CASES = [
    ('typography', 'font_size', True), ('typography', 'font_size', 0), ('typography', 'font_size', '71'),
    ('typography', 'bold', '-1'), ('typography', 'spacing', 1.5),
    ('typography', 'font_name', 'A,B'), ('typography', 'font_name', 'A' + NL + 'B'), ('typography', 'font_name', ' '),
    ('typography', 'primary_colour', 'red'), ('typography', 'primary_colour', '&H0000FFFF' + NL),
    ('typography', 'back_colour', '&H0000FFFF,Bold'),
    ('safe_area', 'margin_left', -1), ('safe_area', 'margin_vertical', True),
    ('profile', 'max_words_per_line', 0), ('profile', 'max_chars_per_line', True), ('profile', 'play_res_x', '360'),
]


@pytest.mark.parametrize('section, key, value', INVALID_CASES)
def test_invalid_value_is_rejected(section: str, key: str, value: object) -> None:
    _rejected(INVALID_INPUT, f'invalid_{section}.{key}', **{section: _with(section, **{key: value})})


def test_safe_area_must_fit_inside_play_res() -> None:
    _rejected(INVALID_INPUT, 'invalid_safe_area', safe_area=_with('safe_area', margin_left=200, margin_right=160))
    _rejected(INVALID_INPUT, 'invalid_safe_area', safe_area=_with('safe_area', margin_vertical=640))


@pytest.mark.parametrize('words', [
    pytest.param((TimedWord('a', 0, 500), TimedWord('b', 400, 900)), id='overlap'),
    pytest.param((TimedWord('a', 100, 100),), id='empty_span'),
    pytest.param((TimedWord('a', -1, 100),), id='negative_start'),
    pytest.param((TimedWord('a', 0, True),), id='bool_end'),
    pytest.param((TimedWord(' ', 0, 100),), id='blank_text'),
    pytest.param(('a',), id='not_timed_word'),
    pytest.param('abc', id='not_sequence'),
])
def test_invalid_words_are_rejected_by_plan(words: object) -> None:
    _rejected(INVALID_INPUT, 'invalid_words', words=words)


TAG_RE = re.compile(re.escape('{' + BS + 'k') + '([0-9]+)' + re.escape('}'))
BLOCK_RE = re.compile('[{][^}]*[}]')
HEADER_LINES = 13
EXPECTED_ASS = NL.join([
    '[Script Info]', 'ScriptType: v4.00+', 'PlayResX: 360', 'PlayResY: 640', 'WrapStyle: 2',
    'ScaledBorderAndShadow: yes', '', '[V4+ Styles]',
    'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, '
    'Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, '
    'MarginR, MarginV, Encoding',
    'Style: Karaoke,FixtureFont,71,&H0000FFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,3,1,2,48,52,160,1',
    '', '[Events]', 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text',
    'Dialogue: 0,0:00:00.00,0:00:00.90,Karaoke,,48,52,160,,{' + BS + 'k42}Breaking {' + BS + 'k48}news',
]) + NL


def _dialogues(ass: str) -> list:
    return [line for line in ass.split(NL) if line.startswith('Dialogue:')]


def _parts(line: str) -> tuple:
    fields = line.split(',', 9)
    return fields[1], fields[2], fields[9]


def _cs(stamp: str) -> int:
    hours, minutes, rest = stamp.split(':')
    seconds, centis = rest.split('.')
    return ((int(hours) * 60 + int(minutes)) * 60 + int(seconds)) * 100 + int(centis)


def _ass(words: tuple, **changes: object) -> str:
    return render_ass(_build(words=words, **changes))


def test_fixture_payload_renders_exact_ass_text() -> None:
    plan = build_karaoke_plan(parse_word_timing(_valid()), TYPOGRAPHY, SAFE_AREA, PROFILE)
    assert render_ass(plan) == EXPECTED_ASS


def test_k_tags_come_from_differences_of_rounded_marks() -> None:
    words = (TimedWord('a', 0, 14), TimedWord('b', 14, 28), TimedWord('c', 28, 42))
    assert sum((w.end_ms - w.start_ms + 5) // 10 for w in words) == 3
    (line,) = _dialogues(_ass(words))
    start, end, text = _parts(line)
    assert (start, end) == ('0:00:00.00', '0:00:00.04')
    assert text == '{' + BS + 'k1}a {' + BS + 'k2}b {' + BS + 'k1}c'


def test_sum_of_k_tags_equals_dialogue_duration_for_irregular_marks() -> None:
    marks = (0, 14, 29, 61, 62, 130, 133, 207, 210, 395, 401, 777, 781, 1004, 1009, 1263)
    words = tuple(TimedWord('w', marks[i], marks[i + 1]) for i in range(0, len(marks) - 1, 2))
    dialogues = _dialogues(_ass(words))
    assert len(dialogues) == 3
    for line in dialogues:
        start, end, text = _parts(line)
        assert sum(int(n) for n in TAG_RE.findall(text)) == _cs(end) - _cs(start)


def test_gap_between_words_is_an_empty_k_tag() -> None:
    (line,) = _dialogues(_ass((TimedWord('a', 0, 100), TimedWord('b', 250, 300))))
    start, end, text = _parts(line)
    assert (start, end) == ('0:00:00.00', '0:00:00.30')
    assert text == '{' + BS + 'k10}a {' + BS + 'k15}{' + BS + 'k5}b'


def test_line_starts_at_first_word_and_timestamps_round_half_up() -> None:
    (line,) = _dialogues(_ass((TimedWord('a', 1234, 1300),)))
    assert _parts(line)[:2] == ('0:00:01.23', '0:00:01.30')
    (line,) = _dialogues(_ass((TimedWord('a', 3723455, 3723900),)))
    assert _parts(line)[:2] == ('1:02:03.46', '1:02:03.90')


def test_each_line_gets_its_own_dialogue_event() -> None:
    ass = _ass(_words(4), profile=_with('profile', max_words_per_line=2))
    rows = [_parts(line) for line in _dialogues(ass)]
    assert [(start, end) for start, end, _ in rows] == [('0:00:00.00', '0:00:00.20'), ('0:00:00.20', '0:00:00.40')]
    assert len(ass.split(NL)) == HEADER_LINES + 2 + 1


INJECTIONS = [
    ('{' + BS + 'an8}', chr(0xFF5B) + chr(0xFF3C) + 'an8' + chr(0xFF5D)),
    ('a}b', 'a' + chr(0xFF5D) + 'b'),
    ('x' + BS + 'Ny', 'x' + chr(0xFF3C) + 'Ny'),
    ('l1' + NL + 'l2', 'l1 l2'),
    ('c' + chr(0) + 'd' + chr(27), 'c d '),
    ('u' + chr(0x2028) + 'v', 'u v'),
    (BS + 'h', chr(0xFF3C) + 'h'),
    ('p' + chr(13) + NL + 'q', 'p  q'),
]


def test_word_text_cannot_inject_overrides_or_lines() -> None:
    words = tuple(TimedWord(raw, index * 100, index * 100 + 100) for index, (raw, _) in enumerate(INJECTIONS))
    ass = _ass(words, profile=_with('profile', max_words_per_line=1, max_chars_per_line=200))
    assert '{' + BS + 'an8}' not in ass
    assert chr(13) not in ass
    assert len(ass.splitlines()) == HEADER_LINES + len(words)
    texts = [_parts(line)[2] for line in _dialogues(ass)]
    assert len(texts) == len(INJECTIONS)
    for (raw, expected), text in zip(INJECTIONS, texts):
        assert all(TAG_RE.fullmatch(block) for block in BLOCK_RE.findall(text)), raw
        assert TAG_RE.sub('', text) == expected, raw


def test_render_is_deterministic_and_reads_style_from_input() -> None:
    first = _ass(_words(3))
    assert first == _ass(_words(3))
    reordered = dict(reversed(list(TYPOGRAPHY.items())))
    assert first == _ass(_words(3), typography=reordered)
    other = _with('typography', font_name='OtherFont', font_size=99)
    changed = _ass(_words(3), typography=other)
    assert 'FixtureFont' not in changed
    assert 'Style: Karaoke,OtherFont,99,' in changed
    wide = _ass(_words(3), profile=_with('profile', play_res_x=720, play_res_y=1280))
    assert 'PlayResX: 720' in wide and 'PlayResY: 1280' in wide


def test_render_rejects_non_plan() -> None:
    with pytest.raises(KaraokePlanRejected) as caught:
        render_ass('plan')
    assert (caught.value.code, caught.value.reason) == (INVALID_INPUT, 'invalid_plan')


def _module_tree() -> ast.AST:
    return ast.parse(MODULE_PATH.read_text(encoding='utf-8'))


def test_module_imports_only_allowed_stdlib() -> None:
    allowed = {'__future__', 're', 'unicodedata', 'collections.abc', 'dataclasses', 'types'}
    imported = set()
    for node in ast.walk(_module_tree()):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or '')
    assert imported <= allowed


def test_module_holds_no_font_colour_or_size_literals() -> None:
    constants = [node.value for node in ast.walk(_module_tree()) if isinstance(node, ast.Constant)]
    numbers = {v for v in constants if isinstance(v, (int, float)) and not isinstance(v, bool)}
    assert numbers <= {0, 1, 2, 10, 60, 100}
    texts = [v for v in constants if isinstance(v, str)]
    assert [t for t in texts if re.search('[0-9]{3,}', t)] == []
    assert [t for t in texts if re.fullmatch('&H[0-9A-Fa-f]{8}', t)] == []
    assert [t for t in texts if 'fixture' in t.lower()] == []
    fonts = {'arial', 'helvetica', 'roboto', 'impact', 'verdana', 'tahoma', 'times new roman', 'open sans'}
    assert [t for t in texts if t.lower() in fonts] == []
