"""PW-G4: CapabilityReader builds the desktop_production capability view from injected probes (CT-ORC-007, CT-WF-007).

Synchronous: the workflow wiring calls it through to_thread. Fail-closed: a probe that raises or returns a non-bool gives unknown, never available.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping

CAPABILITY_KEY = 'desktop_production'
PROBE_NAMES = ('app_session_active', 'ffmpeg_pinned', 'gpu_lease_ready')
AVAILABLE = 'available'
DEGRADED = 'degraded'
UNAVAILABLE = 'unavailable'
UNKNOWN = 'unknown'


class CapabilityReader:
    def __init__(self, probes: Mapping[str, Callable[[], bool]]) -> None:
        if not isinstance(probes, Mapping) or set(probes) != set(PROBE_NAMES):
            raise ValueError('probes must be exactly ' + ', '.join(PROBE_NAMES))
        for name in PROBE_NAMES:
            if not callable(probes[name]):
                raise TypeError(name + ' probe must be callable')
        self._probes = {name: probes[name] for name in PROBE_NAMES}

    def __call__(self) -> dict[str, dict[str, str]]:
        return {CAPABILITY_KEY: {'status': self._status()}}

    def _status(self) -> str:
        results: dict[str, bool] = {}
        for name in PROBE_NAMES:
            try:
                value = self._probes[name]()
            except Exception:
                return UNKNOWN
            if not isinstance(value, bool):
                return UNKNOWN
            results[name] = value
        if not (results['app_session_active'] and results['ffmpeg_pinned']):
            return UNAVAILABLE
        return AVAILABLE if results['gpu_lease_ready'] else DEGRADED


__all__ = ['AVAILABLE', 'CAPABILITY_KEY', 'DEGRADED', 'CapabilityReader', 'PROBE_NAMES', 'UNAVAILABLE', 'UNKNOWN']
