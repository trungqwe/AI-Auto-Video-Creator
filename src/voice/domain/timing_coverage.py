"""E-10: word coverage, confidence and gap report of WordTiming (CT-SUB-001).

Pure domain: no I/O, no clock. Tokenization rules, gap_tolerance_ms and min_confidence are policy inputs.
The module has no default value for any of them: a missing policy or field raises TimingPolicyRejected(INPUT_NOT_READY).

coveredIds: CT-SUB-001 (word coverage, gap, confidence)
"""
from __future__ import annotations

import difflib
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

from voice.domain.word_timing import WordTimingWord

INPUT_NOT_READY = 'INPUT_NOT_READY'
UNICODE_FORMS = ('NFC', 'NFD', 'NFKC', 'NFKD')


class TimingPolicyRejected(Exception):
    """A policy input is missing: `code` is INPUT_NOT_READY, `reason` is the stable machine reason."""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(f'{code}: {reason}')
        self.code = code
        self.reason = reason


@dataclass(frozen=True, kw_only=True)
class TokenizationPolicy:
    """Policy input supplied by the caller; every field defaults to None, which means not ready.

    unicode_form is one of UNICODE_FORMS; edge_strip_categories are Unicode general-category prefixes
    (for example 'P') stripped from both ends of every token; min_confidence is in [0, 1].
    """

    revision: str | None = None
    unicode_form: str | None = None
    casefold: bool | None = None
    edge_strip_categories: tuple[str, ...] | None = None
    gap_tolerance_ms: int | None = None
    min_confidence: int | float | None = None


@dataclass(frozen=True)
class CoverageReport:
    policy_revision: str
    expected_count: int
    matched_count: int
    missing_indices: tuple[int, ...]
    extra_indices: tuple[int, ...]
    complete: bool


@dataclass(frozen=True)
class AlignmentGap:
    start_ms: int
    end_ms: int

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    def to_payload(self) -> dict[str, int]:
        return {'start_ms': self.start_ms, 'end_ms': self.end_ms}


@dataclass(frozen=True)
class LowConfidenceWord:
    index: int
    confidence: int | float


@dataclass(frozen=True)
class GapReport:
    alignment_gaps: tuple[AlignmentGap, ...]
    low_confidence_words: tuple[LowConfidenceWord, ...]


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _require(policy: TokenizationPolicy | None, *names: str) -> TokenizationPolicy:
    if policy is None:
        raise TimingPolicyRejected(INPUT_NOT_READY, 'missing_policy')
    if not isinstance(policy, TokenizationPolicy):
        raise TypeError('policy must be a TokenizationPolicy')
    for name in names:
        if getattr(policy, name) is None:
            raise TimingPolicyRejected(INPUT_NOT_READY, f'missing_{name}')
    return policy


def _check_rules(policy: TokenizationPolicy | None) -> TokenizationPolicy:
    policy = _require(policy, 'revision', 'unicode_form', 'casefold', 'edge_strip_categories')
    categories = policy.edge_strip_categories
    if not isinstance(policy.revision, str) or not policy.revision:
        raise ValueError('revision must be a non-empty string')
    if policy.unicode_form not in UNICODE_FORMS:
        raise ValueError('unicode_form must be one of NFC, NFD, NFKC, NFKD')
    if not isinstance(policy.casefold, bool):
        raise ValueError('casefold must be a bool')
    if not isinstance(categories, tuple) or not all(isinstance(item, str) and item for item in categories):
        raise ValueError('edge_strip_categories must be a tuple of non-empty Unicode category prefixes')
    return policy


def _strip_edges(token: str, categories: tuple[str, ...]) -> str:
    start, end = 0, len(token)
    while start < end and unicodedata.category(token[start]).startswith(categories):
        start += 1
    while end > start and unicodedata.category(token[end - 1]).startswith(categories):
        end -= 1
    return token[start:end]


def tokenize_script(text: str, policy: TokenizationPolicy | None) -> tuple[str, ...]:
    """Split on whitespace, normalize per policy, strip edge punctuation; tokens that become empty are dropped."""
    if not isinstance(text, str):
        raise TypeError('text must be a str')
    policy = _check_rules(policy)
    folded = unicodedata.normalize(policy.unicode_form, text)
    if policy.casefold:
        folded = unicodedata.normalize(policy.unicode_form, folded.casefold())
    stripped = (_strip_edges(raw, policy.edge_strip_categories) for raw in folded.split())
    return tuple(token for token in stripped if token)


def check_coverage(script_text: str, words: Iterable[WordTimingWord], policy: TokenizationPolicy | None) -> CoverageReport:
    """Compare the script tokens with word.normalized_text in order.

    complete is True only when the two sequences are identical and non-empty; a word whose normalized_text
    is None or differs from the token is both a missing script index and an extra word index.
    """
    expected = tokenize_script(script_text, policy)
    if isinstance(words, (str, bytes)):
        raise TypeError('words must be an iterable of WordTimingWord')
    actual = tuple(word.normalized_text for word in words)
    blocks = difflib.SequenceMatcher(None, expected, actual, autojunk=False).get_matching_blocks()
    matched_expected = {i + k for i, _, size in blocks for k in range(size)}
    matched_actual = {j + k for _, j, size in blocks for k in range(size)}
    missing = tuple(i for i in range(len(expected)) if i not in matched_expected)
    extra = tuple(j for j in range(len(actual)) if j not in matched_actual)
    complete = bool(expected) and not missing and not extra
    return CoverageReport(policy.revision, len(expected), len(matched_expected), missing, extra, complete)


def build_gap_report(words: Iterable[WordTimingWord], voice_duration_ms: int | None, policy: TokenizationPolicy | None) -> GapReport:
    """Report gaps strictly longer than policy.gap_tolerance_ms (leading from 0, between words, trailing to the voice end)
    and words whose confidence is strictly below policy.min_confidence; words without confidence are not scored.

    A missing policy, gap_tolerance_ms, min_confidence or voice_duration_ms raises TimingPolicyRejected(INPUT_NOT_READY).
    """
    policy = _require(policy, 'gap_tolerance_ms', 'min_confidence')
    tolerance, minimum = policy.gap_tolerance_ms, policy.min_confidence
    if not _is_int(tolerance) or tolerance < 0:
        raise ValueError('gap_tolerance_ms must be an integer >= 0')
    if not _is_number(minimum) or not 0 <= minimum <= 1:
        raise ValueError('min_confidence must be a number in [0, 1]')
    if voice_duration_ms is None:
        raise TimingPolicyRejected(INPUT_NOT_READY, 'missing_voice_duration_ms')
    if not _is_int(voice_duration_ms) or voice_duration_ms <= 0:
        raise ValueError('voice_duration_ms must be an integer > 0')
    ordered = tuple(words)
    gaps: list[AlignmentGap] = []
    cursor = 0
    for word in ordered:
        if word.start_ms - cursor > tolerance:
            gaps.append(AlignmentGap(cursor, word.start_ms))
        cursor = max(cursor, word.end_ms)
    if voice_duration_ms - cursor > tolerance:
        gaps.append(AlignmentGap(cursor, voice_duration_ms))
    low = tuple(
        LowConfidenceWord(index, word.confidence)
        for index, word in enumerate(ordered)
        if _is_number(word.confidence) and word.confidence < minimum
    )
    return GapReport(tuple(gaps), low)
