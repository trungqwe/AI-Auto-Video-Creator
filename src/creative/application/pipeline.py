"""Creative command chain of D (D-14): eight commands, each one unit of work with its new output, AIInvocationRecord (when AI is called), receipt and outbox event.

coveredIds: TST-INT-INV-004, TST-INT-INV-005

Application layer: depends on domain and ports only, never on adapters, clock, id generation or network; event ids and times come from the caller's EventContext.
GIẢ ĐỊNH (D8): the prompt revision of an ai_role is pinned in the snapshot's configuration_revision_refs (ref_type 'prompt', ref_id = ai_role); a missing pin is INPUT_NOT_READY before any AI call (CT-CFG-002 has no binding yet, CONV-D-07).
"""
from __future__ import annotations

import dataclasses
import enum
import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

from controlplane.application.model_json import ModelJsonError, parse_model_json_object
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
from creative.application.provider_failure import ProviderCallStatus, ProviderFailureHandler, ProviderFailurePolicy, parse_failure_policy
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
REF_ARTICLE_REVISION = 'article_revision'
SELECTION_ID_PREFIX = 'selection:'
ARTICLE_ROLES = frozenset({ROLE_ANALYSIS, ROLE_ANGLES, ROLE_SCRIPT})
SINGLE_ATTEMPT = 1  # failure_policy=None (D-14, PW-D1, PW-D2 tests that configure no retry): one model call, no retry; production always passes a policy from ai.retry.max_attempts
ORIGIN_AI_GENERATED = 'ai_generated'
AI_ILLUSTRATION_NOTE = 'Includes AI-generated illustrations.'


class PipelineRejected(Exception):
    """A command is refused: `code` is a stable machine code, `reason` the stable machine reason, `field` locates it; nothing is persisted. attempts is the number of model calls made when the output failed validation on every attempt, 0 otherwise."""

    def __init__(self, code: str, reason: str, field: str = '', attempts: int = 0) -> None:
        super().__init__(f'{code}: {reason}' + (f' ({field})' if field else ''))
        self.code = code
        self.reason = reason
        self.field = field
        self.attempts = attempts


class IdempotencyConflict(ValueError):
    """The idempotency key was already used with a different request_hash (TST-INT-INV-005); the stored receipt stays untouched."""

    def __init__(self, command: str, idempotency_key: str, existing_hash: str, incoming_hash: str) -> None:
        super().__init__(IDEMPOTENCY_CONFLICT_CODE)
        self.code = IDEMPOTENCY_CONFLICT_CODE
        self.command = command
        self.idempotency_key = idempotency_key
        self.existing_hash = existing_hash
        self.incoming_hash = incoming_hash


class ProviderWaiting(Exception):
    """The provider has no capacity right now (quota, budget, rate limit, timeout): `code` is a WaitReason value; the activity answers 'waiting' and G tries again later."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


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


@dataclasses.dataclass(frozen=True, kw_only=True)
class _AiPlan:
    """What an AI command reads before the model call: role, snapshot, envelope and route request, the validator of its role (raises on a model-output failure) and the writer that stores the validated output in the second unit of work."""

    role: str
    snapshot: ProductionSnapshot
    envelope: PromptEnvelope
    route_request: Mapping[str, Any]
    validate: Callable[[Any], Any]
    store: Callable[[Any, Any, Any], _Outcome]


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


def _uses_ai_illustration(plans: Sequence[Any]) -> bool:
    """True when a plan timeline has a visual whose origin is ORIGIN_AI_GENERATED; the plan is the source, not the transient ai_illustration ref, because a second video of one article reuses an AI image already registered."""
    for plan in plans:
        timeline = plan.timeline
        segments = timeline.get('segments') if isinstance(timeline, Mapping) else None
        for segment in segments if isinstance(segments, (list, tuple)) else ():
            visuals = segment.get('visuals') if isinstance(segment, Mapping) else None
            for visual in visuals if isinstance(visuals, (list, tuple)) else ():
                if isinstance(visual, Mapping) and visual.get('origin') == ORIGIN_AI_GENERATED:
                    return True
    return False


def _with_illustration_note(metadata: OutputMetadata) -> OutputMetadata:
    if AI_ILLUSTRATION_NOTE in metadata.caption:
        return metadata
    return dataclasses.replace(metadata, caption=metadata.caption.rstrip() + ' ' + AI_ILLUSTRATION_NOTE)


class ArticleContextPort(Protocol):
    """Normalized text of the article revisions a snapshot pins; the pipeline puts it in the data block only (CT-AI-000)."""

    def articles(self, workspace_id: str, source_refs: Sequence[Mapping[str, str]]) -> Sequence[Mapping[str, Any]]:
        ...


class SelectionStorePort(Protocol):
    """Durable CreativeAssetSelection per job: `save` is idempotent for equal content, `load` returns None for an unknown selection_id."""

    def save(self, *, workspace_id: str, job_id: str, selection: CreativeAssetSelection) -> Any:
        ...

    def load(self, *, workspace_id: str, selection_id: str) -> CreativeAssetSelection | None:
        ...


class CreativePipeline:
    """Runs the eight D commands over one unit-of-work factory, one route port and one AI port; fakes in tests, J adapters later (CONV-D-02). failure_policy (ai.retry.max_attempts from the production profile) bounds the model calls of one command; None means a single call."""

    def __init__(
        self,
        *,
        uow_factory: Callable[[], IUnitOfWork],
        route: ProviderRoutePort,
        ai: AIInvocationPort,
        instructions: Mapping[str, str],
        articles: ArticleContextPort | None = None,
        selections: SelectionStorePort | None = None,
        failure_policy: ProviderFailurePolicy | Mapping[str, Any] | None = None,
    ) -> None:
        if not callable(uow_factory):
            raise TypeError('uow_factory must be callable')
        if not isinstance(route, ProviderRoutePort) or not isinstance(ai, AIInvocationPort):
            raise TypeError('route and ai must implement the D ports')
        self._uow_factory = uow_factory
        self._route = route
        self._ai = ai
        self._instructions = dict(instructions)
        self._articles = articles
        self._selections = selections
        self._failures = ProviderFailureHandler(uow_factory=uow_factory, route=route, ai=ai)
        self._failure_policy = None if failure_policy is None else parse_failure_policy(failure_policy)

    def _execute(
        self,
        *,
        command: str,
        context: EventContext,
        idempotency_key: str,
        payload: Mapping[str, Any],
        work: Callable[[Any], _Outcome | _AiPlan],
    ) -> CommandResult:
        """Receipt lookup (replay or conflict), then work: one unit of work, or for an AI command a read-only unit, the bounded model call (attempt records commit on their own) and a second unit with output, receipt and event."""
        if not isinstance(context, EventContext):
            raise TypeError('context must be an EventContext')
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise ValueError('idempotency_key must be a non-empty string')
        workspace_id = context.workspace_id
        digest = request_hash({'workspace_id': workspace_id, 'command_name': command, 'payload': _plain(payload)})
        with self._uow_factory() as uow:
            replay = self._replay(uow, command, workspace_id, idempotency_key, digest)
            if replay is not None:
                return replay
            step = work(uow)
            if isinstance(step, _Outcome):
                return self._finish(uow, command, workspace_id, idempotency_key, digest, step)
        call = self._call_model(step, idempotency_key)
        with self._uow_factory() as uow:
            replay = self._replay(uow, command, workspace_id, idempotency_key, digest)
            if replay is not None:
                return replay
            return self._finish(uow, command, workspace_id, idempotency_key, digest, step.store(uow, call.output, call.final_record))

    @staticmethod
    def _replay(uow, command, workspace_id, idempotency_key, digest) -> CommandResult | None:
        known = uow.receipts.get(workspace_id, idempotency_key)
        if known is None:
            return None
        if known.request_hash != digest:
            raise IdempotencyConflict(command, idempotency_key, known.request_hash, digest)
        return CommandResult(command=command, receipt=known, replayed=True, output=None, event_id=None, trace=None)

    @staticmethod
    def _finish(uow, command, workspace_id, idempotency_key, digest, outcome: _Outcome) -> CommandResult:
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

    def _call_model(self, plan: _AiPlan, idempotency_key: str) -> Any:
        """The bounded call of CT-AI-ROUTE-002: returns the accepted ProviderCallOutcome; anything else raises ProviderWaiting, PipelineRejected (code of the last failed output, attempts) or PipelineRejected(AI_INVOCATION_FAILED)."""
        configured = self._failure_policy is not None
        policy = self._failure_policy if configured else ProviderFailurePolicy(max_attempts=SINGLE_ATTEMPT)
        rejections: list[Exception] = []

        def validate(result: Any) -> Any:
            try:
                return plan.validate(result)
            except Exception as rejected:
                rejections.append(rejected)
                raise

        outcome = self._failures.run(
            idempotency_key=idempotency_key, route_request=plan.route_request, envelope=plan.envelope,
            config_revision=plan.snapshot.configuration_bundle_fingerprint, validator=validate, policy=policy,
            retry_same_provider=configured)
        if outcome.status is not ProviderCallStatus.WAITING:
            return outcome
        problem, last = outcome.problem, outcome.final_record
        if problem is None or last is None:
            raise PipelineRejected(AI_INVOCATION_FAILED, 'no_attempt_made', plan.role)
        if problem.wait_code:
            raise ProviderWaiting(problem.wait_code)
        if last.validation_result == 'failed':
            final = rejections[-1] if rejections else PipelineRejected(problem.code, problem.reason, problem.field)
            final.attempts = len(outcome.records)  # the role's own rejection (AnalysisRejected, ScriptRejected, ...) keeps its type
            raise final
        raise PipelineRejected(AI_INVOCATION_FAILED, problem.reason, plan.role)

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

    @staticmethod
    def _prior_item(workspace_id: str, kind: str, ref_type: str, ref_id: str, revision: Any, value: Any) -> tuple[str, Any, ResourceRef]:
        """An earlier-stage result for the data block of the next call: its kind, the stored record and where it came from."""
        return (kind, value, ResourceRef(workspace_id, ref_type, ref_id, str(revision)))

    @staticmethod
    def _data_item(kind: str, value: Any, provenance: ResourceRef) -> UntrustedText:
        """External or earlier-stage content as one untrusted JSON data item: kind, content and the source ref (workspace_id, ref_type, ref_id, revision_id of its provenance) so the model can cite it; it is never part of the instructions."""
        return UntrustedText(json.dumps({'kind': kind, 'content': _plain(value), 'ref': _plain(provenance)}, sort_keys=True, ensure_ascii=False), provenance)

    def _article_data(self, workspace_id: str, snapshot: ProductionSnapshot, role: str) -> list[UntrustedText]:
        """Normalized text of the snapshot's article revisions for the roles that read content; a revision that is not stored is INPUT_NOT_READY."""
        if self._articles is None or role not in ARTICLE_ROLES:
            return []
        refs = [ref for ref in snapshot.source_refs if ref['ref_type'] == REF_ARTICLE_REVISION]
        items = list(self._articles.articles(workspace_id, refs))
        if len(items) != len(refs):
            raise PipelineRejected(INPUT_NOT_READY, 'article_revision_not_found', 'source_refs')
        return [
            self._data_item('article', item, ResourceRef(workspace_id, REF_ARTICLE_REVISION, item['article_id'], item['article_revision_id']))
            for item in items
        ]

    def _stored_selection(self, workspace_id: str, selection_ref: str) -> CreativeAssetSelection:
        """The selection read from the selection store by its id; no store or an unknown id is INPUT_NOT_READY."""
        if self._selections is None:
            raise PipelineRejected(INPUT_NOT_READY, 'selection_store_missing', 'selection_ref')
        found = self._selections.load(workspace_id=workspace_id, selection_id=selection_ref)
        if found is None:
            raise PipelineRejected(INPUT_NOT_READY, 'selection_not_found', 'selection_ref')
        return found

    @staticmethod
    def _key(context: EventContext, idempotency_key: str) -> str:
        return f'{context.workspace_id}:{idempotency_key}'

    def _ai_plan(self, *, context: EventContext, role: str, snapshot: ProductionSnapshot, payload: Mapping[str, Any], validate: Callable[[Any, ResourceRef], Any], store: Callable[[Any, Any, Any], _Outcome], prior: Sequence[tuple[str, Any, ResourceRef]] = ()) -> _AiPlan:
        """Everything an AI command reads before the model call; the data block holds the payload ids, the article text (analysis, angles and script only) and the earlier results in `prior`, never the instructions. The route is resolved and the model called later by _call_model, outside any unit of work."""
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
        data = [
            UntrustedText(json.dumps(_plain(payload), sort_keys=True, ensure_ascii=False), provenance),
            *self._article_data(workspace_id, snapshot, role),
            *(self._data_item(kind, value, ref) for kind, value, ref in prior),
        ]
        envelope = PromptEnvelope(prompt_ref=prompt_ref, instructions=instructions, data=tuple(data))
        route_request = {
            'ai_role': route_key(role),
            'job_ref': snapshot.video_job_ref or snapshot.snapshot_id,
            'snapshot_ref': snapshot.snapshot_id,
            'config_refs': ['{ref_type}:{ref_id}@{revision_id}'.format(**ref) for ref in snapshot.configuration_revision_refs],
            'data_sensitivity': DATA_SENSITIVITY,
            'quality_latency_cost_bounds': {},
            'allowed_fallbacks': [],
        }
        return _AiPlan(
            role=role, snapshot=snapshot, envelope=envelope, route_request=route_request,
            validate=lambda result: validate(result, prompt_ref), store=store)

    @staticmethod
    def _model_json(result: Any) -> dict[str, Any]:
        try:
            return parse_model_json_object(result.output.text)
        except ModelJsonError as error:
            raise PipelineRejected(SCHEMA_VIOLATION, error.reason, '$') from error

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
        """AnalyzeContent (CT-AI-002): one AI call per attempt, at most max_attempts attempts, over the pinned snapshot; the trace stored in the analysis comes from the invocation record, never from the model."""
        payload = {'snapshot_id': snapshot_id, 'analysis_id': analysis_id, 'revision': revision}

        def work(uow: Any) -> _Outcome | _AiPlan:
            snapshot = self._committed_snapshot(uow, snapshot_id)
            key = self._key(context, idempotency_key)

            def validate(result: Any, prompt_ref: ResourceRef) -> Any:
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
                return parse_content_analysis(raw, snapshot, self._resolver(context.workspace_id, snapshot, prompt_ref))

            def store(unit: Any, analysis: Any, record: Any) -> _Outcome:
                unit.analyses.append(analysis_id, revision, analysis)
                return _Outcome(
                    output=analysis, aggregate_ref=analysis_id, aggregate_revision=revision, trace=self._trace(snapshot, record, key))

            return self._ai_plan(
                context=context, role=ROLE_ANALYSIS, snapshot=snapshot, payload=payload, validate=validate, store=store)

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

        def work(uow: Any) -> _Outcome | _AiPlan:
            snapshot = self._committed_snapshot(uow, snapshot_id)
            analysis = self._analysis(uow, snapshot_id, analysis_id, analysis_revision)
            prior = [self._prior_item(context.workspace_id, 'content_analysis', 'content_analysis', analysis_id, analysis_revision, analysis)]
            key = self._key(context, idempotency_key)

            def validate(result: Any, prompt_ref: ResourceRef) -> Any:
                candidates = self._angles(self._resolver(context.workspace_id, snapshot), self._model_json(result))
                return build_story_angle_set(
                    set_id=set_id, analysis_id=analysis_id, analysis_revision=analysis_revision, requested_count=requested_count,
                    candidates=candidates, variation_policy_revision=variation_policy_revision, history=history,
                    initial_set_fingerprints=initial)

            def store(unit: Any, angle_set: Any, record: Any) -> _Outcome:
                unit.angle_sets.append(set_id, 1, angle_set)
                event = build_story_angles_generated(context, aggregate_id=set_id, aggregate_revision=1, angle_set=angle_set)
                return _Outcome(
                    output=angle_set, aggregate_ref=set_id, aggregate_revision=1, trace=self._trace(snapshot, record, key), event=event)

            return self._ai_plan(
                context=context, role=ROLE_ANGLES, snapshot=snapshot, payload=payload, prior=prior, validate=validate, store=store)

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

        def work(uow: Any) -> _Outcome | _AiPlan:
            snapshot = self._committed_snapshot(uow, snapshot_id)
            analysis = self._analysis(uow, snapshot_id, analysis_id, analysis_revision)
            angle = self._angle(uow, set_id, angle_id)
            prior = [
                self._prior_item(context.workspace_id, 'content_analysis', 'content_analysis', analysis_id, analysis_revision, analysis),
                self._prior_item(context.workspace_id, 'story_angle', 'story_angle', angle_id, set_id, angle),
            ]
            key = self._key(context, idempotency_key)

            def validate(result: Any, prompt_ref: ResourceRef) -> Any:
                raw = {**self._model_json(result), 'script_version_id': script_version_id}
                return build_script_version(
                    raw, resolver=self._resolver(context.workspace_id, snapshot), language_policy=language_policy, target_range=target_range)

            def store(unit: Any, script: Any, record: Any) -> _Outcome:
                unit.scripts.append(script_version_id, 1, script)
                event = build_script_version_created(context, aggregate_id=script_version_id, aggregate_revision=1, script=script)
                return _Outcome(
                    output=script, aggregate_ref=script_version_id, aggregate_revision=1,
                    trace=self._trace(snapshot, record, key), event=event)

            return self._ai_plan(
                context=context, role=ROLE_SCRIPT, snapshot=snapshot, payload=payload, prior=prior, validate=validate, store=store)

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
        """SelectCreativeAssets (CT-AI-006): one AI call; with a selection store the selection is saved per job (idempotent) and the receipt names it as 'selection:<selection_fingerprint>'."""
        inputs = {
            'media_candidates': list(media_candidates), 'visual_hook_candidates': list(visual_hook_candidates),
            'audio_hook_candidates': list(audio_hook_candidates), 'thumbnail_candidates': list(thumbnail_candidates),
            'safety_policy': safety_policy, 'music_sfx_policy_revision': music_sfx_policy_revision,
            'preset_registry_revision': preset_registry_revision, 'weights': weights,
        }
        payload = {'snapshot_id': snapshot_id, 'script_version_id': script_version_id, 'set_id': set_id, 'angle_id': angle_id, **inputs}

        def work(uow: Any) -> _Outcome | _AiPlan:
            snapshot = self._committed_snapshot(uow, snapshot_id)
            script = self._stored(uow.scripts, script_version_id, None, 'script_not_found', 'script_version_id')
            angle = self._angle(uow, set_id, angle_id)
            prior = [
                self._prior_item(context.workspace_id, 'script', 'script_version', script_version_id, script.script_fingerprint, script),
                self._prior_item(context.workspace_id, 'story_angle', 'story_angle', angle_id, set_id, angle),
            ]
            key = self._key(context, idempotency_key)

            def validate(result: Any, prompt_ref: ResourceRef) -> Any:
                return select_creative_assets(
                    workspace_id=context.workspace_id, snapshot_ref=snapshot_id, script_ref=script_version_id, angle_ref=angle_id,
                    proposal=self._model_json(result), **inputs)

            def store(unit: Any, selection: Any, record: Any) -> _Outcome:
                if self._selections is not None:
                    self._selections.save(workspace_id=context.workspace_id, job_id=snapshot.video_job_ref or snapshot_id, selection=selection)
                return _Outcome(
                    output=selection, aggregate_ref='selection:' + selection.selection_fingerprint, aggregate_revision=1,
                    trace=self._trace(snapshot, record, key))

            return self._ai_plan(
                context=context, role=ROLE_SELECTION, snapshot=snapshot, payload=payload, prior=prior, validate=validate, store=store)

        return self._execute(command='SelectCreativeAssets', context=context, idempotency_key=idempotency_key, payload=payload, work=work)

    def build_production_plan(
        self,
        *,
        context: EventContext,
        idempotency_key: str,
        snapshot_id: str,
        script_version_id: str,
        selection: CreativeAssetSelection | None = None,
        production_plan_id: str,
        preset_revision_ref: str,
        selection_ref: str | None = None,
    ) -> CommandResult:
        """BuildProductionPlan (CT-AI-007): one AI call; the plan is built from the stored script and a selection, either given or read from the selection store by `selection_ref`, and stored with ProductionPlanCreated."""
        if (selection is None) == (selection_ref is None):
            raise ValueError('exactly one of selection and selection_ref is required')
        if selection is not None and not isinstance(selection, CreativeAssetSelection):
            raise TypeError('selection must be a CreativeAssetSelection')
        payload = {
            'snapshot_id': snapshot_id, 'script_version_id': script_version_id, 'production_plan_id': production_plan_id,
            'preset_revision_ref': preset_revision_ref,
        }
        if selection is not None:
            payload['selection_fingerprint'] = selection.selection_fingerprint
        else:
            payload['selection_ref'] = selection_ref

        def work(uow: Any) -> _Outcome | _AiPlan:
            snapshot = self._committed_snapshot(uow, snapshot_id)
            script = self._stored(uow.scripts, script_version_id, None, 'script_not_found', 'script_version_id')
            chosen =selection if selection is not None else self._stored_selection(context.workspace_id, selection_ref)
            if chosen.snapshot_ref != snapshot_id:
                raise PipelineRejected(CONTEXT_MISMATCH, 'selection_snapshot_mismatch', 'selection')
            prior = [
                self._prior_item(context.workspace_id, 'script', 'script_version', script_version_id, script.script_fingerprint, script),
                self._prior_item(
                    context.workspace_id, 'selection', 'creative_asset_selection', SELECTION_ID_PREFIX + chosen.selection_fingerprint,
                    chosen.selection_fingerprint, chosen),
            ]
            key = self._key(context, idempotency_key)

            def validate(result: Any, prompt_ref: ResourceRef) -> Any:
                return build_production_plan(
                    self._model_json(result), production_plan_id=production_plan_id, script=script, selection=chosen,
                    preset_revision_ref=preset_revision_ref)

            def store(unit: Any, plan: Any, record: Any) -> _Outcome:
                unit.plans.append(production_plan_id, 1, plan)
                event = build_production_plan_created(context, aggregate_id=production_plan_id, aggregate_revision=1, plan=plan)
                return _Outcome(
                    output=plan, aggregate_ref=production_plan_id, aggregate_revision=1,
                    trace=self._trace(snapshot, record, key), event=event)

            return self._ai_plan(
                context=context, role=ROLE_PLAN, snapshot=snapshot, payload=payload, prior=prior, validate=validate, store=store)

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

        def work(uow: Any) -> _Outcome | _AiPlan:
            snapshot = self._committed_snapshot(uow, snapshot_id)
            plans =[stored.record for stored in (uow.plans.latest(ref) for ref in refs) if stored is not None]
            illustrated = _uses_ai_illustration(plans)
            prior = [
                self._prior_item(context.workspace_id, 'plan', 'production_plan', plan.production_plan_id, plan.plan_fingerprint, plan)
                for plan in plans
            ]
            key = self._key(context, idempotency_key)

            def validate(result: Any, prompt_ref: ResourceRef) -> Any:
                raw = self._model_json(result)
                try:
                    metadata = OutputMetadata(
                        title=raw['title'], caption=raw['caption'], hashtags=tuple(raw['hashtags']), language=OUTPUT_LANGUAGE,
                        source_job_ref=source_job_ref, source_output_refs=refs, metadata_revision=metadata_revision)
                except (KeyError, TypeError, ValueError) as error:
                    raise PipelineRejected(SCHEMA_VIOLATION, 'invalid_output_metadata', 'output_metadata') from error
                if illustrated:
                    metadata = _with_illustration_note(metadata)
                if sanitizer is not None:
                    metadata = metadata.with_filename_safe(sanitizer)
                return metadata

            def store(unit: Any, metadata: Any, record: Any) -> _Outcome:
                unit.output_metadata.append(source_job_ref, metadata_revision, metadata)
                event = build_output_metadata_created(
                    context, aggregate_id=source_job_ref, aggregate_revision=metadata_revision, metadata=metadata)
                return _Outcome(
                    output=metadata, aggregate_ref=source_job_ref, aggregate_revision=metadata_revision,
                    trace=self._trace(snapshot, record, key), event=event)

            return self._ai_plan(
                context=context, role=ROLE_METADATA, snapshot=snapshot, payload=payload, prior=prior, validate=validate, store=store)

        return self._execute(command='GenerateOutputMetadata', context=context, idempotency_key=idempotency_key, payload=payload, work=work)


__all__ = [
    'AI_ROLES',
    'ArticleContextPort',
    'CommandResult',
    'CreativePipeline',
    'IdempotencyConflict',
    'OutputTrace',
    'PipelineRejected',
    'ProviderWaiting',
    'SelectionStorePort',
]
