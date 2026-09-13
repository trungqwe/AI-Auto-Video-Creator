"""Windows DPAPI Native Secure Vault for Cloud Token Broker (ADR-0009).

Conforms strictly to ADR-0009 and M1-P3 security requirements:
- Uses Windows DPAPI (CryptProtectData / CryptUnprotectData from Crypt32.dll) via ctypes.
- Zero plaintext refresh tokens or client secrets stored on disk.
- Vault files contain only metadata and base64-encoded DPAPI ciphertext.
- Applicable to Windows runtime environments.
"""
from __future__ import annotations
import base64
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_VAULT_DIR = Path.home() / ".cloud_token_broker"
DEFAULT_VAULT_FILE = DEFAULT_VAULT_DIR / "vault.json"


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


def _dpapi_encrypt(plaintext: bytes) -> bytes:
    """Encrypt byte payload using Windows DPAPI CryptProtectData."""
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    in_blob = _DATA_BLOB(
        len(plaintext),
        ctypes.cast(ctypes.create_string_buffer(plaintext), ctypes.POINTER(ctypes.c_byte)),
    )
    out_blob = _DATA_BLOB()

    # CRYPTPROTECT_UI_FORBIDDEN = 0x1
    flags = 0x1
    success = crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        "BrokerVaultSecret",
        None,
        None,
        None,
        flags,
        ctypes.byref(out_blob),
    )
    if not success:
        error_code = ctypes.GetLastError()
        raise OSError(f"CryptProtectData failed with Windows error code {error_code}")

    encrypted_bytes = ctypes.string_at(out_blob.pbData, out_blob.cbData)
    kernel32.LocalFree(out_blob.pbData)
    return encrypted_bytes


def _dpapi_decrypt(ciphertext: bytes) -> bytes:
    """Decrypt byte payload using Windows DPAPI CryptUnprotectData."""
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    in_blob = _DATA_BLOB(
        len(ciphertext),
        ctypes.cast(ctypes.create_string_buffer(ciphertext), ctypes.POINTER(ctypes.c_byte)),
    )
    out_blob = _DATA_BLOB()

    # CRYPTPROTECT_UI_FORBIDDEN = 0x1
    flags = 0x1
    success = crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        flags,
        ctypes.byref(out_blob),
    )
    if not success:
        error_code = ctypes.GetLastError()
        raise OSError(f"CryptUnprotectData failed with Windows error code {error_code}")

    decrypted_bytes = ctypes.string_at(out_blob.pbData, out_blob.cbData)
    kernel32.LocalFree(out_blob.pbData)
    return decrypted_bytes


class DPAPISecureVault:
    """Encrypted token vault backed by Windows Data Protection API (DPAPI)."""

    def __init__(self, vault_path: Optional[Path] = None):
        self.vault_path = Path(vault_path) if vault_path else DEFAULT_VAULT_FILE
        self._accounts: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self):
        """Load and decrypt accounts from disk, migrating legacy plaintext format if encountered."""
        if not self.vault_path.is_file():
            self._accounts = {}
            return

        try:
            raw_text = self.vault_path.read_text(encoding="utf-8")
            data = json.loads(raw_text)
        except Exception:
            self._accounts = {}
            return

        # Check if already in encrypted DPAPI format
        if isinstance(data, dict) and data.get("encrypted") is True and data.get("ciphertext"):
            try:
                cipher_bytes = base64.b64decode(data["ciphertext"])
                decrypted_bytes = _dpapi_decrypt(cipher_bytes)
                self._accounts = json.loads(decrypted_bytes.decode("utf-8"))
            except Exception as e:
                # Corrupted or inaccessible vault
                self._accounts = {}
            return

        # Legacy plaintext format: migrate immediately to DPAPI encrypted format
        if isinstance(data, dict):
            self._accounts = data
            self._save()

    def _save(self):
        """Encrypt and persist accounts to disk."""
        self.vault_path.parent.mkdir(parents=True, exist_ok=True)
        payload_bytes = json.dumps(self._accounts, indent=2).encode("utf-8")

        encrypted_bytes = _dpapi_encrypt(payload_bytes)
        b64_ciphertext = base64.b64encode(encrypted_bytes).decode("ascii")

        now_iso = datetime.now(timezone.utc).isoformat()
        vault_envelope = {
            "version": "1.0",
            "encryption": "WINDOWS_DPAPI",
            "encrypted": True,
            "ciphertext": b64_ciphertext,
            "updated_at": now_iso,
        }

        # Write envelope to disk
        self.vault_path.write_text(json.dumps(vault_envelope, indent=2), encoding="utf-8")

    def store_account(
        self,
        account_id: str,
        refresh_token: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        """Store long-term refresh token and client secrets in encrypted vault."""
        self._accounts[account_id] = {
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
            "mint_counter": 0,
        }
        self._save()

    def get_account(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve decrypted account details in memory."""
        return self._accounts.get(account_id)

    def has_account(self, account_id: str) -> bool:
        """Check if account exists in vault."""
        return account_id in self._accounts

    def remove_account(self, account_id: str) -> bool:
        """Remove account from encrypted vault."""
        if account_id in self._accounts:
            self._accounts.pop(account_id)
            self._save()
            return True
        return False

    def list_accounts(self) -> List[str]:
        """List all account IDs stored in vault."""
        return list(self._accounts.keys())
