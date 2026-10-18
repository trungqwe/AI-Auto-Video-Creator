"""Keyword topic classification for module B (D8-B-08); rules come from the topic config revision passed by the caller."""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from ingestion.domain.normalization import normalize_text

UNCLASSIFIED = 'unclassified'
_WORD_RE = re.compile(r'\w+')


def _phrase(text: str) -> str:
    return ' '.join(_WORD_RE.findall(normalize_text(normalize_text(text).casefold())))


def classify_topic(text: str, topic_rules: Sequence[Mapping]) -> tuple[str, bool]:
    """Return (topic, uncertain).

    The rule with the most distinct whole-phrase keyword hits wins; a tie keeps rule order and is uncertain;
    no hit or no rule gives (UNCLASSIFIED, True).
    """
    haystack = f' {_phrase(text)} '
    best_topic, best_hits, tied = UNCLASSIFIED, 0, False
    for rule in topic_rules:
        topic, keywords = rule['topic'], rule['keywords']
        if not isinstance(topic, str) or not topic or isinstance(keywords, str) or not isinstance(keywords, Sequence):
            raise ValueError('topic rule needs a non-empty topic and a keyword sequence')
        phrases = {_phrase(keyword) for keyword in keywords} - {''}
        hits = sum(1 for phrase in phrases if f' {phrase} ' in haystack)
        if hits > best_hits:
            best_topic, best_hits, tied = topic, hits, False
        elif hits and hits == best_hits:
            tied = True
    if not best_hits:
        return UNCLASSIFIED, True
    return best_topic, tied
