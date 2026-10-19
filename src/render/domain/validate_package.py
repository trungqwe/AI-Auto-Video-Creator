"""F-08: ValidateRenderPackage aggregate (CT-RND-003 items 1-9), fail early before heavy render.

Merges the F-06 and F-07 checks into one frozen report with findings ordered by (condition, code, field).
A missing context part yields INPUT_NOT_READY and never passes. Pure domain: no I/O, no clock, no renderer.

coveredIds: CT-RND-003, TST-INT-INV-008 (phía F)
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from controlplane.application.idempotency.canonicalization import request_hash
from render.domain.package_contract import RenderPackageRecord
from render.domain.preconditions_artifacts import (
    IssuedOutputPath, LanguageEvidencePolicy, LanguageEvidenceView, ToolCapability, VerifiedArtifact,
    check_artifacts_verified, check_language_evidence, check_output_path, check_preset_tool_compat,
)
from render.domain.preconditions_media import (
    VoiceTrackInfo, WordTimingInfo, check_hook_preconditions, check_timeline_coverage, check_voice_timing_binding,
)


@dataclass(frozen=True)
class Finding:
    condition: int
    code: str
    field: str


@dataclass(frozen=True, kw_only=True)
class ValidationContext:
    voice: VoiceTrackInfo | None = None
    word_timing: WordTimingInfo | None = None
    verified: Mapping[str, VerifiedArtifact] | None = None
    issued_paths: Mapping[str, IssuedOutputPath] | None = None
    language_evidence: Mapping[str, LanguageEvidenceView] | None = None
    language_policy: LanguageEvidencePolicy | None = None
    preset: object | None = None
    capability: ToolCapability | None = None


def _order_key(finding: Finding) -> tuple[int, str, str]:
    return (finding.condition, finding.code, finding.field)


def _compute_report_id(package_fingerprint: str, findings: tuple[Finding, ...]) -> str:
    return request_hash({
        'package_fingerprint': package_fingerprint,
        'findings': [{'condition': item.condition, 'code': item.code, 'field': item.field} for item in findings],
    })


@dataclass(frozen=True, kw_only=True)
class PackageValidationReport:
    """Frozen CT-RND-003 report; `passed` is derived from findings alone and report_id is request_hash of fingerprint and findings."""

    package_fingerprint: str
    findings: tuple[Finding, ...]
    passed: bool
    report_id: str

    def __post_init__(self) -> None:
        findings = tuple(self.findings)
        if not all(type(item) is Finding for item in findings):
            raise ValueError('wrong_type:findings')
        if list(findings) != sorted(findings, key=_order_key):
            raise ValueError('invalid_value:findings')
        object.__setattr__(self, 'findings', findings)
        if self.passed is not (not findings):
            raise ValueError('invalid_value:passed')
        if self.report_id != _compute_report_id(self.package_fingerprint, findings):
            raise ValueError('invalid_value:report_id')


class PackageNotRenderable(Exception):
    """Raised by require_valid_package; `report` carries every finding."""

    def __init__(self, report: PackageValidationReport) -> None:
        super().__init__(f'package_not_renderable:{len(report.findings)}')
        self.report = report


def _mapping(value: object) -> Mapping | None:
    return value if isinstance(value, Mapping) else None


def _instance(value: object, kind: type) -> object | None:
    return value if isinstance(value, kind) else None


def validate_render_package(record: RenderPackageRecord, context: ValidationContext | None = None) -> PackageValidationReport:
    """Run the F-06 and F-07 checks (CT-RND-003 items 1-9) and return every finding, never only the first.

    A context that is not a ValidationContext counts as empty. Missing or wrongly typed policy, evidence, verified,
    issued_paths, preset or capability give INPUT_NOT_READY (F-07); a missing voice or word timing gives voice_missing or
    word_timing_missing (F-06). Findings are ordered by (condition, code, field); `passed` is True only without findings.
    """
    if not isinstance(record, RenderPackageRecord):
        raise TypeError('record must be a RenderPackageRecord')
    ctx = context if isinstance(context, ValidationContext) else ValidationContext()
    raw = [
        *check_hook_preconditions(record),
        *check_voice_timing_binding(record, ctx.voice, ctx.word_timing),
        *check_timeline_coverage(record.timeline),
        *check_language_evidence(record, _mapping(ctx.language_evidence), _instance(ctx.language_policy, LanguageEvidencePolicy)),
        *check_artifacts_verified(record, _mapping(ctx.verified)),
        *check_output_path(record, _mapping(ctx.issued_paths)),
        *check_preset_tool_compat(ctx.preset, ctx.capability),
    ]
    findings = tuple(sorted((Finding(item.condition, item.code, item.field) for item in raw), key=_order_key))
    return PackageValidationReport(
        package_fingerprint=record.package_fingerprint,
        findings=findings,
        passed=not findings,
        report_id=_compute_report_id(record.package_fingerprint, findings),
    )


def require_valid_package(report: PackageValidationReport) -> None:
    """Raise PackageNotRenderable carrying the report unless it passed; call before any renderer is invoked."""
    if not isinstance(report, PackageValidationReport):
        raise TypeError('report must be a PackageValidationReport')
    if not report.passed:
        raise PackageNotRenderable(report)
