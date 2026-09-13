"""Media ownership port used by the M1-P1 completion proof."""

from __future__ import annotations

import uuid
from datetime import datetime

import psycopg


class PostgresMediaUsageOwnerPort:
    """Persist C-owned usage rows through the caller's transaction."""

    def record_usages(
        self,
        connection: psycopg.Connection,
        *,
        workspace_id: str,
        completion_id: str,
        job_id: str,
        usages: list[dict[str, object]],
        completed_at: datetime,
    ) -> None:
        for usage in usages:
            identity = ":".join(
                (
                    workspace_id,
                    completion_id,
                    str(usage["media_id"]),
                    str(usage["artifact_id"]),
                    str(usage["role"]),
                    str(usage["time_range"]),
                )
            )
            usage_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"m1-p1-usage:{identity}"))
            connection.execute(
                """
                INSERT INTO media_usages (
                    workspace_id, usage_id, completion_id, job_id, media_id,
                    artifact_id, role, time_range, transform_ref,
                    selection_rationale, completed_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    workspace_id,
                    usage_id,
                    completion_id,
                    job_id,
                    usage["media_id"],
                    usage["artifact_id"],
                    usage["role"],
                    usage["time_range"],
                    usage["transform_ref"],
                    usage["selection_rationale"],
                    completed_at,
                ),
            )
