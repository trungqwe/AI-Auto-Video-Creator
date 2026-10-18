"""B-2: deterministic text normalization and keyword topic classification (D8-B-01, D8-B-08)."""
import unicodedata

import pytest

from ingestion.domain.normalization import NORMALIZER_VERSION, normalize_text
from ingestion.domain.topic import UNCLASSIFIED, classify_topic

VIETNAMESE = 'Hà Nội mưa lớn, người dân đội mũ bảo hiểm khi đi xe máy'
TOPIC_RULES = [
    {'topic': 'the_thao', 'keywords': ['bóng đá', 'World Cup']},
    {'topic': 'kinh_te', 'keywords': ['lãi suất', 'chứng khoán']},
]


def _nfd(text: str) -> str:
    return unicodedata.normalize('NFD', text)


def test_nfd_input_is_normalized_to_nfc() -> None:
    nfd = _nfd(VIETNAMESE)
    assert nfd != VIETNAMESE
    assert normalize_text(nfd) == VIETNAMESE
    assert normalize_text(VIETNAMESE) == VIETNAMESE


def test_control_characters_are_removed() -> None:
    assert normalize_text('Hà\x00 Nội\x07\x7f mưa​ to﻿') == 'Hà Nội mưa to'


def test_whitespace_is_collapsed_and_stripped() -> None:
    assert normalize_text('  Hà \t Nội\r\n\n mưa 　to  ') == 'Hà Nội mưa to'


def test_control_character_between_base_and_mark_still_yields_nfc() -> None:
    assert normalize_text('a\x00́') == 'á'


def test_normalize_is_idempotent_and_deterministic() -> None:
    raw = _nfd('  Xin\tchào\x00  Việt Nam ')
    first = normalize_text(raw)
    assert first == 'Xin chào Việt Nam'
    assert normalize_text(raw) == first
    assert normalize_text(first) == first
    assert unicodedata.is_normalized('NFC', first)


def test_normalize_rejects_non_string() -> None:
    for value in (None, b'abc', 1):
        with pytest.raises(TypeError):
            normalize_text(value)


def test_normalizer_version_is_set() -> None:
    assert NORMALIZER_VERSION == 'normalize-text-r1'


def test_topic_matches_keyword_phrase() -> None:
    assert classify_topic('Đội tuyển bóng đá Việt Nam thắng đậm', TOPIC_RULES) == ('the_thao', False)


def test_topic_matches_nfd_and_case_insensitive_text() -> None:
    assert classify_topic(_nfd('Ngân hàng giảm LÃI SUẤT cho vay'), TOPIC_RULES) == ('kinh_te', False)
    assert classify_topic('Lịch thi đấu world cup 2026', TOPIC_RULES) == ('the_thao', False)


def test_topic_requires_whole_word_match() -> None:
    rules = [{'topic': 'the_thao', 'keywords': ['đá']}]
    assert classify_topic('Đám đông xem pháo hoa', rules) == (UNCLASSIFIED, True)
    assert classify_topic('Trận đá bóng tối qua', rules) == ('the_thao', False)


def test_topic_without_matching_rule_is_unclassified_and_uncertain() -> None:
    assert classify_topic('Thời tiết hôm nay nắng đẹp', TOPIC_RULES) == ('unclassified', True)


def test_empty_rules_never_assign_topic() -> None:
    text = 'Đội tuyển bóng đá Việt Nam thắng đậm'
    assert classify_topic(text, []) == ('unclassified', True)
    assert classify_topic(text, [{'topic': 'the_thao', 'keywords': []}]) == ('unclassified', True)
    assert classify_topic(text, [{'topic': 'the_thao', 'keywords': ['', '  ']}]) == ('unclassified', True)


def test_topic_with_most_keyword_hits_wins() -> None:
    text = 'Bóng đá ảm đạm khi lãi suất tăng và chứng khoán giảm'
    assert classify_topic(text, TOPIC_RULES) == ('kinh_te', False)


def test_topic_tie_keeps_rule_order_and_is_uncertain() -> None:
    text = 'Cổ phiếu bóng đá trên sàn chứng khoán'
    assert classify_topic(text, TOPIC_RULES) == ('the_thao', True)
    assert classify_topic(text, list(reversed(TOPIC_RULES))) == ('kinh_te', True)


def test_topic_classification_is_deterministic() -> None:
    text = _nfd('Đội tuyển bóng đá Việt Nam thắng đậm')
    assert classify_topic(text, TOPIC_RULES) == classify_topic(text, TOPIC_RULES) == ('the_thao', False)


def test_invalid_topic_rule_is_rejected() -> None:
    for rule in ({'topic': '', 'keywords': ['x']}, {'topic': 'x', 'keywords': 'bóng đá'}, {'topic': 1, 'keywords': ['x']}):
        with pytest.raises(ValueError):
            classify_topic('bóng đá', [rule])
