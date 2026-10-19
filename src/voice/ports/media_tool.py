"""MediaToolPort: E-local port that runs one RenditionPlan with a media tool (CT-PROC-007, CONV-E-07).

Pure declarations: no I/O and no process execution here; the adapter that really runs a tool lives outside the domain (CP7-E-04).
A non-succeeded outcome never carries an output: unverified bytes are not recorded as a rendition.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from voice.domain.processing import (
    CONSTRAINT_VIOLATION,
    ENUM_VIOLATION,
    MISSING_REQUIRED,
    WRONG_TYPE,
    Disposition,
    ProcessingContractError,
)

if TYPE_CHECKING:
    from voice.domain.normalize import RenditionPlan

_SHA256_PATTERN = r'[0-9a-f]{64}'


def _require_text(value: object, field: str) -> str:
    if value is None:
        raise ProcessingContractError(MISSING_REQUIRED, field)
    if not isinstance(value, str):
        raise ProcessingContractError(WRONG_TYPE, field)
    if not value.strip():
        raise ProcessingContractError(CONSTRAINT_VIOLATION, field)
    return value


@dataclass(frozen=True)
class ToolOutcome:
    """Result of one tool run: new output ref and sha256 on success, error text on failure."""

    status: Disposition
    output_ref: str | None = None
    output_sha256: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        status = self.status
        if status is None:
            raise ProcessingContractError(MISSING_REQUIRED, 'status')
        if isinstance(status, str) and not isinstance(status, Disposition):
            try:
                status = Disposition(status)
            except ValueError:
                raise ProcessingContractError(ENUM_VIOLATION, 'status') from None
        if not isinstance(status, Disposition):
            raise ProcessingContractError(WRONG_TYPE, 'status')
        object.__setattr__(self, 'status', status)
        if status is Disposition.SUCCEEDED:
            _require_text(self.output_ref, 'output_ref')
            if self.output_sha256 is None:
                raise ProcessingContractError(MISSING_REQUIRED, 'output_sha256')
            if not isinstance(self.output_sha256, str) or not re.fullmatch(_SHA256_PATTERN, self.output_sha256):
                raise ProcessingContractError(WRONG_TYPE, 'output_sha256')
            if self.error is not None:
                raise ProcessingContractError(CONSTRAINT_VIOLATION, 'error')
            return
        if self.output_ref is not None:
            raise ProcessingContractError(CONSTRAINT_VIOLATION, 'output_ref')
        if self.output_sha256 is not None:
            raise ProcessingContractError(CONSTRAINT_VIOLATION, 'output_sha256')
        if status is Disposition.FAILED or self.error is not None:
            _require_text(self.error, 'error')


@runtime_checkable
class MediaToolPort(Protocol):
    def run(self, plan: RenditionPlan) -> ToolOutcome:
        """Run the plan with the tool and report one outcome; never write over the plan input."""
        ...
