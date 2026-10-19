"""Staging root path safety for desktop materialization (CT-STO-004, CT-STO-008)."""
from __future__ import annotations

import re
from pathlib import Path, PureWindowsPath

_FORBIDDEN_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')
_RESERVED_NAMES = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{n}" for n in range(1, 10)),
        *(f"LPT{n}" for n in range(1, 10)),
    }
)


class StagingPathError(ValueError):
    """Raised when a relative path cannot be safely resolved under the staging root."""


def _split_components(relative_path: object) -> list[str]:
    if not isinstance(relative_path, str) or not relative_path:
        raise StagingPathError(f"Relative path must be a non-empty string, got {relative_path!r}")
    normalized = relative_path.replace("\\", "/")
    if normalized.startswith("/") or PureWindowsPath(normalized).anchor:
        raise StagingPathError(f"Absolute, drive, or UNC paths are not allowed: {relative_path!r}")
    parts = normalized.split("/")
    for part in parts:
        if not part.rstrip(" ."):
            raise StagingPathError(
                f"Path component cannot be empty or consist only of dots/spaces: {relative_path!r}"
            )
        if _FORBIDDEN_CHARS.search(part):
            raise StagingPathError(f"Path component contains forbidden characters: {relative_path!r}")
        stem = part.split(".", 1)[0].rstrip(" ").upper()
        if stem in _RESERVED_NAMES:
            raise StagingPathError(f"Path component matches reserved device name {stem!r}: {relative_path!r}")
    return parts


def resolve_staging_path(staging_root: Path, relative_path: str) -> Path:
    parts = _split_components(relative_path)
    root = Path(staging_root)
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink() or current.is_junction():
            raise StagingPathError(f"Path component is a symlink or junction: {part!r} in {relative_path!r}")
    resolved = current.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise StagingPathError(f"Resolved path escapes staging root: {resolved!r}")
    return resolved
