"""D-15-FIX2: parse_model_json_object strips code fences and surrounding sentences from model output (R31, CP7-10 RG-09).

coveredIds: D-15-FIX2
"""
from __future__ import annotations

import json

import pytest

from controlplane.application.ai_output.model_json import ModelJsonError, parse_model_json_object

OBJ = {'topic': 'port strike', 'items': [1, 2]}
BODY = json.dumps(OBJ)
FENCE = chr(96) * 3
NL = chr(10)


def reason_of(text):
    with pytest.raises(ModelJsonError) as caught:
        parse_model_json_object(text)
    return caught.value.reason


def test_plain_object():
    assert parse_model_json_object(BODY) == OBJ


def test_fence_with_language_and_closing():
    assert parse_model_json_object(FENCE + 'json' + NL + BODY + NL + FENCE) == OBJ


def test_fence_without_language():
    assert parse_model_json_object(FENCE + NL + BODY + NL + FENCE) == OBJ


def test_fence_without_closing():
    assert parse_model_json_object(FENCE + 'json' + NL + BODY) == OBJ


@pytest.mark.parametrize('text', [
    'Here is the JSON:' + NL + BODY,
    BODY + NL + 'Hope this helps.',
    'Here is the JSON:' + NL + BODY + NL + 'Hope this helps.',
    FENCE + 'json' + NL + BODY + NL + FENCE + NL + 'Hope this helps.',
])
def test_sentences_around_the_object(text):
    assert parse_model_json_object(text) == OBJ


def test_raw_newline_and_tab_inside_a_string_value():
    text = '{"a": "line1' + NL + 'line2' + chr(9) + 'end"}'
    assert parse_model_json_object(text) == {'a': 'line1' + NL + 'line2' + chr(9) + 'end'}


@pytest.mark.parametrize('text', ['', '  ', None, 123])
def test_empty_output(text):
    assert reason_of(text) == 'empty_output'


@pytest.mark.parametrize('text', ['not json', BODY[:-1], FENCE + 'json' + NL + BODY[:-1] + NL + FENCE])
def test_not_json(text):
    assert reason_of(text) == 'not_json'


@pytest.mark.parametrize('text', ['[1, 2]', '[{"a": 1}]'])
def test_not_a_json_object(text):
    assert reason_of(text) == 'not_a_json_object'


class Boom(Exception):
    pass


def reject(name):
    raise Boom(name)


def test_parse_constant_error_passes_through():
    with pytest.raises(Boom):
        parse_model_json_object('{"a": NaN}', parse_constant=reject)


def test_parse_constant_error_passes_through_inside_extracted_span():
    with pytest.raises(Boom):
        parse_model_json_object('Result: {"a": NaN} done', parse_constant=reject)


def test_model_json_error_is_a_value_error():
    assert issubclass(ModelJsonError, ValueError)
