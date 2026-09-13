"""Pytest fixtures for M1-P6 Evidence Manifest & Audit Proof."""
from __future__ import annotations
import sys
from pathlib import Path
from typing import Any, Dict
import pytest

REPOSITORY_ROOT = Path(__file__).parents[3]
src_path = str(REPOSITORY_ROOT / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

@pytest.fixture
def repo_root() -> Path:
    return REPOSITORY_ROOT

@pytest.fixture
def sample_valid_manifest() -> Dict[str, Any]:
    """Provide a structurally complete mock manifest conforming to M1-P6 schema."""
    return {
        "schema_version": "1.0",
        "milestone": "M1",
        "version_lock": {
            "revision": "M1-R1",
            "uv_lock_sha256": "31bae731c8ec80e52fbd9a75b3969d0d556e7489f48fc13d151c0c0cfe4e9380",
        },
        "packages": {
            "m1-p0": {"status": "PASS", "evidence_files": []},
            "m1-p1": {"status": "PASS", "evidence_files": []},
            "m1-p2": {"status": "PASS", "evidence_files": []},
            "m1-p3": {"status": "PASS", "evidence_files": []},
            "m1-p4": {"status": "PASS", "evidence_files": []},
            "m1-p5": {"status": "PASS", "evidence_files": []},
        },
        "gates": {
            "G01": "PARTIALLY_PROVEN",
            "G04": "PARTIALLY_PROVEN",
            "G07": "SMOKE_COMPATIBILITY_PASS_M1_SCOPE",
        },
        "contracts_audited": ["CT-CMN-001..013", "CT-STO-005/008/009", "ADR-0003/0004/0006/0009/0010"],
    }
