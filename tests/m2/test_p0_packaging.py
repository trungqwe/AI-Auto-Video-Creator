"""Tests for Packaging Strategy, Toolchain Locks & Skeleton Interfaces (ARCH-001, ADR-0007).

Verifies:
1. controlplane package can be imported directly without sys.path hacks.
2. CLI entrypoint controlplane.entrypoint:main executes cleanly.
3. No sys.path hacks exist in production controlplane code.
4. src/controlplane/pyproject.toml defines valid PEP 517/621 package metadata.
5. src/controlplane/ui/package.json strictly exact-pins all dependencies.
6. No extraneous npm lockfile exists at repo root.
7. Pure domain skeleton interfaces raise NotImplementedError on abstract invocations.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parents[2]
CONTROLPLANE_SRC = REPO_ROOT / "src"


def test_tst_m2_p0_003_controlplane_import_without_syspath_hack() -> None:
    """Positive test: controlplane must be importable as a regular package."""
    import controlplane
    import controlplane.entrypoint as ep

    assert controlplane.__file__ is not None
    assert ep.main() == 0


def test_tst_m2_p0_003_no_syspath_hacks_in_controlplane_source() -> None:
    """Positive test: production controlplane code must not use sys.path hacks."""
    for py_file in (CONTROLPLANE_SRC / "controlplane").rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        assert "sys.path.insert" not in content, f"sys.path hack found in production file: {py_file}"
        assert "sys.path.append" not in content, f"sys.path hack found in production file: {py_file}"


def test_tst_m2_p0_003_subprocess_clean_import() -> None:
    """Positive test: fresh python subprocess can import controlplane and invoke entrypoint."""
    code = "import controlplane; import controlplane.entrypoint as ep; assert ep.main() == 0"
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, f"Subprocess import failed: {result.stderr}"
    assert "AI Auto Video Creator - Control Plane" in result.stdout


def test_tst_m2_p0_003_pyproject_metadata() -> None:
    """Positive test: controlplane/pyproject.toml specifies exact package metadata."""
    pyproject_file = REPO_ROOT / "src" / "controlplane" / "pyproject.toml"
    assert pyproject_file.is_file(), "src/controlplane/pyproject.toml must exist"

    content = pyproject_file.read_text(encoding="utf-8")
    assert 'name = "controlplane"' in content
    assert 'version = "0.2.0"' in content
    assert 'fastapi==0.141.1' in content
    assert 'uvicorn==0.52.4' in content
    assert 'psycopg[binary,pool]==3.3.5' in content
    assert 'httpx==0.28.1' in content


def test_tst_m2_p0_004_frontend_toolchain_exact_pins() -> None:
    """Positive test: UI package.json contains 100% exact pins (no ^, ~, or latest)."""
    ui_package_json = REPO_ROOT / "src" / "controlplane" / "ui" / "package.json"
    assert ui_package_json.is_file(), "src/controlplane/ui/package.json must exist"

    data = json.loads(ui_package_json.read_text(encoding="utf-8"))
    assert data["name"] == "controlplane-admin-ui"

    deps = data.get("dependencies", {})
    dev_deps = data.get("devDependencies", {})
    all_deps = {**deps, **dev_deps}

    assert len(all_deps) > 0, "UI package.json must declare dependencies"
    for dep_name, version in all_deps.items():
        assert not version.startswith("^"), f"Floating version '^' forbidden: {dep_name}: {version}"
        assert not version.startswith("~"), f"Floating version '~' forbidden: {dep_name}: {version}"
        assert version.lower() != "latest", f"Floating version 'latest' forbidden: {dep_name}"

    # Verify AG Grid Community v32-lts patch
    assert deps.get("ag-grid-community") == "32.3.9"
    assert deps.get("ag-grid-react") == "32.3.9"

    # Verify lockfile in UI dir
    lock_file = REPO_ROOT / "src" / "controlplane" / "ui" / "package-lock.json"
    assert lock_file.is_file(), "src/controlplane/ui/package-lock.json must exist"

    # Verify NO extraneous lockfile at repo root
    root_lock = REPO_ROOT / "package-lock.json"
    assert not root_lock.exists(), "Extraneous package-lock.json must NOT exist at repo root"


def test_tst_m2_p0_005_skeleton_interfaces_raise_not_implemented() -> None:
    """Positive test: domain skeleton interfaces raise NotImplementedError for P1+ behavioral RED."""
    from controlplane.domain.interfaces import (
        IRepository,
        IStateMachine,
        IUnitOfWork,
        IOutboxWriter,
        ISecretVault,
    )

    class DummyUoW(IUnitOfWork):
        def begin(self) -> None:
            return super().begin()

        def commit(self) -> None:
            return super().commit()

        def rollback(self) -> None:
            return super().rollback()

        def __enter__(self):
            return super().__enter__()

        def __exit__(self, exc_type, exc_val, exc_tb):
            return super().__exit__(exc_type, exc_val, exc_tb)

    uow = DummyUoW()
    with pytest.raises(NotImplementedError):
        uow.begin()
    with pytest.raises(NotImplementedError):
        uow.commit()
    with pytest.raises(NotImplementedError):
        uow.rollback()

    class DummyVault(ISecretVault):
        def retrieve_secret(self, secret_handle: str) -> str:
            return super().retrieve_secret(secret_handle)

    vault = DummyVault()
    with pytest.raises(NotImplementedError):
        vault.retrieve_secret("sec_handle_test")
