"""J-05: resolve configuration bundle with provenance (CT-CFG-002, D8-J-10).

Pure application function: no I/O, no clock, no DB access and no mutation of its inputs. ConfigRevision (P5A, 9 fields) is only read; effective_at travels in the EffectiveConfigRevision wrapper.
"""
from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from controlplane.application.config_security.publish_plan import SCOPE_KINDS, _contains_sensitive_key
from controlplane.domain.config_security import ConfigRevision, ConfigRevisionStatus

MERGE_ORDER = ('workspace', 'module', 'provider', 'preset', 'policy')
PROMPT_KIND = 'prompt'
SNAPSHOT_STATES = frozenset({'NOT_COMMITTED', 'COMMITTED'})


class MissingPinError(Exception):
    """COMMITTED snapshot has no usable pinned revision for a required scope."""


class PinnedRevisionInvalidatedError(Exception):
    """The pinned revision of a required scope is INVALIDATED."""


class MissingScopeError(Exception):
    """No applicable PUBLISHED revision exists for a required scope."""


class BundleSecretError(Exception):
    """A selected revision payload contains a sensitive key at some depth."""


@dataclass(frozen=True)
class EffectiveConfigRevision:
    revision: ConfigRevision
    effective_at: datetime | None


    def __post_init__(self) -> None:
        if self.effective_at is not None and self.effective_at.utcoffset() is None:
            raise ValueError('naive_effective_at')



@dataclass(frozen=True)
class BundleRequest:
    workspace_id: str
    job_ref: str
    stage_ref: str
    evaluation_time: datetime
    required_scopes: tuple[tuple[str, str], ...]
    snapshot_state: str
    pinned_revision_ids: Mapping[tuple[str, str], str] = field(default_factory=dict)


@dataclass(frozen=True)
class ConfigBundle:
    revision_refs: tuple[str, ...]
    values: dict[str, Any]
    provenance: dict[str, str]
    bundle_fingerprint: str
    warnings: tuple[str, ...]




_RANK = {kind: index for index, kind in enumerate((*MERGE_ORDER, PROMPT_KIND))}


def _validate_request(request: BundleRequest) -> None:
    if request.snapshot_state not in SNAPSHOT_STATES:
        raise ValueError('invalid_snapshot_state')
    if request.evaluation_time.utcoffset() is None:
        raise ValueError('naive_evaluation_time')
    if any(kind not in SCOPE_KINDS for kind, _ in request.required_scopes):
        raise ValueError('invalid_scope_kind')


def _select_pinned(candidates: Sequence[EffectiveConfigRevision], pin: str | None) -> ConfigRevision:
    pinned = next((item.revision for item in candidates if item.revision.config_revision_id == pin), None)
    if pin is None or pinned is None:
        raise MissingPinError('missing_pin')
    if pinned.status is ConfigRevisionStatus.INVALIDATED:
        raise PinnedRevisionInvalidatedError('pinned_revision_invalidated')
    if pinned.status is ConfigRevisionStatus.DRAFT:
        raise MissingPinError('pinned_revision_not_published')
    return pinned


def _select_current(candidates: Sequence[EffectiveConfigRevision], evaluation_time: datetime) -> ConfigRevision:
    effective = [
        item.revision for item in candidates
        if item.revision.status is ConfigRevisionStatus.PUBLISHED and (item.effective_at is None or item.effective_at <= evaluation_time)
    ]
    if not effective:
        raise MissingScopeError('missing_scope')
    return max(effective, key=lambda revision: revision.config_revision_number)



def _drop_provenance(provenance: dict[tuple[str, ...], str], path: tuple[str, ...]) -> None:
    for key in [key for key in provenance if key[:len(path)] == path]:
        del provenance[key]


def _record_provenance(provenance: dict[tuple[str, ...], str], path: tuple[str, ...], value: object, revision_id: str) -> None:
    if isinstance(value, dict) and value:
        for key, child in value.items():
            _record_provenance(provenance, (*path, str(key)), child, revision_id)
    else:
        provenance[path] = revision_id


def _overlay(target: dict[str, Any], source: Mapping[str, Any], path: tuple[str, ...], revision_id: str, provenance: dict[tuple[str, ...], str]) -> None:
    for key, value in source.items():
        child_path = (*path, str(key))
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _overlay(target[key], value, child_path, revision_id, provenance)
            continue
        _drop_provenance(provenance, child_path)
        target[key] = copy.deepcopy(value)
        _record_provenance(provenance, child_path, target[key], revision_id)


def _fingerprint(revision_refs: tuple[str, ...], values: dict[str, Any]) -> str:
    canonical = json.dumps({'revision_refs': list(revision_refs), 'values': values}, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()



def resolve_bundle(revisions: Sequence[EffectiveConfigRevision], request: BundleRequest) -> ConfigBundle:
    """Resolve the configuration bundle of one job stage (CT-CFG-002); never touches `revisions` or `request`.

    COMMITTED uses exactly the pinned revision of each required scope (newer revisions are ignored, INV-004). NOT_COMMITTED picks the highest
    config_revision_number among PUBLISHED revisions whose effective_at is None or not later than evaluation_time. Revisions of other workspaces
    are filtered out silently. Layers merge workspace < module < provider < preset < policy (D8-J-10, deep dict merge); same-kind scopes merge in
    scope_key order; prompt revisions only appear in revision_refs. Provenance maps the dotted path of every leaf value to the config_revision_id
    that supplied it. A sensitive key in any selected payload raises BundleSecretError.
    """
    _validate_request(request)
    workspace_revisions = [item for item in revisions if item.revision.workspace_id == request.workspace_id]
    scopes = sorted(set(request.required_scopes), key=lambda scope: (_RANK[scope[0]], scope[1]))
    selected: list[ConfigRevision] = []
    for scope in scopes:
        candidates = [item for item in workspace_revisions if (item.revision.scope_kind, item.revision.scope_key) == scope]
        if request.snapshot_state == 'COMMITTED':
            selected.append(_select_pinned(candidates, request.pinned_revision_ids.get(scope)))
        else:
            selected.append(_select_current(candidates, request.evaluation_time))
    if any(_contains_sensitive_key(revision.payload) for revision in selected):
        raise BundleSecretError('secret_in_bundle')
    values: dict[str, Any] = {}
    provenance_by_path: dict[tuple[str, ...], str] = {}
    for revision in selected:
        if revision.scope_kind != PROMPT_KIND:
            _overlay(values, revision.payload, (), revision.config_revision_id, provenance_by_path)
    revision_refs = tuple(sorted(revision.config_revision_id for revision in selected))
    provenance = {'.'.join(path): revision_id for path, revision_id in sorted(provenance_by_path.items())}
    return ConfigBundle(revision_refs, values, provenance, _fingerprint(revision_refs, values), ())
