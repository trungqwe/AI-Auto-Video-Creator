"""Voice domain processing contract definitions and ready condition."""
from __future__ import annotations

from collections.abc import Mapping
import dataclasses
import enum
import re
from types import MappingProxyType

from controlplane.application.idempotency.canonicalization import request_hash

REQUEST_FIELDS = (
    'processing_operation_id',
    'stage_run_id',
    'execution_grant',
    'input_artifact_refs',
    'operation_spec_revision',
    'expected_output_profile',
    'resource_limits',
    'output_storage_intent',
)

RESULT_FIELDS = (
    'disposition',
    'output_artifact_refs',
    'processor_identity',
    'input_fingerprint',
    'output_hashes',
    'technical_report',
    'warnings',
    'operation_receipt_ref',
)

MISSING_REQUIRED = 'missing_required'
WRONG_TYPE = 'wrong_type'
ENUM_VIOLATION = 'enum_violation'
CONSTRAINT_VIOLATION = 'constraint_violation'

_SHA256_RE = re.compile(r'^[0-9a-f]{64}$')


class ProcessingContractError(ValueError):
    def __init__(self, code: str, field: str) -> None:
        self.code = code
        self.field = field
        super().__init__(f'{code}: {field}')


class Disposition(enum.StrEnum):
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'
    WAITING = 'waiting'
    OUTCOME_UNKNOWN = 'outcome_unknown'


class OutputClass(enum.StrEnum):
    REUSABLE = 'reusable'
    PER_VIDEO = 'per_video'
    DIAGNOSTIC = 'diagnostic'


def _check_str(value: object, field: str) -> str:
    if value is None:
        raise ProcessingContractError(MISSING_REQUIRED, field)
    if not isinstance(value, str):
        raise ProcessingContractError(WRONG_TYPE, field)
    if not value.strip():
        raise ProcessingContractError(CONSTRAINT_VIOLATION, field)
    return value


def _check_mapping(value: object, field: str) -> Mapping:
    if value is None:
        raise ProcessingContractError(MISSING_REQUIRED, field)
    if not isinstance(value, Mapping):
        raise ProcessingContractError(WRONG_TYPE, field)
    return value


def _check_sha256(value: object, field: str = 'content_sha256') -> str:
    if value is None:
        raise ProcessingContractError(MISSING_REQUIRED, field)
    if not isinstance(value, str):
        raise ProcessingContractError(WRONG_TYPE, field)
    if not _SHA256_RE.fullmatch(value):
        raise ProcessingContractError(WRONG_TYPE, field)
    return value


@dataclasses.dataclass(frozen=True)
class ArtifactRef:
    ref: str
    content_sha256: str

    def __post_init__(self) -> None:
        _check_str(self.ref, 'ref')
        _check_sha256(self.content_sha256, 'content_sha256')


def _as_artifact_ref(value: object) -> ArtifactRef:
    if isinstance(value, ArtifactRef):
        return value
    if isinstance(value, Mapping):
        if 'ref' not in value:
            raise ProcessingContractError(MISSING_REQUIRED, 'ref')
        if 'content_sha256' not in value:
            raise ProcessingContractError(MISSING_REQUIRED, 'content_sha256')
        return ArtifactRef(value['ref'], value['content_sha256'])
    raise ProcessingContractError(WRONG_TYPE, 'artifact_ref')


def _as_refs(value: object, field: str) -> tuple[ArtifactRef, ...]:
    if value is None:
        raise ProcessingContractError(MISSING_REQUIRED, field)
    if isinstance(value, (str, bytes, Mapping)):
        raise ProcessingContractError(WRONG_TYPE, field)
    try:
        iterator = iter(value)
    except TypeError:
        raise ProcessingContractError(WRONG_TYPE, field) from None
    return tuple(_as_artifact_ref(x) for x in iterator)


def compute_input_fingerprint(
    input_artifact_refs: object,
    operation_spec_revision: object,
    expected_output_profile: object,
) -> str:
    refs = _as_refs(input_artifact_refs, 'input_artifact_refs')
    rev = _check_str(operation_spec_revision, 'operation_spec_revision')
    profile = _check_mapping(expected_output_profile, 'expected_output_profile')
    return request_hash({
        'input_artifact_refs': [
            {'ref': r.ref, 'content_sha256': r.content_sha256}
            for r in refs
        ],
        'operation_spec_revision': rev,
        'expected_output_profile': profile,
    })


@dataclasses.dataclass(frozen=True)
class ProcessingRequest:
    processing_operation_id: object
    stage_run_id: object
    execution_grant: object
    input_artifact_refs: object
    operation_spec_revision: object
    expected_output_profile: object
    resource_limits: object
    output_storage_intent: object

    def __post_init__(self) -> None:
        for name in REQUEST_FIELDS:
            if getattr(self, name) is None:
                raise ProcessingContractError(MISSING_REQUIRED, name)
        _check_str(self.processing_operation_id, 'processing_operation_id')
        _check_str(self.stage_run_id, 'stage_run_id')
        eg = _check_mapping(self.execution_grant, 'execution_grant')
        if not eg:
            raise ProcessingContractError(MISSING_REQUIRED, 'execution_grant')
        tuple_refs = _as_refs(self.input_artifact_refs, 'input_artifact_refs')
        if len(tuple_refs) == 0:
            raise ProcessingContractError(MISSING_REQUIRED, 'input_artifact_refs')
        object.__setattr__(self, 'input_artifact_refs', tuple_refs)
        _check_str(self.operation_spec_revision, 'operation_spec_revision')
        _check_mapping(self.expected_output_profile, 'expected_output_profile')
        _check_mapping(self.resource_limits, 'resource_limits')
        _check_str(self.output_storage_intent, 'output_storage_intent')

    @classmethod
    def from_mapping(cls, payload: Mapping) -> ProcessingRequest:
        if not isinstance(payload, Mapping):
            raise ProcessingContractError(WRONG_TYPE, 'payload')
        for n in REQUEST_FIELDS:
            if n not in payload:
                raise ProcessingContractError(MISSING_REQUIRED, n)
        return cls(**{n: payload[n] for n in REQUEST_FIELDS})

    @property
    def input_fingerprint(self) -> str:
        return compute_input_fingerprint(
            self.input_artifact_refs,
            self.operation_spec_revision,
            self.expected_output_profile,
        )


@dataclasses.dataclass(frozen=True)
class ProcessingResult:
    disposition: object
    output_artifact_refs: object
    processor_identity: object
    input_fingerprint: object
    output_hashes: object
    technical_report: object
    warnings: object
    operation_receipt_ref: object

    def __post_init__(self) -> None:
        for name in RESULT_FIELDS:
            if name == 'operation_receipt_ref':
                continue
            if getattr(self, name) is None:
                raise ProcessingContractError(MISSING_REQUIRED, name)

        disp = self.disposition
        if isinstance(disp, Disposition):
            disp_val = disp
        elif isinstance(disp, str):
            try:
                disp_val = Disposition(disp)
            except ValueError:
                raise ProcessingContractError(ENUM_VIOLATION, 'disposition') from None
        else:
            raise ProcessingContractError(WRONG_TYPE, 'disposition')
        object.__setattr__(self, 'disposition', disp_val)

        tuple_out_refs = _as_refs(self.output_artifact_refs, 'output_artifact_refs')
        object.__setattr__(self, 'output_artifact_refs', tuple_out_refs)

        pid = _check_mapping(self.processor_identity, 'processor_identity')
        if not pid:
            raise ProcessingContractError(MISSING_REQUIRED, 'processor_identity')
        _check_str(pid.get('tool'), 'processor_identity.tool')
        _check_str(pid.get('version'), 'processor_identity.version')

        _check_sha256(self.input_fingerprint, 'input_fingerprint')

        oh = self.output_hashes
        if not isinstance(oh, (list, tuple)):
            raise ProcessingContractError(WRONG_TYPE, 'output_hashes')
        checked_hashes = tuple(_check_sha256(x, 'output_hashes') for x in oh)
        object.__setattr__(self, 'output_hashes', checked_hashes)
        if checked_hashes != tuple(r.content_sha256 for r in tuple_out_refs):
            raise ProcessingContractError(CONSTRAINT_VIOLATION, 'output_hashes')

        _check_mapping(self.technical_report, 'technical_report')

        wn = self.warnings
        if not isinstance(wn, (list, tuple)):
            raise ProcessingContractError(WRONG_TYPE, 'warnings')
        for w in wn:
            if not isinstance(w, str) or not w:
                raise ProcessingContractError(WRONG_TYPE, 'warnings')
        object.__setattr__(self, 'warnings', tuple(wn))

        rcpt = self.operation_receipt_ref
        if rcpt is None:
            if disp_val == Disposition.SUCCEEDED:
                raise ProcessingContractError(MISSING_REQUIRED, 'operation_receipt_ref')
        else:
            _check_str(rcpt, 'operation_receipt_ref')

        if disp_val == Disposition.SUCCEEDED and len(tuple_out_refs) == 0:
            raise ProcessingContractError(CONSTRAINT_VIOLATION, 'output_artifact_refs')

    @classmethod
    def from_mapping(cls, payload: Mapping) -> ProcessingResult:
        if not isinstance(payload, Mapping):
            raise ProcessingContractError(WRONG_TYPE, 'payload')
        for n in RESULT_FIELDS:
            if n not in payload:
                raise ProcessingContractError(MISSING_REQUIRED, n)
        return cls(**{n: payload[n] for n in RESULT_FIELDS})


RETENTION_INTENT_BY_KIND = MappingProxyType({
    'rendition': OutputClass.REUSABLE,
    'analysis': OutputClass.REUSABLE,
    'voice': OutputClass.PER_VIDEO,
    'word_timing': OutputClass.PER_VIDEO,
    'mix_temp': OutputClass.PER_VIDEO,
    'frame': OutputClass.DIAGNOSTIC,
    'log': OutputClass.DIAGNOSTIC,
    'debug_report': OutputClass.DIAGNOSTIC,
})


def retention_intent(output_kind: object) -> OutputClass:
    if not isinstance(output_kind, str):
        raise ProcessingContractError(WRONG_TYPE, 'output_kind')
    if output_kind not in RETENTION_INTENT_BY_KIND:
        raise ProcessingContractError(CONSTRAINT_VIOLATION, 'output_kind')
    return RETENTION_INTENT_BY_KIND[output_kind]


def is_ready(result: object, verified_refs: object) -> bool:
    """Check if processing result is ready with verified output refs from I."""
    if not isinstance(result, ProcessingResult):
        raise ProcessingContractError(WRONG_TYPE, 'result')
    if verified_refs is None:
        raise ProcessingContractError(MISSING_REQUIRED, 'verified_refs')
    if isinstance(verified_refs, (str, bytes, Mapping)):
        raise ProcessingContractError(WRONG_TYPE, 'verified_refs')
    try:
        iterator = iter(verified_refs)
    except TypeError:
        raise ProcessingContractError(WRONG_TYPE, 'verified_refs') from None

    verified_set = set()
    for item in iterator:
        if not isinstance(item, str):
            raise ProcessingContractError(WRONG_TYPE, 'verified_refs')
        verified_set.add(item)

    return (
        result.disposition is Disposition.SUCCEEDED
        and len(result.output_artifact_refs) > 0
        and all(r.ref in verified_set for r in result.output_artifact_refs)
    )


def validate_result_for_request(request: object, result: object) -> None:
    if not isinstance(request, ProcessingRequest):
        raise ProcessingContractError(WRONG_TYPE, 'request')
    if not isinstance(result, ProcessingResult):
        raise ProcessingContractError(WRONG_TYPE, 'result')
    if result.input_fingerprint != request.input_fingerprint:
        raise ProcessingContractError(CONSTRAINT_VIOLATION, 'input_fingerprint')
    input_ref_ids = {r.ref for r in request.input_artifact_refs}
    for out_ref in result.output_artifact_refs:
        if out_ref.ref in input_ref_ids:
            raise ProcessingContractError(CONSTRAINT_VIOLATION, 'output_artifact_refs')
    return None


__all__ = (
    'REQUEST_FIELDS',
    'RESULT_FIELDS',
    'MISSING_REQUIRED',
    'WRONG_TYPE',
    'ENUM_VIOLATION',
    'CONSTRAINT_VIOLATION',
    'ProcessingContractError',
    'Disposition',
    'OutputClass',
    'ArtifactRef',
    'ProcessingRequest',
    'ProcessingResult',
    'RETENTION_INTENT_BY_KIND',
    'compute_input_fingerprint',
    'is_ready',
    'retention_intent',
    'validate_result_for_request',
)