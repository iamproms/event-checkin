"""Credential primitives. Raw secrets never enter database records or logs."""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from collections.abc import Iterable

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PASSWORD_HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
DUMMY_HASH = PASSWORD_HASHER.hash("unregistered-account-dummy-password")


def new_token() -> str:
    return secrets.token_urlsafe(48)


def token_digest(token: str) -> bytes:
    return hashlib.sha256(token.encode("ascii")).digest()


def hash_password(password: str) -> str:
    if not 12 <= len(password) <= 128:
        raise ValueError("Password must contain 12 to 128 characters")
    return PASSWORD_HASHER.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return (
            PASSWORD_HASHER.verify(password_hash or DUMMY_HASH, password)
            and password_hash is not None
        )
    except (VerifyMismatchError, InvalidHashError):
        return False


def new_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def encrypt_totp(secret: str, key: bytes, user_id: str) -> bytes:
    nonce = secrets.token_bytes(12)
    return nonce + AESGCM(key).encrypt(nonce, secret.encode("ascii"), user_id.encode("ascii"))


def decrypt_totp(ciphertext: bytes, key: bytes, user_id: str) -> str:
    return (
        AESGCM(key)
        .decrypt(ciphertext[:12], ciphertext[12:], user_id.encode("ascii"))
        .decode("ascii")
    )


def totp_code(secret: str, step: int) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 15
    number = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{number % 1_000_000:06d}"


def accepted_totp_step(
    secret: str, code: str, last_step: int | None, now: float | None = None
) -> int | None:
    if len(code) != 6 or not code.isascii() or not code.isdecimal():
        return None
    current = int((time.time() if now is None else now) // 30)
    for step in (current - 1, current, current + 1):
        if step > (last_step if last_step is not None else -1) and hmac.compare_digest(
            totp_code(secret, step), code
        ):
            return step
    return None


def recovery_codes() -> Iterable[str]:
    for _ in range(10):
        yield secrets.token_hex(10)
