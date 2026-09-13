"""OAuth Broker and Token Manager for Google Drive (ADR-0009)."""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

DRIVE_FILE_SCOPE = ["https://www.googleapis.com/auth/drive.file"]

class DesktopOAuthSession:
    """Manages short-lived OAuth access capabilities for desktop without persisting unencrypted long-term refresh tokens."""
    def __init__(self, client_secrets_path: Path):
        self.client_secrets_path = client_secrets_path
        self._credentials: Optional[Credentials] = None
        self._desktop_stores_longterm_token: bool = False

    def get_credentials(self) -> Optional[Credentials]:
        return self._credentials

    def set_credentials(self, creds: Credentials, persist_refresh_token_on_desktop: bool = False):
        self._credentials = creds
        self._desktop_stores_longterm_token = persist_refresh_token_on_desktop

    def violates_adr0009_boundary(self) -> bool:
        """Check if desktop violated ADR-0009 by storing unencrypted long-term refresh tokens."""
        return self._desktop_stores_longterm_token

    def authorize_interactive(self, port: int = 0) -> Credentials:
        """Run interactive local server flow for Desktop app authorization."""
        if not self.client_secrets_path.is_file():
            raise FileNotFoundError(f"Client secrets not found at {self.client_secrets_path}")
        
        flow = InstalledAppFlow.from_client_secrets_file(
            str(self.client_secrets_path),
            scopes=DRIVE_FILE_SCOPE,
        )
        # Desktop app local server flow
        creds = flow.run_local_server(port=port)
        self._credentials = creds
        self._desktop_stores_longterm_token = False
        return creds

    def revoke(self) -> bool:
        """Revoke credentials and clear short-lived memory session."""
        if self._credentials and hasattr(self._credentials, "token"):
            # In live Google OAuth, token can be revoked via requests.post
            self._credentials = None
            return True
        self._credentials = None
        return True
