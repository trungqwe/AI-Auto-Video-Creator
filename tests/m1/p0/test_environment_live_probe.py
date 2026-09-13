import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "src"))

from m1proof import environment


BOOTSTRAP = ROOT / "docs/milestones/m1-proof/evidence/m1-p0/bootstrap.json"
DSN = "postgresql://postgres@127.0.0.1:55432/aiavc_m1"


def test_capture_and_validation_probe_live_workspace(tmp_path: Path) -> None:
    manifest = tmp_path / "environment.json"
    environment.capture_environment(
        BOOTSTRAP, manifest, project_root=ROOT, postgresql_dsn=DSN
    )
    environment.validate_environment_manifest(
        BOOTSTRAP, manifest, project_root=ROOT, postgresql_dsn=DSN
    )


def test_validation_detects_live_lockfile_drift(tmp_path: Path) -> None:
    manifest = tmp_path / "environment.json"
    environment.capture_environment(
        BOOTSTRAP, manifest, project_root=ROOT, postgresql_dsn=DSN
    )
    project = tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_bytes((ROOT / "pyproject.toml").read_bytes())
    (project / "uv.lock").write_bytes((ROOT / "uv.lock").read_bytes())
    with (project / "uv.lock").open("a", encoding="utf-8") as target:
        target.write("\n# drift\n")

    with pytest.raises(ValueError, match="uv.lock live hash mismatch"):
        environment.validate_environment_manifest(
            BOOTSTRAP, manifest, project_root=project, postgresql_dsn=DSN
        )


def test_capture_fails_when_postgresql_endpoint_is_not_live(tmp_path: Path) -> None:
    with pytest.raises(environment.EnvironmentProbeError, match="PostgreSQL"):
        environment.capture_environment(
            BOOTSTRAP,
            tmp_path / "environment.json",
            project_root=ROOT,
            postgresql_dsn="postgresql://postgres@127.0.0.1:1/aiavc_m1?connect_timeout=1",
        )
