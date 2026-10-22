from __future__ import annotations

"""ADAPT-WIRE: wiring cho phân hệ E (voice).
Đấu nối RealKokoroTts, RealWhisperAligner, RealFfmpegMediaTool, LlmImageSafetyDetector và PostgresVoiceUnitOfWork.
Không nạp mô hình hay tải trọng số lúc dựng."""

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
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
from voice.adapters.real_ffmpeg_media_tool import RealFfmpegMediaTool
from voice.adapters.real_kokoro_tts import KokoroConfig, RealKokoroTts
from voice.adapters.real_llm_image_safety import LlmImageSafetyDetector
from voice.adapters.real_whisper_aligner import (
    RealWhisperAligner,
    WhisperAlignerConfig,
)
from voice.domain.processing import ArtifactRef
from voice.domain.timing_coverage import TokenizationPolicy
from voice.persistence.unit_of_work import PostgresVoiceUnitOfWork

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
            resolve_audio=lambda ref: resolve_under_root(voice_root, ref),
            tokenization_policy=policy,
            max_unmatched_word_ratio=al.max_unmatched_word_ratio,
            language=al.language,
            device=al.device,
            compute_type=al.compute_type,
        )
    )
    media_tool = RealFfmpegMediaTool(
        runtime.ffmpeg_path,
        runtime.runtime_lock_path,
        lambda ref: resolve_under_root(media_root, ref),
        lambda ref, ext: resolve_under_root(media_root, ref.replace(':', '_') + '.' + ext),
    )

    def detector_factory(artifact_ref: ArtifactRef) -> LlmImageSafetyDetector:
        def read_image(ref: str) -> tuple[bytes, str]:
            path = resolve_under_root(media_root, ref)
            suf = path.suffix.lower()
            if suf not in _MEDIA_TYPES:
                raise ValueError('UNSUPPORTED_IMAGE_TYPE')
            return (path.read_bytes(), _MEDIA_TYPES[suf])

        return LlmImageSafetyDetector(
            runtime.vision_route,
            artifact_ref,
            read_image,
            categories=im.categories,
            timeout_seconds=im.vision_timeout_seconds,
        )

    uow_factory = partial(PostgresVoiceUnitOfWork, manager, workspace_id=config.workspace_id)
    return VoiceServices('production', uow_factory, tts, aligner, media_tool, detector_factory)


__all__ = ['VoiceServices', 'build_voice_services']
