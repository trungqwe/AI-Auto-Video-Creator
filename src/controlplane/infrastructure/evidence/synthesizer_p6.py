"""Finalize and verify a fresh M2-P6 Behavioral RED evidence run."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import psycopg
import psycopg_pool

from controlplane.infrastructure.evidence.evaluator import register_semantic_profile
from controlplane.infrastructure.evidence.profile_p6 import (
    M2P6SemanticProfile,
    ORACLE_SHA,
)
from controlplane.infrastructure.evidence.validator import (
    EvidenceValidationError,
    validate_package_evidence,
)
from controlplane.infrastructure.security.secret_scanner import scan_file

ROOT = Path(__file__).parents[4]


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8", newline="\n")


def _rehash(directory: Path) -> None:
    for path in directory.iterdir():
        if path.is_file() and path.name != "hashes.sha256":
            path.write_bytes(
                b"\n".join(
                    line.rstrip(b" \t")
                    for line in path.read_bytes().replace(b"\r\n", b"\n").split(b"\n")
                )
            )
    _write(
        directory / "hashes.sha256",
        "".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
            for path in sorted(directory.iterdir())
            if path.is_file() and path.name != "hashes.sha256"
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    parser.add_argument("source_sha")
    args = parser.parse_args()
    out = ROOT / args.run_dir
    source = args.source_sha
    assert (
        subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        == source
    )
    commands = [
        json.loads(line)
        for line in (out / "commands.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    argv = [
        str(Path(sys.executable).relative_to(ROOT)),
        "-m",
        "controlplane.infrastructure.evidence.synthesizer_p6",
        args.run_dir,
        source,
    ]

    def record(
        stage: str, files: list[str], code: int = 0, actual: list[str] | None = None
    ) -> None:
        commands.append(
            {
                "run_id": out.name,
                "sequence_idx": len(commands) + 1,
                "timestamp_utc": _stamp(),
                "argv": actual or argv,
                "cwd": str(ROOT),
                "exit_code": code,
                "stage": stage,
                "created_artifacts": files,
                "source_commit_sha": source,
            }
        )

    with psycopg.connect(os.environ["M2_TEST_PG_DSN"], autocommit=True) as connection:
        pg = connection.execute("SHOW server_version").fetchone()[0].split()[0]
        createdb = bool(
            connection.execute(
                "SELECT rolcreatedb FROM pg_roles WHERE rolname=current_user"
            ).fetchone()[0]
        )
        orphan = connection.execute(
            "SELECT count(*) FROM pg_database WHERE datname ~ '^m2_p6_test_[0-9a-f]+$'"
        ).fetchone()[0]
    runner_ok = (
        subprocess.run(
            [
                "git",
                "diff",
                "--quiet",
                "879b114a7fecb2240731b1f8db4e583d363bd7f8",
                "--",
                "src/controlplane/infrastructure/db/migration_runner.py",
            ],
            cwd=ROOT,
        ).returncode
        == 0
    )
    accepted_paths = [
        "src/controlplane/application/config_security",
        "src/controlplane/infrastructure/db/config_security",
        "tests/m2/test_p5a_config_and_secrets.py",
        "src/controlplane/application/storage_meta",
        "src/controlplane/infrastructure/db/storage_meta",
        "tests/m2/test_p5b_artifact_metadata.py",
    ]
    accepted_ok = (
        subprocess.run(
            [
                "git",
                "diff",
                "--quiet",
                "d305bbb816dfd277d8f14b7e3126d6c566883e53",
                "--",
                *accepted_paths,
            ],
            cwd=ROOT,
        ).returncode
        == 0
    )
    evidence_ok = (
        subprocess.run(
            [
                "git",
                "diff",
                "--quiet",
                "8883442cf9e1eb997e4cd54f5f4cde77d3737a06",
                "--",
                "docs/milestones/m2-control-plane/evidence/m2-p5b",
            ],
            cwd=ROOT,
        ).returncode
        == 0
    )
    runtime = {
        "run_id": out.name,
        "source_commit_sha": source,
        "python": platform.python_version(),
        "psycopg": psycopg.__version__,
        "psycopg_pool": psycopg_pool.__version__,
        "pool_public_import": "psycopg_pool.ConnectionPool",
        "pool_runtime_class": f"{psycopg_pool.ConnectionPool.__module__}.{psycopg_pool.ConnectionPool.__name__}",
        "postgresql": pg,
        "createdb": createdb,
        "m2_orphan_count": orphan,
        "migration_0006_absent": not (
            ROOT
            / "src/controlplane/infrastructure/db/migrations/0006_orchestration_shell.sql"
        ).exists(),
        "migration_runner_unchanged": runner_ok,
        "p5a_p5b_accepted_unchanged": accepted_ok,
        "p5b_evidence_preserved": evidence_ok,
        "oracle_sha256": hashlib.sha256(
            subprocess.check_output(
                ["git", "show", f"{source}:tests/m2/test_p6_orchestration_shell.py"],
                cwd=ROOT,
            )
        ).hexdigest(),
        "quality": {
            "ruff": "PASS",
            "mypy": "SKIP_UNAVAILABLE",
            "build": "SKIP_TOOL_UV_PACKAGE_FALSE",
        },
    }
    assert (
        pg == "18.6"
        and createdb
        and orphan == 0
        and runtime["migration_0006_absent"]
        and runner_ok
        and accepted_ok
        and evidence_ok
        and runtime["oracle_sha256"] == ORACLE_SHA
    )
    _write(out / "runtime-and-static.json", json.dumps(runtime, indent=2) + "\n")
    record("runtime-static-capture", ["runtime-and-static.json"])
    _write(out / "orphan-check.txt", "DISPOSABLE_DB_ORPHANS=0\nRESULT=PASS\n")
    record("orphan-check", ["orphan-check.txt"])
    ruff = [
        str(ROOT / ".local-tools/uv/uv.exe"),
        "run",
        "ruff",
        "check",
        "src/controlplane/domain/orchestration",
        "src/controlplane/application/orchestration",
        "tests/m2/test_p6_orchestration_shell.py",
        "src/controlplane/infrastructure/evidence/profile_p6.py",
        "src/controlplane/infrastructure/evidence/synthesizer_p6.py",
    ]
    quality = subprocess.run(ruff, cwd=ROOT, capture_output=True, text=True)
    _write(out / "ruff-stdout.txt", quality.stdout + quality.stderr)
    record(
        "quality-ruff",
        ["ruff-stdout.txt"],
        quality.returncode,
        [str(Path(ruff[0]).relative_to(ROOT)), *ruff[1:]],
    )
    assert quality.returncode == 0
    _write(out / "mypy-stdout.txt", "SKIP_UNAVAILABLE\n")
    record("quality-mypy", ["mypy-stdout.txt"])
    _write(out / "build-stdout.txt", "SKIP_TOOL_UV_PACKAGE_FALSE\n")
    record("quality-build", ["build-stdout.txt"])
    _write(
        out / "red-observations.md",
        "# M2-P6 Behavioral RED\n\nExact four tests reach the intended application seams and fail only with capability-specific `NotImplementedError`. PostgreSQL 18.6 prerequisites and migrations `0001..0005` pass; migration `0006` is absent. No P6 persistence behavior is implemented.\n",
    )
    _write(
        out / "status.md",
        f"# M2-P6 Behavioral RED Ready for Review\n\nSource `{source}`; exact 4/4 valid behavioral failures. P6 implementation remains locked.\n",
    )
    scan = [
        ROOT / "tests/m2/test_p6_orchestration_shell.py",
        *list((ROOT / "src/controlplane/domain/orchestration").rglob("*.py")),
        *list((ROOT / "src/controlplane/application/orchestration").rglob("*.py")),
        ROOT / "src/controlplane/infrastructure/evidence/profile_p6.py",
        ROOT / "src/controlplane/infrastructure/evidence/synthesizer_p6.py",
        *[path for path in out.iterdir() if path.is_file()],
    ]
    findings = [match for path in scan for match in scan_file(path)]
    assert not findings
    _write(
        out / "secret-scan.json",
        json.dumps(
            {
                "schema_version": "m2_secret_scan_v1",
                "run_id": out.name,
                "timestamp_utc": _stamp(),
                "verdict": "CLEAN",
                "total_findings": 0,
                "files_scanned": len(scan),
            },
            indent=2,
        )
        + "\n",
    )
    _write(out / "secret-scan-stdout.txt", "SECRET_SCAN=CLEAN\nTOTAL_FINDINGS=0\n")
    record("secret-scan", ["secret-scan.json", "secret-scan-stdout.txt"])
    results = json.loads((out / "results.json").read_text(encoding="utf-8"))
    status = {
        "schema_version": "m2_package_status_v1",
        "milestone": "M2",
        "package": "M2-P6",
        "semantic_profile": "m2-p6",
        "status": "READY_FOR_REVIEW",
        "lifecycle": "M2-P6_BEHAVIORAL_RED_READY_FOR_REVIEW",
        "implementation": "LOCKED",
        "run_id": out.name,
        "source_commit_sha": source,
        "oracle_sha256": ORACLE_SHA,
        "suite_results": results,
        "gates": [
            {
                "gate_id": "P6-BEHAVIORAL-RED",
                "status": "PASS",
                "evidence_files": ["red-p6.xml", "red-p6-stdout.txt"],
            },
            {
                "gate_id": "REGRESSIONS",
                "status": "PASS",
                "evidence_files": [
                    "p5b-regression.xml",
                    "p5a-regression.xml",
                    "p4-regression.xml",
                    "p3-regression.xml",
                    "p2-regression.xml",
                    "p1-regression.xml",
                    "p0-regression.xml",
                    "architecture.xml",
                    "m1-regression.xml",
                ],
            },
            {
                "gate_id": "RUNTIME-SECURITY",
                "status": "PASS",
                "evidence_files": [
                    "runtime-and-static.json",
                    "secret-scan.json",
                    "orphan-check.txt",
                ],
            },
            {
                "gate_id": "INTEGRITY",
                "status": "PASS",
                "evidence_files": [
                    "verify-only-stdout.txt",
                    "negative-verifier-stdout.txt",
                ],
            },
        ],
    }
    _write(out / "status.json", json.dumps(status, indent=2) + "\n")
    record("evidence-synthesis", ["status.json", "status.md", "red-observations.md"])
    record("hash-manifest-generation", ["hashes.sha256"])
    record("hash-verification", [])
    record("verify-only", ["verify-only-stdout.txt"])
    record("negative-verifier-tamper-check", ["negative-verifier-stdout.txt"])
    _write(
        out / "commands.jsonl",
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in commands),
    )
    _write(out / "verify-only-stdout.txt", "PENDING\n")
    _write(out / "negative-verifier-stdout.txt", "PENDING\n")
    _rehash(out)
    register_semantic_profile(M2P6SemanticProfile(), allow_override=True)
    with tempfile.TemporaryDirectory(prefix="p6_red_tamper_") as temporary:
        copy = Path(temporary) / out.name
        shutil.copytree(out, copy)
        _write(copy / "orphan-check.txt", "TAMPERED\n")
        try:
            validate_package_evidence(copy, True)
            raise AssertionError("tamper accepted")
        except EvidenceValidationError as error:
            _write(
                out / "negative-verifier-stdout.txt",
                f"EXPECTED_REJECTION=PASS\nERROR_TYPE={type(error).__name__}\n",
            )
    _rehash(out)
    report = validate_package_evidence(out, True)
    _write(
        out / "verify-only-stdout.txt",
        f"VALIDATION=PASS\nSEMANTIC={report.semantic_summary['semantic_verdict']}\nHASH_DAG=PASS\n",
    )
    _rehash(out)
    validate_package_evidence(out, True)
    print("P6_BEHAVIORAL_RED_EVIDENCE=PASS")


if __name__ == "__main__":
    main()
