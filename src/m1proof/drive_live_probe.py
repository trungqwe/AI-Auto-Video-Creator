"""Live External Probe on Google Drive (E3 Environment) for M1-P3 Proof."""
from __future__ import annotations
import hashlib
import io
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload

# Đảm bảo stdout in ngay lập tức
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]

def get_or_create_e3_credentials(client_secrets_path: Path, token_cache_path: Path) -> Credentials:
    """Retrieve existing cached credentials or run desktop authorization flow."""
    creds = None
    if token_cache_path.is_file():
        try:
            creds = Credentials.from_authorized_user_file(str(token_cache_path), DRIVE_SCOPES)
            print("[OAUTH] Found cached token at Credentials/token_e3_test.json")
        except Exception as e:
            print(f"[OAUTH] Cached token invalid: {e}")
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            print("[OAUTH] Refreshing expired access token...")
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(client_secrets_path),
                scopes=DRIVE_SCOPES,
            )
            auth_prompt = (
                "\n=======================================================\n"
                "[OAUTH REQUIRED] Please authorize Google Drive access:\n"
                "{url}\n"
                "=======================================================\n"
            )
            print("[OAUTH] Starting local HTTP server to receive OAuth callback...")
            creds = flow.run_local_server(
                port=0,
                open_browser=True,
                prompt="consent",
                authorization_prompt_message=auth_prompt,
                timeout_seconds=300,
            )

        token_cache_path.write_text(creds.to_json(), encoding="utf-8")
        print("[OAUTH] Authorization successful! Token cached securely.")

    return creds

def run_live_e3_drive_probe(client_secrets_path: Path, token_cache_path: Path) -> Dict[str, Any]:
    """Execute live external verification probe on Google Drive API."""
    creds = get_or_create_e3_credentials(client_secrets_path, token_cache_path)
    service = build("drive", "v3", credentials=creds)

    # 1. Xin pre-generated ID từ Google Drive API
    print("[E3-PROBE] Step 1: Requesting pre-generated file ID from Google Drive API...")
    gen_res = service.files().generateIds(count=1).execute()
    pregenerated_id = gen_res.get("ids", [])[0]
    print(f"[E3-PROBE] Pre-generated ID obtained: {pregenerated_id[:6]}... (redacted)")

    # 2. Resumable upload một artifact test
    test_payload = b"AI_AUTO_VIDEO_CREATOR_M1_P3_LIVE_PROOF_PAYLOAD_BYTE_VERIFICATION"
    expected_size = len(test_payload)
    expected_sha256 = hashlib.sha256(test_payload).hexdigest()
    
    media = MediaIoBaseUpload(io.BytesIO(test_payload), mimetype="text/plain", resumable=True)
    file_metadata = {
        "id": pregenerated_id,
        "name": f"m1_p3_proof_{pregenerated_id[:8]}.txt",
        "description": "M1-P3 architecture proof temporary verification artifact",
    }

    print("[E3-PROBE] Step 2: Uploading artifact with pre-generated ID using resumable upload...")
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

    return {
        "status": "PASS_E3_LIVE",
        "pregenerated_id_redacted": f"{uploaded_id[:6]}...{uploaded_id[-4:]}",
        "byte_size": expected_size,
        "sha256_verified": True,
        "sha256_hash": actual_sha256,
        "scope": DRIVE_SCOPES[0],
    }

if __name__ == "__main__":
    secrets_file = Path("Credentials/client_secret_900503434223-mgnj2rdgf5v6hmgfe4dqbgatid7iiqtu.apps.googleusercontent.com.json")
    token_file = Path("Credentials/token_e3_test.json")
    res = run_live_e3_drive_probe(secrets_file, token_file)
    print("\n[RESULT]", json.dumps(res, indent=2))
