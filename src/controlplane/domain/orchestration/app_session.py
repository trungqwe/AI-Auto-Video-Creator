"""G-14: AppSession bất biến và log_ref (CT-ORC-011; TST-E2E-013).

Pure domain: không I/O, không đồng hồ.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

INVALID_SESSION = 'INVALID_SESSION'
INVALID_CHECKPOINT = 'INVALID_CHECKPOINT'
INVALID_LOG_REF = 'INVALID_LOG_REF'
INVALID_COMPLETED_COUNT = 'INVALID_COMPLETED_COUNT'
OUTPUT_FOLDER_WITHOUT_VIDEO = 'OUTPUT_FOLDER_WITHOUT_VIDEO'
SESSION_ALREADY_CLOSED = 'SESSION_ALREADY_CLOSED'
SESSION_ID_REUSED = 'SESSION_ID_REUSED'


class AppSessionError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _is_text(value: object) -> bool:
    return isinstance(value, str) and value.strip() != ''


def _parse_aware(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    text = value[:-1] + '+00:00' if value.endswith('Z') else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


@dataclass(frozen=True)
class JobCheckpoint:
    job_id: str
    last_stage_run_id: str | None = None

    def __post_init__(self) -> None:
        if not _is_text(self.job_id):
            raise AppSessionError(INVALID_CHECKPOINT)
        if self.last_stage_run_id is not None and not _is_text(self.last_stage_run_id):
            raise AppSessionError(INVALID_CHECKPOINT)


@dataclass(frozen=True)
class SessionCheckpoint:
    batch_id: str
    job_checkpoints: tuple[JobCheckpoint, ...] = ()

    def __post_init__(self) -> None:
        if not _is_text(self.batch_id):
            raise AppSessionError(INVALID_CHECKPOINT)
        if not isinstance(self.job_checkpoints, tuple):
            raise AppSessionError(INVALID_CHECKPOINT)
        seen_jobs: set[str] = set()
        for jc in self.job_checkpoints:
            if not isinstance(jc, JobCheckpoint):
                raise AppSessionError(INVALID_CHECKPOINT)
            if jc.job_id in seen_jobs:
                raise AppSessionError(INVALID_CHECKPOINT)
            seen_jobs.add(jc.job_id)


@dataclass(frozen=True)
class OutputFolderIntent:
    session_id: str
    completed_video_count: int

    def __post_init__(self) -> None:
        if not _is_text(self.session_id):
            raise AppSessionError(INVALID_SESSION)
        if (
            isinstance(self.completed_video_count, bool)
            or not isinstance(self.completed_video_count, int)
            or self.completed_video_count < 1
        ):
            raise AppSessionError(OUTPUT_FOLDER_WITHOUT_VIDEO)


@dataclass(frozen=True)
class AppSession:
    session_id: str
    started_at: str
    desktop_identity: str
    log_scope: str
    ended_at: str | None = None
    checkpoint: SessionCheckpoint | None = None
    output_folder_intent: OutputFolderIntent | None = None

    def __post_init__(self) -> None:
        if not _is_text(self.session_id):
            raise AppSessionError(INVALID_SESSION)
        if not _is_text(self.desktop_identity):
            raise AppSessionError(INVALID_SESSION)
        if not _is_text(self.log_scope):
            raise AppSessionError(INVALID_SESSION)

        started = _parse_aware(self.started_at)
        if started is None:
            raise AppSessionError(INVALID_SESSION)

        if self.ended_at is not None:
            ended = _parse_aware(self.ended_at)
            if ended is None or ended < started:
                raise AppSessionError(INVALID_SESSION)

        if self.checkpoint is not None and not isinstance(self.checkpoint, SessionCheckpoint):
            raise AppSessionError(INVALID_SESSION)

        if self.output_folder_intent is not None:
            if not isinstance(self.output_folder_intent, OutputFolderIntent):
                raise AppSessionError(INVALID_SESSION)
            if self.ended_at is None:
                raise AppSessionError(INVALID_SESSION)
            if self.output_folder_intent.session_id != self.session_id:
                raise AppSessionError(INVALID_SESSION)


@dataclass(frozen=True)
class LogRef:
    session_id: str
    job_id: str
    stage: str
    correlation_id: str

    def __post_init__(self) -> None:
        if (
            not _is_text(self.session_id)
            or not _is_text(self.job_id)
            or not _is_text(self.stage)
            or not _is_text(self.correlation_id)
        ):
            raise AppSessionError(INVALID_LOG_REF)


def close_session(session: AppSession, completed_video_count: int, *, ended_at: str) -> AppSession:
    if not isinstance(session, AppSession):
        raise TypeError('session must be AppSession')
    if session.ended_at is not None:
        raise AppSessionError(SESSION_ALREADY_CLOSED)
    if (
        isinstance(completed_video_count, bool)
        or not isinstance(completed_video_count, int)
        or completed_video_count < 0
    ):
        raise AppSessionError(INVALID_COMPLETED_COUNT)

    intent = (
        OutputFolderIntent(session.session_id, completed_video_count)
        if completed_video_count > 0
        else None
    )
    return replace(session, ended_at=ended_at, output_folder_intent=intent)


def resume_session(
    previous: AppSession,
    *,
    new_session_id: str,
    started_at: str,
    desktop_identity: str,
    log_scope: str,
) -> AppSession:
    if not isinstance(previous, AppSession):
        raise TypeError('previous must be AppSession')
    if new_session_id == previous.session_id:
        raise AppSessionError(SESSION_ID_REUSED)

    return AppSession(
        session_id=new_session_id,
        started_at=started_at,
        desktop_identity=desktop_identity,
        log_scope=log_scope,
        ended_at=None,
        checkpoint=previous.checkpoint,
        output_folder_intent=None,
    )


def make_log_ref(
    session: AppSession,
    *,
    job_id: str,
    stage: str,
    correlation_id: str,
) -> LogRef:
    if not isinstance(session, AppSession):
        raise TypeError('session must be AppSession')
    return LogRef(session.session_id, job_id, stage, correlation_id)


__all__ = [
    'INVALID_SESSION',
    'INVALID_CHECKPOINT',
    'INVALID_LOG_REF',
    'INVALID_COMPLETED_COUNT',
    'OUTPUT_FOLDER_WITHOUT_VIDEO',
    'SESSION_ALREADY_CLOSED',
    'SESSION_ID_REUSED',
    'AppSession',
    'AppSessionError',
    'JobCheckpoint',
    'LogRef',
    'OutputFolderIntent',
    'SessionCheckpoint',
    'close_session',
    'make_log_ref',
    'resume_session',
]
