"""Pytest fixtures for M1-P5 Compatibility Smoke."""
from __future__ import annotations
import os
import shutil
import sys
from pathlib import Path
import pytest

REPOSITORY_ROOT = Path(__file__).parents[3]
src_path = str(REPOSITORY_ROOT / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

@pytest.fixture
def repo_root() -> Path:
    return REPOSITORY_ROOT

@pytest.fixture
def lock_file_path() -> Path:
    return REPOSITORY_ROOT / "uv.lock"

@pytest.fixture
def ffmpeg_bin_path() -> str:
    win_custom = Path(r"C:\ffmpeg\bin\ffmpeg.exe")
    if win_custom.is_file():
        return str(win_custom)
    which_bin = shutil.which("ffmpeg")
    if which_bin:
        return which_bin
    return "ffmpeg"

@pytest.fixture
def sample_media_fixture(tmp_path: Path) -> Path:
    """Provide a small synthetic media file for probe testing."""
    fixture_file = tmp_path / "smoke_test_fixture.mp4"
    # Dùng header MP4 tối thiểu hoặc synthetic byte stream có thể probe
    fixture_file.write_bytes(b"\x00\x00\x00\x1cftypisom\x00\x00\x02\x00isomiso2mp41\x00\x00\x00\x08free")
    return fixture_file
