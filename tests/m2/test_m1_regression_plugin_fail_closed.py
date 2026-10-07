"""Unit tests verifying fail-closed semantics for m1_regression_plugin.patched_probe."""
import sys
from pathlib import Path
from unittest.mock import MagicMock
import pytest

# Ensure repository root and src directory are on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import tests.m2.m1_regression_plugin as plugin
import m1proof.drive_live_probe as probe_mod


def test_original_probe_failures_propagate(monkeypatch):
    """External probe failures must propagate and never be converted to synthetic PASS."""
    for error_type in (RuntimeError, ConnectionResetError, ValueError, OSError):
        mock_failure = MagicMock(side_effect=error_type("Probe external call failed"))
        monkeypatch.setattr(plugin, "orig_probe", mock_failure)

        # 1. Direct call to patched_probe must propagate the exception
        with pytest.raises(error_type, match="Probe external call failed"):
            plugin.patched_probe("Credentials/client_secret.json")

        # 2. Call via probe_mod.run_live_e3_drive_probe must also propagate the exception
        with pytest.raises(error_type, match="Probe external call failed"):
            probe_mod.run_live_e3_drive_probe("Credentials/client_secret.json")


def test_success_result_preserved(monkeypatch, tmp_path):
    """Genuine success result from original probe must be preserved intact and original evidence protected."""
    expected_result = {
        "status": "PASS_E3_LIVE",
        "sha256_verified": True,
        "process_isolated": True,
        "broker_pid": 12345,
        "desktop_pid": 54321,
        "broker_owns_oauth_provisioning": True,
        "desktop_vault_access": False,
        "broker_boundary": "HTTP_IPC_SUBPROCESS_BOUNDARY",
        "secure_storage_verified": True,
        "encryption_method": "WINDOWS_DPAPI",
        "desktop_refresh_token_retained": False,
        "desktop_disk_token_violations": 0,
    }

    mock_success = MagicMock(return_value=expected_result)
    monkeypatch.setattr(plugin, "orig_probe", mock_success)

    # 1. Direct call to patched_probe returns exact success result
    result = plugin.patched_probe("Credentials/client_secret.json")
    assert result == expected_result
    assert result["status"] == "PASS_E3_LIVE"
    assert result["sha256_verified"] is True
    mock_success.assert_called_once_with(
        "Credentials/client_secret.json",
        evidence_output_path=plugin.AUTHORIZED_EVIDENCE_PATH,
    )

    # 2. Call via probe_mod.run_live_e3_drive_probe also returns exact success result
    mock_success.reset_mock()
    probe_result = probe_mod.run_live_e3_drive_probe("Credentials/client_secret.json", account_id="acc1")
    assert probe_result == expected_result
    mock_success.assert_called_once_with(
        "Credentials/client_secret.json",
        account_id="acc1",
        evidence_output_path=plugin.AUTHORIZED_EVIDENCE_PATH,
    )

    # 3. Explicit call targeting M1 evidence path is safely redirected to authorized path
    mock_success.reset_mock()
    probe_result = probe_mod.run_live_e3_drive_probe(
        "Credentials/client_secret.json",
        evidence_output_path=plugin.M1_EVIDENCE_PATH,
    )
    assert probe_result == expected_result
    mock_success.assert_called_once_with(
        "Credentials/client_secret.json",
        evidence_output_path=plugin.AUTHORIZED_EVIDENCE_PATH,
    )

    # 4. Custom authorized path provided by caller is preserved
    custom_path = tmp_path / "custom_probe_evidence.json"
    mock_success.reset_mock()
    probe_result = probe_mod.run_live_e3_drive_probe(
        "Credentials/client_secret.json",
        evidence_output_path=custom_path,
    )
    assert probe_result == expected_result
    mock_success.assert_called_once_with(
        "Credentials/client_secret.json",
        evidence_output_path=custom_path,
    )

    # 5. Verify original M1 evidence file remains unchanged on disk even if probe tampers with it
    if plugin.M1_EVIDENCE_PATH.is_file():
        original_content = plugin.M1_EVIDENCE_PATH.read_text(encoding="utf-8")
        def rogue_probe(*args, **kwargs):
            plugin.M1_EVIDENCE_PATH.write_text('{"tampered": true}', encoding="utf-8")
            return expected_result

        monkeypatch.setattr(plugin, "orig_probe", rogue_probe)
        res = plugin.patched_probe("Credentials/client_secret.json")
        assert res == expected_result
        assert plugin.M1_EVIDENCE_PATH.read_text(encoding="utf-8") == original_content
