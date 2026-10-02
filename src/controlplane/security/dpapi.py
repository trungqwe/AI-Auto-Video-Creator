"""Windows Data Protection API (DPAPI) integration for credential security.

Scaffold RED: Zero-logic placeholder; functions do not encrypt/decrypt real ciphertext.
"""

class DPAPIError(Exception):
    """Base exception for DPAPI operations."""
    pass

class DPAPIDecryptionError(DPAPIError):
    """Raised when ciphertext cannot be decrypted or is tampered with."""
    pass

def dpapi_encrypt(data: bytes, entropy: bytes | None = None) -> bytes:
    """Encrypts raw bytes using DPAPI.
    
    Scaffold RED: Returns raw bytes directly without encryption (will fail assertion).
    """
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("data must be bytes")
    return bytes(data)

def dpapi_decrypt(cipher: bytes, entropy: bytes | None = None) -> bytes:
    """Decrypts ciphertext using DPAPI.
    
    Scaffold RED: Returns cipher directly without decryption (will fail tamper test).
    """
    if not isinstance(cipher, (bytes, bytearray)):
        raise TypeError("cipher must be bytes")
    return bytes(cipher)
