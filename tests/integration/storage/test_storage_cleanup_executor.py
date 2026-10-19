"""I-09: LocalCleanupExecutor xoá tệp staging có fencing (CT-STO-008, ADR-0010, INV-011)."""
from __future__ import annotations

import dataclasses
import hashlib
import pathlib
from datetime import datetime, timezone

import pytest

from controlplane.domain.statemachine import ArtifactLocationState
from controlplane.domain.storage_meta import ArtifactLocation, CleanupAuthorization
from controlplane.infrastructure.storage import cleanup_executor
from controlplane.infrastructure.storage.cleanup_executor import CleanupResult, LocalCleanupExecutor

CONTENT = b"rendered-output-bytes"
CONTENT_SHA256 = hashlib.sha256(CONTENT).hexdigest()
OTHER_SHA256 = hashlib.sha256(b"other-bytes").hexdigest()
NOW = datetime(2026, 10, 18, 9, 30, tzinfo=timezone.utc)
AFTER = datetime(2026, 10, 18, 10, 0, 1, tzinfo=timezone.utc)
AT_EXPIRY = datetime(2026, 10, 18, 10, 0, tzinfo=timezone.utc)
EXPIRES_AT = "2026-10-18T10:00:00+00:00"
EPOCH = 7
RELATIVE = "videos/out.mp4"


def make_authorization(**overrides) -> CleanupAuthorization:
    fields = {
        "workspace_id": "ws-1",
        "cleanup_authorization_id": "auth-1",
        "location_id": "loc-1",
        "artifact_version_id": "ver-1",
        "artifact_hash": CONTENT_SHA256,
        "reason": "completion",
        "policy_revision": "policy-1",
        "completion_evidence_ref": "completion-1",
        "verification_evidence_ref": "verify-1",
        "issued_at": "2026-10-18T09:00:00+00:00",
        "expires_at": EXPIRES_AT,
        "recovery_epoch": EPOCH,
        "authorizing_owner_ref": "owner-1",
        "actor_ref": "actor-1",
        "audit_ref": "audit-1",
        "correlation_ref": "corr-1",
    }
    fields.update(overrides)
    return CleanupAuthorization(**fields)


def make_location(**overrides) -> ArtifactLocation:
    fields = {
        "workspace_id": "ws-1",
        "location_id": "loc-1",
        "artifact_version_id": "ver-1",
        "backend_ref": "local",
        "provider_namespace_ref": "ns",
        "provider_object_ref": "obj",
        "logical_locator": RELATIVE,
        "observed_hash": CONTENT_SHA256,
        "observed_size_bytes": len(CONTENT),
        "provider_metadata_revision": None,
        "verification_evidence_ref": "verify-1",
        "state": ArtifactLocationState.CLEANUP_AUTHORIZED,
        "revision": 1,
        "created_at": "2026-10-18T09:00:00+00:00",
        "updated_at": "2026-10-18T09:00:00+00:00",
    }
    fields.update(overrides)
    return ArtifactLocation(**fields)


@pytest.fixture
def root(tmp_path: pathlib.Path) -> pathlib.Path:
    staging = tmp_path / "staging"
    staging.mkdir()
    return staging


@pytest.fixture
def target(root: pathlib.Path) -> pathlib.Path:
    (root / "videos").mkdir(parents=True, exist_ok=True)
    target_path = root / "videos" / "out.mp4"
    target_path.write_bytes(CONTENT)
    return target_path


def run(
    root: pathlib.Path,
    authorization: CleanupAuthorization | None = None,
    location: ArtifactLocation | None = None,
    relative: str = RELATIVE,
    epoch: str = "7",
    now: datetime = NOW,
    active_lease: bool = False,
) -> CleanupResult:
    return LocalCleanupExecutor(root).execute(
        authorization or make_authorization(),
        location or make_location(),
        relative,
        epoch,
        now,
        active_lease,
    )


def test_valid_authorization_deletes_only_target(root: pathlib.Path, target: pathlib.Path) -> None:
    keep_path = root / "videos" / "keep.mp4"
    keep_path.write_bytes(b"keep")
    result = run(root)
    assert result == CleanupResult(True, ())
    assert not target.exists()
    assert keep_path.exists()
    assert (root / "videos").is_dir()


@pytest.mark.parametrize(
    ("auth_overrides", "location_overrides", "run_kwargs", "reasons"),
    [
        pytest.param(
            {"artifact_hash": OTHER_SHA256},
            {"observed_hash": OTHER_SHA256},
            {},
            ("HASH_MISMATCH",),
            id="hash differs",
        ),
        pytest.param({}, {}, {"epoch": "8"}, ("STALE_RECOVERY_EPOCH",), id="stale epoch"),
        pytest.param({}, {}, {"now": AFTER}, ("EXPIRED",), id="expired"),
        pytest.param({}, {}, {"now": AT_EXPIRY}, ("EXPIRED",), id="now equals expiry"),
        pytest.param({}, {}, {"active_lease": True}, ("ACTIVE_LEASE",), id="active lease"),
        pytest.param(
            {},
            {"state": ArtifactLocationState.VERIFIED},
            {},
            ("LOCATION_NOT_AUTHORIZED",),
            id="location not authorized",
        ),
        pytest.param({}, {"location_id": "loc-2"}, {}, ("LOCATION_MISMATCH",), id="location mismatch"),
        pytest.param({"expires_at": "not-a-date"}, {}, {}, ("INVALID_EXPIRY",), id="invalid expiry"),
    ],
)
def test_unauthorized_deletion_keeps_file(
    root: pathlib.Path,
    target: pathlib.Path,
    auth_overrides: dict,
    location_overrides: dict,
    run_kwargs: dict,
    reasons: tuple[str, ...],
) -> None:
    result = run(
        root,
        make_authorization(**auth_overrides),
        make_location(**location_overrides),
        **run_kwargs,
    )
    assert result == CleanupResult(False, reasons)
    assert target.exists()
    assert target.read_bytes() == CONTENT


@pytest.mark.parametrize("relative", ["../outside.bin", "a/../../outside.bin", None])
def test_path_outside_staging_is_rejected(
    tmp_path: pathlib.Path,
    root: pathlib.Path,
    target: pathlib.Path,
    relative: str | None,
) -> None:
    outside = tmp_path / "outside.bin"
    outside.write_bytes(CONTENT)
    rel = str(outside) if relative is None else relative
    result = run(root, relative=rel)
    assert result == CleanupResult(False, ("PATH_OUTSIDE_STAGING",))
    assert outside.read_bytes() == CONTENT
    assert target.exists()


def test_directory_target_is_not_a_file(root: pathlib.Path, target: pathlib.Path) -> None:
    result = run(root, relative="videos")
    assert result == CleanupResult(False, ("NOT_A_FILE",))
    assert (root / "videos").is_dir()
    assert target.read_bytes() == CONTENT


def test_missing_target_is_not_a_file(root: pathlib.Path, target: pathlib.Path) -> None:
    result = run(root, relative="videos/missing.mp4")
    assert result == CleanupResult(False, ("NOT_A_FILE",))
    assert target.exists()


def test_resolve_runs_before_authorization(
    tmp_path: pathlib.Path,
    root: pathlib.Path,
    target: pathlib.Path,
) -> None:
    outside = tmp_path / "outside.bin"
    outside.write_bytes(CONTENT)
    result = run(root, relative="../outside.bin", now=AFTER)
    assert result == CleanupResult(False, ("PATH_OUTSIDE_STAGING",))


def test_authorization_runs_before_not_a_file(root: pathlib.Path, target: pathlib.Path) -> None:
    result = run(root, relative="videos", now=AFTER)
    assert result == CleanupResult(False, ("EXPIRED",))
    assert (root / "videos").is_dir()


def test_unreadable_target_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    root: pathlib.Path,
    target: pathlib.Path,
) -> None:
    def deny(self, *args, **kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr(pathlib.Path, "open", deny)
    result = run(root)
    monkeypatch.undo()
    assert result == CleanupResult(False, ("HASH_MISMATCH",))
    assert target.read_bytes() == CONTENT


@pytest.mark.parametrize("error", [OSError("boom"), PermissionError("locked")])
def test_unlink_oserror_returns_delete_failed(
    monkeypatch: pytest.MonkeyPatch,
    root: pathlib.Path,
    target: pathlib.Path,
    error: Exception,
) -> None:
    def fail(self, *args, **kwargs):
        raise error

    monkeypatch.setattr(pathlib.Path, "unlink", fail)
    result = run(root)
    monkeypatch.undo()
    assert result == CleanupResult(False, ("DELETE_FAILED",))
    assert target.read_bytes() == CONTENT


def test_source_has_no_directory_removal() -> None:
    source = pathlib.Path(cleanup_executor.__file__).read_text(encoding="utf-8")
    assert "rmtree" not in source
    assert "rmdir" not in source


def test_cleanup_result_is_frozen() -> None:
    result = CleanupResult(True, ())
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.deleted = False
