"""StoryAngle and StoryAngleSet (CT-AI-003, TST-AI-INV-013 at angle level).

Pure domain: no I/O, no clock, no id generation, no AI call. Ids, history and the variation policy revision are caller
input with no hidden default. The distinction fingerprint hashes only the normalized narrative question, focus entities
and timeframe, never the angle id, title, summary or style.
"""
from __future__ import annotations

import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from controlplane.application.idempotency.canonicalization import request_hash
from creative.domain.ref_resolver import ResourceRef

MIN_REQUESTED_COUNT = 1
MAX_REQUESTED_COUNT = 3
REQUESTED_COUNT_OUT_OF_RANGE = 'requested_count_out_of_range'
SAME_RUN_ANGLE_DUPLICATE = 'same_run_angle_duplicate'
INSUFFICIENT_DISTINCT_ANGLES = 'insufficient_distinct_angles'
INITIAL_SET_NOT_EXHAUSTED = 'initial_set_not_exhausted'
INPUT_NOT_READY = 'INPUT_NOT_READY'
GENERATION_INITIAL = 'initial'
GENERATION_NEW_SET = 'new_set'
EXCLUDED_LATEST_SCRIPT = 'matches_latest_script_angle'


class AngleSetRejected(Exception):
    """The angle set cannot be built: `code` is one of the module constants, `reason` the stable machine reason, `field` locates it."""

    def __init__(self, code: str, reason: str, field_path: str = '') -> None:
        super().__init__(f'{code}: {reason}' + (f' ({field_path})' if field_path else ''))
        self.code = code
        self.reason = reason
        self.field = field_path


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a non-empty string')
    return value


def _texts(name: str, values: object) -> tuple[str, ...]:
    if isinstance(values, (str, bytes, Mapping)) or not isinstance(values, Iterable):
        raise ValueError(f'{name} must be an iterable, not a string or mapping')
    return tuple(_text(f'{name} item', item) for item in values)


def _checked(name: str, items: object, cls: type) -> tuple:
    if isinstance(items, (str, bytes, Mapping)) or not isinstance(items, Iterable):
        raise TypeError(f'{name} must be an iterable of {cls.__name__}')
    values = tuple(items)
    if not all(isinstance(item, cls) for item in values):
        raise TypeError(f'{name} items must be {cls.__name__}')
    return values


def normalize_text(value: str) -> str:
    """Fold a value for fingerprinting: NFKC, casefold, collapsed whitespace; diacritics are kept."""
    return ' '.join(unicodedata.normalize('NFKC', unicodedata.normalize('NFKC', value).casefold()).split())


def compute_distinction_fingerprint(narrative_question: str, focus_entities: Iterable[str], timeframe: str) -> str:
    """sha256 (request_hash) over the normalized narrative question, sorted unique normalized focus entities and timeframe."""
    entities = sorted({normalize_text(item) for item in focus_entities})
    basis = {'narrative_question': normalize_text(narrative_question), 'focus_entities': entities, 'timeframe': normalize_text(timeframe)}
    return request_hash(basis)


@dataclass(frozen=True, kw_only=True)
class StoryAngle:
    """CT-AI-003 angle. Tuples are frozen copies; distinction_fingerprint is derived in __post_init__ and cannot be passed in."""

    angle_id: str
    title: str
    summary: str
    narrative_question: str
    focus_entities: tuple[str, ...]
    timeframe: str
    evidence_refs: tuple[ResourceRef, ...]
    planned_inference_elements: tuple[str, ...]
    planned_creative_elements: tuple[str, ...]
    suitability: str
    risk_flags: tuple[str, ...]
    distinction_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ('angle_id', 'title', 'summary', 'narrative_question', 'timeframe', 'suitability'):
            _text(name, getattr(self, name))
        entities = _texts('focus_entities', self.focus_entities)
        refs = _checked('evidence_refs', self.evidence_refs, ResourceRef)
        if not entities:
            raise ValueError('focus_entities must not be empty')
        if not refs:
            raise ValueError('evidence_refs must not be empty')
        object.__setattr__(self, 'focus_entities', entities)
        object.__setattr__(self, 'evidence_refs', refs)
        for name in ('planned_inference_elements', 'planned_creative_elements', 'risk_flags'):
            object.__setattr__(self, name, _texts(name, getattr(self, name)))
        object.__setattr__(
            self, 'distinction_fingerprint', compute_distinction_fingerprint(self.narrative_question, entities, self.timeframe))

    def to_payload(self) -> dict[str, object]:
        return {
            'angle_id': self.angle_id,
            'title': self.title,
            'summary': self.summary,
            'narrative_question': self.narrative_question,
            'focus_entities': list(self.focus_entities),
            'timeframe': self.timeframe,
            'evidence_refs': [
                {'workspace_id': ref.workspace_id, 'ref_type': ref.ref_type, 'ref_id': ref.ref_id, 'revision_id': ref.revision_id}
                for ref in self.evidence_refs
            ],
            'planned_inference_elements': list(self.planned_inference_elements),
            'planned_creative_elements': list(self.planned_creative_elements),
            'distinction_fingerprint': self.distinction_fingerprint,
            'suitability': self.suitability,
            'risk_flags': list(self.risk_flags),
        }


@dataclass(frozen=True, kw_only=True)
class AngleHistoryEntry:
    """One earlier script of the same news; a higher `sequence` is more recent; carries that script's angle fingerprint."""

    script_id: str
    sequence: int
    distinction_fingerprint: str

    def __post_init__(self) -> None:
        _text('script_id', self.script_id)
        _text('distinction_fingerprint', self.distinction_fingerprint)
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence < 1:
            raise ValueError('sequence must be a positive integer')


@dataclass(frozen=True, kw_only=True)
class ExcludedAngle:
    angle_id: str
    distinction_fingerprint: str
    reason: str


@dataclass(frozen=True, kw_only=True)
class StoryAngleSet:
    """CT-AI-003 output: 1-3 angles with distinct fingerprints, the angles dropped by history and the variation policy revision used."""

    set_id: str
    analysis_id: str
    analysis_revision: int
    requested_count: int
    generation: str
    variation_policy_revision: str
    angles: tuple[StoryAngle, ...]
    excluded: tuple[ExcludedAngle, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            'set_id': self.set_id,
            'analysis_id': self.analysis_id,
            'analysis_revision': self.analysis_revision,
            'requested_count': self.requested_count,
            'generation': self.generation,
            'variation_policy_revision': self.variation_policy_revision,
            'angles': [angle.to_payload() for angle in self.angles],
            'excluded': [
                {'angle_id': item.angle_id, 'distinction_fingerprint': item.distinction_fingerprint, 'reason': item.reason}
                for item in self.excluded
            ],
        }


def build_story_angle_set(
    *,
    set_id: str,
    analysis_id: str,
    analysis_revision: int,
    requested_count: int,
    candidates: Iterable[StoryAngle],
    variation_policy_revision: str | None,
    history: Iterable[AngleHistoryEntry] = (),
    initial_set_fingerprints: Iterable[str] = (),
) -> StoryAngleSet:
    """Build a StoryAngleSet (CT-AI-003): reject requested_count outside 1-3, same_run_angle_duplicate, an unexhausted initial set; drop angles matching the latest history script; record the variation policy revision."""
    _text('set_id', set_id)
    _text('analysis_id', analysis_id)
    if isinstance(analysis_revision, bool) or not isinstance(analysis_revision, int) or analysis_revision < 1:
        raise ValueError('analysis_revision must be a positive integer')
    if isinstance(requested_count, bool) or not isinstance(requested_count, int) or not MIN_REQUESTED_COUNT <= requested_count <= MAX_REQUESTED_COUNT:
        raise AngleSetRejected(REQUESTED_COUNT_OUT_OF_RANGE, 'out_of_range', 'requested_count')
    if not isinstance(variation_policy_revision, str) or not variation_policy_revision.strip():
        raise AngleSetRejected(INPUT_NOT_READY, 'missing_variation_policy_revision', 'variation_policy_revision')
    angles = _checked('candidates', candidates, StoryAngle)
    entries = _checked('history', history, AngleHistoryEntry)
    initial = frozenset(_texts('initial_set_fingerprints', initial_set_fingerprints))
    seen_ids: set[str] = set()
    seen_fingerprints: set[str] = set()
    for index, angle in enumerate(angles):
        if angle.angle_id in seen_ids:
            raise ValueError(f'duplicate angle_id: {angle.angle_id}')
        if angle.distinction_fingerprint in seen_fingerprints:
            raise AngleSetRejected(SAME_RUN_ANGLE_DUPLICATE, 'same_distinction_fingerprint', f'candidates[{index}]')
        seen_ids.add(angle.angle_id)
        seen_fingerprints.add(angle.distinction_fingerprint)
    if len({entry.sequence for entry in entries}) != len(entries):
        raise ValueError('history sequence values must be unique')
    if initial and not initial <= {entry.distinction_fingerprint for entry in entries}:
        raise AngleSetRejected(INITIAL_SET_NOT_EXHAUSTED, 'initial_angles_not_all_exploited', 'initial_set_fingerprints')
    latest = max(entries, key=lambda entry: entry.sequence).distinction_fingerprint if entries else None
    kept = [angle for angle in angles if angle.distinction_fingerprint != latest]
    excluded = tuple(
        ExcludedAngle(angle_id=angle.angle_id, distinction_fingerprint=angle.distinction_fingerprint, reason=EXCLUDED_LATEST_SCRIPT)
        for angle in angles if angle.distinction_fingerprint == latest
    )
    if not kept:
        raise AngleSetRejected(INSUFFICIENT_DISTINCT_ANGLES, 'no_angle_left_after_history_exclusion', 'candidates')
    return StoryAngleSet(
        set_id=set_id, analysis_id=analysis_id, analysis_revision=analysis_revision, requested_count=requested_count,
        generation=GENERATION_NEW_SET if initial else GENERATION_INITIAL, variation_policy_revision=variation_policy_revision,
        angles=tuple(kept[:requested_count]), excluded=excluded,
    )
