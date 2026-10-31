"""Shared parser for JSON objects returned by AI models (D-15-FIX2, R31).

Models often wrap a correct JSON object in a Markdown code fence or surround it with a sentence; every consumer of model output uses this one parser.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any


class ModelJsonError(ValueError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def _unfence(text: str) -> str:
    if not text.startswith('```'):
        return text
    lines = text.splitlines()[1:]
    if lines and lines[-1].strip().startswith('```'):
        lines = lines[:-1]
    return chr(10).join(lines).strip()


def parse_model_json_object(text: object, *, parse_constant: Callable[[str], Any] | None = None) -> dict[str, Any]:
    if not isinstance(text, str) or not text.strip():
        raise ModelJsonError('empty_output')
    body = _unfence(text.strip())
    try:
        data = json.loads(body, strict=False, parse_constant=parse_constant)
    except json.JSONDecodeError:
        start = body.find('{')
        end = body.rfind('}')
        if start < 0 or end < start:
            raise ModelJsonError('not_json') from None
        try:
            data = json.loads(body[start:end + 1], strict=False, parse_constant=parse_constant)
        except json.JSONDecodeError:
            raise ModelJsonError('not_json') from None
    if not isinstance(data, dict):
        raise ModelJsonError('not_a_json_object')
    return data
