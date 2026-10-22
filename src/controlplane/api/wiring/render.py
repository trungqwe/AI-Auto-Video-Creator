from __future__ import annotations

"""ADAPT-WIRE: wiring cho phân hệ F (render).
Đấu nối RealFfmpegRenderer, RealFfprobeProbe và PostgresRenderUnitOfWork.
Không chạy ffmpeg và không kiểm pin lúc dựng."""

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import Any

from controlplane.api.wiring.production_profile import (
    PROFILE_PRODUCTION,
    WiringConfig,
)
from render.adapters.fake_renderer import FakeOutputStorage, FakeRenderer
from render.adapters.memory import InMemoryUnitOfWork
from render.adapters.real_ffmpeg_renderer import RealFfmpegRenderer
from render.adapters.real_ffprobe_probe import RealFfprobeProbe
from render.persistence.unit_of_work import PostgresRenderUnitOfWork


@dataclass(frozen=True)
class RenderServices:
    mode: str
    uow_factory: Callable[[], Any]
    renderer: Any
    probe: Any


def build_render_services(manager: Any, config: WiringConfig) -> RenderServices:
    if config.mode != PROFILE_PRODUCTION:
        return RenderServices(
            config.mode,
            InMemoryUnitOfWork,
            FakeRenderer(FakeOutputStorage(), output_ref='memory://render/output.mp4'),
            None,
        )

    profile, runtime = config.production_parts()
    renderer = RealFfmpegRenderer(
        lease=runtime.gpu_lease,
        ffmpeg_path=str(runtime.ffmpeg_path),
        lock_path=runtime.runtime_lock_path,
        timeout_seconds=profile.render.timeout_seconds,
    )
    probe = RealFfprobeProbe(
        ffprobe_path=str(runtime.ffprobe_path),
        timeout_seconds=profile.render.timeout_seconds,
    )
    uow_factory = partial(PostgresRenderUnitOfWork, manager, workspace_id=config.workspace_id)
    return RenderServices('production', uow_factory, renderer, probe)


__all__ = ['RenderServices', 'build_render_services']
