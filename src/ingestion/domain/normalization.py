"""Deterministic text normalization for module B article revisions (D8-B-01, CT-CNT-003)."""
from __future__ import annotations

import unicodedata

NORMALIZER_VERSION = 'normalize-text-r1'
_REMOVED_CATEGORIES = frozenset({'Cc', 'Cf'})


def normalize_text(text: str) -> str:
    """Drop control/format characters, collapse whitespace runs to one space, strip, then compose to NFC."""
    if not isinstance(text, str):
        raise TypeError('text must be a str')
    kept = ''.join(ch for ch in text if ch.isspace() or unicodedata.category(ch) not in _REMOVED_CATEGORIES)
    return unicodedata.normalize('NFC', ' '.join(kept.split()))
