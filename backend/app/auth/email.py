"""Provider-independent transactional email boundary."""

import smtplib
from email.message import EmailMessage
from hashlib import sha256
from typing import Protocol
from uuid import UUID

from app.auth.address import single_email_address


class DeliveryUnavailable(RuntimeError):
    pass


class EmailDelivery(Protocol):
    def send_link(self, recipient: str, subject: str, link: str) -> None: ...


class DisabledEmailDelivery:
    def send_link(self, recipient: str, subject: str, link: str) -> None:
        raise DeliveryUnavailable("Transactional email delivery is not configured")


class SmtpEmailDelivery:
    """Local SMTP adapter. Production activation requires an approved provider."""

    def __init__(self, host: str, port: int, sender: str) -> None:
        self.host, self.port, self.sender = host, port, sender

    def send_link(self, recipient: str, subject: str, link: str) -> None:
        recipient = single_email_address(recipient)
        message = EmailMessage()
        message["To"] = recipient
        message["From"] = self.sender
        message["Subject"] = subject
        if subject.startswith("Welcome to ") and "organizer account" in subject:
            organization = subject.removeprefix("Welcome to ").split(" — ", 1)[0]
            introduction = (
                f"Welcome to {organization}. You have been invited as an organizer. "
                "Use this single-use, time-limited link to set your password and complete "
                "authenticator setup. You can then sign in at the same application address."
            )
        elif subject == "Reset your password":
            introduction = (
                "Use this single-use, time-limited link to reset your Event Check-in "
                "password. If you did not request a reset, contact your administrator."
            )
        else:
            introduction = (
                "You have been invited to an authorized Event Check-in staff workspace. "
                "Use this single-use, time-limited link to set your password and complete "
                "any required authenticator setup."
            )
        message.set_content(
            f"{introduction} Never share this link.\n\n{link}\n\n"
            "For access help, contact the event organizer or your platform support contact.\n"
        )
        with smtplib.SMTP(self.host, self.port, timeout=10) as smtp:
            smtp.send_message(message)


class BrevoEmailDelivery:
    """Remote transactional link delivery through Brevo's HTTPS API."""

    def __init__(self, client: object, sender: str, sender_name: str) -> None:
        self.client = client
        self.sender = single_email_address(sender)
        self.sender_name = sender_name

    def send_link(self, recipient: str, subject: str, link: str) -> None:
        from app.delivery.brevo import BrevoTransactionalClient

        if not isinstance(self.client, BrevoTransactionalClient):
            raise DeliveryUnavailable("Transactional email delivery is unavailable")
        recipient = single_email_address(recipient)
        digest = bytearray(sha256(link.encode("utf-8")).digest()[:16])
        digest[6] = (digest[6] & 0x0F) | 0x40
        digest[8] = (digest[8] & 0x3F) | 0x80
        idempotency_key = str(UUID(bytes=bytes(digest)))
        text = (
            "Use this single-use, time-limited Event Check-in link to continue. "
            "If you did not request or expect it, contact your administrator. "
            f"Never share this link.\n\n{link}\n"
        )
        self.client.send(
            {
                "sender": {"email": self.sender, "name": self.sender_name},
                "to": [{"email": recipient}],
                "subject": subject,
                "textContent": text,
                "tags": ["event-checkin-auth"],
            },
            idempotency_key,
        )
