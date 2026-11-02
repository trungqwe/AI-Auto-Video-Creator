"""Real image fetch and staging for source ingestion (ADAPT-A; A-RULE-013, CT-MED-001).

Every image is loaded through SecureFetcher with the image FetchPolicy, so the SSRF policy runs on
every hop and the size limit applies while the body streams. A loaded image needs a readable header and a short side of at least 360 px (read from the first bytes, never from Content-Type); it is then hashed with SHA-256,
written under the configured staging root and handed to C as a DiscoveryObservation. A rejected or
failed image is returned as a ProblemDetail and never raised.
"""
from __future__ import annotations

import hashlib
import logging
import os
import uuid
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from catalog.application.discovery import DiscoveryObservation
from catalog.domain.identity import CanonicalFingerprint, MediaKind, ProvenanceEntry, ProvenanceRelation
from controlplane.domain.common.contracts import ProblemDetail
from source_ingestion.adapters.image_header import read_image_size
from source_ingestion.adapters.secure_fetch import PROBLEM_TYPE_PREFIX, FetchPolicy, SecureFetcher

_LOG = logging.getLogger(__name__)

MAX_IMAGES_PER_ARTICLE = 12
MIN_SHORT_SIDE = 360

_EXTENSIONS = {'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp'}
_DISCOVERY_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, 'urn:source-ingestion:media-discovery')
_SEPARATOR = chr(31)


def _new_correlation_id() -> str:
    return 'media-' + uuid.uuid4().hex


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _staging_problem(correlation_id: str) -> ProblemDetail:
    _LOG.info('media fetch problem code=STAGING_WRITE_FAILED')
    return ProblemDetail.create(
        type=PROBLEM_TYPE_PREFIX + 'staging_write_failed',
        title='STAGING_WRITE_FAILED',
        detail='Image could not be written to the staging root.',
        instance=f'urn:source-ingestion:media:{correlation_id}',
        code='STAGING_WRITE_FAILED',
        category='internal',
        retryable=False,
        correlation_id=correlation_id,
    )


def _image_problem(code: str, detail: str, correlation_id: str, **facts: int) -> ProblemDetail:
    _LOG.info('media fetch problem code=%s', code)
    return ProblemDetail.create(
        type=PROBLEM_TYPE_PREFIX + code.lower(),
        title=code,
        detail=detail,
        instance=f'urn:source-ingestion:media:{correlation_id}',
        code=code,
        category='policy',
        retryable=False,
        correlation_id=correlation_id,
        **facts,
    )


@dataclass(frozen=True)
class StagedImage:
    """One staged image and the DiscoveryObservation that C registers."""

    observation: DiscoveryObservation
    staged_path: Path
    sha256: str
    size_bytes: int
    media_type: str
    final_locator: str


@dataclass(frozen=True)
class MediaFetchBatch:
    staged: tuple[StagedImage, ...]
    problems: tuple[ProblemDetail, ...]


class RealMediaFetcher:
    """Fetch article images through SecureFetcher and stage them for C."""

    def __init__(
        self,
        fetcher: SecureFetcher,
        *,
        image_policy: FetchPolicy,
        staging_root: str | Path,
        max_images_per_article: int = MAX_IMAGES_PER_ARTICLE,
        utc_now: Callable[[], datetime] = _utc_now,
        correlation_id: Callable[[], str] = _new_correlation_id,
    ) -> None:
        if not isinstance(fetcher, SecureFetcher) or not isinstance(image_policy, FetchPolicy):
            raise ValueError('INVALID_MEDIA_FETCH_CONFIG')
        if type(max_images_per_article) is not int or max_images_per_article <= 0:
            raise ValueError('INVALID_MEDIA_FETCH_CONFIG')
        root = Path(staging_root)
        if not root.is_absolute():
            raise ValueError('INVALID_STAGING_ROOT')
        self._fetcher = fetcher
        self._policy = image_policy
        self._root = root
        self._max_images = max_images_per_article
        self._utc_now = utc_now
        self._new_correlation_id = correlation_id

    def _stage(self, body: bytes, digest: str, media_type: str) -> Path:
        extension = _EXTENSIONS.get(media_type, 'bin')
        target = self._root / f'{digest}.{extension}'
        part = self._root / f'{digest}.{extension}.part'
        self._root.mkdir(parents=True, exist_ok=True)
        if target.is_file() and target.stat().st_size == len(body):
            return target
        try:
            part.write_bytes(body)
            os.replace(part, target)
        finally:
            part.unlink(missing_ok=True)
        return target

    def fetch_image(
        self, locator: str, *, role: str, source_ref: str | None, article_ref: str | None, event_ref: str | None = None
    ) -> StagedImage | ProblemDetail:
        correlation_id = self._new_correlation_id()
        fetched = self._fetcher.fetch(locator, self._policy, correlation_id=correlation_id)
        if isinstance(fetched, ProblemDetail):
            return fetched
        observation = fetched.observation
        size = read_image_size(fetched.body)
        if size is None:
            return _image_problem('IMAGE_HEADER_UNREADABLE', 'Image header could not be read.', correlation_id)
        if min(size) < MIN_SHORT_SIDE:
            return _image_problem(
                'IMAGE_TOO_SMALL',
                'Image short side is below the minimum.',
                correlation_id,
                width=size[0],
                height=size[1],
                min_short_side=MIN_SHORT_SIDE,
            )
        digest = hashlib.sha256(fetched.body).hexdigest()
        try:
            path = self._stage(fetched.body, digest, observation.media_type)
        except OSError:
            return _staging_problem(correlation_id)
        relation = ProvenanceRelation.HERO_IMAGE if role == 'hero' else ProvenanceRelation.INLINE_IMAGE
        observed_at = self._utc_now().astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        provenance = ProvenanceEntry(
            source_ref, article_ref, event_ref, observation.requested_locator, observed_at, relation
        )
        identity = _SEPARATOR.join((source_ref or '', article_ref or '', observation.requested_locator, digest))
        discovery = DiscoveryObservation(
            discovery_id=str(uuid.uuid5(_DISCOVERY_NAMESPACE, identity)),
            kind=MediaKind.IMAGE,
            provenance=provenance,
            fingerprint=CanonicalFingerprint(digest),
            locator_validated=True,
        )
        return StagedImage(
            discovery, path, digest, observation.size_bytes, observation.media_type, observation.final_locator
        )

    def fetch_article_media(
        self,
        media_items: Iterable[Mapping[str, object]],
        *,
        source_ref: str | None,
        article_ref: str | None,
        event_ref: str | None = None,
    ) -> MediaFetchBatch:
        """Fetch the image items (media_kind image) of one article; at most max_images_per_article attempts."""
        staged: list[StagedImage] = []
        problems: list[ProblemDetail] = []
        seen: set[str] = set()
        for item in media_items:
            if not isinstance(item, Mapping) or item.get('media_kind') != 'image':
                continue
            locator, role = item.get('locator'), item.get('role')
            if not isinstance(locator, str) or not isinstance(role, str) or locator in seen:
                continue
            if len(seen) >= self._max_images:
                break
            seen.add(locator)
            result = self.fetch_image(
                locator, role=role, source_ref=source_ref, article_ref=article_ref, event_ref=event_ref
            )
            if isinstance(result, ProblemDetail):
                problems.append(result)
            else:
                staged.append(result)
        return MediaFetchBatch(tuple(staged), tuple(problems))
