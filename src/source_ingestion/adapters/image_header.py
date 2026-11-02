"""Image size read from the first bytes of a JPEG, PNG or WebP file (ADAPT-A-FIX1; stdlib only).

read_image_size never raises: a damaged, truncated or unknown header and a zero side give None.
"""
from __future__ import annotations

_PNG_SIGNATURE = bytes.fromhex('89504e470d0a1a0a')
_JPEG_SOF = frozenset(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}


def _jpeg_size(data: bytes) -> tuple[int, int] | None:
    length = len(data)
    pos = 2
    while pos + 1 < length:
        if data[pos] != 0xFF:
            return None
        while pos < length and data[pos] == 0xFF:
            pos += 1
        if pos >= length:
            return None
        marker = data[pos]
        pos += 1
        if marker == 0x01 or 0xD0 <= marker <= 0xD8:
            continue
        if marker in (0xD9, 0xDA) or pos + 2 > length:
            return None
        segment = (data[pos] << 8) | data[pos + 1]
        if segment < 2:
            return None
        if marker in _JPEG_SOF:
            if pos + 7 > length:
                return None
            return (data[pos + 5] << 8) | data[pos + 6], (data[pos + 3] << 8) | data[pos + 4]
        pos += segment
    return None


def _png_size(data: bytes) -> tuple[int, int] | None:
    if len(data) < 24 or data[12:16] != b'IHDR':
        return None
    return int.from_bytes(data[16:20], 'big'), int.from_bytes(data[20:24], 'big')


def _webp_size(data: bytes) -> tuple[int, int] | None:
    kind = data[12:16]
    if kind == b'VP8 ' and len(data) >= 30 and data[23:26] == bytes.fromhex('9d012a'):
        return int.from_bytes(data[26:28], 'little') & 0x3FFF, int.from_bytes(data[28:30], 'little') & 0x3FFF
    if kind == b'VP8L' and len(data) >= 25 and data[20] == 0x2F:
        bits = int.from_bytes(data[21:25], 'little')
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if kind == b'VP8X' and len(data) >= 30:
        return int.from_bytes(data[24:27], 'little') + 1, int.from_bytes(data[27:30], 'little') + 1
    return None


def read_image_size(data: bytes) -> tuple[int, int] | None:
    """(width, height) from the header bytes, or None; never raises."""
    try:
        raw = data if isinstance(data, bytes) else bytes(data)
        if raw[:2] == bytes.fromhex('ffd8'):
            size = _jpeg_size(raw)
        elif raw[:8] == _PNG_SIGNATURE:
            size = _png_size(raw)
        elif raw[:4] == b'RIFF' and raw[8:12] == b'WEBP':
            size = _webp_size(raw)
        else:
            size = None
        if size is None or size[0] <= 0 or size[1] <= 0:
            return None
        return size
    except Exception:
        return None
