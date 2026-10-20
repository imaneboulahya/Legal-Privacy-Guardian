import base64
import binascii
import os
import re

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from privacy import transform_sensitive_data


KEY_ENVIRONMENT_VARIABLE = "DATA_ENCRYPTION_KEY"
TOKEN_PATTERN = re.compile(r"\[\[LPG1:([A-Za-z0-9_-]+)\]\]")
ASSOCIATED_DATA = b"LegalPrivacyGuardian:v1"


class EncryptionConfigurationError(ValueError):
    pass


class DecryptionError(ValueError):
    pass


def load_encryption_key(value: str | None = None) -> bytes:
    encoded_key = value if value is not None else os.environ.get(KEY_ENVIRONMENT_VARIABLE)
    if not encoded_key:
        raise EncryptionConfigurationError(
            f"Configurez {KEY_ENVIRONMENT_VARIABLE} avec une clé base64 de 32 octets."
        )
    try:
        key = base64.b64decode(encoded_key.encode("ascii"), altchars=b"-_", validate=True)
    except (UnicodeEncodeError, binascii.Error, ValueError) as error:
        raise EncryptionConfigurationError("La clé de chiffrement n’est pas un base64 valide.") from error
    if len(key) != 32:
        raise EncryptionConfigurationError("La clé de chiffrement doit représenter exactement 32 octets.")
    return key


def encryption_is_configured() -> bool:
    try:
        load_encryption_key()
    except EncryptionConfigurationError:
        return False
    return True


def encrypt_sensitive_text(text: str) -> tuple[dict[str, int], str]:
    cipher = AESGCM(load_encryption_key())

    def encrypt_value(_category: str, value: str) -> str:
        nonce = os.urandom(12)
        ciphertext = cipher.encrypt(nonce, value.encode("utf-8"), ASSOCIATED_DATA)
        token = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii").rstrip("=")
        return f"[[LPG1:{token}]]"

    return transform_sensitive_data(text, encrypt_value)


def decrypt_sensitive_text(text: str) -> str:
    cipher = AESGCM(load_encryption_key())
    token_count = 0

    def decrypt_token(match: re.Match[str]) -> str:
        nonlocal token_count
        token_count += 1
        encoded = match.group(1)
        try:
            packed = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
            if len(packed) < 29:
                raise ValueError("token is too short")
            return cipher.decrypt(packed[:12], packed[12:], ASSOCIATED_DATA).decode("utf-8")
        except (binascii.Error, InvalidTag, UnicodeDecodeError, ValueError) as error:
            raise DecryptionError(
                "Le jeton est invalide ou ne correspond pas à la clé configurée."
            ) from error

    decrypted = TOKEN_PATTERN.sub(decrypt_token, text)
    if token_count == 0:
        raise DecryptionError("Aucun jeton Legal Privacy Guardian n’a été trouvé dans le fichier.")
    return decrypted
