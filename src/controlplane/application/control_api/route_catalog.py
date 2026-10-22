"""Danh mục tài nguyên listing và metadata router cho Control API.

UpdateSourceMetadata nằm ở route lệnh control.py (CT-API-003, trả receipt accepted) nên 'sources' chỉ có listing;
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
        "media",
        "/v1/media",
        ("updated_at", "name"),
        frozenset({"kind", "tag", "availability"}),
        50,
        100,
        True,
    ),
)

METADATA_RESOURCES: tuple[MetadataResource, ...] = (
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