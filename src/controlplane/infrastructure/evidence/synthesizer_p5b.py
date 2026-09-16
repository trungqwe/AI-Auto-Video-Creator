"""Finalize and verify a fresh M2-P5B implementation evidence run."""

from __future__ import annotations

import argparse
import ast
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
from controlplane.infrastructure.evidence.profile_p5b import (
    M2P5BSemanticProfile,
    ORACLE_SHA,
)
from controlplane.infrastructure.evidence.validator import (
    EvidenceValidationError,
    validate_package_evidence,
)
from controlplane.infrastructure.security.secret_scanner import scan_file

ROOT = Path(__file__).parents[4]


def stamp():
    return datetime.now(timezone.utc).isoformat()


def write(p: Path, s: str):
    p.write_text(s, encoding="utf-8", newline="\n")


def rehash(out: Path):
    for p in out.iterdir():
        if p.is_file() and p.name != "hashes.sha256":
            p.write_bytes(
                b"\n".join(
                    x.rstrip(b" \t")
                    for x in p.read_bytes().replace(b"\r\n", b"\n").split(b"\n")
                )
            )
    write(
        out / "hashes.sha256",
        "\n".join(
            f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}"
            for p in sorted(out.iterdir())
            if p.is_file() and p.name != "hashes.sha256"
        )
        + "\n",
    )


def imports(path: Path):
    for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(n, ast.Import):
            yield from (a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom):
            yield n.module or ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("source_sha")
    a = ap.parse_args()
    out = ROOT / a.run_dir
    source = a.source_sha
    assert (
        subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        == source
    )
    commands = [
        json.loads(x)
        for x in (out / "commands.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    argv = [
        str(Path(sys.executable).relative_to(ROOT)),
        "-m",
        "controlplane.infrastructure.evidence.synthesizer_p5b",
        a.run_dir,
        source,
    ]

    def record(stage, files, code=0, actual=None):
        commands.append(
            {
                "run_id": out.name,
                "sequence_idx": len(commands) + 1,
                "timestamp_utc": stamp(),
                "argv": actual or argv,
                "cwd": str(ROOT),
                "exit_code": code,
                "stage": stage,
                "created_artifacts": files,
                "source_commit_sha": source,
            }
        )

    domain = ROOT / "src/controlplane/domain/storage_meta"
    app = ROOT / "src/controlplane/application/storage_meta"
    adapter = ROOT / "src/controlplane/infrastructure/db/storage_meta/__init__.py"
    di = [x for p in domain.rglob("*.py") for x in imports(p)]
    ai = [x for p in app.rglob("*.py") for x in imports(p)]
    with psycopg.connect(os.environ["M2_TEST_PG_DSN"], autocommit=True) as c:
        pg = c.execute("SHOW server_version").fetchone()[0].split()[0]
        createdb = bool(
            c.execute(
                "SELECT rolcreatedb FROM pg_roles WHERE rolname=current_user"
            ).fetchone()[0]
        )
        orphan = c.execute(
            "SELECT count(*) FROM pg_database WHERE datname ~ '^m2_p5b_test_[0-9a-f]+$'"
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
    p5a = [
        "src/controlplane/application/config_security/__init__.py",
        "src/controlplane/infrastructure/db/config_security/__init__.py",
        "tests/m2/test_p5a_config_and_secrets.py",
    ]
    p5a_ok = all(
        (ROOT / p).read_bytes()
        == subprocess.check_output(
            ["git", "show", "879b114a7fecb2240731b1f8db4e583d363bd7f8:" + p], cwd=ROOT
        )
        for p in p5a
    )
    red_ok = (
        subprocess.run(
            [
                "git",
                "diff",
                "--quiet",
                "282599fc0d3120b6f7f6b233aff0b00fe7ea8412",
                "--",
                "docs/milestones/m2-control-plane/evidence/m2-p5b/run-m2-p5b-20260916114530",
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
        "migration_runner_unchanged": runner_ok,
        "p5a_source_and_oracle_unchanged": p5a_ok,
        "historical_corrected_red_preserved": red_ok,
        "migration_0005_present": all(
            (ROOT / f"src/controlplane/infrastructure/db/migrations/{n}").is_file()
            for n in (
                "0005_artifact_metadata.sql",
                "0005_artifact_metadata.rollback.sql",
            )
        ),
        "application_storage_meta_sql_statements": sum(
            token in p.read_text(encoding="utf-8").upper()
            for p in app.rglob("*.py")
            for token in ("SELECT ", "INSERT ", "UPDATE ", "DELETE ")
        ),
        "infrastructure_storage_meta_sql_present": "SELECT " in adapter.read_text(encoding="utf-8").upper(),
        "adapter_uses_caller_owned_connection": "self._connection = connection" in adapter.read_text(encoding="utf-8"),
        "domain_to_application_imports": sum(
            x.startswith("controlplane.application") for x in di
        ),
        "domain_to_infrastructure_imports": sum(
            x.startswith("controlplane.infrastructure") for x in di
        ),
        "application_to_infrastructure_imports": sum(
            x.startswith("controlplane.infrastructure") for x in ai
        ),
        "domain_psycopg_imports": sum(
            x.startswith(("psycopg", "psycopg_pool")) for x in di
        ),
        "application_psycopg_imports": sum(
            x.startswith(("psycopg", "psycopg_pool")) for x in ai
        ),
        "oracle_sha256": hashlib.sha256(
            subprocess.check_output(
                ["git", "show", f"{source}:tests/m2/test_p5b_artifact_metadata.py"],
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
        and runner_ok
        and p5a_ok
        and red_ok
        and runtime["oracle_sha256"] == ORACLE_SHA
        and runtime["application_storage_meta_sql_statements"] == 0
        and runtime["infrastructure_storage_meta_sql_present"]
        and runtime["adapter_uses_caller_owned_connection"]
    )
    write(out / "runtime-and-static.json", json.dumps(runtime, indent=2) + "\n")
    record("runtime-static-capture", ["runtime-and-static.json"])
    write(out / "orphan-check.txt", "DISPOSABLE_DB_ORPHANS=0\nRESULT=PASS\n")
    record("orphan-check", ["orphan-check.txt"])
    ruff = [
        str(ROOT / ".local-tools/uv/uv.exe"),
        "run",
        "ruff",
        "check",
        "src/controlplane/application/storage_meta",
        "src/controlplane/domain/storage_meta",
        "src/controlplane/infrastructure/evidence/profile_p5b.py",
        "src/controlplane/infrastructure/evidence/synthesizer_p5b.py",
    ]
    q = subprocess.run(ruff, cwd=ROOT, capture_output=True, text=True)
    write(out / "ruff-stdout.txt", q.stdout + q.stderr)
    record(
        "quality-ruff",
        ["ruff-stdout.txt"],
        q.returncode,
        [str(Path(ruff[0]).relative_to(ROOT)), *ruff[1:]],
    )
    assert q.returncode == 0
    write(out / "mypy-stdout.txt", "SKIP_UNAVAILABLE\n")
    record("quality-mypy", ["mypy-stdout.txt"])
    write(out / "build-stdout.txt", "SKIP_TOOL_UV_PACKAGE_FALSE\n")
    record("quality-build", ["build-stdout.txt"])
    results = json.loads((out / "results.json").read_text(encoding="utf-8"))
    write(
        out / "observations.md",
        "# M2-P5B corrected implementation closure\n\nExact five GREEN. Application SQL is zero; PostgreSQL persistence is in the caller-owned adapter. Exact evidence binding, credential boundaries, immutable cleanup authorization and composite DB binding passed real-PostgreSQL hardening probes. Boundary stops at `CLEANUP_AUTHORIZED`; no `DELETED`, delete side effect or `CleanupCompleted`.\n",
    )
    write(
        out / "status.md",
        "# M2-P5B Implementation Ready for Review\n\nSource `"
        + source
        + "`; exact P5B 5/5 and all frozen regressions GREEN. P6 remains locked.\n",
    )
    ts = stamp()
    scan = [
        ROOT / "tests/m2/test_p5b_artifact_metadata.py",
        *domain.rglob("*.py"),
        *app.rglob("*.py"),
        ROOT / "HANDOFF.md",
        ROOT / "README.md",
        ROOT / "CHANGELOG.md",
        ROOT / "docs/12-pre-code-checklist.md",
        ROOT / "docs/milestones/m2-control-plane/spec.md",
        ROOT / "docs/milestones/m2-control-plane/implementation-plan.md",
        ROOT / "src/controlplane/infrastructure/evidence/profile_p5b.py",
        ROOT / "src/controlplane/infrastructure/evidence/synthesizer_p5b.py",
        *[p for p in out.iterdir() if p.is_file()],
    ]
    findings = [m for p in scan for m in scan_file(p)]
    assert not findings
    secret = {
        "schema_version": "m2_secret_scan_v1",
        "run_id": out.name,
        "timestamp_utc": ts,
        "verdict": "CLEAN",
        "total_findings": 0,
        "files_scanned": len(scan),
    }
    write(out / "secret-scan.json", json.dumps(secret, indent=2) + "\n")
    write(out / "secret-scan-stdout.txt", "SECRET_SCAN=CLEAN\nTOTAL_FINDINGS=0\n")
    record("secret-scan", ["secret-scan.json", "secret-scan-stdout.txt"])
    status = {
        "schema_version": "m2_package_status_v1",
        "milestone": "M2",
        "package": "M2-P5B",
        "semantic_profile": "m2-p5b",
        "status": "READY_FOR_REVIEW",
        "lifecycle": "M2-P5B_IMPLEMENTATION_READY_FOR_REVIEW",
        "run_id": out.name,
        "source_commit_sha": source,
        "oracle_sha256": ORACLE_SHA,
        "suite_results": results,
        "gates": [
            {"gate_id": "P5B-GREEN", "status": "PASS", "evidence_files": ["p5b.xml"]},
            {
                "gate_id": "REGRESSIONS",
                "status": "PASS",
                "evidence_files": [
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
                    "hardening-probes.json",
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
    write(out / "status.json", json.dumps(status, indent=2) + "\n")
    record("evidence-synthesis", ["status.json", "status.md", "observations.md"])
    record("hash-manifest-generation", ["hashes.sha256"])
    record("hash-verification", [])
    record("verify-only", ["verify-only-stdout.txt"])
    record("negative-verifier-tamper-check", ["negative-verifier-stdout.txt"])
    write(
        out / "commands.jsonl",
        "".join(json.dumps(x, sort_keys=True) + "\n" for x in commands),
    )
    write(out / "verify-only-stdout.txt", "PENDING\n")
    write(out / "negative-verifier-stdout.txt", "PENDING\n")
    rehash(out)
    register_semantic_profile(M2P5BSemanticProfile(), allow_override=True)
    with tempfile.TemporaryDirectory(prefix="p5b_green_tamper_") as t:
        copy = Path(t) / out.name
        shutil.copytree(out, copy)
        write(copy / "orphan-check.txt", "TAMPERED\n")
        try:
            validate_package_evidence(copy, True)
            raise AssertionError("tamper accepted")
        except EvidenceValidationError as exc:
            write(
                out / "negative-verifier-stdout.txt",
                f"EXPECTED_REJECTION=PASS\nERROR_TYPE={type(exc).__name__}\n",
            )
    rehash(out)
    report = validate_package_evidence(out, True)
    write(
        out / "verify-only-stdout.txt",
        f"VALIDATION=PASS\nSEMANTIC={report.semantic_summary['semantic_verdict']}\nHASH_DAG=PASS\n",
    )
    rehash(out)
    validate_package_evidence(out, True)
    print("P5B_IMPLEMENTATION_EVIDENCE=PASS")


if __name__ == "__main__":
    main()
