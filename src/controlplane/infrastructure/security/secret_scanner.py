"""Production Secret & Sensitive Pattern Scanner for Control Plane (ADR-0008).

Standalone scanner for M2 to ensure no plaintext tokens, private keys, or passwords
are committed or leaked in source code, configuration, logs, and evidence.
Does not import M1 prototype code.
"""
from __future__ import annotations

import datetime
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence


SUPPORTED_SCAN_EXTENSIONS = frozenset({
    ".py",
    ".json",
    ".jsonl",
    ".md",
    ".toml",
    ".yaml",
    ".yml",
    ".ts",
    ".tsx",
    ".js",
    ".txt",
    ".log",
    ".xml",
    ".sql",
})

SENSITIVE_PATTERNS = [
    ("PRIVATE_KEY", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("GOOGLE_CLIENT_SECRET", re.compile(r'"client_secret"\s*:\s*"[^"]+"')),
    ("BEARER_TOKEN", re.compile(r"bearer\s+[a-zA-Z0-9_\-\.]{25,}", re.IGNORECASE)),
    ("GENERIC_PASSWORD", re.compile(r'(?:password|secret|passwd)\s*[:=]\s*["\']([^"\']{8,})["\']', re.IGNORECASE)),
    ("TEMPORAL_AUTH_KEY", re.compile(r"temporal[_-]token\s*=\s*['\"][a-zA-Z0-9_\-]{20,}['\"]", re.IGNORECASE)),
]


@dataclass(frozen=True)
class SecretMatch:
    pattern_name: str
    file_path: str
    line_number: int
    matched_snippet: str


def scan_text(text: str, file_path: str = "") -> list[SecretMatch]:
    """Scan string content for sensitive pattern occurrences."""
    matches: list[SecretMatch] = []
    lines = text.splitlines()
    for line_idx, line in enumerate(lines, 1):
        for pattern_name, regex in SENSITIVE_PATTERNS:
            if regex.search(line):
                redacted = line.strip()[:60] + "...[REDACTED]"
                matches.append(
                    SecretMatch(
                        pattern_name=pattern_name,
                        file_path=file_path,
                        line_number=line_idx,
                        matched_snippet=redacted,
                    )
                )
    return matches


def scan_file(path: Path) -> list[SecretMatch]:
    """Scan file on disk for secrets."""
    if not path.is_file():
        return []
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    return scan_text(content, file_path=str(path))


def scan_directory(
    root_dir: Path,
    exclude_patterns: tuple[str, ...] = (".git", ".venv", "__pycache__", "node_modules"),
) -> list[SecretMatch]:
    """Scan all text files under root_dir including code, configs, logs, and evidence."""
    matches: list[SecretMatch] = []
    for file_path in root_dir.rglob("*"):
        if any(exc in file_path.parts for exc in exclude_patterns):
            continue
        if file_path.is_file() and file_path.suffix in SUPPORTED_SCAN_EXTENSIONS:
            matches.extend(scan_file(file_path))
    return matches


def generate_secret_scan_report(
    target_dirs: Sequence[Path],
    output_file: Path | None = None,
    exclude_patterns: tuple[str, ...] = (".git", ".venv", "__pycache__", "node_modules"),
    run_id: str | None = None,
) -> dict[str, Any]:
    """Generate machine-readable secret scan report with optional provenance run_id."""
    scanned_files_count = 0
    all_matches: list[SecretMatch] = []

    for d in target_dirs:
        if not d.exists():
            continue
        for f in d.rglob("*"):
            if any(exc in f.parts for exc in exclude_patterns):
                continue
            if f.is_file() and f.suffix in SUPPORTED_SCAN_EXTENSIONS:
                scanned_files_count += 1
                all_matches.extend(scan_file(f))

    report: dict[str, Any] = {
        "schema_version": "m2_secret_scan_v1",
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "scan_scope": {
            "directories": [str(d) for d in target_dirs],
            "supported_extensions": sorted(SUPPORTED_SCAN_EXTENSIONS),
            "excluded_patterns": list(exclude_patterns),
        },
        "total_files_scanned": scanned_files_count,
        "total_findings": len(all_matches),
        "verdict": "CLEAN" if len(all_matches) == 0 else "VIOLATIONS_DETECTED",
        "findings": [asdict(m) for m in all_matches],
    }
    if run_id is not None:
        report["run_id"] = run_id

    if output_file is not None:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return report

