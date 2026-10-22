from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from controlplane.domain.orchestration.retry_policy import RetryPolicy
from controlplane.domain.orchestration.workflow_catalog import TaskQueue

NOT_READY = 'NOT_READY'
READY = 'READY'
PARAM_START_TO_CLOSE = 'workflow.start_to_close_seconds'
PARAM_HEARTBEAT = 'workflow.heartbeat_seconds'
PARAM_RETRY = 'workflow.retry'
PARAM_SCHEDULE = 'workflow.schedule'
PARAM_CAPABILITY_POLL = 'ai.quota_wait_poll_seconds'
PARAM_PROFILE_REVISION = 'meta.revision'


def _require_positive_number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f'{name} must be a number')
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f'{name} must be positive and finite')
    return float(value)


@dataclass(frozen=True)
class WorkflowSettings:
    start_to_close_seconds: Mapping[str, float]
    heartbeat_seconds: float
    retry: RetryPolicy
    capability_poll_seconds: float
    retry_policy_ref: str
    cloud_schedule_enabled: bool

    def to_payload(self) -> dict[str, Any]:
        return {
            'start_to_close_seconds': dict(self.start_to_close_seconds),
            'heartbeat_seconds': self.heartbeat_seconds,
            'retry': {
                'max_attempts': self.retry.max_attempts,
                'initial_delay_seconds': self.retry.initial_delay_seconds,
                'multiplier': self.retry.multiplier,
                'max_delay_seconds': self.retry.max_delay_seconds,
            },
            'capability_poll_seconds': self.capability_poll_seconds,
            'retry_policy_ref': self.retry_policy_ref,
            'cloud_schedule_enabled': self.cloud_schedule_enabled,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> WorkflowSettings:
        if not isinstance(payload, Mapping):
            raise TypeError('payload must be a mapping')
        for key in ('start_to_close_seconds', 'heartbeat_seconds', 'retry', 'capability_poll_seconds', 'retry_policy_ref', 'cloud_schedule_enabled'):
            if key not in payload:
                raise ValueError(f'missing payload key: {key}')
        raw_stc = payload['start_to_close_seconds']
        if not isinstance(raw_stc, Mapping):
            raise ValueError('start_to_close_seconds must be a mapping')
        stc: dict[str, float] = {}
        for queue in TaskQueue:
            if queue.value not in raw_stc:
                raise ValueError(f'missing queue timeout: {queue}')
            stc[queue.value] = _require_positive_number(f'start_to_close_seconds[{queue.value}]', raw_stc[queue.value])
        hb = _require_positive_number('heartbeat_seconds', payload['heartbeat_seconds'])
        cp = _require_positive_number('capability_poll_seconds', payload['capability_poll_seconds'])
        raw_retry = payload['retry']
        if not isinstance(raw_retry, Mapping):
            raise ValueError('retry must be a mapping')
        retry = RetryPolicy(
            max_attempts=raw_retry['max_attempts'],
            initial_delay_seconds=raw_retry['initial_delay_seconds'],
            multiplier=raw_retry['multiplier'],
            max_delay_seconds=raw_retry['max_delay_seconds'],
        )
        ref = payload['retry_policy_ref']
        if not isinstance(ref, str) or not ref.strip():
            raise ValueError('retry_policy_ref must be a non-empty string')
        sched = payload['cloud_schedule_enabled']
        if type(sched) is not bool:
            raise TypeError('cloud_schedule_enabled must be bool')
        return cls(
            start_to_close_seconds=stc,
            heartbeat_seconds=hb,
            retry=retry,
            capability_poll_seconds=cp,
            retry_policy_ref=ref,
            cloud_schedule_enabled=sched,
        )


def settings_from_parameters(parameters: Mapping[str, Any]) -> WorkflowSettings:
    if not isinstance(parameters, Mapping):
        raise TypeError('parameters must be a mapping')
    for key in (
        PARAM_START_TO_CLOSE,
        PARAM_HEARTBEAT,
        PARAM_RETRY,
        PARAM_SCHEDULE,
        PARAM_CAPABILITY_POLL,
        PARAM_PROFILE_REVISION,
    ):
        if key not in parameters:
            raise ValueError(f'missing workflow parameter: {key}')

    raw_stc = parameters[PARAM_START_TO_CLOSE]
    if not isinstance(raw_stc, Mapping):
        raise ValueError(f'missing workflow parameter: {PARAM_START_TO_CLOSE}')
    stc: dict[str, float] = {}
    for queue in TaskQueue:
        if queue.value not in raw_stc:
            raise ValueError(f'missing queue timeout: {queue}')
        stc[queue.value] = _require_positive_number(f'timeout for {queue.value}', raw_stc[queue.value])

    hb = _require_positive_number('heartbeat_seconds', parameters[PARAM_HEARTBEAT])
    cp = _require_positive_number('capability_poll_seconds', parameters[PARAM_CAPABILITY_POLL])

    raw_retry = parameters[PARAM_RETRY]
    if not isinstance(raw_retry, Mapping):
        raise ValueError(f'missing workflow parameter: {PARAM_RETRY}')
    retry = RetryPolicy(
        max_attempts=raw_retry['maximum_attempts'],
        initial_delay_seconds=raw_retry['initial_interval_seconds'],
        multiplier=raw_retry['backoff_coefficient'],
        max_delay_seconds=raw_retry['maximum_interval_seconds'],
    )

    raw_sched = parameters[PARAM_SCHEDULE]
    if not isinstance(raw_sched, Mapping) or 'cloud_schedule_enabled' not in raw_sched or type(raw_sched['cloud_schedule_enabled']) is not bool:
        raise ValueError(f'missing workflow parameter: {PARAM_SCHEDULE}')
    cloud_schedule_enabled = raw_sched['cloud_schedule_enabled']

    rev = parameters[PARAM_PROFILE_REVISION]
    if type(rev) is not int or rev <= 0:
        raise ValueError('meta.revision must be a positive int')
    retry_policy_ref = f'profile-{rev}:workflow.retry'

    return WorkflowSettings(
        start_to_close_seconds=stc,
        heartbeat_seconds=hb,
        retry=retry,
        capability_poll_seconds=cp,
        retry_policy_ref=retry_policy_ref,
        cloud_schedule_enabled=cloud_schedule_enabled,
    )


def start_to_close_for(settings: WorkflowSettings, queue: TaskQueue) -> float:
    return settings.start_to_close_seconds[queue.value]


def schedule_state(settings: WorkflowSettings, *, timezone_approved: bool) -> str:
    if type(timezone_approved) is not bool:
        raise TypeError('timezone_approved must be bool')
    if timezone_approved is True and settings.cloud_schedule_enabled is True:
        return READY
    return NOT_READY


__all__ = [
    'NOT_READY',
    'PARAM_CAPABILITY_POLL',
    'PARAM_HEARTBEAT',
    'PARAM_PROFILE_REVISION',
    'PARAM_RETRY',
    'PARAM_SCHEDULE',
    'PARAM_START_TO_CLOSE',
    'READY',
    'WorkflowSettings',
    'schedule_state',
    'settings_from_parameters',
    'start_to_close_for',
]
