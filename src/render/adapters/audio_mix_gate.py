"""PW-W2-FIX7: AUDIO_MIX_QUALITY warning gate measured on the pinned FFmpeg (CT-QC-001, PW-F2-01).

AudioMixGate is the callable given to OutputPipeline as warning_gates. For one output it reads the thresholds of the QualityPolicy (policy.thresholds['AUDIO_MIX_QUALITY']: target_lufs, tolerance_lu, max_true_peak_dbtp), checks the ffmpeg pin, measures integrated loudness and true peak, and returns exactly one audio_mix_result; a missing or non-numeric threshold gives no result. A pin that is refused or a measurement that fails gives not_evaluated (loudness_not_measured) and never raises. Out of target is a failed warning, never a hard failure. Nothing is changed in the output and no audio is processed.

coveredIds: CT-QC-001, PW-F2-01
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from pathlib import Path

from render.adapters.real_ffmpeg_renderer import FfmpegPinRejected, verify_ffmpeg_pin
from render.adapters.real_ffprobe_probe import LoudnessStats, measure_loudness
from render.adapters.real_output_inspector import audio_mix_result
from render.domain.package_contract import RenderPackageRecord
from render.domain.quality_report import GateName, GateResult, QualityPolicy

THRESHOLD_KEYS = ('target_lufs', 'tolerance_lu', 'max_true_peak_dbtp')


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value)


class AudioMixGate:
    def __init__(self, *, ffmpeg_path: str | Path, lock_path: str | Path, staging_root: str | Path, timeout_seconds: float) -> None:
        self._ffmpeg = Path(ffmpeg_path)
        self._lock = Path(lock_path)
        self._staging_root = Path(staging_root)
        self._timeout = float(timeout_seconds)

    def _media(self, output_ref: str) -> Path:
        path = Path(output_ref)
        if not path.is_file() and (self._staging_root / path).is_file():
            return self._staging_root / path
        return path

    def __call__(self, output_ref: str, package: RenderPackageRecord, policy: QualityPolicy) -> tuple[GateResult, ...]:
        entry = policy.thresholds.get(GateName.AUDIO_MIX_QUALITY.value)
        if not isinstance(entry, Mapping):
            return ()
        limits = {key: _number(entry.get(key)) for key in THRESHOLD_KEYS}
        if any(value is None for value in limits.values()):
            return ()
        try:
            verify_ffmpeg_pin(self._ffmpeg, self._lock)
        except FfmpegPinRejected:
            stats = LoudnessStats()
        else:
            stats = measure_loudness(self._ffmpeg, self._media(output_ref), timeout_seconds=self._timeout)
        return (audio_mix_result(
            stats, target_lufs=limits['target_lufs'], tolerance_lu=limits['tolerance_lu'], max_true_peak_dbtp=limits['max_true_peak_dbtp'],
            threshold_revision=policy.revision, evidence_ref=output_ref,
        ),)


__all__ = ['AudioMixGate']
