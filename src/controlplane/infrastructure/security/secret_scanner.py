"""Production Secret & Sensitive Pattern Scanner for Control Plane (ADR-0008).

Standalone scanner for M2 to ensure no plaintext tokens, private keys, or passwords
are committed or leaked in logs/evidence.
Does not import M1 prototype code.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


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
                # Redact snippet for safety
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


def scan_directory(root_dir: Path, exclude_patterns: tuple[str, ...] = (".git", ".venv", "__pycache__", "node_modules")) -> list[SecretMatch]:
    """Scan all text files under root_dir."""
    matches: list[SecretMatch] = []
    for file_path in root_dir.rglob("*"):
        if any(exc in file_path.parts for exc in exclude_patterns):
            continue
        if file_path.is_file() and file_path.suffix in (".py", ".json", ".md", ".toml", ".yaml", ".yml", ".ts", ".tsx", ".js"):
            matches.extend(scan_file(file_path))
    return matches
