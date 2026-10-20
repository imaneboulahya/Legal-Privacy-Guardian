import base64
import unittest
from unittest.mock import patch

from encryption import (
    DecryptionError,
    EncryptionConfigurationError,
    decrypt_sensitive_text,
    encrypt_sensitive_text,
    load_encryption_key,
)


class EncryptionTests(unittest.TestCase):
    def setUp(self):
        self.key = base64.urlsafe_b64encode(b"0123456789abcdef0123456789abcdef").decode("ascii")
        self.assertEqual(len(base64.urlsafe_b64decode(self.key)), 32)
        self.environment = patch.dict("os.environ", {"DATA_ENCRYPTION_KEY": self.key})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_aes_gcm_sensitive_text_can_be_restored_with_the_configured_key(self):
        original = "Contact: private@example.com"
        findings, encrypted = encrypt_sensitive_text(original)
        self.assertGreaterEqual(findings["adresses e-mail"], 1)
        self.assertNotIn("private@example.com", encrypted)
        self.assertIn("[[LPG1:", encrypted)
        self.assertNotEqual(encrypted, encrypt_sensitive_text(original)[1])
        self.assertEqual(decrypt_sensitive_text(encrypted), original)

    def test_invalid_key_and_tampered_token_are_rejected(self):
        with self.assertRaises(EncryptionConfigurationError):
            load_encryption_key("not-a-key")

        _, encrypted = encrypt_sensitive_text("Email: private@example.com")
        damaged = encrypted.replace("[[LPG1:", "[[LPG1:AAAA", 1)
        with self.assertRaises(DecryptionError):
            decrypt_sensitive_text(damaged)


if __name__ == "__main__":
    unittest.main()
