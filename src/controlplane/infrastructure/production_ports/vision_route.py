"""PP-7: RouterVisionRoute, a VisionRoutePort that sends one image to 9Router (CT-AI-ROUTE-001, INV-012, QR-SEC-009).

The route posts an OpenAI-style chat/completions body to the approved endpoint only and returns choices[0].message.content. The key comes from credentials.acquire for the length of one call; it is never cached, logged or put into an exception. A redirect is not followed and no proxy is used. Every failure is a VisionRouteError with a fixed code, never a message built from the response or the key.
"""
from __future__ import annotations

import http.client
import json
import math
import re
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence

from controlplane.application.config_security.route_resolver import CREDENTIAL_METHOD
from controlplane.config.adapter import ApprovedEndpointRegistry

MAX_RESPONSE_BYTES = 1048576
MAX_CHAT_IMAGES = 4
COMPLETIONS_PATH = '/chat/completions'
_IMAGE_BASE64 = re.compile(r'[A-Za-z0-9+/]+={0,2}')
_MEDIA_TYPE = re.compile(r'image/[A-Za-z0-9][A-Za-z0-9.+-]*')
_BEARER_KEY = re.compile(r'[!-~]+')


class VisionRouteError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class VisionRouteTimeoutError(VisionRouteError, TimeoutError):
    pass


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _require_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a non-empty string')
    return value


def _http_code(status: int) -> str:
    if status in (401, 403):
        return 'unauthorized'
    if status == 429:
        return 'rate_limited'
    if status >= 500:
        return 'server_error'
    return 'http_error'


def _extract_content(raw: bytes) -> str:
    try:
        content = json.loads(raw.decode('utf-8'))['choices'][0]['message']['content']
    except (UnicodeDecodeError, ValueError, KeyError, IndexError, TypeError, RecursionError):
        raise VisionRouteError('bad_response') from None
    if not isinstance(content, str) or not content.strip():
        raise VisionRouteError('bad_response')
    return content


def _chat_image_parts(images: Sequence[tuple[str, str]]) -> list[dict]:
    if isinstance(images, (str, bytes, bytearray, Mapping)) or not isinstance(images, Sequence):
        raise ValueError('images must be a sequence of (image_base64, media_type) pairs')
    if len(images) > MAX_CHAT_IMAGES:
        raise ValueError(f'images must hold at most {MAX_CHAT_IMAGES} pairs')
    parts = []
    for pair in images:
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValueError('each image must be an (image_base64, media_type) pair')
        image_base64, media_type = pair
        if not isinstance(image_base64, str) or _IMAGE_BASE64.fullmatch(image_base64) is None:
            raise ValueError('image_base64 must be a base64 string')
        if not isinstance(media_type, str) or _MEDIA_TYPE.fullmatch(media_type) is None:
            raise ValueError('media_type must be an image media type')
        parts.append({'type': 'image_url', 'image_url': {'url': f'data:{media_type};base64,{image_base64}'}})
    return parts


class RouterVisionRoute:
    def __init__(self, endpoint: str, model_refs: Mapping[str, str], credentials: object, account_ref: str) -> None:
        registry = ApprovedEndpointRegistry.from_config([endpoint])
        if not isinstance(model_refs, Mapping) or not model_refs:
            raise ValueError('model_refs must be a non-empty mapping')
        if not callable(getattr(credentials, 'acquire', None)):
            raise ValueError('credentials must provide acquire')
        self._registry = registry
        self._endpoint = registry.validate(endpoint)
        self._model_refs = {
            _require_text(role, 'model_refs role'): _require_text(model_ref, 'model_refs model_ref')
            for role, model_ref in model_refs.items()
        }
        self._credentials = credentials
        self._account_ref = _require_text(account_ref, 'account_ref')
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirectHandler())

    @property
    def endpoint(self) -> str:
        return self._endpoint

    def invoke_vision(
        self,
        ai_role: str,
        instructions: str,
        image_base64: str,
        media_type: str,
        timeout_seconds: float,
    ) -> str:
        if not isinstance(ai_role, str) or ai_role not in self._model_refs:
            raise VisionRouteError('unknown_role')
        _require_text(instructions, 'instructions')
        if not isinstance(image_base64, str) or _IMAGE_BASE64.fullmatch(image_base64) is None:
            raise ValueError('image_base64 must be a base64 string')
        if not isinstance(media_type, str) or _MEDIA_TYPE.fullmatch(media_type) is None:
            raise ValueError('media_type must be an image media type')
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise ValueError('timeout_seconds must be a positive finite number')
        url = self._registry.validate(self._endpoint) + COMPLETIONS_PATH
        body = json.dumps({
            'model': self._model_refs[ai_role],
            'messages': [{
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': instructions},
                    {'type': 'image_url', 'image_url': {'url': f'data:{media_type};base64,{image_base64}'}},
                ],
            }],
        }).encode('utf-8')
        with self._credentials.acquire(CREDENTIAL_METHOD, self._account_ref) as key:
            if not isinstance(key, str) or _BEARER_KEY.fullmatch(key) is None:
                raise VisionRouteError('bad_credential')
            raw = self._post(url, body, key, float(timeout_seconds))
        return _extract_content(raw)

    def invoke_chat(
        self,
        ai_role: str,
        system: str,
        text: str,
        images: Sequence[tuple[str, str]] = (),
        *,
        timeout: float,
    ) -> str:
        if not isinstance(ai_role, str) or ai_role not in self._model_refs:
            raise VisionRouteError('unknown_role')
        _require_text(system, 'system')
        _require_text(text, 'text')
        parts = _chat_image_parts(images)
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout)
            or timeout <= 0
        ):
            raise ValueError('timeout must be a positive finite number')
        url = self._registry.validate(self._endpoint) + COMPLETIONS_PATH
        content = [{'type': 'text', 'text': text}, *parts] if parts else text
        body = json.dumps({
            'model': self._model_refs[ai_role],
            'messages': [
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': content},
            ],
        }).encode('utf-8')
        with self._credentials.acquire(CREDENTIAL_METHOD, self._account_ref) as key:
            if not isinstance(key, str) or _BEARER_KEY.fullmatch(key) is None:
                raise VisionRouteError('bad_credential')
            raw = self._post(url, body, key, float(timeout))
        return _extract_content(raw)

    def _post(self, url: str, body: bytes, key: str, timeout: float) -> bytes:
        request = urllib.request.Request(
            url,
            data=body,
            method='POST',
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Authorization': 'Bearer ' + key,
            },
        )
        try:
            with self._opener.open(request, timeout=timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            exc.close()
            raise VisionRouteError(_http_code(exc.code)) from None
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise VisionRouteTimeoutError('timeout') from None
            raise VisionRouteError('network_error') from None
        except TimeoutError:
            raise VisionRouteTimeoutError('timeout') from None
        except (OSError, http.client.HTTPException):
            raise VisionRouteError('network_error') from None
        except ValueError:
            raise VisionRouteError('bad_request') from None
        if len(raw) > MAX_RESPONSE_BYTES:
            raise VisionRouteError('bad_response')
        return raw

    def __repr__(self) -> str:
        return f'RouterVisionRoute(endpoint={self._endpoint!r}, account_ref={self._account_ref!r})'


__all__ = ['MAX_CHAT_IMAGES', 'MAX_RESPONSE_BYTES','RouterVisionRoute', 'VisionRouteError', 'VisionRouteTimeoutError']
