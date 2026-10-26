"""Production ActivityInputPort of D (PW-D2): input_refs of an ActivityRequest to the typed arguments of the one D-14 command.

Every id built here comes from job_id and the stage revision of stage_run_id, so a retry with the same operation_key gives the same arguments and the command receipt replays. The source set, the media, hook and thumbnail candidates and the variant history come from injected ports; their production sources belong to PW-D3 and to G.
"""
from __future__ import annotations

import dataclasses
import datetime
import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

from controlplane.domain.orchestration import ExecutionGrant
from creative.domain.asset_selection import CreativeAssetSelection
from creative.domain.script import LanguageVoicePolicy, TargetRange
from creative.domain.variant import build_variant_fingerprint
from creative.ports.repositories import EventContext
from creative.worker.activity_handler import CreativeActivityDeps, handle_activity

INPUT_NOT_READY = 'INPUT_NOT_READY'
UNKNOWN_ACTIVITY = 'UNKNOWN_ACTIVITY'
REF_FIELDS = ('ref_type', 'ref_id', 'revision_id')
REF_ARTICLE_REVISION = 'article_revision'
REF_SOURCE_SET = 'source_set'
REF_SNAPSHOT = 'production_snapshot'
REF_ANALYSIS = 'content_analysis'
REF_ANGLE_SET = 'story_angle_set'
REF_SCRIPT = 'script_version'
REF_SELECTION = 'creative_asset_selection'
REF_PLAN = 'production_plan'
REF_VARIANT = 'variant_validation'
REF_SELECTED_MEDIA = 'selected_media'
COMMAND_SELECT = 'SelectCreativeAssets'
SELECTION_INPUT_KEYS = (
    'media_candidates', 'visual_hook_candidates', 'audio_hook_candidates', 'thumbnail_candidates', 'safety_policy',
    'music_sfx_policy_revision', 'preset_registry_revision', 'weights')
VARIANT_CONTEXT_KEYS = ('completed', 'active_reservations', 'same_run', 'registry_revision', 'variation_policy_revision')
PHASE_BY_STAGE = {'plan': 'plan', 'qc': 'output', 'output': 'output'}
_STAGE_RUN_ID = re.compile(r'(.+):([^:]+):r([0-9]+)')


class ActivityInputError(ValueError):
    """The input_refs cannot give the command its inputs; `code` is the stable token the activity handler reports, `reason` the machine reason."""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(f'{code}: {reason}')
        self.code = code
        self.reason = reason


@dataclasses.dataclass(frozen=True, kw_only=True)
class SourceSetPin:
    """The pinned source set of a job; refs carry ref_type, ref_id and revision_id (article_revision refs)."""

    production_mode: str
    source_refs: Sequence[Mapping[str, str]]
    eligibility_reason: str
    index_revision_refs: Sequence[Mapping[str, str]] = ()
    timeline_policy: Any = None


@dataclasses.dataclass(frozen=True, kw_only=True)
class CreativeSettings:
    language_policy: LanguageVoicePolicy
    target_range: TargetRange
    requested_angle_count: int
    variation_policy_revision: str
    preset_revision_ref: str


def _pinned(refs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """The refs as the snapshot pins them (only REF_FIELDS, sorted), so a retry hashes the same as the first call."""
    return sorted(({name: ref[name] for name in REF_FIELDS} for ref in refs), key=lambda ref: tuple(ref[name] for name in REF_FIELDS))


class SourceSetPort(Protocol):
    def source_set(self, *, workspace_id: str, source_set_ref: str) -> SourceSetPin:
        ...


class PromptRefsPort(Protocol):
    def snapshot_refs(self) -> Sequence[Mapping[str, str]]:
        ...


class SelectionInputsPort(Protocol):
    """Candidates, policy and weights of SelectCreativeAssets: a mapping with every key of SELECTION_INPUT_KEYS (PW-D3 provides the production source)."""

    def selection_inputs(self, *, workspace_id: str, snapshot: Any, script: Any, angle: Any) -> Mapping[str, Any]:
        ...


class VariantContextPort(Protocol):
    """Variant history of ValidateVariant: a mapping with every key of VARIANT_CONTEXT_KEYS plus optional own_reservation_id and output_hash (G owns the data)."""

    def variant_context(self, *, workspace_id: str, job_id: str, phase: str, input_refs: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
        ...


def parse_stage_run_id(stage_run_id: str) -> tuple[str, str, int]:
    """(owner, stage, revision) of a stage_run_id `<owner>:<stage>:r<revision>`."""
    match = _STAGE_RUN_ID.fullmatch(stage_run_id) if isinstance(stage_run_id, str) else None
    if match is None:
        raise ActivityInputError(INPUT_NOT_READY, 'invalid_stage_run_id')
    return match.group(1), match.group(2), int(match.group(3))


def variant_phase(stage_run_id: str) -> str:
    """ValidateVariant phase of the stage that runs it: stage plan is phase plan, stage qc (after render) is phase output; any other stage is refused, never defaulted."""
    phase = PHASE_BY_STAGE.get(parse_stage_run_id(stage_run_id)[1])
    if phase is None:
        raise ActivityInputError(INPUT_NOT_READY, 'validate_variant_stage_unsupported')
    return phase


def _iso(moment: datetime.datetime) -> str:
    if not isinstance(moment, datetime.datetime) or moment.tzinfo is None:
        raise ValueError('clock must return a timezone-aware datetime')
    return moment.astimezone(datetime.timezone.utc).replace(microsecond=0).isoformat()


def _last_ref(refs: Sequence[Mapping[str, Any]], ref_type: str) -> Mapping[str, Any]:
    found = [ref for ref in refs if ref.get('ref_type') == ref_type and isinstance(ref.get('ref_id'), str) and ref['ref_id'].strip()]
    if not found:
        raise ActivityInputError(INPUT_NOT_READY, f'missing_{ref_type}_ref')
    return found[-1]


def _revision(ref: Mapping[str, Any]) -> int:
    try:
        value = int(ref.get('revision_id'))
    except (TypeError, ValueError):
        raise ActivityInputError(INPUT_NOT_READY, 'invalid_revision_id') from None
    if value < 1:
        raise ActivityInputError(INPUT_NOT_READY, 'invalid_revision_id')
    return value


def selected_media_refs(selection: CreativeAssetSelection) -> list[dict[str, str]]:
    """One selected_media ref per distinct image of the selection, in scene order (fan-out input of the media stage)."""
    refs: list[dict[str, str]] = []
    seen: set[str] = set()
    for assignment in selection.assignments:
        if assignment.media_asset_id not in seen:
            seen.add(assignment.media_asset_id)
            refs.append({'ref_type': REF_SELECTED_MEDIA, 'ref_id': assignment.media_asset_id, 'revision_id': assignment.artifact_version_ref})
    return refs


def handle_creative_activity(request: Mapping[str, Any], grant: ExecutionGrant, deps: CreativeActivityDeps, selections: Any) -> dict[str, Any]:
    """Production entry point of D: handle_activity, and for SelectCreativeAssets the output refs become the stored selection ref plus one selected_media ref per image."""
    result = handle_activity(request, grant, deps)
    if request.get('activity_name') != COMMAND_SELECT or result.get('disposition') != 'succeeded':
        return result
    stored = next((dict(ref) for ref in result['output_refs'] if ref.get('ref_type') == REF_SELECTION), None)
    if stored is None:
        return result
    selection = selections.load(workspace_id=grant.workspace_id, selection_id=stored['ref_id'])
    if selection is None:
        raise ActivityInputError(INPUT_NOT_READY, 'selection_not_stored')
    return {**result, 'output_refs': [stored, *selected_media_refs(selection)]}


@dataclasses.dataclass(frozen=True)
class _Frame:
    workspace_id: str
    job_id: str
    stage: str
    stage_run_id: str
    revision: int
    refs: Sequence[Mapping[str, Any]]


class ProductionActivityInputs:
    """ActivityInputPort of D for production: `resolve` returns the keyword arguments of the CreativePipeline method named by the activity, with `context` and without `idempotency_key`."""

    def __init__(
        self, *, uow_factory: Callable[[], Any], prompts: PromptRefsPort, sources: SourceSetPort,
        selection_inputs: SelectionInputsPort, variant_context: VariantContextPort, selections: Any,
        settings: CreativeSettings, clock: Callable[[], datetime.datetime],
    ) -> None:
        self._uow_factory = uow_factory
        self._prompts = prompts
        self._sources = sources
        self._selection_inputs = selection_inputs
        self._variants = variant_context
        self._selections = selections
        self._settings = settings
        self._clock = clock
        self._builders = {
            'BuildProductionSnapshot': self._snapshot, 'AnalyzeContent': self._analysis, 'GenerateStoryAngles': self._angles,
            'GenerateScript': self._script, COMMAND_SELECT: self._selection, 'BuildProductionPlan': self._plan,
            'ValidateVariant': self._variant, 'GenerateOutputMetadata': self._metadata,
        }

    def resolve(self, activity_name: str, request: Mapping[str, Any], grant: ExecutionGrant) -> dict[str, Any]:
        builder = self._builders.get(activity_name)
        if builder is None:
            raise ActivityInputError(UNKNOWN_ACTIVITY, 'unknown_activity')
        _, stage, revision = parse_stage_run_id(request['stage_run_id'])
        frame = _Frame(grant.workspace_id, request.get('video_job_id') or grant.job_id, stage, request['stage_run_id'], revision, request['input_refs'])
        key = request['operation_key']
        context = EventContext(
            workspace_id=grant.workspace_id, correlation_id=request['workflow_run_id'], actor='creative-worker',
            occurred_at=_iso(self._clock()), recovery_epoch=str(grant.recovery_epoch), event_id=f'evt:{key}', message_id=f'msg:{key}')
        return {'context': context, **builder(frame)}

    def _read(self, read: Callable[[Any], Any]) -> Any:
        with self._uow_factory() as uow:
            return read(uow)

    @staticmethod
    def _latest(repository: Any, key: str, reason: str) -> Any:
        stored = repository.latest(key)
        if stored is None:
            raise ActivityInputError(INPUT_NOT_READY, reason)
        return stored.record

    def _first_angle(self, set_id: str) -> Any:
        """GIẢ ĐỊNH (D8): the angle used by script, selection and variant is the first angle of the stored set."""
        angle_set = self._read(lambda uow: self._latest(uow.angle_sets, set_id, 'angle_set_not_found'))
        if not angle_set.angles:
            raise ActivityInputError(INPUT_NOT_READY, 'angle_set_empty')
        return angle_set.angles[0]

    def _snapshot(self, frame: _Frame) -> dict[str, Any]:
        pin = self._sources.source_set(workspace_id=frame.workspace_id, source_set_ref=_last_ref(frame.refs, REF_SOURCE_SET)['ref_id'])
        snapshot_id = f'snapshot:{frame.job_id}:r{frame.revision}'
        existing = self._read(lambda uow: uow.snapshots.get(snapshot_id))
        if existing is None:
            configs, stamp = _pinned(self._prompts.snapshot_refs()), _iso(self._clock())
        else:
            configs, stamp = _pinned(existing.configuration_revision_refs), existing.snapshot_timestamp
        return {
            'snapshot_id': snapshot_id, 'production_mode': pin.production_mode, 'source_refs': _pinned(pin.source_refs),
            'index_revision_refs': _pinned(pin.index_revision_refs), 'configuration_revision_refs': configs,
            'content_ref_types': [REF_ARTICLE_REVISION], 'eligibility_reason': pin.eligibility_reason, 'snapshot_timestamp': stamp,
            'video_job_ref': frame.job_id, 'timeline_policy': pin.timeline_policy,
        }

    def _analysis(self, frame: _Frame) -> dict[str, Any]:
        return {
            'snapshot_id': _last_ref(frame.refs, REF_SNAPSHOT)['ref_id'], 'analysis_id': f'analysis:{frame.job_id}:r{frame.revision}',
            'revision': 1,
        }

    def _angles(self, frame: _Frame) -> dict[str, Any]:
        analysis = _last_ref(frame.refs, REF_ANALYSIS)
        return {
            'snapshot_id': _last_ref(frame.refs, REF_SNAPSHOT)['ref_id'], 'analysis_id': analysis['ref_id'],
            'analysis_revision': _revision(analysis), 'set_id': f'angles:{frame.job_id}:r{frame.revision}',
            'requested_count': self._settings.requested_angle_count,
            'variation_policy_revision': self._settings.variation_policy_revision,
        }

    def _script(self, frame: _Frame) -> dict[str, Any]:
        analysis = _last_ref(frame.refs, REF_ANALYSIS)
        set_id = _last_ref(frame.refs, REF_ANGLE_SET)['ref_id']
        return {
            'snapshot_id': _last_ref(frame.refs, REF_SNAPSHOT)['ref_id'], 'analysis_id': analysis['ref_id'],
            'analysis_revision': _revision(analysis), 'set_id': set_id, 'angle_id': self._first_angle(set_id).angle_id,
            'script_version_id': f'script:{frame.job_id}:r{frame.revision}',
            'language_policy': self._settings.language_policy, 'target_range': self._settings.target_range,
        }

    def _selection(self, frame: _Frame) -> dict[str, Any]:
        snapshot_id = _last_ref(frame.refs, REF_SNAPSHOT)['ref_id']
        script_id = _last_ref(frame.refs, REF_SCRIPT)['ref_id']
        set_id = _last_ref(frame.refs, REF_ANGLE_SET)['ref_id']
        angle = self._first_angle(set_id)
        snapshot, script = self._read(
            lambda uow: (uow.snapshots.get(snapshot_id), self._latest(uow.scripts, script_id, 'script_not_found')))
        if snapshot is None:
            raise ActivityInputError(INPUT_NOT_READY, 'snapshot_not_committed')
        extra = self._selection_inputs.selection_inputs(workspace_id=frame.workspace_id, snapshot=snapshot, script=script, angle=angle)
        missing = [name for name in SELECTION_INPUT_KEYS if name not in extra]
        if missing:
            raise ActivityInputError(INPUT_NOT_READY, f'missing_{missing[0]}')
        return {
            'snapshot_id': snapshot_id, 'script_version_id': script_id, 'set_id': set_id, 'angle_id': angle.angle_id,
            **{name: extra[name] for name in SELECTION_INPUT_KEYS},
        }

    def _plan(self, frame: _Frame) -> dict[str, Any]:
        return {
            'snapshot_id': _last_ref(frame.refs, REF_SNAPSHOT)['ref_id'], 'script_version_id': _last_ref(frame.refs, REF_SCRIPT)['ref_id'],
            'selection_ref': _last_ref(frame.refs, REF_SELECTION)['ref_id'],
            'production_plan_id': f'plan:{frame.job_id}:r{frame.revision}', 'preset_revision_ref': self._settings.preset_revision_ref,
        }

    def _variant(self, frame: _Frame) -> dict[str, Any]:
        phase = variant_phase(frame.stage_run_id)
        script_id = _last_ref(frame.refs, REF_SCRIPT)['ref_id']
        plan_id = _last_ref(frame.refs, REF_PLAN)['ref_id']
        script, plan = self._read(
            lambda uow: (self._latest(uow.scripts, script_id, 'script_not_found'), self._latest(uow.plans, plan_id, 'plan_not_found')))
        selection = self._selections.load(workspace_id=frame.workspace_id, selection_id=_last_ref(frame.refs, REF_SELECTION)['ref_id'])
        if selection is None:
            raise ActivityInputError(INPUT_NOT_READY, 'selection_not_found')
        angle = self._first_angle(_last_ref(frame.refs, REF_ANGLE_SET)['ref_id'])
        candidate = build_variant_fingerprint(
            script=script, plan=plan, selection=selection, angle_distinction_fingerprint=angle.distinction_fingerprint)
        context = self._variants.variant_context(workspace_id=frame.workspace_id, job_id=frame.job_id, phase=phase, input_refs=frame.refs)
        missing = [name for name in VARIANT_CONTEXT_KEYS if name not in context]
        if missing:
            raise ActivityInputError(INPUT_NOT_READY, f'missing_{missing[0]}')
        return {
            'snapshot_id': _last_ref(frame.refs, REF_SNAPSHOT)['ref_id'], 'variant_ref': f'variant:{frame.job_id}', 'candidate': candidate,
            **{name: context[name] for name in VARIANT_CONTEXT_KEYS}, 'phase': phase,
            'own_reservation_id': context.get('own_reservation_id'), 'output_hash': context.get('output_hash'),
        }

    def _metadata(self, frame: _Frame) -> dict[str, Any]:
        outputs = [_last_ref(frame.refs, REF_PLAN)['ref_id']]
        variants = [ref['ref_id'] for ref in frame.refs if ref.get('ref_type') == REF_VARIANT]
        if variants:
            outputs.append(variants[-1])
        return {
            'snapshot_id': _last_ref(frame.refs, REF_SNAPSHOT)['ref_id'], 'source_job_ref': frame.job_id,
            'source_output_refs': tuple(outputs), 'metadata_revision': frame.revision,
        }


__all__ = [
    'ActivityInputError',
    'CreativeSettings',
    'ProductionActivityInputs',
    'PromptRefsPort',
    'SelectionInputsPort',
    'SourceSetPin',
    'SourceSetPort',
    'VariantContextPort',
    'handle_creative_activity',
    'parse_stage_run_id',
    'selected_media_refs',
    'variant_phase',
]
