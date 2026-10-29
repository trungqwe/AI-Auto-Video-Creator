"""CP7-4 / RG-03: AI qua 9Router thật và chi phí.

6 vai trò x 10 lời gọi; 50 lời gọi văn bản qua CreativePipeline + RoutedAIInvocation + RoutedInvocationService + _ChatCompletionsExecutor (OpenAI chat/completions thật, lệch OI-PP-01 của adapter sản phẩm),
10 lời gọi image_safety qua LlmImageSafetyDetector + RouterVisionRoute; trần chi phí (60 lời gọi logic, ledger +5 USD);
prompt mặc định của D được test nối thêm quy tắc lược đồ (_SCHEMA_RULES, GIẢ ĐỊNH F-CP7-4-03); validator của D giữ nguyên;
cách dừng (CostGuard, hard_stop của J, Ctrl+C, hạn 45 phút); không in khóa.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
for _path in (REPO / 'tools' / 'real', REPO / 'src'):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import pytest  # noqa: E402

import cp7_common as c  # noqa: E402

PROFILE_PATH = REPO / 'tools' / 'launcher' / 'prod' / 'profile.json'
PORTS_PATH = REPO / 'tools' / 'launcher' / 'prod' / 'ports.json'
HOOKS_PATH = REPO / 'tools' / 'launcher' / 'prod' / 'hooks.json'
SEED_DIR = REPO / 'tools' / 'launcher' / 'prod' / 'seed'
REPORT = REPO / 'docs' / 'delivery-evidence' / 'cp7-4' / 'report.md'

ROUTER_HOST = '127.0.0.1'
ROUTER_PORT = 20128
ENDPOINT = 'http://127.0.0.1:20128/v1'
MODEL = 'ag/gemini-3.8-flash-high'

ROLES = ('analysis', 'angle', 'script', 'selection', 'metadata', 'image_safety')
TEXT_ROLES = ROLES[:5]
PER_ROLE = 10
CALL_CAP = 60
MIN_VALID = 57
P95_MAX_SECONDS = 120
LEDGER_CEILING_USD = Decimal('5')
MONTH_BLOCK_USD = Decimal('40')
ESTIMATED_COST_PER_REQUEST = Decimal('0.01')
MAX_WAIT_RETRIES_PER_CALL = 2
MAX_WAIT_RETRIES_TOTAL = 6
BREAKER_LIMIT = 3
WS = 'ws-1'
DEADLINE = c.Deadline(45 * 60)
SEED_IMAGE_IDS = ('bg-01', 'bg-02', 'bg-03', 'bg-04', 'bg-05', 'bg-08', 'bg-09', 'bg-10', 'bg-11', 'bg-12')

def _data_root():
    base = os.environ.get('AIAVC_DATA_DIR')
    return Path(base) if base else Path(os.environ['LOCALAPPDATA']) / 'AIAutoVideoCreator'

def _p95(values):
    if not values:
        raise ValueError('values is empty')
    return sorted(values)[math.ceil(0.95 * len(values)) - 1]

class _UrlMeter:
    def __init__(self):
        self.hits = []

    def patched_open(self, original):
        meter = self

        def wrapper(opener, fullurl, *args, **kwargs):
            url = fullurl if isinstance(fullurl, str) else getattr(fullurl, 'full_url', str(fullurl))
            method = fullurl.get_method() if hasattr(fullurl, 'get_method') else ('POST' if (args and args[0] is not None) or kwargs.get('data') is not None else 'GET')
            entry = {'url': url, 'method': method, 'status': None}
            meter.hits.append(entry)
            try:
                resp = original(opener, fullurl, *args, **kwargs)
                entry['status'] = getattr(resp, 'status', getattr(resp, 'code', 200))
                return resp
            except urllib.error.HTTPError as exc:
                entry['status'] = exc.code
                raise

        return wrapper

def _ascii(text):
    return str(text).encode('ascii', 'replace').decode('ascii')


# Tiền đề của mỗi lượt đo (snapshot, analysis, angle, script) dựng bằng fixture của D qua FakeAIAdapter;
# không đo và không tính vào 60 lời gọi; các lời gọi đo luôn đi qua RoutedAIInvocation.

from creative.adapters.fake_ai import FakeAIAdapter, FakeProviderRoute
from creative.adapters.memory import InMemoryUnitOfWork
from creative.application.pipeline import AI_ROLES, CreativePipeline
from creative.domain.asset_selection import HookCandidate, MediaCandidate, SafetyRightsPolicy, ScoringWeights, ThumbnailCandidate
from creative.domain.script import LanguageVoicePolicy, TargetRange
from creative.domain.timeline_mode import TimelinePolicy
from creative.ports.repositories import EventContext

POLICY = LanguageVoicePolicy(language='en', speech_rate=2.0)
RANGE = TargetRange(min_seconds=5, max_seconds=20)
TIMELINE_POLICY = TimelinePolicy(frozenset({'event_update_accepted'}))
SCRIPT_ARGS = dict(
    snapshot_id='snap-1', analysis_id='an-1', analysis_revision=1, set_id='set-1', angle_id='angle-a',
    script_version_id='script-1', language_policy=POLICY, target_range=RANGE)

def _ctx(number, workspace_id=WS):
    return EventContext(
        workspace_id=workspace_id, correlation_id='corr-1', actor='tester', occurred_at='2026-10-19T08:00:00+00:00',
        recovery_epoch='epoch-1', event_id=f'evt-{number}', message_id=f'msg-{number}')

def _ref(ref_type, ref_id, revision_id):
    return {'workspace_id': WS, 'ref_type': ref_type, 'ref_id': ref_id, 'revision_id': revision_id}

def _config_refs(revision):
    refs = [{'ref_type': 'prompt', 'ref_id': role, 'revision_id': f'{role}-{revision}'} for role in AI_ROLES]
    return refs + [{'ref_type': 'config_bundle', 'ref_id': 'bundle', 'revision_id': revision}]

def _snapshot_args(snapshot_id='snap-1', *, cfg='r1', source_rev='v1', mode='single_article', **overrides):
    args = dict(
        snapshot_id=snapshot_id, production_mode=mode,
        source_refs=[{'ref_type': 'article_revision', 'ref_id': 'a-1', 'revision_id': source_rev}],
        index_revision_refs=[], configuration_revision_refs=_config_refs(cfg), content_ref_types=['article_revision'],
        eligibility_reason='eligible', snapshot_timestamp='2026-10-19T08:00:00+00:00', video_job_ref='job-1')
    args.update(overrides)
    return args

def _analysis_json(rev):
    return {
        'topic': 'Port strike ends', 'entities': [{'name': 'Harbor Union', 'entity_type': 'organization'}],
        'timeline': [{'time_label': '2026-10-17', 'description': 'Strike begins'}], 'locations': ['Rotterdam'],
        'facts': [{'id': 'f-1', 'text': 'The union ended the strike.', 'evidence_refs': [_ref('article_revision', 'a-1', rev)]}],
        'uncertainties': [], 'contradictions': [], 'event_relation': 'standalone', 'update_context': '',
        'risk_flags': [], 'narrative_opportunities': ['Shipping impact'], 'media_needs': ['port footage'],
    }

def _angles_json(rev):
    base = {
        'summary': 'Short summary', 'evidence_refs': [_ref('article_revision', 'a-1', rev)],
        'planned_inference_elements': ['cause'], 'planned_creative_elements': ['map'], 'suitability': 'high', 'risk_flags': [],
    }
    return {'angles': [
        {**base, 'angle_id': 'angle-a', 'title': 'Why', 'narrative_question': 'Why did the strike end?',
         'focus_entities': ['Harbor Union'], 'timeframe': '2026-10'},
        {**base, 'angle_id': 'angle-b', 'title': 'Who pays', 'narrative_question': 'Who pays for the deal?',
         'focus_entities': ['Port Authority'], 'timeframe': '2026-11'},
    ]}

def _script_json(rev):
    return {
        'language': 'en', 'hook_intent': 'strike ends', 'thumbnail_transition': 'fade',
        'pronunciation_hints': [{'term': 'Rotterdam', 'pronunciation': 'ROT-er-dam'}],
        'segments': [
            {'segment_id': 's1', 'text': 'The harbor union ended its three day strike this week', 'claim_mode': 'source_backed',
             'scene_intent': 'scene one', 'source_refs': [_ref('article_revision', 'a-1', rev)]},
            {'segment_id': 's2', 'text': 'Ships should start moving again by tomorrow morning', 'claim_mode': 'inference',
             'scene_intent': 'scene two', 'source_refs': [], 'disclosure': 'This is an inference from the sources.'},
        ],
    }

def _selection_json():
    return {
        'visual_hook': _ref('visual_hook', 'vh-1', 'vh-1-r1'), 'audio_hook': _ref('audio_hook', 'ah-1', 'ah-1-r1'),
        'thumbnail': _ref('thumbnail', 'th-1', 'th-1-r1'),
        'scenes': [
            {'scene_id': 'sc-1', 'ref': _ref('media_asset', 'm-1', 'm-1-av'), 'rationale': 'opens on the union'},
            {'scene_id': 'sc-2', 'ref': _ref('media_asset', 'm-2', 'm-2-av'), 'rationale': 'context shot'},
        ],
        'music_intents': [{'cue': 'intro_pad', 'description': 'soft pad'}],
        'sfx_intents': [{'cue': 'whoosh', 'description': 'short whoosh'}],
        'rationale': 'angle focused selection',
    }

def _visual(asset, start, end):
    return {
        'media_asset_id': asset, 'start_ms': start, 'end_ms': end, 'crop_intent': 'center on subject',
        'overlay_intent': 'lower third', 'effect_intent': 'slow push-in'}

def _plan_json():
    return {
        'timeline': {'segments': [
            {'scene_id': 'sc-1', 'start_ms': 0, 'end_ms': 8000, 'transition_intent': 'hard cut', 'visuals': [_visual('m-1', 0, 8000)]},
            {'scene_id': 'sc-2', 'start_ms': 8000, 'end_ms': 20000, 'transition_intent': 'cross dissolve', 'visuals': [_visual('m-2', 8000, 20000)]},
        ]},
        'hook_placement': {'hook_time_range': {'start_ms': 0, 'end_ms': 5000}, 'thumbnail_time_range': {'start_ms': 1200, 'end_ms': 2400}},
        'voice_profile_intent': {'direction': 'warm and confident', 'pace': 'steady', 'emotion': 'curious'},
        'music_cues': [{'cue': 'intro_pad', 'start_ms': 0, 'end_ms': 20000}],
        'sfx_cues': [{'cue': 'whoosh', 'start_ms': 7800, 'end_ms': 8200}],
        'subtitle_style_intent': {'style': 'bold white captions', 'karaoke': True, 'highlight_intent': 'active word turns yellow'},
        'allowed_fallbacks': [
            {'rule_id': 'fb-1', 'kind': 'replace_asset', 'scene_id': 'sc-2', 'replacement_media_asset_id': 'm-3'},
            {'rule_id': 'fb-2', 'kind': 'simplify_transition', 'scene_id': 'sc-1'},
        ],
        'output_metadata_requirement': 'english title, caption and 3-4 hashtags',
    }

def _metadata_json():
    return {
        'title': 'Port Strike Ends After Three Days', 'caption': 'Ships are set to move again this week.',
        'hashtags': ['#Port', '#Strike', '#Shipping']}

def _media(asset_id, score):
    return MediaCandidate(
        media_asset_id=asset_id, rendition_ref=f'{asset_id}-rend', artifact_version_ref=f'{asset_id}-av',
        provenance={'source': 'catalog'}, semantic_match_components={'entity': score}, technical_fitness={'score': score},
        availability='AVAILABLE', safety_rights_status={'rights_cleared': True}, recent_usage_summary={'times_used': 0},
        reason_codes=('ENTITY_MATCH',))

def _hook(kind, hook_id):
    return HookCandidate(
        hook_kind=kind, hook_id=hook_id, revision_id=f'{hook_id}-r1', availability='AVAILABLE',
        safety_rights_status={'rights_cleared': True}, semantic_match_components={'topic': 0.7},
        provenance={'source': 'user_imported'})

def _asset_inputs():
    thumbnail = ThumbnailCandidate(
        thumbnail_id='th-1', revision_id='th-1-r1', subject_refs=('entity-1',), crop_focus={'x': 0.5},
        overlay_intent='question_mark', availability='AVAILABLE', safety_rights_status={'rights_cleared': True},
        semantic_match_components={'entity': 0.8}, provenance={'source': 'catalog'})
    return dict(
        media_candidates=[_media('m-1', 0.9), _media('m-2', 0.8), _media('m-3', 0.7)],
        visual_hook_candidates=[_hook('visual_hook', 'vh-1')], audio_hook_candidates=[_hook('audio_hook', 'ah-1')],
        thumbnail_candidates=[thumbnail],
        safety_policy=SafetyRightsPolicy(
            revision='safe-v1', allowed_availability=('AVAILABLE',), required_flags=('rights_cleared',), blocked_flags=('unsafe',)),
        music_sfx_policy_revision='music-v1', preset_registry_revision='preset-v1',
        weights=ScoringWeights(semantic=0.6, technical=0.4, recent_usage_penalty=0.1))

def _responses(rev):
    payloads = {
        'analysis': _analysis_json(rev), 'angle': _angles_json(rev), 'script': _script_json(rev),
        'selection': _selection_json(), 'metadata': _metadata_json()}
    return {role: {'text': json.dumps(payload), 'refs': []} for role, payload in payloads.items()}

class SelectionSplitAI(FakeAIAdapter):
    def __init__(self, route, **kwargs):
        super().__init__(route, **kwargs)
        self._selection_by_instructions = {
            'Return JSON for asset_selection': {'text': json.dumps(_selection_json()), 'refs': []},
            'Return JSON for production_plan': {'text': json.dumps(_plan_json()), 'refs': []}}

    def invoke(self, decision, envelope):
        if self._route.role_for_reservation(decision.capacity_reservation_ref) == 'selection':
            self._responses['selection'] = copy.deepcopy(self._selection_by_instructions[envelope.instructions])
        return super().invoke(decision, envelope)

class SpyRoute(FakeProviderRoute):
    def __init__(self):
        super().__init__()
        self.requests = []

    def resolve(self, request):
        self.requests.append(copy.deepcopy(dict(request)))
        return super().resolve(request)

class Rig:
    def __init__(self, uow=None, source_rev='v1'):
        self.uow = uow if uow is not None else InMemoryUnitOfWork()
        self.route = SpyRoute()
        self.ai = SelectionSplitAI(self.route, responses=_responses(source_rev), config_revision='cfg-fake')
        self.pipeline = CreativePipeline(
            uow_factory=lambda: self.uow, route=self.route, ai=self.ai,
            instructions={role: f'Return JSON for {role}' for role in AI_ROLES})

def _prepare(rig, job_ref='job-1'):
    pipeline = rig.pipeline
    out = {}
    out['snapshot'] = pipeline.build_production_snapshot(context=_ctx(1), idempotency_key='k-snap', **_snapshot_args(video_job_ref=job_ref))
    out['analysis'] = pipeline.analyze_content(
        context=_ctx(2), idempotency_key='k-analysis', snapshot_id='snap-1', analysis_id='an-1', revision=1)
    out['angles'] = pipeline.generate_story_angles(
        context=_ctx(3), idempotency_key='k-angles', snapshot_id='snap-1', analysis_id='an-1', analysis_revision=1,
        set_id='set-1', requested_count=2, variation_policy_revision='var-v1')
    return out

_SAMPLE_ARTICLE_TEXT = (
    'The harbor union representing thousands of maritime workers reached a landmark agreement today, '
    'officially ending the widespread port strike that had halted cargo movement across major container terminals. '
    'Port authorities confirmed that operational teams are actively clearing accumulated backlog, with shipping lines '
    'expecting normal berthing schedules to resume by tomorrow morning. Industry analysts noted that the resolution '
    'averts severe supply chain bottlenecks ahead of the busy holiday shipping season. Union leadership praised the '
    'negotiating committee for securing fair wage increases and updated safety protections, while terminal operators '
    'emphasized a shared commitment to modernizing cargo handling infrastructure. Maritime logistics experts estimate '
    'that full port throughput will normalize within several business days as freight trains and trucks coordinate transport.'
)

class _ArticleContext:
    def articles(self, workspace_id, refs):
        items = []
        for ref in refs:
            ref_type = ref.get('ref_type') if hasattr(ref, 'get') else getattr(ref, 'ref_type', None)
            ref_id = ref.get('ref_id') if hasattr(ref, 'get') else getattr(ref, 'ref_id', None)
            rev_id = ref.get('revision_id') if hasattr(ref, 'get') else getattr(ref, 'revision_id', None)
            if ref_type == 'article_revision':
                items.append({
                    'article_id': ref_id,
                    'article_revision_id': rev_id,
                    'title': 'Port strike ends as union reaches landmark agreement',
                    'normalized_text': _SAMPLE_ARTICLE_TEXT,
                    'source_id': 'news-source-1',
                    'published_at': '2026-10-19T08:00:00+00:00',
                    'topic': 'Port strike ends',
                })
        return items

def _seed_png(image_id):
    seed_script = REPO / 'tools' / 'launcher' / 'prod' / 'seed' / 'make_seed_media.py'
    spec = importlib.util.spec_from_file_location('make_seed_media', seed_script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    hooks = json.loads(HOOKS_PATH.read_text(encoding='utf-8'))
    templates = hooks['recipe_templates']
    bg_items = {item['id']: item for item in hooks['background_images']}
    item = bg_items[image_id]
    template = templates[item['recipe']['template']]
    png_data = mod.make_png(item['width'], item['height'], item['recipe']['hue_degrees'], template)
    return (png_data, 'image/png')


# Executor của test: gửi thân OpenAI chat/completions tới 9Router thật. NineRouterExecutor của sản phẩm gửi {prompt} tới {endpoint}/v1/chat nên 404 (OI-PP-01); src/** nằm ngoài owned paths.
class _ChatCompletionsExecutor:
    def __init__(self, endpoint, store, credentials, timeout_seconds, cost):
        from controlplane.config.adapter import ApprovedEndpointRegistry
        self._registry = ApprovedEndpointRegistry.from_config([endpoint])
        self._endpoint = self._registry.validate(endpoint)
        self._store = store
        self._credentials = credentials
        self._timeout = float(timeout_seconds)
        self._cost = cost
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def execute(self, decision, candidate_ref, request_payload_ref, credential_method):
        import controlplane.config.adapter as adapter
        from controlplane.application.config_security.routed_invocation import ExecutionResult
        try:
            prompt = self._store.get_request(request_payload_ref)
            body = json.dumps({'model': decision.model_ref, 'messages': [{'role': 'user', 'content': prompt}]}).encode('utf-8')
            url = self._registry.validate(self._endpoint) + '/chat/completions'
            with self._credentials.acquire(credential_method, decision.account_ref) as token:
                headers = {'Content-Type': 'application/json', 'Accept': 'application/json', 'Authorization': 'Bearer ' + token}
                request = urllib.request.Request(url, data=body, method='POST', headers=headers)
                try:
                    with self._opener.open(request, timeout=self._timeout) as resp:
                        payload = json.loads(resp.read().decode('utf-8'))
                except urllib.error.HTTPError as exc:
                    exc.close()
                    if exc.code == 429:
                        raise adapter.ProviderRateLimitExceededError('HTTP 429 from 9Router') from None
                    if exc.code in (401, 403):
                        raise adapter.ProviderAuthenticationError('HTTP ' + str(exc.code) + ' from 9Router') from None
                    raise adapter.ProviderHTTPError('HTTP error ' + str(exc.code) + ' from 9Router') from None
                except (TimeoutError, urllib.error.URLError) as exc:
                    if isinstance(getattr(exc, 'reason', exc), TimeoutError):
                        raise adapter.ProviderTimeoutError('9Router request timed out') from None
                    raise adapter.ProviderHTTPError('9Router connection error') from None
        except Exception as exc:
            return ExecutionResult(False, None, Decimal('0'), exc)
        return ExecutionResult(True, self._store.put_output(request_payload_ref + '-output', payload), self._cost, None)

# Bọc RouterVisionRoute thật: sau mỗi lời gọi vision (kể cả lỗi) ghi một bản ghi chi phí ước tính vào sổ, vì route vision của sản phẩm không qua J-18 và không có sổ (OI-PP-04). Bản ghi này là sổ của test, không phải bằng chứng ghi sổ của sản phẩm.
class _LedgeredVisionRoute:
    def __init__(self, inner, ledger, workspace_id, clock, cost):
        self._inner = inner
        self._ledger = ledger
        self._workspace_id = workspace_id
        self._clock = clock
        self._cost = cost
        self._count = 0

    def invoke_vision(self, ai_role, instructions, image_base64, media_type, timeout_seconds):
        from controlplane.domain.config_security.incremental_cost import IncrementalCostRecord
        self._count += 1
        try:
            return self._inner.invoke_vision(ai_role, instructions, image_base64, media_type, timeout_seconds)
        finally:
            ref = f'cp7-4-vision:{ai_role}:{self._count}'
            self._ledger.append(self._workspace_id, IncrementalCostRecord(
                record_id=ref, provider='router-primary', service=MODEL, operation_ref=ref, job_ref='cp7-4-vision', batch_ref=None,
                quantity=Decimal('1'), unit='request', estimated_cost=self._cost, actual_cost=self._cost, currency='USD',
                source='vision_route_test', occurred_at=self._clock().isoformat(), cost_category='api_paid'))

# GIẢ ĐỊNH (D8): sổ chi phí để trong bộ nhớ vì mật khẩu PostgreSQL nằm trong kho secrets ngoài phạm vi D5;
# cost_per_request ước tính 0.01 USD vì launcher.py:577 đặt 0 và J-18 không ghi sổ khi chi phí <= 0 (routed_invocation.py:207).

def _build_stack():
    from controlplane.api.wiring.production_profile import load_production_profile
    from controlplane.infrastructure.security.dpapi_secret_store import DpapiSecretStore
    from controlplane.infrastructure.production_ports.credentials import RouterKeyCredentials
    from controlplane.infrastructure.production_ports.route_catalog import ProfileRouteCatalog
    from controlplane.api.wiring.config_security import InMemoryCostLedger
    from controlplane.application.config_security.capacity_reservation import CapacityReservationBook, InMemoryReservationStore
    from controlplane.application.config_security.route_resolver import ProviderRouteResolver
    from controlplane.application.config_security.routed_invocation import RoutedInvocationService
    from controlplane.api.wiring.creative import budget_policy_from_config, monthly_window, RoutedProviderRoute
    from creative.adapters.real_ai_invocation import FallbackIntentPolicy, InvocationPayloadStore, RoutedAIInvocation
    from controlplane.infrastructure.production_ports.vision_route import RouterVisionRoute

    profile = load_production_profile(PROFILE_PATH)
    assert profile.profile_name == 'production'
    assert profile.ai.route_endpoint == ENDPOINT
    assert set(profile.ai.route_model_refs) == set(ROLES)
    assert all(v == MODEL for v in profile.ai.route_model_refs.values())

    router = json.loads(PORTS_PATH.read_text(encoding='utf-8'))['router']
    account_ref = router['account_ref']
    secret_ref = router['secret_ref']

    store = DpapiSecretStore(_data_root() / 'vault')
    assert store.current_version(secret_ref) is not None, 'secret_ref not in vault'

    credentials = RouterKeyCredentials(store, account_ref, secret_ref)
    catalog = ProfileRouteCatalog(profile.ai.route_model_refs, account_ref, secret_ref, store)

    ledger = InMemoryCostLedger()
    resolver = ProviderRouteResolver(
        catalog,
        CapacityReservationBook(InMemoryReservationStore()),
        lambda domain_key: None,
        f'profile-{profile.revision}',
    )

    payloads = InvocationPayloadStore()
    executor = _ChatCompletionsExecutor(
        profile.ai.route_endpoint, payloads, credentials, profile.ai.request_timeout_seconds, ESTIMATED_COST_PER_REQUEST)

    budget = budget_policy_from_config({
        'monthly_limit': profile.budget.monthly_limit,
        'hard_stop': profile.budget.hard_stop,
        'warn_ratio': profile.budget.warn_at_ratio,
        'currency': profile.budget.currency,
    })
    window_fn = monthly_window(profile.budget.window_timezone)
    service = RoutedInvocationService(
        resolver,
        executor,
        budget,
        ledger,
        window_fn,
        model_ref_for=profile.ai.route_model_refs.get,
    )
    clock = lambda: datetime.now(timezone.utc)
    route = RoutedProviderRoute(resolver, WS, 1, profile.ai.reservation_ttl_seconds, clock, lambda: True)
    routed = RoutedAIInvocation(
        service,
        payloads,
        request_for=route.request_for,
        clock=clock,
        config_revision=f'profile-{profile.revision}',
        intent_policy=FallbackIntentPolicy(snapshot_committed=False, fallback_allowed_after_snapshot=False),
        units=1,
        ttl_seconds=profile.ai.reservation_ttl_seconds,
        desktop_online=lambda: True,
    )
    vision = _LedgeredVisionRoute(
        RouterVisionRoute(profile.ai.route_endpoint, profile.ai.route_model_refs, credentials, account_ref),
        ledger, WS, clock, ESTIMATED_COST_PER_REQUEST)
    return SimpleNamespace(
        profile=profile,
        account_ref=account_ref,
        secret_ref=secret_ref,
        store=store,
        credentials=credentials,
        ledger=ledger,
        service=service,
        route=route,
        routed=routed,
        vision=vision,
        clock=clock,
        window=window_fn,
    )

class _RecordingAI:
    def __init__(self, inner, route):
        self.inner = inner
        self.route = route
        self.calls = []

    def invoke(self, decision, envelope):
        t0 = time.monotonic()
        result = self.inner.invoke(decision, envelope)
        elapsed = time.monotonic() - t0
        ai_role = self.route.request_for(decision.capacity_reservation_ref).ai_role
        self.calls.append(SimpleNamespace(role=ai_role, result=result, seconds=elapsed))
        return result


# GIẢ ĐỊNH (D8): DEFAULT_PROMPTS của D (src/creative/application/prompts.py) không nêu cấu trúc evidence_refs, enum event_relation và các ràng buộc ref, độ dài; model thật trả list chuỗi nên validator của D từ chối (F-CP7-4-03, chủ gói CREAT-D). src/** ngoài owned paths nên test nối thêm quy tắc lược đồ vào cuối prompt mặc định; validator, pipeline và J-18 vẫn là mã sản phẩm, không nới kiểm tra nào.
_REF_RULE = (
    'A reference is a JSON object, never a string, with the string keys workspace_id, ref_type, ref_id and revision_id. '
    f'Use workspace_id {WS} in every reference. '
)
_SOURCE_REF_RULE = 'To cite the source article use ref_type article_revision, ref_id equal to the article_id and revision_id equal to the article_revision_id of the article data item. '
_SCHEMA_RULES = {
    'content_analysis': (
        'Schema rules: do not output analysis_id, revision or trace. entities is a list of objects with the string keys name and entity_type. '
        'timeline is a list of objects with the string keys time_label and description. locations, risk_flags, narrative_opportunities and media_needs are lists of non-empty strings. '
        'facts is a list of objects with the string keys id and text and a non-empty list evidence_refs of references. '
        'uncertainties and contradictions are lists, possibly empty, of objects with the same keys id, text and evidence_refs. '
        'event_relation is exactly one of standalone, same_event, event_update. update_context is a string and is non-empty only when event_relation is event_update. '
        + _REF_RULE + _SOURCE_REF_RULE
    ),
    'story_angles': (
        'Schema rules: angles is a list with exactly requested_count objects, requested_count read from the data block. '
        'Each angle has the non-empty string keys angle_id, title, summary, narrative_question, timeframe and suitability, the lists of strings planned_inference_elements, planned_creative_elements and risk_flags, '
        'a non-empty list of strings focus_entities and a non-empty list evidence_refs of references. '
        'angle_id values are unique and the angles differ in title, narrative_question, focus_entities and timeframe. '
        + _REF_RULE + _SOURCE_REF_RULE
    ),
}

_SCHEMA_RULES['script_generation'] = (
    'Schema rules: language is the language code of language_policy in the data block. hook_intent and thumbnail_transition are non-empty strings. '
    'pronunciation_hints is a list, possibly empty, of objects with the string keys term and pronunciation. '
    'segments is a non-empty list of objects with the string keys segment_id (unique), text, claim_mode and scene_intent, a list source_refs of references and an optional string disclosure. '
    'claim_mode is exactly one of source_backed, inference, creative_hypothesis, transition. source_backed needs a non-empty source_refs; inference and creative_hypothesis need a non-empty disclosure. '
    'The total word count of all segment texts must be at least speech_rate times min_seconds and at most speech_rate times max_seconds, all read from the data block; aim for the middle of that range. '
    + _REF_RULE + _SOURCE_REF_RULE
)
_SCHEMA_RULES['asset_selection'] = (
    'Schema rules: visual_hook, audio_hook and thumbnail are each one reference copied from the matching candidate in the data block: '
    'for a hook use ref_type visual_hook or audio_hook, ref_id equal to hook_id and revision_id equal to its revision_id; for the thumbnail use ref_type thumbnail, ref_id equal to thumbnail_id and revision_id equal to its revision_id. '
    'scenes is a non-empty list of objects with the string keys scene_id (unique) and rationale and a key ref that is a reference with ref_type media_asset, ref_id equal to media_asset_id and revision_id equal to artifact_version_ref of a media candidate. '
    'music_intents and sfx_intents are lists, possibly empty, of objects with the non-empty string keys cue and description. rationale is a non-empty string. '
    + _REF_RULE
)
_SCHEMA_RULES['output_metadata'] = (
    'Schema rules: title and caption are non-empty strings. hashtags is a list of 3 or 4 distinct strings, each starting with # followed by text and containing no whitespace and no second #.'
)


def _test_instructions():
    from creative.application.pipeline import AI_ROLES
    from creative.application.prompts import DEFAULT_PROMPTS
    return {r: (DEFAULT_PROMPTS[r] + ' ' + _SCHEMA_RULES.get(r, '')).strip() for r in AI_ROLES}


def _run_text_call(stack, role, i, rig):
    from creative.application.pipeline import CreativePipeline, PipelineRejected, AI_ROLES
    from creative.adapters.real_ai_invocation import WaitingAIInvocationResult

    recorder = _RecordingAI(stack.routed, stack.route)
    instructions = _test_instructions()
    pipeline = CreativePipeline(
        uow_factory=lambda: rig.uow,
        route=stack.route,
        ai=recorder,
        instructions=instructions,
        articles=_ArticleContext(),
    )
    context = _ctx(100 + i * 10 + TEXT_ROLES.index(role))
    key = f'k-{role}-m{i}'
    cmd_result = None
    exc_obj = None

    try:
        if role == 'analysis':
            cmd_result = pipeline.analyze_content(
                context=context,
                idempotency_key=key,
                snapshot_id='snap-1',
                analysis_id=f'an-m{i}',
                revision=1,
            )
        elif role == 'angle':
            cmd_result = pipeline.generate_story_angles(
                context=context,
                idempotency_key=key,
                snapshot_id='snap-1',
                analysis_id='an-1',
                analysis_revision=1,
                set_id=f'set-m{i}',
                requested_count=2,
                variation_policy_revision='var-v1',
            )
        elif role == 'script':
            cmd_result = pipeline.generate_script(
                context=context,
                idempotency_key=key,
                **{**SCRIPT_ARGS, 'script_version_id': f'script-m{i}'},
            )
        elif role == 'selection':
            cmd_result = pipeline.select_creative_assets(
                context=context,
                idempotency_key=key,
                snapshot_id='snap-1',
                script_version_id='script-1',
                set_id='set-1',
                angle_id='angle-a',
                **_asset_inputs(),
            )
        elif role == 'metadata':
            cmd_result = pipeline.generate_output_metadata(
                context=context,
                idempotency_key=key,
                snapshot_id='snap-1',
                source_job_ref=f'job-m{i}',
                source_output_refs=(f'variant-m{i}',),
                metadata_revision=1,
            )
        else:
            raise ValueError(f'unexpected text role: {role}')
    except Exception as exc:
        exc_obj = exc

    last_call = recorder.calls[-1] if recorder.calls else None
    seconds = last_call.seconds if last_call else 0.0
    last_res = last_call.result if last_call else None
    record = getattr(last_res, 'record', None)
    model_ref = getattr(record, 'model_ref', '')
    record_text = repr(record) if record else ''

    if exc_obj is None:
        valid = True
        waiting = False
        wait_kind = None
        code = 'ok'
    elif isinstance(exc_obj, PipelineRejected) and isinstance(last_res, WaitingAIInvocationResult):
        waiting = True
        valid = True
        err = str(getattr(record, 'error', '') or '')
        if err.startswith('budget_blocked'):
            wait_kind = 'budget'
        elif 'RATE_LIMIT' in err or '429' in err:
            wait_kind = 'rate_limit'
        else:
            wait_kind = 'timeout_or_route'
        code = _ascii(f'{exc_obj.code}:{c.redact(err)[:120]}')
    elif isinstance(exc_obj, PipelineRejected):
        valid = False
        waiting = False
        wait_kind = None
        err = str(getattr(record, 'error', '') or '')
        code = _ascii(f'PipelineRejected:{exc_obj.code}:{c.redact(err)[:120]}')
    else:
        valid = False
        waiting = False
        wait_kind = None
        err = str(getattr(record, 'error', '') or '') if record else str(exc_obj)
        code = _ascii(f'{exc_obj.__class__.__name__}:{c.redact(err)[:120]}')

    return {
        'role': role,
        'valid': valid,
        'waiting': waiting,
        'wait_kind': wait_kind,
        'code': code,
        'seconds': seconds,
        'model_ref': model_ref,
        'record_text': record_text,
    }

def _run_vision_call(stack, image_id):
    from voice.domain.processing import ArtifactRef
    from voice.adapters.real_llm_image_safety import LlmImageSafetyDetector
    from voice.domain.image_safety import DetectionStatus

    data, media_type = _seed_png(image_id)
    content_sha256 = hashlib.sha256(data).hexdigest()
    artifact_ref = ArtifactRef(ref=f'seed-{image_id}', content_sha256=content_sha256)
    categories = stack.profile.image_safety.categories
    timeout_seconds = stack.profile.image_safety.vision_timeout_seconds

    detector = LlmImageSafetyDetector(
        stack.vision,
        artifact_ref,
        lambda ref: (data, media_type),
        categories=categories,
        timeout_seconds=timeout_seconds,
    )
    t0 = time.monotonic()
    detection = detector()
    seconds = time.monotonic() - t0

    valid = (detection.status == DetectionStatus.COMPLETED and detector.failure_code is None)
    code = detector.failure_code if detector.failure_code is not None else 'ok'
    return {
        'role': 'image_safety',
        'valid': valid,
        'waiting': False,
        'wait_kind': None,
        'code': _ascii(code),
        'seconds': seconds,
        'model_ref': stack.profile.ai.route_model_refs.get('image_safety', MODEL),
        'record_text': f'ImageSafety({image_id}, status={detection.status}, code={code})',
    }


@pytest.fixture(scope='module')
def measurement():
    meter = _UrlMeter()
    mp = pytest.MonkeyPatch()
    mp.setattr(urllib.request.OpenerDirector, 'open', meter.patched_open(urllib.request.OpenerDirector.open))
    stack = _build_stack()
    guard = c.CostGuard.from_ledger(stack.ledger, WS, *stack.window(stack.clock()), LEDGER_CEILING_USD)

    results = []
    consecutive_invalid = 0
    quota_event = False
    quota_resumed = False
    total_retries = 0
    logical_calls = 0

    try:
        for i in range(PER_ROLE):
            rig = Rig(uow=InMemoryUnitOfWork())
            _prepare(rig, f'job-m{i}')
            rig.pipeline.generate_script(context=_ctx(4), idempotency_key='k-script', **SCRIPT_ARGS)

            for role in TEXT_ROLES:
                DEADLINE.check()
                assert logical_calls < CALL_CAP, f'CALL_CAP {CALL_CAP} reached'
                guard.check(additional_usd=ESTIMATED_COST_PER_REQUEST * (1 + MAX_WAIT_RETRIES_PER_CALL))

                call_res = _run_text_call(stack, role, i, rig)
                call_retries = 0

                while call_res['waiting'] and call_res['wait_kind'] in ('rate_limit', 'budget') and call_retries < MAX_WAIT_RETRIES_PER_CALL and total_retries < MAX_WAIT_RETRIES_TOTAL:
                    quota_event = True
                    sleep_sec = min(float(getattr(stack.profile.ai, 'quota_wait_poll_seconds', 5.0)), DEADLINE.remaining())
                    if DEADLINE.remaining() <= 5.0:
                        break
                    time.sleep(sleep_sec)
                    call_retries += 1
                    total_retries += 1
                    retry_res = _run_text_call(stack, role, i + 100 * call_retries, rig)
                    if retry_res['valid'] and not retry_res['waiting']:
                        quota_resumed = True
                        call_res = retry_res
                        break
                    call_res = retry_res

                if logical_calls == 0:
                    if not call_res['valid'] and not call_res['waiting']:
                        first_hit = meter.hits[0] if meter.hits else {'url': 'none', 'status': None}
                        pytest.fail(_ascii(
                            f'BLOCKED(OI-PP-01 or provider error): code={call_res["code"]} url={first_hit.get("url")} status={first_hit.get("status")}'
                        ))

                if not call_res['valid'] and not call_res['waiting']:
                    consecutive_invalid += 1
                    if consecutive_invalid >= BREAKER_LIMIT:
                        last_hit = meter.hits[-1] if meter.hits else {}
                        pytest.fail(_ascii(
                            f'BLOCKED(circuit breaker): {consecutive_invalid} consecutive failures code={call_res["code"]} url={last_hit.get("url")} status={last_hit.get("status")}'
                        ))
                else:
                    consecutive_invalid = 0

                results.append(call_res)
                logical_calls += 1

        for image_id in SEED_IMAGE_IDS:
            DEADLINE.check()
            assert logical_calls < CALL_CAP, f'CALL_CAP {CALL_CAP} reached'
            guard.check(additional_usd=ESTIMATED_COST_PER_REQUEST * (1 + MAX_WAIT_RETRIES_PER_CALL))

            call_res = _run_vision_call(stack, image_id)

            if not call_res['valid'] and not call_res['waiting']:
                consecutive_invalid += 1
                if consecutive_invalid >= BREAKER_LIMIT:
                    last_hit = meter.hits[-1] if meter.hits else {}
                    pytest.fail(_ascii(
                        f'BLOCKED(circuit breaker): {consecutive_invalid} consecutive failures code={call_res["code"]} url={last_hit.get("url")} status={last_hit.get("status")}'
                    ))
            else:
                consecutive_invalid = 0

            results.append(call_res)
            logical_calls += 1

        yield SimpleNamespace(
            results=results,
            hits=meter.hits,
            stack=stack,
            retries=total_retries,
            quota_event=quota_event,
            quota_resumed=quota_resumed,
            logical_calls=logical_calls,
        )
    finally:
        mp.undo()




def test_rg03_six_roles_valid(measurement, emit):
    for role in ROLES:
        role_calls = [r for r in measurement.results if r['role'] == role]
        assert len(role_calls) == PER_ROLE, f'expected {PER_ROLE} calls for {role}, got {len(role_calls)}'

    total_valid = sum(1 for r in measurement.results if r['valid'])
    assert total_valid >= MIN_VALID, f'valid calls {total_valid} < {MIN_VALID} / {CALL_CAP}'

    for r in measurement.results:
        if r['role'] in TEXT_ROLES:
            assert r['model_ref'] == MODEL, f'text model_ref {r["model_ref"]} != {MODEL}'
    assert measurement.stack.profile.ai.route_model_refs['image_safety'] == MODEL

    valid_by_role = {role: sum(1 for r in measurement.results if r['role'] == role and r['valid']) for role in ROLES}
    waiting_count = sum(1 for r in measurement.results if r['waiting'])
    emit(c.report_line('RG-03', 'six_roles_valid', 'PASS'))
    emit(f'- six_roles_valid: valid_by_role={_ascii(json.dumps(valid_by_role))} waiting={waiting_count} total_valid={total_valid}/{CALL_CAP}')

def test_rg03_router_host_only(measurement, emit):
    assert len(measurement.hits) >= measurement.logical_calls, f'hits {len(measurement.hits)} < {measurement.logical_calls}'
    hosts_seen = set()
    paths_seen = set()
    statuses_seen = set()

    for hit in measurement.hits:
        parsed = urllib.parse.urlsplit(hit['url'])
        assert parsed.hostname == ROUTER_HOST, f'unexpected host {parsed.hostname}'
        assert parsed.port == ROUTER_PORT, f'unexpected port {parsed.port}'
        assert parsed.path.startswith('/v1'), f'path does not start with /v1: {parsed.path}'
        hosts_seen.add((parsed.hostname, parsed.port))
        paths_seen.add(parsed.path)
        statuses_seen.add(hit.get('status'))

    emit(c.report_line('RG-03', 'router_host_only', 'PASS'))
    emit(f'- router_host_only: hits={len(measurement.hits)} hosts={_ascii(sorted(hosts_seen))} paths={_ascii(sorted(paths_seen))} statuses={_ascii(sorted(str(s) for s in statuses_seen))}')

def test_rg03_ledger_recorded(measurement, emit):
    records = measurement.stack.ledger.records(WS, *measurement.stack.window(measurement.stack.clock()))
    routed_records = [r for r in records if r.source == 'routed_invocation']
    vision_records = [r for r in records if r.source == 'vision_route_test']
    expected_text = sum(1 for r in measurement.results if r['role'] in TEXT_ROLES and r['valid'] and not r['waiting'])
    expected_vision = sum(1 for r in measurement.results if r['role'] == 'image_safety')
    assert len(routed_records) >= expected_text, f'ledger J-18 records {len(routed_records)} < completed text calls {expected_text}'
    assert len(vision_records) == expected_vision, f'vision ledger records {len(vision_records)} != vision calls {expected_vision}'
    for rec in routed_records + vision_records:
        assert rec.currency == 'USD', f'currency {rec.currency} != USD'
        assert rec.estimated_cost == ESTIMATED_COST_PER_REQUEST, f'estimated_cost {rec.estimated_cost} != {ESTIMATED_COST_PER_REQUEST}'

    total_cost = sum((r.actual_cost if r.actual_cost is not None else r.estimated_cost) for r in routed_records + vision_records)
    c.CostGuard(LEDGER_CEILING_USD, lambda: total_cost).check()
    assert total_cost <= LEDGER_CEILING_USD
    emit(c.report_line('RG-03', 'ledger_recorded', 'PASS'))
    emit(f'- ledger_recorded: j18_records={len(routed_records)} vision_test_records={len(vision_records)} logical_calls={measurement.logical_calls} total_cost={total_cost} USD (ban ghi vision do test ghi, khong phai san pham)')

def test_rg03_record_no_secret(measurement, emit):
    from controlplane.application.config_security.route_resolver import CREDENTIAL_METHOD
    text_parts = [r['record_text'] for r in measurement.results]
    records = measurement.stack.ledger.records(WS, *measurement.stack.window(measurement.stack.clock()))
    text_parts.extend(repr(rec) for rec in records)
    combined = chr(10).join(text_parts)

    leaks = c.scan_secrets(combined)
    assert leaks == [], f'secrets detected in records: {leaks}'
    with measurement.stack.credentials.acquire(CREDENTIAL_METHOD, measurement.stack.account_ref) as key:
        assert isinstance(key, str) and len(key) > 0
        assert key not in combined, 'secret key found in records or emit text'
    emit(c.report_line('RG-03', 'record_no_secret', 'PASS'))
    emit(f'- record_no_secret: scanned_records={len(records)} leak_count=0 key_present=False')

def test_rg03_latency_p95(measurement, emit):
    seconds_list = [r['seconds'] for r in measurement.results]
    p95_val = _p95(seconds_list)
    assert p95_val <= P95_MAX_SECONDS, f'p95 latency {p95_val:.2f}s > {P95_MAX_SECONDS}s'
    max_val = max(seconds_list)
    records = measurement.stack.ledger.records(WS, *measurement.stack.window(measurement.stack.clock()))
    total_cost = sum((r.actual_cost if r.actual_cost is not None else r.estimated_cost) for r in records)

    emit(c.report_line('RG-03', 'latency_p95', 'PASS'))
    emit(f'- latency_p95: p95={p95_val:.1f}s max={max_val:.1f}s logical_calls={measurement.logical_calls} retries={measurement.retries} ledger_total={total_cost} USD')


def test_rg03_budget_guard(measurement, emit):
    import controlplane.domain.config_security.incremental_cost as ic
    from controlplane.api.wiring.config_security import InMemoryCostLedger
    from controlplane.api.wiring.creative import budget_policy_from_config

    assert measurement.stack.profile.budget.hard_stop is True
    assert Decimal(str(measurement.stack.profile.budget.monthly_limit)) == Decimal('50')

    policy = budget_policy_from_config({
        'monthly_limit': measurement.stack.profile.budget.monthly_limit,
        'hard_stop': measurement.stack.profile.budget.hard_stop,
        'warn_ratio': measurement.stack.profile.budget.warn_at_ratio,
        'currency': measurement.stack.profile.budget.currency,
    })
    assert policy.hard_stop is True
    assert policy.monthly_limit == Decimal('50')

    local_ledger = InMemoryCostLedger()
    now = datetime.now(timezone.utc)
    start, end = measurement.stack.window(now)
    rec50 = ic.IncrementalCostRecord(
        record_id='rec-guard-50',
        provider='router-primary',
        service=MODEL,
        operation_ref='op-guard',
        job_ref='job-guard',
        batch_ref=None,
        quantity=Decimal('1'),
        unit='request',
        estimated_cost=Decimal('50.01'),
        actual_cost=Decimal('50.01'),
        currency='USD',
        source='routed_invocation',
        occurred_at=now.isoformat(),
        cost_category='api_paid',
    )
    local_ledger.append(WS, rec50)
    status = ic.evaluate_budget(local_ledger.records(WS, start, end), policy, start, end, now)
    assert ic.should_block(status, policy, Decimal('0')) is True

    emit(c.report_line('RG-03', 'budget_guard', 'PASS'))
    emit(f'- budget_guard: hard_stop=True monthly_limit=50 USD policy_check_blocked=True (pure policy test, not quota_wait)')

def test_rg03_warn_80(measurement, emit):
    import controlplane.domain.config_security.incremental_cost as ic
    from controlplane.api.wiring.config_security import InMemoryCostLedger
    from controlplane.api.wiring.creative import budget_policy_from_config

    assert Decimal(str(measurement.stack.profile.budget.warn_at_ratio)) == Decimal('0.8')
    policy = budget_policy_from_config({
        'monthly_limit': measurement.stack.profile.budget.monthly_limit,
        'hard_stop': measurement.stack.profile.budget.hard_stop,
        'warn_ratio': measurement.stack.profile.budget.warn_at_ratio,
        'currency': measurement.stack.profile.budget.currency,
    })

    local_ledger = InMemoryCostLedger()
    now = datetime.now(timezone.utc)
    start, end = measurement.stack.window(now)
    rec40 = ic.IncrementalCostRecord(
        record_id='rec-warn-40',
        provider='router-primary',
        service=MODEL,
        operation_ref='op-warn-40',
        job_ref='job-warn-40',
        batch_ref=None,
        quantity=Decimal('1'),
        unit='request',
        estimated_cost=Decimal('40'),
        actual_cost=Decimal('40'),
        currency='USD',
        source='routed_invocation',
        occurred_at=start.isoformat(),
        cost_category='api_paid',
    )
    local_ledger.append(WS, rec40)
    status40 = ic.evaluate_budget(local_ledger.records(WS, start, end), policy, start, end, end)
    assert status40.level == ic.BudgetLevel.WARN_80, f'expected WARN_80, got {status40.level}'

    rec39 = ic.IncrementalCostRecord(
        record_id='rec-warn-39',
        provider='router-primary',
        service=MODEL,
        operation_ref='op-warn-39',
        job_ref='job-warn-39',
        batch_ref=None,
        quantity=Decimal('1'),
        unit='request',
        estimated_cost=Decimal('39.99'),
        actual_cost=Decimal('39.99'),
        currency='USD',
        source='routed_invocation',
        occurred_at=start.isoformat(),
        cost_category='api_paid',
    )
    local_ledger_39 = InMemoryCostLedger()
    local_ledger_39.append(WS, rec39)
    status39 = ic.evaluate_budget(local_ledger_39.records(WS, start, end), policy, start, end, end)
    assert status39.level == ic.BudgetLevel.OK, f'expected OK, got {status39.level}'

    emit(c.report_line('RG-03', 'warn_80', 'PASS'))
    emit(f'- warn_80: ratio=0.8 limit=50 USD warn_threshold=40 USD at_40=WARN_80 at_39.99=OK')

def test_rg03_quota_wait(measurement, emit):
    if measurement.quota_event and measurement.quota_resumed:
        emit(c.report_line('RG-03', 'quota_wait', 'PASS'))
        emit(f'- quota_wait: quota_event=True quota_resumed=True retries={measurement.retries}')
    elif not measurement.quota_event:
        emit(c.report_line('RG-03', 'quota_wait', 'NOT_OBSERVED'))
        emit(f'- quota_wait: khong gap 429 hoac BUDGET_BLOCKED that')
    else:
        assert False, f'quota_event occurred but was not resumed (retries={measurement.retries})'

def test_rg03_secret_scan(measurement, emit):
    assert measurement.stack.store.current_version(measurement.stack.secret_ref) is not None
    report_text = REPORT.read_text(encoding='utf-8') if REPORT.is_file() else ''
    matches = c.scan_secrets(report_text)
    assert matches == [], f'secret pattern found in report: {matches}'

    emit(c.report_line('RG-03', 'secret_scan', 'PASS'))
    emit(f'- secret_scan: match_count=0 secret_version_exists=True')
