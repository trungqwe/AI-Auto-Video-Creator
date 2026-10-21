"""Vision LLM image safety detector via route J (ai_role image_safety).

Fail-closed implementation for ADAPT-E-MEDIA, CT-PROC-005, and plan.md 7.3.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import time
from collections.abc import Callable, Mapping
from typing import Protocol

from voice.adapters.real_ffmpeg_media_tool import format_mask_ref
from voice.domain.image_safety import DetectionStatus, ImageDetection
from voice.domain.image_transform import TransformRegion
from voice.domain.processing import ArtifactRef

AI_ROLE = 'image_safety'
DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_CATEGORIES = ('minor_child', 'nudity_sexual', 'graphic_violence', 'weapon', 'hate_symbol')
INSTRUCTIONS = (
    'Classify the image for safety. Answer with one JSON object only, no markdown: '
    '{"confidence": number 0..1, "detections": [{"category": one of the allowed categories, '
    '"confidence": number 0..1, "region": null or {"x": number, "y": number, "width": number, "height": number}}]}. '
    'Region is normalized to 0..1 of the image. Empty detections when nothing sensitive.'
)


class VisionRoutePort(Protocol):
    def invoke_vision(
        self,
        ai_role: str,
        instructions: str,
        image_base64: str,
        media_type: str,
        timeout_seconds: float,
    ) -> str | Mapping[str, object]:
        ...


class ImageSafetyDetectionError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ImageSafetyDetectionError('wrong_type')
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ImageSafetyDetectionError('wrong_type')
    return number


def _reject_constant(val: str) -> float:
    raise ImageSafetyDetectionError('wrong_type')


def parse_vision_output(raw: object, categories: tuple[str, ...]) -> tuple[ImageDetection, tuple[TransformRegion, ...]]:
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith('```'):
            lines = text.splitlines()
            if len(lines) >= 2 and lines[-1].strip().startswith('```'):
                lines = lines[1:-1]
            elif len(lines) >= 1:
                lines = lines[1:]
            text = '\n'.join(lines).strip()
        try:
            data = json.loads(text, parse_constant=_reject_constant)
        except ImageSafetyDetectionError:
            raise
        except (ValueError, TypeError):
            raise ImageSafetyDetectionError('bad_json') from None
    elif isinstance(raw, Mapping):
        data = dict(raw)
    else:
        raise ImageSafetyDetectionError('wrong_type')

    if not isinstance(data, dict):
        raise ImageSafetyDetectionError('wrong_type')
    if 'confidence' not in data or 'detections' not in data:
        raise ImageSafetyDetectionError('wrong_type')

    overall_confidence = _number(data['confidence'])
    detections_list = data['detections']
    if not isinstance(detections_list, list):
        raise ImageSafetyDetectionError('wrong_type')

    found_categories: set[str] = set()
    detection_confidences: list[float] = []
    regions_out: list[TransformRegion] = []

    for item in detections_list:
        if not isinstance(item, dict):
            raise ImageSafetyDetectionError('wrong_type')
        if 'category' not in item or 'confidence' not in item:
            raise ImageSafetyDetectionError('wrong_type')
        category = item['category']
        if not isinstance(category, str) or category not in categories:
            raise ImageSafetyDetectionError('unknown_category')
        confidence = _number(item['confidence'])
        found_categories.add(category)
        detection_confidences.append(confidence)

        region = item.get('region')
        if region is not None:
            if not isinstance(region, dict):
                raise ImageSafetyDetectionError('wrong_type')
            try:
                x = _number(region.get('x'))
                y = _number(region.get('y'))
                w = _number(region.get('width'))
                h = _number(region.get('height'))
                mask_ref = format_mask_ref(x, y, w, h)
            except (ImageSafetyDetectionError, ValueError):
                raise ImageSafetyDetectionError('invalid_region') from None
            regions_out.append(TransformRegion(category, confidence, mask_ref))

    final_conf = max(detection_confidences) if detection_confidences else overall_confidence
    detection = ImageDetection(
        status=DetectionStatus.COMPLETED,
        categories=tuple(sorted(found_categories)),
        confidence=final_conf,
    )
    return detection, tuple(regions_out)


class LlmImageSafetyDetector:
    """Callable detector matching assess_image_safety protocol."""

    def __init__(
        self,
        route: VisionRoutePort,
        artifact_ref: ArtifactRef,
        read_image: Callable[[str], tuple[bytes, str]],
        *,
        categories: tuple[str, ...] = DEFAULT_CATEGORIES,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not isinstance(artifact_ref, ArtifactRef):
            raise ValueError('artifact_ref must be ArtifactRef')
        if not callable(read_image) or not callable(clock):
            raise ValueError('read_image and clock must be callable')
        if not isinstance(categories, tuple) or not categories or not all(isinstance(c, str) and c for c in categories):
            raise ValueError('categories must be non-empty tuple of str')
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or timeout_seconds <= 0:
            raise ValueError('timeout_seconds must be positive number')

        self._route = route
        self._artifact_ref = artifact_ref
        self._read_image = read_image
        self._categories = categories
        self._timeout = float(timeout_seconds)
        self._clock = clock
        self.regions: tuple[TransformRegion, ...] = ()
        self.failure_code: str | None = None

    def __call__(self) -> ImageDetection:
        self.regions = ()
        self.failure_code = None
        try:
            data, media_type = self._read_image(self._artifact_ref.ref)
            if not isinstance(data, (bytes, bytearray)) or len(data) == 0:
                raise ImageSafetyDetectionError('bad_image')
            if not isinstance(media_type, str) or not media_type.startswith('image/'):
                raise ImageSafetyDetectionError('bad_image')
            if hashlib.sha256(data).hexdigest() != self._artifact_ref.content_sha256:
                raise ImageSafetyDetectionError('image_sha256_mismatch')

            started = self._clock()
            prompt = f"{INSTRUCTIONS} Allowed categories: {', '.join(self._categories)}"
            raw = self._route.invoke_vision(
                AI_ROLE,
                prompt,
                base64.b64encode(data).decode('ascii'),
                media_type,
                self._timeout,
            )
            if self._clock() - started > self._timeout:
                raise ImageSafetyDetectionError('route_timeout')

            detection, regions = parse_vision_output(raw, self._categories)
            self.regions = regions
            return detection
        except ImageSafetyDetectionError as exc:
            self.failure_code = exc.code
        except TimeoutError:
            self.failure_code = 'route_timeout'
        except Exception:
            self.failure_code = 'detector_error'

        return ImageDetection(status=DetectionStatus.FAILED)


__all__ = (
    'AI_ROLE',
    'DEFAULT_CATEGORIES',
    'DEFAULT_TIMEOUT_SECONDS',
    'ImageSafetyDetectionError',
    'LlmImageSafetyDetector',
    'VisionRoutePort',
    'parse_vision_output',
)