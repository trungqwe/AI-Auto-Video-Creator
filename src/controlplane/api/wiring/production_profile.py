from __future__ import annotations

"""ADAPT-WIRE: hồ sơ production có kiểu; thiếu tham số thì lỗi gọi tên tham số, không default ẩn."""

from collections.abc import Mapping
import dataclasses
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any
import uuid

PROFILE_TEST = 'test'
PROFILE_PRODUCTION = 'production'


class ProductionProfileError(ValueError):
    def __init__(self, parameter: str, reason: str) -> None:
        super().__init__(f'{reason}: {parameter}')
        self.parameter = parameter


REQUIRED_PARAMETERS = tuple(
    'meta.profile_name meta.revision collection.source_kind collection.tiers '
    'collection.fetch_policy.feed collection.fetch_policy.article collection.fetch_policy.image '
    'collection.retry_fetch collection.concurrency collection.collection_interval_minutes '
    'collection.freshness_window_hours collection.extraction_min_text_chars collection.user_agent '
    'ai.route_endpoint ai.route_model_refs ai.request_timeout_seconds ai.retry '
    'ai.reservation_ttl_seconds ai.quota_wait_poll_seconds ai.quota_wait_max '
    'budget.monthly_limit budget.currency budget.hard_stop budget.warn_at_ratio '
    'budget.window_timezone credential.max_ttl_seconds voice.engine voice.duration_range_ms '
    'voice.speech_rate_wpm voice.tts_timeout_seconds voice.stage_retry aligner.engine '
    'aligner.word_timing_tolerance_ms aligner.max_unmatched_word_ratio audio.loudness '
    'audio.bed_gain_db image_safety.categories image_safety.thresholds image_safety.boxblur '
    'image_safety.vision render.profile render.nvenc render.fallback render.timeout_seconds '
    'render.presets render.ass_style render.layout render.sections render.output_stream '
    'qc.duration_range_ms qc.required_language qc.karaoke_tolerance_ms '
    'qc.hook_similarity_min qc.hook_audio_min_dbfs qc.visual_continuity_min qc.max_file_bytes '
    'qc.quality_thresholds '
    'gpu.slots drive.account drive.folders drive.chunk_bytes drive.chunk_timeout_seconds '
    'drive.retry drive.session_ttl_seconds drive.quota_reserve_ratio drive.verify '
    'working_set.max_video_sets working_set.max_bytes working_set.disk_reserve_bytes '
    'retention.original retention.reusable retention.output retention.temporary '
    'retention.log_days retention.audit_days time.timezone workflow.start_to_close_seconds '
    'workflow.heartbeat_seconds workflow.retry workflow.schedule '
    'batch.videos_per_news_per_round batch.target resume.ready_within_seconds'.split()
)


def _leaf(data: Any, name: str) -> Any:
    cur = data
    for part in name.split('.'):
        if not isinstance(cur, dict) or part not in cur:
            raise ProductionProfileError(name, 'missing parameter')
        cur = cur[part]
    if not isinstance(cur, dict) or 'value' not in cur:
        raise ProductionProfileError(name, 'missing parameter')
    val = cur['value']
    if val is None:
        raise ProductionProfileError(name, 'null parameter')
    return val


def _member(value: Any, name: str, key: str, check: Any) -> Any:
    if not isinstance(value, dict) or key not in value:
        raise ProductionProfileError(f'{name}.{key}', 'missing parameter')
    v = value[key]
    if not check(v):
        raise ProductionProfileError(f'{name}.{key}', 'invalid parameter')
    return v


def _whole(value: Any, name: str, check: Any) -> Any:
    if not check(value):
        raise ProductionProfileError(name, 'invalid parameter')
    return value


def _is_int(v: Any) -> bool:
    return type(v) is int


def _is_pos_int(v: Any) -> bool:
    return type(v) is int and v > 0


def _is_nonneg_int(v: Any) -> bool:
    return type(v) is int and v >= 0


def _is_num(v: Any) -> bool:
    return type(v) in (int, float) and not isinstance(v, bool)


def _is_pos_num(v: Any) -> bool:
    return _is_num(v) and v > 0


def _is_text(v: Any) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _is_bool(v: Any) -> bool:
    return type(v) is bool


def _is_dict(v: Any) -> bool:
    return isinstance(v, dict)


def _is_text_list(v: Any) -> bool:
    return isinstance(v, list) and len(v) > 0 and all(_is_text(x) for x in v)


def _is_text_map(v: Any) -> bool:
    return isinstance(v, dict) and len(v) > 0 and all(_is_text(k) and _is_text(val) for k, val in v.items())


def _is_ratio(v: Any) -> bool:
    return _is_num(v) and 0 <= v <= 1


@dataclass(frozen=True)
class FetchPolicyValues:
    max_redirects: int
    max_body_bytes: int
    timeout_seconds: float
    content_types: tuple[str, ...]


@dataclass(frozen=True)
class RetryValues:
    max_attempts: int
    backoff_base_seconds: float
    backoff_max_seconds: float


@dataclass(frozen=True)
class CollectionConfig:
    source_kinds: tuple[str, ...]
    feed: FetchPolicyValues
    article: FetchPolicyValues
    image: FetchPolicyValues
    user_agent: str
    extraction_min_text_chars: int


@dataclass(frozen=True)
class AiConfig:
    route_endpoint: str
    route_model_refs: Mapping[str, str]
    request_timeout_seconds: float
    retry: RetryValues
    reservation_ttl_seconds: int


@dataclass(frozen=True)
class BudgetConfig:
    monthly_limit: Decimal
    currency: str
    hard_stop: bool
    warn_at_ratio: Decimal
    window_timezone: str


@dataclass(frozen=True)
class VoiceConfig:
    library: str
    voice: str
    lang: str
    speed: float
    sample_rate_hz: int
    tts_timeout_seconds: float


@dataclass(frozen=True)
class AlignerConfig:
    library: str
    model: str
    device: str
    compute_type: str
    language: str
    max_unmatched_word_ratio: float


@dataclass(frozen=True)
class ImageSafetyConfig:
    categories: tuple[str, ...]
    vision_timeout_seconds: float


@dataclass(frozen=True)
class RenderConfig:
    timeout_seconds: float


@dataclass(frozen=True)
class DriveConfig:
    chunk_bytes: int
    chunk_timeout_seconds: float
    retry: RetryValues
    session_ttl_seconds: int
    quota_reserve_ratio: float


@dataclass(frozen=True)
class ProductionProfile:
    profile_name: str
    revision: int
    collection: CollectionConfig
    ai: AiConfig
    budget: BudgetConfig
    credential_max_ttl_seconds: int
    voice: VoiceConfig
    aligner: AlignerConfig
    image_safety: ImageSafetyConfig
    render: RenderConfig
    drive: DriveConfig
    parameters: Mapping[str, object]


def _fetch(value: Any, name: str) -> FetchPolicyValues:
    return FetchPolicyValues(
        max_redirects=_member(value, name, 'max_redirects', _is_nonneg_int),
        max_body_bytes=_member(value, name, 'max_body_bytes', _is_pos_int),
        timeout_seconds=float(_member(value, name, 'timeout_seconds', _is_pos_num)),
        content_types=tuple(_member(value, name, 'content_types', _is_text_list)),
    )


def _retry(value: Any, name: str) -> RetryValues:
    return RetryValues(
        max_attempts=_member(value, name, 'max_attempts', _is_pos_int),
        backoff_base_seconds=float(_member(value, name, 'backoff_base_seconds', _is_pos_num)),
        backoff_max_seconds=float(_member(value, name, 'backoff_max_seconds', _is_pos_num)),
    )


def load_production_profile(path: Path | str) -> ProductionProfile:
    try:
        raw = Path(path).read_text(encoding='utf-8')
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError('not a dict')
    except Exception as exc:
        raise ProductionProfileError('profile.json', 'invalid profile file') from exc

    values = {name: _leaf(data, name) for name in REQUIRED_PARAMETERS}
    if values['meta.profile_name'] != 'production':
        raise ProductionProfileError('meta.profile_name', 'invalid parameter')
    revision = _whole(values['meta.revision'], 'meta.revision', _is_pos_int)

    # Collection
    source_kinds = tuple(_whole(values['collection.source_kind'], 'collection.source_kind', _is_text_list))
    feed = _fetch(values['collection.fetch_policy.feed'], 'collection.fetch_policy.feed')
    article = _fetch(values['collection.fetch_policy.article'], 'collection.fetch_policy.article')
    image = _fetch(values['collection.fetch_policy.image'], 'collection.fetch_policy.image')
    user_agent = _whole(values['collection.user_agent'], 'collection.user_agent', _is_text)
    extraction_min_text_chars = _whole(
        values['collection.extraction_min_text_chars'],
        'collection.extraction_min_text_chars',
        _is_pos_int,
    )
    collection = CollectionConfig(
        source_kinds=source_kinds,
        feed=feed,
        article=article,
        image=image,
        user_agent=user_agent,
        extraction_min_text_chars=extraction_min_text_chars,
    )

    # AI
    route_endpoint = _whole(values['ai.route_endpoint'], 'ai.route_endpoint', _is_text)
    route_model_refs = _whole(values['ai.route_model_refs'], 'ai.route_model_refs', _is_text_map)
    for key in ('analysis', 'angle', 'script', 'selection', 'metadata', 'image_safety'):
        if key not in route_model_refs:
            raise ProductionProfileError(f'ai.route_model_refs.{key}', 'missing parameter')
    request_timeout_seconds = float(_whole(values['ai.request_timeout_seconds'], 'ai.request_timeout_seconds', _is_pos_num))
    ai_retry = _retry(values['ai.retry'], 'ai.retry')
    reservation_ttl_seconds = _whole(values['ai.reservation_ttl_seconds'], 'ai.reservation_ttl_seconds', _is_pos_int)
    ai = AiConfig(
        route_endpoint=route_endpoint,
        route_model_refs=MappingProxyType(dict(route_model_refs)),
        request_timeout_seconds=request_timeout_seconds,
        retry=ai_retry,
        reservation_ttl_seconds=reservation_ttl_seconds,
    )

    # Budget
    monthly_limit = Decimal(str(_whole(values['budget.monthly_limit'], 'budget.monthly_limit', _is_pos_num)))
    currency = _whole(values['budget.currency'], 'budget.currency', _is_text)
    hard_stop = _whole(values['budget.hard_stop'], 'budget.hard_stop', _is_bool)
    warn_at_ratio = Decimal(str(_whole(values['budget.warn_at_ratio'], 'budget.warn_at_ratio', _is_ratio)))
    window_timezone = _whole(values['budget.window_timezone'], 'budget.window_timezone', _is_text)
    budget = BudgetConfig(
        monthly_limit=monthly_limit,
        currency=currency,
        hard_stop=hard_stop,
        warn_at_ratio=warn_at_ratio,
        window_timezone=window_timezone,
    )

    # Credential
    credential_max_ttl_seconds = _whole(
        values['credential.max_ttl_seconds'],
        'credential.max_ttl_seconds',
        _is_pos_int,
    )

    # Voice
    v_eng = values['voice.engine']
    v_lib = _member(v_eng, 'voice.engine', 'library', _is_text)
    v_voice = _member(v_eng, 'voice.engine', 'voice', _is_text)
    v_lang = _member(v_eng, 'voice.engine', 'lang', _is_text)
    v_speed = float(_member(v_eng, 'voice.engine', 'speed', _is_pos_num))
    v_output = _member(v_eng, 'voice.engine', 'output', _is_dict)
    v_sample_rate = _member(v_output, 'voice.engine.output', 'sample_rate_hz', _is_pos_int)
    tts_timeout_seconds = float(_whole(values['voice.tts_timeout_seconds'], 'voice.tts_timeout_seconds', _is_pos_num))
    voice = VoiceConfig(
        library=v_lib,
        voice=v_voice,
        lang=v_lang,
        speed=v_speed,
        sample_rate_hz=v_sample_rate,
        tts_timeout_seconds=tts_timeout_seconds,
    )

    # Aligner
    al_eng = values['aligner.engine']
    al_lib = _member(al_eng, 'aligner.engine', 'library', _is_text)
    al_model = _member(al_eng, 'aligner.engine', 'model', _is_text)
    al_device = _member(al_eng, 'aligner.engine', 'device', _is_text)
    al_compute = _member(al_eng, 'aligner.engine', 'compute_type', _is_text)
    al_lang = _member(al_eng, 'aligner.engine', 'language', _is_text)
    max_unmatched_word_ratio = float(_whole(
        values['aligner.max_unmatched_word_ratio'],
        'aligner.max_unmatched_word_ratio',
        _is_ratio,
    ))
    aligner = AlignerConfig(
        library=al_lib,
        model=al_model,
        device=al_device,
        compute_type=al_compute,
        language=al_lang,
        max_unmatched_word_ratio=max_unmatched_word_ratio,
    )

    # Image safety
    categories = tuple(_whole(values['image_safety.categories'], 'image_safety.categories', _is_text_list))
    vision_timeout_seconds = float(_member(values['image_safety.vision'], 'image_safety.vision', 'timeout_seconds', _is_pos_num))
    image_safety = ImageSafetyConfig(
        categories=categories,
        vision_timeout_seconds=vision_timeout_seconds,
    )

    # Render
    render_timeout_seconds = float(_whole(values['render.timeout_seconds'], 'render.timeout_seconds', _is_pos_num))
    render = RenderConfig(timeout_seconds=render_timeout_seconds)

    # Drive
    chunk_bytes = _whole(values['drive.chunk_bytes'], 'drive.chunk_bytes', _is_pos_int)
    chunk_timeout_seconds = float(_whole(values['drive.chunk_timeout_seconds'], 'drive.chunk_timeout_seconds', _is_pos_num))
    drive_retry = _retry(values['drive.retry'], 'drive.retry')
    session_ttl_seconds = _whole(values['drive.session_ttl_seconds'], 'drive.session_ttl_seconds', _is_pos_int)
    quota_reserve_ratio = float(_whole(values['drive.quota_reserve_ratio'], 'drive.quota_reserve_ratio', _is_ratio))
    drive = DriveConfig(
        chunk_bytes=chunk_bytes,
        chunk_timeout_seconds=chunk_timeout_seconds,
        retry=drive_retry,
        session_ttl_seconds=session_ttl_seconds,
        quota_reserve_ratio=quota_reserve_ratio,
    )

    parameters = MappingProxyType(values)
    return ProductionProfile(
        profile_name='production',
        revision=revision,
        collection=collection,
        ai=ai,
        budget=budget,
        credential_max_ttl_seconds=credential_max_ttl_seconds,
        voice=voice,
        aligner=aligner,
        image_safety=image_safety,
        render=render,
        drive=drive,
        parameters=parameters,
    )


@dataclass(frozen=True, kw_only=True)
class ProductionRuntime:
    ffmpeg_path: Path
    ffprobe_path: Path
    runtime_lock_path: Path
    weights_dir: Path
    weights_lock_path: Path
    whisper_model_dir: Path
    staging_root: Path
    secret_store_root: Path
    oauth_client_secrets_path: Path
    oauth_consent_timeout_seconds: int
    route_cost_per_request: Decimal
    tokenization: Mapping[str, Any]
    drive_placement: Mapping[str, str]
    drive_fallback_parent_id: str
    route_catalog: Any
    provider_credentials: Any
    vision_route: Any
    artifact_source: Any
    drive_token_broker: Any
    gpu_lease: Any

    def __post_init__(self) -> None:
        path_fields = (
            'ffmpeg_path',
            'ffprobe_path',
            'runtime_lock_path',
            'weights_dir',
            'weights_lock_path',
            'whisper_model_dir',
            'staging_root',
            'secret_store_root',
            'oauth_client_secrets_path',
        )
        for name in path_fields:
            val = getattr(self, name)
            if not isinstance(val, Path) or not val.is_absolute():
                raise ProductionProfileError('runtime.' + name, 'invalid parameter')

        if type(self.oauth_consent_timeout_seconds) is not int or self.oauth_consent_timeout_seconds <= 0:
            raise ProductionProfileError('runtime.oauth_consent_timeout_seconds', 'invalid parameter')

        try:
            c = Decimal(str(self.route_cost_per_request))
            if not c.is_finite() or c < 0:
                raise ValueError()
            object.__setattr__(self, 'route_cost_per_request', c)
        except (InvalidOperation, ValueError, Exception):
            raise ProductionProfileError('runtime.route_cost_per_request', 'invalid parameter')

        if not isinstance(self.tokenization, Mapping):
            raise ProductionProfileError('runtime.tokenization', 'invalid parameter')

        if (
            not isinstance(self.drive_placement, Mapping)
            or not self.drive_placement
            or not all(_is_text(k) and _is_text(v) for k, v in self.drive_placement.items())
        ):
            raise ProductionProfileError('runtime.drive_placement', 'invalid parameter')

        if not _is_text(self.drive_fallback_parent_id):
            raise ProductionProfileError('runtime.drive_fallback_parent_id', 'invalid parameter')

        ports = (
            'route_catalog',
            'provider_credentials',
            'vision_route',
            'artifact_source',
            'drive_token_broker',
            'gpu_lease',
        )
        for name in ports:
            if getattr(self, name) is None:
                raise ProductionProfileError('runtime.' + name, 'invalid parameter')


@dataclass(frozen=True)
class WiringConfig:
    mode: str
    workspace_id: str
    profile: ProductionProfile | None = None
    runtime: ProductionRuntime | None = None

    def __post_init__(self) -> None:
        if self.mode not in (PROFILE_TEST, PROFILE_PRODUCTION):
            raise ProductionProfileError('mode', 'invalid parameter')

        if not isinstance(self.workspace_id, str):
            raise ProductionProfileError('workspace_id', 'invalid parameter')
        try:
            uuid.UUID(self.workspace_id)
        except Exception:
            raise ProductionProfileError('workspace_id', 'invalid parameter')

        if self.mode == PROFILE_PRODUCTION:
            if self.profile is None:
                raise ProductionProfileError('profile', 'missing parameter')
            if self.runtime is None:
                raise ProductionProfileError('runtime', 'missing parameter')

    def production_parts(self) -> tuple[ProductionProfile, ProductionRuntime]:
        if self.mode != PROFILE_PRODUCTION:
            raise ProductionProfileError('mode', 'not a production profile')
        assert self.profile is not None and self.runtime is not None
        return (self.profile, self.runtime)


__all__ = [
    'PROFILE_TEST',
    'PROFILE_PRODUCTION',
    'REQUIRED_PARAMETERS',
    'ProductionProfileError',
    'FetchPolicyValues',
    'RetryValues',
    'CollectionConfig',
    'AiConfig',
    'BudgetConfig',
    'VoiceConfig',
    'AlignerConfig',
    'ImageSafetyConfig',
    'RenderConfig',
    'DriveConfig',
    'ProductionProfile',
    'ProductionRuntime',
    'WiringConfig',
    'load_production_profile',
]
