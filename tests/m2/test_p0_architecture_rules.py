"""Tests for Architecture Boundary Rules via AST checker (ARCH-001, ADR-0001, ADR-0002).

Test oracle:
- Positive: Current src/controlplane source tree has ZERO architecture violations.
- Negative: Domain importing external frameworks (fastapi, psycopg) is strictly caught.
- Negative: Any production controlplane code importing m1proof is strictly caught.
- Negative: Domain importing outer layers (infrastructure, api) is strictly caught.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from controlplane.infrastructure.evidence.ast_checker import (
    check_file_boundary,
    check_source_tree,
)


REPO_ROOT = Path(__file__).parents[2]
CONTROLPLANE_ROOT = REPO_ROOT / "src" / "controlplane"


def test_tst_m2_p0_001_ast_boundary_rules_clean_codebase() -> None:
    """Positive test: existing controlplane tree complies 100% with architecture boundaries."""
    violations = check_source_tree(CONTROLPLANE_ROOT)
    assert violations == [], f"Architecture boundary violations detected in clean codebase: {violations}"


def test_tst_m2_p0_001_domain_rejects_fastapi_import(tmp_path: Path) -> None:
    """Negative test: domain importing fastapi must be rejected with ARCH-RULE-002."""
    bad_domain_file = tmp_path / "domain_sample.py"
    bad_domain_file.write_text("from fastapi import APIRouter\n", encoding="utf-8")

    violations = check_file_boundary(bad_domain_file, is_domain_layer=True)
    assert len(violations) == 1
    assert violations[0].rule_violated == "ARCH-RULE-002:DOMAIN_FRAMEWORK_PURITY"
    assert "fastapi" in violations[0].message


def test_tst_m2_p0_001_domain_rejects_psycopg_import(tmp_path: Path) -> None:
    """Negative test: domain importing psycopg or psycopg_pool must be rejected."""
    bad_domain_file = tmp_path / "domain_repo.py"
    bad_domain_file.write_text("import psycopg_pool\n", encoding="utf-8")

    violations = check_file_boundary(bad_domain_file, is_domain_layer=True)
    assert len(violations) == 1
    assert violations[0].rule_violated == "ARCH-RULE-002:DOMAIN_FRAMEWORK_PURITY"
    assert "psycopg_pool" in violations[0].message


def test_tst_m2_p0_001_rejects_m1proof_prototype_import(tmp_path: Path) -> None:
    """Negative test: production code importing m1proof must be rejected with ARCH-RULE-001."""
    bad_infra_file = tmp_path / "infra_adapter.py"
    bad_infra_file.write_text("from m1proof.drive_adapter import DriveStorageAdapter\n", encoding="utf-8")

    violations = check_file_boundary(bad_infra_file, is_domain_layer=False)
    assert len(violations) == 1
    assert violations[0].rule_violated == "ARCH-RULE-001:NO_M1_PROTOTYPE_IMPORT"
    assert "m1proof" in violations[0].message


def test_tst_m2_p0_001_rejects_src_m1proof_prefix_import(tmp_path: Path) -> None:
    """Negative test: production code importing src.m1proof prefix must be rejected with ARCH-RULE-001."""
    bad_file = tmp_path / "infra_service.py"
    bad_file.write_text("import src.m1proof.environment as env\n", encoding="utf-8")

    violations = check_file_boundary(bad_file, is_domain_layer=False)
    assert len(violations) == 1
    assert violations[0].rule_violated == "ARCH-RULE-001:NO_M1_PROTOTYPE_IMPORT"
    assert "src.m1proof" in violations[0].message



def test_tst_m2_p0_001_domain_rejects_outer_layer_import(tmp_path: Path) -> None:
    """Negative test: domain importing infrastructure must be rejected with ARCH-RULE-003."""
    bad_domain_file = tmp_path / "domain_service.py"
    bad_domain_file.write_text("from controlplane.infrastructure.db import PostgresPool\n", encoding="utf-8")

    violations = check_file_boundary(bad_domain_file, is_domain_layer=True)
    assert len(violations) == 1
    assert violations[0].rule_violated == "ARCH-RULE-003:DOMAIN_ONE_WAY_DEPENDENCY"
    assert "controlplane.infrastructure" in violations[0].message
