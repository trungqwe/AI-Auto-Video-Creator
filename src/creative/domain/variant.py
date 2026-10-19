"""VariantValidation (CT-AI-008, CT-ORC-012 phía D): VariantFingerprint và validate_variant.

Pure domain: không I/O, không clock, không gọi AI, không tạo hay release reservation (thuộc G). Fingerprint chỉ tính từ nội dung thực tế của script, plan, selection và góc khai thác, không từ seed, id hay revision.

coveredIds: CT-AI-008, TST-AI-INV-013, TST-AI-INV-014, TST-WF-VAR-004
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from controlplane.application.idempotency.canonicalization import request_hash
from controlplane.domain.orchestration import ReservationState, VariantReservation
from creative.domain.angles import normalize_text
from creative.domain.asset_selection import CreativeAssetSelection
from creative.domain.production_plan import ProductionPlan
from creative.domain.script import ScriptVersion

INPUT_NOT_READY = 'INPUT_NOT_READY'
INVALID_INPUT = 'invalid_variant_input'
CONTEXT_MISMATCH = 'variant_context_mismatch'
PHASE_PLAN = 'plan'
PHASE_OUTPUT = 'output'
PHASES = (PHASE_PLAN, PHASE_OUTPUT)
FACTOR_VOICE = 'voice'
FACTOR_SOUND = 'sound'
FACTOR_HOOK = 'hook'
FACTOR_MEDIA = 'media'
FACTOR_EFFECTS = 'effects'
FACTOR_CONTENT = 'content'
FACTOR_NARRATION_STYLE = 'narration_style'
FACTOR_BACKGROUND_MUSIC = 'background_music'
FACTOR_ANGLE = 'angle'
DISTINCT_FACTORS = (FACTOR_VOICE, FACTOR_SOUND, FACTOR_HOOK, FACTOR_MEDIA, FACTOR_EFFECTS, FACTOR_CONTENT, FACTOR_NARRATION_STYLE, FACTOR_BACKGROUND_MUSIC, FACTOR_ANGLE)
REASON_VALID = 'variant_distinct'
REASON_SAME_RUN_ANGLE_DUPLICATE = 'same_run_angle_duplicate'
REASON_EXACT_DUPLICATE = 'exact_duplicate'
REASON_NO_DISTINCT_FACTOR = 'no_distinct_factor'
_SHA256 = re.compile(r'[0-9a-f]{64}')


class VariantRejected(Exception):
    """Đầu vào thiếu hoặc sai: `code` là INPUT_NOT_READY, INVALID_INPUT hoặc CONTEXT_MISMATCH, `reason` là lý do máy đọc được, `field` chỉ vị trí."""

    def __init__(self, code: str, reason: str, field: str = '') -> None:
        super().__init__(f'{code}: {reason}' + (f' ({field})' if field else ''))
        self.code = code
        self.reason = reason
        self.field = field


def _reject(code: str, reason: str, field: str = '') -> None:
    raise VariantRejected(code, reason, field)




def _require_text(value: object, reason: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _reject(INPUT_NOT_READY, reason, field)
    return value


def _require_sha256(value: object, field: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        _reject(INVALID_INPUT, 'invalid_sha256', field)
    return value


def _norm(value):
    """Chuẩn hoá mọi chuỗi (NFKC, casefold, gộp khoảng trắng) ở mọi vị trí lồng; khoá và số giữ nguyên."""
    if isinstance(value, str):
        return normalize_text(value)
    if isinstance(value, Mapping):
        return {key: _norm(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_norm(item) for item in value]
    return value


@dataclass(frozen=True, kw_only=True)
class VariantFingerprint:
    """`factors` là hash từng yếu tố khác biệt (đúng DISTINCT_FACTORS); `fingerprint` là hash nội dung đầy đủ (gồm cả chi tiết plan ngoài các yếu tố). Không chứa id, seed hay revision."""

    factors: Mapping[str, str]
    fingerprint: str

    def __post_init__(self) -> None:
        if not isinstance(self.factors, Mapping) or set(self.factors) != set(DISTINCT_FACTORS):
            _reject(INVALID_INPUT, 'factors_mismatch', 'factors')
        for name in DISTINCT_FACTORS:
            _require_sha256(self.factors[name], f'factors.{name}')
        _require_sha256(self.fingerprint, 'fingerprint')
        object.__setattr__(self, 'factors', MappingProxyType({name: self.factors[name] for name in DISTINCT_FACTORS}))

    def to_payload(self) -> dict[str, object]:
        return {'factors': dict(self.factors), 'fingerprint': self.fingerprint}


_EXACT_PLAN_FIELDS = ('timeline', 'hook_placement', 'thumbnail_overlay_intent', 'voice_profile_intent', 'music_cues', 'sfx_cues', 'subtitle_style_intent', 'allowed_fallbacks')


def _factor_values(script: ScriptVersion, payload: Mapping[str, object], angle: str) -> dict[str, object]:
    segments = payload['timeline']['segments']
    visuals = [v for s in segments for v in sorted(s['visuals'], key=lambda item: (item['start_ms'], item['end_ms']))]
    placement = payload['hook_placement']
    return {
        FACTOR_VOICE: _norm({'profile': payload['voice_profile_intent'], 'speech_rate': script.speech_rate}),
        FACTOR_SOUND: _norm(payload['sfx_cues']),
        FACTOR_HOOK: {
            'visual_hook_ref': placement['visual_hook_ref'], 'audio_hook_ref': placement['audio_hook_ref'],
            'hook_time_range': placement['hook_time_range'], 'hook_intent': normalize_text(script.hook_intent),
        },
        FACTOR_MEDIA: [{'media_asset_id': v['media_asset_id'], 'artifact_version_ref': v['artifact_version_ref']} for v in visuals],
        FACTOR_EFFECTS: _norm({
            'visuals': [{key: v[key] for key in ('crop_intent', 'overlay_intent', 'effect_intent')} for v in visuals],
            'transitions': [s['transition_intent'] for s in segments],
            'subtitle_style_intent': payload['subtitle_style_intent'],
            'thumbnail_overlay_intent': payload['thumbnail_overlay_intent'],
            'thumbnail_transition': script.thumbnail_transition,
        }),
        FACTOR_CONTENT: _norm(list(script.narration)),
        FACTOR_NARRATION_STYLE: _norm({'claim_modes': [s.claim_mode for s in script.segments], 'scene_intents': list(script.scene_intents)}),
        FACTOR_BACKGROUND_MUSIC: _norm(payload['music_cues']),
        FACTOR_ANGLE: angle,
    }


def build_variant_fingerprint(*, script, plan, selection, angle_distinction_fingerprint) -> VariantFingerprint:
    """Dựng VariantFingerprint (CT-AI-008 bất biến 3, 4) từ nội dung thật của script, plan, selection và fingerprint góc khai thác (StoryAngle.distinction_fingerprint).

    Không đọc production_plan_id, script_version_id, snapshot/angle ref, preset revision, rationale hay seed. Raise VariantRejected(code, reason, field).
    """
    if not isinstance(script, ScriptVersion):
        _reject(INPUT_NOT_READY, 'missing_script_version', 'script')
    if not isinstance(plan, ProductionPlan):
        _reject(INPUT_NOT_READY, 'missing_production_plan', 'plan')
    if not isinstance(selection, CreativeAssetSelection):
        _reject(INPUT_NOT_READY, 'missing_asset_selection', 'selection')
    angle = _require_text(angle_distinction_fingerprint, 'missing_angle_distinction_fingerprint', 'angle_distinction_fingerprint')
    if plan.script_version_id != script.script_version_id or plan.script_fingerprint != script.script_fingerprint:
        _reject(CONTEXT_MISMATCH, 'script_mismatch', 'plan.script_version_id')
    if plan.selection_fingerprint != selection.selection_fingerprint:
        _reject(CONTEXT_MISMATCH, 'selection_mismatch', 'plan.selection_fingerprint')
    payload = plan.to_payload()
    values = _factor_values(script, payload, angle)
    factors = {name: request_hash({'factor': name, 'value': values[name]}) for name in DISTINCT_FACTORS}
    content = {'factors': factors, 'plan': {name: payload[name] for name in _EXACT_PLAN_FIELDS}}
    return VariantFingerprint(factors=factors, fingerprint=request_hash(content))


def _check_prior(ref_id: object, fingerprint: object) -> None:
    _require_text(ref_id, 'missing_ref_id', 'ref_id')
    if not isinstance(fingerprint, VariantFingerprint):
        _reject(INVALID_INPUT, 'wrong_type', 'fingerprint')


@dataclass(frozen=True, kw_only=True)
class CompletedVariant:
    """Video đã hoàn thành của cùng article/event, do caller cung cấp (lịch sử completed)."""

    ref_id: str
    fingerprint: VariantFingerprint

    def __post_init__(self) -> None:
        _check_prior(self.ref_id, self.fingerprint)


@dataclass(frozen=True, kw_only=True)
class SameRunVariant:
    """Video khác trong cùng lượt sản xuất (không gồm chính ứng viên)."""

    ref_id: str
    fingerprint: VariantFingerprint

    def __post_init__(self) -> None:
        _check_prior(self.ref_id, self.fingerprint)


@dataclass(frozen=True, kw_only=True)
class VariantValidationResult:
    """Kết quả CT-AI-008 bất biến. `valid=true` không cấp quyền completion: G kiểm CAS theo CT-ORC-012; dùng is_current_for để biết bằng chứng còn hiệu lực."""

    valid: bool
    same_run_angle_distinct: bool
    exact_duplicate: bool
    distinct_factors: tuple[str, ...]
    nearest_prior_refs: tuple[str, ...]
    reason_codes: tuple[str, ...]
    input_hashes: Mapping[str, str]
    registry_revision: int
    phase: str
    variation_policy_revision: str
    own_reservation_id: str | None
    output_hash: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, 'input_hashes', MappingProxyType(dict(self.input_hashes)))

    def to_payload(self) -> dict[str, object]:
        return {
            'valid': self.valid, 'same_run_angle_distinct': self.same_run_angle_distinct, 'exact_duplicate': self.exact_duplicate,
            'distinct_factors': list(self.distinct_factors), 'nearest_prior_refs': list(self.nearest_prior_refs),
            'reason_codes': list(self.reason_codes), 'input_hashes': dict(self.input_hashes),
            'registry_revision': self.registry_revision, 'phase': self.phase,
            'variation_policy_revision': self.variation_policy_revision,
            'own_reservation_id': self.own_reservation_id, 'output_hash': self.output_hash,
        }

    @property
    def validation_hash(self) -> str:
        return request_hash(self.to_payload())

    def is_current_for(self, *, registry_revision: int, phase: str, output_hash: str | None = None) -> bool:
        """Đúng khi cùng registry revision và cùng phase; phase output còn bắt buộc đúng exact output hash. Kết quả phase plan không bao giờ xác nhận output."""
        if self.registry_revision != registry_revision or self.phase != phase:
            return False
        if phase == PHASE_OUTPUT:
            return self.output_hash is not None and self.output_hash == output_hash
        return output_hash is None


def _items(values: object, cls: type, field: str) -> tuple:
    if isinstance(values, (str, bytes, Mapping)) or not isinstance(values, Iterable):
        _reject(INVALID_INPUT, 'wrong_type', field)
    items = tuple(values)
    for index, item in enumerate(items):
        if not isinstance(item, cls):
            _reject(INVALID_INPUT, 'wrong_type', f'{field}[{index}]')
    return items


def _unique(ids: list[str], field: str) -> None:
    if len(set(ids)) != len(ids):
        _reject(INVALID_INPUT, 'duplicate_ref', field)


def _check_arguments(candidate, registry_revision, variation_policy_revision, phase, own_reservation_id, output_hash) -> str:
    """Kiểm các đầu vào vô hướng; trả về variation policy revision."""
    if not isinstance(candidate, VariantFingerprint):
        _reject(INVALID_INPUT, 'wrong_type', 'candidate')
    if isinstance(registry_revision, bool) or not isinstance(registry_revision, int) or registry_revision < 0:
        _reject(INPUT_NOT_READY, 'missing_registry_revision', 'registry_revision')
    policy = _require_text(variation_policy_revision, 'missing_variation_policy_revision', 'variation_policy_revision')
    if phase not in PHASES:
        _reject(INVALID_INPUT, 'unknown_phase', 'phase')
    if own_reservation_id is not None:
        _require_text(own_reservation_id, 'missing_own_reservation_id', 'own_reservation_id')
    if phase == PHASE_OUTPUT:
        if output_hash is None:
            _reject(INPUT_NOT_READY, 'missing_output_hash', 'output_hash')
        _require_sha256(output_hash, 'output_hash')
    elif output_hash is not None:
        _reject(INVALID_INPUT, 'output_hash_not_allowed_in_plan_phase', 'output_hash')
    return policy


def _prior_entries(items) -> list[dict[str, object]]:
    return sorted(
        ({'ref_id': item.ref_id, 'fingerprint': item.fingerprint.fingerprint, 'factors': dict(item.fingerprint.factors)} for item in items),
        key=lambda entry: entry['ref_id'],
    )


def _reservation_entries(items) -> list[dict[str, object]]:
    return sorted(
        (
            {'reservation_id': item.reservation_id, 'fingerprint': item.fingerprint, 'committed_registry_revision': item.committed_registry_revision}
            for item in items
        ),
        key=lambda entry: entry['reservation_id'],
    )


def _input_hashes(candidate, history, siblings, others, phase, output_hash) -> dict[str, str]:
    hashes = {
        'candidate': request_hash(candidate.to_payload()),
        'completed_history': request_hash(_prior_entries(history)),
        'active_reservations': request_hash(_reservation_entries(others)),
        'same_run': request_hash(_prior_entries(siblings)),
    }
    if phase == PHASE_OUTPUT:
        hashes['output'] = output_hash
    return hashes


def validate_variant(
    *, candidate, completed, active_reservations, registry_revision, same_run, variation_policy_revision, phase,
    own_reservation_id=None, output_hash=None,
) -> VariantValidationResult:
    """CT-AI-008 ValidateVariant: thuần, không gọi AI, không tạo hay release reservation.

    Cùng lượt trùng góc → invalid. Giữa các lượt: exact duplicate (kể cả trùng reservation ACTIVE của job khác) hoặc có video completed không khác yếu tố nào → invalid. Reservation có reservation_id == own_reservation_id bị loại, job khác vẫn tính. Reservation chỉ mang fingerprint tổng nên chỉ đối chiếu exact; yếu tố khác biệt tính trên lịch sử completed (không có lịch sử → mọi yếu tố).
    """
    policy = _check_arguments(candidate, registry_revision, variation_policy_revision, phase, own_reservation_id, output_hash)
    history = _items(completed, CompletedVariant, 'completed')
    siblings = _items(same_run, SameRunVariant, 'same_run')
    reservations = _items(active_reservations, VariantReservation, 'active_reservations')
    _unique([item.ref_id for item in history], 'completed')
    _unique([item.ref_id for item in siblings], 'same_run')
    _unique([item.reservation_id for item in reservations], 'active_reservations')
    for index, item in enumerate(reservations):
        if item.reservation_id != own_reservation_id and item.state is not ReservationState.ACTIVE:
            _reject(INVALID_INPUT, 'reservation_not_active', f'active_reservations[{index}]')
    others = tuple(item for item in reservations if item.reservation_id != own_reservation_id)
    factors = candidate.factors
    same_angle = [item.ref_id for item in siblings if item.fingerprint.factors[FACTOR_ANGLE] == factors[FACTOR_ANGLE]]
    diffs = {item.ref_id: tuple(name for name in DISTINCT_FACTORS if factors[name] != item.fingerprint.factors[name]) for item in history}
    exact_refs = [item.ref_id for item in history if item.fingerprint.fingerprint == candidate.fingerprint]
    exact_refs += [item.reservation_id for item in others if item.fingerprint == candidate.fingerprint]
    pool = [(len(diff), ref) for ref, diff in diffs.items()]
    pool += [(0, item.reservation_id) for item in others if item.fingerprint == candidate.fingerprint]
    closest = min((distance for distance, _ in pool), default=None)
    nearest = tuple(sorted(ref for distance, ref in pool if distance == closest))
    distinct = diffs[min(diffs, key=lambda ref: (len(diffs[ref]), ref))] if diffs else DISTINCT_FACTORS
    reasons = []
    if same_angle:
        reasons.append(REASON_SAME_RUN_ANGLE_DUPLICATE)
    if exact_refs:
        reasons.append(REASON_EXACT_DUPLICATE)
    if any(not diff for diff in diffs.values()):
        reasons.append(REASON_NO_DISTINCT_FACTOR)
    return VariantValidationResult(
        valid=not reasons, same_run_angle_distinct=not same_angle, exact_duplicate=bool(exact_refs),
        distinct_factors=tuple(distinct), nearest_prior_refs=nearest, reason_codes=tuple(reasons) or (REASON_VALID,),
        input_hashes=_input_hashes(candidate, history, siblings, others, phase, output_hash),
        registry_revision=registry_revision, phase=phase, variation_policy_revision=policy,
        own_reservation_id=own_reservation_id, output_hash=output_hash,
    )
