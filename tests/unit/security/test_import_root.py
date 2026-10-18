"""Import-root guard: controlplane.security modules bind to the src/ import root (D1)."""
import unittest

from controlplane.security import broker, dpapi, interfaces, sanitizer


class ImportRootTests(unittest.TestCase):
    def test_sanitizer_uses_canonical_secret_credential(self) -> None:
        self.assertIs(sanitizer.SecretCredential, interfaces.SecretCredential)

    def test_broker_uses_canonical_dpapi_decrypt(self) -> None:
        self.assertIs(broker.dpapi_decrypt, dpapi.dpapi_decrypt)
