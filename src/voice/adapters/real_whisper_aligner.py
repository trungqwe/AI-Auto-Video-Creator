"""Real AlignerPort: local faster_whisper word timestamps matched to the script text (CT-SUB-001).

Word times come from the model (Whisper); an edge that sits in a pause is adjusted to the Silero VAD speech runs of the same audio. Nothing is interpolated or spread evenly: a script word without model or VAD evidence stays unmatched and gets no time. One exception (ADAPT-E-FIX3): a script group and a heard group that write the same whole number differently (words vs digits, several tokens vs one token) share the heard span, split by character count and counted in split_word_count under the max_unmatched_word_ratio cap.
"""
from __future__ import annotations

import difflib
import hashlib
import importlib.metadata
import json
import math
import re
import wave
from collections.abc import Callable, Sequence
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
ERROR_SPLIT_RATIO_EXCEEDED = 'alignment_split_ratio_exceeded'
ERROR_RUNTIME = 'aligner_runtime_error'
_SHA256_RE = re.compile(r'[0-9a-f]{64}')
ARTIFACT_REF_RE = re.compile(r'voice-artifact-[0-9a-f]{64}')
SPEECH_SAMPLE_RATE = 16000
_SAMPLES_PER_MS = 16


@dataclass(frozen=True, kw_only=True)
class WhisperAlignerConfig:
    model_dir: Path
    lock_path: Path
    resolve_audio: Callable[[str], Path] | None = None
    voice_root: Path | None = None
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
        if (self.resolve_audio is None) == (self.voice_root is None):
            raise ValueError('exactly one of resolve_audio and voice_root is required')
        if self.resolve_audio is not None and not callable(self.resolve_audio):
            raise ValueError('resolve_audio must be callable')
        if self.voice_root is not None and (not isinstance(self.voice_root, Path) or not self.voice_root.is_absolute()):
            raise ValueError('voice_root must be an absolute Path')
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


def _voice_artifact_path(voice_root: Path, ref: str) -> Path:
    """DQ-13: open exactly <voice root>/voice-artifact-<sha256>; any other name is refused."""
    if not isinstance(ref, str) or ARTIFACT_REF_RE.fullmatch(ref) is None:
        raise ValueError('voice artifact ref is not voice-artifact-<sha256>')
    return voice_root / ref


@dataclass(frozen=True)
class AlignmentReport:
    """Counts of the last align call; unmatched_ratio = (missing script words + extra model words) / (script words + model words); split_word_count = script words that took a share of one heard span (ADAPT-E-FIX3 number groups)."""

    script_token_count: int
    transcript_word_count: int
    matched_count: int
    missing_script_indices: tuple[int, ...]
    extra_transcript_indices: tuple[int, ...]
    unmatched_ratio: float
    split_word_count: int = 0


@dataclass(frozen=True)
class _Heard:
    normalized: str | None
    start_ms: int
    end_ms: int
    probability: float


@dataclass(frozen=True)
class _Slot:
    script_index: int
    first: int
    last: int
    start_ms: int
    end_ms: int
    rescued: bool


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


_NUMBER_RE = re.compile(r'[1-9][0-9]{0,2}(?:,[0-9]{3}){1,3}|[1-9][0-9]{0,11}')
_SCALE_WORDS = ('hundred', 'thousand', 'million', 'billion')
_SMALL = ('zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen')
_TENS = ('', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety')
_SCALES = ((10 ** 9, 'billion'), (10 ** 6, 'million'), (1000, 'thousand'), (100, 'hundred'))


def _cardinal(value: int) -> list[str]:
    """English cardinal words of 1 <= value <= 999999999999, one word per element, no 'and', no hyphen."""
    if value < 20:
        return [_SMALL[value]]
    if value < 100:
        return [_TENS[value // 10], *(_cardinal(value % 10) if value % 10 else ())]
    for size, name in _SCALES:
        if value >= size:
            return [*_cardinal(value // size), name, *(_cardinal(value % size) if value % size else ())]
    raise ValueError('value out of range')


def _same_number(digits: Sequence[str], words: Sequence[str]) -> bool:
    """ADAPT-E-FIX3: True when one digit token and a group of two or more tokens write the same whole number (156 = one hundred and fifty-six, 2026 = two thousand twenty-six = twenty twenty-six, 100 = a hundred)."""
    if len(digits) != 1 or len(words) < 2 or _NUMBER_RE.fullmatch(digits[0]) is None:
        return False
    value = int(digits[0].replace(',', ''))
    tokens = [part for word in words for part in word.split('-')]
    if tokens[0] == 'a' and tokens[1] in _SCALE_WORDS:
        tokens[0] = 'one'
    tokens = [t for k, t in enumerate(tokens) if not (t == 'and' and 0 < k < len(tokens) - 1 and tokens[k - 1] in _SCALE_WORDS)]
    forms = [_cardinal(value)]
    if 1000 <= value <= 9999 and value % 100 >= 10:
        forms.append(_cardinal(value // 100) + _cardinal(value % 100))
    return tokens in forms


def _match_script(expected: list[str], heard: list[_Heard]) -> list[tuple[int, int, int, int]]:
    """Return (first script index, last script index, first heard index, last heard index); equal blocks match word by word, a replace block only as a split compound, a same-size respelling or (ADAPT-E-FIX3 exception) one whole number written as digits on one side and as words on the other."""
    names = [item.normalized for item in heard]
    matches: list[tuple[int, int, int, int]] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, expected, names, autojunk=False).get_opcodes():
        if tag == 'equal':
            matches.extend((i1 + k, i1 + k, j1 + k, j1 + k) for k in range(i2 - i1))
        elif tag == 'replace' and None not in names[j1:j2]:
            if i2 - i1 == 1 and j2 - j1 > 1 and ''.join(names[j1:j2]) == expected[i1]:
                matches.append((i1, i1, j1, j2 - 1))
            elif i2 - i1 == j2 - j1:
                matches.extend((i1 + k, i1 + k, j1 + k, j1 + k) for k in range(i2 - i1))
            elif _same_number(names[j1:j2], expected[i1:i2]):
                matches.append((i1, i2 - 1, j1, j1))
            elif _same_number(expected[i1:i2], names[j1:j2]):
                matches.append((i1, i1, j1, j2 - 1))
    return matches


def _run_at_start(runs: Sequence[tuple[int, int]], ms: int) -> tuple[int, int] | None:
    return next((run for run in runs if run[0] <= ms < run[1]), None)


def _run_at_end(runs: Sequence[tuple[int, int]], ms: int) -> tuple[int, int] | None:
    return next((run for run in runs if run[0] < ms <= run[1]), None)


def _refine_edges(start: int, end: int, lo: int, hi: int, runs: Sequence[tuple[int, int]]) -> tuple[int, int]:
    """Move a model edge to the speech run edge only where the model left a gap; lo and hi are the neighbour bounds. An empty result keeps the model pair."""
    overlapping = [run for run in runs if run[0] < end and run[1] > start]
    if len(overlapping) > 1:
        on, off = max(overlapping, key=lambda run: min(run[1], end) - max(run[0], start))
        new_start, new_end = max(on, start), min(off, end)
    else:
        new_start, new_end = start, end
        run = _run_at_start(runs, start)
        if run is not None:
            new_start = max(run[0], lo)
        else:
            onsets = [on for on, _ in runs if start <= on < end]
            if onsets:
                new_start = onsets[0]
        run = _run_at_end(runs, end)
        if run is not None:
            new_end = min(run[1], hi)
        else:
            offsets = [off for _, off in runs if start < off <= end]
            if offsets:
                new_end = offsets[-1]
    return (new_start, new_end) if lo <= new_start < new_end <= hi else (start, end)


def _normalize_runs(spans: Sequence[tuple[int, int]], duration_ms: int) -> tuple[tuple[int, int], ...]:
    runs: list[tuple[int, int]] = []
    for span in spans:
        start, end = span
        if isinstance(start, bool) or isinstance(end, bool) or not isinstance(start, int) or not isinstance(end, int):
            raise _fail(ERROR_RUNTIME, 'speech detector returned a non-integer span')
        start, end = max(start, 0), min(end, duration_ms)
        if end > start:
            runs.append((start, end))
    return tuple(sorted(runs))


def _default_speech_detector(audio_path: Path) -> list[tuple[int, int]]:
    """Silero speech runs in ms of the verified WAV (16-bit mono PCM, linearly resampled to 16 kHz); raw edges, no padding."""
    import numpy as np
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    try:
        with wave.open(str(audio_path), 'rb') as wav:
            channels, width, rate = wav.getnchannels(), wav.getsampwidth(), wav.getframerate()
            frames = wav.readframes(wav.getnframes())
    except (wave.Error, EOFError):
        raise _fail(ERROR_RUNTIME, 'voice audio is not a readable PCM WAV') from None
    if channels != 1 or width != 2 or rate <= 0:
        raise _fail(ERROR_RUNTIME, 'voice audio must be 16-bit mono PCM')
    samples = np.frombuffer(frames, dtype='<i2').astype(np.float32) / 32768.0
    if samples.size == 0:
        return []
    if rate != SPEECH_SAMPLE_RATE:
        count = max(1, int(round(samples.size * SPEECH_SAMPLE_RATE / rate)))
        samples = np.interp(np.arange(count) * rate / SPEECH_SAMPLE_RATE, np.arange(samples.size), samples).astype(np.float32)
    spans = get_speech_timestamps(samples, VadOptions(threshold=0.5, min_speech_duration_ms=0, min_silence_duration_ms=100, speech_pad_ms=0))
    return [(int(round(span['start'] / _SAMPLES_PER_MS)), int(round(span['end'] / _SAMPLES_PER_MS))) for span in spans]


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
        speech_detector: Callable[[Path], Sequence[tuple[int, int]]] | None = None,
        known_secrets: tuple[str, ...] = (),
    ) -> None:
        if not isinstance(config, WhisperAlignerConfig):
            raise TypeError('config must be WhisperAlignerConfig')
        if isinstance(known_secrets, str):
            raise TypeError('known_secrets must not be str')
        self._config = config
        self._factory = model_factory or _default_factory
        self._speech_detector = speech_detector or _default_speech_detector
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
            config = self._config
            path = Path(config.resolve_audio(request.voice_artifact_ref)) if config.resolve_audio is not None else _voice_artifact_path(config.voice_root, request.voice_artifact_ref)
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
            runs = _normalize_runs(self._speech_detector(audio), request.voice_duration_ms)
        except AlignerError:
            raise
        except Exception as exc:
            raise self._runtime_error(exc) from None
        expected = [token for _, token in pairs]
        duration = request.voice_duration_ms
        slots: list[_Slot] = []
        previous_end = 0
        split_count = 0
        for i, i_last, first, last in _match_script(expected, heard):
            start = max(heard[first].start_ms, previous_end)
            end = min(heard[last].end_ms, duration)
            if i_last > i:
                w = [len(expected[n]) for n in range(i, i_last + 1)]
                b = [start + (end - start) * sum(w[:n]) // sum(w) for n in range(len(w))] + [end]
                if all(b[n] < b[n + 1] for n in range(len(w))):
                    slots.extend(_Slot(i + n, first, last, b[n], b[n + 1], False) for n in range(len(w)))
                    split_count += len(w)
                    previous_end = end
                continue
            rescued = end <= start
            if rescued:
                run = _run_at_end(runs, end)  # the speech run holding t - 1 ms
                start = max(run[0], previous_end) if run is not None else end
                if start >= end:
                    continue  # zero-length model word without speech evidence: it stays unmatched
            slots.append(_Slot(i, first, last, start, end, rescued))
            previous_end = end
        words: list[dict[str, object]] = []
        timed_script: set[int] = set()
        timed_heard: set[int] = set()
        final_end = 0
        for k, slot in enumerate(slots):
            start, end = slot.start_ms, slot.end_ms
            if runs and not slot.rescued:
                lo = max(slots[k - 1].end_ms, final_end) if k else 0
                hi = slots[k + 1].start_ms if k + 1 < len(slots) else duration
                start, end = _refine_edges(start, end, lo, hi, runs)
            confidence = min(item.probability for item in heard[slot.first:slot.last + 1])
            words.append({'start_ms': start, 'end_ms': end, 'text': pairs[slot.script_index][0], 'normalized_text': expected[slot.script_index], 'confidence': confidence})
            timed_script.add(slot.script_index)
            timed_heard.update(range(slot.first, slot.last + 1))
            final_end = end
        missing = tuple(i for i in range(len(expected)) if i not in timed_script)
        extra = tuple(j for j in range(len(heard)) if j not in timed_heard)
        total = len(expected) + len(heard)
        ratio = (len(missing) + len(extra)) / total if total else 1.0
        self.last_report = AlignmentReport(len(expected), len(heard), len(words), missing, extra, ratio, split_count)
        if not words:
            raise _fail(ERROR_NO_ALIGNED_WORDS, 'no script word could be aligned to a model word')
        if ratio > config.max_unmatched_word_ratio:
            raise _fail(ERROR_UNMATCHED_RATIO_EXCEEDED, f'unmatched word ratio {ratio:.4f} exceeds {config.max_unmatched_word_ratio}')
        if split_count / len(expected) > config.max_unmatched_word_ratio:
            raise _fail(ERROR_SPLIT_RATIO_EXCEEDED, f'split word ratio {split_count / len(expected):.4f} exceeds {config.max_unmatched_word_ratio}')
        language =getattr(info, 'language', None)
        return AlignmentResult(
            words=tuple(words),
            segment_boundaries=boundaries,
            voice_locale_reported=language if isinstance(language, str) and language else config.language,
            aligner_revision=f'faster-whisper=={_library_version()};model-sha256={self._model_hash}',
        )


__all__ = ('AlignmentReport', 'RealWhisperAligner', 'WhisperAlignerConfig')
