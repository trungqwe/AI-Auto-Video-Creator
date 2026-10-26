"""Measure a WAV duration from its own header and sample count with stdlib wave (PW-E2, CT-TTS-001). No estimate: duration is frames * 1000 // sample_rate after every frame the header declares was read; a corrupt or cut-off WAV is rejected."""
from __future__ import annotations

import io
import struct
import wave
from dataclasses import dataclass

ERROR_WAV_INVALID = 'wav_invalid'


class InvalidWavError(ValueError):
    def __init__(self, reason: str) -> None:
        self.code = ERROR_WAV_INVALID
        self.reason = reason
        super().__init__(f'{ERROR_WAV_INVALID}: {reason}')


@dataclass(frozen=True)
class WavInfo:
    frames: int
    sample_rate: int
    channels: int
    sample_width: int

    @property
    def samples(self) -> int:
        return self.frames * self.channels

    @property
    def duration_ms(self) -> int:
        return self.frames * 1000 // self.sample_rate


def read_wav_info(audio: bytes) -> WavInfo:
    if not isinstance(audio, bytes):
        raise TypeError('audio must be bytes')
    try:
        with wave.open(io.BytesIO(audio), 'rb') as wav:
            channels, width, rate, frames = wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes()
            if channels < 1 or width < 1 or rate < 1 or frames < 1:
                raise InvalidWavError('header_values')
            data = wav.readframes(frames)
    except InvalidWavError:
        raise
    except (wave.Error, EOFError, struct.error) as exc:
        raise InvalidWavError(type(exc).__name__) from None
    if len(data) != frames * channels * width:
        raise InvalidWavError('truncated_data')
    return WavInfo(frames, rate, channels, width)


def measure_wav_duration_ms(audio: bytes) -> int:
    return read_wav_info(audio).duration_ms


__all__ = ('InvalidWavError', 'WavInfo', 'measure_wav_duration_ms', 'read_wav_info')
