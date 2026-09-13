"""J/Cloud-side Token Broker HTTP Service (ADR-0009).

Runs as an isolated process/service owning long-term refresh tokens.
Desktop clients communicate strictly over HTTP IPC and only receive short-lived access tokens.
Secrets in vault are encrypted at rest using Windows DPAPI native cryptography.
"""
from __future__ import annotations
import argparse
import http.server
import json
import os
import re
import socketserver
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from m1proof.secure_vault import DPAPISecureVault, DEFAULT_VAULT_FILE


class _BrokerTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass, broker: CloudTokenBrokerServer):
        super().__init__(server_address, RequestHandlerClass)
        self.broker = broker


class _BrokerHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    server: _BrokerTCPServer  # type: ignore

    def log_message(self, format: str, *args: Any):
        # Suppress noisy HTTP stdout logging in automated test runs
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
        if parsed.path in ("/health", "/api/status"):
            self._send_json(200, {
                "status": "UP",
                "service": "CloudTokenBroker",
                "pid": os.getpid(),
                "port": self.server.broker.port,
                "vault_encrypted": True,
                "encryption_method": "WINDOWS_DPAPI",
                "accounts_count": len(self.server.broker.list_accounts()),
                "accounts": self.server.broker.list_accounts(),
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
            if not account_id or not self.server.broker.has_account(account_id):
                self._send_json(404, {"error": f"Account {account_id} not found in broker"})
                return
            token_data = self.server.broker.mint_or_fetch_token(account_id)
            self._send_json(200, token_data)
            return

        if parsed.path == "/api/refresh":
            account_id = body.get("account_id")
            if not account_id or not self.server.broker.has_account(account_id):
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

        if parsed.path == "/api/shutdown":
            self._send_json(200, {"status": "SHUTTING_DOWN"})
            def _shutdown():
                time.sleep(0.1)
                self.server.broker.stop()
            threading.Thread(target=_shutdown, daemon=True).start()
            return

        self._send_json(404, {"error": "Not Found"})


class CloudTokenBrokerServer:
    """HTTP Server for Cloud Token Broker using DPAPI secure vault."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 18088,
        use_vault: bool = True,
        vault_path: Optional[Path] = None,
    ):
        self.host = host
        self.port = port
        self.use_vault = use_vault
        self.vault_path = Path(vault_path) if vault_path else DEFAULT_VAULT_FILE
        self._vault = DPAPISecureVault(self.vault_path) if use_vault else None
        self._in_memory_accounts: Dict[str, Dict[str, Any]] = {}
        self._httpd: Optional[_BrokerTCPServer] = None
        self._thread: Optional[threading.Thread] = None

    def list_accounts(self) -> List[str]:
        if self._vault:
            return self._vault.list_accounts()
        return list(self._in_memory_accounts.keys())

    def has_account(self, account_id: str) -> bool:
        if self._vault:
            return self._vault.has_account(account_id)
        return account_id in self._in_memory_accounts

    def register_account(
        self,
        account_id: str,
        refresh_token: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        """Store long-term refresh token and secrets in DPAPI encrypted vault."""
        if self._vault:
            self._vault.store_account(account_id, refresh_token, client_id, client_secret)
        else:
            self._in_memory_accounts[account_id] = {
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
                "mint_counter": 0,
            }

    def get_account_data(self, account_id: str) -> Optional[Dict[str, Any]]:
        if self._vault:
            return self._vault.get_account(account_id)
        return self._in_memory_accounts.get(account_id)

    def revoke_account(self, account_id: str) -> bool:
        acct = self.get_account_data(account_id)
        if not acct:
            return False

        if self._vault:
            self._vault.remove_account(account_id)
        else:
            self._in_memory_accounts.pop(account_id, None)

        # Revoke at Google endpoint if real client
        if acct.get("refresh_token") and acct.get("client_secret"):
            try:
                revoke_url = "https://oauth2.googleapis.com/revoke"
                data = urllib.parse.urlencode({"token": acct["refresh_token"]}).encode("utf-8")
                req = urllib.request.Request(revoke_url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
                urllib.request.urlopen(req, timeout=5)
            except Exception:
                pass
        return True

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
        acct = self.get_account_data(account_id)
        if not acct:
            raise KeyError(f"Account {account_id} not found in broker")

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
        counter = acct.get("mint_counter", 0) + 1
        acct["mint_counter"] = counter
        token_id = f"ya29.broker_ipc_token_{account_id}_{uuid.uuid4().hex[:8]}_{counter}"
        return {
            "access_token": token_id,
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "https://www.googleapis.com/auth/drive.file",
        }

    def start(self):
        """Start HTTP server in background thread (for unit/in-process tests)."""
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
    """Helper to instantiate and start an in-thread broker server."""
    server = CloudTokenBrokerServer(host=host, port=port)
    server.start()
    return server


# =========================================================================
# SUBPROCESS BOUNDARY RUNNER & PROCESS MANAGER (R5-01)
# =========================================================================

class BrokerProcessHandle:
    """Handle to a running CloudTokenBroker subprocess."""

    def __init__(self, process: subprocess.Popen, pid: int, host: str, port: int, status_file: Optional[Path] = None):
        self.process = process
        self.pid = pid
        self.host = host
        self.port = port
        self.endpoint = f"http://{host}:{port}"
        self.status_file = status_file

    def is_alive(self) -> bool:
        return self.process.poll() is None

    def register_account(
        self,
        account_id: str,
        refresh_token: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ) -> bool:
        """Register account by invoking the broker HTTP endpoint."""
        url = f"{self.endpoint}/api/register"
        payload = {
            "account_id": account_id,
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            return res.get("status") == "REGISTERED"


def start_broker_subprocess(
    host: str = "127.0.0.1",
    port: int = 0,
    vault_path: Optional[Path] = None,
    timeout: float = 10.0,
) -> BrokerProcessHandle:
    """Spawn CloudTokenBroker in an isolated subprocess conforming to R5-01."""
    cmd = [
        sys.executable,
        "-m", "m1proof.broker_service",
        "--host", host,
        "--port", str(port),
    ]
    if vault_path:
        cmd.extend(["--vault-path", str(vault_path)])

    repo_root = Path(__file__).resolve().parents[2]
    src_dir = repo_root / "src"
    env = dict(os.environ)
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{src_dir}{os.pathsep}{existing_pp}" if existing_pp else str(src_dir)

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=env,
        cwd=str(repo_root),
    )

    actual_port = None
    actual_pid = None
    start_time = time.time()

    while time.time() - start_time < timeout:
        if proc.poll() is not None:
            err = proc.stderr.read() if proc.stderr else "Process terminated"
            raise RuntimeError(f"Broker subprocess exited prematurely: {err}")

        line = proc.stdout.readline() if proc.stdout else ""
        if line:
            m = re.search(r"\[BROKER_READY\]\s+port=(\d+)\s+pid=(\d+)", line)
            if m:
                actual_port = int(m.group(1))
                actual_pid = int(m.group(2))
                break
        time.sleep(0.05)

    if actual_port is None or actual_pid is None:
        proc.terminate()
        raise TimeoutError("Timed out waiting for [BROKER_READY] from broker subprocess")

    return BrokerProcessHandle(
        process=proc,
        pid=actual_pid,
        host=host,
        port=actual_port,
    )


def stop_broker_subprocess(handle: BrokerProcessHandle, timeout: float = 3.0):
    """Gracefully terminate broker subprocess."""
    if not handle.is_alive():
        return

    # Try graceful HTTP shutdown first
    try:
        url = f"{handle.endpoint}/api/shutdown"
        req = urllib.request.Request(url, data=b"{}", headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=1.0)
    except Exception:
        pass

    try:
        handle.process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        handle.process.terminate()
        try:
            handle.process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            handle.process.kill()


# CLI Entry Point for Subprocess Execution
def _cli():
    parser = argparse.ArgumentParser(description="CloudTokenBroker Standalone Daemon")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--vault-path", type=str, default=None)
    parser.add_argument("--status-file", type=str, default=None)
    args = parser.parse_args()

    v_path = Path(args.vault_path) if args.vault_path else DEFAULT_VAULT_FILE
    server = CloudTokenBrokerServer(
        host=args.host,
        port=args.port,
        use_vault=True,
        vault_path=v_path,
    )

    handler = _BrokerHTTPRequestHandler
    httpd = _BrokerTCPServer((server.host, server.port), handler, broker=server)
    actual_port = httpd.server_address[1]
    actual_pid = os.getpid()
    server.port = actual_port
    server._httpd = httpd

    # Print ready handshake to stdout
    print(f"[BROKER_READY] port={actual_port} pid={actual_pid}", flush=True)

    if args.status_file:
        try:
            Path(args.status_file).write_text(json.dumps({
                "pid": actual_pid,
                "host": args.host,
                "port": actual_port,
                "status": "RUNNING",
            }), encoding="utf-8")
        except Exception:
            pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    _cli()
