"""Live External Verification test on Google Drive E3 environment."""
from pathlib import Path
import pytest
from m1proof.drive_live_probe import run_live_e3_drive_probe

REPOSITORY_ROOT = Path(__file__).parents[3]

def test_live_e3_drive_verification(credentials_path: Path):
    """Run live external proof on Google Drive using genuine credentials."""
    if not credentials_path.is_file():
        pytest.skip(f"Live credentials not found at {credentials_path}, skipping live E3 test.")

    token_file = REPOSITORY_ROOT / "Credentials" / "token_e3_test.json"
    if not token_file.is_file():
        pytest.skip("Cached token not found. Run python src/m1proof/drive_live_probe.py first to authorize.")

    result = run_live_e3_drive_probe(credentials_path, token_file)
    assert result["status"] == "PASS_E3_LIVE"
    assert result["sha256_verified"] is True
