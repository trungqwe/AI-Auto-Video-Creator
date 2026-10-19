"""TTS ports: route resolution through J and speech synthesis (CT-AI-ROUTE-001, CT-AI-ROUTE-002, CT-TTS-001).

Pure declarations: no I/O. E never holds secrets; J returns refs and the real adapter acquires credentials through J secret broker (CONV-E-11).
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from voice.domain.tts_invocation import ProviderRouteDecision, TtsSynthesis
from voice.ports.script_text import ScriptText


@runtime_checkable
class VoiceRoutePort(Protocol):
    def resolve(self, request: Mapping[str, object]) -> ProviderRouteDecision:
        """Resolve ProviderRouteRequest (binding j-provider-route) to decision with refs only; raise RouteContractViolation if request violates binding."""
        ...


@runtime_checkable
class TtsEnginePort(Protocol):
    def synthesize(self, decision: ProviderRouteDecision, script_text: ScriptText, request: Mapping[str, object]) -> TtsSynthesis:
        """Synthesize speech from script text and VoiceTrackRequest; provider errors are TtsProviderError with retryable and redacted message."""
        ...


__all__ = ('TtsEnginePort', 'VoiceRoutePort')
