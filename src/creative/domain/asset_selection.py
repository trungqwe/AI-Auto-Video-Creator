"""Creative asset selection (CT-AI-006) over media candidates (CT-MED-005); D side of BINDING-C-D-MEDIA-CANDIDATES.

Constants mirror the binding; unknown additive fields are ignored. Hook and thumbnail candidates (CT-MED-004/006) have no
binding yet, so they are D-local value objects (CONV-D-07). Pure domain: no I/O, no clock, no id generation, no AI call;
policies, weights and revisions are caller input and the module has no hidden default for them.
"""
from __future__ import annotations

import copy
import dataclasses
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from controlplane.application.idempotency.canonicalization import request_hash
from creative.domain.ref_resolver import RefResolver, ResourceRef

MISSING_REQUIRED = 'missing_required'
WRONG_TYPE = 'wrong_type'
INPUT_NOT_READY = 'INPUT_NOT_READY'
MISSING_REQUIRED_HOOK = 'missing_required_hook'
HALLUCINATED_REF = 'hallucinated_ref'
CANDIDATE_BLOCKED = 'candidate_blocked'
INVALID_PROPOSAL = 'invalid_proposal'
SEED_SCENE_WITH_ILLUSTRATION = 'seed_scene_while_illustration_eligible'
BINDING_VERSION = '1.0.0'
ORIGIN_SEED = 'seed'

REF_TYPE_MEDIA = 'media_asset'
REF_TYPE_VISUAL_HOOK = 'visual_hook'
REF_TYPE_AUDIO_HOOK = 'audio_hook'
REF_TYPE_THUMBNAIL = 'thumbnail'
HOOK_KINDS = (REF_TYPE_VISUAL_HOOK, REF_TYPE_AUDIO_HOOK)
SELECTION_REF_TYPES = (REF_TYPE_MEDIA, REF_TYPE_VISUAL_HOOK, REF_TYPE_AUDIO_HOOK, REF_TYPE_THUMBNAIL)
REQUIRED_SLOTS = (REF_TYPE_VISUAL_HOOK, REF_TYPE_AUDIO_HOOK, REF_TYPE_THUMBNAIL)

QUERY_REQUIRED = MappingProxyType({
    'production_snapshot_ref': 'string',
    'scene_intent': 'object',
    'media_kinds': 'array',
    'roles': 'array',
    'safety_policy_revision': 'string',
    'limit': 'integer',
})
QUERY_OPTIONAL = MappingProxyType({
    'technical_constraints': 'object',
    'recency_diversity_preferences': 'object',
    'excluded_usage_refs': 'array',
    'page_cursor': 'string',
})
QUERY_ITEMS = MappingProxyType({'media_kinds': 'string', 'roles': 'string'})
CANDIDATE_REQUIRED = MappingProxyType({
    'media_asset_id': 'string',
    'rendition_ref': 'string',
    'artifact_version_ref': 'string',
    'provenance': 'object',
    'semantic_match_components': 'object',
    'technical_fitness': 'object',
    'availability': 'string',
    'safety_rights_status': 'object',
    'recent_usage_summary': 'object',
    'reason_codes': 'array',
})
CANDIDATE_OPTIONAL = MappingProxyType({})
CANDIDATE_ITEMS = MappingProxyType({'reason_codes': 'string'})


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    field: str


class SelectionRejected(Exception):
    """Inputs or proposal cannot produce a selection: `code` is INPUT_NOT_READY, missing_required_hook, hallucinated_ref, candidate_blocked or invalid_proposal; `reason` is the stable machine reason; `field` locates it."""

    def __init__(self, code: str, reason: str, field: str = '') -> None:
        super().__init__(f'{code}: {reason}' + (f' ({field})' if field else ''))
        self.code = code
        self.reason = reason
        self.field = field


def matches_type(value: object, type_name: str) -> bool:
    if type_name == 'string':
        return isinstance(value, str)
    if type_name == 'integer':
        return isinstance(value, int) and not isinstance(value, bool)
    if type_name == 'object':
        return isinstance(value, dict)
    if type_name == 'array':
        return isinstance(value, list)
    return False


def _validate(payload: object, required: Mapping[str, str], optional: Mapping[str, str], items: Mapping[str, str]) -> list[ValidationIssue]:
    if not isinstance(payload, Mapping):
        return [ValidationIssue(WRONG_TYPE, '$')]
    issues: list[ValidationIssue] = []
    for name, type_name in (*required.items(), *optional.items()):
        if name not in payload:
            if name in required:
                issues.append(ValidationIssue(MISSING_REQUIRED, name))
            continue
        value = payload[name]
        if value is None:
            if name in required:
                issues.append(ValidationIssue(WRONG_TYPE, name))
            continue
        if not matches_type(value, type_name):
            issues.append(ValidationIssue(WRONG_TYPE, name))
        elif name in items and any(not matches_type(item, items[name]) for item in value):
            issues.append(ValidationIssue(WRONG_TYPE, name))
    return issues


def validate_media_candidate_query(payload: object) -> list[ValidationIssue]:
    """Return boundary issues of a MediaCandidateQuery payload (CT-MED-005); empty list means valid."""
    return _validate(payload, QUERY_REQUIRED, QUERY_OPTIONAL, QUERY_ITEMS)


def validate_media_candidate(payload: object) -> list[ValidationIssue]:
    """Return boundary issues of a MediaCandidate payload (CT-MED-005); empty list means valid."""
    return _validate(payload, CANDIDATE_REQUIRED, CANDIDATE_OPTIONAL, CANDIDATE_ITEMS)


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f'{name} must be a non-empty string')
    return value


def _texts(name: str, values: object) -> tuple[str, ...]:
    if isinstance(values, (str, bytes, Mapping)) or not isinstance(values, Iterable):
        raise ValueError(f'{name} must be an iterable, not a string or mapping')
    return tuple(_text(f'{name} item', item) for item in values)


def _frozen_mapping(name: str, value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f'{name} must be a mapping')
    return MappingProxyType(copy.deepcopy(dict(value)))


def _pin_fields(instance: object, texts: tuple[str, ...], mappings: tuple[str, ...]) -> None:
    for name in texts:
        _text(name, getattr(instance, name))
    for name in mappings:
        object.__setattr__(instance, name, _frozen_mapping(name, getattr(instance, name)))


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


@dataclass(frozen=True, kw_only=True)
class MediaCandidateQuery:
    """CT-MED-005 request value; mappings are read-only copies, so later changes to caller input never reach it."""

    production_snapshot_ref: str
    scene_intent: Mapping[str, object]
    media_kinds: tuple[str, ...]
    roles: tuple[str, ...]
    safety_policy_revision: str
    limit: int
    technical_constraints: Mapping[str, object] | None = None
    recency_diversity_preferences: Mapping[str, object] | None = None
    excluded_usage_refs: tuple[str, ...] = ()
    page_cursor: str | None = None

    def to_payload(self) -> dict[str, object]:
        """Return the binding payload (plain dict/list); empty optional fields are omitted."""
        payload: dict[str, object] = {
            'production_snapshot_ref': self.production_snapshot_ref,
            'scene_intent': copy.deepcopy(dict(self.scene_intent)),
            'media_kinds': list(self.media_kinds),
            'roles': list(self.roles),
            'safety_policy_revision': self.safety_policy_revision,
            'limit': self.limit,
        }
        if self.technical_constraints is not None:
            payload['technical_constraints'] = copy.deepcopy(dict(self.technical_constraints))
        if self.recency_diversity_preferences is not None:
            payload['recency_diversity_preferences'] = copy.deepcopy(dict(self.recency_diversity_preferences))
        if self.excluded_usage_refs:
            payload['excluded_usage_refs'] = list(self.excluded_usage_refs)
        if self.page_cursor is not None:
            payload['page_cursor'] = self.page_cursor
        return payload


def build_media_candidate_query(
    *,
    production_snapshot_ref: str,
    scene_intent: Mapping[str, object],
    media_kinds: Iterable[str],
    roles: Iterable[str],
    safety_policy_revision: str | None,
    limit: int,
    technical_constraints: Mapping[str, object] | None = None,
    recency_diversity_preferences: Mapping[str, object] | None = None,
    excluded_usage_refs: Iterable[str] = (),
    page_cursor: str | None = None,
) -> MediaCandidateQuery:
    """Build the CT-MED-005 query and pass it through the binding validator.

    Raises SelectionRejected(INPUT_NOT_READY, reason) for a missing policy revision, scene intent, media kinds or roles,
    ValueError for malformed arguments.
    """
    _text('production_snapshot_ref', production_snapshot_ref)
    if safety_policy_revision is None or safety_policy_revision == '':
        raise SelectionRejected(INPUT_NOT_READY, 'missing_safety_policy_revision', 'safety_policy_revision')
    _text('safety_policy_revision', safety_policy_revision)
    scene = _frozen_mapping('scene_intent', scene_intent)
    if not scene:
        raise SelectionRejected(INPUT_NOT_READY, 'missing_scene_intent', 'scene_intent')
    kinds = tuple(dict.fromkeys(_texts('media_kinds', media_kinds)))
    if not kinds:
        raise SelectionRejected(INPUT_NOT_READY, 'missing_media_kinds', 'media_kinds')
    role_values = tuple(dict.fromkeys(_texts('roles', roles)))
    if not role_values:
        raise SelectionRejected(INPUT_NOT_READY, 'missing_roles', 'roles')
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError('limit must be a positive integer')
    query = MediaCandidateQuery(
        production_snapshot_ref=production_snapshot_ref,
        scene_intent=scene,
        media_kinds=kinds,
        roles=role_values,
        safety_policy_revision=safety_policy_revision,
        limit=limit,
        technical_constraints=None if technical_constraints is None else _frozen_mapping('technical_constraints', technical_constraints),
        recency_diversity_preferences=None if recency_diversity_preferences is None else _frozen_mapping('recency_diversity_preferences', recency_diversity_preferences),
        excluded_usage_refs=tuple(dict.fromkeys(_texts('excluded_usage_refs', excluded_usage_refs))),
        page_cursor=None if page_cursor is None else _text('page_cursor', page_cursor),
    )
    issues = validate_media_candidate_query(query.to_payload())
    if issues:
        raise ValueError(f'query failed boundary validation: {issues!r}')
    return query


class _RefMixin:
    def resource_ref(self, workspace_id: str) -> ResourceRef:
        return ResourceRef(workspace_id, self.ref_type, self.ref_id, self.ref_revision_id)


@dataclass(frozen=True, kw_only=True)
class MediaCandidate(_RefMixin):
    """CT-MED-005 candidate read from C; one candidate per media_asset_id (GIẢ ĐỊNH: C returns the best rendition)."""

    media_asset_id: str
    rendition_ref: str
    artifact_version_ref: str
    provenance: Mapping[str, object]
    semantic_match_components: Mapping[str, object]
    technical_fitness: Mapping[str, object]
    availability: str
    safety_rights_status: Mapping[str, object]
    recent_usage_summary: Mapping[str, object]
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        _pin_fields(
            self,
            ('media_asset_id', 'rendition_ref', 'artifact_version_ref', 'availability'),
            ('provenance', 'semantic_match_components', 'technical_fitness', 'safety_rights_status', 'recent_usage_summary'),
        )
        object.__setattr__(self, 'reason_codes', _texts('reason_codes', self.reason_codes))

    @property
    def ref_type(self) -> str:
        return REF_TYPE_MEDIA

    @property
    def ref_id(self) -> str:
        return self.media_asset_id

    @property
    def ref_revision_id(self) -> str:
        return self.artifact_version_ref

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {}
        for name in CANDIDATE_REQUIRED:
            value = getattr(self, name)
            payload[name] = copy.deepcopy(dict(value)) if isinstance(value, Mapping) else value
        payload['reason_codes'] = list(self.reason_codes)
        return payload


def parse_media_candidate(payload: object) -> MediaCandidate:
    """Read a MediaCandidate payload (e.g. a fixture) through the binding validator; raises ValueError on any issue."""
    issues = validate_media_candidate(payload)
    if issues:
        raise ValueError(f'media candidate failed boundary validation: {issues!r}')
    return MediaCandidate(**{name: payload[name] for name in CANDIDATE_REQUIRED})


@dataclass(frozen=True, kw_only=True)
class HookCandidate(_RefMixin):
    """D-local visual/audio hook candidate (CT-MED-006 has no binding yet, CONV-D-07)."""

    hook_kind: str
    hook_id: str
    revision_id: str
    availability: str
    safety_rights_status: Mapping[str, object]
    semantic_match_components: Mapping[str, object]
    provenance: Mapping[str, object]

    def __post_init__(self) -> None:
        if self.hook_kind not in HOOK_KINDS:
            raise ValueError(f'hook_kind must be one of {HOOK_KINDS!r}')
        _pin_fields(self, ('hook_id', 'revision_id', 'availability'), ('safety_rights_status', 'semantic_match_components', 'provenance'))

    @property
    def ref_type(self) -> str:
        return self.hook_kind

    @property
    def ref_id(self) -> str:
        return self.hook_id

    @property
    def ref_revision_id(self) -> str:
        return self.revision_id


@dataclass(frozen=True, kw_only=True)
class ThumbnailCandidate(_RefMixin):
    """D-local thumbnail candidate (CT-MED-004 has no binding yet, CONV-D-07)."""

    thumbnail_id: str
    revision_id: str
    subject_refs: tuple[str, ...]
    crop_focus: Mapping[str, object]
    overlay_intent: str
    availability: str
    safety_rights_status: Mapping[str, object]
    semantic_match_components: Mapping[str, object]
    provenance: Mapping[str, object]

    def __post_init__(self) -> None:
        _pin_fields(self, ('thumbnail_id', 'revision_id', 'overlay_intent', 'availability'), ('crop_focus', 'safety_rights_status', 'semantic_match_components', 'provenance'))
        object.__setattr__(self, 'subject_refs', _texts('subject_refs', self.subject_refs))

    @property
    def ref_type(self) -> str:
        return REF_TYPE_THUMBNAIL

    @property
    def ref_id(self) -> str:
        return self.thumbnail_id

    @property
    def ref_revision_id(self) -> str:
        return self.revision_id


@dataclass(frozen=True, kw_only=True)
class SafetyRightsPolicy:
    """Safety/rights policy passed by the caller: a candidate is eligible only if its availability is allowed, every required flag is True in safety_rights_status and no blocked flag is True."""

    revision: str
    allowed_availability: frozenset[str]
    required_flags: frozenset[str]
    blocked_flags: frozenset[str]

    def __post_init__(self) -> None:
        if not isinstance(self.revision, str) or not self.revision:
            raise SelectionRejected(INPUT_NOT_READY, 'missing_safety_policy_revision', 'revision')
        for name in ('allowed_availability', 'required_flags', 'blocked_flags'):
            object.__setattr__(self, name, frozenset(_texts(name, getattr(self, name))))
        if not self.allowed_availability:
            raise SelectionRejected(INPUT_NOT_READY, 'missing_allowed_availability', 'allowed_availability')

    def allows(self, availability: str, status: Mapping[str, object]) -> bool:
        if availability not in self.allowed_availability:
            return False
        if any(status.get(flag) is not True for flag in self.required_flags):
            return False
        return not any(status.get(flag) is True for flag in self.blocked_flags)


@dataclass(frozen=True, kw_only=True)
class ScoringWeights:
    """Caller-supplied weights; score = semantic*w + technical*w - times_used*recent_usage_penalty."""

    semantic: float
    technical: float
    recent_usage_penalty: float

    def __post_init__(self) -> None:
        for name in ('semantic', 'technical', 'recent_usage_penalty'):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f'{name} must be a finite non-negative number')


@dataclass(frozen=True, kw_only=True)
class SceneAssignment:
    order: int
    scene_id: str
    media_asset_id: str
    rendition_ref: str
    artifact_version_ref: str
    rationale: str
    origin: str | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            'order': self.order,
            'scene_id': self.scene_id,
            'media_asset_id': self.media_asset_id,
            'rendition_ref': self.rendition_ref,
            'artifact_version_ref': self.artifact_version_ref,
            'rationale': self.rationale,
        }
        if self.origin is not None:
            payload['origin'] = self.origin
        return payload


@dataclass(frozen=True, kw_only=True)
class FallbackCandidate:
    media_asset_id: str
    rendition_ref: str
    artifact_version_ref: str
    total_score: float

    def to_payload(self) -> dict[str, object]:
        return {
            'media_asset_id': self.media_asset_id,
            'rendition_ref': self.rendition_ref,
            'artifact_version_ref': self.artifact_version_ref,
            'total_score': self.total_score,
        }


def _ref_payload(ref: ResourceRef) -> dict[str, str]:
    return {'workspace_id': ref.workspace_id, 'ref_type': ref.ref_type, 'ref_id': ref.ref_id, 'revision_id': ref.revision_id}


@dataclass(frozen=True, kw_only=True)
class CreativeAssetSelection:
    """CT-AI-006 output; selection_fingerprint hashes refs, order, intents, fallbacks and revisions, never rationale or scores."""

    snapshot_ref: str
    script_ref: str
    angle_ref: str
    safety_policy_revision: str
    music_sfx_policy_revision: str
    preset_registry_revision: str
    visual_hook: ResourceRef
    audio_hook: ResourceRef
    thumbnail: ResourceRef
    thumbnail_overlay_intent: str
    assignments: tuple[SceneAssignment, ...]
    music_intents: tuple[Mapping[str, str], ...]
    sfx_intents: tuple[Mapping[str, str], ...]
    fallback_candidates: tuple[FallbackCandidate, ...]
    rationale: str
    score_components: Mapping[str, Mapping[str, float]]
    selection_fingerprint: str = ''

    def fingerprint_basis(self) -> dict[str, object]:
        return {
            'snapshot_ref': self.snapshot_ref,
            'script_ref': self.script_ref,
            'angle_ref': self.angle_ref,
            'safety_policy_revision': self.safety_policy_revision,
            'music_sfx_policy_revision': self.music_sfx_policy_revision,
            'preset_registry_revision': self.preset_registry_revision,
            'visual_hook': _ref_payload(self.visual_hook),
            'audio_hook': _ref_payload(self.audio_hook),
            'thumbnail': _ref_payload(self.thumbnail),
            'thumbnail_overlay_intent': self.thumbnail_overlay_intent,
            'assignments': [{k: v for k, v in a.to_payload().items() if k != 'rationale'} for a in self.assignments],
            'music_intents': [dict(item) for item in self.music_intents],
            'sfx_intents': [dict(item) for item in self.sfx_intents],
            'fallback_candidates': [{k: v for k, v in f.to_payload().items() if k != 'total_score'} for f in self.fallback_candidates],
        }

    def compute_fingerprint(self) -> str:
        return request_hash(self.fingerprint_basis())

    def to_payload(self) -> dict[str, object]:
        payload = self.fingerprint_basis()
        payload['assignments'] = [a.to_payload() for a in self.assignments]
        payload['fallback_candidates'] = [f.to_payload() for f in self.fallback_candidates]
        payload['rationale'] = self.rationale
        payload['score_components'] = {key: dict(value) for key, value in self.score_components.items()}
        payload['selection_fingerprint'] = self.selection_fingerprint
        return payload


def _checked(name: str, items: object, cls: type) -> tuple:
    if isinstance(items, (str, bytes, Mapping)) or not isinstance(items, Iterable):
        raise TypeError(f'{name} must be an iterable of {cls.__name__}')
    values = tuple(items)
    if not all(isinstance(item, cls) for item in values):
        raise TypeError(f'{name} items must be {cls.__name__}')
    return values


def _split_by_policy(items: tuple, policy: SafetyRightsPolicy) -> tuple[list, set[tuple[str, str]]]:
    eligible = []
    blocked: set[tuple[str, str]] = set()
    for item in items:
        if policy.allows(item.availability, item.safety_rights_status):
            eligible.append(item)
        else:
            blocked.add((item.ref_type, item.ref_id))
    return eligible, blocked


def _resolve_pick(resolver: RefResolver, blocked: set[tuple[str, str]], proposed: object, expected_type: str, field: str) -> ResourceRef:
    if not isinstance(proposed, Mapping):
        raise SelectionRejected(INVALID_PROPOSAL, 'not_a_mapping', field)
    resolution = resolver.resolve(proposed)
    if not resolution.ok:
        ref_type, ref_id = proposed.get('ref_type'), proposed.get('ref_id')
        if isinstance(ref_type, str) and isinstance(ref_id, str) and (ref_type, ref_id) in blocked:
            raise SelectionRejected(CANDIDATE_BLOCKED, 'safety_rights_policy', field)
        raise SelectionRejected(HALLUCINATED_REF, resolution.reason or 'unknown_ref', field)
    if resolution.ref.ref_type != expected_type:
        raise SelectionRejected(HALLUCINATED_REF, 'ref_type_mismatch', field)
    return resolution.ref


def _required_text(proposal: Mapping[str, object], key: str, field: str) -> str:
    value = proposal.get(key)
    if not isinstance(value, str) or not value:
        raise SelectionRejected(INVALID_PROPOSAL, f'{key}_missing', field)
    return value


def _intents(proposal: Mapping[str, object], key: str) -> tuple[Mapping[str, str], ...]:
    items = proposal.get(key)
    if not isinstance(items, list):
        raise SelectionRejected(INVALID_PROPOSAL, f'{key}_missing', key)
    result = []
    for index, item in enumerate(items):
        field = f'{key}[{index}]'
        if not isinstance(item, Mapping):
            raise SelectionRejected(INVALID_PROPOSAL, 'not_a_mapping', field)
        cue, description = item.get('cue'), item.get('description')
        if not (isinstance(cue, str) and cue and isinstance(description, str) and description):
            raise SelectionRejected(INVALID_PROPOSAL, 'cue_and_description_required', field)
        result.append(MappingProxyType({'cue': cue, 'description': description}))
    return tuple(result)


def _score_components(candidate: MediaCandidate, weights: ScoringWeights) -> dict[str, float]:
    numbers = [n for n in (_number(v) for v in candidate.semantic_match_components.values()) if n is not None]
    semantic = sum(numbers) / len(numbers) if numbers else 0.0
    technical = _number(candidate.technical_fitness.get('score')) or 0.0
    recent_usage = _number(candidate.recent_usage_summary.get('times_used')) or 0.0
    total = weights.semantic * semantic + weights.technical * technical - weights.recent_usage_penalty * recent_usage
    return {'semantic': round(semantic, 6), 'technical': round(technical, 6), 'recent_usage': round(recent_usage, 6), 'total': round(total, 6)}


def _origin_of(candidate: MediaCandidate) -> str | None:
    """Provenance origin text of a media candidate; None when it has none."""
    origin = candidate.provenance.get('origin')
    return origin if isinstance(origin, str) and origin else None


def select_creative_assets(
    *,
    workspace_id: str,
    snapshot_ref: str,
    script_ref: str,
    angle_ref: str,
    media_candidates: Iterable[MediaCandidate],
    visual_hook_candidates: Iterable[HookCandidate],
    audio_hook_candidates: Iterable[HookCandidate],
    thumbnail_candidates: Iterable[ThumbnailCandidate],
    proposal: Mapping[str, object],
    safety_policy: SafetyRightsPolicy | None,
    music_sfx_policy_revision: str | None,
    preset_registry_revision: str | None,
    weights: ScoringWeights | None,
) -> CreativeAssetSelection:
    """Validate a model proposal against the received candidate sets (CT-AI-006).

    Candidates failing safety_policy are dropped; every proposed ref must resolve through the D-03 RefResolver built from the
    eligible candidates only. Raises SelectionRejected (INPUT_NOT_READY, missing_required_hook, hallucinated_ref,
    candidate_blocked, invalid_proposal); TypeError/ValueError for malformed candidates.
    A scene on a seed image is rejected (invalid_proposal, seed_scene_while_illustration_eligible) when an eligible candidate has an origin other than seed.
    """
    for name, value in (('workspace_id', workspace_id), ('snapshot_ref', snapshot_ref), ('script_ref', script_ref), ('angle_ref', angle_ref)):
        _text(name, value)
    if not isinstance(safety_policy, SafetyRightsPolicy):
        raise SelectionRejected(INPUT_NOT_READY, 'missing_safety_policy', 'safety_policy')
    if not isinstance(music_sfx_policy_revision, str) or not music_sfx_policy_revision:
        raise SelectionRejected(INPUT_NOT_READY, 'missing_music_sfx_policy_revision', 'music_sfx_policy_revision')
    if not isinstance(preset_registry_revision, str) or not preset_registry_revision:
        raise SelectionRejected(INPUT_NOT_READY, 'missing_preset_registry_revision', 'preset_registry_revision')
    if not isinstance(weights, ScoringWeights):
        raise SelectionRejected(INPUT_NOT_READY, 'missing_scoring_weights', 'weights')
    media = _checked('media_candidates', media_candidates, MediaCandidate)
    visual = _checked('visual_hook_candidates', visual_hook_candidates, HookCandidate)
    audio = _checked('audio_hook_candidates', audio_hook_candidates, HookCandidate)
    thumbnails = _checked('thumbnail_candidates', thumbnail_candidates, ThumbnailCandidate)
    if any(item.hook_kind != REF_TYPE_VISUAL_HOOK for item in visual) or any(item.hook_kind != REF_TYPE_AUDIO_HOOK for item in audio):
        raise ValueError('hook candidates must match their hook kind')
    if not isinstance(proposal, Mapping):
        raise SelectionRejected(INVALID_PROPOSAL, 'proposal_not_mapping', '$')
    for slot in REQUIRED_SLOTS:
        if proposal.get(slot) is None:
            raise SelectionRejected(MISSING_REQUIRED_HOOK, slot, slot)
    eligible_media, blocked = _split_by_policy(media, safety_policy)
    eligible_visual, blocked_visual = _split_by_policy(visual, safety_policy)
    eligible_audio, blocked_audio = _split_by_policy(audio, safety_policy)
    eligible_thumbnails, blocked_thumbnails = _split_by_policy(thumbnails, safety_policy)
    blocked = blocked | blocked_visual | blocked_audio | blocked_thumbnails
    eligible = [*eligible_media, *eligible_visual, *eligible_audio, *eligible_thumbnails]
    resolver = RefResolver(
        workspace_id=workspace_id,
        allowed_refs=[item.resource_ref(workspace_id) for item in eligible],
        allowed_ref_types=SELECTION_REF_TYPES,
    )
    visual_ref = _resolve_pick(resolver, blocked, proposal['visual_hook'], REF_TYPE_VISUAL_HOOK, 'visual_hook')
    audio_ref = _resolve_pick(resolver, blocked, proposal['audio_hook'], REF_TYPE_AUDIO_HOOK, 'audio_hook')
    thumbnail_ref = _resolve_pick(resolver, blocked, proposal['thumbnail'], REF_TYPE_THUMBNAIL, 'thumbnail')
    thumbnail = next(item for item in eligible_thumbnails if item.ref_id == thumbnail_ref.ref_id)
    media_by_id = {item.media_asset_id: item for item in eligible_media}
    illustrated = any(_origin_of(item) != ORIGIN_SEED for item in eligible_media)
    scenes = proposal.get('scenes')
    if not isinstance(scenes, list) or not scenes:
        raise SelectionRejected(INVALID_PROPOSAL, 'scenes_missing', 'scenes')
    assignments: list[SceneAssignment] = []
    seen: set[str] = set()
    for index, scene in enumerate(scenes):
        field = f'scenes[{index}]'
        if not isinstance(scene, Mapping):
            raise SelectionRejected(INVALID_PROPOSAL, 'not_a_mapping', field)
        scene_id = _required_text(scene, 'scene_id', f'{field}.scene_id')
        if scene_id in seen:
            raise SelectionRejected(INVALID_PROPOSAL, 'duplicate_scene_id', f'{field}.scene_id')
        seen.add(scene_id)
        rationale = _required_text(scene, 'rationale', f'{field}.rationale')
        ref = _resolve_pick(resolver, blocked, scene.get('ref'), REF_TYPE_MEDIA, f'{field}.ref')
        candidate = media_by_id[ref.ref_id]
        origin = _origin_of(candidate)
        if illustrated and origin == ORIGIN_SEED:
            raise SelectionRejected(INVALID_PROPOSAL, SEED_SCENE_WITH_ILLUSTRATION, f'{field}.ref')
        assignments.append(SceneAssignment(
            order=index, scene_id=scene_id, media_asset_id=candidate.media_asset_id,
            rendition_ref=candidate.rendition_ref, artifact_version_ref=candidate.artifact_version_ref, rationale=rationale,
            origin=origin))
    music_intents = _intents(proposal, 'music_intents')
    sfx_intents = _intents(proposal, 'sfx_intents')
    overall_rationale = _required_text(proposal, 'rationale', 'rationale')
    components = {item.media_asset_id: _score_components(item, weights) for item in eligible_media}
    used = {assignment.media_asset_id for assignment in assignments}
    # DQ-11: an image that still needs AssessImageSafety is chosen for a scene only, never offered as a fallback replacement.
    ranked = sorted(
        (item for item in eligible_media if item.media_asset_id not in used and item.safety_rights_status.get('needs_image_safety') is not True),
        key=lambda item: (-components[item.media_asset_id]['total'], item.media_asset_id))
    selection = CreativeAssetSelection(
        snapshot_ref=snapshot_ref, script_ref=script_ref, angle_ref=angle_ref,
        safety_policy_revision=safety_policy.revision, music_sfx_policy_revision=music_sfx_policy_revision,
        preset_registry_revision=preset_registry_revision,
        visual_hook=visual_ref, audio_hook=audio_ref, thumbnail=thumbnail_ref, thumbnail_overlay_intent=thumbnail.overlay_intent,
        assignments=tuple(assignments), music_intents=music_intents, sfx_intents=sfx_intents,
        fallback_candidates=tuple(FallbackCandidate(
            media_asset_id=item.media_asset_id, rendition_ref=item.rendition_ref,
            artifact_version_ref=item.artifact_version_ref, total_score=components[item.media_asset_id]['total']) for item in ranked),
        rationale=overall_rationale,
        score_components=MappingProxyType({key: MappingProxyType(value) for key, value in components.items()}),
    )
    return dataclasses.replace(selection, selection_fingerprint=selection.compute_fingerprint())
