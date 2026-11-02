"""IMGGEN-ROUTE: luật minh hoạ thuần của creative.domain.illustration (kế hoạch style card, thông điệp chú thích, kiểm chú thích bằng mã).

coveredIds: OI-CP7-11-Q1
"""
from __future__ import annotations

import ast
import dataclasses
import pathlib
import re

import pytest

from creative.domain.illustration import (
    BANNED_WORDS, CAPTION_RULES, MAX_CAPTION_WORDS, MIN_CAPTION_WORDS, SHOT_KINDS, STYLE_CARD_FIELDS, TARGET_CANVAS,
    CaptionProblem, IllustrationPlan, IllustrationPlanError, ShotRequest, StyleCard,
    caption_message, check_caption, explain, parse_plan,
)

SOURCE = pathlib.Path(__file__).resolve().parents[3] / 'src' / 'creative' / 'domain' / 'illustration.py'
SENTENCE = 'A weathered fisherman stands on a wet pier at dusk and holds a coiled rope in both hands while the low sun lights the side of his face.'
QUOTES = '"' + chr(0x201c) + chr(0x201d) + chr(0x201e) + chr(0xab) + chr(0xbb)
CARD = {'palette': 'muted teal and rust', 'light': 'low golden sun', 'contrast': 'medium', 'grain': 'fine', 'lens': '35mm prime', 'depth_of_field': 'deep', 'weather': 'light fog', 'mood': 'quiet'}


def caption_of(words: int) -> str:
    return ' '.join((SENTENCE.split() * 20)[:words])


def payload(count: int = 3) -> dict:
    return {'style_card': dict(CARD), 'requests': [{'shot': SHOT_KINDS[i], 'scene_intent': f'intent {i}', 'description': f'description {i}'} for i in range(count)]}


def fails(data, count, code, field) -> None:
    with pytest.raises(IllustrationPlanError) as info:
        parse_plan(data, count)
    assert isinstance(info.value, ValueError) and (info.value.code, info.value.field) == (code, field)


def test_constants_have_the_agreed_values() -> None:
    assert (MIN_CAPTION_WORDS, MAX_CAPTION_WORDS) == (80, 350)
    assert BANNED_WORDS == ('logo', 'brand', 'trademark', 'watermark', 'lettering', 'inscription', 'signage', 'headline', 'caption', 'text')
    assert SHOT_KINDS == ('wide', 'medium', 'close_detail', 'object', 'aftermath')
    assert STYLE_CARD_FIELDS == ('palette', 'light', 'contrast', 'grain', 'lens', 'depth_of_field', 'weather', 'mood')
    assert TARGET_CANVAS == 'TARGET CANVAS: 9:16'
    names = lambda cls: tuple(f.name for f in dataclasses.fields(cls))
    assert names(StyleCard) == STYLE_CARD_FIELDS and names(ShotRequest) == ('shot', 'scene_intent', 'description')
    assert names(IllustrationPlan) == ('style_card', 'requests') and names(CaptionProblem) == ('code', 'detail')


def test_caption_rules_are_six_plain_sentences_without_banned_words_or_quotes() -> None:
    assert len(re.findall(r'[.](?:\s|\Z)', CAPTION_RULES)) == 6 and CAPTION_RULES.count(chr(10)) == 0
    assert [p for p in check_caption(CAPTION_RULES) if p.code in ('banned_word', 'double_quote')] == []
    assert not any(ch in CAPTION_RULES for ch in QUOTES)


def test_value_objects_are_frozen_slots_dataclasses() -> None:
    plan = parse_plan(payload(2), 2)
    for obj in (plan, plan.style_card, plan.requests[0], CaptionProblem('x', 'y')):
        assert not hasattr(obj, '__dict__')
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(obj, dataclasses.fields(obj)[0].name, 'changed')
    assert isinstance(plan.requests, tuple)


@pytest.mark.parametrize('count', [1, 2, 3, 4, 5])
def test_parse_plan_accepts_each_count(count) -> None:
    plan = parse_plan(payload(count), count)
    assert plan.style_card == StyleCard(**CARD)
    assert plan.requests == tuple(ShotRequest(SHOT_KINDS[i], f'intent {i}', f'description {i}') for i in range(count))


@pytest.mark.parametrize('raw', ['Close Detail', 'close-detail', ' CLOSE_DETAIL ', 'close detail'])
def test_parse_plan_normalizes_shot_names(raw) -> None:
    data = payload(1)
    data['requests'][0]['shot'] = raw
    assert parse_plan(data, 1).requests[0].shot == 'close_detail'


@pytest.mark.parametrize('count', [0, 6, -1, True, '3', 2.0, None])
def test_parse_plan_rejects_bad_count(count) -> None:
    with pytest.raises(ValueError):
        parse_plan(payload(3), count)


def test_parse_plan_requires_exact_request_count() -> None:
    fails(payload(3), 2, 'request_count', 'requests')
    fails(payload(3), 4, 'request_count', 'requests')


@pytest.mark.parametrize('data', [None, [], 'plan', 7])
def test_parse_plan_rejects_a_payload_that_is_not_an_object(data) -> None:
    fails(data, 1, 'plan_not_object', 'payload')


def test_parse_plan_rejects_bad_style_card_and_requests_containers() -> None:
    data = payload(1)
    del data['style_card']
    fails(data, 1, 'missing', 'style_card')
    data['style_card'] = []
    fails(data, 1, 'invalid_object', 'style_card')
    data = payload(1)
    del data['requests']
    fails(data, 1, 'missing', 'requests')
    data['requests'] = 'abc'
    fails(data, 1, 'invalid_list', 'requests')
    data['requests'] = [7]
    fails(data, 1, 'invalid_object', 'requests[0]')


@pytest.mark.parametrize('name', STYLE_CARD_FIELDS)
def test_parse_plan_requires_each_style_card_field_as_one_line(name) -> None:
    field = 'style_card.' + name
    for value, code in ((None, 'missing'), ('   ', 'invalid_text'), (7, 'invalid_text'), ('a' + chr(10) + 'b', 'multiline'), ('a' + chr(13) + 'b', 'multiline'), ('x' * 401, 'too_long')):
        data = payload(1)
        data['style_card'][name] = value
        fails(data, 1, code, field)
    data = payload(1)
    data['style_card'][name] = 'x' * 400
    assert parse_plan(data, 1).style_card is not None


@pytest.mark.parametrize('name', ['shot', 'scene_intent', 'description'])
def test_parse_plan_requires_each_request_field_as_one_line(name) -> None:
    for value, code in ((None, 'missing'), ('', 'invalid_text'), (7, 'invalid_text'), ('a' + chr(10) + 'b', 'multiline'), ('x' * 401, 'too_long')):
        data = payload(2)
        data['requests'][1][name] = value
        fails(data, 2, code, f'requests[1].{name}')


def test_parse_plan_rejects_unknown_and_duplicate_shots() -> None:
    data = payload(2)
    data['requests'][1]['shot'] = 'panorama'
    fails(data, 2, 'unknown_shot', 'requests[1].shot')
    data['requests'][1]['shot'] = 'WIDE'
    fails(data, 2, 'duplicate_shot', 'requests[1].shot')


def message(retry=None) -> str:
    request = ShotRequest('wide', 'show the pier', 'wide view of the pier at dusk')
    return caption_message(request, StyleCard(**CARD), retry)


def test_caption_message_orders_canvas_request_style_card_rules_and_retry() -> None:
    expected = [TARGET_CANVAS, 'SHOT: wide', 'SCENE INTENT: show the pier', 'DESCRIPTION: wide view of the pier at dusk', 'STYLE CARD:']
    expected += [f'- {name}: {CARD[name]}' for name in STYLE_CARD_FIELDS] + [CAPTION_RULES]
    assert message().split(chr(10)) == expected
    assert message('Write at least 80 words.').split(chr(10)) == expected + ['RETRY REASON: Write at least 80 words.']
    assert message('  first' + chr(10) + 'second  ').split(chr(10))[-1] == 'RETRY REASON: first second'
    assert message('') == message(None) == message('   ')
    assert [p for p in check_caption(message()) if p.code == 'banned_word'] == []
    with pytest.raises(ValueError):
        message(7)


def codes(problems) -> list:
    return [p.code for p in problems]


def test_check_caption_accepts_a_good_caption_and_is_deterministic() -> None:
    assert check_caption(caption_of(84)) == () and check_caption(caption_of(84)) == check_caption(caption_of(84))


@pytest.mark.parametrize('words, expected', [(0, ['too_short']), (79, ['too_short']), (80, []), (350, []), (351, ['too_long'])])
def test_check_caption_enforces_word_limits(words, expected) -> None:
    assert codes(check_caption(caption_of(words))) == expected
    if expected:
        assert check_caption(caption_of(words))[0].detail == str(words)


def test_check_caption_rejects_non_string_arguments() -> None:
    for args in ((7,), (None,), (caption_of(90), 'Putin'), (caption_of(90), b'x'), (caption_of(90), [7])):
        with pytest.raises(ValueError):
            check_caption(*args)


@pytest.mark.parametrize('word', BANNED_WORDS)
@pytest.mark.parametrize('suffix', ['', 's', 'es', 'ed', 'ing', 'S', 'ING'])
def test_check_caption_flags_banned_words_and_their_forms(word, suffix) -> None:
    form = word.upper() + suffix if suffix.isupper() else word + suffix
    caption = caption_of(90) + ' ' + form + '.'
    assert CaptionProblem('banned_word', word) in check_caption(caption)


@pytest.mark.parametrize('clean', ['texture', 'context', 'logical', 'textile', 'headlights'])
def test_check_caption_leaves_words_that_only_contain_a_banned_word(clean) -> None:
    assert check_caption(caption_of(90) + ' ' + clean + '.') == ()


def test_check_caption_reports_each_banned_word_once_in_list_order() -> None:
    caption = caption_of(90) + ' text logo text Logos'
    assert [p.detail for p in check_caption(caption) if p.code == 'banned_word'] == ['logo', 'text']


@pytest.mark.parametrize('quote', list(QUOTES))
def test_check_caption_flags_every_double_quote_form(quote) -> None:
    assert 'double_quote' in codes(check_caption(caption_of(90) + ' ' + quote + 'x'))


def test_check_caption_allows_apostrophes() -> None:
    assert check_caption(caption_of(90) + ' the fisherman' + chr(39) + 's rope') == ()


def test_check_caption_flags_non_english_text() -> None:
    accented = ' '.join(['Một người đàn ông đứng trên cầu tàu lúc hoàng hôn và cầm một cuộn dây thừng'] * 6)
    plain = ' '.join(['Mot nguoi dan ong dung tren cau tau luc hoang hon va cam mot cuon day thung'] * 6)
    assert 'not_english' in codes(check_caption(accented)) and 'not_english' in codes(check_caption(plain))
    assert check_caption(caption_of(90) + ' caf' + chr(0xe9)) == ()
    assert 'not_english' in codes(check_caption(caption_of(90) + ' ' + ' '.join([chr(0xe9)] * 12)))


def test_check_caption_flags_entity_names() -> None:
    base = caption_of(90)
    assert CaptionProblem('entity_name', 'Harbor Master') in check_caption(base + ' the harbor master waves', ('Harbor Master',))
    assert CaptionProblem('entity_name', 'Putin') in check_caption(base + ' Putin' + chr(39) + 's coat', ('Putin',))
    assert check_caption(base + ' Lights and kimono', ('Li', 'Kim')) == ()
    assert CaptionProblem('entity_name', 'Li') in check_caption(base + ' Li waits', ('Li',))
    assert check_caption(base + ' li waits', ('Li',)) == ()
    assert CaptionProblem('entity_name', 'Kim') in check_caption(base + ' Kim waits', ['Kim'])
    assert check_caption(base + ' a pier', ('', '   ')) == ()
    assert codes(check_caption(base + ' Putin Putin', ('Putin', 'Putin'))) == ['entity_name']


def test_check_caption_orders_problems_by_length_language_quotes_banned_entities() -> None:
    caption = 'The pier ' + chr(0x201c) + 'logo' + chr(0x201d) + ' near Putin and the old boat on the water'
    assert codes(check_caption(caption, ('Putin',))) == ['too_short', 'double_quote', 'banned_word', 'entity_name']


def test_explain_gives_one_sentence_per_problem_without_double_quotes() -> None:
    problems = (CaptionProblem('too_short', '40'), CaptionProblem('too_long', '400'), CaptionProblem('not_english', 'x'), CaptionProblem('double_quote', 'double quotation marks'), CaptionProblem('banned_word', 'logo'), CaptionProblem('entity_name', 'Mr ' + chr(0x201c) + 'Xan' + chr(0x201d)), CaptionProblem('other_code', 'y'))
    text = explain(problems)
    assert len(re.findall(r'[.](?:\s|\Z)', text)) == len(problems) and not any(ch in text for ch in QUOTES)
    assert '40' in text and '400' in text and 'logo' in text and 'Xan' in text and 'other_code' in text
    assert explain(()) == '' and isinstance(explain(check_caption(caption_of(10))), str)


def test_the_module_is_pure_and_names_no_test_double() -> None:
    text = SOURCE.read_text(encoding='utf-8')
    low = text.lower()
    for word in ('mock', 'fake', 'os.environ', 'memory', 'getenv', 'print(', 'open(', 'subprocess', 'socket', 'datetime', 'random'):
        assert word not in low
    modules = set()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add(node.module)
    assert modules == {'__future__', 're', 'collections.abc', 'dataclasses'}
