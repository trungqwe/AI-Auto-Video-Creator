from __future__ import annotations

"""ADAPT-WIRE: wiring cho phân hệ D (creative).
GIẢ ĐỊNH: capacities trả None (chưa có nguồn snapshot hạn mức, resolver coi là không rõ);
intent_policy bảo thủ (snapshot_committed False, fallback_allowed_after_snapshot False);
units 1; desktop_online luôn True vì v1 chỉ chạy trên máy này; một workspace mỗi lần dựng."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import partial
from typing import Any
from controlplane.api.wiring.workflow import creative_handler
from controlplane.domain.orchestration import ReservationState, VariantReservation
from controlplane.infrastructure.db.control_api_commands import PostgresConfigScope
from controlplane.infrastructure.db.orchestration.variants import PostgresVariantRegistry
from creative.adapters.activity_inputs import (
    ActivityInputError,
    CreativeSettings,
    ProductionActivityInputs,
    REF_SELECTION,
    selected_media_refs,
)
from creative.adapters.article_context import PostgresArticleContext
from creative.adapters.prompt_source import ConfigPromptSource
from creative.application.pipeline import CreativePipeline
from creative.application.provider_failure import ProviderFailurePolicy
from creative.domain.asset_selection import SafetyRightsPolicy, ScoringWeights
from creative.domain.layout_choice import DEFAULT_LAYOUT, LAYOUT_KEYS
from creative.domain.script import LanguageVoicePolicy, TargetRange, INPUT_NOT_READY, SCRIPT_CHARS_PER_SECOND
from creative.worker.activity_handler import CreativeActivityDeps
from zoneinfo import ZoneInfo

from controlplane.api.wiring._shared import PooledCostLedger, PooledReservationStore
from controlplane.api.wiring.production_profile import (
    PROFILE_PRODUCTION,
    WiringConfig,
)
from controlplane.application.config_security.capacity_reservation import (
    CapacityReservationBook,
)
from controlplane.application.config_security.fallback_policy import (
    FallbackIntentPolicy,
)
from controlplane.application.config_security.route_resolver import (
    ProviderRouteResolver,
)
from controlplane.application.config_security.routed_invocation import (
    RoutedInvocationService,
)
from controlplane.domain.config_security.route_binding import (
    ProviderRouteRequest,
)
from creative.adapters.fake_ai import FakeAIAdapter, FakeProviderRoute
from creative.adapters.memory import InMemoryUnitOfWork
from creative.adapters.real_ai_invocation import (
    RoutedAIInvocation,
    budget_policy_from_config,
)
from creative.adapters.real_route_executor import (
    InvocationPayloadStore,
    NineRouterExecutor,
    RouteExecutorConfig,
)
from creative.domain.invocation import (
    ProviderRouteDecision as CreativeRouteDecision,
    RouteContractViolation,
    validate_provider_route_request,
)
from creative.persistence.uow import PostgresCreativeUnitOfWork


class RoutedProviderRoute:
    def __init__(
        self,
        resolver: ProviderRouteResolver,
        workspace_id: str,
        units: int,
        ttl_seconds: int,
        clock: Callable[[], datetime],
        desktop_online: Callable[[], bool],
    ) -> None:
        self._resolver = resolver
        self._workspace_id = workspace_id
        self._units = units
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._desktop_online = desktop_online
        self.requests: dict[str, ProviderRouteRequest] = {}

    def resolve(self, request: Mapping[str, Any]) -> CreativeRouteDecision:
        issues = validate_provider_route_request(request)
        if issues:
            raise RouteContractViolation('ProviderRouteRequest', issues)
        req = ProviderRouteRequest(
            ai_role=request['ai_role'],
            job_ref=request['job_ref'],
            snapshot_ref=request['snapshot_ref'],
            config_refs=list(request['config_refs']),
            data_sensitivity=request['data_sensitivity'],
            quality_latency_cost_bounds=dict(request['quality_latency_cost_bounds']),
            allowed_fallbacks=list(request['allowed_fallbacks']),
            health_quota_ref=request.get('health_quota_ref'),
        )
        decision = self._resolver.resolve(
            req,
            self._workspace_id,
            self._clock(),
            self._units,
            self._ttl_seconds,
            self._desktop_online(),
        )
        self.requests[decision.capacity_reservation_ref] = req
        payload: dict[str, Any] = {
            'provider_ref': decision.provider_ref,
            'model_ref': decision.model_ref,
            'account_ref': decision.account_ref,
            'route_revision': decision.route_revision,
            'rationale_codes': list(decision.rationale_codes),
            'fallback_order': list(decision.fallback_order),
            'capacity_reservation_ref': decision.capacity_reservation_ref,
            'credential_acquisition_method': decision.credential_acquisition_method,
            'estimated_cost_class': decision.estimated_cost_class,
        }
        if decision.project_ref is not None:
            payload['project_ref'] = decision.project_ref
        return CreativeRouteDecision.from_payload(payload)

    def request_for(self, ref: str) -> ProviderRouteRequest:
        return self.requests[ref]


def monthly_window(timezone_name: str) -> Callable[[datetime], tuple[datetime, datetime]]:
    tz = ZoneInfo(timezone_name)

    def window(now: datetime) -> tuple[datetime, datetime]:
        local = now.astimezone(tz)
        start = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        nxt = (start + timedelta(days=32)).replace(day=1)
        return (start.astimezone(timezone.utc), nxt.astimezone(timezone.utc))

    return window


@dataclass(frozen=True)
class CreativeServices:
    mode: str
    uow_factory: Callable[[], Any]
    route: Any
    ai: Any
    executor: Any
    payload_store: Any


def build_creative_services(manager: Any, config: WiringConfig) -> CreativeServices:
    if config.mode != PROFILE_PRODUCTION:
        route = FakeProviderRoute()
        ai = FakeAIAdapter(route, responses={}, config_revision='test-profile')
        return CreativeServices(config.mode, InMemoryUnitOfWork, route, ai, None, None)

    profile, runtime = config.production_parts()
    a = profile.ai
    rev = f'profile-{profile.revision}'
    clock = lambda: datetime.now(timezone.utc)
    executor_config = RouteExecutorConfig.from_mapping({
        'endpoint': a.route_endpoint,
        'approved_endpoints': [a.route_endpoint],
        'request_timeout_seconds': a.request_timeout_seconds,
        'max_retries': a.retry.max_attempts - 1,
        'backoff_factor': a.retry.backoff_base_seconds,
        'cost_per_request': runtime.route_cost_per_request,
    })
    store = InvocationPayloadStore()
    executor = NineRouterExecutor(executor_config, store, runtime.provider_credentials)
    budget = budget_policy_from_config({
        'monthly_limit': profile.budget.monthly_limit,
        'hard_stop': profile.budget.hard_stop,
        'warn_ratio': profile.budget.warn_at_ratio,
        'currency': profile.budget.currency,
    })
    book = CapacityReservationBook(PooledReservationStore(manager, config.workspace_id))
    resolver = ProviderRouteResolver(runtime.route_catalog, book, lambda domain_key: None, rev)
    service = RoutedInvocationService(
        resolver,
        executor,
        budget,
        PooledCostLedger(manager),
        monthly_window(profile.budget.window_timezone),
        model_ref_for=a.route_model_refs.get,
    )
    route = RoutedProviderRoute(resolver, config.workspace_id, 1, a.reservation_ttl_seconds, clock, lambda: True)
    ai = RoutedAIInvocation(
        service,
        store,
        request_for=route.request_for,
        clock=clock,
        config_revision=rev,
        intent_policy=FallbackIntentPolicy(snapshot_committed=False, fallback_allowed_after_snapshot=False),
        units=1,
        ttl_seconds=a.reservation_ttl_seconds,
        desktop_online=lambda: True,
    )
    uow_factory = partial(PostgresCreativeUnitOfWork, manager, workspace_id=config.workspace_id)
    return CreativeServices('production', uow_factory, route, ai, executor, store)




class PostgresPromptScope:
    def __init__(self, manager: Any) -> None:
        self._manager = manager

    def current(self, *, workspace_id: str, scope_kind: str, scope_key: str) -> Any | None:
        with self._manager.borrow_connection() as connection:
            return PostgresConfigScope(connection).current(
                workspace_id=workspace_id, scope_kind=scope_kind, scope_key=scope_key
            )


class LazyInstructions(Mapping):
    def __init__(self, prompts: Any) -> None:
        self._prompts = prompts
        self._cache: dict[str, str] | None = None

    def _get(self) -> dict[str, str]:
        if self._cache is None:
            self._cache = self._prompts.instructions()
        return self._cache

    def __getitem__(self, key: str) -> str:
        return self._get()[key]

    def __iter__(self):
        return iter(self._get())

    def get(self, key: str, default: Any = None) -> Any:
        return self._get().get(key, default)

    def __len__(self) -> int:
        return len(self._get())


def layout_presets_of(presets: object) -> dict[str, str] | None:
    """PRS-LAYOUT-QUOTA (FR-PRS-003): layout key -> preset name, inverted from render.presets.variants.<preset>.layout of the profile;
    None unless each of the five layouts is named by exactly one variant (the plan then keeps the fixed preset as before)."""
    variants = presets.get('variants') if isinstance(presets, Mapping) else None
    if not isinstance(variants, Mapping):
        return None
    found: dict[str, str] = {}
    for name, variant in variants.items():
        layout = variant.get('layout') if isinstance(variant, Mapping) else None
        if layout is None:
            continue
        if layout not in LAYOUT_KEYS or layout in found or not isinstance(name, str) or not name.strip():
            return None
        found[layout] = name
    return found if set(found) == set(LAYOUT_KEYS) else None


# PRS-LAYOUT-QUOTA: layouts already used by the other jobs of a job's batch (latest plan of each job, failed jobs left out) and the
# batch target_count; the creative pipeline caps a layout at BATCH_SHARE_MAX of the batch with them (creative.domain.layout_choice).
LAYOUT_USAGE_SQL = (
    "SELECT DISTINCT ON (j.job_id) p.payload->'layout_choice'->>'layout_key' FROM controlplane.cp_video_jobs j "
    "JOIN controlplane.cp_production_plans p ON p.workspace_id = j.workspace_id AND p.production_plan_id LIKE 'plan:' || j.job_id || ':r%' "
    "WHERE j.workspace_id = %s::uuid AND j.batch_id = (SELECT batch_id FROM controlplane.cp_video_jobs WHERE workspace_id = %s::uuid AND job_id = %s) "
    "AND j.job_id <> %s AND j.status <> 'FAILED_FINAL' ORDER BY j.job_id, p.created_at DESC"
)
LAYOUT_TARGET_SQL = (
    'SELECT b.target_count FROM controlplane.cp_production_batches b JOIN controlplane.cp_video_jobs j '
    'ON j.workspace_id = b.workspace_id AND j.batch_id = b.batch_id WHERE j.workspace_id = %s::uuid AND j.job_id = %s'
)


class PostgresLayoutUsage:
    """LayoutUsagePort of the creative activity inputs over the control plane tables; None (no cap) when the job has no batch row."""

    def __init__(self, manager: Any) -> None:
        self._manager = manager

    def usage(self, *, workspace_id: str, job_id: str) -> tuple[dict[str, int], int] | None:
        with self._manager.borrow_connection() as conn:
            target = conn.execute(LAYOUT_TARGET_SQL, (workspace_id, job_id)).fetchone()
            if target is None:
                return None
            rows = conn.execute(LAYOUT_USAGE_SQL, (workspace_id, workspace_id, job_id, job_id)).fetchall()
        used: dict[str, int] = {}
        for (key,) in rows:
            if key in LAYOUT_KEYS:
                used[key] = used.get(key, 0) + 1
        return used, int(target[0])


def creative_settings(profile: Any) -> CreativeSettings:
    min_ms = 60000
    max_ms = 70000
    dur = None
    v = getattr(profile, 'voice', None)
    if v is not None and hasattr(v, 'duration_range_ms'):
        dur = getattr(v, 'duration_range_ms')
    elif hasattr(profile, 'parameters') and isinstance(profile.parameters, Mapping):
        dur = profile.parameters.get('voice.duration_range_ms')
    if isinstance(dur, Mapping):
        min_ms = dur.get('min', min_ms)
        max_ms = dur.get('max', max_ms)
    min_s = float(min_ms) / 1000.0
    max_s = float(max_ms) / 1000.0
    target_range = TargetRange(min_seconds=min_s, max_seconds=max_s)

    lang = 'en'
    qc = getattr(profile, 'qc', None)
    if qc is not None and hasattr(qc, 'required_language'):
        lang = str(getattr(qc, 'required_language'))
    elif hasattr(profile, 'parameters') and isinstance(profile.parameters, Mapping):
        lang = str(profile.parameters.get('qc.required_language', 'en'))

    wpm = 150.0
    if hasattr(profile, 'parameters') and isinstance(profile.parameters, Mapping):
        if 'voice.speech_rate_wpm' in profile.parameters:
            try:
                wpm = float(profile.parameters['voice.speech_rate_wpm'])
            except Exception:
                pass
    speech_rate = max(0.1, wpm / 60.0)
    language_policy = LanguageVoicePolicy(language=lang, speech_rate=speech_rate, chars_per_second=SCRIPT_CHARS_PER_SECOND)

    rev = getattr(profile, 'revision', 1)
    variation_policy_revision = f'profile-{rev}'
    requested_angle_count = 2
    preset_revision_ref = 'preset-default'
    layout_presets = None
    if hasattr(profile, 'parameters') and isinstance(profile.parameters, Mapping):
        if 'batch.videos_per_news_per_round' in profile.parameters:
            try:
                requested_angle_count = int(profile.parameters['batch.videos_per_news_per_round'])
            except Exception:
                pass
        if 'render.presets' in profile.parameters:
            presets = profile.parameters['render.presets']
            # PRS-LAYOUT-QUOTA (FR-PRS-003): with a layout per preset the model picks the layout and the plan takes its preset;
            # preset_revision_ref is then the preset of the default layout. Without it the first preset is kept as before.
            layout_presets = layout_presets_of(presets)
            if layout_presets is not None:
                preset_revision_ref = layout_presets[DEFAULT_LAYOUT]
            elif isinstance(presets, Mapping) and presets:
                preset_revision_ref = str(next(iter(presets.keys())))
            elif isinstance(presets, (list, tuple)) and presets:
                preset_revision_ref = str(presets[0])

    return CreativeSettings(
        language_policy=language_policy,
        target_range=target_range,
        requested_angle_count=requested_angle_count,
        variation_policy_revision=variation_policy_revision,
        preset_revision_ref=preset_revision_ref,
        layout_presets=layout_presets,
    )


class ProductionSelectionInputs:
    def __init__(self, *, media: Any, visual_hooks: Any, audio_hooks: Any, thumbnails: Any, profile: Any) -> None:
        self._media = media
        self._visual_hooks = visual_hooks
        self._audio_hooks = audio_hooks
        self._thumbnails = thumbnails
        self._profile = profile

    def selection_inputs(self, *, workspace_id: str, snapshot: Any, script: Any, angle: Any) -> Mapping[str, Any]:
        media_cands = self._media.media_candidates(workspace_id=workspace_id, snapshot=snapshot)
        snap_ref = getattr(snapshot, 'snapshot_id', str(snapshot))
        v_hooks = self._visual_hooks.visual_hook_candidates(workspace_id=workspace_id, snapshot_ref=snap_ref)
        a_hooks = self._audio_hooks.audio_hook_candidates(workspace_id=workspace_id, snapshot_ref=snap_ref)
        th_cands = self._thumbnails.thumbnail_candidates(visual_hooks=v_hooks, media_candidates=media_cands)

        rev = getattr(self._profile, 'revision', 1)
        safety_policy = SafetyRightsPolicy(
            revision=f'safe-r{rev}',
            allowed_availability=('AVAILABLE',),
            required_flags=('rights_cleared',),
            blocked_flags=('unsafe',),
        )
        weights = ScoringWeights(semantic=0.6, technical=0.4, recent_usage_penalty=0.1)

        return {
            'media_candidates': media_cands,
            'visual_hook_candidates': v_hooks,
            'audio_hook_candidates': a_hooks,
            'thumbnail_candidates': th_cands,
            'safety_policy': safety_policy,
            'music_sfx_policy_revision': f'music-r{rev}',
            'preset_registry_revision': f'preset-r{rev}',
            'weights': weights,
        }


class ProductionVariantContext:
    def __init__(self, *, manager: Any, profile: Any) -> None:
        self._manager = manager
        self._profile = profile

    def variant_context(
        self,
        *,
        workspace_id: str,
        job_id: str,
        phase: str,
        input_refs: Sequence[Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        with self._manager.borrow_connection() as conn:
            registry_revision = PostgresVariantRegistry(conn).current_revision(workspace_id)
            rows = conn.execute(
                'SELECT reservation_id, workspace_id::text, job_id, fingerprint, '
                'snapshot_scope, validation_ref, variation_policy_revision, '
                'committed_registry_revision, state '
                'FROM controlplane.cp_variant_reservations '
                'WHERE workspace_id = %s',
                (workspace_id,),
            ).fetchall()

        settings = creative_settings(self._profile)
        variation_policy_revision = settings.variation_policy_revision

        active_reservations = []
        completed = []
        same_run = []
        own_reservation_id = None

        for row in rows:
            res_id = str(row[0])
            r_job_id = str(row[2])
            fp = str(row[3])
            scope = str(row[4])
            v_ref = str(row[5])
            v_pol = str(row[6])
            com_rev = int(row[7])
            state = ReservationState(str(row[8]))

            rec = VariantReservation(
                reservation_id=res_id,
                workspace_id=workspace_id,
                job_id=r_job_id,
                fingerprint=fp,
                snapshot_scope=scope,
                validation_ref=v_ref,
                variation_policy_revision=v_pol,
                committed_registry_revision=com_rev,
                state=state,
            )
            if state is ReservationState.ACTIVE:
                active_reservations.append(rec)
            if r_job_id == job_id:
                own_reservation_id = res_id

        result = {
            'completed': tuple(completed),
            'active_reservations': tuple(active_reservations),
            'same_run': tuple(same_run),
            'registry_revision': registry_revision,
            'variation_policy_revision': variation_policy_revision,
        }

        if phase == 'output':
            if own_reservation_id is not None:
                result['own_reservation_id'] = own_reservation_id
            # output_hash là sha256 nội dung video mà render_video đã xác minh, mang trong ref render_output; không có thì bỏ trống để miền trả INPUT_NOT_READY.
            rendered = [
                ref['sha256']
                for ref in input_refs
                if ref.get('ref_type') == 'render_output' and isinstance(ref.get('sha256'), str) and ref['sha256']
            ]
            if rendered:
                result['output_hash'] = rendered[-1]

        return result


def creative_activity_deps(
    services: CreativeServices,
    *,
    manager: Any,
    workspace_id: str,
    profile: Any,
    runtime: Any,
    grants: Any,
    sources: Any,
    selection_inputs: Any,
    selections: Any,
    clock: Callable[[], datetime.datetime],
) -> CreativeActivityDeps:
    prompts = ConfigPromptSource(PostgresPromptScope(manager), workspace_id)
    articles = PostgresArticleContext(manager.borrow_connection)
    lazy_instructions = LazyInstructions(prompts)
    pipeline = CreativePipeline(
        uow_factory=services.uow_factory,
        route=services.route,
        ai=services.ai,
        instructions={},
        articles=articles,
        selections=selections,
        # D-15-FIX1: attempts of one command in one activity come from the production profile.
        failure_policy=ProviderFailurePolicy(max_attempts=profile.ai.retry.max_attempts),
    )
    pipeline._instructions = lazy_instructions
    inputs = ProductionActivityInputs(
        uow_factory=services.uow_factory,
        prompts=prompts,
        sources=sources,
        selection_inputs=selection_inputs,
        variant_context=ProductionVariantContext(manager=manager, profile=profile),
        selections=selections,
        settings=creative_settings(profile),
        clock=clock,
        layout_usage=PostgresLayoutUsage(manager),
    )
    return CreativeActivityDeps(
        pipeline=pipeline,
        grants=grants,
        inputs=inputs,
        clock=clock,
    )


def creative_activity_handlers(
    deps: CreativeActivityDeps,
    selections: Any,
    *,
    workspace_id: str,
) -> dict[str, Any]:
    base = creative_handler(deps, workspace_id=workspace_id)

    def handle_select(request: Mapping[str, Any], claims: Any) -> dict[str, Any]:
        result = base(request, claims)
        if result.get('disposition') == 'succeeded':
            stored = next(
                (dict(ref) for ref in result.get('output_refs', ()) if ref.get('ref_type') == REF_SELECTION),
                None,
            )
            if stored is not None:
                sel = selections.load(workspace_id=workspace_id, selection_id=stored['ref_id'])
                if sel is None:
                    raise ActivityInputError(INPUT_NOT_READY, 'selection_not_stored')
                return {**result, 'output_refs': [stored, *selected_media_refs(sel)]}
        return result

    return {
        'BuildProductionSnapshot': base,
        'AnalyzeContent': base,
        'GenerateStoryAngles': base,
        'GenerateScript': base,
        'SelectCreativeAssets': handle_select,
        'BuildProductionPlan': base,
        'ValidateVariant': base,
        'GenerateOutputMetadata': base,
    }


__all__ = [
    'CreativeServices',
    'RoutedProviderRoute',
    'build_creative_services',
    'monthly_window',
    'creative_activity_deps',
    'creative_activity_handlers',
    'creative_settings',
    'PostgresPromptScope',
    'LazyInstructions',
    'PostgresLayoutUsage',
    'layout_presets_of',
    'ProductionSelectionInputs',
    'ProductionVariantContext',
]
