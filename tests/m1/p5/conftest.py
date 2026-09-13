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
    """Provide a structurally valid audio media fixture (RIFF WAV) recognized by FFmpeg and ffprobe."""
    import wave
    fixture_file = tmp_path / "smoke_test_fixture.wav"
    with wave.open(str(fixture_file), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        # Generate 0.5 seconds of PCM audio frames (22050 samples = 44100 bytes)
        frames = bytes(44100)
        w.writeframes(frames)
    return fixture_file
