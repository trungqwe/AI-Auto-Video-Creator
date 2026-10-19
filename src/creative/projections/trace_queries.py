"""Read-only trace projection of D (D-17): walks an output back to its snapshot, analysis, angle, AI invocations and input revisions; no AI call, no repository write, filtered by workspace, errors redacted.

coveredIds: acceptance §12 mục 7, exit gate G1
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable, Mapping
from types import MappingProxyType
from typing import Any, Protocol

from creative.domain.invocation import redact_error
from creative.ports.repositories import KIND_OUTPUT_METADATA, KIND_PLAN, KIND_SCRIPT, KIND_VARIANT_VALIDATION

OUTPUT_KINDS = (KIND_PLAN, KIND_SCRIPT, KIND_OUTPUT_METADATA, KIND_VARIANT_VALIDATION)
SNAPSHOT_FIELDS = (
    'snapshot_id',
    'production_mode',
    'source_refs',
    'index_revision_refs',
    'configuration_revision_refs',
    'source_set_fingerprint',
    'configuration_bundle_fingerprint',
    'snapshot_timestamp',
)
REQUIRED_INVOCATION_FIELDS = (
    'provider_ref',
    'model_ref',
    'route_revision',
    'prompt_revision',
    'config_revision',
    'input_fingerprint',
)
_REPOSITORIES = MappingProxyType({
    KIND_PLAN: 'plans',
    KIND_SCRIPT: 'scripts',
    KIND_OUTPUT_METADATA: 'output_metadata',
    KIND_VARIANT_VALIDATION: 'variant_validations',
})
_FINGERPRINT_ATTRS = MappingProxyType({
    KIND_PLAN: 'plan_fingerprint',
    KIND_SCRIPT: 'script_fingerprint',
    KIND_OUTPUT_METADATA: None,
    KIND_VARIANT_VALIDATION: 'validation_hash',
})


class TraceNotFound(LookupError):
    """No stored output of this workspace matches; an output of another workspace gives the same error, so its existence never leaks."""

    def __init__(self) -> None:
        super().__init__('trace_not_found')


class TraceIncomplete(ValueError):
    """The chain back from an output is broken; reason and field are fixed codes, never stored values."""

    def __init__(self, reason: str, field: str) -> None:
        super().__init__(f'trace_incomplete: {reason} ({field})')
        self.reason = reason
        self.field = field


def _text(name: str, value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a non-empty string')


def _positive(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f'{name} must be a positive integer')


@dataclasses.dataclass(frozen=True, kw_only=True)
class InvocationRef:
    """Key and revision of one AIInvocationRecord in the invocation repository."""

    key: str
    revision: int

    def __post_init__(self) -> None:
        _text('key', self.key)
        _positive('revision', self.revision)


@dataclasses.dataclass(frozen=True, kw_only=True)
class TraceLink:
    """Caller-supplied edges of one output revision: its workspace plus the exact refs it was produced from (GIẢ ĐỊNH until D-14 and CONV-D-02 fill it)."""

    workspace_id: str
    output_kind: str
    output_key: str
    output_revision: int
    snapshot_id: str
    analysis_id: str
    analysis_revision: int
    angle_set_key: str
    angle_set_revision: int
    angle_id: str
    invocation_refs: tuple[InvocationRef, ...]

    def __post_init__(self) -> None:
        for name in ('workspace_id', 'output_key', 'snapshot_id', 'analysis_id', 'angle_set_key', 'angle_id'):
            _text(name, getattr(self, name))
        for name in ('output_revision', 'analysis_revision', 'angle_set_revision'):
            _positive(name, getattr(self, name))
        if self.output_kind not in OUTPUT_KINDS:
            raise ValueError(f'output_kind must be one of {OUTPUT_KINDS!r}')
        refs = self.invocation_refs
        if isinstance(refs, (str, bytes, Mapping)) or not isinstance(refs, Iterable):
            raise ValueError('invocation_refs must be a non-empty tuple of InvocationRef')
        refs = tuple(refs)
        if not refs or not all(isinstance(ref, InvocationRef) for ref in refs):
            raise ValueError('invocation_refs must be a non-empty tuple of InvocationRef')
        object.__setattr__(self, 'invocation_refs', refs)

    @property
    def identity(self) -> tuple[str, str, str, int]:
        return (self.workspace_id, self.output_kind, self.output_key, self.output_revision)


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_thaw(item) for item in value]
    return value


@dataclasses.dataclass(frozen=True, kw_only=True)
class RevisionEntry:
    output_kind: str
    output_key: str
    revision: int
    output_fingerprint: str | None

    def to_payload(self) -> dict[str, object]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True, kw_only=True)
class InvocationTrace:
    key: str
    revision: int
    ai_role: str
    provider_ref: str
    model_ref: str
    account_ref: str
    route_revision: str
    prompt_revision: str
    config_revision: str
    input_fingerprint: str
    output_fingerprint: str | None
    attempt: int
    validation_result: str
    error: str | None

    def to_payload(self) -> dict[str, object]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True, kw_only=True)
class OutputTrace:
    """Refs, revisions and fingerprints only: never output text, a secret or an unredacted error."""

    workspace_id: str
    output_kind: str
    output_key: str
    output_revision: int
    output_fingerprint: str | None
    snapshot: Mapping[str, Any]
    analysis: Mapping[str, Any]
    angle: Mapping[str, Any]
    invocations: tuple[InvocationTrace, ...]
    history: tuple[RevisionEntry, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            'workspace_id': self.workspace_id,
            'output': {
                'kind': self.output_kind,
                'key': self.output_key,
                'revision': self.output_revision,
                'fingerprint': self.output_fingerprint,
            },
            'snapshot': _thaw(self.snapshot),
            'analysis': _thaw(self.analysis),
            'angle': _thaw(self.angle),
            'invocations': [item.to_payload() for item in self.invocations],
            'history': [item.to_payload() for item in self.history],
        }


class _SnapshotReader(Protocol):
    def get(self, snapshot_id: str) -> Any: ...


class _RecordReader(Protocol):
    def latest(self, key: str) -> Any: ...

    def revisions(self, key: str) -> tuple[Any, ...]: ...


class TraceStore(Protocol):
    """Read side of the D repositories (InMemoryUnitOfWork has this shape); the projection calls only get, latest and revisions."""

    snapshots: _SnapshotReader
    analyses: _RecordReader
    angle_sets: _RecordReader
    scripts: _RecordReader
    plans: _RecordReader
    variant_validations: _RecordReader
    output_metadata: _RecordReader
    invocations: _RecordReader



def _index(links: Iterable[TraceLink]) -> dict[tuple[str, str, str, int], TraceLink]:
    if isinstance(links, (str, bytes, Mapping)) or not isinstance(links, Iterable):
        raise TypeError('links must be an iterable of TraceLink')
    index: dict[tuple[str, str, str, int], TraceLink] = {}
    for link in links:
        if not isinstance(link, TraceLink):
            raise TypeError('links items must be TraceLink')
        if link.identity in index:
            raise ValueError('duplicate trace link')
        index[link.identity] = link
    return index


def _check_query(workspace_id: str, output_kind: str, output_key: str) -> None:
    _text('workspace_id', workspace_id)
    _text('output_key', output_key)
    if output_kind not in OUTPUT_KINDS:
        raise ValueError(f'output_kind must be one of {OUTPUT_KINDS!r}')


def _repository(store: TraceStore, output_kind: str) -> _RecordReader:
    return getattr(store, _REPOSITORIES[output_kind])


def _fingerprint(output_kind: str, record: object) -> str | None:
    name = _FINGERPRINT_ATTRS[output_kind]
    return None if name is None else getattr(record, name)


def list_outputs(links: Iterable[TraceLink], *, workspace_id: str) -> tuple[tuple[str, str, int], ...]:
    """Sorted (kind, key, revision) of every output linked to workspace_id; reads no store."""
    _text('workspace_id', workspace_id)
    return tuple(sorted(
        (link.output_kind, link.output_key, link.output_revision)
        for link in _index(links).values()
        if link.workspace_id == workspace_id
    ))


def list_output_revisions(
    store: TraceStore,
    links: Iterable[TraceLink],
    *,
    workspace_id: str,
    output_kind: str,
    output_key: str,
) -> tuple[RevisionEntry, ...]:
    """Every stored revision of one output key linked in workspace_id, ascending; older revisions are never overwritten."""
    _check_query(workspace_id, output_kind, output_key)
    index = _index(links)
    return tuple(
        RevisionEntry(
            output_kind=output_kind,
            output_key=output_key,
            revision=item.revision,
            output_fingerprint=_fingerprint(output_kind, item.record),
        )
        for item in _repository(store, output_kind).revisions(output_key)
        if (workspace_id, output_kind, output_key, item.revision) in index
    )


def _stored(repository: _RecordReader, key: str, revision: int) -> Any:
    return next((item.record for item in repository.revisions(key) if item.revision == revision), None)


def _require(record: Any, reason: str, field: str) -> Any:
    if record is None:
        raise TraceIncomplete(reason, field)
    return record


def _same_workspace(workspace_id: str, refs: Iterable[Any], field: str) -> None:
    if any(ref.workspace_id != workspace_id for ref in refs):
        raise TraceIncomplete('workspace_mismatch', field)


def _snapshot_section(store: TraceStore, link: TraceLink) -> tuple[Any, Mapping[str, Any]]:
    snapshot = _require(store.snapshots.get(link.snapshot_id), 'snapshot_missing', 'snapshot')
    payload = snapshot.to_payload()
    return snapshot, _freeze({name: payload[name] for name in SNAPSHOT_FIELDS})


def _analysis_section(store: TraceStore, link: TraceLink, snapshot: Any) -> Mapping[str, Any]:
    analysis = _require(_stored(store.analyses, link.analysis_id, link.analysis_revision), 'analysis_missing', 'analysis')
    origin = (snapshot.snapshot_id, snapshot.source_set_fingerprint, snapshot.configuration_bundle_fingerprint)
    if (analysis.snapshot_id, analysis.source_set_fingerprint, analysis.configuration_bundle_fingerprint) != origin:
        raise TraceIncomplete('snapshot_mismatch', 'analysis.snapshot_id')
    ref = analysis.trace.prompt_ref
    _same_workspace(link.workspace_id, (ref,), 'analysis.trace.prompt_ref')
    return _freeze({
        'analysis_id': analysis.analysis_id,
        'revision': analysis.revision,
        'snapshot_id': analysis.snapshot_id,
        'provider': analysis.trace.provider,
        'model': analysis.trace.model,
        'policy_revision': analysis.trace.policy_revision,
        'prompt_ref': {
            'workspace_id': ref.workspace_id,
            'ref_type': ref.ref_type,
            'ref_id': ref.ref_id,
            'revision_id': ref.revision_id,
        },
    })


def _angle_section(store: TraceStore, link: TraceLink) -> Mapping[str, Any]:
    angle_set = _require(_stored(store.angle_sets, link.angle_set_key, link.angle_set_revision), 'angle_set_missing', 'angle_set')
    if (angle_set.analysis_id, angle_set.analysis_revision) != (link.analysis_id, link.analysis_revision):
        raise TraceIncomplete('analysis_mismatch', 'angle_set.analysis_id')
    angle = _require(next((a for a in angle_set.angles if a.angle_id == link.angle_id), None), 'angle_missing', 'angle_id')
    _same_workspace(link.workspace_id, angle.evidence_refs, 'angle.evidence_refs')
    return _freeze({
        'set_id': angle_set.set_id,
        'set_key': link.angle_set_key,
        'set_revision': link.angle_set_revision,
        'analysis_id': angle_set.analysis_id,
        'analysis_revision': angle_set.analysis_revision,
        'variation_policy_revision': angle_set.variation_policy_revision,
        'angle_id': angle.angle_id,
        'distinction_fingerprint': angle.distinction_fingerprint,
    })


def _invocation(store: TraceStore, ref: InvocationRef, position: int) -> InvocationTrace:
    record = _require(_stored(store.invocations, ref.key, ref.revision), 'invocation_missing', f'invocation_refs[{position}]')
    for name in REQUIRED_INVOCATION_FIELDS:
        value = getattr(record, name)
        if not isinstance(value, str) or not value.strip():
            raise TraceIncomplete('trace_field_missing', f'invocations[{position}].{name}')
    return InvocationTrace(
        key=ref.key,
        revision=ref.revision,
        ai_role=record.ai_role,
        provider_ref=record.provider_ref,
        model_ref=record.model_ref,
        account_ref=record.account_ref,
        route_revision=record.route_revision,
        prompt_revision=record.prompt_revision,
        config_revision=record.config_revision,
        input_fingerprint=record.input_fingerprint,
        output_fingerprint=record.output_fingerprint,
        attempt=record.attempt,
        validation_result=record.validation_result,
        error=None if record.error is None else redact_error(record.error),
    )


def trace_output(
    store: TraceStore,
    links: Iterable[TraceLink],
    *,
    workspace_id: str,
    output_kind: str,
    output_key: str,
    output_revision: int | None = None,
) -> OutputTrace:
    """Trace one output revision back to snapshot, analysis, angle and AI invocations; latest stored revision when output_revision is None.

    Raises TraceNotFound for an unknown output or one outside workspace_id, TraceIncomplete for a broken or cross-workspace chain; never calls AI, never writes.
    """
    _check_query(workspace_id, output_kind, output_key)
    index = _index(links)
    repository = _repository(store, output_kind)
    if output_revision is None:
        latest = repository.latest(output_key)
        output_revision = None if latest is None else latest.revision
    link = index.get((workspace_id, output_kind, output_key, output_revision))
    record = None if link is None else _stored(repository, output_key, output_revision)
    if record is None:
        raise TraceNotFound()
    if output_kind == KIND_SCRIPT:
        refs = [ref for segment in record.segments for ref in segment.source_refs]
        _same_workspace(workspace_id, refs, 'script.source_refs')
    snapshot, snapshot_section = _snapshot_section(store, link)
    analysis_section = _analysis_section(store, link, snapshot)
    angle_section = _angle_section(store, link)
    invocations = tuple(_invocation(store, ref, position) for position, ref in enumerate(link.invocation_refs))
    return OutputTrace(
        workspace_id=workspace_id,
        output_kind=output_kind,
        output_key=output_key,
        output_revision=output_revision,
        output_fingerprint=_fingerprint(output_kind, record),
        snapshot=snapshot_section,
        analysis=analysis_section,
        angle=angle_section,
        invocations=invocations,
        history=list_output_revisions(
            store, index.values(), workspace_id=workspace_id, output_kind=output_kind, output_key=output_key),
    )


__all__ = [
    'InvocationRef',
    'InvocationTrace',
    'OUTPUT_KINDS',
    'OutputTrace',
    'REQUIRED_INVOCATION_FIELDS',
    'RevisionEntry',
    'SNAPSHOT_FIELDS',
    'TraceIncomplete',
    'TraceLink',
    'TraceNotFound',
    'TraceStore',
    'list_output_revisions',
    'list_outputs',
    'trace_output',
]
