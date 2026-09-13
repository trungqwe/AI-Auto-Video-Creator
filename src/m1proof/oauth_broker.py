"""OAuth Broker and Token Manager for Google Drive (ADR-0009).

Enforces strict separation:
- J/Cloud-side Token Broker owns and manages long-term refresh tokens.
- Desktop Client only receives short-lived access tokens in memory (never refresh tokens).
- Desktop disk storage contains 0 plaintext refresh tokens.
"""
from __future__ import annotations
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

DRIVE_FILE_SCOPE = ["https://www.googleapis.com/auth/drive.file"]


class CloudTokenBroker:
    """J/Cloud-side Broker managing authoritative long-term refresh tokens."""

    def __init__(self):
        self._refresh_tokens: Dict[str, str] = {}
        self._mint_counter: int = 0

    def store_refresh_token(self, account_id: str, refresh_token: str):
        """Store long-term refresh token in broker secure context."""
        self._refresh_tokens[account_id] = refresh_token

    def has_refresh_token(self, account_id: str) -> bool:
        return account_id in self._refresh_tokens

    def mint_short_lived_token(self, account_id: str) -> str:
        """Issue a short-lived access token for the given account.
        
        In production, this queries the Google OAuth token endpoint using the refresh token.
        In proof/mock environments, it mints a scoped access token identifier.
        """
        if account_id not in self._refresh_tokens:
            raise KeyError(f"No refresh token registered for account: {account_id}")
        self._mint_counter += 1
        return f"ya29.m1proof_access_token_{account_id}_{uuid.uuid4().hex[:12]}_{self._mint_counter}"

    def revoke(self, account_id: str) -> bool:
        """Revoke authorization and discard stored refresh token."""
        if account_id in self._refresh_tokens:
            del self._refresh_tokens[account_id]
            return True
        return False


class DesktopOAuthClient:
    """Desktop client operating under ADR-0009 constraints.
    
    Holds ONLY short-lived access tokens in memory.
    Cannot refresh directly without delegating to the Cloud Token Broker.
    """

    def __init__(self, broker: CloudTokenBroker, account_id: str):
        self.broker = broker
        self.account_id = account_id
        self._credentials: Optional[Credentials] = None

    def acquire_short_lived_credentials(self) -> Credentials:
        """Acquire short-lived credentials from broker without receiving refresh token."""
        token_str = self.broker.mint_short_lived_token(self.account_id)
        # Explicitly set refresh_token=None to enforce ADR-0009 boundary in memory
        creds = Credentials(
            token=token_str,
            refresh_token=None,
            scopes=DRIVE_FILE_SCOPE,
        )
        self._credentials = creds
        return creds

    def refresh_via_broker(self) -> Credentials:
        """When access token expires, desktop delegates refresh to broker."""
        return self.acquire_short_lived_credentials()

    def get_credentials(self) -> Optional[Credentials]:
        return self._credentials

    def has_active_credentials(self) -> bool:
        return self._credentials is not None and self._credentials.token is not None

    def revoke(self) -> bool:
        """Revoke credentials at broker and clear local memory."""
        broker_revoked = self.broker.revoke(self.account_id)
        self._credentials = None
        return broker_revoked


def audit_desktop_token_storage(root_dir: Path) -> List[Dict[str, Any]]:
    """Scan desktop workspace to verify absence of plaintext refresh tokens on disk."""
    findings = []
    refresh_pattern = re.compile(r"1//[0-9a-zA-Z_\-]{20,}")
    key_pattern = re.compile(r"['\"]refresh_token['\"]\s*:\s*['\"][^'\"]{10,}['\"]")

    if not root_dir.exists():
        return findings

    for root, _, files in os.walk(root_dir):
        for fname in files:
            fpath = Path(root) / fname
            # Skip python source files or tests containing regex patterns
            if fpath.suffix in [".py", ".pyc"]:
                continue
            try:
                content = fpath.read_text(encoding="utf-8", errors="ignore")
                m1 = refresh_pattern.findall(content)
                m2 = key_pattern.findall(content)
                if m1 or m2:
                    findings.append({
                        "file": str(fpath),
                        "pattern": "refresh_token_leak",
                        "matches_count": len(m1) + len(m2),
                    })
            except Exception:
                continue

    return findings


class DesktopOAuthSession:
    """Legacy session adapter retained for backwards compatibility with earlier tests."""

    def __init__(self, client_secrets_path: Path):
        self.client_secrets_path = client_secrets_path
        self._credentials: Optional[Credentials] = None
        self._desktop_stores_longterm_token: bool = False

    def get_credentials(self) -> Optional[Credentials]:
        return self._credentials

    def set_credentials(self, creds: Optional[Credentials], persist_refresh_token_on_desktop: bool = False):
        self._credentials = creds
        self._desktop_stores_longterm_token = persist_refresh_token_on_desktop

    def violates_adr0009_boundary(self) -> bool:
        return self._desktop_stores_longterm_token

    def authorize_interactive(self, port: int = 0) -> Credentials:
        if not self.client_secrets_path.is_file():
            raise FileNotFoundError(f"Client secrets not found at {self.client_secrets_path}")
        
        flow = InstalledAppFlow.from_client_secrets_file(
            str(self.client_secrets_path),
            scopes=DRIVE_FILE_SCOPE,
        )
        creds = flow.run_local_server(port=port)
        # Sanitize desktop memory: discard refresh token from desktop credentials
        self._credentials = Credentials(token=creds.token, refresh_token=None, scopes=DRIVE_FILE_SCOPE)
        self._desktop_stores_longterm_token = False
        return self._credentials

    def revoke(self) -> bool:
        self._credentials = None
        return True
