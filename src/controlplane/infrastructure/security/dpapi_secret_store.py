"""J-17: DpapiSecretStore trên desktop, hiện thực SecretStorePort của J-10 (INV-012, CT-SEC-001)."""
from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Iterable
from pathlib import Path

from controlplane.infrastructure.security.secret_redaction import SecretValue
from controlplane.security.dpapi import dpapi_encrypt

_VERSION_FILE = re.compile(r'^v([1-9][0-9]*)\.(bin|revoked)$')


class DpapiSecretStore:
    """Lưu ciphertext DPAPI theo version; không có API đọc plaintext (INV-012)."""

    def __init__(self, root: Path, entropy: bytes | None = None) -> None:
        if entropy is not None and not isinstance(entropy, (bytes, bytearray)):
            raise TypeError('entropy must be bytes or None')
        self._root = Path(root)
        self._entropy = None if entropy is None else bytes(entropy)

    def _ref_dir(self, secret_ref: str) -> Path:
        if not isinstance(secret_ref, str):
            raise TypeError('secret_ref must be a string')
        if not secret_ref.strip():
            raise ValueError('secret_ref must be non-empty')
        digest = hashlib.sha256(secret_ref.encode('utf-8')).hexdigest()
        return self._root / digest

    @staticmethod
    def _versions(ref_dir: Path) -> dict[int, set[str]]:
        if not ref_dir.is_dir():
            return {}
        result: dict[int, set[str]] = {}
        for entry in ref_dir.iterdir():
            if entry.is_file():
                m = _VERSION_FILE.match(entry.name)
                if m:
                    result.setdefault(int(m.group(1)), set()).add(m.group(2))
        return result

    def put(self, secret_ref: str, value: SecretValue) -> int:
        ref_dir = self._ref_dir(secret_ref)
        if not isinstance(value, SecretValue):
            raise TypeError('value must be a SecretValue')
        raw = value.reveal()
        if isinstance(raw, str):
            raw_bytes = raw.encode('utf-8')
        elif isinstance(raw, (bytes, bytearray)):
            raw_bytes = bytes(raw)
        else:
            raise TypeError('secret value must be str or bytes')
        if not raw_bytes:
            raise ValueError('secret value must not be empty')

        cipher = dpapi_encrypt(raw_bytes, self._entropy)
        ref_dir.mkdir(parents=True, exist_ok=True)
        version = max(self._versions(ref_dir).keys(), default=0) + 1
        final = ref_dir / f'v{version}.bin'
        tmp = ref_dir / f'v{version}.bin.tmp'
        try:
            with open(tmp, 'wb') as f:
                f.write(cipher)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, final)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
        return version

    def revoke(self, secret_ref: str, version: int) -> None:
        ref_dir = self._ref_dir(secret_ref)
        if isinstance(version, bool) or not isinstance(version, int):
            raise TypeError('version must be an int')
        if version < 1:
            raise ValueError('version must be >= 1')
        kinds = self._versions(ref_dir).get(version)
        if not kinds:
            raise ValueError('unknown secret version')
        if 'revoked' not in kinds:
            tmp_marker = ref_dir / f'v{version}.revoked.tmp'
            marker = ref_dir / f'v{version}.revoked'
            try:
                tmp_marker.write_bytes(b'')
                os.replace(tmp_marker, marker)
            except BaseException:
                tmp_marker.unlink(missing_ok=True)
                raise
        (ref_dir / f'v{version}.bin').unlink(missing_ok=True)

    def current_version(self, secret_ref: str) -> int | None:
        ref_dir = self._ref_dir(secret_ref)
        live = [n for n, k in self._versions(ref_dir).items() if 'bin' in k and 'revoked' not in k]
        return max(live) if live else None

    def export_vault(self, secret_refs: Iterable[str]) -> dict[str, bytes]:
        if isinstance(secret_refs, (str, bytes, bytearray)):
            raise TypeError('secret_refs must be an iterable of strings, not a single string')
        result: dict[str, bytes] = {}
        for ref in secret_refs:
            version = self.current_version(ref)
            if version is None:
                continue
            try:
                result[ref] = (self._ref_dir(ref) / f'v{version}.bin').read_bytes()
            except FileNotFoundError:
                continue
        return result
