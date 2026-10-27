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
