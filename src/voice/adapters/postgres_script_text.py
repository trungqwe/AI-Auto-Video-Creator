"""Real ScriptTextPort over controlplane.cp_script_versions (PW-E2, CT-TTS-001, CONV-E-07). Reads the stored script version of one workspace by script_version_id (the script_ref); nothing comes from a command payload. The stored payload has no fingerprint column, so the fingerprint is computed with the rule of D: request_hash of {'narration': segment texts in stored order}."""
from __future__ import annotations

import json
from typing import Any

from controlplane.application.idempotency.canonicalization import request_hash
from voice.ports.script_text import ScriptText

_SELECT = (
    'SELECT payload FROM controlplane.cp_script_versions '
    'WHERE workspace_id = %s::uuid AND script_version_id = %s ORDER BY revision DESC LIMIT 1'
)


class ScriptVersionNotFound(LookupError):
    def __init__(self, script_version_id: str) -> None:
        self.script_version_id = script_version_id
        super().__init__(f'script version not found: {script_version_id}')


class ScriptPayloadInvalid(ValueError):
    pass


class PostgresScriptText:
    def __init__(self, manager: Any, *, workspace_id: str) -> None:
        if not isinstance(workspace_id, str) or not workspace_id:
            raise ValueError('workspace_id must be a non-empty string')
        self._manager = manager
        self._workspace_id = workspace_id

    def get_text(self, script_version_id: str) -> ScriptText:
        if not isinstance(script_version_id, str) or not script_version_id:
            raise ValueError('script_version_id must be a non-empty string')
        with self._manager.borrow_connection() as connection:
            row = connection.execute(_SELECT, (self._workspace_id, script_version_id)).fetchone()
        if row is None:
            raise ScriptVersionNotFound(script_version_id)
        payload = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        segments = payload.get('segments') if isinstance(payload, dict) else None
        if not isinstance(segments, list) or not segments:
            raise ScriptPayloadInvalid('stored script has no segments')
        narration = [segment.get('text') if isinstance(segment, dict) else None for segment in segments]
        if not all(isinstance(text, str) and text.strip() for text in narration):
            raise ScriptPayloadInvalid('stored script segment text is not a non-empty string')
        return ScriptText(script_version_id, ' '.join(narration), request_hash({'narration': narration}))


__all__ = ('PostgresScriptText', 'ScriptPayloadInvalid', 'ScriptVersionNotFound')
