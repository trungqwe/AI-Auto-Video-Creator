"""Compatibility Smoke tests for M1-P5 (TST-M1-P5-001..007)."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import pytest
from m1proof.compatibility import (
    check_ffmpeg_compat,
    check_google_client_boundaries,
    check_postgresql_compat,
    check_runtime_environment,
    check_temporal_compat,
    generate_compatibility_matrix,
    verify_evidence_integrity,
)


def test_tst_m1_p5_001_exact_python_uv_and_frozen_lock_integrity(lock_file_path: Path):
    """TST-M1-P5-001: Strict equality check for Python 3.13.15, uv 0.12.13, and uv.lock."""
    result = check_runtime_environment(
        expected_python="3.13.15",
        expected_uv="0.12.13",
        lock_file=lock_file_path,
    )
    assert result["python_version"] == "3.13.15"
    assert result["uv_version"] == "0.12.13"
    assert result["python_matches"] is True
    assert result["uv_matches"] is True
    assert len(result["lock_hash"]) == 64
    assert result["frozen_status"] == "FROZEN_VALID"

    # Negative test: Nếu expected sai -> phải fail-closed
    with pytest.raises(ValueError, match="Python version mismatch"):
        check_runtime_environment(expected_python="3.14.0", expected_uv="0.12.13", lock_file=lock_file_path)

    with pytest.raises(ValueError, match="uv version mismatch"):
        check_runtime_environment(expected_python="3.13.15", expected_uv="0.99.0", lock_file=lock_file_path)


def test_tst_m1_p5_002_postgresql_connection_rollback_and_vietnamese_utf8():
    """TST-M1-P5-002: Verify PostgreSQL 18.6 exact connection, rollback, and UTF-8 Vietnamese encoding."""
    result = check_postgresql_compat(expected_version="18.6", expected_psycopg="3.3.5")
    assert result["connected"] is True
    assert result["rollback_tested"] is True
    assert result["utf8_roundtrip"] == "Tiếng Việt có dấu đầy đủ và chuẩn xác: Chào mừng bạn đến với AI Auto Video Creator"
    assert result["psycopg_version"] == "3.3.5"
    assert "18.6" in result["server_version"]

    # Negative test: Sai expected version -> fail-closed
    with pytest.raises(ValueError, match="PostgreSQL version mismatch"):
        check_postgresql_compat(expected_version="19.0")


@pytest.mark.asyncio
async def test_tst_m1_p5_003_temporal_sdk_and_server_handshake_smoke():
    """TST-M1-P5-003: Verify Temporal Server 1.31.2 gRPC connection, exact version, and SDK 1.32.0."""
    result = await check_temporal_compat(
        expected_server_version="1.31.2",
        expected_sdk_version="1.32.0",
    )
    assert result["temporal_sdk_version"] == "1.32.0"
    assert result["server_version"] == "1.31.2"
    assert result["handshake_status"] == "CONNECTED_EXACT_SERVER"
    assert result["replay_supported"] is True

    # Negative test: Sai port hoặc server không reachable -> fail-closed
    with pytest.raises(RuntimeError, match="Could not connect to Temporal Server"):
        await check_temporal_compat(target_host="127.0.0.1:17233")


def test_tst_m1_p5_004_google_client_boundaries_and_missing_credential_classification():
    """TST-M1-P5-004: Safe Google client construction and missing credential classification without leak."""
    result = check_google_client_boundaries()
    assert result["classification"] in ("CREDENTIAL_MISSING_OR_FILE_NOT_FOUND", "AUTHENTICATION_REQUIRED")
    assert result["secret_leaked"] is False


def test_tst_m1_p5_005_ffmpeg_version_buildconf_ffprobe_and_safe_probe(
    ffmpeg_bin_path: str,
    sample_media_fixture: Path,
):
    """TST-M1-P5-005: Capture FFmpeg full -version, -buildconf, binary hashes, and verify media with ffprobe."""
    result = check_ffmpeg_compat(
        ffmpeg_bin=ffmpeg_bin_path,
        fixture_path=sample_media_fixture,
    )
    assert result["ffmpeg_found"] is True
    assert "ffmpeg version" in result["version_output"]
    assert "--enable-" in result["buildconf_output"]
    assert len(result["binary_sha256"]) == 64
    assert len(result["ffprobe_sha256"]) == 64
    assert result["probe_executed"] is True
    assert result["probe_valid"] is True
    assert result["ffprobe_verified"] is True
    assert result["ffprobe_output"]["duration"] > 0
    assert result["build_identity"]["compiler"] == "gcc 14.2.0"


def test_tst_m1_p5_006_evidence_hash_mismatch_and_unsupported_version_rejected():
    """TST-M1-P5-006: Reject evidence hash mismatch and unsupported versions fail-closed."""
    valid_data = b"VALID_EVIDENCE_PAYLOAD"
    valid_hash = hashlib.sha256(valid_data).hexdigest()
    allowed = ["3.13.15"]

    # Case A: Hợp lệ
    assert verify_evidence_integrity(valid_hash, valid_data, allowed, "3.13.15") is True

    # Case B: Hash sai lệch
    with pytest.raises(ValueError, match="Hash mismatch"):
        verify_evidence_integrity("bad_hash_0000000000000000000000000000000000000000000000000000000000", valid_data, allowed, "3.13.15")

    # Case C: Phiên bản không được phép
    with pytest.raises(ValueError, match="Unsupported version"):
        verify_evidence_integrity(valid_hash, valid_data, allowed, "3.14.0")


def test_tst_m1_p5_007_machine_readable_compatibility_matrix(tmp_path: Path):
    """TST-M1-P5-007: Generate and validate machine-readable compatibility matrix JSON."""
    matrix = generate_compatibility_matrix(output_path=tmp_path / "compatibility_matrix.json")
    assert matrix["schema_version"] == "1.0"
    assert matrix["milestone"] == "M1-R1"
    assert "runtimes" in matrix
    assert matrix["runtimes"]["cpython"]["expected"] == "3.13.15"
    assert matrix["runtimes"]["cpython"]["result"] == "PASS"
    assert matrix["runtimes"]["postgresql"]["expected"] == "18.6"
    assert matrix["runtimes"]["temporal_server"]["expected"] == "1.31.2"
    assert matrix["runtimes"]["ffmpeg"]["binary_sha256"] == "f845a09b5467cf11651385e0be0dd4df6f70519264f8af2115e3acd6ab7f9480"


def test_tst_m1_p5_008_dynamic_matrix_observation(tmp_path: Path):
    """TST-M1-P5-008 (R4-05):
    Compatibility matrix must be generated dynamically from real runtime observation:
    - timestamp must reflect current UTC execution time (not hardcoded static string).
    - observed fields must be populated from actual inspection.
    - result must be evaluated dynamically (PASS if observed == expected, FAIL otherwise).
    """
    from datetime import datetime, timezone
    import platform
    matrix = generate_compatibility_matrix(output_path=tmp_path / "matrix_dyn.json")

    # 1. Timestamp must be dynamically generated (within 120s of now)
    ts_str = matrix.get("timestamp", "")
    matrix_time = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    delta = abs((now - matrix_time).total_seconds())
    assert delta < 120, f"Timestamp is hardcoded or stale! Delta: {delta}s, ts: {ts_str}"

    # 2. Results must be dynamically evaluated based on matching
    cpython_entry = matrix["runtimes"]["cpython"]
    assert cpython_entry["observed"] == platform.python_version()
    expected_result = "PASS" if cpython_entry["observed"] == cpython_entry["expected"] else "FAIL"
    assert cpython_entry["result"] == expected_result
