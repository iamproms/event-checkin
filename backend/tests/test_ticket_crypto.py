"""Opaque ticket credentials remain bound to server keys and database scope."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from cryptography.exceptions import InvalidTag

from app.tickets.crypto import TicketKeyring
from app.tickets.email import ticket_message


def test_ticket_entropy_digest_and_authenticated_resend_copy() -> None:
    keys = TicketKeyring({1: b"a" * 32, 2: b"b" * 32}, 2)
    tenant, event, registration, ticket = (uuid4() for _ in range(4))
    credential, version = keys.new_credential()
    other, _ = keys.new_credential()
    assert version == 2
    assert credential.startswith("v2.")
    assert credential != other
    assert all(str(identifier) not in credential for identifier in (tenant, event, registration))
    digest = keys.digest(credential)
    assert digest is not None and len(digest) == 32
    assert keys.digest(credential[:-1] + ("A" if credential[-1] != "A" else "B")) != digest
    encrypted = keys.encrypt(credential, tenant, event, registration, ticket)
    assert credential.encode("ascii") not in encrypted
    assert keys.decrypt(encrypted, version, tenant, event, registration, ticket) == credential
    with pytest.raises(InvalidTag):
        keys.decrypt(encrypted, version, tenant, event, registration, uuid4())
    with pytest.raises(InvalidTag):
        TicketKeyring({2: b"c" * 32}, 2).decrypt(
            encrypted, version, tenant, event, registration, ticket
        )


def test_rotation_retains_old_verification_until_old_key_is_removed() -> None:
    old = TicketKeyring({1: b"a" * 32}, 1)
    credential, _ = old.new_credential()
    rotated = TicketKeyring({1: b"a" * 32, 2: b"b" * 32}, 2)
    assert rotated.digest(credential) == old.digest(credential)
    assert TicketKeyring({2: b"b" * 32}, 2).digest(credential) is None
    assert rotated.new_credential()[0].startswith("v2.")


def test_ticket_email_escapes_brand_and_event_and_renders_qr() -> None:
    message = ticket_message(
        intent_id=uuid4(),
        recipient="ada@example.test",
        credential="v1." + "A" * 43,
        event_name="Demo <script>",
        starts_at=datetime(2026, 11, 3, 8, tzinfo=UTC),
        timezone="Africa/Lagos",
        organizer_name="Àjọ & Co",
        sender_name="Àjọ Tickets",
        primary_color="#46806A",
        logo_png=b"\x89PNGfixture",
    )
    assert "<script>" not in message.html
    assert "Demo &lt;script&gt;" in message.html
    assert "Àjọ &amp; Co" in message.html
    assert "border-top:6px solid #46806A" in message.html
    assert message.qr_png.startswith(b"\x89PNG")
    assert message.logo_png == b"\x89PNGfixture"
    assert message.sender_name == "Àjọ Tickets"
    assert 'src="cid:organizer-logo"' in message.html
    assert "v1." not in message.html and "v1." not in message.text


def test_ticket_email_rejects_header_control_characters() -> None:
    message = ticket_message(
        intent_id=uuid4(),
        recipient="ada@example.test",
        credential="v1." + "A" * 43,
        event_name="Demo",
        starts_at=datetime(2026, 11, 3, 8, tzinfo=UTC),
        timezone="Africa/Lagos",
        organizer_name="Unsafe\nBcc: attacker@example.test",
        sender_name="Unsafe\r\nBcc: attacker@example.test",
    )
    assert message.sender_name == "Event organizer"
