"""Provider-independent transactional email boundary."""

import smtplib
from email.message import EmailMessage
from typing import Protocol

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
        message.set_content(f"Open this single-use link:\n\n{link}\n")
        with smtplib.SMTP(self.host, self.port, timeout=10) as smtp:
            smtp.send_message(message)
