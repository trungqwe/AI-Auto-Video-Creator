"""ScriptVersion, claim_mode, disclosure (CT-AI-004) và đầu vào VoiceTrackRequest (CT-TTS-001) phía D; pure domain, không I/O, không clock, không sinh id, không gọi AI; policy và target range là input của caller, không có hằng mặc định ẩn."""
from __future__ import annotations

import copy
import math
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from controlplane.application.idempotency.canonicalization import request_hash
from creative.domain.ref_resolver import RefResolver, ResourceRef

INPUT_NOT_READY = 'INPUT_NOT_READY'
DURATION_OUT_OF_RANGE = 'duration_out_of_range'
SCHEMA_VIOLATION = 'ai_output_schema_violation'
HALLUCINATED_REF = 'hallucinated_ref'
MISSING_SOURCE_REF = 'missing_source_ref'
MISSING_DISCLOSURE = 'missing_disclosure'
LANGUAGE_MISMATCH = 'language_mismatch'
MISSING_REQUIRED = 'missing_required'
WRONG_TYPE = 'wrong_type'
ENUM_VIOLATION = 'enum_violation'
EMPTY_VALUE = 'empty_value'
DUPLICATE_ID = 'duplicate_id'
BINDING_ENTITY = 'VoiceTrackRequest'
CLAIM_SOURCE_BACKED = 'source_backed'
CLAIM_INFERENCE = 'inference'
CLAIM_CREATIVE_HYPOTHESIS = 'creative_hypothesis'
CLAIM_TRANSITION = 'transition'
DISCLOSURE_MODES = (CLAIM_INFERENCE, CLAIM_CREATIVE_HYPOTHESIS)

CLAIM_MODES = (
    CLAIM_SOURCE_BACKED,
    CLAIM_INFERENCE,
    CLAIM_CREATIVE_HYPOTHESIS,
    CLAIM_TRANSITION,
)
VOICE_TRACK_INPUT_TYPES = MappingProxyType({
    'script_version_id': 'string',
    'script_fingerprint': 'sha256',
    'pronunciation_hints': 'array',
})


class ScriptRejected(Exception):
    def __init__(self, code: str, reason: str, field: str = '') -> None:
        super().__init__(f'{code}: {reason}' + (f' ({field})' if field else ''))
        self.code = code
        self.reason = reason
        self.field = field


@dataclass(frozen=True, kw_only=True)
class LanguageVoicePolicy:
    """Language and voice policy with speech rate in words per second."""

    language: str
    speech_rate: float

    def __post_init__(self) -> None:
        if self.language is None or self.language == '':
            raise ScriptRejected(INPUT_NOT_READY, 'missing_language', 'language')
        if not isinstance(self.language, str):
            raise ValueError('language must be a string')
        if self.speech_rate is None:
            raise ScriptRejected(INPUT_NOT_READY, 'missing_speech_rate', 'speech_rate')
        if (
            isinstance(self.speech_rate, bool)
            or not isinstance(self.speech_rate, (int, float))
            or not math.isfinite(self.speech_rate)
            or self.speech_rate <= 0
        ):
            raise ValueError('speech_rate must be a positive finite number')
        object.__setattr__(self, 'speech_rate', float(self.speech_rate))


@dataclass(frozen=True, kw_only=True)
class TargetRange:
    """Target duration range in seconds (inclusive)."""

    min_seconds: float
    max_seconds: float

    def __post_init__(self) -> None:
        if self.min_seconds is None:
            raise ScriptRejected(INPUT_NOT_READY, 'missing_target_range', 'min_seconds')
        if self.max_seconds is None:
            raise ScriptRejected(INPUT_NOT_READY, 'missing_target_range', 'max_seconds')
        if (
            isinstance(self.min_seconds, bool)
            or not isinstance(self.min_seconds, (int, float))
            or not math.isfinite(self.min_seconds)
            or self.min_seconds <= 0
        ):
            raise ValueError('min_seconds must be a positive finite number')
        if (
            isinstance(self.max_seconds, bool)
            or not isinstance(self.max_seconds, (int, float))
            or not math.isfinite(self.max_seconds)
            or self.max_seconds <= 0
        ):
            raise ValueError('max_seconds must be a positive finite number')
        if float(self.min_seconds) > float(self.max_seconds):
            raise ValueError('min_seconds cannot exceed max_seconds')
        object.__setattr__(self, 'min_seconds', float(self.min_seconds))
        object.__setattr__(self, 'max_seconds', float(self.max_seconds))


@dataclass(frozen=True, kw_only=True)
class ScriptSegment:
    segment_id: str
    order: int
    text: str
    claim_mode: str
    scene_intent: str
    source_refs: tuple[ResourceRef, ...]
    disclosure: str | None
    word_count: int
    estimated_seconds: float


@dataclass(frozen=True, kw_only=True)
class ScriptVersion:
    """ScriptVersion frozen aggregate. coveredIds: CT-AI-004, CT-TTS-001."""

    script_version_id: str
    language: str
    hook_intent: str
    thumbnail_transition: str
    segments: tuple[ScriptSegment, ...]
    pronunciation_hints: tuple[Mapping[str, str], ...]
    speech_rate: float
    estimated_duration_seconds: float

    @property
    def scene_intents(self) -> tuple[str, ...]:
        return tuple(s.scene_intent for s in self.segments)

    @property
    def narration(self) -> tuple[str, ...]:
        return tuple(s.text for s in self.segments)

    def fingerprint_basis(self) -> dict[str, object]:
        return {'narration': list(self.narration)}

    @property
    def script_fingerprint(self) -> str:
        return request_hash(self.fingerprint_basis())

    def to_voice_track_inputs(self) -> dict[str, object]:
        """Convert to voice track request inputs matching d-e-f-voice-timing/VoiceTrackRequest binding. coveredIds: CT-AI-004, CT-TTS-001."""
        return {
            'script_version_id': self.script_version_id,
            'script_fingerprint': self.script_fingerprint,
            'pronunciation_hints': [
                {'term': str(h['term']), 'pronunciation': str(h['pronunciation'])}
                for h in self.pronunciation_hints
            ],
        }


def normalize_narration(text: str) -> str:
    if not isinstance(text, str):
        raise ValueError('text must be a string')
    return ' '.join(unicodedata.normalize('NFKC', text).split())


def count_words(text: str) -> int:
    return len(normalize_narration(text).split())


def _reject(field: str, reason: str) -> None:
    raise ScriptRejected(SCHEMA_VIOLATION, reason, field)


def _value(source: Mapping[str, object], key: str, path: str = '') -> object:
    if key not in source:
        _reject(path + key, MISSING_REQUIRED)
    val = source[key]
    if val is None:
        _reject(path + key, WRONG_TYPE)
    return val


def _text(source: Mapping[str, object], key: str, path: str = '') -> str:
    val = _value(source, key, path)
    if not isinstance(val, str):
        _reject(path + key, WRONG_TYPE)
    if not val.strip():
        _reject(path + key, EMPTY_VALUE)
    return val


def _list(source: Mapping[str, object], key: str, path: str = '') -> list[object]:
    val = _value(source, key, path)
    if not isinstance(val, list):
        _reject(path + key, WRONG_TYPE)
    return val


def _parse_raw(raw: object) -> dict[str, object]:
    if not isinstance(raw, Mapping):
        _reject('$', WRONG_TYPE)

    script_version_id = _text(raw, 'script_version_id')
    language = _text(raw, 'language')
    hook_intent = _text(raw, 'hook_intent')
    thumbnail_transition = _text(raw, 'thumbnail_transition')

    raw_hints = _list(raw, 'pronunciation_hints')
    hints: list[dict[str, str]] = []
    for i, h in enumerate(raw_hints):
        if not isinstance(h, Mapping):
            _reject(f'pronunciation_hints[{i}]', WRONG_TYPE)
        term = _text(h, 'term', f'pronunciation_hints[{i}].')
        pronunciation = _text(h, 'pronunciation', f'pronunciation_hints[{i}].')
        hints.append({'term': term, 'pronunciation': pronunciation})

    raw_segments = _list(raw, 'segments')
    if not raw_segments:
        _reject('segments', EMPTY_VALUE)

    seen_segment_ids: set[str] = set()
    segments: list[dict[str, object]] = []
    for i, seg in enumerate(raw_segments):
        path = f'segments[{i}].'
        if not isinstance(seg, Mapping):
            _reject(f'segments[{i}]', WRONG_TYPE)

        segment_id = _text(seg, 'segment_id', path)
        if segment_id in seen_segment_ids:
            raise ScriptRejected(SCHEMA_VIOLATION, DUPLICATE_ID, f'segments[{i}].segment_id')
        seen_segment_ids.add(segment_id)

        raw_text = _text(seg, 'text', path)
        norm_text = normalize_narration(raw_text)
        if not norm_text:
            _reject(f'segments[{i}].text', EMPTY_VALUE)

        if 'claim_mode' not in seg:
            _reject(f'segments[{i}].claim_mode', MISSING_REQUIRED)
        raw_mode = seg['claim_mode']
        if not isinstance(raw_mode, str):
            _reject(f'segments[{i}].claim_mode', WRONG_TYPE)
        if raw_mode not in CLAIM_MODES:
            raise ScriptRejected(SCHEMA_VIOLATION, ENUM_VIOLATION, f'segments[{i}].claim_mode')

        scene_intent = _text(seg, 'scene_intent', path)

        raw_refs = _list(seg, 'source_refs', path)
        parsed_refs: list[Mapping[str, object]] = []
        for j, r in enumerate(raw_refs):
            if not isinstance(r, Mapping):
                _reject(f'segments[{i}].source_refs[{j}]', WRONG_TYPE)
            parsed_refs.append(r)

        raw_disc = seg.get('disclosure')
        if raw_disc is not None and not isinstance(raw_disc, str):
            _reject(f'segments[{i}].disclosure', WRONG_TYPE)

        segments.append({
            'segment_id': segment_id,
            'text': norm_text,
            'claim_mode': raw_mode,
            'scene_intent': scene_intent,
            'refs': parsed_refs,
            'disclosure': raw_disc,
        })

    return {
        'script_version_id': script_version_id,
        'language': language,
        'hook_intent': hook_intent,
        'thumbnail_transition': thumbnail_transition,
        'hints': hints,
        'segments': segments,
    }


def build_script_version(
    raw: object,
    *,
    resolver: RefResolver,
    language_policy: LanguageVoicePolicy,
    target_range: TargetRange,
) -> ScriptVersion:
    """Build and validate a ScriptVersion from raw input against domain invariants.

    Raw schema:
        script_version_id (str)
        language (str)
        hook_intent (str)
        thumbnail_transition (str)
        pronunciation_hints (list[dict[term: str, pronunciation: str]])
        segments (list[dict]):
            segment_id (str, unique)
            text (str, non-empty)
            claim_mode (str in CLAIM_MODES)
            scene_intent (str)
            source_refs (list[dict])
            disclosure (optional str, required for inference & creative_hypothesis)

    Rejections:
        INPUT_NOT_READY: missing language_policy or target_range
        SCHEMA_VIOLATION: missing_required, wrong_type, enum_violation, empty_value, duplicate_id
        LANGUAGE_MISMATCH: policy_language_mismatch
        HALLUCINATED_REF: ref not verified by resolver
        MISSING_SOURCE_REF: source_backed_requires_ref
        MISSING_DISCLOSURE: disclosure_required
        DURATION_OUT_OF_RANGE: below_target_range, above_target_range

    coveredIds: CT-AI-004, CT-TTS-001
    """
    if not isinstance(resolver, RefResolver):
        raise TypeError('resolver must be a RefResolver')
    if not isinstance(language_policy, LanguageVoicePolicy):
        raise ScriptRejected(INPUT_NOT_READY, 'missing_language_policy', 'language_policy')
    if not isinstance(target_range, TargetRange):
        raise ScriptRejected(INPUT_NOT_READY, 'missing_target_range', 'target_range')

    data = _parse_raw(raw)

    if data['language'] != language_policy.language:
        raise ScriptRejected(LANGUAGE_MISMATCH, 'policy_language_mismatch', 'language')

    built_segments: list[ScriptSegment] = []
    total_words = 0

    for i, seg in enumerate(data['segments']):
        resolved_refs: list[ResourceRef] = []
        for j, proposed in enumerate(seg['refs']):
            result = resolver.resolve(proposed)
            if not result.ok:
                raise ScriptRejected(HALLUCINATED_REF, result.reason or 'unknown_ref', f'segments[{i}].source_refs[{j}]')
            resolved_refs.append(result.ref)  # type: ignore[arg-type]

        claim_mode = seg['claim_mode']
        if claim_mode == CLAIM_SOURCE_BACKED and len(resolved_refs) == 0:
            raise ScriptRejected(MISSING_SOURCE_REF, 'source_backed_requires_ref', f'segments[{i}].source_refs')

        raw_disc = seg['disclosure']
        if claim_mode in DISCLOSURE_MODES:
            if raw_disc is None:
                raise ScriptRejected(MISSING_DISCLOSURE, 'disclosure_required', f'segments[{i}].disclosure')
            norm_disc = normalize_narration(raw_disc)
            if not norm_disc:
                raise ScriptRejected(MISSING_DISCLOSURE, 'disclosure_required', f'segments[{i}].disclosure')
            saved_disc: str | None = norm_disc
        else:
            if raw_disc is not None:
                norm_disc = normalize_narration(raw_disc)
                saved_disc = norm_disc if norm_disc else None
            else:
                saved_disc = None

        words = count_words(seg['text'])
        total_words += words
        est_seconds = round(words / language_policy.speech_rate, 6)

        built_segments.append(
            ScriptSegment(
                segment_id=seg['segment_id'],
                order=i,
                text=seg['text'],
                claim_mode=claim_mode,
                scene_intent=seg['scene_intent'],
                source_refs=tuple(resolved_refs),
                disclosure=saved_disc,
                word_count=words,
                estimated_seconds=est_seconds,
            )
        )

    estimated_duration = total_words / language_policy.speech_rate
    if estimated_duration < target_range.min_seconds:
        raise ScriptRejected(DURATION_OUT_OF_RANGE, 'below_target_range', 'segments')
    if estimated_duration > target_range.max_seconds:
        raise ScriptRejected(DURATION_OUT_OF_RANGE, 'above_target_range', 'segments')

    hints_proxy = tuple(
        MappingProxyType(copy.deepcopy(h))
        for h in data['hints']
    )

    return ScriptVersion(
        script_version_id=data['script_version_id'],
        language=data['language'],
        hook_intent=data['hook_intent'],
        thumbnail_transition=data['thumbnail_transition'],
        segments=tuple(built_segments),
        pronunciation_hints=hints_proxy,
        speech_rate=language_policy.speech_rate,
        estimated_duration_seconds=round(estimated_duration, 6),
    )