"""Real AlignerPort: local faster_whisper word timestamps matched to the script text (CT-SUB-001).

Every start and end comes from the model. A script word the model did not produce is reported as unmatched and gets no time; nothing is interpolated or spread evenly.
"""
from __future__ import annotations

import difflib
import hashlib
import importlib.metadata
import json
import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from voice.domain.timing_coverage import TokenizationPolicy, tokenize_script
from voice.domain.tts_invocation import redact_error
from voice.ports.aligner import AlignerError, AlignmentRequest, AlignmentResult

MODEL_GROUP = 'faster-whisper-small.en'
ERROR_WEIGHTS_UNPINNED = 'weights_unpinned'
ERROR_WEIGHTS_MISSING = 'weights_missing'
ERROR_WEIGHTS_SHA256_MISMATCH = 'weights_sha256_mismatch'
ERROR_WEIGHTS_IN_GIT_TREE = 'weights_in_git_tree'
ERROR_VOICE_UNAVAILABLE = 'voice_unavailable'
ERROR_VOICE_HASH_MISMATCH = 'voice_hash_mismatch'
ERROR_MODEL_OUTPUT_INVALID = 'model_output_invalid'
ERROR_TOKENIZATION_INCONSISTENT = 'tokenization_inconsistent'
ERROR_NO_ALIGNED_WORDS = 'no_aligned_words'
ERROR_UNMATCHED_RATIO_EXCEEDED = 'alignment_unmatched_ratio_exceeded'
ERROR_RUNTIME = 'aligner_runtime_error'
_SHA256_RE = re.compile(r'[0-9a-f]{64}')


@dataclass(frozen=True, kw_only=True)
class WhisperAlignerConfig:
    model_dir: Path
    lock_path: Path
    resolve_audio: Callable[[str], Path]
    tokenization_policy: TokenizationPolicy
    max_unmatched_word_ratio: float
    language: str = 'en'
    device: str = 'cpu'
    compute_type: str = 'int8'
    model_group: str = MODEL_GROUP
    model_hash_file: str = 'model.bin'

    def __post_init__(self) -> None:
        for name in ('model_dir', 'lock_path'):
            value = getattr(self, name)
            if not isinstance(value, Path) or not value.is_absolute():
                raise ValueError(f'{name} must be an absolute Path')
        if not callable(self.resolve_audio):
            raise ValueError('resolve_audio must be callable')
        for name in ('language', 'device', 'compute_type', 'model_group', 'model_hash_file'):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f'{name} must be a non-empty string')
        ratio = self.max_unmatched_word_ratio
        if isinstance(ratio, bool) or not isinstance(ratio, (int, float)) or not 0.0 <= ratio <= 1.0:
            raise ValueError('max_unmatched_word_ratio must be a number in [0, 1]')
        if not isinstance(self.tokenization_policy, TokenizationPolicy):
            raise ValueError('tokenization_policy must be a TokenizationPolicy')
        tokenize_script('probe', self.tokenization_policy)


def _fail(code: str, message: str, known_secrets: tuple[str, ...] = ()) -> AlignerError:
    return AlignerError(code, redact_error(message, known_secrets), retryable=False)


def _file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open('rb') as handle:
        while chunk := handle.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


def _inside_git_tree(path: Path) -> bool:
    resolved = path.resolve()
    return any((candidate / '.git').exists() for candidate in (resolved, *resolved.parents))


def _pinned_group(lock_path: Path, group: str) -> dict[str, str]:
    """Return name -> pinned sha256 of every file of the group; a missing, null, BLOCKED or malformed pin is weights_unpinned."""
    try:
        entries = json.loads(lock_path.read_text(encoding='utf-8'))['files']
        members = [entry for entry in entries if isinstance(entry, dict) and entry.get('group') == group]
    except (OSError, ValueError, KeyError, TypeError):
        raise _fail(ERROR_WEIGHTS_UNPINNED, 'weights lock unreadable') from None
    if not members:
        raise _fail(ERROR_WEIGHTS_UNPINNED, 'weights group not in lock')
    pins: dict[str, str] = {}
    for entry in members:
        name = entry.get('name')
        sha = entry.get('sha256')
        if not isinstance(name, str) or not isinstance(sha, str) or not _SHA256_RE.fullmatch(sha) or entry.get('status') == 'BLOCKED':
            raise _fail(ERROR_WEIGHTS_UNPINNED, f'sha256 not pinned for {name}')
        pins[name] = sha
    return pins


def _script_pairs(script_text: str, policy: TokenizationPolicy) -> list[tuple[str, str]]:
    """Pair each raw script token with its normalized token; fail closed if this differs from tokenize_script of the whole text."""
    pairs = [(raw, token) for raw in script_text.split() for token in tokenize_script(raw, policy)]
    if tuple(token for _, token in pairs) != tokenize_script(script_text, policy):
        raise _fail(ERROR_TOKENIZATION_INCONSISTENT, 'script tokenization is not stable per token')
    return pairs


def _ms(seconds: object) -> int:
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds):
        raise _fail(ERROR_MODEL_OUTPUT_INVALID, 'model returned a non-finite or non-numeric time')
    return int(round(seconds * 1000))


@dataclass(frozen=True)
class AlignmentReport:
    """Counts of the last align call; unmatched_ratio = (missing script words + extra model words) / (script words + model words)."""

    script_token_count: int
    transcript_word_count: int
    matched_count: int
    missing_script_indices: tuple[int, ...]
    extra_transcript_indices: tuple[int, ...]
    unmatched_ratio: float


@dataclass(frozen=True)
class _Heard:
    normalized: str | None
    start_ms: int
    end_ms: int
    probability: float


def _heard_words(segments: list, policy: TokenizationPolicy) -> list[_Heard]:
    """Flatten model words; punctuation-only words are dropped and a word that splits into several tokens never matches."""
    heard: list[_Heard] = []
    for segment in segments:
        for item in getattr(segment, 'words', None) or ():
            tokens = tokenize_script(item.word, policy)
            if not tokens:
                continue
            probability = item.probability
            if isinstance(probability, bool) or not isinstance(probability, (int, float)) or not math.isfinite(probability):
                raise _fail(ERROR_MODEL_OUTPUT_INVALID, 'model returned an invalid word probability')
            heard.append(_Heard(tokens[0] if len(tokens) == 1 else None, _ms(item.start), _ms(item.end), min(max(float(probability), 0.0), 1.0)))
    return heard


def _segment_boundaries(segments: list, duration_ms: int) -> tuple[dict[str, int], ...]:
    boundaries: list[dict[str, int]] = []
    previous_end = 0
    for segment in segments:
        start = max(_ms(segment.start), previous_end)
        end = min(_ms(segment.end), duration_ms)
        if end > start:
            boundaries.append({'start_ms': start, 'end_ms': end})
            previous_end = end
    return tuple(boundaries)


def _matching_pairs(expected: list[str], heard: list[_Heard]) -> list[tuple[int, int]]:
    blocks = difflib.SequenceMatcher(None, expected, [item.normalized for item in heard], autojunk=False).get_matching_blocks()
    return [(i + k, j + k) for i, j, size in blocks for k in range(size)]


def _default_factory(model_dir: str, device: str, compute_type: str) -> object:
    from faster_whisper import WhisperModel

    return WhisperModel(model_dir, device=device, compute_type=compute_type, local_files_only=True)


def _library_version() -> str:
    try:
        return importlib.metadata.version('faster-whisper')
    except importlib.metadata.PackageNotFoundError:
        return 'unknown'


class RealWhisperAligner:
    """AlignerPort over a local faster_whisper model; weights are verified once and the model is loaded once."""

    def __init__(
        self,
        config: WhisperAlignerConfig,
        *,
        model_factory: Callable[[str, str, str], object] | None = None,
        known_secrets: tuple[str, ...] = (),
    ) -> None:
        if not isinstance(config, WhisperAlignerConfig):
            raise TypeError('config must be WhisperAlignerConfig')
        if isinstance(known_secrets, str):
            raise TypeError('known_secrets must not be str')
        self._config = config
        self._factory = model_factory or _default_factory
        self._known_secrets = (*known_secrets, str(config.model_dir))
        self._model: object | None = None
        self._model_hash = ''
        self.last_report: AlignmentReport | None = None

    def _runtime_error(self, exc: Exception) -> AlignerError:
        return _fail(ERROR_RUNTIME, f'{type(exc).__name__}: {exc}', self._known_secrets)

    def _verify_model(self) -> str:
        config = self._config
        if _inside_git_tree(config.model_dir):
            raise _fail(ERROR_WEIGHTS_IN_GIT_TREE, 'model directory is inside a Git tree')
        pins = _pinned_group(config.lock_path, config.model_group)
        if config.model_hash_file not in pins:
            raise _fail(ERROR_WEIGHTS_UNPINNED, f'sha256 not pinned for {config.model_hash_file}')
        for name, expected in pins.items():
            path = config.model_dir / name
            if not path.is_file():
                raise _fail(ERROR_WEIGHTS_MISSING, f'model file missing: {name}')
            try:
                actual = _file_sha256(path)
            except OSError:
                raise _fail(ERROR_WEIGHTS_MISSING, f'model file unreadable: {name}') from None
            if actual != expected:
                raise _fail(ERROR_WEIGHTS_SHA256_MISMATCH, f'sha256 mismatch for {name}')
        return pins[config.model_hash_file]

    def _load(self) -> object:
        if self._model is None:
            model_hash = self._verify_model()
            try:
                model = self._factory(str(self._config.model_dir), self._config.device, self._config.compute_type)
            except Exception as exc:
                raise self._runtime_error(exc) from None
            self._model_hash = model_hash
            self._model = model
        return self._model

    def _verify_voice(self, request: AlignmentRequest) -> Path:
        try:
            path = Path(self._config.resolve_audio(request.voice_artifact_ref))
            actual = _file_sha256(path)
        except Exception:
            raise _fail(ERROR_VOICE_UNAVAILABLE, 'voice artifact unavailable') from None
        if actual != request.voice_hash:
            raise _fail(ERROR_VOICE_HASH_MISMATCH, 'voice artifact hash differs from request')
        return path

    def align(self, request: AlignmentRequest) -> AlignmentResult:
        if not isinstance(request, AlignmentRequest):
            raise TypeError('request must be AlignmentRequest')
        config = self._config
        policy = config.tokenization_policy
        audio = self._verify_voice(request)
        model = self._load()
        try:
            segments, info = model.transcribe(
                str(audio), language=config.language, word_timestamps=True, vad_filter=False, condition_on_previous_text=False,
            )
            segments = list(segments)
            heard = _heard_words(segments, policy)
            boundaries = _segment_boundaries(segments, request.voice_duration_ms)
            pairs = _script_pairs(request.script_text, policy)
        except AlignerError:
            raise
        except Exception as exc:
            raise self._runtime_error(exc) from None
        expected = [token for _, token in pairs]
        words: list[dict[str, object]] = []
        timed_script: set[int] = set()
        timed_heard: set[int] = set()
        previous_end = 0
        for i, j in _matching_pairs(expected, heard):
            item = heard[j]
            start = max(item.start_ms, previous_end)
            end = min(item.end_ms, request.voice_duration_ms)
            if end <= start:
                continue  # no usable interval from the model: the word stays unmatched
            words.append({'start_ms': start, 'end_ms': end, 'text': pairs[i][0], 'normalized_text': expected[i], 'confidence': item.probability})
            timed_script.add(i)
            timed_heard.add(j)
            previous_end = end
        missing = tuple(i for i in range(len(expected)) if i not in timed_script)
        extra = tuple(j for j in range(len(heard)) if j not in timed_heard)
        total = len(expected) + len(heard)
        ratio = (len(missing) + len(extra)) / total if total else 1.0
        self.last_report = AlignmentReport(len(expected), len(heard), len(words), missing, extra, ratio)
        if not words:
            raise _fail(ERROR_NO_ALIGNED_WORDS, 'no script word could be aligned to a model word')
        if ratio > config.max_unmatched_word_ratio:
            raise _fail(ERROR_UNMATCHED_RATIO_EXCEEDED, f'unmatched word ratio {ratio:.4f} exceeds {config.max_unmatched_word_ratio}')
        language = getattr(info, 'language', None)
        return AlignmentResult(
            words=tuple(words),
            segment_boundaries=boundaries,
            voice_locale_reported=language if isinstance(language, str) and language else config.language,
            aligner_revision=f'faster-whisper=={_library_version()};model-sha256={self._model_hash}',
        )


__all__ = ('AlignmentReport', 'RealWhisperAligner', 'WhisperAlignerConfig')
