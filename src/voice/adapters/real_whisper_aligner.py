"""Real AlignerPort: local faster_whisper word timestamps matched to the script text (CT-SUB-001).

Word times come from the model (Whisper); an edge that sits in a pause is adjusted to the Silero VAD speech runs of the same audio. Nothing is interpolated or spread evenly: a script word without model or VAD evidence stays unmatched and gets no time. One exception (ADAPT-E-FIX3): a script group and a heard group that write the same whole number differently (words vs digits, several tokens vs one token) share the heard span, split by character count and counted in split_word_count. A second exception (ADAPT-E-FIX4): Whisper pieces that rejoin into exactly one script token (long + -term, 9 + -year + -old) take the span of the pieces, and a cluster of script words and Whisper pieces that read the same value and unit (dollars, cents, percent, decimals, up to trillion) shares the heard span by character count, counted in split_word_count. A third exception (ADAPT-E-FIX6): a model word that ends where the word before it ends (Whisper gave it no time of its own, e.g. a zero-length word) shares the span of the word before it by character count, counted in split_word_count. A fourth exception (ADAPT-E-FIX7): a run of at most four script words with no model word of their own, between two matched words, takes the model words left unused between those two words, or, when there are none, joins the span of the matched word next to it; the shared span is split by character count and counted in split_word_count and split_group_count. Last (ADAPT-E-FIX8): a run of script words that still has no time after every rule above, at most 5% of the script words in all, takes the span between the two timed words around it (or, with no room there, a share of the span of the word next to it), split by character count, with confidence 0.0; these words still count as unmatched in unmatched_ratio and are counted in split_word_count and split_group_count. Before all these rules (ADAPT-E-FIX9): when the first pass fails the coverage or the ratio gate because Whisper skipped a whole clause (a run of script words with no model word), the audio around that run (RELISTEN_CONTEXT matched words on each side, at most RELISTEN_MAX_MS long) is transcribed again with clip_timestamps, at most RELISTEN_MAX_WINDOWS times, and the model words of the window replace the first-pass words there only when they cover more script words; a job that passes both gates in the first pass is never transcribed again, and a failed second pass keeps the first pass. The max_unmatched_word_ratio cap applies to split_group_count, one per shared heard span (ADAPT-E-FIX5): the two ends of a group are model times, only the inner word edges are shared.
"""
from __future__ import annotations

import difflib
import hashlib
import importlib.metadata
import json
import math
import re
import threading
import unicodedata
import wave
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from fractions import Fraction
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
    """Counts of the last align call; unmatched_ratio = (missing script words + extra model words) / (script words + model words); split_word_count = script words that took a share of one heard span (ADAPT-E-FIX3 number groups, ADAPT-E-FIX4 amount clusters); split_group_count = shared heard spans that were split (ADAPT-E-FIX5), the count the max_unmatched_word_ratio cap applies to. relisten_count = clause windows transcribed again whose model words were kept (ADAPT-E-FIX9)."""

    script_token_count: int
    transcript_word_count: int
    matched_count: int
    missing_script_indices: tuple[int, ...]
    extra_transcript_indices: tuple[int, ...]
    unmatched_ratio: float
    split_word_count: int = 0
    split_group_count: int = 0
    relisten_count: int = 0


@dataclass(frozen=True)
class _Heard:
    normalized: str | None
    start_ms: int
    end_ms: int
    probability: float
    raw: str = ''


@dataclass(frozen=True)
class _Slot:
    script_index: int
    first: int
    last: int
    start_ms: int
    end_ms: int
    rescued: bool


def _heard_words(segments: list, policy: TokenizationPolicy) -> list[_Heard]:
    """Flatten model words; punctuation-only words are dropped (ADAPT-E-FIX4: a '%' piece glued to the word before it joins that word's raw text and end) and a word that splits into several tokens never matches."""
    heard: list[_Heard] = []
    for segment in segments:
        for item in getattr(segment, 'words', None) or ():
            tokens = tokenize_script(item.word, policy)
            if not tokens:
                if heard and '%' in item.word and not item.word[:1].isspace():
                    last = heard[-1]
                    heard[-1] = _Heard(last.normalized, last.start_ms, max(last.end_ms, _ms(item.end)), last.probability, last.raw + item.word)
                continue
            probability = item.probability
            if isinstance(probability, bool) or not isinstance(probability, (int, float)) or not math.isfinite(probability):
                raise _fail(ERROR_MODEL_OUTPUT_INVALID, 'model returned an invalid word probability')
            heard.append(_Heard(tokens[0] if len(tokens) == 1 else None, _ms(item.start), _ms(item.end), min(max(float(probability), 0.0), 1.0), item.word))
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
_SCALE_WORDS = ('hundred', 'thousand', 'million', 'billion', 'trillion')
_SMALL = ('zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen')
_TENS = ('', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety')
_SCALES = ((10 ** 12, 'trillion'), (10 ** 9, 'billion'), (10 ** 6, 'million'), (1000, 'thousand'), (100, 'hundred'))


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


_MULTIPLIERS = {'thousand': 10 ** 3, 'million': 10 ** 6, 'billion': 10 ** 9, 'trillion': 10 ** 12}
_UNITS = {'$': '$', 'dollar': '$', 'dollars': '$', 'cent': 'c', 'cents': 'c', '%': '%', 'percent': '%'}
_AMOUNT_WORDS = frozenset((*_SMALL, *_TENS[2:], *_SCALE_WORDS, *_UNITS, 'point', 'a', 'and'))
_ATOM_RE = re.compile(r'[0-9][0-9,.]*[0-9]|[0-9]|[a-z]+|[^0-9a-z]')
_DECIMAL_RE = re.compile(r'(?:0|[1-9][0-9]{0,2}(?:,[0-9]{3})+|[1-9][0-9]*)(?:[.][0-9]+)?')


def _atoms(text: str) -> list[str]:
    """ADAPT-E-FIX4: letter runs, number runs and symbols of text; punctuation (except '%'), spaces and control characters are dropped."""
    return [x for x in _ATOM_RE.findall(text.casefold()) if x == '%' or unicodedata.category(x[0])[0] not in 'PZC']


def _amount_atom(atom: str) -> bool:
    return atom[0].isdigit() or atom in _AMOUNT_WORDS


def _amount_token(token: str) -> bool:
    atoms = _atoms(token)
    return bool(atoms) and all(_amount_atom(x) for x in atoms)


def _amount(text: str) -> tuple[Fraction, str | None] | None:
    """ADAPT-E-FIX4: (value, unit) of one amount written in digits or English words, unit '$', '%' or None (cents become dollars); None when text is not one readable amount."""
    a = _atoms(text)
    head = bool(a) and a[0] == '$'
    tail = bool(a) and a[-1] in _UNITS
    if head and tail:
        return None
    unit = None
    if head:
        unit, a = '$', a[1:]
    elif tail:
        unit, a = _UNITS[a[-1]], a[:-1]
    scale = 1
    if len(a) > 1 and a[-1] in _MULTIPLIERS and ('point' in a or a[0][0].isdigit()):
        scale, a = _MULTIPLIERS[a[-1]], a[:-1]
    if len(a) == 1 and _DECIMAL_RE.fullmatch(a[0]):
        value = Fraction(a[0].replace(',', ''))
    else:
        k = a.index('point') if 'point' in a else len(a)
        whole, frac = a[:k], a[k + 1:]
        if len(whole) > 1:
            if whole[0] == 'a' and whole[1] in _SCALE_WORDS:
                whole = ['one', *whole[1:]]
            whole = [x for n, x in enumerate(whole) if not (x == 'and' and 0 < n < len(whole) - 1 and whole[n - 1] in _SCALE_WORDS)]
        total = part = 0
        for x in whole:
            if x in _SMALL:
                part += _SMALL.index(x)
            elif x in _TENS[2:]:
                part += 10 * _TENS.index(x)
            elif x == 'hundred':
                part *= 100
            elif x in _MULTIPLIERS:
                total, part = total + part * _MULTIPLIERS[x], 0
            else:
                return None
        if not whole or _cardinal(total + part) != whole:
            return None
        value = Fraction(total + part)
        if k < len(a):
            if not frac or any(x not in _SMALL[:10] for x in frac):
                return None
            value += Fraction(int(''.join(str(_SMALL.index(x)) for x in frac)), 10 ** len(frac))
    if unit == 'c':
        value, unit = value / 100, '$'
    return value * scale, unit


def _key(token: str) -> tuple:
    """ADAPT-E-FIX4: atoms of a token where every run of amount atoms is replaced by its (value, unit) when readable."""
    key: list = []
    run: list[str] = []
    for atom in [*_atoms(token), None]:
        if atom is not None and _amount_atom(atom):
            run.append(atom)
            continue
        if run:
            amount = _amount(' '.join(run))
            key.extend([amount] if amount is not None else run)
            run = []
        if atom is not None:
            key.append(atom)
    return tuple(key)


def _rejoined(tokens: Sequence[str], items: Sequence[_Heard], policy: TokenizationPolicy) -> list[tuple[int, int]] | None:
    """ADAPT-E-FIX4: for each script token the shortest run of consecutive heard items whose joined raw text tokenizes to exactly that token (same _key); (first, last) item offsets per token, or None when a token has no such run or items are left over."""
    spans: list[tuple[int, int]] = []
    j = 0
    for token in tokens:
        want = [_key(token)]
        for k in range(j + 1, len(items) + 1):
            if [_key(x) for x in tokenize_script(''.join(i.raw for i in items[j:k]), policy)] == want:
                spans.append((j, k - 1))
                j = k
                break
        else:
            return None
    return spans if j == len(items) else None


FALLBACK_MAX_SCRIPT = 4
FALLBACK_MAX_HEARD = 6


def _cover_gaps(matches: list[tuple[int, int, int, int]], expected: list[str], heard: list[_Heard]) -> list[tuple[int, int, int, int]]:
    """ADAPT-E-FIX7: a run of at most FALLBACK_MAX_SCRIPT unmatched script words without an amount word, next to at least one matched word, takes the unused heard words between its neighbours (at most FALLBACK_MAX_HEARD, none with a digit or an amount word), or, when no heard word is left, joins the span of the matched word after it (before it at the end of the script). The model times stay the only time source; align() splits the shared span by character count and counts the group."""
    found = list(matches)
    covered = {n for m in found for n in range(m[0], m[1] + 1)}
    n = 0
    while n < len(expected):
        if n in covered:
            n += 1
            continue
        s1 = n
        while n < len(expected) and n not in covered:
            n += 1
        s2 = n
        if s2 - s1 > FALLBACK_MAX_SCRIPT or any(_amount_token(expected[k]) for k in range(s1, s2)):
            continue
        before = next((m for m in found if m[1] == s1 - 1), None)
        after = next((m for m in found if m[0] == s2), None)
        if before is None and after is None:
            continue
        used = {j for m in found for j in range(m[2], m[3] + 1)}
        free = [j for j in range(before[3] + 1 if before is not None else 0, after[2] if after is not None else len(heard)) if j not in used]
        if free:
            if len(free) > FALLBACK_MAX_HEARD or any(any(c.isdigit() for c in heard[j].raw) or (heard[j].normalized is not None and _amount_token(heard[j].normalized)) for j in free):
                continue
            found.append((s1, s2 - 1, free[0], free[-1]))
        elif after is not None:
            found[found.index(after)] = (s1, after[1], after[2], after[3])
        else:
            found[found.index(before)] = (before[0], s2 - 1, before[2], before[3])
    return sorted(found)


def _match_script(expected: list[str], heard: list[_Heard], raws: list[str], policy: TokenizationPolicy) -> list[tuple[int, int, int, int]]:
    """Return (first script index, last script index, first heard index, last heard index); equal blocks match word by word, a replace block only as a split compound, a same-size respelling, (ADAPT-E-FIX3) one whole number written as digits on one side and as words on the other, or (ADAPT-E-FIX4) Whisper pieces that rejoin into the script tokens; a run of adjacent amount words and pieces that read the same value and unit becomes one group."""
    names = [item.normalized for item in heard]
    matches: list[tuple[int, int, int, int]] = []
    units: list[tuple[int, int, int, int, str]] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, expected, names, autojunk=False).get_opcodes():
        if tag == 'equal':
            matches.extend((i1 + k, i1 + k, j1 + k, j1 + k) for k in range(i2 - i1))
            units.extend((i1 + k, i1 + k + 1, j1 + k, j1 + k + 1, 'pair') for k in range(i2 - i1))
            continue
        before = len(matches)
        if tag == 'replace' and None not in names[j1:j2]:
            if i2 - i1 == 1 and j2 - j1 > 1 and ''.join(names[j1:j2]) == expected[i1]:
                matches.append((i1, i1, j1, j2 - 1))
            elif i2 - i1 == j2 - j1:
                matches.extend((i1 + k, i1 + k, j1 + k, j1 + k) for k in range(i2 - i1))
            elif _same_number(names[j1:j2], expected[i1:i2]):
                matches.append((i1, i2 - 1, j1, j1))
            elif _same_number(expected[i1:i2], names[j1:j2]):
                matches.append((i1, i1, j1, j2 - 1))
            elif (g := _rejoined(expected[i1:i2], heard[j1:j2], policy)) is not None:
                matches.extend((i1 + k, i1 + k, j1 + a, j1 + b) for k, (a, b) in enumerate(g))
        units.append((i1, i2, j1, j2, 'open' if len(matches) == before else 'done'))

    def joinable(unit: tuple[int, int, int, int, str]) -> bool:
        i1, i2, j1, j2, kind = unit
        return not (kind == 'pair' and expected[i1] in ('a', 'and')) and None not in names[j1:j2] and all(_amount_token(t) for t in (*expected[i1:i2], *names[j1:j2]))

    k = 0
    while k < len(units):
        end = k
        while end < len(units) and joinable(units[end]):
            end += 1
        run, k = units[k:end], max(end, k + 1)
        if not any(u[4] == 'open' for u in run):
            continue
        s1, h1, s2, h2 = run[0][0], run[0][2], run[-1][1], run[-1][3]
        if s1 < s2 and h1 < h2 and heard[h2 - 1].end_ms - heard[h1].start_ms >= s2 - s1:
            want = _amount(' '.join(raws[s1:s2]))
            if want is not None and want == _amount(''.join(item.raw for item in heard[h1:h2])):
                matches = [m for m in matches if not s1 <= m[0] < s2]
                matches.append((s1, s2 - 1, h1, h2 - 1))
    return _cover_gaps(sorted(matches), expected, heard)


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


FILL_MIN_MS = 40
FILL_MAX_RATIO = 0.05


def _fill_stragglers(words: list[dict[str, object]], indices: list[int], pairs: list[tuple[str, str]], expected: list[str], timed: set[int], cap_ratio: float) -> tuple[int, int]:
    """ADAPT-E-FIX8: script words still without a time after every other rule, at most int(min(cap_ratio, FILL_MAX_RATIO) * script words) in all, take the span between the two timed words around their run (confidence 0.0, still counted as unmatched); with less than FILL_MIN_MS per word between the neighbours they share the span of the word before, else of the word after, by character count. Returns (words filled, runs filled)."""
    present = set(indices)
    runs: list[tuple[int, int]] = []
    n = 0
    while n < len(expected):
        if n in present:
            n += 1
            continue
        s1 = n
        while n < len(expected) and n not in present:
            n += 1
        runs.append((s1, n))
    if not runs or sum(s2 - s1 for s1, s2 in runs) > int(min(cap_ratio, FILL_MAX_RATIO) * len(expected)):
        return 0, 0
    order = list(indices)
    filled = groups = 0
    for s1, s2 in reversed(runs):
        count = s2 - s1
        pos = sum(1 for x in order if x < s1)
        before = words[pos - 1] if pos > 0 else None
        after = words[pos] if pos < len(words) else None
        if before is None and after is None:
            continue
        lo = before['end_ms'] if before is not None else after['start_ms']
        hi = after['start_ms'] if after is not None else before['end_ms']
        w = [len(expected[k]) for k in range(s1, s2)]
        side = 'gap'
        if hi - lo < FILL_MIN_MS * count:
            if before is not None and before['end_ms'] - before['start_ms'] >= FILL_MIN_MS * (count + 1):
                side = 'before'
            elif after is not None and after['end_ms'] - after['start_ms'] >= FILL_MIN_MS * (count + 1):
                side = 'after'
            else:
                continue
        if side == 'before':
            start, end, weights = before['start_ms'], before['end_ms'], [len(expected[order[pos - 1]]), *w]
        elif side == 'after':
            start, end, weights = after['start_ms'], after['end_ms'], [*w, len(expected[order[pos]])]
        else:
            start, end, weights = lo, hi, w
        b = [start + (end - start) * sum(weights[:k]) // sum(weights) for k in range(len(weights))] + [end]
        if not all(b[k] < b[k + 1] for k in range(len(weights))):
            continue
        marks = b
        if side == 'before':
            before['end_ms'], marks = b[1], b[1:]
        elif side == 'after':
            after['start_ms'], marks = b[count], b[:count + 1]
        for k in range(count):
            words.insert(pos + k, {'start_ms': marks[k], 'end_ms': marks[k + 1], 'text': pairs[s1 + k][0], 'normalized_text': expected[s1 + k], 'confidence': 0.0})
        order[pos:pos] = range(s1, s2)
        timed.update(range(s1, s2))
        filled += count
        groups += 1
    return filled, groups


RELISTEN_CONTEXT = 2
RELISTEN_MAX_WINDOWS = 3
RELISTEN_MAX_MS = 28000


def _covered_count(matches: Sequence[tuple[int, int, int, int]]) -> int:
    """ADAPT-E-FIX9: number of script words that have a model word."""
    return len({n for m in matches for n in range(m[0], m[1] + 1)})


def _uncovered_runs(matches: Sequence[tuple[int, int, int, int]], count: int) -> list[tuple[int, int]]:
    """ADAPT-E-FIX9: (first, end) script index runs, end exclusive, that no match covers."""
    covered = {n for m in matches for n in range(m[0], m[1] + 1)}
    runs: list[tuple[int, int]] = []
    n = 0
    while n < count:
        if n in covered:
            n += 1
            continue
        s1 = n
        while n < count and n not in covered:
            n += 1
        runs.append((s1, n))
    return runs


def _relisten_window(matches: Sequence[tuple[int, int, int, int]], heard: list[_Heard], run: tuple[int, int], duration_ms: int) -> tuple[int, int, int, int] | None:
    """ADAPT-E-FIX9: (start_ms, end_ms, first, end_index) of the audio around an uncovered run: from the heard start of the RELISTEN_CONTEXT-th match before the run (0 when there are fewer) to the heard end of the RELISTEN_CONTEXT-th match after it (the end of the voice when there are fewer); heard[first:end_index] is what a second pass replaces. None when the run is empty or the window is longer than RELISTEN_MAX_MS."""
    s1, s2 = run
    if s2 <= s1:
        return None
    ordered = sorted(matches)
    before = [m for m in ordered if m[1] < s1]
    after = [m for m in ordered if m[0] >= s2]
    if len(before) >= RELISTEN_CONTEXT:
        first = before[-RELISTEN_CONTEXT][2]
        start = heard[first].start_ms
    else:
        first, start = 0, 0
    if len(after) >= RELISTEN_CONTEXT:
        end_index = after[RELISTEN_CONTEXT - 1][3] + 1
        end = heard[end_index - 1].end_ms
    else:
        end_index, end = len(heard), duration_ms
    end = min(end, duration_ms)
    if end <= start or end - start > RELISTEN_MAX_MS or first > end_index:
        return None
    return start, end, first, end_index


def _short_of_gates(matches: Sequence[tuple[int, int, int, int]], script_count: int, heard_count: int, cap_ratio: float) -> bool:
    """ADAPT-E-FIX9: True when the matches leave more script words without a model word than the fill rule may take (int(min(cap_ratio, FILL_MAX_RATIO) * script_count)), or when (those words + unmatched model words) / (script words + model words) is above cap_ratio."""
    missing = script_count - _covered_count(matches)
    used = {j for m in matches for j in range(m[2], m[3] + 1)}
    extra = heard_count - len(used)
    total = script_count + heard_count
    return missing > int(min(cap_ratio, FILL_MAX_RATIO) * script_count) or (total > 0 and (missing + extra) / total > cap_ratio)


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
        self._load_lock = threading.Lock()
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
            with self._load_lock:
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

    def _relisten(self, model: object, audio: Path, expected: list[str], heard: list[_Heard], raws: list[str], duration_ms: int) -> tuple[list[_Heard], int]:
        """ADAPT-E-FIX9: only when the first-pass match is short of the gates, transcribe the window around the longest untried uncovered run again (at most RELISTEN_MAX_WINDOWS calls); the model words of the second pass whose midpoint lies in the window replace heard[first:end_index], kept only when more script words are covered; any error of a second pass keeps what was heard before. Returns (heard, windows kept)."""
        config = self._config
        policy = config.tokenization_policy
        cap = config.max_unmatched_word_ratio
        matches = _match_script(expected, heard, raws, policy)
        if not _short_of_gates(matches, len(expected), len(heard), cap):
            return heard, 0
        tried: set[tuple[int, int]] = set()
        calls = kept = 0
        while calls < RELISTEN_MAX_WINDOWS:
            runs = [run for run in _uncovered_runs(matches, len(expected)) if run not in tried]
            if not runs:
                break
            run = max(runs, key=lambda item: (item[1] - item[0], -item[0]))
            tried.add(run)
            window = _relisten_window(matches, heard, run, duration_ms)
            if window is None:
                continue
            start, end, first, end_index = window
            calls += 1
            try:
                segments, _ = model.transcribe(
                    str(audio), language=config.language, word_timestamps=True, vad_filter=False, condition_on_previous_text=False,
                    clip_timestamps=[start / 1000, end / 1000],
                )
                again = [item for item in _heard_words(list(segments), policy) if start <= (item.start_ms + item.end_ms) / 2 <= end]
                candidate = [*heard[:first], *again, *heard[end_index:]]
                found = _match_script(expected, candidate, raws, policy)
            except Exception:
                continue
            if _covered_count(found) > _covered_count(matches):
                heard, matches, kept = candidate, found, kept + 1
                if not _short_of_gates(matches, len(expected), len(heard), cap):
                    break
        return heard, kept

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
        heard, relistened = self._relisten(model, audio, expected, heard, [raw for raw, _ in pairs], duration)
        slots: list[_Slot] = []
        previous_end = 0
        split_count = 0
        split_groups = 0
        for i, i_last, first, last in _match_script(expected, heard, [raw for raw, _ in pairs], policy):
            start = max(heard[first].start_ms, previous_end)
            end = min(heard[last].end_ms, duration)
            if i_last > i:
                w = [len(expected[n]) for n in range(i, i_last + 1)]
                b = [start + (end - start) * sum(w[:n]) // sum(w) for n in range(len(w))] + [end]
                if all(b[n] < b[n + 1] for n in range(len(w))):
                    slots.extend(_Slot(i + n, first, last, b[n], b[n + 1], False) for n in range(len(w)))
                    split_count += len(w)
                    split_groups += 1
                    previous_end = end
                continue
            if end <= previous_end and slots and not slots[-1].rescued:  # ADAPT-E-FIX6: a word with no time of its own shares the span of the word before it
                prev = slots[-1]
                own, mine = len(expected[prev.script_index]), len(expected[i])
                cut = prev.start_ms + (prev.end_ms - prev.start_ms) * own // (own + mine)
                if prev.start_ms < cut < prev.end_ms:
                    shared = any(s.first == prev.first and s.last == prev.last for s in slots[:-1])
                    slots[-1] = _Slot(prev.script_index, prev.first, prev.last, prev.start_ms, cut, False)
                    slots.append(_Slot(i, first, last, cut, prev.end_ms, False))
                    split_count += 1 if shared else 2
                    split_groups += 1
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
        filled, fill_runs = _fill_stragglers(words, [slot.script_index for slot in slots], pairs, expected, timed_script, config.max_unmatched_word_ratio)
        split_count += filled
        split_groups += fill_runs
        missing = tuple(i for i in range(len(expected)) if i not in timed_script)
        extra = tuple(j for j in range(len(heard)) if j not in timed_heard)
        total = len(expected) + len(heard)
        ratio = (len(missing) + filled + len(extra)) / total if total else 1.0
        self.last_report = AlignmentReport(len(expected), len(heard), len(words), missing, extra, ratio, split_count, split_groups, relistened)
        if not words:
            raise _fail(ERROR_NO_ALIGNED_WORDS, 'no script word could be aligned to a model word')
        if ratio > config.max_unmatched_word_ratio:
            raise _fail(ERROR_UNMATCHED_RATIO_EXCEEDED, f'unmatched word ratio {ratio:.4f} exceeds {config.max_unmatched_word_ratio}')
        if split_groups / len(expected) > config.max_unmatched_word_ratio:
            raise _fail(ERROR_SPLIT_RATIO_EXCEEDED, f'split group ratio {split_groups / len(expected):.4f} exceeds {config.max_unmatched_word_ratio} ({split_count} split words)')
        language =getattr(info, 'language', None)
        return AlignmentResult(
            words=tuple(words),
            segment_boundaries=boundaries,
            voice_locale_reported=language if isinstance(language, str) and language else config.language,
            aligner_revision=f'faster-whisper=={_library_version()};model-sha256={self._model_hash}',
        )


__all__ = ('AlignmentReport', 'RealWhisperAligner', 'WhisperAlignerConfig')
