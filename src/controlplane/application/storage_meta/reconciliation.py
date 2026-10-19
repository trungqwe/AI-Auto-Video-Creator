"""I-10: đối soát DB, cloud, journal và ledger sau restart/restore theo recovery epoch (CT-STO-009, INV-016)."""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum


class ReconcileCode(StrEnum):
    CLOUD_OBJECT_MISSING = 'CLOUD_OBJECT_MISSING'
    HASH_MISMATCH = 'HASH_MISMATCH'
    ORPHAN_PROVIDER_OBJECT = 'ORPHAN_PROVIDER_OBJECT'
    DUPLICATE_PROVIDER_OBJECT = 'DUPLICATE_PROVIDER_OBJECT'
    JOURNAL_GENERATION_MISMATCH = 'JOURNAL_GENERATION_MISMATCH'
    STALE_EPOCH_ENTRY = 'STALE_EPOCH_ENTRY'
    COMPLETION_WITHOUT_VERIFIED_OUTPUT = 'COMPLETION_WITHOUT_VERIFIED_OUTPUT'


class ReconcileAction(StrEnum):
    REISSUE_UNDER_NEW_EPOCH = 'REISSUE_UNDER_NEW_EPOCH'


@dataclass(frozen=True)
class VersionRecord:
    artifact_version_id: str
    content_sha256: str
    size_bytes: int


@dataclass(frozen=True)
class CloudLocationRecord:
    location_id: str
    artifact_version_id: str
    provider_object_ref: str


@dataclass(frozen=True)
class CloudObjectObservation:
    provider_object_ref: str
    observed_sha256: str | None
    observed_size_bytes: int | None


@dataclass(frozen=True)
class JournalEntry:
    operation_key: str
    artifact_version_id: str
    generation: int
    recovery_epoch: str


@dataclass(frozen=True)
class CompletionRecord:
    video_job_id: str
    output_artifact_version_id: str
    output_sha256: str
    cloud_location_ref: str


@dataclass(frozen=True)
class ReconcileSnapshot:
    current_recovery_epoch: str
    versions: tuple[VersionRecord, ...] = ()
    cloud_locations: tuple[CloudLocationRecord, ...] = ()
    cloud_objects: tuple[CloudObjectObservation, ...] = ()
    journal_entries: tuple[JournalEntry, ...] = ()
    stage_generations: Mapping[str, int] = field(default_factory=dict)
    completions: tuple[CompletionRecord, ...] = ()


@dataclass(frozen=True)
class ReconcileFinding:
    code: ReconcileCode
    ref: str
    action: ReconcileAction | None = None


def _matches(version: VersionRecord, observed: CloudObjectObservation) -> bool:
    return observed.observed_sha256 == version.content_sha256 and observed.observed_size_bytes == version.size_bytes


def _output_verified(
    completion: CompletionRecord,
    versions: dict[str, VersionRecord],
    locations: dict[str, CloudLocationRecord],
    observed: dict[str, list[CloudObjectObservation]],
) -> bool:
    location = locations.get(completion.cloud_location_ref)
    version = versions.get(completion.output_artifact_version_id)
    if location is None or version is None:
        return False
    if (
        location.artifact_version_id != completion.output_artifact_version_id
        or version.content_sha256 != completion.output_sha256
    ):
        return False
    objects = observed.get(location.provider_object_ref, [])
    return bool(objects) and all(_matches(version, item) for item in objects)


def reconcile(snapshot: ReconcileSnapshot) -> tuple[ReconcileFinding, ...]:
    versions = {item.artifact_version_id: item for item in snapshot.versions}
    locations = {item.location_id: item for item in snapshot.cloud_locations}
    observed: dict[str, list[CloudObjectObservation]] = {}
    for item in snapshot.cloud_objects:
        observed.setdefault(item.provider_object_ref, []).append(item)
    referenced = {item.provider_object_ref for item in snapshot.cloud_locations}
    findings: set[ReconcileFinding] = set()

    for location in snapshot.cloud_locations:
        objects = observed.get(location.provider_object_ref, [])
        if not objects:
            findings.add(ReconcileFinding(ReconcileCode.CLOUD_OBJECT_MISSING, location.location_id))
            continue
        version = versions.get(location.artifact_version_id)
        if version is not None and not all(_matches(version, item) for item in objects):
            findings.add(ReconcileFinding(ReconcileCode.HASH_MISMATCH, location.location_id))

    for ref in observed:
        if ref not in referenced:
            findings.add(ReconcileFinding(ReconcileCode.ORPHAN_PROVIDER_OBJECT, ref))

    location_counts = Counter(item.provider_object_ref for item in snapshot.cloud_locations)
    for ref in referenced | set(observed):
        if location_counts[ref] > 1 or len(observed.get(ref, [])) > 1:
            findings.add(ReconcileFinding(ReconcileCode.DUPLICATE_PROVIDER_OBJECT, ref))

    current = str(snapshot.current_recovery_epoch)
    for entry in snapshot.journal_entries:
        if str(entry.recovery_epoch) != current:
            findings.add(
                ReconcileFinding(
                    ReconcileCode.STALE_EPOCH_ENTRY,
                    entry.operation_key,
                    ReconcileAction.REISSUE_UNDER_NEW_EPOCH,
                )
            )
        elif snapshot.stage_generations.get(entry.operation_key) != entry.generation:
            findings.add(
                ReconcileFinding(
                    ReconcileCode.JOURNAL_GENERATION_MISMATCH,
                    entry.operation_key,
                )
            )

    for completion in snapshot.completions:
        if not _output_verified(completion, versions, locations, observed):
            findings.add(
                ReconcileFinding(
                    ReconcileCode.COMPLETION_WITHOUT_VERIFIED_OUTPUT,
                    completion.video_job_id,
                )
            )

    return tuple(
        sorted(
            findings,
            key=lambda item: (item.code.value, item.ref, item.action.value if item.action else ''),
        )
    )


__all__ = [
    'CloudLocationRecord',
    'CloudObjectObservation',
    'CompletionRecord',
    'JournalEntry',
    'ReconcileAction',
    'ReconcileCode',
    'ReconcileFinding',
    'ReconcileSnapshot',
    'VersionRecord',
    'reconcile',
]
