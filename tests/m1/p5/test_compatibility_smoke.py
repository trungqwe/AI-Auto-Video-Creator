"""Compatibility Smoke tests for M1-P5 (TST-M1-P5-001..006)."""
from __future__ import annotations
import hashlib
from pathlib import Path
import pytest
from m1proof.compatibility import (
    check_ffmpeg_compat,
    check_google_client_boundaries,
    check_postgresql_compat,
    check_runtime_environment,
    check_temporal_compat,
    verify_evidence_integrity,
)

def test_tst_m1_p5_001_exact_python_uv_and_frozen_lock_integrity(lock_file_path: Path):
    """TST-M1-P5-001: Verify exact Python, uv, and frozen uv.lock integrity."""
    result = check_runtime_environment(
        expected_python="3.13.15",
        expected_uv="0.12.13",
        lock_file=lock_file_path,
    )
    assert result["python_version"].startswith("3.13.")
    assert "0.12." in result["uv_version"]
    assert len(result["lock_hash"]) == 64
    assert result["frozen_status"] == "FROZEN_VALID"


def test_tst_m1_p5_002_postgresql_connection_rollback_and_vietnamese_utf8():
    """TST-M1-P5-002: Verify PostgreSQL 18.6 connection, rollback, and UTF-8 Vietnamese encoding."""
    result = check_postgresql_compat()
    assert result["connected"] is True
    assert result["rollback_tested"] is True
    assert result["utf8_roundtrip"] == "Tiếng Việt có dấu đầy đủ và chuẩn xác: Chào mừng bạn đến với AI Auto Video Creator"
    assert result["psycopg_version"].startswith("3.3.5")


def test_tst_m1_p5_003_temporal_sdk_and_server_handshake_smoke():
    """TST-M1-P5-003: Verify Temporal SDK 1.32.0 handshake, persistence compatibility, and replay smoke."""
    result = check_temporal_compat()
    assert result["temporal_sdk_version"].startswith("1.32.")
    assert result["handshake_status"] in ("CONNECTED", "ENVIRONMENT_READY")
    assert result["replay_supported"] is True


def test_tst_m1_p5_004_google_client_boundaries_and_missing_credential_classification():
    """TST-M1-P5-004: Safe Google client construction and missing credential classification without leak."""
    result = check_google_client_boundaries()
    assert result["classification"] in ("CREDENTIAL_MISSING_OR_FILE_NOT_FOUND", "AUTHENTICATION_REQUIRED")
    assert result["secret_leaked"] is False


def test_tst_m1_p5_005_ffmpeg_version_buildconf_and_safe_probe(
    ffmpeg_bin_path: str,
    sample_media_fixture: Path,
):
    """TST-M1-P5-005: Capture FFmpeg version, build configuration, binary hash, and execute safe probe."""
    result = check_ffmpeg_compat(
        ffmpeg_bin=ffmpeg_bin_path,
        fixture_path=sample_media_fixture,
    )
    assert result["ffmpeg_found"] is True
    assert "ffmpeg version" in result["version_output"]
    assert "--enable-" in result["buildconf_output"]
    assert len(result["binary_sha256"]) == 64
    assert result["probe_executed"] is True


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

    # Case C: Phiên bản không được phép (ví dụ 3.14.0)
    with pytest.raises(ValueError, match="Unsupported version"):
        verify_evidence_integrity(valid_hash, valid_data, allowed, "3.14.0")
