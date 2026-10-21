"""Domain entity and database row/JSON codecs for source ingestion persistence."""
from __future__ import annotations

import dataclasses
import datetime
from collections.abc import Iterable, Mapping
from typing import Any

from source_ingestion.domain.checkpoint import CheckpointCompleteness, CollectionCheckpoint
from source_ingestion.domain.collection_run import (
    AttemptOutcome,
    CollectionAttempt,
    CollectionPurpose,
    CollectionRun,
    ReconciliationRecord,
    ReconciliationResult,
    RetryPolicy,
    RunStatus,
    TerminalDecision,
    TerminalReason,
)
from source_ingestion.domain.source import Source, SourceStatus
from source_ingestion.domain.source_candidate import CandidateStatus, SourceCandidate


def iso(dt: datetime.datetime) -> str:
    return dt.isoformat()


def parse_dt(text: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(text)


def source_payload(s: Source) -> dict[str, Any]:
    return {
        'name': s.name,
        'source_kind': s.source_kind,
        'tier': s.tier,
        'topics': sorted(s.topics),
        'notes': s.notes,
        'admin_metadata': [list(p) for p in s.admin_metadata],
        'status_reason': s.status_reason,
        'previous_status': s.previous_status.value if s.previous_status is not None else None,
        'policy_revision': s.policy_revision,
        'created_by': s.created_by,
        'created_at': iso(s.created_at),
        'updated_by': s.updated_by,
        'updated_at': iso(s.updated_at),
    }


def source_from_row(
    workspace_id: str,
    source_id: str,
    canonical_locator: str,
    status: str,
    revision: int,
    payload: Mapping[str, Any],
) -> Source:
    admin_meta = tuple(tuple(p) for p in payload.get('admin_metadata', []))
    prev_status = payload.get('previous_status')
    return Source(
        source_id=source_id,
        workspace_id=workspace_id,
        canonical_locator=canonical_locator,
        name=payload['name'],
        source_kind=payload['source_kind'],
        tier=payload['tier'],
        topics=frozenset(payload.get('topics', [])),
        notes=payload.get('notes', ''),
        admin_metadata=admin_meta,
        status=SourceStatus(status),
        status_reason=payload.get('status_reason', ''),
        previous_status=SourceStatus(prev_status) if prev_status is not None else None,
        policy_revision=payload['policy_revision'],
        revision=revision,
        created_by=payload['created_by'],
        created_at=parse_dt(payload['created_at']),
        updated_by=payload['updated_by'],
        updated_at=parse_dt(payload['updated_at']),
    )


def candidate_payload(c: SourceCandidate) -> dict[str, Any]:
    return {
        'observed_locator': c.observed_locator,
        'discovery_method': c.discovery_method,
        'discovery_evidence': c.discovery_evidence,
        'source_kind_candidates': list(c.source_kind_candidates),
        'topic_candidates': list(c.topic_candidates),
        'updated_by': c.updated_by,
        'updated_at': iso(c.updated_at),
        'matched_source_ref': c.matched_source_ref,
        'matched_tombstone_ref': c.matched_tombstone_ref,
        'registered_source_ref': c.registered_source_ref,
        'source_kind': c.source_kind,
        'topics': list(c.topics),
        'tier': c.tier,
        'policy_revision': c.policy_revision,
        'reason': c.reason,
    }


def candidate_from_row(
    workspace_id: str,
    candidate_id: str,
    canonical_locator: str,
    status: str,
    revision: int,
    payload: Mapping[str, Any],
) -> SourceCandidate:
    return SourceCandidate(
        candidate_id=candidate_id,
        workspace_id=workspace_id,
        observed_locator=payload['observed_locator'],
        canonical_locator=canonical_locator,
        discovery_method=payload['discovery_method'],
        discovery_evidence=payload['discovery_evidence'],
        source_kind_candidates=tuple(payload.get('source_kind_candidates', ())),
        topic_candidates=tuple(payload.get('topic_candidates', ())),
        status=CandidateStatus(status),
        revision=revision,
        updated_by=payload['updated_by'],
        updated_at=parse_dt(payload['updated_at']),
        matched_source_ref=payload.get('matched_source_ref'),
        matched_tombstone_ref=payload.get('matched_tombstone_ref'),
        registered_source_ref=payload.get('registered_source_ref'),
        source_kind=payload.get('source_kind'),
        topics=tuple(payload.get('topics', ())),
        tier=payload.get('tier'),
        policy_revision=payload.get('policy_revision'),
        reason=payload.get('reason'),
    )


def run_payload(run: CollectionRun) -> dict[str, Any]:
    td = run.terminal_decision
    return {
        'retry_policy': {
            'revision': run.retry_policy.revision,
            'max_attempts': run.retry_policy.max_attempts,
        },
        'committed_package_count': run.committed_package_count,
        'checkpoint_ref': run.checkpoint_ref,
        'terminal_decision': {
            'status': td.status.value,
            'reason': td.reason.value,
            'policy_revision': td.policy_revision,
            'checkpoint_ref': td.checkpoint_ref,
        } if td is not None else None,
        'warnings': list(run.warnings),
        'reconciliations': [
            {
                'attempt_no': r.attempt_no,
                'result': r.result.value,
                'evidence_ref': r.evidence_ref,
            }
            for r in run.reconciliations
        ],
    }


def run_from_rows(
    workspace_id: str,
    run_id: str,
    source_id: str,
    run_kind: str,
    business_date: datetime.date | str,
    status: str,
    payload: Mapping[str, Any],
    attempts: Iterable[tuple[int, str]],
) -> CollectionRun:
    b_date = (
        datetime.date.fromisoformat(business_date)
        if isinstance(business_date, str)
        else business_date
    )
    rp_raw = payload['retry_policy']
    retry_policy = RetryPolicy(
        revision=rp_raw['revision'],
        max_attempts=rp_raw['max_attempts'],
    )
    att_list = tuple(
        CollectionAttempt(attempt_no=idx, outcome=AttemptOutcome(outcome_text))
        for idx, outcome_text in attempts
    )
    reconciliations = tuple(
        ReconciliationRecord(
            attempt_no=r['attempt_no'],
            result=ReconciliationResult(r['result']),
            evidence_ref=r['evidence_ref'],
        )
        for r in payload.get('reconciliations', ())
    )
    td_raw = payload.get('terminal_decision')
    td = None
    if td_raw is not None:
        td = TerminalDecision(
            status=RunStatus(td_raw['status']),
            reason=TerminalReason(td_raw['reason']),
            policy_revision=td_raw['policy_revision'],
            checkpoint_ref=td_raw.get('checkpoint_ref'),
        )
    return CollectionRun(
        run_id=run_id,
        workspace_id=workspace_id,
        source_id=source_id,
        business_date=b_date,
        purpose=CollectionPurpose(run_kind),
        retry_policy=retry_policy,
        status=RunStatus(status),
        attempts=att_list,
        reconciliations=reconciliations,
        committed_package_count=payload.get('committed_package_count', 0),
        checkpoint_ref=payload.get('checkpoint_ref'),
        terminal_decision=td,
        warnings=tuple(payload.get('warnings', ())),
    )


def checkpoint_payload(cp: CollectionCheckpoint) -> dict[str, Any]:
    data = {}
    for f in dataclasses.fields(cp):
        val = getattr(cp, f.name)
        if f.name == 'item_ids':
            data[f.name] = list(val)
        elif f.name == 'completeness':
            data[f.name] = val.value
        else:
            data[f.name] = val
    return data


def checkpoint_from_payload(payload: Mapping[str, Any]) -> CollectionCheckpoint:
    kwargs = dict(payload)
    kwargs['item_ids'] = tuple(kwargs['item_ids'])
    kwargs['completeness'] = CheckpointCompleteness(kwargs['completeness'])
    return CollectionCheckpoint(**kwargs)
