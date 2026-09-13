"""Live External Probe on Google Drive (E3 Environment) for M1-P3 Proof.

Conforms strictly to ADR-0009 Cloud Token Broker and Audit R5 requirements:
- Broker executes in an isolated SUBPROCESS with a distinct PID.
- Desktop process communicates with the Broker over an HTTP boundary.
- Broker vault is encrypted with Windows native DPAPI; zero plaintext secrets on disk.
- Desktop credentials hold ONLY ephemeral access token (refresh_token is None).
- Zero plaintext tokens on desktop disk.
"""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import io
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Flush stdout immediately
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# Ensure src directory is in sys.path
SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload

from m1proof.broker_service import (
    BrokerProcessHandle,
    start_broker_subprocess,
    stop_broker_subprocess,
    DEFAULT_VAULT_FILE,
)
from m1proof.oauth_broker import DesktopOAuthClient, audit_desktop_token_storage

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def run_live_e3_drive_probe(
    client_secrets_path: Path,
    broker_handle: Optional[BrokerProcessHandle] = None,
    account_id: str = "m1_drive_account",
    evidence_output_path: Optional[Path] = None,
    vault_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute live external verification probe on Google Drive API over a real SUBPROCESS boundary.

    Conforms to R5.1:
    - Broker subprocess is spawned FIRST.
    - Broker subprocess is the SOLE process opening/decrypting DPAPI vault and owning OAuth credentials.
    - Desktop orchestrator NEVER imports DPAPISecureVault, NEVER touches refresh token or vault file.
    - Desktop client only communicates via REST IPC with Broker and receives short-lived access tokens.
    """
    should_stop_handle = False
    handle = broker_handle
    v_path = vault_path or DEFAULT_VAULT_FILE

    # 1. Spawn isolated broker subprocess FIRST if handle not supplied
    if handle is None:
        print("[E3-PROBE] Step 1: Spawning independent CloudTokenBroker subprocess with provisioning capability...")
        handle = start_broker_subprocess(
            host="127.0.0.1",
            port=0,
            vault_path=v_path,
            provision_credentials=client_secrets_path,
        )
        should_stop_handle = True

    try:
        desktop_pid = os.getpid()
        broker_pid = handle.pid
        print(f"[E3-PROBE] Subprocess boundary verified: Desktop PID={desktop_pid}, Broker PID={broker_pid}")
        assert broker_pid != desktop_pid, "Broker PID must be distinct from Desktop PID (subprocess isolation required)!"
        assert broker_pid > 0

        # Verify broker-owned provisioning via broker status endpoint
        import urllib.request
        status_req = urllib.request.Request(f"{handle.endpoint}/api/status")
        with urllib.request.urlopen(status_req, timeout=5) as resp:
            status_data = json.loads(resp.read().decode("utf-8"))

        assert status_data.get("status") == "running"
        assert status_data.get("broker_owns_oauth_provisioning") is True
        assert status_data.get("encryption_method") == "WINDOWS_DPAPI"
        assert status_data.get("broker_boundary") == "HTTP_IPC_SUBPROCESS_BOUNDARY"

        # If account is not yet in broker, instruct broker process to provision it
        if account_id not in status_data.get("accounts", []):
            print(f"[E3-PROBE] Instructing broker process to provision '{account_id}'...")
            handle.provision_account(account_id=account_id, credentials_file=client_secrets_path)

        # 2. Desktop side: client communicates strictly with broker over HTTP IPC
        broker_url = handle.endpoint
        print(f"[E3-PROBE] Step 2: Desktop client connecting to Broker HTTP endpoint: {broker_url}...")
        desktop_client = DesktopOAuthClient(broker_url=broker_url, account_id=account_id)
        desktop_creds = desktop_client.acquire_short_lived_credentials()

        # ADR-0009 Boundary assertions
        assert desktop_creds.refresh_token is None, "Desktop credentials MUST NOT contain refresh_token!"
        assert desktop_creds.token is not None, "Desktop must acquire valid access token from broker!"

        # Audit desktop storage: 0 plaintext tokens on disk
        repo_root = Path(__file__).parents[2]
        findings = audit_desktop_token_storage(repo_root)
        assert len(findings) == 0, f"Desktop disk must contain ZERO plaintext tokens! Violations: {findings}"

        print("[E3-PROBE] ADR-0009 Desktop boundary verified: 0 refresh token retained, 0 tokens on disk, vault DPAPI encrypted in broker process.")

        service = build("drive", "v3", credentials=desktop_creds)

        # 1. Xin pre-generated ID từ Google Drive API
        print("[E3-PROBE] Step 1: Requesting pre-generated file ID from Google Drive API...")
        gen_res = service.files().generateIds(count=1).execute()
        pregenerated_id = gen_res.get("ids", [])[0]
        print(f"[E3-PROBE] Pre-generated ID obtained: {pregenerated_id[:6]}... (redacted)")

        # 2. Resumable upload artifact 64 bytes
        test_payload = b"AI_AUTO_VIDEO_CREATOR_M1_P3_LIVE_PROOF_PAYLOAD_BYTE_VERIFICATION"
        expected_size = len(test_payload)
        expected_sha256 = hashlib.sha256(test_payload).hexdigest()

        media = MediaIoBaseUpload(io.BytesIO(test_payload), mimetype="text/plain", resumable=True)
        file_metadata = {
            "id": pregenerated_id,
            "name": f"m1_p3_broker_subproc_proof_{pregenerated_id[:8]}.txt",
            "description": "M1-P3 ADR-0009 broker subprocess architecture proof temporary artifact",
        }

        print("[E3-PROBE] Step 2: Uploading 64-byte artifact with pre-generated ID via resumable upload...")
        created_file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, name, size, md5Checksum",
        ).execute()

        uploaded_id = created_file.get("id")
        uploaded_size = int(created_file.get("size", 0))
        print(f"[E3-PROBE] Upload successful! ID: {uploaded_id[:6]}..., Size: {uploaded_size} bytes")

        # 3. Download và kiểm tra byte integrity & SHA-256
        print("[E3-PROBE] Step 3: Downloading byte stream to verify SHA-256 byte integrity...")
        request = service.files().get_media(fileId=uploaded_id)
        downloaded_buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(downloaded_buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        downloaded_bytes = downloaded_buffer.getvalue()
        actual_sha256 = hashlib.sha256(downloaded_bytes).hexdigest()
        assert actual_sha256 == expected_sha256, "SHA-256 mismatch on downloaded Google Drive file!"
        assert len(downloaded_bytes) == expected_size, "Size mismatch on downloaded Google Drive file!"
        print(f"[E3-PROBE] Byte integrity verified 100%! SHA-256: {actual_sha256[:16]}... matched.")

        # 4. Dọn dẹp artifact test trên Drive
        print("[E3-PROBE] Step 4: Cleaning up test artifact from Google Drive...")
        service.files().delete(fileId=uploaded_id).execute()
        print("[E3-PROBE] Cleanup complete.")

        now_iso = datetime.now(timezone.utc).isoformat()
        result: Dict[str, Any] = {
            "status": "PASS_E3_LIVE",
            "architecture": "ADR-0009_CLOUD_TOKEN_BROKER",
            "broker_boundary": "HTTP_IPC_SUBPROCESS_BOUNDARY",
            "process_isolated": True,
            "broker_pid": broker_pid,
            "desktop_pid": desktop_pid,
            "broker_endpoint": handle.endpoint,
            "broker_owns_oauth_provisioning": True,
            "desktop_vault_access": False,
            "desktop_refresh_token_retained": False,
            "secure_storage_verified": True,
            "encryption_method": "WINDOWS_DPAPI",
            "desktop_disk_token_violations": 0,
            "pregenerated_id_redacted": f"{uploaded_id[:6]}...{uploaded_id[-4:]}",
            "byte_size": expected_size,
            "sha256_verified": True,
            "sha256_hash": actual_sha256,
            "scope": DRIVE_SCOPES[0],
            "timestamp_utc": now_iso,
            "limitations": "DPAPI proof runs under one Windows user; OS-account isolation between cloud host and desktop belongs to later deployment validation.",
        }

        # Ghi nhận bằng chứng machine-readable
        out_path = evidence_output_path or (repo_root / "docs" / "milestones" / "m1-proof" / "evidence" / "m1-p3" / "drive_e3_evidence.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"[E3-PROBE] Machine-readable evidence written to {out_path}")

        return result
    finally:
        if should_stop_handle and handle:
            stop_broker_subprocess(handle)


if __name__ == "__main__":
    secrets_file = Path("Credentials/client_secret_900503434223-mgnj2rdgf5v6hmgfe4dqbgatid7iiqtu.apps.googleusercontent.com.json")
    res = run_live_e3_drive_probe(secrets_file)
    print("\n[FINAL RESULT]", json.dumps(res, indent=2))
