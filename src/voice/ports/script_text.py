"""ScriptTextPort: E-local read port for script text and the D-computed fingerprint (CT-TTS-001, CONV-E-07).

Pure declarations: no I/O. The fingerprint is computed by D and carried through as given; E never recomputes it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ScriptText:
    """Text of one exact script version with the fingerprint D computed for it."""

    script_version_id: str
    text: str
    script_fingerprint: str


@runtime_checkable
class ScriptTextPort(Protocol):
    def get_text(self, script_version_id: str) -> ScriptText:
        """Return the text and D-computed fingerprint of the exact script version."""
        ...
