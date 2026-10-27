"""PW-B1: PostgresCandidateSelector chọn ứng viên từ bảng B cho lô (CandidateSelectorPort.next_candidate)."""
from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from controlplane.domain.orchestration.allocation_policy import AllocationCandidate
from ingestion.application.ports import UnitOfWork
from ingestion.application.source_set import PRODUCTION_MODES, SINGLE_ARTICLE, SourceSetRejected, build_source_set

DEFAULT_VIDEOS_PER_NEWS_PER_ROUND = 2
ANGLE_SLOT_PREFIX = 'angle-'
_TIER_RE = re.compile(r'tier_([1-3])')
ConnectionFactory = Callable[[], AbstractContextManager[Any]]


def _default_tier_scores() -> Mapping[int, float]:
    return MappingProxyType({1: 1.0, 2: 0.5, 3: 0.0})


@dataclass(frozen=True)
class HotnessWeights:
    independent_sources: float = 1.0
    freshness: float = 1.0
    tier: float = 1.0
    freshness_window_hours: float = 72.0
    tier_scores: Mapping[int, float] = field(default_factory=_default_tier_scores)


DEFAULT_WEIGHTS = HotnessWeights()

_REVISIONS_SQL = (
    "SELECT r.article_id, r.payload->>'article_revision_id', r.payload->>'source_id', "
    "r.payload->>'published_at', r.payload->>'fetched_at' "
    'FROM controlplane.cp_article_revisions r '
    'JOIN controlplane.cp_articles a ON a.workspace_id = r.workspace_id AND a.article_id = r.article_id '
    'WHERE r.workspace_id = %s ORDER BY r.article_id, r.revision'
)
_EVENTS_SQL = "SELECT event_id, payload->'member_refs' FROM controlplane.cp_events WHERE workspace_id = %s ORDER BY event_id"
_TIERS_SQL = "SELECT source_id, payload->>'tier' FROM controlplane.cp_sources WHERE workspace_id = %s"
_USAGE_SQL = 'SELECT candidate_ref, count(*) FROM controlplane.cp_job_candidates WHERE workspace_id = %s GROUP BY candidate_ref'


@dataclass(frozen=True)
class _Revision:
    article_id: str
    revision_id: str
    source_id: str
    moment: datetime | None


@dataclass(frozen=True)
class _Subject:
    subject_id: str
    revisions: tuple[_Revision, ...]


def _moment(*values: str | None) -> datetime | None:
    for value in values:
        if not value:
            continue
        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            continue
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
    return None


def hotness(subject: _Subject, tiers: Mapping[str, int], weights: HotnessWeights, now: datetime) -> float:
    """Mức nóng = trọng số * số nguồn độc lập + trọng số * độ mới (0..1 trong freshness_window_hours) + trọng số * điểm tier tốt nhất."""
    sources = {revision.source_id for revision in subject.revisions}
    moments = [revision.moment for revision in subject.revisions if revision.moment is not None]
    freshness = 0.0
    if moments:
        age_hours = (now - max(moments)).total_seconds() / 3600.0
        freshness = min(1.0, max(0.0, 1.0 - age_hours / weights.freshness_window_hours))
    ranks = [tiers[source] for source in sources if source in tiers]
    tier_score = weights.tier_scores.get(min(ranks), 0.0) if ranks else 0.0
    return weights.independent_sources * len(sources) + weights.freshness * freshness + weights.tier * tier_score


def _subjects(production_mode: str, revision_rows: list[Any], event_rows: list[Any]) -> tuple[_Subject, ...]:
    revisions = [_Revision(row[0], row[1], row[2], _moment(row[3], row[4])) for row in revision_rows]
    if production_mode == SINGLE_ARTICLE:
        latest = {revision.article_id: revision for revision in revisions}  # hàng đã ORDER BY revision nên bản cuối thắng
        return tuple(_Subject(article_id, (revision,)) for article_id, revision in latest.items())
    pinned = {(revision.article_id, revision.revision_id): revision for revision in revisions}
    subjects = []
    for event_id, refs in event_rows:
        members = json.loads(refs) if isinstance(refs, str) else (refs or [])
        found = tuple(pinned[(member[0], member[1])] for member in members if (member[0], member[1]) in pinned)
        subjects.append(_Subject(str(event_id), found))
    return tuple(subjects)


def _tiers(rows: list[Any]) -> dict[str, int]:
    tiers: dict[str, int] = {}
    for source_id, text in rows:
        match = _TIER_RE.fullmatch(text or '')
        if match is not None:
            tiers[str(source_id)] = int(match.group(1))
    return tiers


def _usage(rows: list[Any]) -> dict[str, int]:
    return {str(candidate_ref): int(count) for candidate_ref, count in rows}


class PostgresCandidateSelector:
    """CandidateSelectorPort: chủ thể nóng nhất còn suất, xác định với cùng dữ liệu và cùng đồng hồ.

    Chủ thể là article_id (single_article) hoặc event_id (hai mode sự kiện). Số video đã dùng của chủ thể đếm trong cp_job_candidates của mọi lô trong workspace (GIẢ ĐỊNH D8) nên chủ thể đủ suất không bao giờ lặp giữa các lô; angle_slot là angle-<số video đã dùng + 1>. Chỉ đọc; không mở giao dịch ghi.
    """

    def __init__(
        self, connection_factory: ConnectionFactory, uow_factory: Callable[[], UnitOfWork], *, workspace_id: str,
        clock: Callable[[], datetime], videos_per_news_per_round: int = DEFAULT_VIDEOS_PER_NEWS_PER_ROUND,
        weights_provider: Callable[[], HotnessWeights] | None = None, source_set_builder: Callable[..., Any] | None = None,
    ) -> None:
        if isinstance(videos_per_news_per_round, bool) or not isinstance(videos_per_news_per_round, int) or videos_per_news_per_round < 1:
            raise ValueError('videos_per_news_per_round must be a positive integer')
        self._connection_factory = connection_factory
        self._uow_factory = uow_factory
        self._workspace_id = workspace_id
        self._clock = clock
        self._per_news = videos_per_news_per_round
        self._weights_provider = weights_provider or (lambda: DEFAULT_WEIGHTS)
        self._source_set_builder = source_set_builder or build_source_set

    def _read(self, production_mode: str) -> tuple[list[Any], list[Any], list[Any], list[Any]]:
        params = (self._workspace_id,)
        with self._connection_factory() as connection:
            revisions = connection.execute(_REVISIONS_SQL, params).fetchall()
            events = [] if production_mode == SINGLE_ARTICLE else connection.execute(_EVENTS_SQL, params).fetchall()
            tiers = connection.execute(_TIERS_SQL, params).fetchall()
            usage = connection.execute(_USAGE_SQL, params).fetchall()
        return revisions, events, tiers, usage

    def next_candidate(self, batch_id: str, production_mode: str) -> AllocationCandidate | None:
        """batch_id chỉ để khớp port; việc loại trừ tính trên mọi lô của workspace. Trả None khi hết ứng viên."""
        if not isinstance(batch_id, str) or not batch_id.strip():
            raise ValueError('batch_id must be a non-empty string')
        if production_mode not in PRODUCTION_MODES:
            raise ValueError(f'production_mode must be one of {PRODUCTION_MODES!r}')
        weights, now = self._weights_provider(), self._clock()
        if now.tzinfo is None:
            raise ValueError('clock must return a timezone-aware datetime')
        revision_rows, event_rows, tier_rows, usage_rows = self._read(production_mode)
        tiers, used = _tiers(tier_rows), _usage(usage_rows)
        ranked = sorted(_subjects(production_mode, revision_rows, event_rows), key=lambda s: (-hotness(s, tiers, weights, now), s.subject_id))
        with self._uow_factory() as uow:
            for subject in ranked:
                count = used.get(subject.subject_id, 0)
                if count >= self._per_news:
                    continue
                try:
                    source_set = self._source_set_builder(production_mode, subject.subject_id, uow)
                except (SourceSetRejected, LookupError):
                    continue
                source_set_ref = f'{production_mode}:{subject.subject_id}:{source_set.source_set_fingerprint}'
                return AllocationCandidate(subject.subject_id, f'{ANGLE_SLOT_PREFIX}{count + 1}', source_set_ref)
        return None


__all__ = ['DEFAULT_VIDEOS_PER_NEWS_PER_ROUND', 'DEFAULT_WEIGHTS', 'HotnessWeights', 'PostgresCandidateSelector']