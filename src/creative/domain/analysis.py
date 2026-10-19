"""ContentAnalysis value and boundary parser (CT-AI-002, CT-AI-000).

Pure domain: no I/O, no clock, no id generation.
The parser only reads documented keys; model self-assessment fields do not decide validity.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from creative.domain.ref_resolver import RefResolver, ResourceRef
from creative.domain.snapshot import ENUM_VIOLATION, MISSING_REQUIRED, WRONG_TYPE, ProductionSnapshot
from creative.domain.untrusted import PROMPT_REVISION_REF_TYPE, TRUST_CLASS_UNTRUSTED

SCHEMA_VIOLATION = 'ai_output_schema_violation'
HALLUCINATED_REF = 'hallucinated_ref'
EMPTY_VALUE = 'empty_value'
NOT_IN_SNAPSHOT = 'not_in_snapshot'
EVENT_RELATIONS = ('standalone', 'same_event', 'event_update')
REQUIRED_FIELDS = (
    'analysis_id',
    'revision',
    'topic',
    'entities',
    'timeline',
    'locations',
    'facts',
    'uncertainties',
    'contradictions',
    'event_relation',
    'update_context',
    'risk_flags',
    'narrative_opportunities',
    'media_needs',
    'trace',
)


class AnalysisRejected(Exception):
    """Raised when raw model output violates schema or references invalid resources."""

    def __init__(self, code: str, field_path: str, reason: str):
        super().__init__(f'{code}: {field_path} ({reason})')
        self.code = code
        self.field = field_path
        self.reason = reason


@dataclass(frozen=True)
class AnalysisEntity:
    name: str
    entity_type: str


@dataclass(frozen=True)
class TimelineEvent:
    time_label: str
    description: str


@dataclass(frozen=True)
class Statement:
    statement_id: str
    text: str
    evidence: tuple[ResourceRef, ...]
    trust_class: str = field(default=TRUST_CLASS_UNTRUSTED, init=False)


@dataclass(frozen=True)
class Fact(Statement):
    """Source-backed factual claim with non-empty evidence."""


@dataclass(frozen=True)
class Uncertainty(Statement):
    """Unconfirmed assertion; never treated as Fact."""


@dataclass(frozen=True)
class Contradiction(Statement):
    """Disputed claim between sources; never treated as Fact."""


@dataclass(frozen=True)
class AnalysisTrace:
    provider: str
    model: str
    prompt_ref: ResourceRef
    policy_revision: str


@dataclass(frozen=True, kw_only=True)
class ContentAnalysis:
    """Immutable content analysis maintaining provenance and untrusted trust class."""

    analysis_id: str
    revision: int
    snapshot_id: str
    source_set_fingerprint: str
    configuration_bundle_fingerprint: str
    source_refs: tuple[Mapping[str, str], ...]
    topic: str
    entities: tuple[AnalysisEntity, ...]
    timeline: tuple[TimelineEvent, ...]
    locations: tuple[str, ...]
    facts: tuple[Fact, ...]
    uncertainties: tuple[Uncertainty, ...]
    contradictions: tuple[Contradiction, ...]
    event_relation: str
    update_context: str
    risk_flags: tuple[str, ...]
    narrative_opportunities: tuple[str, ...]
    media_needs: tuple[str, ...]
    trace: AnalysisTrace
    trust_class: str = field(default=TRUST_CLASS_UNTRUSTED, init=False)


def _reject(field_path: str, reason: str):
    raise AnalysisRejected(SCHEMA_VIOLATION, field_path, reason)


def _require(source: Mapping, key: str, path: str = ''):
    if key not in source:
        _reject(path + key, MISSING_REQUIRED)
    value = source[key]
    if value is None:
        _reject(path + key, WRONG_TYPE)
    return value


def _text(source: Mapping, key: str, path: str = '') -> str:
    value = _require(source, key, path)
    if not isinstance(value, str):
        _reject(path + key, WRONG_TYPE)
    if not value.strip():
        _reject(path + key, EMPTY_VALUE)
    return value


def _mapping(source: Mapping, key: str, path: str = '') -> Mapping:
    value = _require(source, key, path)
    if not isinstance(value, Mapping):
        _reject(path + key, WRONG_TYPE)
    return value


def _list(source: Mapping, key: str, path: str = '') -> list:
    value = _require(source, key, path)
    if not isinstance(value, list):
        _reject(path + key, WRONG_TYPE)
    return value


def _items(source: Mapping, key: str) -> list[tuple[str, Mapping]]:
    items = []
    for index, item in enumerate(_list(source, key)):
        if not isinstance(item, Mapping):
            _reject(f'{key}[{index}]', WRONG_TYPE)
        items.append((f'{key}[{index}].', item))
    return items


def _strings(source: Mapping, key: str) -> tuple[str, ...]:
    values = _list(source, key)
    for index, item in enumerate(values):
        if not isinstance(item, str):
            _reject(f'{key}[{index}]', WRONG_TYPE)
        if not item.strip():
            _reject(f'{key}[{index}]', EMPTY_VALUE)
    return tuple(values)


def _drafts(source: Mapping, key: str, *, require_evidence: bool) -> list[tuple[str, str, list[tuple[str, Mapping]]]]:
    """Schema-check statements; returns (id, text, [(field_path, proposed_ref)]) with refs still unresolved."""
    drafts = []
    for path, item in _items(source, key):
        statement_id = _text(item, 'id', path)
        text = _text(item, 'text', path)
        proposed = _list(item, 'evidence_refs', path)
        if require_evidence and not proposed:
            _reject(path + 'evidence_refs', EMPTY_VALUE)
        refs = []
        for index, ref in enumerate(proposed):
            if not isinstance(ref, Mapping):
                _reject(f'{path}evidence_refs[{index}]', WRONG_TYPE)
            refs.append((f'{path}evidence_refs[{index}]', ref))
        drafts.append((statement_id, text, refs))
    return drafts


def _resolve(resolver: RefResolver, proposed: Mapping, field_path: str, snapshot_keys: set | None) -> ResourceRef:
    result = resolver.resolve(proposed)
    if not result.ok:
        raise AnalysisRejected(HALLUCINATED_REF, field_path, result.reason)
    ref = result.ref
    if snapshot_keys is not None and (ref.ref_type, ref.ref_id, ref.revision_id) not in snapshot_keys:
        raise AnalysisRejected(HALLUCINATED_REF, field_path, NOT_IN_SNAPSHOT)
    return ref


def _statements(cls, drafts, resolver: RefResolver, snapshot_keys: set) -> tuple:
    return tuple(
        cls(statement_id, text, tuple(_resolve(resolver, ref, path, snapshot_keys) for path, ref in refs))
        for statement_id, text, refs in drafts
    )


def parse_content_analysis(raw: Mapping[str, object], snapshot: ProductionSnapshot, resolver: RefResolver) -> ContentAnalysis:
    """Build the frozen ContentAnalysis (CT-AI-002) from raw model output.

    Schema is checked fully first (ai_output_schema_violation with field, no partial accept); then every evidence ref and
    the prompt ref go through the D-03 resolver (hallucinated_ref). Only documented keys are read; analysis_id and
    revision are caller-injected into raw.
    """
    if not isinstance(snapshot, ProductionSnapshot):
        raise TypeError('snapshot must be a ProductionSnapshot')
    if not isinstance(resolver, RefResolver):
        raise TypeError('resolver must be a RefResolver')
    if not isinstance(raw, Mapping):
        _reject('$', WRONG_TYPE)
    analysis_id = _text(raw, 'analysis_id')
    revision = _require(raw, 'revision')
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        _reject('revision', WRONG_TYPE)
    topic = _text(raw, 'topic')
    entities = tuple(AnalysisEntity(_text(i, 'name', p), _text(i, 'entity_type', p)) for p, i in _items(raw, 'entities'))
    timeline = tuple(TimelineEvent(_text(i, 'time_label', p), _text(i, 'description', p)) for p, i in _items(raw, 'timeline'))
    locations = _strings(raw, 'locations')
    fact_drafts = _drafts(raw, 'facts', require_evidence=True)
    uncertainty_drafts = _drafts(raw, 'uncertainties', require_evidence=False)
    contradiction_drafts = _drafts(raw, 'contradictions', require_evidence=False)
    event_relation = _text(raw, 'event_relation')
    if event_relation not in EVENT_RELATIONS:
        _reject('event_relation', ENUM_VIOLATION)
    update_context = _require(raw, 'update_context')
    if not isinstance(update_context, str):
        _reject('update_context', WRONG_TYPE)
    if event_relation == 'event_update' and not update_context.strip():
        _reject('update_context', EMPTY_VALUE)
    risk_flags = _strings(raw, 'risk_flags')
    narrative_opportunities = _strings(raw, 'narrative_opportunities')
    media_needs = _strings(raw, 'media_needs')
    trace_raw = _mapping(raw, 'trace')
    provider = _text(trace_raw, 'provider', 'trace.')
    model = _text(trace_raw, 'model', 'trace.')
    policy_revision = _text(trace_raw, 'policy_revision', 'trace.')
    prompt_proposed = _mapping(trace_raw, 'prompt_ref', 'trace.')
    keys = {(ref['ref_type'], ref['ref_id'], ref['revision_id']) for ref in snapshot.source_refs}
    facts = _statements(Fact, fact_drafts, resolver, keys)
    uncertainties = _statements(Uncertainty, uncertainty_drafts, resolver, keys)
    contradictions = _statements(Contradiction, contradiction_drafts, resolver, keys)
    prompt_ref = _resolve(resolver, prompt_proposed, 'trace.prompt_ref', None)
    if prompt_ref.ref_type != PROMPT_REVISION_REF_TYPE:
        raise AnalysisRejected(HALLUCINATED_REF, 'trace.prompt_ref', 'not_allowlisted')
    return ContentAnalysis(
        analysis_id=analysis_id,
        revision=revision,
        snapshot_id=snapshot.snapshot_id,
        source_set_fingerprint=snapshot.source_set_fingerprint,
        configuration_bundle_fingerprint=snapshot.configuration_bundle_fingerprint,
        source_refs=snapshot.source_refs,
        topic=topic,
        entities=entities,
        timeline=timeline,
        locations=locations,
        facts=facts,
        uncertainties=uncertainties,
        contradictions=contradictions,
        event_relation=event_relation,
        update_context=update_context,
        risk_flags=risk_flags,
        narrative_opportunities=narrative_opportunities,
        media_needs=media_needs,
        trace=AnalysisTrace(provider, model, prompt_ref, policy_revision),
    )
