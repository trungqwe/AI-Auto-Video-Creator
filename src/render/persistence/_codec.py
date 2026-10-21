"""Domain object <-> JSON codecs for render PostgreSQL persistence (PERSIST-F)."""
from __future__ import annotations

import dataclasses
import datetime
import json
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from controlplane.domain.statemachine import OperationState
from render.application.package_pipeline import CommandReceipt, CommandTrace
from render.domain.package_contract import validate_render_package_payload
from render.domain.quality_report import GateResult, QualityReport
from render.domain.render_attempt import RenderAttempt
from render.domain.validate_package import Finding, PackageValidationReport


def plain(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: plain(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, Mapping):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    raise TypeError(f'Unsupported value type for plain encoding: {type(value)}')


def package_payload(record: Any) -> Any:
    return plain(record)


def package_from_payload(payload: Any) -> Any:
    return validate_render_package_payload(payload)


def attempt_payload(attempt: RenderAttempt) -> dict[str, Any]:
    return {**attempt.to_dict(), 'command_spec_text': attempt.command_spec}


def attempt_from_payload(p: dict[str, Any]) -> RenderAttempt:
    return RenderAttempt(
        render_attempt_id=p['render_attempt_id'],
        package_fingerprint=p['package_fingerprint'],
        output_artifact_ref=p['output_artifact_ref'],
        tool_name=p['tool_name'],
        tool_version=p['tool_version'],
        build_version=p['build_version'],
        command_spec=p['command_spec_text'],
        receipt_state=OperationState(p['receipt_state']),
        receipt_ref=p['receipt_ref'],
        revision=p['revision'],
        started_at=None if p.get('started_at') is None else datetime.datetime.fromisoformat(p['started_at']),
        finished_at=None if p.get('finished_at') is None else datetime.datetime.fromisoformat(p['finished_at']),
        wall_time_ms=p.get('wall_time_ms'),
        cpu_metrics=MappingProxyType(dict(p['cpu_metrics'])) if p.get('cpu_metrics') is not None else MappingProxyType({}),
        gpu_metrics=MappingProxyType(dict(p['gpu_metrics'])) if p.get('gpu_metrics') is not None else MappingProxyType({}),
        peak_disk_bytes=p.get('peak_disk_bytes'),
        warnings=tuple(p['warnings']) if p.get('warnings') is not None else (),
        error=p.get('error'),
    )


def gate_payload(item: GateResult) -> dict[str, Any]:
    return {
        'gate': item.gate.value,
        'status': item.status.value,
        'evidence_ref': item.evidence_ref,
        'time_range': None if item.time_range is None else list(item.time_range),
        'measured_value': item.measured_value,
        'threshold_revision': item.threshold_revision,
        'reason': item.reason,
    }


def gate_from_payload(p: dict[str, Any]) -> GateResult:
    return GateResult(
        gate=p['gate'],
        status=p['status'],
        evidence_ref=p.get('evidence_ref'),
        time_range=p.get('time_range'),
        measured_value=p.get('measured_value'),
        threshold_revision=p.get('threshold_revision'),
        reason=p.get('reason'),
    )


def quality_header(report: QualityReport) -> dict[str, Any]:
    return {
        'report_id': report.report_id,
        'policy_revision': report.policy_revision,
        'passed': report.passed,
    }


def quality_gates(report: QualityReport) -> dict[str, Any]:
    return {'gates': [gate_payload(g) for g in report.gates]}


def quality_from_payload(header: dict[str, Any], gates: dict[str, Any]) -> QualityReport:
    return QualityReport(
        report_id=header['report_id'],
        policy_revision=header.get('policy_revision'),
        gates=tuple(gate_from_payload(g) for g in gates['gates']),
        passed=header['passed'],
    )


def validation_payload(report: PackageValidationReport) -> dict[str, Any]:
    return {
        'package_fingerprint': report.package_fingerprint,
        'findings': [
            {'condition': f.condition, 'code': f.code, 'field': f.field}
            for f in report.findings
        ],
        'passed': report.passed,
        'report_id': report.report_id,
    }


def validation_from_payload(p: dict[str, Any]) -> PackageValidationReport:
    return PackageValidationReport(
        package_fingerprint=p['package_fingerprint'],
        findings=tuple(
            Finding(f['condition'], f['code'], f['field'])
            for f in p['findings']
        ),
        passed=p['passed'],
        report_id=p['report_id'],
    )


def receipt_key(command: str, operation_key: str) -> str:
    return f'{command}:{operation_key}'


def receipt_ref_json(receipt: CommandReceipt) -> str:
    return json.dumps({
        'receipt_ref': receipt.receipt_ref,
        'state': receipt.state.value,
        'render_package_id': receipt.render_package_id,
        'package_fingerprint': receipt.package_fingerprint,
        'report_id': receipt.report_id,
    }, sort_keys=True, ensure_ascii=False)


def receipt_from_row(
    workspace_id: str,
    idempotency_key: str,
    request_hash: str,
    aggregate_ref: str,
    aggregate_revision: int,
) -> CommandReceipt:
    command, operation_key = idempotency_key.split(':', 1)
    data = json.loads(aggregate_ref)
    return CommandReceipt(
        command=command,
        workspace_id=workspace_id,
        operation_key=operation_key,
        request_hash=request_hash,
        receipt_ref=data['receipt_ref'],
        state=OperationState(data['state']),
        revision=aggregate_revision,
        render_package_id=data['render_package_id'],
        package_fingerprint=data['package_fingerprint'],
        report_id=data['report_id'],
    )


def trace_payload(trace: CommandTrace) -> dict[str, Any]:
    return {
        'command': trace.command,
        'workspace_id': trace.workspace_id,
        'operation_key': trace.operation_key,
        'correlation_id': trace.correlation_id,
        'actor': trace.actor,
        'occurred_at': trace.occurred_at,
        'receipt_ref': trace.receipt_ref,
        'grant_id': trace.grant_id,
        'execution_generation': trace.execution_generation,
        'subject_ref': trace.subject_ref,
        'outcome': trace.outcome,
    }


def trace_from_payload(sequence: int, p: dict[str, Any]) -> CommandTrace:
    return CommandTrace(sequence=sequence, **p)


SUCCEEDED_TRACE_OUTCOMES = frozenset({
    'package_resolved',
    'validation_passed',
    'render_succeeded',
    'reconcile_succeeded',
})


def audit_outcome(outcome: str) -> str:
    return 'succeeded' if outcome in SUCCEEDED_TRACE_OUTCOMES else 'failed'