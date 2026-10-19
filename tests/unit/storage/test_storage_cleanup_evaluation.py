"""I-08: đánh giá cleanup (CT-STO-007) và kiểm tra cleanup authorization (CT-STO-008)."""
import dataclasses
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from controlplane.application.storage_meta.cleanup_evaluation import (
    CleanupEvaluation,
    CleanupEvaluationRequest,
    check_cleanup_authorization,
    evaluate_cleanup,
)
from controlplane.domain.statemachine import ArtifactLocationState
from controlplane.domain.storage_meta import ArtifactLocation, CleanupAuthorization

State = ArtifactLocationState
FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "contracts" / "g-c-i-completion" / "payloads.json"
VALID = json.loads(FIXTURE.read_text(encoding="utf-8"))["entities"]["CommitVideoCompletionRequest"]["valid"][0]
OUTPUT_SHA256 = VALID["output_sha256"]
RECOVERY_EPOCH = VALID["recovery_epoch"]
VERSION_ID = VALID["output_artifact_version_id"]
CLEANABLE_STATES = (State.VERIFIED, State.CLEANUP_ELIGIBLE)
DURABLE = "DURABLE_COPY_NOT_VERIFIED"


def make_request(**overrides):
    fields = {
        "storage_class": "local_staging", "location_state": State.VERIFIED, "retention_class": "output",
        "cloud_copy_verified": True, "active_lease": False, "completion_ref": "completion-1", "superseded_ref": None,
        "request_recovery_epoch": RECOVERY_EPOCH, "current_recovery_epoch": RECOVERY_EPOCH,
    }
    fields.update(overrides)
    return CleanupEvaluationRequest(**fields)


EVALUATE_CASES = [
    pytest.param({}, "eligible", (), id="output verified with completion"),
    pytest.param({"location_state": State.CLEANUP_ELIGIBLE}, "eligible", (), id="cleanup eligible state"),
    pytest.param({"storage_class": "local_cache"}, "eligible", (), id="local cache"),
    pytest.param({"completion_ref": None, "superseded_ref": "superseded-1"}, "eligible", (), id="superseded ref only"),
    pytest.param({"retention_class": "per_video", "cloud_copy_verified": False}, "eligible", (), id="per_video needs no cloud copy"),
    pytest.param({"retention_class": "temporary", "cloud_copy_verified": False}, "eligible", (), id="temporary needs no cloud copy"),
    pytest.param({"retention_class": "output", "cloud_copy_verified": False}, "forbidden", (DURABLE,), id="output not cloud verified"),
    pytest.param({"retention_class": "original", "cloud_copy_verified": False}, "forbidden", (DURABLE,), id="original not cloud verified"),
    pytest.param({"retention_class": "reusable", "cloud_copy_verified": False}, "forbidden", (DURABLE,), id="reusable not cloud verified"),
    pytest.param({"retention_class": "unknown", "cloud_copy_verified": False}, "forbidden", (DURABLE,), id="unknown retention is durable"),
    pytest.param({"cloud_copy_verified": None}, "forbidden", (DURABLE,), id="cloud verified None is not True"),
    pytest.param({"storage_class": "cloud_drive"}, "forbidden", ("NOT_LOCAL_STAGING",), id="cloud storage class"),
    pytest.param({"storage_class": ""}, "forbidden", ("NOT_LOCAL_STAGING",), id="empty storage class"),
    pytest.param({"request_recovery_epoch": "epoch-0000"}, "forbidden", ("STALE_RECOVERY_EPOCH",), id="stale epoch"),
    pytest.param({"active_lease": True}, "deferred", ("ACTIVE_LEASE",), id="active lease"),
    pytest.param({"completion_ref": None}, "deferred", ("NO_COMPLETION_EVIDENCE",), id="no evidence refs"),
    pytest.param({"completion_ref": "  "}, "deferred", ("NO_COMPLETION_EVIDENCE",), id="blank completion ref"),
    pytest.param({"active_lease": True, "completion_ref": None}, "deferred", ("ACTIVE_LEASE", "NO_COMPLETION_EVIDENCE"), id="both deferred reasons"),
    pytest.param({"storage_class": "cloud_drive", "active_lease": True, "completion_ref": None}, "forbidden", ("NOT_LOCAL_STAGING",), id="forbidden wins over deferred"),
    pytest.param(
        {"storage_class": "cloud_drive", "location_state": State.MISSING, "cloud_copy_verified": False, "request_recovery_epoch": "epoch-0000"},
        "forbidden", ("NOT_LOCAL_STAGING", "LOCATION_NOT_VERIFIED", DURABLE, "STALE_RECOVERY_EPOCH"), id="all forbidden reasons in order",
    ),
]


@pytest.mark.parametrize(("overrides", "decision", "reasons"), EVALUATE_CASES)
def test_evaluate_cleanup_table(overrides, decision, reasons):
    result = evaluate_cleanup(make_request(**overrides))
    assert isinstance(result, CleanupEvaluation)
    assert (result.decision, result.reason_codes) == (decision, reasons)
    assert result.earliest_cleanup_at is None


@pytest.mark.parametrize("state", [s for s in State if s not in CLEANABLE_STATES])
def test_evaluate_cleanup_forbids_every_other_location_state(state):
    result = evaluate_cleanup(make_request(location_state=state))
    assert (result.decision, result.reason_codes) == ("forbidden", ("LOCATION_NOT_VERIFIED",))


def test_fixture_values_are_well_formed():
    assert re.fullmatch(r"[0-9a-f]{64}", OUTPUT_SHA256)
    assert isinstance(RECOVERY_EPOCH, str) and RECOVERY_EPOCH


def test_result_and_request_are_frozen_with_contract_fields():
    assert [f.name for f in dataclasses.fields(CleanupEvaluation)] == ["decision", "reason_codes", "earliest_cleanup_at"]
    with pytest.raises(dataclasses.FrozenInstanceError):
        evaluate_cleanup(make_request()).decision = "forbidden"
    with pytest.raises(dataclasses.FrozenInstanceError):
        make_request().active_lease = True


UTC = timezone.utc
EXPIRES_AT = "2026-10-18T10:00:00+00:00"
BEFORE = datetime(2026, 10, 18, 9, 59, 59, tzinfo=UTC)
AT_EXPIRY = datetime(2026, 10, 18, 10, 0, 0, tzinfo=UTC)
AFTER = datetime(2026, 10, 18, 10, 0, 1, tzinfo=UTC)
PLUS7 = timezone(timedelta(hours=7))
LOCATION_ID = "location-1"
OTHER_SHA256 = "b" * 64


def make_location(**overrides):
    fields = {
        "workspace_id": "workspace-1", "location_id": LOCATION_ID, "artifact_version_id": VERSION_ID,
        "backend_ref": "backend-1", "provider_namespace_ref": "namespace-1", "provider_object_ref": "object-1",
        "logical_locator": "staging/output.mp4", "observed_hash": OUTPUT_SHA256, "observed_size_bytes": 1024,
        "provider_metadata_revision": None, "verification_evidence_ref": "evidence-1",
        "state": State.CLEANUP_AUTHORIZED, "revision": 3,
        "created_at": "2026-10-18T08:00:00+00:00", "updated_at": "2026-10-18T09:00:00+00:00",
    }
    fields.update(overrides)
    return ArtifactLocation(**fields)


def make_authorization(**overrides):
    fields = {
        "workspace_id": "workspace-1", "cleanup_authorization_id": "authorization-1", "location_id": LOCATION_ID,
        "artifact_version_id": VERSION_ID, "artifact_hash": OUTPUT_SHA256, "reason": "completion",
        "policy_revision": "policy-1", "completion_evidence_ref": "completion-1", "verification_evidence_ref": "evidence-1",
        "issued_at": "2026-10-18T09:00:00+00:00", "expires_at": EXPIRES_AT, "recovery_epoch": RECOVERY_EPOCH,
        "authorizing_owner_ref": "owner-1", "actor_ref": "actor-1", "audit_ref": "audit-1", "correlation_ref": "correlation-1",
    }
    fields.update(overrides)
    return CleanupAuthorization(**fields)


def check(authorization=None, location=None, epoch=RECOVERY_EPOCH, now=BEFORE, path_within_staging=True, active_lease=False):
    return check_cleanup_authorization(
        authorization or make_authorization(), location or make_location(), epoch, now, path_within_staging, active_lease
    )


AUTH_CASES = [
    pytest.param({}, {}, {}, (True, ()), id="valid before expiry"),
    pytest.param({"location_id": "location-2"}, {}, {}, (False, ("LOCATION_MISMATCH",)), id="other location"),
    pytest.param({"artifact_version_id": "version-2"}, {}, {}, (False, ("ARTIFACT_VERSION_MISMATCH",)), id="other version"),
    pytest.param({"artifact_hash": OTHER_SHA256}, {}, {}, (False, ("HASH_MISMATCH",)), id="authorization hash differs"),
    pytest.param({}, {"observed_hash": OTHER_SHA256}, {}, (False, ("HASH_MISMATCH",)), id="location hash differs"),
    pytest.param({}, {"observed_hash": None}, {}, (False, ("HASH_MISMATCH",)), id="location hash missing"),
    pytest.param({}, {}, {"active_lease": True}, (False, ("ACTIVE_LEASE",)), id="active lease"),
    pytest.param({}, {}, {"now": AT_EXPIRY}, (False, ("EXPIRED",)), id="now equals expiry"),
    pytest.param({}, {}, {"now": AFTER}, (False, ("EXPIRED",)), id="now after expiry"),
    pytest.param({}, {}, {"now": datetime(2026, 10, 18, 17, 0, 0, tzinfo=PLUS7)}, (False, ("EXPIRED",)), id="now equals expiry in +07:00"),
    pytest.param({}, {}, {"now": datetime(2026, 10, 18, 11, 0, 0, tzinfo=PLUS7)}, (True, ()), id="+07:00 wall clock later but instant earlier"),
    pytest.param({"expires_at": "2026-10-18T17:00:00+07:00"}, {}, {}, (True, ()), id="expiry with offset before"),
    pytest.param({"expires_at": "2026-10-18T17:00:00+07:00"}, {}, {"now": AT_EXPIRY}, (False, ("EXPIRED",)), id="expiry with offset reached"),
    pytest.param({}, {}, {"epoch": "epoch-0002"}, (False, ("STALE_RECOVERY_EPOCH",)), id="stale epoch"),
    pytest.param({"recovery_epoch": 7}, {}, {"epoch": "7"}, (True, ()), id="int epoch compared via str"),
    pytest.param({"recovery_epoch": 7}, {}, {"epoch": "8"}, (False, ("STALE_RECOVERY_EPOCH",)), id="int epoch stale"),
    pytest.param({}, {}, {"path_within_staging": False}, (False, ("PATH_OUTSIDE_STAGING",)), id="path outside staging"),
    pytest.param(
        {"location_id": "location-2", "artifact_hash": OTHER_SHA256}, {}, {"active_lease": True, "now": AFTER, "path_within_staging": False},
        (False, ("LOCATION_MISMATCH", "HASH_MISMATCH", "ACTIVE_LEASE", "EXPIRED", "PATH_OUTSIDE_STAGING")), id="all failures in order",
    ),
]


@pytest.mark.parametrize(("auth", "loc", "call", "expected"), AUTH_CASES)
def test_check_cleanup_authorization_table(auth, loc, call, expected):
    assert check(make_authorization(**auth), make_location(**loc), **call) == expected


@pytest.mark.parametrize("state", [s for s in State if s is not State.CLEANUP_AUTHORIZED])
def test_location_must_be_cleanup_authorized(state):
    assert check(location=make_location(state=state)) == (False, ("LOCATION_NOT_AUTHORIZED",))


@pytest.mark.parametrize("expires_at", ["not-a-date", "", None, 12345, "2026-10-18T10:00:00", "2026-10-18"])
def test_invalid_expires_at_fails_closed_without_raising(expires_at):
    assert check(make_authorization(expires_at=expires_at)) == (False, ("INVALID_EXPIRY",))


def test_naive_now_fails_closed_without_raising():
    assert check(now=datetime(2026, 10, 18, 9, 0, 0)) == (False, ("INVALID_EXPIRY",))


def test_invalid_expiry_wins_over_other_failures():
    result = check(make_authorization(expires_at="bad", artifact_hash=OTHER_SHA256), active_lease=True, path_within_staging=False)
    assert result == (False, ("INVALID_EXPIRY",))
