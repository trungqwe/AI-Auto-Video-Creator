"""Tests for Packaging Strategy, Toolchain Locks & Skeleton Interfaces (ARCH-001, ADR-0007).

Verifies:
1. controlplane package can be imported directly without sys.path hacks.
2. CLI entrypoint controlplane.entrypoint:main executes cleanly.
3. No sys.path hacks exist in production controlplane code.
4. Fresh-environment isolated install: wheel builds and installs into fresh venv without .pth file.
5. Exact backend dependency lock and build system lock (setuptools 75.8.0, wheel 0.45.1).
6. Frontend machine-lock: package.json exact pins, packageManager, engines, .nvmrc, .node-version.
7. No extraneous npm lockfile exists at repo root.
8. Pure domain skeleton interfaces raise NotImplementedError on abstract invocations.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parents[2]
CONTROLPLANE_DIR = REPO_ROOT / "src" / "controlplane"
CONTROLPLANE_SRC = REPO_ROOT / "src"


def resolve_uv_executable() -> Path:
    """Resolve uv binary path from environment, PATH, or standard discovery locations.

    Fails closed: raises RuntimeError if not found. Skipping mandatory packaging gate is forbidden.
    """
    candidates = [
        os.environ.get("UV_BIN"),
        shutil.which("uv"),
        str(Path(sys.prefix) / "Scripts" / "uv.exe"),
        str(Path(sys.prefix) / "bin" / "uv"),
        os.path.join(os.environ.get("APPDATA", ""), "Python", "Python313", "Scripts", "uv.exe"),
        os.path.join(os.environ.get("USERPROFILE", ""), ".cargo", "bin", "uv.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "uv", "uv.exe"),
    ]
    for cand in candidates:
        if cand and Path(cand).is_file():
            return Path(cand).resolve()

    raise RuntimeError(
        "Mandatory toolchain binary 'uv' not found in PATH or standard installation locations. "
        "Per fail-closed packaging policy, mandatory packaging gate cannot be skipped."
    )


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


def test_tst_m2_p0_003_pyproject_and_build_lock_metadata() -> None:
    """Positive test: controlplane/pyproject.toml specifies exact package metadata and exact build system."""
    pyproject_file = CONTROLPLANE_DIR / "pyproject.toml"
    assert pyproject_file.is_file(), "src/controlplane/pyproject.toml must exist"

    content = pyproject_file.read_text(encoding="utf-8")
    assert 'name = "controlplane"' in content
    assert 'version = "0.2.0"' in content
    assert 'setuptools==75.8.0' in content
    assert 'wheel==0.45.1' in content
    assert 'fastapi==0.141.1' in content
    assert 'uvicorn==0.52.4' in content
    assert 'psycopg[binary,pool]==3.3.5' in content
    assert 'httpx==0.28.1' in content


def test_tst_m2_p0_003_backend_dependency_graph_and_build_lock() -> None:
    """Positive test: exact lockfiles exist for reproducible frozen installation."""
    uv_lock = CONTROLPLANE_DIR / "uv.lock"
    req_lock = CONTROLPLANE_DIR / "requirements.lock"
    assert uv_lock.is_file(), "src/controlplane/uv.lock must exist"
    assert req_lock.is_file(), "src/controlplane/requirements.lock must exist"

    req_content = req_lock.read_text(encoding="utf-8")
    assert "psycopg-pool==3.3.1" in req_content, "Resolved graph must lock psycopg-pool==3.3.1"
    assert "fastapi==0.141.1" in req_content
    assert "uvicorn==0.52.4" in req_content
    assert "httpx==0.28.1" in req_content
    assert "pydantic==2.13.5" in req_content


def test_tst_m2_p0_003_frozen_project_environment_install(tmp_path: Path) -> None:
    """Positive proof A: clean isolated environment installs strictly from committed requirements.lock.

    Verifies:
    1. Fresh venv contains no workspace .pth.
    2. Exact frozen graph installs from src/controlplane/requirements.lock.
    3. Observed installed versions match lockfile 100% (e.g. psycopg-pool==3.3.1, fastapi==0.141.1).
    """
    uv_path = resolve_uv_executable()
    clean_venv = tmp_path / "frozen_env"

    # 1. Create clean virtual environment
    subprocess.run(
        [str(uv_path), "venv", str(clean_venv), "--python", "3.13"],
        capture_output=True,
        text=True,
        check=True,
    )
    clean_python = clean_venv / "Scripts" / "python.exe"
    assert clean_python.is_file(), "Clean environment python executable must exist"

    # Verify NO controlplane.pth exists in clean environment
    site_packages = clean_venv / "Lib" / "site-packages"
    assert not (site_packages / "controlplane.pth").exists(), "Fresh environment must not have controlplane.pth"

    # 2. Frozen install strictly from committed requirements.lock
    req_lock = CONTROLPLANE_DIR / "requirements.lock"
    assert req_lock.is_file(), "src/controlplane/requirements.lock must exist"

    subprocess.run(
        [str(uv_path), "pip", "install", "-r", str(req_lock), "--python", str(clean_python)],
        capture_output=True,
        text=True,
        check=True,
    )

    # 3. Query observed installed versions via clean python
    query_code = (
        "import importlib.metadata as md, json\n"
        "pkgs = ['psycopg-pool', 'psycopg', 'fastapi', 'uvicorn', 'httpx', 'pydantic', 'pydantic-core']\n"
        "print(json.dumps({p: md.version(p) for p in pkgs}))\n"
    )
    res_query = subprocess.run(
        [str(clean_python), "-c", query_code],
        capture_output=True,
        text=True,
        check=True,
    )
    observed = json.loads(res_query.stdout)
    assert observed["psycopg-pool"] == "3.3.1", f"psycopg-pool mismatch: {observed}"
    assert observed["psycopg"] == "3.3.5", f"psycopg mismatch: {observed}"
    assert observed["fastapi"] == "0.141.1", f"fastapi mismatch: {observed}"
    assert observed["uvicorn"] == "0.52.4", f"uvicorn mismatch: {observed}"
    assert observed["httpx"] == "0.28.1", f"httpx mismatch: {observed}"
    assert observed["pydantic"] == "2.13.5", f"pydantic mismatch: {observed}"
    assert observed["pydantic-core"] == "2.46.5", f"pydantic-core mismatch: {observed}"


def test_tst_m2_p0_003_fresh_environment_wheel_build_and_install(tmp_path: Path) -> None:
    """Positive proof B: build wheel and install into isolated fresh virtualenv with frozen dependencies.

    Verifies:
    1. Dependencies installed from exact committed requirements.lock.
    2. Wheel built cleanly via PEP 517 build backend.
    3. Wheel installed with --no-deps to prove self-containment against frozen graph.
    4. controlplane package import and CLI entrypoint execute successfully without .pth hacks.
    """
    uv_path = resolve_uv_executable()
    clean_venv = tmp_path / "wheel_env"
    wheel_dir = tmp_path / "dist"
    wheel_dir.mkdir()

    # 1. Create clean virtual environment
    subprocess.run(
        [str(uv_path), "venv", str(clean_venv), "--python", "3.13"],
        capture_output=True,
        text=True,
        check=True,
    )
    clean_python = clean_venv / "Scripts" / "python.exe"
    assert clean_python.is_file(), "Clean environment python executable must exist"

    # Verify NO controlplane.pth exists in clean environment
    site_packages = clean_venv / "Lib" / "site-packages"
    assert not (site_packages / "controlplane.pth").exists(), "Fresh environment must not have controlplane.pth"

    # 2. Install frozen dependency set first from committed lockfile
    req_lock = CONTROLPLANE_DIR / "requirements.lock"
    subprocess.run(
        [str(uv_path), "pip", "install", "-r", str(req_lock), "--python", str(clean_python)],
        capture_output=True,
        text=True,
        check=True,
    )

    # 3. Build wheel
    subprocess.run(
        [str(uv_path), "build", "--wheel", str(CONTROLPLANE_DIR), "--out-dir", str(wheel_dir)],
        capture_output=True,
        text=True,
        check=True,
    )
    # Clean up transient build artifacts created during wheel packaging
    for transient in (CONTROLPLANE_DIR / "build", CONTROLPLANE_DIR / "controlplane.egg-info"):
        if transient.exists():
            shutil.rmtree(transient, ignore_errors=True)

    wheel_files = list(wheel_dir.glob("*.whl"))
    assert len(wheel_files) == 1, f"Expected 1 wheel file, got {wheel_files}"
    whl_path = wheel_files[0]

    # 4. Install wheel with --no-deps into clean virtualenv
    subprocess.run(
        [str(uv_path), "pip", "install", str(whl_path), "--no-deps", "--python", str(clean_python)],
        capture_output=True,
        text=True,
        check=True,
    )

    # 5. Execute import and entrypoint in fresh environment
    code = "import controlplane; import controlplane.entrypoint as ep; assert ep.main() == 0; print('FRESH_WHEEL_PASS')"
    res_run = subprocess.run(
        [str(clean_python), "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "FRESH_WHEEL_PASS" in res_run.stdout
    assert "AI Auto Video Creator - Control Plane" in res_run.stdout


def test_tst_m2_p0_003_frozen_install_rejects_mutated_lock_mismatch(tmp_path: Path) -> None:
    """Negative test: mutating lockfile to an unsatisfiable/incompatible version fails closed."""
    uv_path = resolve_uv_executable()
    clean_venv = tmp_path / "bad_env"

    subprocess.run(
        [str(uv_path), "venv", str(clean_venv), "--python", "3.13"],
        capture_output=True,
        text=True,
        check=True,
    )
    clean_python = clean_venv / "Scripts" / "python.exe"

    # Create mutated requirements.lock with nonexistent/conflicting version
    bad_lock = tmp_path / "bad_requirements.lock"
    bad_lock.write_text("psycopg-pool==999.999.999\nfastapi==0.141.1\n", encoding="utf-8")

    res = subprocess.run(
        [str(uv_path), "pip", "install", "-r", str(bad_lock), "--python", str(clean_python)],
        capture_output=True,
        text=True,
    )
    assert res.returncode != 0, "Mutated lockfile with invalid package version must fail closed"



def test_tst_m2_p0_004_frontend_toolchain_exact_pins_and_runtime_manifest() -> None:
    """Positive test: UI package.json contains 100% exact pins, packageManager, engines, .nvmrc."""
    ui_package_json = REPO_ROOT / "src" / "controlplane" / "ui" / "package.json"
    assert ui_package_json.is_file(), "src/controlplane/ui/package.json must exist"

    data = json.loads(ui_package_json.read_text(encoding="utf-8"))
    assert data["name"] == "controlplane-admin-ui"

    # Runtime declarations
    assert data.get("packageManager") == "npm@10.9.2"
    engines = data.get("engines", {})
    assert "22.17.0" in engines.get("node", "")
    assert engines.get("npm") == "10.9.2"

    # Node version manifests
    nvmrc = REPO_ROOT / "src" / "controlplane" / "ui" / ".nvmrc"
    node_version = REPO_ROOT / "src" / "controlplane" / "ui" / ".node-version"
    assert nvmrc.is_file() and "22.17.0" in nvmrc.read_text(encoding="utf-8")
    assert node_version.is_file() and "22.17.0" in node_version.read_text(encoding="utf-8")

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
