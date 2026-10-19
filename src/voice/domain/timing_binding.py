"""E-11: TimingBinding, kiểm binding và invalidation downstream (CT-SUB-001 bất biến 2 và 3).

Pure domain: no I/O, no clock, no mutation. Script fingerprint and voice hash are compared as given; E never recomputes them.
Invalidation only returns refs and reasons: old VoiceTrack and TimingBinding records stay untouched and a replacement is a new record made by the caller.

coveredIds: TST-MEDIA-INV-007 (mức domain), CT-SUB-001 bất biến 2 và 3
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from types import MappingProxyType

from voice.domain.voice_track import VoiceTrack, matches_type
from voice.domain.word_timing import WordTimingRecord

SCRIPT_CHANGED = 'script_changed'
VOICE_CHANGED = 'voice_changed'
VOICE_ARTIFACT_REVISION_CHANGED = 'voice_artifact_revision_changed'
TIMING_BINDING_INVALID = 'timing_binding_invalid'

TIMING_BINDING_FIELDS = MappingProxyType({
    'script_version_id': 'string',
    'script_fingerprint': 'sha256',
    'voice_hash': 'sha256',
    'timing_artifact_ref': 'string',
})
CHANGE_FIELDS = MappingProxyType({
    SCRIPT_CHANGED: MappingProxyType({'old_script_fingerprint': 'sha256'}),
    VOICE_CHANGED: MappingProxyType({'old_voice_hash': 'sha256'}),
    VOICE_ARTIFACT_REVISION_CHANGED: MappingProxyType({'voice_artifact_ref': 'string', 'old_voice_revision': 'string'}),
})
CHANGE_ATTRIBUTES = ('old_script_fingerprint', 'old_voice_hash', 'voice_artifact_ref', 'old_voice_revision')


@dataclass(frozen=True, kw_only=True)
class TimingBinding:
    """The exact script and voice a word timing artifact is bound to (CT-SUB-001 bất biến 2)."""

    script_version_id: str
    script_fingerprint: str
    voice_hash: str
    timing_artifact_ref: str

    def __post_init__(self) -> None:
        for name, type_name in TIMING_BINDING_FIELDS.items():
            if not matches_type(getattr(self, name), type_name):
                raise ValueError(f'{name} must be {type_name}')

    @classmethod
    def from_word_timing(cls, record: WordTimingRecord) -> TimingBinding:
        """Copy the four binding fields of a validated WordTimingRecord."""
        return cls(**{name: getattr(record, name) for name in TIMING_BINDING_FIELDS})


@dataclass(frozen=True)
class TimingBindingCheck:
    """valid is True with empty reasons, or False with reasons in the order script_changed, voice_changed."""

    valid: bool
    reasons: tuple[str, ...]


class TimingBindingError(Exception):
    """The timing is no longer bound to the current script and voice; `reasons` lists script_changed and/or voice_changed."""

    def __init__(self, timing_artifact_ref: str, reasons: Iterable[str]) -> None:
        self.code = TIMING_BINDING_INVALID
        self.timing_artifact_ref = timing_artifact_ref
        self.reasons = tuple(reasons)
        super().__init__(f'{self.code}: {timing_artifact_ref}: ' + ', '.join(self.reasons))


@dataclass(frozen=True, kw_only=True)
class DownstreamChange:
    """What changed upstream; `kind` selects the old identifiers that are required, every other identifier must be None."""

    kind: str
    old_script_fingerprint: str | None = None
    old_voice_hash: str | None = None
    voice_artifact_ref: str | None = None
    old_voice_revision: str | None = None

    def __post_init__(self) -> None:
        required = CHANGE_FIELDS.get(self.kind)
        if required is None:
            raise ValueError(f'kind must be one of {tuple(CHANGE_FIELDS)}')
        for name in CHANGE_ATTRIBUTES:
            value = getattr(self, name)
            if name in required and not matches_type(value, required[name]):
                raise ValueError(f'{name} must be {required[name]} for {self.kind}')
            if name not in required and value is not None:
                raise ValueError(f'{name} must be None for {self.kind}')


@dataclass(frozen=True)
class StaleRecord:
    """A stale record by ref (voice_artifact_ref or timing_artifact_ref) and the change kind that made it stale."""

    ref: str
    reason: str


@dataclass(frozen=True)
class InvalidationResult:
    change: DownstreamChange
    stale_voice_tracks: tuple[StaleRecord, ...]
    stale_timings: tuple[StaleRecord, ...]


def check_timing_binding(timing: TimingBinding, current_script_fingerprint: str, current_voice_hash: str) -> TimingBindingCheck:
    """Compare the timing binding with the current script fingerprint and voice hash (both compared as given).

    Returns valid, or invalid with reasons script_changed and/or voice_changed. Raises TypeError for a non-TimingBinding and
    ValueError when a current value is not a lowercase sha256 hex, so a missing current value is never treated as valid.
    """
    if not isinstance(timing, TimingBinding):
        raise TypeError('timing must be a TimingBinding')
    for name, value in (('current_script_fingerprint', current_script_fingerprint), ('current_voice_hash', current_voice_hash)):
        if not matches_type(value, 'sha256'):
            raise ValueError(f'{name} must be sha256')
    reasons = []
    if timing.script_fingerprint != current_script_fingerprint:
        reasons.append(SCRIPT_CHANGED)
    if timing.voice_hash != current_voice_hash:
        reasons.append(VOICE_CHANGED)
    return TimingBindingCheck(not reasons, tuple(reasons))


def require_valid_timing(timing: TimingBinding, current_script_fingerprint: str, current_voice_hash: str) -> TimingBinding:
    """Return the timing when it is bound to the current script and voice; raise TimingBindingError with the reasons otherwise."""
    check = check_timing_binding(timing, current_script_fingerprint, current_voice_hash)
    if not check.valid:
        raise TimingBindingError(timing.timing_artifact_ref, check.reasons)
    return timing


def invalidate_downstream(change: DownstreamChange, voice_tracks: Iterable[VoiceTrack], timings: Iterable[TimingBinding]) -> InvalidationResult:
    """Return the voice tracks and timings that are stale after `change`, as refs with reason = change.kind.

    script_changed makes voice tracks and timings bound to the old fingerprint stale; voice_changed makes only timings bound to
    the old voice hash stale; voice_artifact_revision_changed makes only timings bound to the hash of the matching voice artifact
    (same ref and old revision) stale. Inputs are only read: nothing is mutated or deleted.
    """
    if not isinstance(change, DownstreamChange):
        raise TypeError('change must be a DownstreamChange')
    tracks, bindings = tuple(voice_tracks), tuple(timings)
    if not all(isinstance(track, VoiceTrack) for track in tracks):
        raise TypeError('voice_tracks must contain only VoiceTrack')
    if not all(isinstance(binding, TimingBinding) for binding in bindings):
        raise TypeError('timings must contain only TimingBinding')
    stale_tracks: list[VoiceTrack] = []
    if change.kind == SCRIPT_CHANGED:
        stale_tracks = [track for track in tracks if track.script_fingerprint == change.old_script_fingerprint]
        stale_timings = [binding for binding in bindings if binding.script_fingerprint == change.old_script_fingerprint]
    elif change.kind == VOICE_CHANGED:
        stale_timings = [binding for binding in bindings if binding.voice_hash == change.old_voice_hash]
    else:
        old_hashes = {
            track.voice_hash
            for track in tracks
            if track.voice_artifact_ref == change.voice_artifact_ref and track.provider_model_voice_revision == change.old_voice_revision
        }
        stale_timings = [binding for binding in bindings if binding.voice_hash in old_hashes]
    return InvalidationResult(
        change,
        tuple(StaleRecord(track.voice_artifact_ref, change.kind) for track in stale_tracks),
        tuple(StaleRecord(binding.timing_artifact_ref, change.kind) for binding in stale_timings),
    )
