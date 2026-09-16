"""Real-PostgreSQL hardening probes for the corrected P5B candidate."""
from __future__ import annotations

import argparse
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg

from controlplane.domain.statemachine import ArtifactLocationState
from tests.m2.test_p5b_artifact_metadata import (
    HASH_A,
    WORKSPACE_A,
    _artifact_version_fixture,
    _authorization_store,
    _disposable_database,
    _location_input,
    _location_store,
    _manager,
    _seed_location_version_prerequisite,
    PRODUCTION_MIGRATIONS,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    output = Path(parser.parse_args().output)
    assert os.environ.get("M2_TEST_PG_DSN")
    checks: dict[str, bool] = {}
    with _disposable_database(PRODUCTION_MIGRATIONS) as database:
        with psycopg.connect(database.dsn) as connection:
            connection.execute(
                "INSERT INTO controlplane.cp_workspaces (workspace_id, name, status) VALUES (%s, 'P5B hardening', 'ACTIVE')",
                (WORKSPACE_A,),
            )
            connection.commit()
        location_store = _location_store()
        authorization_store = _authorization_store()
        version = _artifact_version_fixture()
        with _manager(database.dsn) as manager:
            with manager.unit_of_work() as uow:
                _seed_location_version_prerequisite(uow.connection, version)
                location = location_store.declare(**_location_input(version.artifact_version_id), connection=uow.connection)
            for state in (ArtifactLocationState.MATERIALIZING, ArtifactLocationState.AVAILABLE_UNVERIFIED, ArtifactLocationState.VERIFYING, ArtifactLocationState.VERIFIED, ArtifactLocationState.CLEANUP_ELIGIBLE):
                with manager.unit_of_work() as uow:
                    location = location_store.transition(workspace_id=WORKSPACE_A, location_id=location.location_id, expected_revision=location.revision, requested_state=state, verification_evidence_ref="verify-hardening" if state is ArtifactLocationState.VERIFIED else None, connection=uow.connection)
            now = datetime.now(timezone.utc)
            values = dict(workspace_id=WORKSPACE_A, location_id=location.location_id, artifact_version_id=version.artifact_version_id, artifact_hash=HASH_A, reason="retention-complete", policy_revision="policy-r7", completion_evidence_ref="completion-hardening", verification_evidence_ref="verify-hardening", issued_at=now, expires_at=now + timedelta(hours=1), recovery_epoch=7, current_recovery_epoch=7, authorizing_owner_ref="owner", actor_ref="actor", audit_ref="audit", correlation_ref="correlation")
            try:
                with manager.unit_of_work() as uow:
                    authorization_store.authorize(**{**values, "verification_evidence_ref": "wrong"}, expected_revision=location.revision, connection=uow.connection)
            except ValueError:
                pass
            with manager.unit_of_work() as uow:
                state, revision = uow.connection.execute("SELECT state, revision FROM controlplane.cp_artifact_locations WHERE location_id=%s", (location.location_id,)).fetchone()
                count = uow.connection.execute("SELECT count(*) FROM controlplane.cp_cleanup_authorizations").fetchone()[0]
            checks["mismatched_verification_ref_zero_mutation"] = state == "CLEANUP_ELIGIBLE" and revision == location.revision and count == 0
            rejected = True
            marker = "credential-probe-do-not-persist"
            for field in ("backend_ref", "provider_namespace_ref", "provider_object_ref", "logical_locator"):
                try:
                    with manager.unit_of_work() as uow:
                        location_store.declare(**{**_location_input(version.artifact_version_id), field: f"token={marker}"}, connection=uow.connection)
                    rejected = False
                except ValueError:
                    pass
            with manager.unit_of_work() as uow:
                raw_count = uow.connection.execute("SELECT count(*) FROM controlplane.cp_artifact_locations WHERE backend_ref LIKE %s OR provider_namespace_ref LIKE %s OR provider_object_ref LIKE %s OR logical_locator LIKE %s", (f"%{marker}%",) * 4).fetchone()[0]
            checks["credential_refs_rejected_not_persisted"] = rejected and raw_count == 0
            with manager.unit_of_work() as uow:
                authorization = authorization_store.authorize(**values, expected_revision=location.revision, connection=uow.connection)
            for operation, statement in (("update", "UPDATE controlplane.cp_cleanup_authorizations SET reason='changed' WHERE cleanup_authorization_id=%s"), ("delete", "DELETE FROM controlplane.cp_cleanup_authorizations WHERE cleanup_authorization_id=%s")):
                try:
                    with manager.unit_of_work() as uow:
                        uow.connection.execute(statement, (authorization.cleanup_authorization_id,))
                    checks[f"direct_sql_{operation}_rejected"] = False
                except psycopg.Error:
                    checks[f"direct_sql_{operation}_rejected"] = True
            try:
                with manager.unit_of_work() as uow:
                    uow.connection.execute("INSERT INTO controlplane.cp_cleanup_authorizations (cleanup_authorization_id,workspace_id,location_id,artifact_version_id,artifact_hash,reason,policy_revision,completion_evidence_ref,verification_evidence_ref,issued_at,expires_at,recovery_epoch,authorizing_owner_ref,actor_ref,audit_ref,correlation_ref) VALUES (%s,%s,%s,%s,%s,'x','p','c','v',%s,%s,7,'o','a','u','r')", (str(uuid.uuid4()), WORKSPACE_A, location.location_id, version.artifact_version_id, "b" * 64, now, now + timedelta(hours=1)))
                checks["direct_sql_binding_mismatch_rejected"] = False
            except psycopg.Error:
                checks["direct_sql_binding_mismatch_rejected"] = True
            with manager.unit_of_work() as uow:
                checks["failed_authorization_no_orphan_or_partial"] = uow.connection.execute("SELECT count(*) FROM controlplane.cp_cleanup_authorizations").fetchone()[0] == 1 and uow.connection.execute("SELECT state FROM controlplane.cp_artifact_locations WHERE location_id=%s", (location.location_id,)).fetchone()[0] == "CLEANUP_AUTHORIZED"
    assert all(checks.values()), checks
    output.write_text(json.dumps({"verdict": "PASS", "database": "real_postgresql_disposable", "checks": checks}, indent=2) + "\n", encoding="utf-8")
    print("P5B_HARDENING_PROBES=PASS")
    for name in checks:
        print(f"{name}=PASS")


if __name__ == "__main__":
    main()
