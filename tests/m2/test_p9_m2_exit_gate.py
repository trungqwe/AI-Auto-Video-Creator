"""Tests for Milestone M2 Exit Gate Verification and Final Manifest (M2-P9)."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import subprocess
import uuid
from pathlib import Path
from typing import Any

import psycopg
import pytest

from controlplane.infrastructure.db.migration_runner import MigrationRunner
from controlplane.infrastructure.evidence.validator import sha256_file
from controlplane.infrastructure.security.secret_scanner import generate_secret_scan_report

REPO_ROOT = Path(__file__).resolve().parents[2]
LIVE_MANIFEST_PATH = REPO_ROOT / "docs" / "milestones" / "m2-control-plane" / "evidence" / "manifest.json"
LIVE_AUDIT_PATH = REPO_ROOT / "docs" / "milestones" / "m2-control-plane" / "audit-m2.md"
LIVE_P9_STATUS_PATH = REPO_ROOT / "docs" / "milestones" / "m2-control-plane" / "evidence" / "m2-p9" / "status.json"

M2_ACCEPTED_SHA = "1aedf8fc2c1e90b34b5db8f0c01e28c8003f781e"
BASELINE_PREFIXES = ("src/controlplane/ui/dist/", "tests/m2/e2e/")
MIGRATIONS_REL_DIR = "src/controlplane/infrastructure/db/migrations"
PINNED_MIGRATION_STEMS = (
    "0001_initial_controlplane",
    "0002_idempotency_and_receipts",
    "0003_outbox_and_projections",
    "0004_config_and_secrets",
    "0005_artifact_metadata",
    "0006_orchestration_shell",
    "0007_technical_details",
    "0008_operation_stream_workspace_cursor_index",
)
MIGRATION_FILE_RE = re.compile(r"^\d{4}_[a-z0-9_]+\.sql$")


def git_show_bytes(commit: str, rel_path: str) -> bytes:
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError(f"Baseline commit is not a 40-hex SHA: {commit}")
    proc = subprocess.run(
        ["git", "show", f"{commit}:{rel_path}"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise ValueError(f"Baseline blob unavailable: {commit}:{rel_path}")
    return proc.stdout


def validate_manifest_dict(
    manifest: dict[str, Any],
    project_root: Path,
    *,
    baseline_commit: str | None = None,
    baseline_prefixes: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Validate manifest structure, non-self-referential rule, and artifact hashes."""
    if manifest.get("schema_version") not in ("1.0", "m2_manifest_v1"):
        raise ValueError(f"Invalid schema_version: {manifest.get('schema_version')}")
    if manifest.get("milestone") != "M2":
        raise ValueError(f"Invalid milestone: {manifest.get('milestone')}")
    if not isinstance(manifest.get("packages"), dict) or not manifest["packages"]:
        raise ValueError("Missing or empty 'packages' section in manifest")
    if not isinstance(manifest.get("artifacts"), list) or not manifest["artifacts"]:
        raise ValueError("Missing or empty 'artifacts' section in manifest")

    verified_artifacts = []
    tampered_artifacts = []
    missing_artifacts = []

    for entry in manifest["artifacts"]:
        rel_path = entry.get("path", "")
        expected_hash = entry.get("sha256", "").lower()
        if not rel_path or not expected_hash:
            raise ValueError(f"Malformed artifact entry: {entry}")

        clean_rel = rel_path.replace("\\", "/")
        if clean_rel.endswith("evidence/manifest.json") or clean_rel == "manifest.json":
            raise ValueError(
                f"Self-referential hash error: manifest.json cannot contain its own hash ({clean_rel})"
            )

        if baseline_commit is not None and any(clean_rel.startswith(prefix) for prefix in baseline_prefixes):
            actual_hash = hashlib.sha256(git_show_bytes(baseline_commit, clean_rel)).hexdigest().lower()
        else:
            target_file = project_root / rel_path
            if not target_file.is_file():
                missing_artifacts.append(rel_path)
                continue

            actual_hash = sha256_file(target_file).lower()
        if actual_hash != expected_hash:
            tampered_artifacts.append({
                "path": rel_path,
                "expected": expected_hash,
                "actual": actual_hash,
            })
        else:
            verified_artifacts.append(rel_path)

    if missing_artifacts:
        raise FileNotFoundError(
            f"Missing evidence artifacts declared in manifest: {missing_artifacts}"
        )
    if tampered_artifacts:
        raise ValueError(
            f"Tampered artifacts detected (hash mismatch): {tampered_artifacts}"
        )

    return {
        "valid": True,
        "verified_count": len(verified_artifacts),
        "packages": list(manifest["packages"].keys()),
    }


def validate_manifest_file(manifest_path: Path, project_root: Path) -> dict[str, Any]:
    """Validate manifest file on disk."""
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Manifest file missing: {manifest_path}")
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"Manifest JSON malformed: {exc}") from exc
    return validate_manifest_dict(data, project_root)


def test_tst_m2_p9_001_m2_manifest_and_gate_evaluation() -> None:
    """RED Oracle #1: Live manifest must exist and validate all packages; missing artifact fails closed."""
    live_manifest = json.loads(LIVE_MANIFEST_PATH.read_text(encoding="utf-8"))
    res = validate_manifest_dict(
        live_manifest,
        REPO_ROOT,
        baseline_commit=M2_ACCEPTED_SHA,
        baseline_prefixes=BASELINE_PREFIXES,
    )
    assert res["valid"] is True
    assert res["verified_count"] > 0
    for expected_pkg in ["m2-p0", "m2-p1", "m2-p2", "m2-p3", "m2-p4", "m2-p5a", "m2-p5b", "m2-p6", "m2-p7a", "m2-p7b", "m2-p8", "m2-p9"]:
        assert expected_pkg in res["packages"]

    fake_manifest = {
        "schema_version": "m2_manifest_v1",
        "milestone": "M2",
        "packages": {"m2-p0": {"status": "PASS"}},
        "artifacts": [
            {
                "path": "docs/milestones/m2-control-plane/evidence/m2-p0/nonexistent_file.txt",
                "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
            }
        ],
    }
    with pytest.raises(FileNotFoundError, match="Missing evidence artifacts"):
        validate_manifest_dict(fake_manifest, REPO_ROOT)

    self_ref_manifest = {
        "schema_version": "m2_manifest_v1",
        "milestone": "M2",
        "packages": {"m2-p0": {"status": "PASS"}},
        "artifacts": [
            {
                "path": "docs/milestones/m2-control-plane/evidence/manifest.json",
                "sha256": "1111111111111111111111111111111111111111111111111111111111111111",
            }
        ],
    }
    with pytest.raises(ValueError, match="Self-referential hash error"):
        validate_manifest_dict(self_ref_manifest, REPO_ROOT)

    for prefix in BASELINE_PREFIXES:
        idx = next(
            i for i, entry in enumerate(live_manifest["artifacts"])
            if entry.get("path", "").replace("\\", "/").startswith(prefix)
        )
        tampered = copy.deepcopy(live_manifest)
        tampered["artifacts"][idx]["sha256"] = "0" * 64
        with pytest.raises(ValueError, match="Tampered artifacts detected"):
            validate_manifest_dict(
                tampered,
                REPO_ROOT,
                baseline_commit=M2_ACCEPTED_SHA,
                baseline_prefixes=BASELINE_PREFIXES,
            )

    with pytest.raises(ValueError, match="Baseline blob unavailable"):
        validate_manifest_dict(
            live_manifest,
            REPO_ROOT,
            baseline_commit="f" * 40,
            baseline_prefixes=BASELINE_PREFIXES,
        )

    with pytest.raises(ValueError, match="not a 40-hex SHA"):
        validate_manifest_dict(
            live_manifest,
            REPO_ROOT,
            baseline_commit="not-a-sha",
            baseline_prefixes=BASELINE_PREFIXES,
        )


def test_tst_m2_p9_002_artifact_tamper_detection(tmp_path: Path) -> None:
    """RED Oracle #2: Tampering with 1 byte of an evidence artifact fails closed on isolated copy."""
    iso_dir = tmp_path / "evidence_iso"
    iso_dir.mkdir(parents=True)
    sample_file = iso_dir / "sample_artifact.txt"
    orig_bytes = b"ORIGINAL EVIDENCE RECORD 2026-10-08"
    sample_file.write_bytes(orig_bytes)
    orig_hash = hashlib.sha256(orig_bytes).hexdigest()

    manifest = {
        "schema_version": "m2_manifest_v1",
        "milestone": "M2",
        "packages": {"m2-p0": {"status": "PASS"}},
        "artifacts": [
            {
                "path": str(sample_file.relative_to(tmp_path)),
                "sha256": orig_hash,
            }
        ],
    }

    res = validate_manifest_dict(manifest, tmp_path)
    assert res["valid"] is True

    tampered_bytes = b"TAMPERED EVIDENCE RECORD 2026-10-08"
    sample_file.write_bytes(tampered_bytes)

    with pytest.raises(ValueError, match="Tampered artifacts detected"):
        validate_manifest_dict(manifest, tmp_path)


def test_tst_m2_p9_003_m1_regression_suite_93_tests() -> None:
    """Positive test: M1 regression report confirms 93 tests passed with 0 failures, 0 errors, 0 skipped."""
    import xml.etree.ElementTree as ET

    xml_path = REPO_ROOT / "tests" / "m2" / "evidence" / "m1-regression.xml"
    assert xml_path.is_file(), f"M1 regression XML missing at {xml_path}"

    tree = ET.parse(xml_path)
    root = tree.getroot()
    suite = root.find("testsuite") if root.tag == "testsuites" else root

    tests = int(suite.attrib.get("tests", 0))
    failures = int(suite.attrib.get("failures", 0))
    errors = int(suite.attrib.get("errors", 0))
    skipped = int(suite.attrib.get("skipped", 0))

    assert tests == 93, f"Expected 93 M1 regression tests, got {tests}"
    assert failures == 0, f"Expected 0 failures, got {failures}"
    assert errors == 0, f"Expected 0 errors, got {errors}"
    assert skipped == 0, f"Expected 0 skipped, got {skipped}"


def test_tst_m2_p9_004_secret_scanner_clean_and_fail_closed_canary(tmp_path: Path) -> None:
    """Positive & Negative test: M2 standalone scanner reports 0 findings; canary secret fails closed."""
    dirs_to_scan = [
        REPO_ROOT / "src" / "controlplane" / "api",
        REPO_ROOT / "src" / "controlplane" / "application",
        REPO_ROOT / "src" / "controlplane" / "domain",
        REPO_ROOT / "src" / "controlplane" / "infrastructure",
        REPO_ROOT / "src" / "controlplane" / "ui",
        REPO_ROOT / "tests" / "m2",
        REPO_ROOT / "docs" / "milestones" / "m2-control-plane",
        REPO_ROOT / "migrations",
    ]
    report = generate_secret_scan_report(dirs_to_scan)
    assert report["verdict"] == "CLEAN", f"Secret scanner findings: {report.get('findings')}"
    assert report["total_findings"] == 0
    assert report["total_files_scanned"] > 100

    canary_dir = tmp_path / "canary_leak"
    canary_dir.mkdir(parents=True)
    leak_file = canary_dir / "config_leak.py"
    key_prefix = '"client_' + 'secret"'
    leak_val = '"canary_private_key_leak_12345678"'
    leak_file.write_text(f"CANARY_LEAK = {{{key_prefix}: {leak_val}}}\n", encoding="utf-8")

    canary_report = generate_secret_scan_report([canary_dir])
    assert canary_report["verdict"] == "VIOLATIONS_DETECTED"
    assert canary_report["total_findings"] > 0


def test_tst_m2_p9_005_migration_full_down_up_cycle_disposable_db() -> None:
    """Migration test: Full down/up cycle completes on a disposable test database without modifying migrations."""
    migrations_dir = REPO_ROOT / "src" / "controlplane" / "infrastructure" / "db" / "migrations"
    forward_files = sorted(p for p in migrations_dir.iterdir() if p.is_file() and MIGRATION_FILE_RE.fullmatch(p.name))
    expected_count = len(forward_files)
    assert expected_count >= len(PINNED_MIGRATION_STEMS)
    assert [p.stem for p in forward_files[:8]] == list(PINNED_MIGRATION_STEMS)
    for stem in PINNED_MIGRATION_STEMS:
        for name in (f"{stem}.sql", f"{stem}.rollback.sql"):
            actual_digest = hashlib.sha256((migrations_dir / name).read_bytes()).hexdigest()
            expected_digest = hashlib.sha256(git_show_bytes(M2_ACCEPTED_SHA, f"{MIGRATIONS_REL_DIR}/{name}")).hexdigest()
            assert actual_digest == expected_digest, f"Pinned migration blob mismatch for {name}"

    base_dsn = os.environ.get("M2_TEST_PG_DSN", "postgresql://m2test:m2test@127.0.0.1:57027/postgres")
    dbname = f"m2_p1_test_{uuid.uuid4().hex[:8]}"

    admin_conn = psycopg.connect(base_dsn, autocommit=True)
    try:
        admin_conn.execute(f"CREATE DATABASE {dbname}")
        test_dsn = base_dsn.rsplit("/", 1)[0] + f"/{dbname}"

        runner = MigrationRunner(
            test_dsn,
            migrations_dir,
            is_test_env=True,
            expected_database_name=dbname,
        )

        runner.migrate_up()
        with psycopg.connect(test_dsn) as conn:
            applied = conn.execute(
                "SELECT version, name FROM controlplane.cp_schema_migrations ORDER BY version"
            ).fetchall()
            assert len(applied) == expected_count, f"Expected {expected_count} migrations, got {len(applied)}"
            assert [row[0] for row in applied] == list(range(1, expected_count + 1))
            assert [row[1] for row in applied[:8]] == [stem[5:] for stem in PINNED_MIGRATION_STEMS]

        runner.migrate_down()
        with psycopg.connect(test_dsn) as conn:
            exists = conn.execute(
                "SELECT to_regclass('controlplane.cp_schema_migrations')"
            ).fetchone()[0]
            assert exists is None, "cp_schema_migrations should be dropped after full rollback"

        runner.migrate_up()
        with psycopg.connect(test_dsn) as conn:
            reapplied = conn.execute(
                "SELECT version, name FROM controlplane.cp_schema_migrations ORDER BY version"
            ).fetchall()
            assert len(reapplied) == expected_count
            assert [row[0] for row in reapplied] == list(range(1, expected_count + 1))
            assert [row[1] for row in reapplied[:8]] == [stem[5:] for stem in PINNED_MIGRATION_STEMS]
    finally:
        admin_conn.execute(f"DROP DATABASE IF EXISTS {dbname} WITH (FORCE)")
        admin_conn.close()


def test_tst_m2_p9_006_m2_exit_gate_and_audit_report() -> None:
    """Audit test: audit-m2.md covers all 6 M2 Exit Gate criteria and authorizes M2_READY_FOR_USER_CHECKPOINT."""
    assert LIVE_AUDIT_PATH.is_file(), f"M2 Exit Audit report missing at {LIVE_AUDIT_PATH}"
    content = LIVE_AUDIT_PATH.read_text(encoding="utf-8")

    assert "M2_READY_FOR_USER_CHECKPOINT" in content
    assert "M3" in content and "NOT AUTHORIZED" in content

    assert "100% Hợp đồng Nền tảng Đã Được Kiểm chứng" in content
    assert "Không có Duplicate Aggregate hoặc Duplicate Side Effect" in content
    assert "Bảo vệ Ranh giới Bí mật Tuyệt đối" in content
    assert "Lát cắt Người dùng Hoạt động Đích thực" in content
    assert "Bảo toàn Hồi quy M1" in content
    assert "Báo cáo Kiểm toán M2 Hoàn tất" in content

    assert LIVE_P9_STATUS_PATH.is_file(), f"M2-P9 status.json missing at {LIVE_P9_STATUS_PATH}"
    p9_status = json.loads(LIVE_P9_STATUS_PATH.read_text(encoding="utf-8"))
    assert p9_status.get("status") == "PASS"
    assert p9_status.get("milestone") == "M2"
    assert p9_status.get("package") == "M2-P9"