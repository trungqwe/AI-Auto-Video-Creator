"""SourceAdapter port and fetch result contracts (A-12, implementation-plan section 10).

Operations: probe, list_candidates, fetch_document, extract_candidate, resume_from_checkpoint,
supplemental_search. An adapter that does not support an operation returns CapabilityUnavailable;
it never reports an empty success for a missing capability.
"""
from __future__ import annotations

import enum
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from controlplane.domain.common.contracts import ProblemDetail

CAPABILITY_UNAVAILABLE = 'CAPABILITY_UNAVAILABLE'


class AdapterOperation(str, enum.Enum):
    PROBE = 'probe'
    LIST_CANDIDATES = 'list_candidates'
    FETCH_DOCUMENT = 'fetch_document'
    EXTRACT_CANDIDATE = 'extract_candidate'
    RESUME_FROM_CHECKPOINT = 'resume_from_checkpoint'
    SUPPLEMENTAL_SEARCH = 'supplemental_search'


def _require_text(value: object, reason: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(reason)


@dataclass(frozen=True)
class CapabilityUnavailable:
    """Structured result for an unsupported operation; never a success type."""

    operation: AdapterOperation
    adapter_id: str
    adapter_version: str
    reason: str
    code: str = field(default=CAPABILITY_UNAVAILABLE, init=False)
    retryable: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.operation, AdapterOperation):
            raise ValueError('INVALID_CAPABILITY_UNAVAILABLE')
        for value in (self.adapter_id, self.adapter_version, self.reason):
            _require_text(value, 'INVALID_CAPABILITY_UNAVAILABLE')


@dataclass(frozen=True)
class AdapterDescriptor:
    """Declared capabilities; resume requires a versioned checkpoint semantics."""

    adapter_id: str
    adapter_version: str
    operations: frozenset[AdapterOperation]
    checkpoint_version: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.adapter_id, 'INVALID_ADAPTER_DESCRIPTOR')
        _require_text(self.adapter_version, 'INVALID_ADAPTER_DESCRIPTOR')
        if not isinstance(self.operations, frozenset) or not all(
            isinstance(operation, AdapterOperation) for operation in self.operations
        ):
            raise ValueError('INVALID_ADAPTER_DESCRIPTOR')
        if AdapterOperation.RESUME_FROM_CHECKPOINT in self.operations:
            _require_text(self.checkpoint_version, 'INVALID_ADAPTER_DESCRIPTOR')

    def supports(self, operation: AdapterOperation) -> bool:
        return operation in self.operations

    def unavailable(self, operation: AdapterOperation, reason: str) -> CapabilityUnavailable:
        return CapabilityUnavailable(operation, self.adapter_id, self.adapter_version, reason)


@dataclass(frozen=True)
class ProbeResult:
    locator: str
    descriptor: AdapterDescriptor
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidateListing:
    locators: tuple[str, ...]
    cursor: str | None = None
    complete: bool = True


@dataclass(frozen=True)
class FetchObservation:
    """Safe HTTP observation (spec 6.4); credentials and cookies are never recorded."""

    requested_locator: str
    final_locator: str
    redirect_chain: tuple[str, ...]
    status: int
    media_type: str
    size_bytes: int
    safe_headers: tuple[tuple[str, str], ...]
    policy_revision: str


@dataclass(frozen=True)
class FetchedDocument:
    observation: FetchObservation
    body: bytes = field(repr=False)


@dataclass(frozen=True)
class ExtractedCandidate:
    locator: str
    technical_fields: Mapping[str, object]
    warnings: tuple[str, ...] = ()


@runtime_checkable
class SourceAdapter(Protocol):
    """Standard adapter operations; an unsupported one returns CapabilityUnavailable."""

    def probe(self, locator: str) -> ProbeResult | CapabilityUnavailable | ProblemDetail: ...

    def list_candidates(
        self, locator: str, cursor: str | None
    ) -> CandidateListing | CapabilityUnavailable | ProblemDetail: ...

    def fetch_document(self, locator: str) -> FetchedDocument | CapabilityUnavailable | ProblemDetail: ...

    def extract_candidate(
        self, document: FetchedDocument
    ) -> ExtractedCandidate | CapabilityUnavailable | ProblemDetail: ...

    def resume_from_checkpoint(
        self, checkpoint_version: str, cursor: str
    ) -> CandidateListing | CapabilityUnavailable | ProblemDetail: ...

    def supplemental_search(
        self, intent: Mapping[str, str]
    ) -> CandidateListing | CapabilityUnavailable | ProblemDetail: ...
