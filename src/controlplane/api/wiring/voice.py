from __future__ import annotations

"""ADAPT-WIRE: wiring cho phân hệ E (voice).
Đấu nối RealKokoroTts, RealWhisperAligner, RealFfmpegMediaTool, LlmImageSafetyDetector và PostgresVoiceUnitOfWork.
Không nạp mô hình hay tải trọng số lúc dựng."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

from controlplane.api.wiring._shared import resolve_under_root
from controlplane.api.wiring.production_profile import (
    PROFILE_PRODUCTION,
    ProductionProfileError,
    WiringConfig,
)
from voice.adapters.fake_aligner import FakeAligner
from voice.adapters.fake_tts import FakeTtsEngine, FakeVoiceRoute
from voice.adapters.memory import InMemoryUnitOfWork
from voice.adapters.real_ffmpeg_media_tool import FfmpegToolError, RealFfmpegMediaTool
from voice.adapters.real_kokoro_tts import KokoroConfig, RealKokoroTts, VoiceArtifactPlacer
from voice.adapters.real_llm_image_safety import LlmImageSafetyDetector
from voice.adapters.real_whisper_aligner import (
    RealWhisperAligner,
    WhisperAlignerConfig,
)
from voice.domain.processing import ArtifactRef
from voice.domain.timing_coverage import TokenizationPolicy
from voice.persistence.unit_of_work import PostgresVoiceUnitOfWork
import datetime
import hashlib
import json
import re
import threading
import http.client
import ipaddress
import math
import socket
import ssl
from collections.abc import Sequence
from urllib.parse import urlsplit
from controlplane.api.wiring.workflow import voice_handler
from controlplane.application.orchestration.workflows.activities import ActivityRejected, MISSING_EXECUTION_GRANT, to_execution_grant
from voice.adapters.activity_inputs import ActivityInputError, MediaArtifact, PlanAudio, ProductionActivityInputs, REF_SELECTED_MEDIA, VoiceSettings, _first_ref
from voice.adapters.audio_bed_source import AudioBedSource, HttpsResponse, MusicSource, MusicSourceError, load_music_sources
from voice.adapters.local_voice_route import LocalVoiceRoute
from voice.adapters.postgres_script_text import PostgresScriptText
from voice.adapters.profile_media_policy import build_image_safety_policy, build_image_safety_rules, build_voice_duration_policy
from voice.adapters.wav_duration import measure_wav_duration_ms
from voice.application.media_pipeline import MediaPipeline, VerifiedOutput
from voice.application.voice_pipeline import VoicePipeline
from voice.domain.audio_bed import AudioCue
from voice.domain.image_safety import ImageSafetyAssessment, SafetyOutcome, assess_image_safety
from voice.domain.speed_fit import SpeedFitPolicy
from voice.worker.activity_handler import VoiceActivityDeps, validate_activity_request

_TOKEN_KEYS = (
    'revision',
    'unicode_form',
    'casefold',
    'edge_strip_categories',
    'gap_tolerance_ms',
    'min_confidence',
)
_MEDIA_TYPES = {
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.webp': 'image/webp',
}


def _tokenization(runtime: Any) -> TokenizationPolicy:
    m = runtime.tokenization
    for key in _TOKEN_KEYS:
        if key not in m:
            raise ProductionProfileError('runtime.tokenization.' + key, 'missing parameter')
    return TokenizationPolicy(
        revision=m['revision'],
        unicode_form=m['unicode_form'],
        casefold=m['casefold'],
        edge_strip_categories=tuple(m['edge_strip_categories']),
        gap_tolerance_ms=m['gap_tolerance_ms'],
        min_confidence=m['min_confidence'],
    )


@dataclass(frozen=True)
class VoiceServices:
    mode: str
    uow_factory: Callable[[], Any]
    tts: Any
    aligner: Any
    media_tool: Any
    image_safety_detector_factory: Any
    artifact_placer: Any = None


def build_voice_services(manager: Any, config: WiringConfig) -> VoiceServices:
    if config.mode != PROFILE_PRODUCTION:
        return VoiceServices(
            config.mode,
            InMemoryUnitOfWork,
            FakeTtsEngine(FakeVoiceRoute()),
            FakeAligner(),
            None,
            None,
        )

    profile, runtime = config.production_parts()
    v = profile.voice
    al = profile.aligner
    im = profile.image_safety
    voice_root = runtime.staging_root / 'voice'
    media_root = runtime.staging_root / 'media'

    policy = _tokenization(runtime)
    voice_root.mkdir(parents=True, exist_ok=True)
    media_root.mkdir(parents=True, exist_ok=True)

    tts = RealKokoroTts(
        KokoroConfig(
            weights_dir=runtime.weights_dir,
            lock_path=runtime.weights_lock_path,
            staging_dir=voice_root,
            voice=v.voice,
            speed=v.speed,
            language=v.lang,
            sample_rate=v.sample_rate_hz,
        )
    )
    aligner = RealWhisperAligner(
        WhisperAlignerConfig(
            model_dir=runtime.whisper_model_dir,
            lock_path=runtime.weights_lock_path,
            voice_root=voice_root,
            tokenization_policy=policy,
            max_unmatched_word_ratio=al.max_unmatched_word_ratio,
            language=al.language,
            device=al.device,
            compute_type=al.compute_type,
        )
    )
    locate = locate_media_file(manager, config.workspace_id, runtime.staging_root)

    def resolve_input(ref: str) -> Path:
        found = locate(ref)
        if found is None:
            raise FfmpegToolError('input_missing')
        return found

    media_tool = RealFfmpegMediaTool(
        runtime.ffmpeg_path,
        runtime.runtime_lock_path,
        resolve_input,
        lambda ref, ext: resolve_under_root(media_root, ref.replace(':', '_') + '.' + ext),
    )

    uncertain_min = build_image_safety_rules(profile.parameters).uncertain_min

    def detector_factory(artifact_ref: ArtifactRef) -> LlmImageSafetyDetector:
        return LlmImageSafetyDetector(
            runtime.vision_route,
            artifact_ref,
            read_media_image(locate),
            categories=im.categories,
            timeout_seconds=im.vision_timeout_seconds,
            uncertain_min=uncertain_min,
        )

    artifact_placer = VoiceArtifactPlacer(voice_root)
    uow_factory = partial(PostgresVoiceUnitOfWork, manager, workspace_id=config.workspace_id)
    return VoiceServices('production', uow_factory, tts, aligner, media_tool, detector_factory, artifact_placer)



def _read_tool_version(lock_path: Path | str) -> str:
    try:
        data = json.loads(Path(lock_path).read_text(encoding='utf-8'))
        entry = data.get('pins', {}).get('ffmpeg', {})
        return str(entry.get('archive_name') or entry.get('sha256') or 'ffmpeg-pinned')
    except Exception:
        return 'ffmpeg-pinned'


class ThreadLocalVoiceUow:
    def __init__(self, factory: Callable[[], Any]) -> None:
        self._factory = factory
        self._local = threading.local()

    def _get(self) -> Any:
        if not hasattr(self._local, 'uow'):
            self._local.uow = self._factory()
        return self._local.uow

    def __enter__(self) -> Any:
        return self._get().__enter__()

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Any:
        return self._get().__exit__(exc_type, exc_val, exc_tb)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._get(), name)


class ArtifactRows:
    def __init__(self, manager: Any, workspace_id: str) -> None:
        self._manager = manager
        self._workspace_id = workspace_id

    def media_artifact(
        self, *, workspace_id: str, media_asset_id: str, artifact_version_ref: str
    ) -> MediaArtifact:
        sql = (
            'SELECT v.sha256_hash, v.size_bytes, v.mime_type '
            'FROM controlplane.cp_artifact_versions v '
            'WHERE v.workspace_id = %s::uuid AND v.artifact_version_id = %s::uuid'
        )
        row = None
        try:
            with self._manager.borrow_connection() as conn:
                row = conn.execute(sql, (workspace_id, artifact_version_ref)).fetchone()
        except Exception:
            row = None
        if row is None:
            raise ActivityInputError('INPUT_NOT_READY', 'media_artifact_not_found')
        sha = str(row[0])
        size = int(row[1])
        mime = str(row[2])
        ext = mime.split('/')[-1] if mime and '/' in mime else 'png'
        return MediaArtifact(ArtifactRef(artifact_version_ref, sha), ext, mime, size)


class PlanAudioFromPlans:
    def __init__(self, manager: Any, workspace_id: str) -> None:
        self._manager = manager
        self._workspace_id = workspace_id

    def plan_audio(self, *, workspace_id: str, production_plan_id: str) -> PlanAudio:
        sql = (
            'SELECT payload FROM controlplane.cp_production_plans '
            'WHERE workspace_id = %s::uuid AND production_plan_id = %s '
            'ORDER BY revision DESC LIMIT 1'
        )
        row = None
        try:
            with self._manager.borrow_connection() as conn:
                row = conn.execute(sql, (workspace_id, production_plan_id)).fetchone()
        except Exception:
            row = None
        if row is None:
            raise ActivityInputError('INPUT_NOT_READY', 'production_plan_not_found')
        payload = row[0]
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {}
        if not isinstance(payload, Mapping):
            payload = {}

        cues: list[AudioCue] = []
        music_cues = payload.get('music_cues')
        if isinstance(music_cues, list):
            for m in music_cues:
                if isinstance(m, Mapping) and 'start_ms' in m and 'end_ms' in m and m['start_ms'] < m['end_ms']:
                    cues.append(
                        AudioCue(
                            kind='music',
                            start_ms=int(m['start_ms']),
                            end_ms=int(m['end_ms']),
                            artifact_ref=str(m.get('artifact_ref') or m.get('cue') or 'music-1'),
                            mood=str(m.get('mood') or '').strip() or None,
                        )
                    )
        sfx_cues = payload.get('sfx_cues')
        if isinstance(sfx_cues, list):
            for s in sfx_cues:
                if isinstance(s, Mapping) and 'start_ms' in s and 'end_ms' in s and s['start_ms'] < s['end_ms']:
                    cues.append(
                        AudioCue(
                            kind='sfx',
                            start_ms=int(s['start_ms']),
                            end_ms=int(s['end_ms']),
                            artifact_ref=str(s.get('artifact_ref') or s.get('cue') or 'sfx-1'),
                            mood=str(s.get('mood')) if s.get('mood') else None,
                        )
                    )
        if not cues:
            cues.append(AudioCue(kind='music', start_ms=0, end_ms=5000, artifact_ref='music-default', mood=None))

        preset_audio = str(payload.get('preset_audio_policy_revision') or 'audio-pol-1')
        mix_constraints = payload.get('mix_constraints')
        if not isinstance(mix_constraints, Mapping):
            mix_constraints = {'duck_db': -12}
        fallback_allowed = bool(payload.get('fallback_allowed', False))
        fallback_artifact_refs = tuple(str(x) for x in payload.get('fallback_artifact_refs', ()))

        return PlanAudio(
            cues=tuple(cues),
            preset_audio_policy_revision=preset_audio,
            mix_constraints=dict(mix_constraints),
            fallback_allowed=fallback_allowed,
            fallback_artifact_refs=fallback_artifact_refs,
        )


class SelectionSeedFallback:
    def __init__(self, manager: Any, workspace_id: str) -> None:
        self._manager = manager
        self._workspace_id = workspace_id

    def fallback_media(self, *, workspace_id: str, selection_ref: str) -> Sequence[MediaArtifact]:
        sql = (
            'SELECT payload FROM controlplane.cp_creative_selections '
            'WHERE workspace_id = %s AND selection_id = %s '
            'ORDER BY selection_revision DESC LIMIT 1'
        )
        row = None
        try:
            with self._manager.borrow_connection() as conn:
                row = conn.execute(sql, (workspace_id, selection_ref)).fetchone()
        except Exception:
            row = None
        if row is None:
            raise ActivityInputError('INPUT_NOT_READY', 'creative_selection_not_found')
        payload = row[0]
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {}
        if not isinstance(payload, Mapping):
            payload = {}

        fallbacks = payload.get('fallback_candidates') or []
        results: list[MediaArtifact] = []
        art_sql = (
            'SELECT v.sha256_hash, v.size_bytes, v.mime_type '
            'FROM controlplane.cp_artifact_versions v '
            'WHERE v.workspace_id = %s::uuid AND v.artifact_version_id = %s::uuid'
        )
        with self._manager.borrow_connection() as conn:
            for item in fallbacks:
                if not isinstance(item, Mapping):
                    continue
                v_ref = item.get('artifact_version_ref')
                if not v_ref:
                    continue
                try:
                    arow = conn.execute(art_sql, (workspace_id, str(v_ref))).fetchone()
                except Exception:
                    arow = None
                if arow is not None:
                    sha = str(arow[0])
                    size = int(arow[1])
                    mime = str(arow[2])
                    ext = mime.split('/')[-1] if mime and '/' in mime else 'png'
                    results.append(MediaArtifact(ArtifactRef(str(v_ref), sha), ext, mime, size))
        return tuple(results)


_IMAGE_SUFFIXES = ('png', 'jpg', 'jpeg', 'webp')
_VERSION_REF = re.compile(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}')
_RENDITION_REF = re.compile(r'(?:processed|rendition):[0-9A-Za-z]{8,128}')
_MUSIC_REF = re.compile(r'music-[0-9a-f]{64}')
_BED_NONE_REF = re.compile(r'bed-none-[0-9a-f]{64}')
_VERIFIED_VERSION_SQL = (
    'SELECT v.artifact_id, v.sha256_hash FROM controlplane.cp_artifact_versions v '
    'WHERE v.workspace_id = %s::uuid AND v.artifact_version_id = %s::uuid '
    'AND EXISTS (SELECT 1 FROM controlplane.cp_artifact_locations l '
    'WHERE l.workspace_id = v.workspace_id AND l.artifact_version_id = v.artifact_version_id '
    "AND l.state = 'VERIFIED' AND (l.observed_hash IS NULL OR l.observed_hash = v.sha256_hash))"
)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def locate_media_file(manager: Any, workspace_id: str, staging_root: Path) -> Callable[[str], Path | None]:
    media_root = staging_root / 'media'
    library_root = staging_root / 'audio_library'

    def by_version(ref: str) -> Path | None:
        with manager.borrow_connection() as conn:
            row = conn.execute(_VERIFIED_VERSION_SQL, (workspace_id, ref)).fetchone()
        if row is None:
            return None
        path = resolve_under_root(staging_root, str(row[0]))
        if not path.is_file() or _file_sha256(path) != str(row[1]):
            return None
        return path

    def by_rendition(ref: str) -> Path | None:
        stem = ref.replace(':', '_')
        found = [p for p in (resolve_under_root(media_root, stem + '.' + s) for s in _IMAGE_SUFFIXES) if p.is_file()]
        return found[0] if len(found) == 1 else None

    def by_library(name: str) -> Path | None:
        path = resolve_under_root(library_root, name)
        return path if path.is_file() else None

    def locate(ref: str) -> Path | None:
        if not isinstance(ref, str):
            return None
        try:
            if _VERSION_REF.fullmatch(ref):
                return by_version(ref.lower())
            if _RENDITION_REF.fullmatch(ref):
                return by_rendition(ref)
            if _MUSIC_REF.fullmatch(ref):
                return by_library(ref + '.audio')
            if _BED_NONE_REF.fullmatch(ref):
                return by_library(ref + '.wav')
        except ValueError:
            return None
        return None

    return locate


def verify_media_output(locate: Callable[[str], Path | None]) -> Callable[[str], VerifiedOutput | None]:
    def verify(ref: str) -> VerifiedOutput | None:
        try:
            path = locate(ref)
            if path is None:
                return None
            data = path.read_bytes()
            return VerifiedOutput(hashlib.sha256(data).hexdigest(), len(data))
        except Exception:
            return None

    return verify


def read_media_image(locate: Callable[[str], Path | None]) -> Callable[[str], tuple[bytes, str]]:
    def read_image(ref: str) -> tuple[bytes, str]:
        path = locate(ref)
        if path is None:
            raise ValueError('IMAGE_NOT_FOUND')
        suf = path.suffix.lower()
        if suf not in _MEDIA_TYPES:
            raise ValueError('UNSUPPORTED_IMAGE_TYPE')
        return (path.read_bytes(), _MEDIA_TYPES[suf])

    return read_image


class _PinnedTlsConnection(http.client.HTTPSConnection):
    """TCP goes only to addresses already checked; TLS uses SNI and certificate verification against the host name."""

    def __init__(self, host: str, addresses: Sequence[tuple], timeout: float) -> None:
        self._tls_context = ssl.create_default_context()
        super().__init__(host, 443, timeout=timeout, context=self._tls_context)
        self._pinned = tuple(addresses)

    def connect(self) -> None:
        last_error: OSError = ConnectionError('NO_PINNED_ADDRESS')
        for family, sockaddr in self._pinned:
            sock = socket.socket(family, socket.SOCK_STREAM)
            try:
                sock.settimeout(self.timeout)
                sock.connect(sockaddr)
                self.sock = self._tls_context.wrap_socket(sock, server_hostname=self.host)
            except OSError as error:
                sock.close()
                last_error = error
                continue
            return
        raise last_error


class ProductionHttpsTransport:
    """Resolves the host itself, refuses a name that resolves to nothing or to any non-global address, connects only to the checked address, one GET, no redirect, no proxy."""

    def __init__(self, *, resolve: Callable[..., Sequence[tuple]] = socket.getaddrinfo, user_agent: str = 'AI-Auto-Video-Creator/1.0') -> None:
        self._resolve = resolve
        self._user_agent = user_agent

    @staticmethod
    def _policy(url: str) -> tuple[str, str]:
        try:
            parts = urlsplit(url)
            host, port = parts.hostname, parts.port
        except (ValueError, AttributeError, TypeError):
            raise MusicSourceError('music_url_not_allowed', 'unparsable') from None
        if parts.scheme != 'https' or not host or parts.username or parts.password or port not in (None, 443):
            raise MusicSourceError('music_url_not_allowed', 'policy')
        return host, (parts.path or '/') + ('?' + parts.query if parts.query else '')

    def _checked_addresses(self, host: str) -> list[tuple]:
        infos = self._resolve(host, 443, type=socket.SOCK_STREAM)
        addresses = []
        for family, _kind, _proto, _name, sockaddr in infos:
            try:
                is_global = ipaddress.ip_address(str(sockaddr[0]).split('%')[0]).is_global
            except ValueError:
                is_global = False
            if not is_global:
                raise MusicSourceError('music_url_not_allowed', 'non_global_address')
            addresses.append((family, sockaddr))
        if not addresses:
            raise MusicSourceError('music_url_not_allowed', 'no_address')
        return addresses

    def fetch(self, url: str, *, max_bytes: int, timeout_seconds: float) -> HttpsResponse:
        host, target = self._policy(url)
        addresses = self._checked_addresses(host)
        connection = _PinnedTlsConnection(host, addresses, timeout_seconds)
        try:
            connection.request('GET', target, headers={'User-Agent': self._user_agent, 'Accept': '*/*', 'Accept-Encoding': 'identity', 'Connection': 'close'})
            response = connection.getresponse()
            body = response.read(max_bytes + 1) if response.status == 200 else b''
            return HttpsResponse(response.status, body, url)
        finally:
            connection.close()


def _music_loudness_target(parameters: Any) -> dict[str, float]:
    value = parameters.get('audio.loudness') if isinstance(parameters, Mapping) else None
    if not isinstance(value, Mapping):
        raise ProductionProfileError('audio.loudness', 'missing parameter')
    target: dict[str, float] = {}
    for key in ('integrated_lufs', 'true_peak_dbtp', 'lra'):
        if key not in value:
            raise ProductionProfileError(f'audio.loudness.{key}', 'missing parameter')
        item = value[key]
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item):
            raise ProductionProfileError(f'audio.loudness.{key}', 'invalid parameter')
        target[key] = float(item)
    return target


def voice_activity_deps(
    services: VoiceServices,
    *,
    manager: Any,
    workspace_id: str,
    profile: Any,
    runtime: Any,
    grants: Any,
    clock: Callable[[], datetime.datetime],
    music_sources: Sequence[MusicSource] | None = None,
    music_transport: Any = None,
) -> tuple[VoiceActivityDeps, ProductionActivityInputs]:
    uow = ThreadLocalVoiceUow(services.uow_factory)

    safety_policy = build_image_safety_policy(profile.parameters)
    if hasattr(services.media_tool, '_reassess') and services.media_tool._reassess is None:
        def reassess(processed: ArtifactRef) -> ImageSafetyAssessment:
            try:
                det = services.image_safety_detector_factory(processed)
                res = assess_image_safety('image', det, safety_policy)
                if isinstance(res, ImageSafetyAssessment):
                    return res
            except Exception:
                pass
            return ImageSafetyAssessment(
                outcome=SafetyOutcome.DETECTION_FAILED,
                original_usable=True,
                reason='post_transform_not_reassessed',
                warnings=('post_transform_not_reassessed',),
                policy_revision=str(getattr(safety_policy, 'revision', 'default')),
            )
        services.media_tool._reassess = reassess

    if music_sources is None:
        music_sources = ()
        sources_path = Path('tools/launcher/prod/music_sources.json')
        if sources_path.is_file():
            try:
                music_sources = tuple(load_music_sources(sources_path))
            except Exception:
                music_sources = ()

    loudness = _music_loudness_target(profile.parameters)
    library_dir = runtime.staging_root / 'audio_library'
    audio_bed = AudioBedSource(
        sources=tuple(music_sources),
        library_dir=library_dir,
        transport=music_transport if music_transport is not None else ProductionHttpsTransport(),
        prepare_music=partial(services.media_tool.prepare_music, work_dir=library_dir, **loudness),
        clock=clock,
    )

    media_pipe = MediaPipeline(
        uow=uow,
        probe=services.media_tool,
        tool=services.media_tool,
        transformer=services.media_tool,
        audio_bed=audio_bed,
    )

    voice_pipe = VoicePipeline(
        uow=uow,
        script_port=PostgresScriptText(manager, workspace_id=workspace_id),
        route_port=LocalVoiceRoute(),
        tts_engine=services.tts,
        aligner=services.aligner,
        measure_duration_ms=measure_wav_duration_ms,
        place_artifact=services.artifact_placer,
    )

    dur = None
    v = getattr(profile, 'voice', None)
    if v is not None and hasattr(v, 'duration_range_ms'):
        dur = getattr(v, 'duration_range_ms')
    elif hasattr(profile, 'parameters') and isinstance(profile.parameters, Mapping):
        dur = profile.parameters.get('voice.duration_range_ms')
    min_ms = 60000
    max_ms = 70000
    if isinstance(dur, Mapping):
        min_ms = int(dur.get('min', min_ms))
        max_ms = int(dur.get('max', max_ms))
    duration_policy = (min_ms, max_ms)

    locate = locate_media_file(manager, workspace_id, runtime.staging_root)

    inputs = ProductionActivityInputs(
        parameters=profile.parameters,
        tool_version=_read_tool_version(runtime.runtime_lock_path),
        scripts=PostgresScriptText(manager, workspace_id=workspace_id),
        outputs=uow.outputs,
        media=ArtifactRows(manager, workspace_id),
        plans=PlanAudioFromPlans(manager, workspace_id),
        selections=SelectionSeedFallback(manager, workspace_id),
        vision=runtime.vision_route,
        read_image=read_media_image(locate),
        verify_output=verify_media_output(locate),
        settings=VoiceSettings(
            voice_profile_ref=f'voice-{profile.voice.voice}',
            provider_route_ref='kokoro-local',
            expected_language=getattr(profile.aligner, 'language', 'en'),
            data_sensitivity='internal',
            max_cost_class='low',
            duration_policy=duration_policy,
            tokenization_policy=_tokenization(runtime),
            attempt_policy={'max_attempts': 2, 'max_attempts_per_provider': 2},
            speed_fit=SpeedFitPolicy(
                min_scale=profile.voice.speed_fit_min_scale,
                max_scale=profile.voice.speed_fit_max_scale,
                duration_slope=profile.voice.speed_fit_duration_slope,
            ),
        ),
        clock=clock,
    )

    deps = VoiceActivityDeps(
        voice=voice_pipe,
        media=media_pipe,
        grants=grants,
        inputs=inputs,
        clock=clock,
    )
    return deps, inputs


def voice_activity_handlers(
    services: VoiceServices,
    *,
    manager: Any,
    workspace_id: str,
    profile: Any,
    runtime: Any,
    grants: Any,
    clock: Callable[[], datetime.datetime],
) -> dict[str, Any]:
    deps, inputs = voice_activity_deps(
        services,
        manager=manager,
        workspace_id=workspace_id,
        profile=profile,
        runtime=runtime,
        grants=grants,
        clock=clock,
    )
    base = voice_handler(deps, workspace_id=workspace_id)

    def assess_handler(request: Mapping[str, Any], claims: Any) -> dict[str, Any]:
        result = base(request, claims)
        if result.get('disposition') == 'succeeded':
            return {**result, 'output_refs': inputs.assessment_refs(request)}
        return result

    def transform_handler(request: Mapping[str, Any], claims: Any) -> dict[str, Any]:
        result = base(request, claims)
        if result.get('disposition') == 'succeeded' and result.get('output_refs'):
            return {**result, 'output_refs': inputs.transform_refs(request, result['output_refs'])}
        return result

    def normalize_handler(request: Mapping[str, Any], claims: Any) -> dict[str, Any]:
        if claims is None:
            raise ActivityRejected(MISSING_EXECUTION_GRANT)
        job_id = request.get('video_job_id')
        if not isinstance(job_id, str) or not job_id.strip():
            raise ActivityRejected('INVALID_ACTIVITY_REQUEST')
        grant = to_execution_grant(claims, workspace_id=workspace_id, job_id=job_id)
        if not validate_activity_request(request, grant) and deps.grants.is_grant_current(grant):
            try:
                source = inputs.normalize_source(grant.workspace_id, request['input_refs'])
            except ActivityInputError:
                source = None
            if source is not None and source.artifact is None:
                moment = clock()
                completed_at = moment.astimezone(datetime.timezone.utc).replace(microsecond=0, tzinfo=None).isoformat() + 'Z'
                return {
                    'stage_run_id': grant.stage_run_id,
                    'grant_id': grant.operation_id,
                    'execution_generation': grant.execution_generation,
                    'recovery_epoch': str(grant.recovery_epoch),
                    'disposition': 'succeeded',
                    'output_refs': [],
                    'completed_at': completed_at,
                    'warnings': [f'image_excluded:{source.reason}'],
                }
        result = base(request, claims)
        if result.get('disposition') == 'succeeded' and result.get('output_refs'):
            item = _first_ref(request['input_refs'], REF_SELECTED_MEDIA)
            return {**result, 'output_refs': [{**ref, 'source_ref_id': item['ref_id']} for ref in result['output_refs']]}
        return result

    return {
        'CreateVoiceTrack': base,
        'CreateWordTiming': base,
        'ProbeMedia': base,
        'AssessImageSafety': assess_handler,
        'TransformSensitiveImage': transform_handler,
        'NormalizeMedia': normalize_handler,
        'PrepareAudioBed': base,
    }


__all__ = [
    'VoiceServices',
    'build_voice_services',
    'locate_media_file',
    'read_media_image',
    'verify_media_output',
    'voice_activity_deps',
    'voice_activity_handlers',
]
