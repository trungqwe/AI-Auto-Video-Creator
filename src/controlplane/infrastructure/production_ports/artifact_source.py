"""PP-4: StagingArtifactSource, the read-only ArtifactSourcePort over a staging directory.

ASSUMPTION (D8, OI-PP-03): the file name inside the staging directory is the artifact_version_id.
The reference is checked with a pattern of its own; the resolved path must stay inside the staging root and be a regular file. The stream is opened 'rb' and nothing is created, changed or deleted.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import BinaryIO

_ARTIFACT_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}')
_INVALID_REF = 'INVALID_ARTIFACT_REF'
_NOT_FOUND = 'ARTIFACT_NOT_FOUND'


class StagingArtifactSource:
    def __init__(self, staging_root: Path) -> None:
        if not isinstance(staging_root, Path) or not staging_root.is_absolute():
            raise ValueError('staging_root must be an absolute Path')
        self._root = staging_root

    def open(self, artifact_version_id: str) -> BinaryIO:
        if not isinstance(artifact_version_id, str) or _ARTIFACT_ID.fullmatch(artifact_version_id) is None:
            raise ValueError(_INVALID_REF)
        base = self._root.resolve()
        candidate = (self._root / artifact_version_id).resolve()
        if base not in candidate.parents:
            raise ValueError(_INVALID_REF)
        if not candidate.exists():
            raise FileNotFoundError(_NOT_FOUND)
        if not candidate.is_file():
            raise ValueError(_INVALID_REF)
        return candidate.open('rb')


__all__ = ['StagingArtifactSource']
