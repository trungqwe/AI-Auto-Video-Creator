"""Targeted behavioral tests for DPAPI Vault and Credential Broker Lifetime (INV-015 / CT-SEC-002).

Task: TASK-CAP-J-P1-A-RED
"""
import unittest
from src.controlplane.security.dpapi import (
    dpapi_encrypt,
    dpapi_decrypt,
    DPAPIDecryptionError,
)
from src.controlplane.security.broker import (
    CredentialBroker,
    SecretLifetimeExpiredError,
    UnauthorizedSecretAccessError,
)

class TestDPAPIBroker(unittest.TestCase):

    def test_dpapi_encrypt_decrypt_roundtrip_and_tamper_protection(self):
        """Oracle 1 (INV-015 / CT-SEC-002): DPAPI mã hóa/giải mã toàn vẹn và phát hiện tamper.
        
        - Ciphertext không được trùng raw bytes và không chứa raw string.
        - Decrypt ciphertext trả về đúng raw bytes.
        - Decrypt ciphertext bị chỉnh sửa (tampered) phải ném DPAPIDecryptionError.
        """
        raw_secret = b"SECRET_API_KEY_9999_DPAPI_TEST"
        ciphertext = dpapi_encrypt(raw_secret)
        
        # Pha RED: Scaffold trả về raw_secret nên fail ngay tại assertNotEqual
        self.assertNotEqual(ciphertext, raw_secret, "DPAPI ciphertext must not be identical to plaintext")
        self.assertNotIn(raw_secret, ciphertext, "Raw secret bytes must not appear in DPAPI ciphertext")
        
        decrypted = dpapi_decrypt(ciphertext)
        self.assertEqual(decrypted, raw_secret)
        
        # Tamper test
        tampered = bytearray(ciphertext)
        tampered[0] ^= 0xFF
        with self.assertRaises(DPAPIDecryptionError):
            dpapi_decrypt(bytes(tampered))

    def test_credential_broker_scoped_lifetime_and_automatic_expiration(self):
        """Oracle 2 (INV-015): Secret handle chỉ có giá trị trong context manager và hết hạn khi thoát scope.
        
        - Trong scope: `get_secret_value()` trả về chuỗi secret thật.
        - Ngoài scope: `is_expired()` là True và `get_secret_value()` ném SecretLifetimeExpiredError.
        """
        raw_token = b"REAL_AUTHENTICATED_TOKEN_12345"
        vault = {"gemini_api_key": dpapi_encrypt(raw_token)}
        broker = CredentialBroker(vault=vault)
        
        handle = None
        with broker.acquire_secret("gemini_api_key") as h:
            handle = h
            self.assertFalse(handle.is_expired())
            val = handle.get_secret_value()
            self.assertEqual(val, raw_token.decode("utf-8"))
            
        # Pha RED: Scaffold không đánh dấu expired và không ném SecretLifetimeExpiredError -> Fail
        self.assertTrue(handle.is_expired(), "ScopedSecretHandle must be expired after exiting context")
        with self.assertRaises(SecretLifetimeExpiredError):
            handle.get_secret_value()

    def test_credential_broker_rejects_unauthorized_or_unknown_alias(self):
        """Oracle 3 (INV-015 / CT-SEC-002): Từ chối fail-closed khi yêu cầu secret alias không tồn tại."""
        broker = CredentialBroker(vault={})
        
        # Pha RED: Scaffold yield handle mà không kiểm tra alias -> không ném UnauthorizedSecretAccessError
        with self.assertRaises(UnauthorizedSecretAccessError):
            with broker.acquire_secret("unregistered_malicious_alias"):
                pass

if __name__ == "__main__":
    unittest.main()
