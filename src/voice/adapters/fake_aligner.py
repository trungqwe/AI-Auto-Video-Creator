"""In-memory fake AlignerPort for tests (CT-SUB-001); no tool, no I/O, no clock."""
from __future__ import annotations

import unicodedata

from voice.ports.aligner import AlignerError, AlignmentRequest, AlignmentResult

MODES = ('ok', 'reorder', 'drop_last', 'beyond_duration')


def _normalize(token: str) -> str:
    """NFC, casefold and strip edge punctuation (category P); matches the test tokenization policy."""
    text = unicodedata.normalize('NFC', unicodedata.normalize('NFC', token).casefold())
    start, end = 0, len(text)
    while start < end and unicodedata.category(text[start]).startswith('P'):
        start += 1
    while end > start and unicodedata.category(text[end - 1]).startswith('P'):
        end -= 1
    return text[start:end]


class FakeAligner:
    def __init__(
        self,
        *,
        mode: str = 'ok',
        locale_reported: str | None = None,
        aligner_revision: str = 'fake-aligner-v1',
        confidence: float = 0.95,
        failure: AlignerError | None = None,
    ) -> None:
        if mode not in MODES:
            raise ValueError(f'mode must be one of {MODES}')
        if not isinstance(aligner_revision, str) or not aligner_revision:
            raise ValueError('aligner_revision must be a non-empty string')
        self._mode = mode
        self._locale_reported = locale_reported
        self._aligner_revision = aligner_revision
        self._confidence = confidence
        self._failure = failure
        self.align_calls = 0

    def align(self, request: AlignmentRequest) -> AlignmentResult:
        self.align_calls += 1
        if self._failure is not None:
            raise self._failure
        tokens = request.script_text.split()
        duration = request.voice_duration_ms
        count = max(len(tokens), 1)
        words = [
            {
                'start_ms': duration * index // count,
                'end_ms': duration * (index + 1) // count,
                'text': token,
                'normalized_text': _normalize(token),
                'confidence': self._confidence,
            }
            for index, token in enumerate(tokens)
        ]
        if self._mode == 'reorder':
            texts = [(word['text'], word['normalized_text']) for word in reversed(words)]
            for word, (text, normalized) in zip(words, texts):
                word['text'], word['normalized_text'] = text, normalized
        elif self._mode == 'drop_last':
            words = words[:-1]
        elif self._mode == 'beyond_duration' and words:
            words[-1]['end_ms'] = duration + 1000
        return AlignmentResult(
            words=tuple(words),
            segment_boundaries=({'start_ms': 0, 'end_ms': duration},),
            voice_locale_reported=self._locale_reported if self._locale_reported is not None else request.expected_language,
            aligner_revision=self._aligner_revision,
        )
