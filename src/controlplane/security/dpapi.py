"""Windows Data Protection API (DPAPI) integration for credential security.

Provides hardware/OS-bound symmetric encryption for sensitive API keys and tokens.
Complies with INV-015 and CT-SEC-002.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Optional


class DPAPIError(Exception):
    """Base exception for DPAPI operations."""
    pass


class DPAPIDecryptionError(DPAPIError):
    """Raised when ciphertext cannot be decrypted or is tampered with."""
    pass


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def dpapi_encrypt(data: bytes, entropy: Optional[bytes] = None) -> bytes:
    """Encrypts raw bytes using Windows DPAPI CryptProtectData.

    Args:
        data: The plaintext bytes to encrypt.
        entropy: Optional additional entropy bytes to bind to encryption.

    Returns:
        Encrypted ciphertext bytes.

    Raises:
        TypeError: If data is not bytes or bytearray.
        DPAPIError: If CryptProtectData fails.
    """
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("data must be bytes")
    data_bytes = bytes(data)

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    data_in = DATA_BLOB(
        len(data_bytes),
        ctypes.cast(ctypes.c_char_p(data_bytes), ctypes.POINTER(ctypes.c_char)),
    )
    data_out = DATA_BLOB()

    entropy_blob = None
    p_entropy = None
    if entropy is not None:
        entropy_bytes = bytes(entropy)
        entropy_blob = DATA_BLOB(
            len(entropy_bytes),
            ctypes.cast(ctypes.c_char_p(entropy_bytes), ctypes.POINTER(ctypes.c_char)),
        )
        p_entropy = ctypes.byref(entropy_blob)

    # CRYPTPROTECT_UI_FORBIDDEN = 0x1
    res = crypt32.CryptProtectData(
        ctypes.byref(data_in),
        None,
        p_entropy,
        None,
        None,
        0x1,
        ctypes.byref(data_out),
    )
    if not res:
        raise DPAPIError("CryptProtectData failed")

    out_bytes = ctypes.string_at(data_out.pbData, data_out.cbData)
    kernel32.LocalFree(data_out.pbData)
    return out_bytes


def dpapi_decrypt(cipher: bytes, entropy: Optional[bytes] = None) -> bytes:
    """Decrypts ciphertext using Windows DPAPI CryptUnprotectData.

    Args:
        cipher: The ciphertext bytes to decrypt.
        entropy: Optional additional entropy bytes used during encryption.

    Returns:
        Decrypted plaintext bytes.

    Raises:
        TypeError: If cipher is not bytes or bytearray.
        DPAPIDecryptionError: If ciphertext is tampered with or decryption fails.
    """
    if not isinstance(cipher, (bytes, bytearray)):
        raise TypeError("cipher must be bytes")
    cipher_bytes = bytes(cipher)

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    data_in = DATA_BLOB(
        len(cipher_bytes),
        ctypes.cast(ctypes.c_char_p(cipher_bytes), ctypes.POINTER(ctypes.c_char)),
    )
    data_out = DATA_BLOB()

    entropy_blob = None
    p_entropy = None
    if entropy is not None:
        entropy_bytes = bytes(entropy)
        entropy_blob = DATA_BLOB(
            len(entropy_bytes),
            ctypes.cast(ctypes.c_char_p(entropy_bytes), ctypes.POINTER(ctypes.c_char)),
        )
        p_entropy = ctypes.byref(entropy_blob)

    res = crypt32.CryptUnprotectData(
        ctypes.byref(data_in),
        None,
        p_entropy,
        None,
        None,
        0x1,
        ctypes.byref(data_out),
    )
    if not res:
        raise DPAPIDecryptionError("CryptUnprotectData failed: ciphertext tampered or invalid")

    out_bytes = ctypes.string_at(data_out.pbData, data_out.cbData)
    kernel32.LocalFree(data_out.pbData)
    return out_bytes
