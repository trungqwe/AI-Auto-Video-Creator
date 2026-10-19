"""In-memory fake TTS route and engine adapters for testing (CT-AI-ROUTE-001, CT-TTS-001)."""
from __future__ import annotations

import io
import wave
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from voice.domain.tts_invocation import (
    ERROR_RATE_LIMIT,
    ERROR_TIMEOUT,
    ProviderRouteDecision,
    RouteContractViolation,
    TtsProviderError,
    TtsSynthesis,
    UsageMetrics,
    validate_provider_route_request,
)
from voice.domain.voice_track import verify_script_binding
from voice.ports.script_text import ScriptText


class UnknownReservation(LookupError):
    pass


@dataclass(frozen=True)
class FakeFailure:
    code: str
    message: str
    retryable: bool


def fake_timeout(message: str = 'upstream timeout') -> FakeFailure:
    return FakeFailure(ERROR_TIMEOUT, message, True)


def fake_rate_limit(message: str = 'rate limit exceeded') -> FakeFailure:
    return FakeFailure(ERROR_RATE_LIMIT, message, True)


def _silent_wav(duration_ms: int, sample_rate: int) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(bytes(2 * (sample_rate * duration_ms // 1000)))
    return buffer.getvalue()


class FakeVoiceRoute:
    def __init__(
        self,
        *,
        route_revision: str = 'fake-route-v1',
        provider_ref: str = 'fake-tts-provider',
        model_ref: str = 'fake-tts-model',
        account_ref: str = 'fake-account',
        project_ref: str | None = None,
        estimated_cost_class: str = 'free',
    ) -> None:
        self.route_revision = route_revision
        self.provider_ref = provider_ref
        self.model_ref = model_ref
        self.account_ref = account_ref
        self.project_ref = project_ref
        self.estimated_cost_class = estimated_cost_class
        self.resolve_calls = 0
        self._reservations: dict[str, str] = {}

    def resolve(self, request: Mapping[str, object]) -> ProviderRouteDecision:
        self.resolve_calls += 1
        issues = validate_provider_route_request(request)
        if issues:
            raise RouteContractViolation('ProviderRouteRequest', issues)
        reservation_ref = f'fake-tts-reservation-{id(self)}-{self.resolve_calls}'
        decision = ProviderRouteDecision(
            provider_ref=self.provider_ref,
            model_ref=self.model_ref,
            account_ref=self.account_ref,
            route_revision=self.route_revision,
            project_ref=self.project_ref,
            estimated_cost_class=self.estimated_cost_class,
            rationale_codes=('FAKE_ROUTE',),
            fallback_order=tuple(request['allowed_fallbacks']),
            capacity_reservation_ref=reservation_ref,
            credential_acquisition_method='secret_broker_handle',
        )
        self._reservations[reservation_ref] = str(request['ai_role'])
        return decision

    def role_for_reservation(self, reservation_ref: str) -> str:
        if reservation_ref not in self._reservations:
            raise UnknownReservation(reservation_ref)
        return self._reservations[reservation_ref]


class FakeTtsEngine:
    def __init__(
        self,
        route: object,
        *,
        scripts: Mapping[str, Sequence] | None = None,
        voice_revision: str = 'fake-voice-v1',
        duration_ms: int = 1000,
        sample_rate: int = 16000,
        latency_ms: int = 0,
        known_secrets: object = (),
    ) -> None:
        if not isinstance(route, FakeVoiceRoute):
            raise TypeError('route must be FakeVoiceRoute')
        if isinstance(known_secrets, str):
            raise TypeError('known_secrets must not be str')
        if not isinstance(duration_ms, int) or isinstance(duration_ms, bool) or duration_ms <= 0:
            raise ValueError('duration_ms must be positive integer')
        if not isinstance(sample_rate, int) or isinstance(sample_rate, bool) or sample_rate <= 0:
            raise ValueError('sample_rate must be positive integer')
        if not isinstance(voice_revision, str) or not voice_revision:
            raise ValueError('voice_revision must be non-empty string')
        if not isinstance(latency_ms, int) or isinstance(latency_ms, bool) or latency_ms < 0:
            raise ValueError('latency_ms must be non-negative integer')
        self._route = route
        self._voice_revision = voice_revision
        self._duration_ms = duration_ms
        self._sample_rate = sample_rate
        self._latency_ms = latency_ms
        self._known_secrets = tuple(known_secrets)
        self.synthesize_calls = 0
        self.calls_by_provider: dict[str, int] = {}
        self._scripts: dict[str, tuple] = {}
        if scripts is not None:
            if not isinstance(scripts, Mapping):
                raise ValueError('scripts must be a Mapping')
            for k, seq in scripts.items():
                if not isinstance(k, str) or not isinstance(seq, Sequence) or isinstance(seq, (str, bytes)) or len(seq) == 0:
                    raise ValueError('each script sequence must be non-empty sequence')
                for item in seq:
                    if item != 'ok' and not isinstance(item, FakeFailure):
                        raise ValueError('script item must be ok or FakeFailure')
                self._scripts[k] = tuple(seq)

    def synthesize(
        self,
        decision: ProviderRouteDecision,
        script_text: ScriptText,
        request: Mapping[str, object],
    ) -> TtsSynthesis:
        if not isinstance(decision, ProviderRouteDecision):
            raise TypeError('decision must be ProviderRouteDecision')
        if not isinstance(script_text, ScriptText):
            raise TypeError('script_text must be ScriptText')
        if not isinstance(request, Mapping):
            raise TypeError('request must be Mapping')
        verify_script_binding(request, script_text)
        self._route.role_for_reservation(decision.capacity_reservation_ref)
        self.synthesize_calls += 1
        self.calls_by_provider[decision.provider_ref] = self.calls_by_provider.get(decision.provider_ref, 0) + 1
        seq = self._scripts.get(decision.provider_ref)
        if seq is None:
            outcome = 'ok'
        else:
            idx = min(self.calls_by_provider[decision.provider_ref] - 1, len(seq) - 1)
            outcome = seq[idx]
        if isinstance(outcome, FakeFailure):
            raise TtsProviderError(
                outcome.code,
                outcome.message,
                retryable=outcome.retryable,
                known_secrets=self._known_secrets,
            )
        wav = _silent_wav(self._duration_ms, self._sample_rate)
        return TtsSynthesis(
            audio_bytes=wav,
            voice_revision=self._voice_revision,
            usage_metrics=UsageMetrics({'characters': len(script_text.text)}),
            latency_ms=self._latency_ms,
        )
