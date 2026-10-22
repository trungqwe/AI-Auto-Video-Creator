"""PostgreSQL repositories for module B (PERSIST-B, REQ-B-CONV-02)."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import fields
from types import MappingProxyType
from typing import Any

from psycopg import sql
from psycopg.types.json import Jsonb

from ingestion.application.ports import (
    ArticleRepository,
    EventRepository,
    RecordRepository,
    ResolutionRepository,
)
from ingestion.domain.article import Article, ArticleRevision


def _plain(value: Any) -> Any:
    if isinstance(value, MappingProxyType) or isinstance(value, Mapping) or hasattr(value, "items"):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def _revision_to_dict(rev: ArticleRevision) -> dict[str, Any]:
    return {f.name: _plain(getattr(rev, f.name)) for f in fields(rev)}


def _deserialize_revision(payload: dict[str, Any]) -> ArticleRevision:
    payload = dict(payload)
    payload["provenance_chain"] = tuple(payload.get("provenance_chain", ()))
    payload["media_discovery_refs"] = tuple(payload.get("media_discovery_refs", ()))
    payload["uncertain_fields"] = tuple(payload.get("uncertain_fields", ()))
    return ArticleRevision(**payload)


class PostgresArticleRepository(ArticleRepository):
    def __init__(self, connection_getter: Callable[[], Any], workspace_id: str) -> None:
        self._connection_getter = connection_getter
        self._workspace_id = workspace_id

    @property
    def _conn(self) -> Any:
        return self._connection_getter()

    def get(self, article_id: str) -> Article | None:
        art_row = self._conn.execute(
            "SELECT payload FROM controlplane.cp_articles WHERE workspace_id = %s AND article_id = %s",
            (self._workspace_id, article_id),
        ).fetchone()
        if art_row is None:
            return None
        rev_rows = self._conn.execute(
            "SELECT payload FROM controlplane.cp_article_revisions WHERE workspace_id = %s AND article_id = %s ORDER BY revision",
            (self._workspace_id, article_id),
        ).fetchall()
        revisions = tuple(_deserialize_revision(r[0]) for r in rev_rows)
        art_payload = art_row[0]
        return Article(
            article_id=art_payload["article_id"],
            identity_key=art_payload["identity_key"],
            representative_source_id=art_payload["representative_source_id"],
            revisions=revisions,
        )

    def find_by_identity_key(self, identity_key: str) -> Article | None:
        row = self._conn.execute(
            "SELECT article_id FROM controlplane.cp_articles WHERE workspace_id = %s AND identity_key = %s",
            (self._workspace_id, identity_key),
        ).fetchone()
        if row is None:
            return None
        return self.get(row[0])

    def find_by_exact_fingerprint(self, exact_fingerprint: str) -> Article | None:
        row = self._conn.execute(
            "SELECT article_id FROM controlplane.cp_article_revisions "
            "WHERE workspace_id = %s AND payload->>'exact_fingerprint' = %s "
            "ORDER BY article_id, revision LIMIT 1",
            (self._workspace_id, exact_fingerprint),
        ).fetchone()
        if row is None:
            return None
        return self.get(row[0])

    def list_all(self) -> tuple[Article, ...]:
        rows = self._conn.execute(
            "SELECT article_id FROM controlplane.cp_articles WHERE workspace_id = %s ORDER BY article_id",
            (self._workspace_id,),
        ).fetchall()
        articles: list[Article] = []
        for r in rows:
            art = self.get(r[0])
            if art is not None:
                articles.append(art)
        return tuple(articles)

    def save(self, article: Article) -> None:
        if not isinstance(article, Article):
            raise TypeError("article must be an Article")

        stored_rev_rows = self._conn.execute(
            "SELECT payload FROM controlplane.cp_article_revisions WHERE workspace_id = %s AND article_id = %s ORDER BY revision",
            (self._workspace_id, article.article_id),
        ).fetchall()
        stored_revisions = tuple(_deserialize_revision(r[0]) for r in stored_rev_rows)

        if article.revisions[:len(stored_revisions)] != stored_revisions:
            raise ValueError(f"stored revisions of {article.article_id} are immutable")

        latest = article.latest_revision
        exact_fingerprint = latest.exact_fingerprint if latest is not None else ""
        revision_num = max(len(article.revisions), 1)
        art_payload = {
            "article_id": article.article_id,
            "identity_key": article.identity_key,
            "representative_source_id": article.representative_source_id,
        }

        self._conn.execute(
            "INSERT INTO controlplane.cp_articles (workspace_id, article_id, identity_key, exact_fingerprint, revision, payload) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (workspace_id, article_id) DO UPDATE SET "
            "identity_key = EXCLUDED.identity_key, "
            "exact_fingerprint = EXCLUDED.exact_fingerprint, "
            "revision = EXCLUDED.revision, "
            "payload = EXCLUDED.payload, "
            "updated_at = CURRENT_TIMESTAMP",
            (
                self._workspace_id,
                article.article_id,
                article.identity_key,
                exact_fingerprint,
                revision_num,
                Jsonb(_plain(art_payload)),
            ),
        )

        for rev in article.revisions[len(stored_revisions):]:
            self._conn.execute(
                "INSERT INTO controlplane.cp_article_revisions (workspace_id, article_id, revision, payload) "
                "VALUES (%s, %s, %s, %s)",
                (
                    self._workspace_id,
                    article.article_id,
                    rev.revision_number,
                    Jsonb(_revision_to_dict(rev)),
                ),
            )


class PostgresResolutionRepository(ResolutionRepository):
    def __init__(self, connection_getter: Callable[[], Any], workspace_id: str) -> None:
        self._connection_getter = connection_getter
        self._workspace_id = workspace_id

    @property
    def _conn(self) -> Any:
        return self._connection_getter()

    def get(self, collected_document_id: str, dedup_policy_revision: str) -> Mapping[str, Any] | None:
        row = self._conn.execute(
            "SELECT payload FROM controlplane.cp_collected_document_resolutions "
            "WHERE workspace_id = %s AND collected_document_id = %s AND dedup_policy_revision = %s",
            (self._workspace_id, collected_document_id, str(dedup_policy_revision)),
        ).fetchone()
        if row is None:
            return None
        return dict(row[0])

    def list_all(self) -> tuple[Mapping[str, Any], ...]:
        rows = self._conn.execute(
            "SELECT payload FROM controlplane.cp_collected_document_resolutions "
            "WHERE workspace_id = %s ORDER BY collected_document_id, dedup_policy_revision",
            (self._workspace_id,),
        ).fetchall()
        return tuple(dict(r[0]) for r in rows)

    def save(self, resolution: Mapping[str, Any]) -> None:
        collected_document_id = str(resolution["collected_document_id"])
        dedup_policy_revision = str(resolution["dedup_policy_revision"])
        payload = _plain(dict(resolution))
        self._conn.execute(
            "INSERT INTO controlplane.cp_collected_document_resolutions "
            "(workspace_id, collected_document_id, dedup_policy_revision, payload) "
            "VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (workspace_id, collected_document_id, dedup_policy_revision) DO UPDATE SET "
            "payload = EXCLUDED.payload, "
            "updated_at = CURRENT_TIMESTAMP",
            (self._workspace_id, collected_document_id, dedup_policy_revision, Jsonb(payload)),
        )


class PostgresEventRepository(EventRepository):
    def __init__(self, connection_getter: Callable[[], Any], workspace_id: str) -> None:
        self._connection_getter = connection_getter
        self._workspace_id = workspace_id

    @property
    def _conn(self) -> Any:
        return self._connection_getter()

    def get(self, event_id: str) -> Mapping[str, Any] | None:
        row = self._conn.execute(
            "SELECT payload FROM controlplane.cp_events WHERE workspace_id = %s AND event_id = %s",
            (self._workspace_id, event_id),
        ).fetchone()
        if row is None:
            return None
        return dict(row[0])

    def list_all(self) -> tuple[Mapping[str, Any], ...]:
        rows = self._conn.execute(
            "SELECT payload FROM controlplane.cp_events WHERE workspace_id = %s ORDER BY event_id",
            (self._workspace_id,),
        ).fetchall()
        return tuple(dict(r[0]) for r in rows)

    def save(self, event: Mapping[str, Any]) -> None:
        event_id = str(event["event_id"])
        revision = int(event["revision"])
        payload = _plain(dict(event))
        self._conn.execute(
            "INSERT INTO controlplane.cp_events (workspace_id, event_id, revision, payload) "
            "VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (workspace_id, event_id) DO UPDATE SET "
            "revision = EXCLUDED.revision, "
            "payload = EXCLUDED.payload, "
            "updated_at = CURRENT_TIMESTAMP",
            (self._workspace_id, event_id, revision, Jsonb(payload)),
        )


class UnknownRecordKindError(ValueError):
    """Raised when an unknown record kind is requested."""


RECORD_TABLES: dict[str, str] = {
    "dedup_evidence": "cp_dedup_evidence",
    "event_link_candidate": "cp_event_link_candidates",
    "event_update": "cp_event_updates",
    "event_update_candidate": "cp_event_update_candidates",
}


class PostgresRecordRepository(RecordRepository):
    def __init__(self, connection_getter: Callable[[], Any], workspace_id: str) -> None:
        self._connection_getter = connection_getter
        self._workspace_id = workspace_id

    @property
    def _conn(self) -> Any:
        return self._connection_getter()

    def _get_table_and_key(self, kind: str) -> tuple[str, str]:
        if kind not in RECORD_TABLES:
            raise UnknownRecordKindError(f"unknown record kind {kind!r}")
        table = RECORD_TABLES[kind]
        key_col = "evidence_id" if kind == "dedup_evidence" else "record_id"
        return table, key_col

    def get(self, kind: str, record_id: str) -> Mapping[str, Any] | None:
        table, key_col = self._get_table_and_key(kind)
        query = sql.SQL(
            "SELECT payload FROM controlplane.{} WHERE workspace_id = %s AND {} = %s"
        ).format(sql.Identifier(table), sql.Identifier(key_col))
        row = self._conn.execute(query, (self._workspace_id, record_id)).fetchone()
        if row is None:
            return None
        return dict(row[0])

    def list(self, kind: str) -> tuple[Mapping[str, Any], ...]:
        table, key_col = self._get_table_and_key(kind)
        query = sql.SQL(
            "SELECT payload FROM controlplane.{} WHERE workspace_id = %s ORDER BY {}"
        ).format(sql.Identifier(table), sql.Identifier(key_col))
        rows = self._conn.execute(query, (self._workspace_id,)).fetchall()
        return tuple(dict(r[0]) for r in rows)

    def put(self, kind: str, record_id: str, record: Mapping[str, Any]) -> None:
        table, key_col = self._get_table_and_key(kind)
        payload = _plain(dict(record))

        if kind in ("dedup_evidence", "event_update"):
            select_query = sql.SQL(
                "SELECT payload FROM controlplane.{} WHERE workspace_id = %s AND {} = %s"
            ).format(sql.Identifier(table), sql.Identifier(key_col))
            row = self._conn.execute(select_query, (self._workspace_id, record_id)).fetchone()
            if row is not None:
                if row[0] == payload:
                    return
                raise ValueError(f"{kind} {record_id} is append-only")

            if kind == "dedup_evidence":
                doc_id = record.get("collected_document_id")
                dedup_policy_revision = record.get("dedup_policy_revision")
                if not isinstance(doc_id, str) or not isinstance(dedup_policy_revision, str):
                    raise ValueError("dedup_evidence requires string collected_document_id and dedup_policy_revision")
                insert_query = sql.SQL(
                    "INSERT INTO controlplane.{} (workspace_id, evidence_id, collected_document_id, dedup_policy_revision, payload) "
                    "VALUES (%s, %s, %s, %s, %s)"
                ).format(sql.Identifier(table))
                self._conn.execute(
                    insert_query,
                    (self._workspace_id, record_id, doc_id, dedup_policy_revision, Jsonb(payload)),
                )
            else:
                event_id = record.get("event_id")
                if not isinstance(event_id, str):
                    raise ValueError("event_update requires string event_id")
                insert_query = sql.SQL(
                    "INSERT INTO controlplane.{} (workspace_id, record_id, event_id, payload) "
                    "VALUES (%s, %s, %s, %s)"
                ).format(sql.Identifier(table))
                self._conn.execute(
                    insert_query,
                    (self._workspace_id, record_id, event_id, Jsonb(payload)),
                )
        else:
            upsert_query = sql.SQL(
                "INSERT INTO controlplane.{} (workspace_id, record_id, payload) "
                "VALUES (%s, %s, %s) "
                "ON CONFLICT (workspace_id, record_id) DO UPDATE SET "
                "payload = EXCLUDED.payload, "
                "updated_at = CURRENT_TIMESTAMP"
            ).format(sql.Identifier(table))
            self._conn.execute(
                upsert_query,
                (self._workspace_id, record_id, Jsonb(payload)),
            )
