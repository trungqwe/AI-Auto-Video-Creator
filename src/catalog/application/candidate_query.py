"""Media candidate query for D (CT-MED-005, BINDING-C-D-MEDIA-CANDIDATES).

C returns component scores and evidence, never one opaque score, and keeps index order:
D makes the final choice. Unknown additive query fields are ignored.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from types import MappingProxyType

from catalog.domain.identity import MediaKind
from catalog.domain.states import Availability, Usability, classify_availability

MISSING_REQUIRED = "missing_required"
WRONG_TYPE = "wrong_type"
INVALID_VALUE = "invalid_value"
ENUM_VIOLATION = "enum_violation"
CURSOR_PREFIX = "offset:"
MATCH_COMPONENTS = ("entity", "topic", "scene")

QUERY_REQUIRED = MappingProxyType({
    "production_snapshot_ref": "string",
    "scene_intent": "object",
    "media_kinds": "array",
    "roles": "array",
    "safety_policy_revision": "string",
    "limit": "integer",
})
QUERY_OPTIONAL = MappingProxyType({
    "technical_constraints": "object",
    "recency_diversity_preferences": "object",
    "excluded_usage_refs": "array",
    "page_cursor": "string",
})
QUERY_ITEMS = MappingProxyType({"media_kinds": "string", "roles": "string", "excluded_usage_refs": "string"})
CANDIDATE_REQUIRED = MappingProxyType({
    "media_asset_id": "string",
    "rendition_ref": "string",
    "artifact_version_ref": "string",
    "provenance": "object",
    "semantic_match_components": "object",
    "technical_fitness": "object",
    "availability": "string",
    "safety_rights_status": "object",
    "recent_usage_summary": "object",
    "reason_codes": "array",
})
CANDIDATE_ITEMS = MappingProxyType({"reason_codes": "string"})
_NO_FIELDS = MappingProxyType({})
_AVAILABILITY_VALUES = frozenset(a.value for a in Availability)
_CURSOR_PATTERN = re.compile(r"offset:(0|[1-9]\d*)")


class ContractError(ValueError):
    """Boundary violation of BINDING-C-D-MEDIA-CANDIDATES."""

    def __init__(self, code: str, field: str) -> None:
        super().__init__(f"{code}: {field}")
        self.code = code
        self.field = field


@dataclass(frozen=True, slots=True)
class CandidateIndexEntry:
    """One searchable rendition; semantics, technical and safety data come from other capabilities."""

    media_asset_id: str
    rendition_ref: str
    artifact_version_ref: str
    kind: MediaKind
    roles: tuple[str, ...]
    entities: tuple[str, ...]
    topics: tuple[str, ...]
    scenes: tuple[str, ...]
    provenance: dict
    technical_fitness: dict
    availability: Availability
    safety_rights_status: dict
    usage_refs: tuple[str, ...]


def _matches_type(value: object, type_name: str) -> bool:
    if type_name == "string":
        return isinstance(value, str)
    if type_name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if type_name == "object":
        return isinstance(value, dict)
    if type_name == "array":
        return isinstance(value, list)
    return False


def _check(payload: object, required: MappingProxyType, optional: MappingProxyType, items: MappingProxyType) -> None:
    if not isinstance(payload, dict):
        raise ContractError(WRONG_TYPE, "$")
    for name, type_name in (*required.items(), *optional.items()):
        if name not in payload or (name in optional and payload[name] is None):
            if name in required:
                raise ContractError(MISSING_REQUIRED, name)
            continue
        value = payload[name]
        if not _matches_type(value, type_name):
            raise ContractError(WRONG_TYPE, name)
        if name in items and any(not _matches_type(item, items[name]) for item in value):
            raise ContractError(WRONG_TYPE, name)


def parse_media_candidate_query(payload: dict) -> dict:
    """Return the known MediaCandidateQuery fields; unknown additive fields are dropped."""
    _check(payload, QUERY_REQUIRED, QUERY_OPTIONAL, QUERY_ITEMS)
    if payload["limit"] < 1:
        raise ContractError(INVALID_VALUE, "limit")
    cursor = payload.get("page_cursor")
    if cursor is not None and _CURSOR_PATTERN.fullmatch(cursor) is None:
        raise ContractError(INVALID_VALUE, "page_cursor")
    return {name: payload[name] for name in (*QUERY_REQUIRED, *QUERY_OPTIONAL) if payload.get(name) is not None}


def validate_media_candidate(payload: dict) -> dict:
    """Check one MediaCandidate: component scores in 0..1, no aggregate score, reason codes present."""
    _check(payload, CANDIDATE_REQUIRED, _NO_FIELDS, CANDIDATE_ITEMS)
    for key, value in payload["semantic_match_components"].items():
        if key not in MATCH_COMPONENTS:
            raise ContractError(INVALID_VALUE, "semantic_match_components")
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ContractError(WRONG_TYPE, "semantic_match_components")
        if not 0 <= value <= 1:
            raise ContractError(INVALID_VALUE, "semantic_match_components")
    if payload["availability"] not in _AVAILABILITY_VALUES:
        raise ContractError(ENUM_VIOLATION, "availability")
    if not payload["reason_codes"]:
        raise ContractError(INVALID_VALUE, "reason_codes")
    return payload


def _match_ratio(have: tuple[str, ...], wanted: object) -> float:
    terms = {term for term in wanted if isinstance(term, str)} if isinstance(wanted, list) else set()
    if not terms:
        return 0.0
    return len(terms & set(have)) / len(terms)


def _to_candidate(entry: CandidateIndexEntry, scene_intent: dict) -> dict:
    components = {
        "entity": _match_ratio(entry.entities, scene_intent.get("entities")),
        "topic": _match_ratio(entry.topics, scene_intent.get("topics")),
        "scene": _match_ratio(entry.scenes, scene_intent.get("scenes")),
    }
    availability = Availability(entry.availability)
    reason_codes = ["KIND_MATCH", "ROLE_MATCH"]
    reason_codes += [f"{name.upper()}_MATCH" for name in MATCH_COMPONENTS if components[name] > 0]
    if availability is Availability.UNAVAILABLE_SOURCE:
        reason_codes.append("SOURCE_UNAVAILABLE")
    return {
        "media_asset_id": entry.media_asset_id,
        "rendition_ref": entry.rendition_ref,
        "artifact_version_ref": entry.artifact_version_ref,
        "provenance": dict(entry.provenance),
        "semantic_match_components": components,
        "technical_fitness": dict(entry.technical_fitness),
        "availability": availability.value,
        "safety_rights_status": dict(entry.safety_rights_status),
        "recent_usage_summary": {"times_used": len(entry.usage_refs)},
        "reason_codes": reason_codes,
    }


def query_media_candidates(
    query: dict, entries: Iterable[CandidateIndexEntry]
) -> tuple[list[dict], str | None]:
    """Return one page of eligible candidates in index order and the next ``offset:<n>`` cursor."""
    parsed = parse_media_candidate_query(query)
    kinds = set(parsed["media_kinds"])
    roles = set(parsed["roles"])
    excluded = set(parsed.get("excluded_usage_refs", ()))
    eligible = [
        entry
        for entry in entries
        if MediaKind(entry.kind).value in kinds
        and roles.intersection(entry.roles)
        and classify_availability(entry.availability) is not Usability.NOT_USABLE
        and not excluded.intersection(entry.usage_refs)
    ]
    cursor = parsed.get("page_cursor")
    offset = int(cursor[len(CURSOR_PREFIX):]) if cursor is not None else 0
    end = offset + parsed["limit"]
    candidates = [
        validate_media_candidate(_to_candidate(entry, parsed["scene_intent"])) for entry in eligible[offset:end]
    ]
    return candidates, (f"{CURSOR_PREFIX}{end}" if end < len(eligible) else None)