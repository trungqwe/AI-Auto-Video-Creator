"""Redaction sâu, SecretValue và quét canary (CT-SEC-003 điều 6, INV-012)."""
from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from typing import Any

from controlplane.infrastructure.security.redaction import redact_text

REDACTED = '[REDACTED]'
SENSITIVE_KEYS = (
    'password', 'secret', 'token', 'api_key', 'apikey', 'authorization', 'credential',
    'private_key', 'client_secret', 'refresh_token', 'access_token', 'session_uri', 'upload_session',
)


class SecretValue:
    """Bọc giá trị bí mật; mọi dạng render đều là [REDACTED], chỉ reveal() trả giá trị."""

    __slots__ = ('_value',)

    def __init__(self, value: Any) -> None:
        self._value = value

    def reveal(self) -> Any:
        return self._value

    def __repr__(self) -> str:
        return REDACTED

    def __str__(self) -> str:
        return REDACTED

    def __format__(self, format_spec: str) -> str:
        return REDACTED

    def __reduce__(self):
        raise TypeError('SecretValue không được pickle')

    def __reduce_ex__(self, protocol):
        raise TypeError('SecretValue không được pickle')

    def __copy__(self) -> 'SecretValue':
        return self

    def __deepcopy__(self, memo: dict) -> 'SecretValue':
        return self


_MAX_DEPTH = 32
_TOKEN_PATTERNS = (
    re.compile(r'(?<![A-Za-z0-9])sk-[A-Za-z0-9_\-]{8,}'),
    re.compile(r'AIza[0-9A-Za-z_\-]{35,}'),
    re.compile(r'eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]*'),
    re.compile(r'ya29\.[A-Za-z0-9_\-.]+'),
)
_URL_QUERY_SECRET = re.compile(r'(?i)([?&](?:token|key|upload_id|signature)=)[^&\s<>#\x22\x27]+')


def _redact_string(text: str) -> str:
    result = redact_text(text)
    for pattern in _TOKEN_PATTERNS:
        result = pattern.sub(REDACTED, result)
    return _URL_QUERY_SECRET.sub(lambda match: match.group(1) + REDACTED, result)


def _is_sensitive_key(key: Any) -> bool:
    if not isinstance(key, str):
        return False
    normalized = key.casefold().replace('-', '_').replace(' ', '_')
    return any(normalized == name or normalized.endswith('_' + name) for name in SENSITIVE_KEYS)


def _redact(value: Any, depth: int) -> Any:
    if depth > _MAX_DEPTH:
        raise ValueError('redaction depth exceeded')
    if isinstance(value, SecretValue):
        return REDACTED
    if isinstance(value, str):
        return _redact_string(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, Mapping):
        return {
            _redact(key, depth + 1): REDACTED
            if _is_sensitive_key(key) and item is not None
            else _redact(item, depth + 1)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item, depth + 1) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact(item, depth + 1) for item in value)
    if isinstance(value, frozenset):
        return frozenset(_redact(item, depth + 1) for item in value)
    if isinstance(value, set):
        return {_redact(item, depth + 1) for item in value}
    if isinstance(value, (bytes, bytearray)):
        return _redact_string(bytes(value).decode('utf-8', errors='replace'))
    return _redact_string(str(value))


def redact_value(value: Any) -> Any:
    try:
        return _redact(value, 0)
    except Exception:
        return REDACTED


def redact_exception(exc: BaseException) -> str:
    try:
        message = _redact_string(str(exc))
        name = type(exc).__name__
        return f'{name}: {message}' if message else name
    except Exception:
        return REDACTED


def _renderings(output: Any) -> list[str]:
    renderings: list[str] = []
    for render in (str, repr, lambda item: json.dumps(item, default=repr, ensure_ascii=False)):
        try:
            renderings.append(render(output))
        except Exception:
            continue
    return renderings


def find_canaries(canaries: Iterable[str], *outputs: Any) -> list[str]:
    if isinstance(canaries, str):
        canaries = (canaries,)
    haystacks = [text for output in outputs for text in _renderings(output)]
    found: list[str] = []
    for canary in canaries:
        if isinstance(canary, str) and canary and canary not in found:
            if any(canary in text for text in haystacks):
                found.append(canary)
    return found
