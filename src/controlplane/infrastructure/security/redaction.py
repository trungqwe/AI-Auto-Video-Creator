"""Conservative redaction for diagnostics before storage or output."""

from __future__ import annotations

import re


_ASSIGNMENT = re.compile(
    r"(?i)\b(password|secret|access[_-]?token|refresh[_-]?token|api[_-]?key|credential)"
    r"(\s*[:=]\s*)([^\s,;]+)"
)
_BEARER = re.compile(r"(?i)\bBearer\s+[^\s,;]+")
_PRIVATE_KEY = re.compile(r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----", re.DOTALL)


def redact_text(value: str) -> str:
    text = _PRIVATE_KEY.sub("[REDACTED PRIVATE KEY]", value)
    text = _BEARER.sub("Bearer [REDACTED]", text)
    return _ASSIGNMENT.sub(lambda match: match.group(1) + match.group(2) + "[REDACTED]", text)
