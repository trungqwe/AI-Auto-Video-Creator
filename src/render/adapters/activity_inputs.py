"""ActivityInputPort of F: resolves the input_refs of an ActivityRequest to the one typed F command of each of the six activities (PW-F4); reads PostgreSQL only through manager.borrow_connection() and the F unit of work."""
from __future__ import annotations

import dataclasses
import datetime
import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

from controlplane.domain.orchestration import ExecutionGrant
from controlplane.domain.statemachine import OperationState
from render.adapters.postgres_plan_assets import read_script_segments
from render.application.inspect_output import InspectOutputCommand, PrepareOutputReadyCommand
from render.application.package_pipeline import (
    CommandContext, RenderPackageNotFound, ResolveRenderPackageCommand, ValidateRenderPackageCommand,
)
from render.application.render_video import ReconcileRenderCommand, RenderVideoCommand
from render.domain.content_gates import ExpectedLanguageRevisions
from render.domain.package_contract import RenderPackageRecord
from render.domain.quality_report import GateResult, QualityPolicy
from render.domain.render_command import RenderCommandSpec
from render.domain.validate_package import ValidationContext
from render.ports.inputs import ResolveInputs
from render.ports.repositories import KIND_ATTEMPT, KIND_PACKAGE

REF_PACKAGE = 'render_package'
REF_ATTEMPT = 'render_attempt'
REF_QUALITY_REPORT = 'quality_report'
REF_EXPECTED_SHA256 = 'expected_sha256'

INPUT_REF_MISSING = 'INPUT_REF_MISSING'
INPUT_REF_AMBIGUOUS = 'INPUT_REF_AMBIGUOUS'
WORD_TIMING_NOT_FOUND = 'WORD_TIMING_NOT_FOUND'
WORD_TIMING_INVALID = 'WORD_TIMING_INVALID'
SEGMENTS_EMPTY = 'SEGMENTS_EMPTY'
UNSUPPORTED_ACTIVITY = 'UNSUPPORTED_ACTIVITY'

_TIMING_SQL = 'SELECT payload FROM controlplane.cp_word_timings WHERE workspace_id = %s::uuid AND timing_artifact_ref = %s ORDER BY revision DESC LIMIT 1'


class ActivityInputError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f'{code}: {detail}')
        self.code = code


@dataclasses.dataclass(frozen=True, kw_only=True)
class RenderPlan:
    command_spec: RenderCommandSpec
    output_artifact_ref: str
    secret_values: tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True, kw_only=True)
class QualityInputs:
    policy: QualityPolicy
    expected_language: ExpectedLanguageRevisions
    warning_results: tuple[GateResult, ...] = ()


class RenderInputSources(Protocol):
    """Sources of D/E/I and ConfigRevision (PW-F3) provided by wiring; this class only glues them."""

    def resolve_inputs(self, input_refs: Sequence[Mapping[str, str]]) -> ResolveInputs: ...
    def validation_context(self, package: RenderPackageRecord) -> ValidationContext: ...
    def render_plan(self, package: RenderPackageRecord, render_attempt_id: str) -> RenderPlan: ...
    def quality_inputs(self, package: RenderPackageRecord) -> QualityInputs: ...


class RenderActivityInputs:
    def __init__(
        self,
        *,
        uow_factory: Callable[[], Any],
        manager: Any,
        sources: RenderInputSources,
        actor: str,
        clock: Callable[[], datetime.datetime],
        orphan_after_seconds: int,
    ) -> None:
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError('actor must be a non-empty string')
        if type(orphan_after_seconds) is not int or orphan_after_seconds < 0:
            raise ValueError('orphan_after_seconds must be a non-negative int')
        self._uow_factory = uow_factory
        self._manager = manager
        self._sources = sources
        self._actor = actor
        self._clock = clock
        self._orphan_after_seconds = orphan_after_seconds

    def resolve(self, activity_name: str, request: Mapping[str, Any], grant: ExecutionGrant) -> Mapping[str, Any]:
        routes = {
            'resolve_render_package': self._for_resolve,
            'validate_render_package': self._for_validate,
            'reconcile_render': self._for_reconcile,
            'render_video': self._for_render,
            'inspect_output': self._for_inspect,
            'prepare_output_ready': self._for_prepare,
        }
        handler = routes.get(activity_name)
        if handler is None:
            raise ActivityInputError(UNSUPPORTED_ACTIVITY, activity_name)
        return handler(request, grant)

    def _one(self, refs: Sequence[Mapping[str, str]], ref_type: str, *, required: bool = True) -> str | None:
        matching = [ref['ref_id'] for ref in refs if ref.get('ref_type') == ref_type]
        if not matching:
            if required:
                raise ActivityInputError(INPUT_REF_MISSING, ref_type)
            return None
        if len(set(matching)) > 1:
            raise ActivityInputError(INPUT_REF_AMBIGUOUS, ref_type)
        return matching[0]

    def _context(self, request: Mapping[str, Any], grant: ExecutionGrant) -> CommandContext:
        return CommandContext(
            workspace_id=grant.workspace_id,
            correlation_id=request['workflow_run_id'],
            actor=self._actor,
            occurred_at=self._clock().astimezone(datetime.timezone.utc).isoformat(),
        )

    def _package(self, package_id: str) -> RenderPackageRecord:
        with self._uow_factory() as uow:
            stored = uow.renders.latest(KIND_PACKAGE, package_id)
        if stored is None:
            raise RenderPackageNotFound(package_id)
        return stored.record

    def _for_resolve(self, request: Mapping[str, Any], grant: ExecutionGrant) -> dict[str, Any]:
        refs = request['input_refs']
        key = request['operation_key']
        ctx = self._context(request, grant)
        return {
            'command': ResolveRenderPackageCommand(
                operation_key=key,
                grant=grant,
                inputs=self._sources.resolve_inputs(refs),
                context=ctx,
            )
        }

    def _for_validate(self, request: Mapping[str, Any], grant: ExecutionGrant) -> dict[str, Any]:
        refs = request['input_refs']
        key = request['operation_key']
        ctx = self._context(request, grant)
        package = self._package(self._one(refs, REF_PACKAGE))
        return {
            'command': ValidateRenderPackageCommand(
                operation_key=key,
                grant=grant,
                render_package_id=package.render_package_id,
                validation_context=self._sources.validation_context(package),
                context=ctx,
            )
        }

    def _for_render(self, request: Mapping[str, Any], grant: ExecutionGrant) -> dict[str, Any]:
        refs = request['input_refs']
        key = request['operation_key']
        ctx = self._context(request, grant)
        package = self._package(self._one(refs, REF_PACKAGE))
        plan = self._sources.render_plan(package, key)
        return {
            'command': RenderVideoCommand(
                grant=grant,
                render_package_id=package.render_package_id,
                render_attempt_id=key,
                output_artifact_ref=plan.output_artifact_ref,
                receipt_ref=f'receipt-{key}',
                command_spec=plan.command_spec,
                context=ctx,
                validation_context=self._sources.validation_context(package),
                secret_values=plan.secret_values,
            )
        }

    def _for_reconcile(self, request: Mapping[str, Any], grant: ExecutionGrant) -> dict[str, Any]:
        refs = request['input_refs']
        ctx = self._context(request, grant)
        package = self._package(self._one(refs, REF_PACKAGE))
        attempt_id = self._one(refs, REF_ATTEMPT, required=False) or self._open_attempt(package)
        if attempt_id is None:
            return {'nothing_to_reconcile': True}
        return {
            'command': ReconcileRenderCommand(
                grant=grant,
                render_attempt_id=attempt_id,
                context=ctx,
                expected_sha256=self._one(refs, REF_EXPECTED_SHA256, required=False),
                orphan_after_seconds=self._orphan_after_seconds,
            )
        }

    def _open_attempt(self, package: RenderPackageRecord) -> str | None:
        with self._uow_factory() as uow:
            for attempt_id in reversed(uow.attempt_index.ids(package.package_fingerprint)):
                stored = uow.renders.latest(KIND_ATTEMPT, attempt_id)
                if stored is not None and stored.record.receipt_state in (OperationState.STARTED, OperationState.OUTCOME_UNKNOWN):
                    return attempt_id
        return None

    def _for_inspect(self, request: Mapping[str, Any], grant: ExecutionGrant) -> dict[str, Any]:
        refs = request['input_refs']
        key = request['operation_key']
        ctx = self._context(request, grant)
        package = self._package(self._one(refs, REF_PACKAGE))
        attempt_id = self._one(refs, REF_ATTEMPT)
        quality = self._sources.quality_inputs(package)
        return {
            'command': InspectOutputCommand(
                grant=grant,
                operation_key=key,
                render_package_id=package.render_package_id,
                render_attempt_id=attempt_id,
                policy=quality.policy,
                expected_language=quality.expected_language,
                word_timings=self._word_timings(package, grant.workspace_id),
                segments=self._segments(package, grant.workspace_id),
                context=ctx,
                warning_results=quality.warning_results,
            )
        }

    def _for_prepare(self, request: Mapping[str, Any], grant: ExecutionGrant) -> dict[str, Any]:
        refs = request['input_refs']
        key = request['operation_key']
        ctx = self._context(request, grant)
        package = self._package(self._one(refs, REF_PACKAGE))
        attempt_id = self._one(refs, REF_ATTEMPT)
        report_id = self._one(refs, REF_QUALITY_REPORT)
        return {
            'command': PrepareOutputReadyCommand(
                grant=grant,
                operation_key=key,
                render_package_id=package.render_package_id,
                render_attempt_id=attempt_id,
                quality_report_ref=report_id,
                video_output_id=f'video-output-{attempt_id}',
                expected_sha256=self._one(refs, REF_EXPECTED_SHA256, required=False),
                context=ctx,
                upload_verified=False,
                completion_committed=False,
            )
        }

    def _segments(self, package: RenderPackageRecord, workspace_id: str) -> list[dict[str, str]]:
        infos = read_script_segments(self._manager, workspace_id=workspace_id, script_version_ref=package.script_version_ref)
        if not infos:
            raise ActivityInputError(SEGMENTS_EMPTY, package.script_version_ref)
        return [{'segment_id': i.segment_id, 'claim_mode': i.claim_mode} for i in infos]

    def _word_timings(self, package: RenderPackageRecord, workspace_id: str) -> list[dict[str, int]]:
        with self._manager.borrow_connection() as connection:
            row = connection.execute(_TIMING_SQL, (workspace_id, package.word_timing_ref)).fetchone()
        if row is None:
            raise ActivityInputError(WORD_TIMING_NOT_FOUND, package.word_timing_ref)
        payload = row[0]
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                raise ActivityInputError(WORD_TIMING_INVALID, package.word_timing_ref)
        if not isinstance(payload, Mapping):
            raise ActivityInputError(WORD_TIMING_INVALID, package.word_timing_ref)
        words = payload.get('words')
        if not isinstance(words, list) or not words:
            raise ActivityInputError(WORD_TIMING_INVALID, 'words')
        result = []
        for w in words:
            if not isinstance(w, Mapping):
                raise ActivityInputError(WORD_TIMING_INVALID, 'words')
            start_ms = w.get('start_ms')
            if type(start_ms) is not int or start_ms < 0:
                raise ActivityInputError(WORD_TIMING_INVALID, 'words')
            result.append({'start_ms': start_ms})
        return result


__all__ = [
    'ActivityInputError',
    'QualityInputs',
    'RenderActivityInputs',
    'RenderInputSources',
    'RenderPlan',
]
