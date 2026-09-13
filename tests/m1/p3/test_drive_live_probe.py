"""Live External Verification test on Google Drive E3 environment."""
from pathlib import Path
import pytest
from m1proof.drive_live_probe import run_live_e3_drive_probe

REPOSITORY_ROOT = Path(__file__).parents[3]


def test_live_e3_drive_verification(credentials_path: Path):
    """Run live external proof on Google Drive using genuine credentials and HTTP broker boundary."""
    assert credentials_path.is_file(), f"Live credentials required at {credentials_path}"

    result = run_live_e3_drive_probe(credentials_path)
    assert result["status"] == "PASS_E3_LIVE"
    assert result["sha256_verified"] is True
    assert result["desktop_refresh_token_retained"] is False
    assert result["desktop_disk_token_violations"] == 0
