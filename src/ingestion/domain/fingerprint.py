"""Exact and near-duplicate fingerprints for module B (D8-B-01).

Threshold and shingle size come from the dedup policy revision passed by the caller.
"""
from __future__ import annotations

import hashlib
from collections.abc import Mapping, Set

from ingestion.domain.normalization import normalize_text

NEAR_DUPLICATE_JACCARD = 'near_duplicate_jaccard'
SHINGLE_SIZE = 'shingle_size'


def exact_fingerprint(text: str) -> str:
    """Return the SHA-256 hex digest of the UTF-8 encoded normalized text."""
    return hashlib.sha256(normalize_text(text).encode('utf-8')).hexdigest()


def shingles(text: str, size: int) -> frozenset[tuple[str, ...]]:
    """Return word shingles of the normalized text; a text shorter than size yields one shingle of all its words."""
    if isinstance(size, bool) or not isinstance(size, int) or size < 1:
        raise ValueError('size must be a positive integer')
    words = normalize_text(text).split()
    if len(words) < size:
        return frozenset({tuple(words)}) if words else frozenset()
    return frozenset(tuple(words[i:i + size]) for i in range(len(words) - size + 1))


def jaccard(a: Set, b: Set) -> float:
    """Return len(a & b) / len(a | b); two empty sets give 0.0."""
    union = len(a | b)
    return len(a & b) / union if union else 0.0


def is_near_duplicate(a: str, b: str, policy: Mapping) -> bool:
    """Return True when the shingle Jaccard of a and b reaches the policy threshold, using the policy shingle size."""
    threshold = policy[NEAR_DUPLICATE_JACCARD]
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not 0 < threshold <= 1:
        raise ValueError('near_duplicate_jaccard must be a number in (0, 1]')
    size = policy[SHINGLE_SIZE]
    return jaccard(shingles(a, size), shingles(b, size)) >= threshold
