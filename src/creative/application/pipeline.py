"""Creative command chain of D (D-14): eight commands, each one unit of work with its new output, AIInvocationRecord (when AI is called), receipt and outbox event.

coveredIds: TST-INT-INV-004, TST-INT-INV-005

Application layer: depends on domain and ports only, never on adapters, clock, id generation or network; event ids and times come from the caller's EventContext.
GIẢ ĐỊNH (D8): the prompt revision of an ai_role is pinned in the snapshot's configuration_revision_refs (ref_type 'prompt', ref_id = ai_role); a missing pin is INPUT_NOT_READY before any AI call (CT-CFG-002 has no binding yet, CONV-D-07).
"""
from __future__ import annotations

import dataclasses
import enum
import json
from collections.abc import Callable, Mapping
from typing import Any

from controlplane.application.idempotency.canonicalization import request_hash
from controlplane.domain.interfaces.uow import IUnitOfWork
from creative.application.roles import AI_ROLES, ROLE_ANALYSIS, ROLE_ANGLES, ROLE_METADATA, ROLE_PLAN, ROLE_SCRIPT, ROLE_SELECTION, route_key
from creative.domain.analysis import parse_content_analysis
from creative.domain.angles import StoryAngle, build_story_angle_set
from creative.domain.asset_selection import CreativeAssetSelection, select_creative_assets
from creative.domain.output_metadata import OUTPUT_LANGUAGE, OutputMetadata
from creative.domain.production_plan import build_production_plan
from creative.domain.ref_resolver import RefResolver, ResourceRef
from creative.domain.script import build_script_version
from creative.domain.snapshot import ProductionSnapshot, build_production_snapshot
from creative.domain.timeline_mode import TIMELINE_MODE, authorize_timeline_narrative
from creative.domain.untrusted import PROMPT_REVISION_REF_TYPE, PromptEnvelope, UntrustedText
from creative.domain.variant import validate_variant as validate_variant_domain
from creative.ports.ai import AIInvocationPort, ProviderRoutePort
from creative.ports.repositories import (
    CommandReceipt,
    EventContext,
    build_output_metadata_created,
    build_production_plan_created,
    build_production_snapshot_committed,
    build_script_version_created,
    build_story_angles_generated,
    build_variant_validated,
    deduplication_id_for,
)

INPUT_NOT_READY = 'INPUT_NOT_READY'
SCHEMA_VIOLATION = 'ai_output_schema_violation'
HALLUCINATED_REF = 'hallucinated_ref'
CONTEXT_MISMATCH = 'pipeline_context_mismatch'
AI_INVOCATION_FAILED = 'ai_invocation_failed'
IDEMPOTENCY_CONFLICT_CODE = 'IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD'
PROMPT_CONFIG_REF_TYPE = 'prompt'
DATA_SENSITIVITY = 'internal'


class PipelineRejected(Exception):
    """A command is refused: `code` is a stable machine code, `reason` the stable machine reason, `field` locates it; nothing is persisted."""

    def __init__(self, code: str, reason: str, field: str = '') -> None:
        super().__init__(f'{code}: {reason}' + (f' ({field})' if field else ''))
        self.code = code
        self.reason = reason
        self.field = field


class IdempotencyConflict(ValueError):
    """The idempotency key was already used with a different request_hash (TST-INT-INV-005); the stored receipt stays untouched."""

    def __init__(self, command: str, idempotency_key: str, existing_hash: str, incoming_hash: str) -> None:
        super().__init__(IDEMPOTENCY_CONFLICT_CODE)
        self.code = IDEMPOTENCY_CONFLICT_CODE
        self.command = command
        self.idempotency_key = idempotency_key
        self.existing_hash = existing_hash
        self.incoming_hash = incoming_hash


@dataclasses.dataclass(frozen=True, kw_only=True)
class OutputTrace:
    """Refs every output carries; model_ref, prompt_revision and invocation_key are None for commands that do not call AI."""

    snapshot_ref: str
    config_revision: str
    input_revision: str
    model_ref: str | None = None
    prompt_revision: str | None = None
    invocation_key: str | None = None


@dataclasses.dataclass(frozen=True, kw_only=True)
class CommandResult:
    """Outcome of one command; a replay returns the stored receipt with output, event_id and trace None."""

    command: str
    receipt: CommandReceipt
    replayed: bool
    output: object | None
    event_id: str | None
    trace: OutputTrace | None


@dataclasses.dataclass(frozen=True, kw_only=True)
class _Outcome:
    output: object
    aggregate_ref: str
    aggregate_revision: int
    trace: OutputTrace
    event: Any = None


def _plain(value: Any) -> Any:
    """JSON-safe copy of a command argument for request_hash and prompt data: dataclasses, mappings, sequences, sets and enums become plain values."""
    if isinstance(value, enum.Enum):
        return _plain(value.value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {field.name: _plain(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted((_plain(item) for item in value), key=repr)
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value



class CreativePipeline:
    """Runs the eight D commands over one unit-of-work factory, one route port and one AI port; fakes in tests, J adapters later (CONV-D-02)."""

    def __init__(
        self,
        *,
        uow_factory: Callable[[], IUnitOfWork],
        route: ProviderRoutePort,
        ai: AIInvocationPort,
        instructions: Mapping[str, str],
    ) -> None:
        if not callable(uow_factory):
            raise TypeError('uow_factory must be callable')
        if not isinstance(route, ProviderRoutePort) or not isinstance(ai, AIInvocationPort):
            raise TypeError('route and ai must implement the D ports')
        self._uow_factory = uow_factory
        self._route = route
        self._ai = ai
        self._instructions = dict(instructions)

    def _execute(
        self,
        *,
        command: str,
        context: EventContext,
        idempotency_key: str,
        payload: Mapping[str, Any],
        work: Callable[[Any], _Outcome],
    ) -> CommandResult:
        """One unit of work: receipt lookup (replay or conflict), work, receipt, outbox event, commit; any error rolls everything back."""
        if not isinstance(context, EventContext):
            raise TypeError('context must be an EventContext')
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise ValueError('idempotency_key must be a non-empty string')
        workspace_id = context.workspace_id
        digest = request_hash({'workspace_id': workspace_id, 'command_name': command, 'payload': _plain(payload)})
        with self._uow_factory() as uow:
            known = uow.receipts.get(workspace_id, idempotency_key)
            if known is not None:
                if known.request_hash != digest:
                    raise IdempotencyConflict(command, idempotency_key, known.request_hash, digest)
                return CommandResult(command=command, receipt=known, replayed=True, output=None, event_id=None, trace=None)
            outcome = work(uow)
            receipt = CommandReceipt(
                workspace_id=workspace_id,
                idempotency_key=idempotency_key,
                request_hash=digest,
                aggregate_ref=outcome.aggregate_ref,
                aggregate_revision=outcome.aggregate_revision,
            )
            uow.receipts.put(receipt)
            event_id = None
            if outcome.event is not None:
                event = outcome.event
                event_id = uow.outbox.append_event(event.event_name, event.aggregate_id, dict(event.payload), deduplication_id_for(event))
            uow.commit()
        return CommandResult(command=command, receipt=receipt, replayed=False, output=outcome.output, event_id=event_id, trace=outcome.trace)

    @staticmethod
    def _committed_snapshot(uow: Any, snapshot_id: str) -> ProductionSnapshot:
        snapshot = uow.snapshots.get(snapshot_id)
        if snapshot is None:
            raise PipelineRejected(INPUT_NOT_READY, 'snapshot_not_committed', 'snapshot_id')
        return snapshot

    @staticmethod
    def _trace(snapshot: ProductionSnapshot, record: Any = None, invocation_key: str | None = None) -> OutputTrace:
        return OutputTrace(
            snapshot_ref=snapshot.snapshot_id,
            config_revision=snapshot.configuration_bundle_fingerprint,
            input_revision=snapshot.source_set_fingerprint,
            model_ref=None if record is None else record.model_ref,
            prompt_revision=None if record is None else record.prompt_revision,
            invocation_key=invocation_key,
        )

    def _invoke(self, uow: Any, *, context: EventContext, idempotency_key: str, role: str, snapshot: ProductionSnapshot, payload: Mapping[str, Any]) -> tuple[Any, ResourceRef, str]:
        """Route, call and record one AI invocation inside the open unit of work; returns (AIInvocationResult, prompt ResourceRef, invocation key)."""
        workspace_id = context.workspace_id
        pinned = next(
            (ref for ref in snapshot.configuration_revision_refs if ref['ref_type'] == PROMPT_CONFIG_REF_TYPE and ref['ref_id'] == role),
            None,
        )
        if pinned is None:
            raise PipelineRejected(INPUT_NOT_READY, 'missing_prompt_revision', role)
        instructions = self._instructions.get(role)
        if not isinstance(instructions, str) or not instructions.strip():
            raise PipelineRejected(INPUT_NOT_READY, 'missing_instructions', role)
        prompt_ref = ResourceRef(workspace_id, PROMPT_REVISION_REF_TYPE, pinned['ref_id'], pinned['revision_id'])
        provenance = ResourceRef(workspace_id, 'production_snapshot', snapshot.snapshot_id, snapshot.source_set_fingerprint)
        text = json.dumps(_plain(payload), sort_keys=True, ensure_ascii=False)
        envelope = PromptEnvelope(prompt_ref=prompt_ref, instructions=instructions, data=(UntrustedText(text, provenance),))
        decision = self._route.resolve({
            'ai_role': route_key(role),
            'job_ref': snapshot.video_job_ref or snapshot.snapshot_id,
            'snapshot_ref': snapshot.snapshot_id,
            'config_refs': ['{ref_type}:{ref_id}@{revision_id}'.format(**ref) for ref in snapshot.configuration_revision_refs],
            'data_sensitivity': DATA_SENSITIVITY,
            'quality_latency_cost_bounds': {},
            'allowed_fallbacks': [],
        })
        result = self._ai.invoke(decision, envelope)
        if result.record.error is not None:
            raise PipelineRejected(AI_INVOCATION_FAILED, result.record.error, role)
        key = f'{workspace_id}:{idempotency_key}'
        uow.invocations.append(key, 1, result.record)
        return result, prompt_ref, key

    @staticmethod
    def _model_json(result: Any) -> dict[str, Any]:
        try:
            raw = json.loads(result.output.text)
        except ValueError as error:
            raise PipelineRejected(SCHEMA_VIOLATION, 'not_json', '$') from error
        if not isinstance(raw, dict):
            raise PipelineRejected(SCHEMA_VIOLATION, 'not_a_json_object', '$')
        return raw

    @staticmethod
    def _resolver(workspace_id: str, snapshot: ProductionSnapshot, *extra: ResourceRef) -> RefResolver:
        sources = [ResourceRef(workspace_id, ref['ref_type'], ref['ref_id'], ref['revision_id']) for ref in snapshot.source_refs]
        return RefResolver(
            workspace_id=workspace_id,
            allowed_refs=[*sources, *extra],
            allowed_ref_types={ref.ref_type for ref in [*sources, *extra]},
        )

    @staticmethod
    def _resolved(resolver: RefResolver, proposed: Any, field: str) -> ResourceRef:
        resolution = resolver.resolve(proposed)
        if not resolution.ok:
            raise PipelineRejected(HALLUCINATED_REF, resolution.reason, field)
        return resolution.ref

    @staticmethod
    def _stored(repository: Any, key: str, revision: int | None, reason: str, field: str) -> Any:
        matches = [item for item in repository.revisions(key) if revision is None or item.revision == revision]
        if not matches:
            raise PipelineRejected(INPUT_NOT_READY, reason, field)
        return matches[-1].record

    def _analysis(self, uow: Any, snapshot_id: str, analysis_id: str, analysis_revision: int) -> Any:
        analysis = self._stored(uow.analyses, analysis_id, analysis_revision, 'analysis_not_found', 'analysis_id')
        if analysis.snapshot_id != snapshot_id:
            raise PipelineRejected(CONTEXT_MISMATCH, 'analysis_snapshot_mismatch', 'analysis_id')
        return analysis

    def _angle(self, uow: Any, set_id: str, angle_id: str) -> StoryAngle:
        angle_set = self._stored(uow.angle_sets, set_id, None, 'angle_set_not_found', 'set_id')
        angle = next((item for item in angle_set.angles if item.angle_id == angle_id), None)
        if angle is None:
            raise PipelineRejected(INPUT_NOT_READY, 'angle_not_found', 'angle_id')
        return angle

    def _angles(self, resolver: RefResolver, raw: Mapping[str, Any]) -> list[StoryAngle]:
        try:
            return [
                StoryAngle(
                    angle_id=item['angle_id'],
                    title=item['title'],
                    summary=item['summary'],
                    narrative_question=item['narrative_question'],
                    focus_entities=item['focus_entities'],
                    timeframe=item['timeframe'],
                    evidence_refs=tuple(
                        self._resolved(resolver, ref, f'angles[{index}].evidence_refs[{pos}]')
                        for pos, ref in enumerate(item['evidence_refs'])
                    ),
                    planned_inference_elements=item['planned_inference_elements'],
                    planned_creative_elements=item['planned_creative_elements'],
                    suitability=item['suitability'],
                    risk_flags=item['risk_flags'],
                )
                for index, item in enumerate(raw['angles'])
            ]
        except (KeyError, TypeError, ValueError) as error:
            raise PipelineRejected(SCHEMA_VIOLATION, 'invalid_angle', 'angles') from error

    def build_production_snapshot(
        self,
        *,
        context: EventContext,
        idempotency_key: str,
        snapshot_id: str,
        production_mode: str,
        source_refs: Any,
        index_revision_refs: Any,
        configuration_revision_refs: Any,
        content_ref_types: Any,
        eligibility_reason: str | None,
        snapshot_timestamp: str,
        batch_ref: str | None = None,
        video_job_ref: str | None = None,
        recent_variant_exclusions: Any = (),
        timeline_policy: Any = None,
    ) -> CommandResult:
        """BuildProductionSnapshot (CT-AI-001): pin exact revisions; from_then_to_now must pass D-07 before anything is stored."""
        args = {
            'snapshot_id': snapshot_id, 'production_mode': production_mode, 'source_refs': list(source_refs),
            'index_revision_refs': list(index_revision_refs), 'configuration_revision_refs': list(configuration_revision_refs),
            'content_ref_types': list(content_ref_types), 'eligibility_reason': eligibility_reason,
            'snapshot_timestamp': snapshot_timestamp, 'batch_ref': batch_ref, 'video_job_ref': video_job_ref,
            'recent_variant_exclusions': list(recent_variant_exclusions),
        }
        policy_names = None if timeline_policy is None else sorted(timeline_policy.event_update_ref_types)
        payload = {**args, 'timeline_policy': policy_names}

        def work(uow: Any) -> _Outcome:
            snapshot = build_production_snapshot(**args)
            if snapshot.production_mode == TIMELINE_MODE:
                if timeline_policy is None:
                    raise PipelineRejected(INPUT_NOT_READY, 'missing_timeline_policy', 'timeline_policy')
                authorize_timeline_narrative(snapshot, timeline_policy)
            uow.snapshots.add(snapshot)
            event = build_production_snapshot_committed(context, aggregate_id=snapshot.snapshot_id, aggregate_revision=1, snapshot=snapshot)
            return _Outcome(output=snapshot, aggregate_ref=snapshot.snapshot_id, aggregate_revision=1, trace=self._trace(snapshot), event=event)

        return self._execute(command='BuildProductionSnapshot', context=context, idempotency_key=idempotency_key, payload=payload, work=work)

    def analyze_content(
        self, *, context: EventContext, idempotency_key: str, snapshot_id: str, analysis_id: str, revision: int = 1
    ) -> CommandResult:
        """AnalyzeContent (CT-AI-002): one AI call over the pinned snapshot; the trace stored in the analysis comes from the invocation record, never from the model."""
        payload = {'snapshot_id': snapshot_id, 'analysis_id': analysis_id, 'revision': revision}

        def work(uow: Any) -> _Outcome:
            snapshot = self._committed_snapshot(uow, snapshot_id)
            result, prompt_ref, key = self._invoke(
                uow, context=context, idempotency_key=idempotency_key, role=ROLE_ANALYSIS, snapshot=snapshot, payload=payload)
            record = result.record
            raw = self._model_json(result)
            raw.update(
                analysis_id=analysis_id,
                revision=revision,
                trace={
                    'provider': record.provider_ref,
                    'model': record.model_ref,
                    'policy_revision': record.config_revision,
                    'prompt_ref': {
                        'workspace_id': prompt_ref.workspace_id, 'ref_type': prompt_ref.ref_type,
                        'ref_id': prompt_ref.ref_id, 'revision_id': prompt_ref.revision_id,
                    },
                },
            )
            analysis = parse_content_analysis(raw, snapshot, self._resolver(context.workspace_id, snapshot, prompt_ref))
            uow.analyses.append(analysis_id, revision, analysis)
            return _Outcome(
                output=analysis, aggregate_ref=analysis_id, aggregate_revision=revision, trace=self._trace(snapshot, record, key))

        return self._execute(command='AnalyzeContent', context=context, idempotency_key=idempotency_key, payload=payload, work=work)

    def generate_story_angles(
        self,
        *,
        context: EventContext,
        idempotency_key: str,
        snapshot_id: str,
        analysis_id: str,
        analysis_revision: int,
        set_id: str,
        requested_count: int,
        variation_policy_revision: str | None,
        history: Any = (),
        initial_set_fingerprints: Any = (),
    ) -> CommandResult:
        """GenerateStoryAngles (CT-AI-003): one AI call; angle evidence refs go through the resolver; the set is stored with its StoryAnglesGenerated event."""
        history = tuple(history)
        initial = tuple(initial_set_fingerprints)
        payload = {
            'snapshot_id': snapshot_id, 'analysis_id': analysis_id, 'analysis_revision': analysis_revision, 'set_id': set_id,
            'requested_count': requested_count, 'variation_policy_revision': variation_policy_revision,
            'history': history, 'initial_set_fingerprints': initial,
        }

        def work(uow: Any) -> _Outcome:
            snapshot = self._committed_snapshot(uow, snapshot_id)
            self._analysis(uow, snapshot_id, analysis_id, analysis_revision)
            result, _, key = self._invoke(
                uow, context=context, idempotency_key=idempotency_key, role=ROLE_ANGLES, snapshot=snapshot, payload=payload)
            candidates = self._angles(self._resolver(context.workspace_id, snapshot), self._model_json(result))
            angle_set = build_story_angle_set(
                set_id=set_id, analysis_id=analysis_id, analysis_revision=analysis_revision, requested_count=requested_count,
                candidates=candidates, variation_policy_revision=variation_policy_revision, history=history,
                initial_set_fingerprints=initial)
            uow.angle_sets.append(set_id, 1, angle_set)
            event = build_story_angles_generated(context, aggregate_id=set_id, aggregate_revision=1, angle_set=angle_set)
            return _Outcome(
                output=angle_set, aggregate_ref=set_id, aggregate_revision=1, trace=self._trace(snapshot, result.record, key), event=event)

        return self._execute(command='GenerateStoryAngles', context=context, idempotency_key=idempotency_key, payload=payload, work=work)

    def generate_script(
        self,
        *,
        context: EventContext,
        idempotency_key: str,
        snapshot_id: str,
        analysis_id: str,
        analysis_revision: int,
        set_id: str,
        angle_id: str,
        script_version_id: str,
        language_policy: Any,
        target_range: Any,
    ) -> CommandResult:
        """GenerateScript (CT-AI-004): refused before any route or AI call unless the snapshot is committed and the analysis and angle exist."""
        payload = {
            'snapshot_id': snapshot_id, 'analysis_id': analysis_id, 'analysis_revision': analysis_revision, 'set_id': set_id,
            'angle_id': angle_id, 'script_version_id': script_version_id,
            'language_policy': language_policy, 'target_range': target_range,
        }

        def work(uow: Any) -> _Outcome:
            snapshot = self._committed_snapshot(uow, snapshot_id)
            self._analysis(uow, snapshot_id, analysis_id, analysis_revision)
            self._angle(uow, set_id, angle_id)
            result, _, key = self._invoke(
                uow, context=context, idempotency_key=idempotency_key, role=ROLE_SCRIPT, snapshot=snapshot, payload=payload)
            raw = {**self._model_json(result), 'script_version_id': script_version_id}
            script = build_script_version(
                raw, resolver=self._resolver(context.workspace_id, snapshot), language_policy=language_policy, target_range=target_range)
            uow.scripts.append(script_version_id, 1, script)
            event = build_script_version_created(context, aggregate_id=script_version_id, aggregate_revision=1, script=script)
            return _Outcome(
                output=script, aggregate_ref=script_version_id, aggregate_revision=1,
                trace=self._trace(snapshot, result.record, key), event=event)

        return self._execute(command='GenerateScript', context=context, idempotency_key=idempotency_key, payload=payload, work=work)

    def select_creative_assets(
        self,
        *,
        context: EventContext,
        idempotency_key: str,
        snapshot_id: str,
        script_version_id: str,
        set_id: str,
        angle_id: str,
        media_candidates: Any,
        visual_hook_candidates: Any,
        audio_hook_candidates: Any,
        thumbnail_candidates: Any,
        safety_policy: Any,
        music_sfx_policy_revision: str | None,
        preset_registry_revision: str | None,
        weights: Any,
    ) -> CommandResult:
        """SelectCreativeAssets (CT-AI-006): D-13 has no repository for the selection, so the unit of work stores the invocation record and receipt and returns the selection in the result (open item CONV-D-01)."""
        inputs = {
            'media_candidates': list(media_candidates), 'visual_hook_candidates': list(visual_hook_candidates),
            'audio_hook_candidates': list(audio_hook_candidates), 'thumbnail_candidates': list(thumbnail_candidates),
            'safety_policy': safety_policy, 'music_sfx_policy_revision': music_sfx_policy_revision,
            'preset_registry_revision': preset_registry_revision, 'weights': weights,
        }
        payload = {'snapshot_id': snapshot_id, 'script_version_id': script_version_id, 'set_id': set_id, 'angle_id': angle_id, **inputs}

        def work(uow: Any) -> _Outcome:
            snapshot = self._committed_snapshot(uow, snapshot_id)
            self._stored(uow.scripts, script_version_id, None, 'script_not_found', 'script_version_id')
            self._angle(uow, set_id, angle_id)
            result, _, key = self._invoke(
                uow, context=context, idempotency_key=idempotency_key, role=ROLE_SELECTION, snapshot=snapshot, payload=payload)
            selection = select_creative_assets(
                workspace_id=context.workspace_id, snapshot_ref=snapshot_id, script_ref=script_version_id, angle_ref=angle_id,
                proposal=self._model_json(result), **inputs)
            return _Outcome(
                output=selection, aggregate_ref='selection:' + selection.selection_fingerprint, aggregate_revision=1,
                trace=self._trace(snapshot, result.record, key))

        return self._execute(command='SelectCreativeAssets', context=context, idempotency_key=idempotency_key, payload=payload, work=work)

    def build_production_plan(
        self,
        *,
        context: EventContext,
        idempotency_key: str,
        snapshot_id: str,
        script_version_id: str,
        selection: CreativeAssetSelection,
        production_plan_id: str,
        preset_revision_ref: str,
    ) -> CommandResult:
        """BuildProductionPlan (CT-AI-007): one AI call; the plan is built from the stored script and the given selection and stored with ProductionPlanCreated."""
        if not isinstance(selection, CreativeAssetSelection):
            raise TypeError('selection must be a CreativeAssetSelection')
        payload = {
            'snapshot_id': snapshot_id, 'script_version_id': script_version_id, 'production_plan_id': production_plan_id,
            'preset_revision_ref': preset_revision_ref, 'selection_fingerprint': selection.selection_fingerprint,
        }

        def work(uow: Any) -> _Outcome:
            snapshot = self._committed_snapshot(uow, snapshot_id)
            script = self._stored(uow.scripts, script_version_id, None, 'script_not_found', 'script_version_id')
            if selection.snapshot_ref != snapshot_id:
                raise PipelineRejected(CONTEXT_MISMATCH, 'selection_snapshot_mismatch', 'selection')
            result, _, key = self._invoke(
                uow, context=context, idempotency_key=idempotency_key, role=ROLE_PLAN, snapshot=snapshot, payload=payload)
            plan = build_production_plan(
                self._model_json(result), production_plan_id=production_plan_id, script=script, selection=selection,
                preset_revision_ref=preset_revision_ref)
            uow.plans.append(production_plan_id, 1, plan)
            event = build_production_plan_created(context, aggregate_id=production_plan_id, aggregate_revision=1, plan=plan)
            return _Outcome(
                output=plan, aggregate_ref=production_plan_id, aggregate_revision=1,
                trace=self._trace(snapshot, result.record, key), event=event)

        return self._execute(command='BuildProductionPlan', context=context, idempotency_key=idempotency_key, payload=payload, work=work)

    def validate_variant(
        self,
        *,
        context: EventContext,
        idempotency_key: str,
        snapshot_id: str,
        variant_ref: str,
        candidate: Any,
        completed: Any,
        active_reservations: Any,
        same_run: Any,
        registry_revision: int,
        variation_policy_revision: str | None,
        phase: str,
        own_reservation_id: str | None = None,
        output_hash: str | None = None,
    ) -> CommandResult:
        """ValidateVariant (CT-AI-008): pure, no AI call; the result is always stored with its receipt, VariantValidated is emitted only when the variant is valid."""
        inputs = {
            'candidate': candidate, 'completed': list(completed), 'active_reservations': list(active_reservations),
            'registry_revision': registry_revision, 'same_run': list(same_run),
            'variation_policy_revision': variation_policy_revision, 'phase': phase,
            'own_reservation_id': own_reservation_id, 'output_hash': output_hash,
        }
        payload = {'snapshot_id': snapshot_id, 'variant_ref': variant_ref, **inputs}

        def work(uow: Any) -> _Outcome:
            snapshot = self._committed_snapshot(uow, snapshot_id)
            result = validate_variant_domain(**inputs)
            latest = uow.variant_validations.latest(variant_ref)
            revision = 1 if latest is None else latest.revision + 1
            uow.variant_validations.append(variant_ref, revision, result)
            event = None
            if result.valid:
                event = build_variant_validated(context, aggregate_id=variant_ref, aggregate_revision=revision, result=result)
            return _Outcome(output=result, aggregate_ref=variant_ref, aggregate_revision=revision, trace=self._trace(snapshot), event=event)

        return self._execute(command='ValidateVariant', context=context, idempotency_key=idempotency_key, payload=payload, work=work)

    def generate_output_metadata(
        self,
        *,
        context: EventContext,
        idempotency_key: str,
        snapshot_id: str,
        source_job_ref: str,
        source_output_refs: Any,
        metadata_revision: int = 1,
        sanitizer: Any = None,
    ) -> CommandResult:
        """GenerateOutputMetadata (CT-AI-009): one AI call; the optional sanitizer is the D-local filename port and is not part of the request_hash."""
        refs = tuple(source_output_refs)
        payload = {
            'snapshot_id': snapshot_id, 'source_job_ref': source_job_ref, 'source_output_refs': refs,
            'metadata_revision': metadata_revision,
        }

        def work(uow: Any) -> _Outcome:
            snapshot = self._committed_snapshot(uow, snapshot_id)
            result, _, key = self._invoke(
                uow, context=context, idempotency_key=idempotency_key, role=ROLE_METADATA, snapshot=snapshot, payload=payload)
            raw = self._model_json(result)
            try:
                metadata = OutputMetadata(
                    title=raw['title'], caption=raw['caption'], hashtags=tuple(raw['hashtags']), language=OUTPUT_LANGUAGE,
                    source_job_ref=source_job_ref, source_output_refs=refs, metadata_revision=metadata_revision)
            except (KeyError, TypeError, ValueError) as error:
                raise PipelineRejected(SCHEMA_VIOLATION, 'invalid_output_metadata', 'output_metadata') from error
            if sanitizer is not None:
                metadata = metadata.with_filename_safe(sanitizer)
            uow.output_metadata.append(source_job_ref, metadata_revision, metadata)
            event = build_output_metadata_created(
                context, aggregate_id=source_job_ref, aggregate_revision=metadata_revision, metadata=metadata)
            return _Outcome(
                output=metadata, aggregate_ref=source_job_ref, aggregate_revision=metadata_revision,
                trace=self._trace(snapshot, result.record, key), event=event)

        return self._execute(command='GenerateOutputMetadata', context=context, idempotency_key=idempotency_key, payload=payload, work=work)


__all__ = [
    'AI_ROLES',
    'CommandResult',
    'CreativePipeline',
    'IdempotencyConflict',
    'OutputTrace',
    'PipelineRejected',
]
