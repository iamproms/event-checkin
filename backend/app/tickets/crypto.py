"""Versioned, server-only ticket keys. The QR contains no participant or route data."""

import base64
import hashlib
import hmac
import json
import re
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import Settings

TOKEN = re.compile(r"^v([1-9][0-9]{0,3})\.([A-Za-z0-9_-]{43})$")


class TicketKeyUnavailable(ValueError):
    pass


def _derive(master: bytes, purpose: bytes, version: int) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"eventcheckin.ticket." + purpose + b"." + str(version).encode("ascii"),
    ).derive(master)


def _aad(tenant: UUID, event: UUID, registration: UUID, ticket: UUID) -> bytes:
    return b"|".join(str(part).encode("ascii") for part in (tenant, event, registration, ticket))


@dataclass(frozen=True)
class TicketKeyring:
    """A deployment secret, never persisted in PostgreSQL or sent to clients."""

    keys: Mapping[int, bytes]
    active_version: int

    def __post_init__(self) -> None:
        if self.active_version not in self.keys or not all(
            isinstance(version, int) and 1 <= version <= 9999 and len(key) == 32
            for version, key in self.keys.items()
        ):
            raise TicketKeyUnavailable("Ticket keyring is unavailable")

    @classmethod
    def from_settings(cls, settings: Settings) -> "TicketKeyring":
        secret = settings.ticket_keyring_json
        if secret is None:
            raise TicketKeyUnavailable("Ticket keyring is unavailable")
        try:
            raw = json.loads(secret.get_secret_value())
            if not isinstance(raw, dict) or not raw:
                raise ValueError("keyring shape")
            keys = {
                int(version): base64.b64decode(encoded, validate=True)
                for version, encoded in raw.items()
                if isinstance(version, str) and isinstance(encoded, str)
            }
            if len(keys) != len(raw):
                raise ValueError("keyring entry")
            return cls(keys, settings.ticket_active_key_version)
        except (ValueError, TypeError, KeyError) as exc:
            raise TicketKeyUnavailable("Ticket keyring is invalid") from exc

    def new_credential(self) -> tuple[str, int]:
        random_part = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("=")
        return f"v{self.active_version}.{random_part}", self.active_version

    def version_of(self, credential: str) -> int | None:
        match = TOKEN.fullmatch(credential)
        if match is None:
            return None
        try:
            raw = base64.urlsafe_b64decode(match.group(2) + "=")
        except ValueError:
            return None
        version = int(match.group(1))
        return version if len(raw) == 32 and version in self.keys else None

    def digest(self, credential: str) -> bytes | None:
        version = self.version_of(credential)
        if version is None:
            return None
        key = _derive(self.keys[version], b"digest", version)
        return hmac.new(key, credential.encode("ascii"), hashlib.sha256).digest()

    def encrypt(
        self, credential: str, tenant: UUID, event: UUID, registration: UUID, ticket: UUID
    ) -> bytes:
        version = self.version_of(credential)
        if version is None:
            raise TicketKeyUnavailable("Ticket credential is invalid")
        nonce = secrets.token_bytes(12)
        key = _derive(self.keys[version], b"resend", version)
        ciphertext = AESGCM(key).encrypt(
            nonce, credential.encode("ascii"), _aad(tenant, event, registration, ticket)
        )
        return nonce + ciphertext

    def decrypt(
        self,
        ciphertext: bytes,
        version: int,
        tenant: UUID,
        event: UUID,
        registration: UUID,
        ticket: UUID,
    ) -> str:
        if version not in self.keys or len(ciphertext) < 29:
            raise TicketKeyUnavailable("Ticket key is unavailable")
        key = _derive(self.keys[version], b"resend", version)
        raw = AESGCM(key).decrypt(
            ciphertext[:12], ciphertext[12:], _aad(tenant, event, registration, ticket)
        )
        credential = raw.decode("ascii")
        if self.version_of(credential) != version:
            raise TicketKeyUnavailable("Ticket credential is invalid")
        return credential
