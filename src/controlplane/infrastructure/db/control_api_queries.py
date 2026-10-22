"""Read-only PostgreSQL projections for P7A Control API routes."""

from __future__ import annotations

from typing import Any

from controlplane.application.control_api.errors import CapabilityUnavailableError
from controlplane.application.projections.list_query import ListQuery, Page, build_page
from controlplane.application.projections.operation_view_mapper import map_operation_view
from controlplane.domain.statemachine import OperationState
from controlplane.infrastructure.db.projections.list_queries import (
    BATCHES_SPEC,
    JOBS_SPEC,
    ListSpec,
    fetch_page,
)

_LIST_DIRECTIONS = {"asc": ("ASC", ">"), "desc": ("DESC", "<")}

# started_at is nullable, so the keyset sorts on created_at (NOT NULL); stage_name is exposed as the UI column 'stage'.
STAGE_RUNS_SPEC = ListSpec(
    table="controlplane.cp_stage_runs",
    id_column="stage_run_id",
    sort_columns=("created_at",),
    filter_columns=("job_id", "status"),
    select_columns=(
        "stage_run_id",
        "job_id",
        "stage_name",
        "status",
        "started_at",
        "finished_at",
        "created_at",
    ),
)
LIST_SPECS: dict[str, ListSpec] = {"stage_runs": STAGE_RUNS_SPEC}
_FIELD_RENAMES = {"stage_name": "stage"}
BLOCKED_LIST_RESOURCES: dict[str, tuple[str | None, tuple[str, ...]]] = {
    "sources": ("controlplane.cp_sources", ("tier", "topic_tags", "notes", "enabled")),
    "articles": ("controlplane.cp_articles", ("source_id", "title", "published_at", "fetch_evidence_ref")),
    "events": ("controlplane.cp_events", ("title", "status", "source_id", "fetch_evidence_ref")),
    "media": ("controlplane.cp_media_assets", ("kind", "tags", "notes")),
    "hooks": ("controlplane.cp_hooks", ("tags", "description", "notes")),
    "sessions": ("controlplane.cp_app_sessions", ("job_id",)),
    "logs": (None, ("log_id", "severity", "message")),
    "capabilities": (None, ()),
}


def _list_direction(query: ListQuery, *, sort_key: str) -> tuple[str, str]:
    if query.sort_key != sort_key or query.filters:
        raise ValueError("column_not_allowed")
    if query.direction not in _LIST_DIRECTIONS:
        raise ValueError("direction_invalid")
    if type(query.limit) is not int or query.limit < 1:
        raise ValueError("limit_invalid")
    return _LIST_DIRECTIONS[query.direction]


class PostgresControlQueries:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def operations(self, *, workspace_id: str, query: ListQuery) -> Page:
        direction, operator = _list_direction(query, sort_key="accepted_at")
        conditions = "r.workspace_id = %s AND r.operation_id IS NOT NULL"
        params: list[object] = [workspace_id]
        if query.cursor is not None:
            conditions += f" AND (r.accepted_at, r.receipt_id) {operator} (%s, %s)"
            params.extend(query.cursor)
        params.append(query.limit + 1)
        rows = self._connection.execute(
            f"""SELECT r.operation_id::text, r.command_id, r.receipt_id::text, r.disposition,
                      r.resource_ref, r.accepted_at, p.event_kind, p.summary, b.status AS batch_status
               FROM controlplane.cp_command_receipts r
               LEFT JOIN LATERAL (
                   SELECT event_kind, summary
                   FROM controlplane.cp_operation_stream
                   WHERE workspace_id = r.workspace_id AND operation_id = r.operation_id
                   ORDER BY stream_event_id DESC
                   LIMIT 1
               ) p ON true
               LEFT JOIN controlplane.cp_production_batches b
                   ON b.workspace_id = r.workspace_id
                   AND r.resource_ref->>'kind' = 'production_batch'
                   AND b.batch_id = r.resource_ref->>'batch_id'
               WHERE {conditions}
               ORDER BY r.accepted_at {direction}, r.receipt_id {direction}
               LIMIT %s""",
            tuple(params),
        ).fetchall()
        items = [self._operation_row(row) for row in rows]
        return build_page(items, query=query, sort_field="accepted_at", id_field="receipt_id")

    def operation(self, *, workspace_id: str, operation_id: str) -> dict[str, object] | None:
        row = self._connection.execute(
            """SELECT r.operation_id::text, r.command_id, r.receipt_id::text, r.disposition,
                      r.resource_ref, r.accepted_at, p.event_kind, p.summary, b.status AS batch_status
               FROM controlplane.cp_command_receipts r
               LEFT JOIN LATERAL (
                   SELECT event_kind, summary
                   FROM controlplane.cp_operation_stream
                   WHERE workspace_id = r.workspace_id AND operation_id = r.operation_id
                   ORDER BY stream_event_id DESC
                   LIMIT 1
               ) p ON true
               LEFT JOIN controlplane.cp_production_batches b
                   ON b.workspace_id = r.workspace_id
                   AND r.resource_ref->>'kind' = 'production_batch'
                   AND b.batch_id = r.resource_ref->>'batch_id'
               WHERE r.workspace_id = %s AND r.operation_id = %s""",
            (workspace_id, operation_id),
        ).fetchone()
        return self._operation_row(row) if row is not None else None

    @staticmethod
    def _operation_row(row: Any) -> dict[str, object]:
        batch_status = row[8] if len(row) > 8 else None
        if batch_status:
            status_map = {
                "CREATED": OperationState.PREPARED,
                "RUNNING": OperationState.STARTED,
                "WAITING_CAPABILITY": OperationState.STARTED,
                "COMPLETED_TARGET": OperationState.SUCCEEDED,
                "COMPLETED_EXHAUSTED": OperationState.SUCCEEDED,
                "FAILED_SYSTEM": OperationState.FAILED,
            }
            op_state = status_map.get(batch_status, OperationState.PREPARED)
            wait_reason = {"code": "WAITING_CAPABILITY"} if batch_status == "WAITING_CAPABILITY" else None
            status = map_operation_view(execution_state=op_state, wait_reason=wait_reason)
        else:
            status = "accepted"

        return {
            "operation_id": row[0],
            "command_ref": row[1],
            "receipt_id": row[2],
            "status": status,
            "resource_refs": [row[4]] if row[4] else [],
            "accepted_at": row[5].isoformat() if hasattr(row[5], "isoformat") else row[5],
            "latest_event_kind": row[6],
            "latest_safe_summary": row[7],
        }

    def batches(self, *, workspace_id: str, query: ListQuery) -> Page:
        return fetch_page(self._connection, BATCHES_SPEC, query, workspace_id=workspace_id)

    def batch(self, *, workspace_id: str, batch_id: str) -> dict[str, object] | None:
        row = self._connection.execute(
            "SELECT batch_id, status, target_count, created_at "
            "FROM controlplane.cp_production_batches WHERE workspace_id = %s AND batch_id = %s",
            (workspace_id, batch_id),
        ).fetchone()
        return self._batch_row(row) if row is not None else None

    @staticmethod
    def _batch_row(row: Any) -> dict[str, object]:
        return {
            "batch_id": row[0],
            "status": row[1],
            "target_count": row[2],
            "created_at": row[3].isoformat() if hasattr(row[3], "isoformat") else row[3],
        }

    def jobs(self, *, workspace_id: str, query: ListQuery) -> Page:
        return fetch_page(self._connection, JOBS_SPEC, query, workspace_id=workspace_id)

    def job(self, *, workspace_id: str, job_id: str) -> dict[str, object] | None:
        row = self._connection.execute(
            "SELECT job_id, batch_id, status, snapshot_ref, revision, created_at "
            "FROM controlplane.cp_video_jobs WHERE workspace_id = %s AND job_id = %s",
            (workspace_id, job_id),
        ).fetchone()
        return self._job_row(row) if row is not None else None

    @staticmethod
    def _job_row(row: Any) -> dict[str, object]:
        return {
            "job_id": row[0],
            "batch_id": row[1],
            "status": row[2],
            "snapshot_ref": row[3],
            "revision": row[4],
            "created_at": row[5].isoformat() if hasattr(row[5], "isoformat") else row[5],
        }

    def configs(self, *, workspace_id: str, query: ListQuery) -> Page:
        direction, operator = _list_direction(query, sort_key="created_at")
        conditions = "c.workspace_id = %s"
        params: list[object] = [workspace_id]
        if query.cursor is not None:
            conditions += f" AND (c.created_at, c.config_revision_id) {operator} (%s, %s)"
            params.extend(query.cursor)
        params.append(query.limit + 1)
        rows = self._connection.execute(
            "SELECT config_revision_id::text, scope_kind, scope_key, config_revision_number, "
            "       revision, content_hash, status, created_at "
            f"FROM controlplane.cp_config_revisions c WHERE {conditions} "
            f"ORDER BY c.created_at {direction}, c.config_revision_id {direction} LIMIT %s",
            tuple(params),
        ).fetchall()
        items = [
            {
                "config_revision_id": row[0],
                "scope_kind": row[1],
                "scope_key": row[2],
                "config_revision_number": row[3],
                "revision": row[4],
                "content_hash": row[5],
                "status": row[6],
                "created_at": row[7].isoformat() if hasattr(row[7], "isoformat") else row[7],
            }
            for row in rows
        ]
        return build_page(items, query=query, sort_field="created_at", id_field="config_revision_id")

    def stage_runs(self, *, workspace_id: str, query: ListQuery) -> Page:
        page = fetch_page(self._connection, STAGE_RUNS_SPEC, query, workspace_id=workspace_id)
        items = tuple({_FIELD_RENAMES.get(key, key): value for key, value in item.items()} for item in page.items)
        return Page(items=items, next_cursor=page.next_cursor)

    def sources(self, *, workspace_id: str, query: ListQuery) -> Page:
        raise CapabilityUnavailableError("sources")

    def articles(self, *, workspace_id: str, query: ListQuery) -> Page:
        raise CapabilityUnavailableError("articles")

    def events(self, *, workspace_id: str, query: ListQuery) -> Page:
        raise CapabilityUnavailableError("events")

    def media(self, *, workspace_id: str, query: ListQuery) -> Page:
        raise CapabilityUnavailableError("media")

    def hooks(self, *, workspace_id: str, query: ListQuery) -> Page:
        raise CapabilityUnavailableError("hooks")

    def sessions(self, *, workspace_id: str, query: ListQuery) -> Page:
        raise CapabilityUnavailableError("sessions")

    def logs(self, *, workspace_id: str, query: ListQuery) -> Page:
        raise CapabilityUnavailableError("logs")

    def capabilities(self, *, workspace_id: str, query: ListQuery) -> Page:
        raise CapabilityUnavailableError("capabilities")