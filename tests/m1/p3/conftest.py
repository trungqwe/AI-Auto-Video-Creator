"""Pytest fixtures and configuration for M1-P3 Google Drive & OAuth proof."""
import sys
from pathlib import Path
import pytest

REPOSITORY_ROOT = Path(__file__).parents[3]
src_path = str(REPOSITORY_ROOT / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

@pytest.fixture
def credentials_path() -> Path:
    """Find the client secrets JSON in Credentials/ directory."""
    creds_dir = REPOSITORY_ROOT / "Credentials"
    files = list(creds_dir.glob("client_secret_*.json"))
    if files:
        return files[0]
    # Fallback to default name if exists
    fallback = creds_dir / "client_secret.json"
    return fallback
