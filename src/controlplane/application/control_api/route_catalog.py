"""Danh mục tài nguyên listing và metadata router cho Control API.

Mười tài nguyên đọc (GET danh sách và GET chi tiết, mỗi route chỉ trả dữ liệu khi app.state.module_services có service cùng tên, nếu không trả 503 CAPABILITY_UNAVAILABLE): sources, hooks, media, articles, events, artifacts, snapshots, story-angles, scripts, sessions, accounts, cost; logs và capabilities không có route (docs/implementation/read-screens/plan.md mục 7.1).

'sources' có cả listing và metadata (PATCH /v1/sources/{item_id}, allowlist tier, topic_tags, notes, enabled; docs/implementation/convergence-ext-ui/plan.md:110); RegisterSource, RemoveSource, RestoreSource, TestSource vẫn là route lệnh ở control.py;
không filter nào là workspace_id hay actor_id;
không allowed_fields nào giao với FORBIDDEN_METADATA_FIELDS của metadata_update.py.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ListingResource:
    name: str
    prefix: str
    allowed_sorts: tuple[str, ...]
    allowed_filters: frozenset[str]
    default_limit: int
    max_limit: int
    with_detail: bool


@dataclass(frozen=True)
class MetadataResource:
    name: str
    prefix: str
    allowed_fields: frozenset[str]


LISTING_RESOURCES: tuple[ListingResource, ...] = (
    ListingResource(
        "sources",
        "/v1/sources",
        ("updated_at", "name"),
        frozenset({"topic", "tier", "status"}),
        50,
        100,
        True,
    ),
    ListingResource(
        "hooks",
        "/v1/hooks",
        ("updated_at", "name"),
        frozenset({"kind", "tag", "enabled"}),
        50,
        100,
        True,
    ),
    ListingResource(
        "articles",
        "/v1/articles",
        ("updated_at",),
        frozenset({"source_id"}),
        50,
        100,
        True,
    ),
    ListingResource(
        "events",
        "/v1/events",
        ("updated_at",),
        frozenset({"status"}),
        50,
        100,
        True,
    ),
    ListingResource(
        "artifacts",
        "/v1/artifacts",
        ("created_at",),
        frozenset({"kind", "state"}),
        50,
        100,
        True,
    ),
    ListingResource(
        "snapshots",
        "/v1/snapshots",
        ("created_at",),
        frozenset({"job_id"}),
        50,
        100,
        True,
    ),
    ListingResource(
        "story-angles",
        "/v1/story-angles",
        ("created_at",),
        frozenset(),
        50,
        100,
        True,
    ),
    ListingResource(
        "scripts",
        "/v1/scripts",
        ("created_at",),
        frozenset({"language"}),
        50,
        100,
        True,
    ),
    ListingResource(
        "sessions",
        "/v1/sessions",
        ("started_at",),
        frozenset({"status"}),
        50,
        100,
        True,
    ),
    ListingResource(
        "accounts",
        "/v1/accounts",
        ("updated_at",),
        frozenset({"provider", "status"}),
        50,
        100,
        True,
    ),
    ListingResource(
        "cost",
        "/v1/cost",
        ("recorded_at",),
        frozenset({"provider", "job_id"}),
        50,
        100,
        True,
    ),
    ListingResource(
        "media",
        "/v1/media",
        ("updated_at", "name"),
        frozenset({"kind", "status"}),
        50,
        100,
        True,
    ),
)

METADATA_RESOURCES: tuple[MetadataResource, ...] = (
    MetadataResource(
        "sources",
        "/v1/sources",
        frozenset({"tier", "topic_tags", "notes", "enabled"}),
    ),
    MetadataResource(
        "hooks",
        "/v1/hooks",
        frozenset({"description", "tags", "enabled", "notes"}),
    ),
    MetadataResource(
        "media",
        "/v1/media",
        frozenset({"description", "tags", "notes"}),
    ),
)