"""Real TtsEnginePort: local Kokoro ONNX speech synthesis (CT-TTS-001).

Weights stay outside the Git tree and their sha256 is checked against tools/launcher/prod/model-weights.lock.json before loading; nothing is downloaded and no network is used.

DQ-13: this adapter writes the WAV only as <voice root>/tmp/<sha256 of the WAV bytes>.wav; VoicePipeline names the final file voice-artifact-<sha256> through VoiceArtifactPlacer and the aligner opens that exact name.

SentencePauseKokoro uses the private _split_phonemes and _create_audio API of kokoro-onnx==0.4.9 (pinned in pyproject.toml); a model injected through model_factory replaces the whole model, including the sentence-join rule.

TTS-NUMBERS: for an English voice (language starting with 'en') the text given to the model is speakable_english(script text): espeak, behind phonemize(preserve_punctuation=True), splits '72,000' at the comma and reads 'seventy-two, zero zero zero'. Only the model input changes; ScriptText, usage_metrics['characters'], the aligner and the subtitles keep the digits of the script. The revision carries ';numbers=<SPOKEN_NUMBERS_REVISION>'.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import re
import threading
import time
import wave
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from voice.domain.spoken_numbers import SPOKEN_NUMBERS_REVISION, speakable_english
from voice.domain.tts_invocation import ProviderRouteDecision, TtsProviderError, TtsSynthesis
from voice.domain.voice_track import verify_script_binding
from voice.ports.script_text import ScriptText

MODEL_FILE = 'kokoro-v1.0.onnx'
VOICES_FILE = 'voices-v1.0.bin'
WEIGHTS_GROUP = 'kokoro-onnx'
TEMP_DIR_NAME = 'tmp'
ERROR_WEIGHTS_UNPINNED = 'weights_unpinned'
ERROR_WEIGHTS_MISSING = 'weights_missing'
ERROR_WEIGHTS_SHA256_MISMATCH = 'weights_sha256_mismatch'
ERROR_WEIGHTS_IN_GIT_TREE = 'weights_in_git_tree'
ERROR_STAGING_MISSING = 'staging_missing'
ERROR_SAMPLE_RATE_MISMATCH = 'sample_rate_mismatch'
ERROR_EMPTY_AUDIO = 'empty_audio'
ERROR_RUNTIME = 'tts_runtime_error'
ERROR_SPEED_OUT_OF_RANGE = 'speed_out_of_range'
_SHA256_RE = re.compile(r'[0-9a-f]{64}')
ARTIFACT_NAME_RE = re.compile(r'voice-artifact-([0-9a-f]{64})')


@dataclass(frozen=True, kw_only=True)
class KokoroConfig:
    """Voice, speed, language and sample rate come from configuration, not from the request."""

    weights_dir: Path
    lock_path: Path
    staging_dir: Path
    voice: str
    speed: float
    language: str
    sample_rate: int

    def __post_init__(self) -> None:
        for name in ('weights_dir', 'lock_path', 'staging_dir'):
            value = getattr(self, name)
            if not isinstance(value, Path) or not value.is_absolute():
                raise ValueError(f'{name} must be an absolute Path')
        for name in ('voice', 'language'):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f'{name} must be a non-empty string')
        if isinstance(self.speed, bool) or not isinstance(self.speed, (int, float)) or not 0.5 <= self.speed <= 2.0:
            raise ValueError('speed must be a number in [0.5, 2.0]')
        if isinstance(self.sample_rate, bool) or not isinstance(self.sample_rate, int) or self.sample_rate <= 0:
            raise ValueError('sample_rate must be a positive integer')


def _fail(code: str, message: str, *, known_secrets: tuple[str, ...] = ()) -> TtsProviderError:
    return TtsProviderError(code, message, retryable=False, known_secrets=known_secrets)


def _file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open('rb') as handle:
        while chunk := handle.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


def _inside_git_tree(path: Path) -> bool:
    resolved = path.resolve()
    return any((candidate / '.git').exists() for candidate in (resolved, *resolved.parents))


def _pinned_hashes(lock_path: Path) -> dict[str, str]:
    """Return the pinned sha256 of the two Kokoro files; a missing, unreadable, null or BLOCKED pin is weights_unpinned."""
    try:
        entries = json.loads(lock_path.read_text(encoding='utf-8'))['files']
        found = {entry['name']: entry for entry in entries if isinstance(entry, dict) and entry.get('group') == WEIGHTS_GROUP}
    except (OSError, ValueError, KeyError, TypeError):
        raise _fail(ERROR_WEIGHTS_UNPINNED, 'weights lock unreadable') from None
    pins: dict[str, str] = {}
    for name in (MODEL_FILE, VOICES_FILE):
        entry = found.get(name, {})
        sha = entry.get('sha256')
        if not isinstance(sha, str) or not _SHA256_RE.fullmatch(sha) or entry.get('status') == 'BLOCKED':
            raise _fail(ERROR_WEIGHTS_UNPINNED, f'sha256 not pinned for {name}')
        pins[name] = sha
    return pins


def _to_pcm16(samples: object) -> bytes:
    """Convert float samples in [-1, 1] to little-endian 16-bit PCM; empty or non-finite input gives b''."""
    import numpy as np

    data = np.asarray(samples, dtype=np.float32).reshape(-1)
    if data.size == 0 or not np.isfinite(data).all():
        return b''
    return (np.clip(data, -1.0, 1.0) * 32767.0).astype('<i2').tobytes()


def _default_factory(model_path: str, voices_path: str) -> object:
    from kokoro_onnx import Kokoro

    return SentencePauseKokoro(Kokoro(model_path, voices_path))


class SentencePauseKokoro:
    """Same loop as kokoro_onnx.Kokoro.create 0.4.9, except the model tail is kept at a sentence join: the trailing silence of a non-final batch that ends with . ! or ? is not trimmed, so the join keeps the pause the model generated."""

    def __init__(self, kokoro: object) -> None:
        self._kokoro = kokoro

    def create(self, text: str, voice: str, speed: float, lang: str) -> tuple[object, int]:
        import numpy as np
        from kokoro_onnx.trim import trim

        kokoro = self._kokoro
        if voice not in kokoro.voices:
            raise ValueError(f'voice {voice} not found in available voices')
        style = kokoro.get_voice_style(voice)
        batches = kokoro._split_phonemes(kokoro.tokenizer.phonemize(text, lang))
        pieces = []
        rate = 0
        for index, batch in enumerate(batches):
            audio, rate = kokoro._create_audio(batch, style, speed)
            start, end = (int(value) for value in trim(audio)[1])
            tail = batch.rstrip()[-1:]
            keep_tail = index < len(batches) - 1 and tail in ('.', '!', '?')
            pieces.append(audio[start:] if keep_tail else audio[start:end])
        return np.concatenate(pieces), rate


def _english(language: str) -> bool:
    return language.casefold().startswith('en')


def _library_version() -> str:
    try:
        return importlib.metadata.version('kokoro-onnx')
    except importlib.metadata.PackageNotFoundError:
        return 'unknown'


class RealKokoroTts:
    """TtsEnginePort over a local kokoro_onnx model; weights are verified once, then the model is loaded once and reused."""

    def __init__(
        self,
        config: KokoroConfig,
        *,
        model_factory: Callable[[str, str], object] | None = None,
        known_secrets: tuple[str, ...] = (),
    ) -> None:
        if not isinstance(config, KokoroConfig):
            raise TypeError('config must be KokoroConfig')
        if isinstance(known_secrets, str):
            raise TypeError('known_secrets must not be str')
        self._config = config
        self._factory = model_factory or _default_factory
        self._known_secrets = (*known_secrets, str(config.weights_dir), str(config.staging_dir))
        self._model: object | None = None
        self._revision = ''
        self._load_lock = threading.Lock()

    def _runtime_error(self, exc: Exception) -> TtsProviderError:
        return _fail(ERROR_RUNTIME, f'{type(exc).__name__}: {exc}', known_secrets=self._known_secrets)

    def _verify_weights(self) -> dict[str, str]:
        config = self._config
        if _inside_git_tree(config.weights_dir):
            raise _fail(ERROR_WEIGHTS_IN_GIT_TREE, 'weights directory is inside a Git tree')
        pins = _pinned_hashes(config.lock_path)
        for name, expected in pins.items():
            path = config.weights_dir / name
            if not path.is_file():
                raise _fail(ERROR_WEIGHTS_MISSING, f'weights file missing: {name}')
            try:
                actual = _file_sha256(path)
            except OSError:
                raise _fail(ERROR_WEIGHTS_MISSING, f'weights file unreadable: {name}') from None
            if actual != expected:
                raise _fail(ERROR_WEIGHTS_SHA256_MISMATCH, f'sha256 mismatch for {name}')
        return pins

    def _load(self) -> object:
        if self._model is None:
            with self._load_lock:
                if self._model is None:
                    pins = self._verify_weights()
                    directory = self._config.weights_dir
                    try:
                        model = self._factory(str(directory / MODEL_FILE), str(directory / VOICES_FILE))
                    except Exception as exc:
                        raise self._runtime_error(exc) from None
                    join_tag = ';sentence_joins=model-tail' if isinstance(model, SentencePauseKokoro) else ''
                    numbers_tag = f';numbers={SPOKEN_NUMBERS_REVISION}' if _english(self._config.language) else ''
                    self._revision = f'kokoro-onnx=={_library_version()};model={pins[MODEL_FILE]};voices={pins[VOICES_FILE]};voice={self._config.voice}{numbers_tag}{join_tag}'
                    self._model = model
        return self._model

    def _write_wav(self, pcm: bytes) -> bytes:
        temp_dir = self._config.staging_dir / TEMP_DIR_NAME
        part = temp_dir / f'{hashlib.sha256(pcm).hexdigest()[:32]}.part'
        try:
            with wave.open(str(part), 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(self._config.sample_rate)
                wav.writeframes(pcm)
            wav_bytes = part.read_bytes()
            part.replace(temp_dir / f'{hashlib.sha256(wav_bytes).hexdigest()}.wav')
        finally:
            part.unlink(missing_ok=True)
        return wav_bytes

    def synthesize(self, decision: ProviderRouteDecision, script_text: ScriptText, request: Mapping[str, object], *, speed_scale: float = 1.0) -> TtsSynthesis:
        if not isinstance(decision, ProviderRouteDecision):
            raise TypeError('decision must be ProviderRouteDecision')
        if not isinstance(script_text, ScriptText):
            raise TypeError('script_text must be ScriptText')
        if not isinstance(request, Mapping):
            raise TypeError('request must be Mapping')
        verify_script_binding(request, script_text)
        if isinstance(speed_scale, bool) or not isinstance(speed_scale, (int, float)) or not math.isfinite(speed_scale) or speed_scale <= 0:
            raise ValueError('speed_scale must be a finite number > 0')
        effective = round(self._config.speed * speed_scale, 4)
        if not 0.5 <= effective <= 2.0:
            raise _fail(ERROR_SPEED_OUT_OF_RANGE, f'effective speed {effective} is outside [0.5, 2.0]')
        config = self._config
        if not config.staging_dir.is_dir():
            raise _fail(ERROR_STAGING_MISSING, 'staging directory missing')
        try:
            (config.staging_dir / TEMP_DIR_NAME).mkdir(exist_ok=True)
        except OSError:
            raise _fail(ERROR_STAGING_MISSING, 'staging temp directory unavailable') from None
        model = self._load()
        spoken = speakable_english(script_text.text) if _english(config.language) else script_text.text
        started = time.perf_counter()
        try:
            samples, rate = model.create(spoken, voice=config.voice, speed=effective, lang=config.language)
            if rate != config.sample_rate:
                raise _fail(ERROR_SAMPLE_RATE_MISMATCH, 'model sample rate differs from configured sample rate')
            pcm = _to_pcm16(samples)
            if not pcm:
                raise _fail(ERROR_EMPTY_AUDIO, 'model returned no usable audio')
            wav_bytes = self._write_wav(pcm)
        except TtsProviderError:
            raise
        except Exception as exc:
            raise self._runtime_error(exc) from None
        return TtsSynthesis(
            audio_bytes=wav_bytes,
            voice_revision=self._revision,
            usage_metrics={
                'characters': len(script_text.text),
                'audio_ms': len(pcm) // 2 * 1000 // config.sample_rate,
                'speed': effective,
                'speed_scale': speed_scale,
            },
            latency_ms=int(round((time.perf_counter() - started) * 1000)),
        )


class VoiceArtifactPlacer:
    """DQ-13: the single place that names a voice WAV. VoicePipeline calls it with voice-artifact-<sha256> and the WAV bytes before it commits."""

    def __init__(self, voice_root: Path) -> None:
        if not isinstance(voice_root, Path) or not voice_root.is_absolute():
            raise ValueError('voice_root must be an absolute Path')
        self._root = voice_root

    def __call__(self, artifact_ref: str, audio_bytes: bytes) -> Path:
        match = ARTIFACT_NAME_RE.fullmatch(artifact_ref) if isinstance(artifact_ref, str) else None
        if match is None or not isinstance(audio_bytes, bytes) or hashlib.sha256(audio_bytes).hexdigest() != match.group(1):
            raise ValueError('artifact_ref must be voice-artifact-<sha256 of the WAV bytes>')
        digest = match.group(1)
        final = self._root / artifact_ref
        if final.is_file() and _file_sha256(final) == digest:
            return final
        temp_dir = self._root / TEMP_DIR_NAME
        temp_dir.mkdir(exist_ok=True)
        source = temp_dir / f'{digest}.wav'
        if source.is_file() and _file_sha256(source) == digest:
            source.replace(final)
            return final
        part = temp_dir / f'{digest}.placing'
        try:
            part.write_bytes(audio_bytes)
            part.replace(final)
        finally:
            part.unlink(missing_ok=True)
        return final


__all__ = ('KokoroConfig', 'RealKokoroTts', 'VoiceArtifactPlacer')
