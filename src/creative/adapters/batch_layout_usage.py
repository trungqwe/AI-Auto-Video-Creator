"""PRS-LAYOUT-QUOTA-FIX1: the layouts the other jobs of a plan's batch already hold, read inside the transaction that stores the plan,
after a transaction-scoped advisory lock on the batch.

The usage the activity inputs read before the model call (PostgresLayoutUsage of the wiring) misses the plans other jobs store while
the model runs, about a minute; with six jobs in flight two plans could both take the last free place of a layout (batch 875e2e7d:
HERO_STRIP 41 of 100 against a cap of 40). Plans of one batch are stored one at a time under pg_advisory_xact_lock, and the count is
read after the lock is held: under READ COMMITTED each statement sees every plan committed before it, so the pipeline checks the cap
again against the true usage before the plan row is written, and the lock is released by the commit that writes it.

The count is the one of the activity inputs: LAYOUT_TARGET_SQL and LAYOUT_USAGE_SQL keep the text of controlplane.api.wiring.creative
(a test keeps them equal); the job comes from the production plan id plan:<job_id>:r<revision> the activity inputs build.
coveredIds: FR-PRS-005
"""
from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from creative.domain.layout_choice import LAYOUT_KEYS

PLAN_ID = re.compile(r'plan:(.+):r([0-9]+)')
LOCK_NAMESPACE = 'creative.layout_cap:'
LAYOUT_TARGET_SQL = (
    'SELECT b.target_count FROM controlplane.cp_production_batches b JOIN controlplane.cp_video_jobs j '
    'ON j.workspace_id = b.workspace_id AND j.batch_id = b.batch_id WHERE j.workspace_id = %s::uuid AND j.job_id = %s'
)
LAYOUT_LOCK_SQL = (
    'SELECT pg_advisory_xact_lock(hashtextextended(%s::text || j.batch_id, 0)) FROM controlplane.cp_video_jobs j '
    'WHERE j.workspace_id = %s::uuid AND j.job_id = %s'
)
LAYOUT_USAGE_SQL = (
    "SELECT DISTINCT ON (j.job_id) p.payload->'layout_choice'->>'layout_key' FROM controlplane.cp_video_jobs j "
    "JOIN controlplane.cp_production_plans p ON p.workspace_id = j.workspace_id AND p.production_plan_id LIKE 'plan:' || j.job_id || ':r%%' "
    "WHERE j.workspace_id = %s::uuid AND j.batch_id = (SELECT batch_id FROM controlplane.cp_video_jobs WHERE workspace_id = %s::uuid AND job_id = %s) "
    "AND j.job_id <> %s AND j.status <> 'FAILED_FINAL' ORDER BY j.job_id, p.created_at DESC"
)


def plan_job_id(production_plan_id: str) -> str | None:
    """job_id of a production plan id plan:<job_id>:r<revision>; None for any other id."""
    found = PLAN_ID.fullmatch(production_plan_id) if isinstance(production_plan_id, str) else None
    return found.group(1) if found else None


class PostgresBatchLayoutUsage:
    """Batch layout usage of the creative unit of work; `source` returns the connection of the open transaction."""

    def __init__(self, source: Callable[[], Any], workspace_id: str) -> None:
        self._source = source
        self._workspace_id = workspace_id

    def locked_usage(self, production_plan_id: str) -> tuple[dict[str, int], int] | None:
        """Takes the advisory lock of the plan's batch for the rest of the transaction, then returns (layout key -> plans of the other
        jobs of the batch, failed jobs left out, latest plan of each job; target_count of the batch). None without a lock when the plan
        id names no job or the job has no batch row."""
        job_id = plan_job_id(production_plan_id)
        if job_id is None:
            return None
        connection = self._source()
        target = connection.execute(LAYOUT_TARGET_SQL, (self._workspace_id, job_id)).fetchone()
        if target is None:
            return None
        connection.execute(LAYOUT_LOCK_SQL, (LOCK_NAMESPACE, self._workspace_id, job_id)).fetchall()
        rows = connection.execute(LAYOUT_USAGE_SQL, (self._workspace_id, self._workspace_id, job_id, job_id)).fetchall()
        used: dict[str, int] = {}
        for (key,) in rows:
            if key in LAYOUT_KEYS:
                used[key] = used.get(key, 0) + 1
        return used, int(target[0])


__all__ = ['LAYOUT_LOCK_SQL', 'LAYOUT_TARGET_SQL', 'LAYOUT_USAGE_SQL', 'LOCK_NAMESPACE', 'PostgresBatchLayoutUsage', 'plan_job_id']
