"""E-16-FIX3: pure planning and writing of trailing digital silence for a slightly short re-read take.

Safety net only: the root cause is the word-based script length estimate (D-08-FIX1).
"""

from __future__ import annotations

import struct

TAIL_PAD_MAX_MS = 1500
TAIL_PAD_MARGIN_MS = 100


def plan_tail_pad(actual_duration_ms: int, policy_range: tuple[int, int]) -> int | None:
    """Silence to append in ms, or None when the take is not short or is short by more than the cap."""
    shortfall = policy_range[0] - actual_duration_ms
    if shortfall <= 0 or shortfall > TAIL_PAD_MAX_MS:
        return None
    return min(TAIL_PAD_MAX_MS, shortfall + TAIL_PAD_MARGIN_MS)


def pad_wav_tail(wav_bytes: bytes, pad_ms: int) -> bytes:
    """Append pad_ms of zero samples to a PCM WAV whose data chunk is last; rewrite the RIFF and data sizes."""
    if not 0 < pad_ms <= TAIL_PAD_MAX_MS:
        raise ValueError('pad_ms_out_of_range')
    if len(wav_bytes) < 12 or wav_bytes[0:4] != b'RIFF' or wav_bytes[8:12] != b'WAVE':
        raise ValueError('not_a_wav')
    fmt: tuple[int, int, int] | None = None
    offset = 12
    while offset + 8 <= len(wav_bytes):
        chunk_id = wav_bytes[offset:offset + 4]
        size = struct.unpack_from('<I', wav_bytes, offset + 4)[0]
        body = offset + 8
        if chunk_id == b'fmt ':
            if size < 16 or body + 16 > len(wav_bytes):
                raise ValueError('bad_fmt_chunk')
            audio_format, _channels, rate, _byte_rate, block_align, _bits = struct.unpack_from('<HHIIHH', wav_bytes, body)
            if audio_format != 1:
                raise ValueError('not_pcm')
            fmt = (rate, block_align, 0)
        elif chunk_id == b'data':
            if fmt is None:
                raise ValueError('data_before_fmt')
            if body + size != len(wav_bytes):
                raise ValueError('data_not_last')
            rate, block_align, _ = fmt
            extra = block_align * (rate * pad_ms // 1000)
            header = bytearray(wav_bytes[:body])
            struct.pack_into('<I', header, 4, len(wav_bytes) - 8 + extra)
            struct.pack_into('<I', header, offset + 4, size + extra)
            return bytes(header) + wav_bytes[body:] + bytes(extra)
        offset = body + size + (size & 1)
    raise ValueError('no_data_chunk')
