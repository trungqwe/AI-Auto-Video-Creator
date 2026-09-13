"""J/Cloud-side Token Broker HTTP Service (ADR-0009).

Runs as an isolated process/service owning long-term refresh tokens.
Desktop clients communicate strictly over HTTP IPC and only receive short-lived access tokens.
"""
from __future__ import annotations
import http.server
import json
import socketserver
import threading
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, Optional


class _BrokerTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass, broker: CloudTokenBrokerServer):
        super().__init__(server_address, RequestHandlerClass)
        self.broker = broker


class _BrokerHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    server: _BrokerTCPServer  # type: ignore

    def log_message(self, format: str, *args: Any):
        # Suppress noisy HTTP stdout logging in test runs
        pass

    def _send_json(self, status_code: int, data: Dict[str, Any]):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> Dict[str, Any]:
        content_len = int(self.headers.get("Content-Length", 0))
        if content_len == 0:
            return {}
        body_bytes = self.rfile.read(content_len)
        return json.loads(body_bytes.decode("utf-8"))

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/health":
            self._send_json(200, {
                "status": "UP",
                "service": "CloudTokenBroker",
                "accounts_count": len(self.server.broker.accounts),
            })
            return
        self._send_json(404, {"error": "Not Found"})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        body = self._read_json_body()

        if parsed.path == "/api/register":
            account_id = body.get("account_id")
            refresh_token = body.get("refresh_token")
            if not account_id or not refresh_token:
                self._send_json(400, {"error": "account_id and refresh_token are required"})
                return
            self.server.broker.register_account(
                account_id=account_id,
                refresh_token=refresh_token,
                client_id=body.get("client_id"),
                client_secret=body.get("client_secret"),
            )
            self._send_json(200, {"status": "REGISTERED", "account_id": account_id})
            return

        if parsed.path == "/api/token":
            account_id = body.get("account_id")
            if not account_id or account_id not in self.server.broker.accounts:
                self._send_json(404, {"error": f"Account {account_id} not found in broker"})
                return
            token_data = self.server.broker.mint_or_fetch_token(account_id)
            self._send_json(200, token_data)
            return

        if parsed.path == "/api/refresh":
            account_id = body.get("account_id")
            if not account_id or account_id not in self.server.broker.accounts:
                self._send_json(404, {"error": f"Account {account_id} not found in broker"})
                return
            token_data = self.server.broker.mint_or_fetch_token(account_id, force_refresh=True)
            self._send_json(200, token_data)
            return

        if parsed.path == "/api/revoke":
            account_id = body.get("account_id")
            if not account_id:
                self._send_json(400, {"error": "account_id is required"})
                return
            revoked = self.server.broker.revoke_account(account_id)
            self._send_json(200, {"status": "REVOKED" if revoked else "NOT_FOUND"})
            return

        self._send_json(404, {"error": "Not Found"})


BROKER_VAULT_DIR = Path.home() / ".cloud_token_broker"
BROKER_VAULT_FILE = BROKER_VAULT_DIR / "vault.json"


class CloudTokenBrokerServer:
    """Threaded HTTP Server for the Cloud Token Broker."""

    def __init__(self, host: str = "127.0.0.1", port: int = 18088, use_vault: bool = True):
        self.host = host
        self.port = port
        self.use_vault = use_vault
        self.accounts: Dict[str, Dict[str, Any]] = self._load_vault() if use_vault else {}
        self._httpd: Optional[_BrokerTCPServer] = None
        self._thread: Optional[threading.Thread] = None

    def _load_vault(self) -> Dict[str, Dict[str, Any]]:
        if BROKER_VAULT_FILE.is_file():
            try:
                return json.loads(BROKER_VAULT_FILE.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_vault(self):
        if not self.use_vault:
            return
        try:
            BROKER_VAULT_DIR.mkdir(parents=True, exist_ok=True)
            BROKER_VAULT_FILE.write_text(json.dumps(self.accounts, indent=2), encoding="utf-8")
        except Exception:
            pass

    def register_account(
        self,
        account_id: str,
        refresh_token: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        """Store long-term refresh token in broker-only isolated context."""
        self.accounts[account_id] = {
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
            "mint_counter": 0,
        }
        self._save_vault()

    def has_account(self, account_id: str) -> bool:
        return account_id in self.accounts

    def revoke_account(self, account_id: str) -> bool:
        if account_id in self.accounts:
            acct = self.accounts.pop(account_id)
            self._save_vault()
            # If genuine refresh token and client_secret, optionally call Google revoke endpoint
            if acct.get("refresh_token") and acct.get("client_secret"):
                try:
                    revoke_url = "https://oauth2.googleapis.com/revoke"
                    data = urllib.parse.urlencode({"token": acct["refresh_token"]}).encode("utf-8")
                    req = urllib.request.Request(revoke_url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
                    urllib.request.urlopen(req, timeout=5)
                except Exception:
                    pass
            return True
        return False

    def ensure_authorized_account(self, account_id: str, client_secrets_path: Path) -> bool:
        """Ensure the broker possesses a valid refresh token for the account, prompting if needed."""
        if self.has_account(account_id):
            return True

        from google_auth_oauthlib.flow import InstalledAppFlow
        flow = InstalledAppFlow.from_client_secrets_file(
            str(client_secrets_path),
            scopes=["https://www.googleapis.com/auth/drive.file"],
        )
        auth_prompt = (
            "\n=======================================================\n"
            "[CLOUD TOKEN BROKER] Authorizing Google Drive access for Broker...\n"
            "{url}\n"
            "=======================================================\n"
        )
        print("[BROKER] Initiating authorization flow to acquire long-term refresh token...")
        full_creds = flow.run_local_server(
            port=0,
            open_browser=True,
            prompt="consent",
            authorization_prompt_message=auth_prompt,
            timeout_seconds=600,
        )

        with open(client_secrets_path, "r", encoding="utf-8") as f:
            secret_data = json.load(f)
        client_info = secret_data.get("installed") or secret_data.get("web") or {}

        self.register_account(
            account_id=account_id,
            refresh_token=full_creds.refresh_token or full_creds.token,
            client_id=client_info.get("client_id"),
            client_secret=client_info.get("client_secret"),
        )
        return True

    def mint_or_fetch_token(self, account_id: str, force_refresh: bool = False) -> Dict[str, Any]:
        """Fetch real access token from Google OAuth endpoint, or mint scoped token in test mode."""
        acct = self.accounts[account_id]
        refresh_token = acct["refresh_token"]
        client_id = acct.get("client_id")
        client_secret = acct.get("client_secret")

        # Real Google token exchange if genuine credentials are present
        if client_id and client_secret and not refresh_token.startswith("1//MOCK_"):
            token_url = "https://oauth2.googleapis.com/token"
            payload = {
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }
            data = urllib.parse.urlencode(payload).encode("utf-8")
            req = urllib.request.Request(token_url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                # ADR-0009: strictly return ONLY ephemeral access token, NEVER refresh token
                return {
                    "access_token": resp_data["access_token"],
                    "expires_in": resp_data.get("expires_in", 3600),
                    "token_type": "Bearer",
                    "scope": resp_data.get("scope", "https://www.googleapis.com/auth/drive.file"),
                }

        # Mock / integration mode token issuance
        acct["mint_counter"] += 1
        counter = acct["mint_counter"]
        token_id = f"ya29.broker_ipc_token_{account_id}_{uuid.uuid4().hex[:8]}_{counter}"
        return {
            "access_token": token_id,
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "https://www.googleapis.com/auth/drive.file",
        }

    def start(self):
        """Start HTTP server in background thread."""
        handler = _BrokerHTTPRequestHandler
        self._httpd = _BrokerTCPServer((self.host, self.port), handler, broker=self)
        self.port = self._httpd.server_address[1]

        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop HTTP server and join thread."""
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
            self._thread = None


def run_broker_http_server(host: str = "127.0.0.1", port: int = 18088) -> CloudTokenBrokerServer:
    """Helper to instantiate and start a local broker server."""
    server = CloudTokenBrokerServer(host=host, port=port)
    server.start()
    return server
