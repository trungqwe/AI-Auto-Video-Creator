"""CollectionCheckpoint: A-internal cursor record that only advances over durably committed items (A-RULE-009)."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum


class CheckpointCompleteness(str, Enum):
    PARTIAL = "PARTIAL"
    COMPLETE = "COMPLETE"


class CheckpointRejected(Exception):
    """Fail-closed rejection; ``code`` is a stable machine-readable reason."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class AdapterCheckpointSemantics:
    """Cursor semantics declared by an adapter revision; a semantics change bumps ``checkpoint_version``."""

    adapter_type: str
    adapter_revision: str
    checkpoint_version: int


@dataclass(frozen=True)
class CollectionCheckpoint:
    """Per-source checkpoint.

    ``item_ids`` lists, in adapter order, the items this revision passes over since the previous
    revision; ``cursor`` is the adapter cursor/watermark after the last of them.
    """

    checkpoint_version: int
    revision: int
    source_id: str
    source_revision: int
    adapter_type: str
    adapter_revision: str
    cursor: str
    item_ids: tuple[str, ...]
    run_id: str
    attempt_id: str
    execution_generation: int
    completeness: CheckpointCompleteness
    recorded_at: str
    fingerprint: str

    def __post_init__(self) -> None:
        for name in (
            "source_id", "adapter_type", "adapter_revision", "cursor", "run_id", "attempt_id", "recorded_at", "fingerprint",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise CheckpointRejected("CHECKPOINT_INVALID", f"{name} must be a non-empty string")
        for name, minimum in (
            ("checkpoint_version", 1), ("revision", 1), ("source_revision", 1), ("execution_generation", 0),
        ):
            value = getattr(self, name)
            if type(value) is not int or value < minimum:
                raise CheckpointRejected("CHECKPOINT_INVALID", f"{name} must be an int >= {minimum}")
        if not isinstance(self.item_ids, tuple) or not all(isinstance(item, str) and item for item in self.item_ids):
            raise CheckpointRejected("CHECKPOINT_INVALID", "item_ids must be a tuple of non-empty strings")
        if len(set(self.item_ids)) != len(self.item_ids):
            raise CheckpointRejected("CHECKPOINT_INVALID", "item_ids must not repeat")
        if not isinstance(self.completeness, CheckpointCompleteness):
            raise CheckpointRejected("CHECKPOINT_INVALID", "completeness must be a CheckpointCompleteness")


def compute_checkpoint_fingerprint(checkpoint: CollectionCheckpoint) -> str:
    payload = {f.name: getattr(checkpoint, f.name) for f in dataclasses.fields(checkpoint) if f.name != "fingerprint"}
    payload["completeness"] = checkpoint.completeness.value
    payload["item_ids"] = list(checkpoint.item_ids)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def seal_checkpoint(checkpoint: CollectionCheckpoint) -> CollectionCheckpoint:
    return dataclasses.replace(checkpoint, fingerprint=compute_checkpoint_fingerprint(checkpoint))


def _ensure_sealed(checkpoint: CollectionCheckpoint) -> None:
    if checkpoint.fingerprint != compute_checkpoint_fingerprint(checkpoint):
        raise CheckpointRejected(
            "CHECKPOINT_FINGERPRINT_MISMATCH", f"revision {checkpoint.revision} content does not match its fingerprint"
        )


def _ensure_same_lineage(
    checkpoint: CollectionCheckpoint, source_id: str, adapter_type: str, checkpoint_version: int
) -> None:
    if checkpoint.source_id != source_id:
        raise CheckpointRejected("CHECKPOINT_SOURCE_MISMATCH", f"{checkpoint.source_id} != {source_id}")
    if checkpoint.adapter_type != adapter_type:
        raise CheckpointRejected("CHECKPOINT_ADAPTER_MISMATCH", f"{checkpoint.adapter_type} != {adapter_type}")
    if checkpoint.checkpoint_version != checkpoint_version:
        raise CheckpointRejected(
            "CHECKPOINT_VERSION_MISMATCH",
            f"{checkpoint.checkpoint_version} != {checkpoint_version}; cursor semantics changed, migrate explicitly",
        )


def ensure_checkpoint_loadable(
    checkpoint: CollectionCheckpoint, *, source_id: str, semantics: AdapterCheckpointSemantics
) -> CollectionCheckpoint:
    """Reject a stored checkpoint whose source, adapter or cursor semantics differ from the loading adapter."""
    _ensure_sealed(checkpoint)
    _ensure_same_lineage(checkpoint, source_id, semantics.adapter_type, semantics.checkpoint_version)
    return checkpoint


def advance_checkpoint(
    current: CollectionCheckpoint | None, durable_item_ids: Iterable[str], proposed: CollectionCheckpoint
) -> CollectionCheckpoint:
    """Return ``proposed`` only if it may replace ``current``.

    ``durable_item_ids`` are the ids whose unit of work has committed; every id in ``proposed.item_ids``
    must be among them. Otherwise raise ``CheckpointRejected`` and leave ``current`` in force.
    """
    if isinstance(durable_item_ids, (str, bytes)):
        raise CheckpointRejected("CHECKPOINT_INVALID", "durable_item_ids must be a collection of ids")
    durable = frozenset(durable_item_ids)
    _ensure_sealed(proposed)
    if current is None:
        if proposed.revision != 1:
            raise CheckpointRejected("CHECKPOINT_REVISION_CONFLICT", f"first revision must be 1, got {proposed.revision}")
    else:
        _ensure_sealed(current)
        _ensure_same_lineage(proposed, current.source_id, current.adapter_type, current.checkpoint_version)
        if proposed.execution_generation < current.execution_generation:
            raise CheckpointRejected(
                "CHECKPOINT_STALE_GENERATION", f"{proposed.execution_generation} < {current.execution_generation}"
            )
        if proposed.revision != current.revision + 1:
            raise CheckpointRejected(
                "CHECKPOINT_REVISION_CONFLICT", f"expected {current.revision + 1}, got {proposed.revision}"
            )
    missing = [item for item in proposed.item_ids if item not in durable]
    if missing:
        raise CheckpointRejected("CHECKPOINT_ITEM_NOT_DURABLE", ", ".join(missing))
    return proposed
