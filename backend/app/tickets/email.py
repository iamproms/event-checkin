"""Transactional ticket presentation and provider-neutral delivery boundary."""

import io
import re
import smtplib
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr
from html import escape
from importlib import import_module
from typing import Protocol, cast
from uuid import UUID
from zoneinfo import ZoneInfo

from app.auth.address import single_email_address

BRAND_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


class TicketDeliveryUnavailable(RuntimeError):
    pass


def _sender_label(value: str, fallback: str) -> str:
    for candidate in (value.strip(), fallback.strip(), "Event organizer"):
        if (
            1 <= len(candidate) <= 100
            and not any(ord(character) < 32 for character in candidate)
            and not any(character in "<>" for character in candidate)
        ):
            return candidate
    return "Event organizer"


@dataclass(frozen=True)
class TicketMessage:
    recipient: str
    sender_name: str
    subject: str
    text: str
    html: str
    qr_png: bytes
    logo_png: bytes | None
    intent_id: UUID


class TicketTransport(Protocol):
    """Production adapters must map intent_id to a provider idempotency key."""

    def send(self, message: TicketMessage) -> str: ...


class DisabledTicketTransport:
    def send(self, message: TicketMessage) -> str:
        raise TicketDeliveryUnavailable("Transactional ticket email is not configured")


class MemoryTicketTransport:
    """Deterministic local/test transport; it never delivers external mail."""

    def __init__(self) -> None:
        self.messages: dict[UUID, TicketMessage] = {}

    def send(self, message: TicketMessage) -> str:
        self.messages.setdefault(message.intent_id, message)
        return f"local-{message.intent_id}"


class LocalSmtpTicketTransport:
    """Local Mailpit-style SMTP only. No production activation or delivery guarantee."""

    def __init__(self, host: str, port: int, sender: str) -> None:
        self.host, self.port, self.sender = host, port, single_email_address(sender)

    def send(self, message: TicketMessage) -> str:
        outgoing = EmailMessage()
        outgoing["To"] = single_email_address(message.recipient)
        outgoing["From"] = formataddr((message.sender_name, self.sender))
        outgoing["Subject"] = message.subject
        outgoing["Message-ID"] = f"<ticket-{message.intent_id}@local.eventcheckin.invalid>"
        outgoing.set_content(message.text)
        outgoing.add_alternative(message.html, subtype="html")
        html_part = cast(EmailMessage, outgoing.get_body(preferencelist=("html",)))
        if message.logo_png is not None:
            html_part.add_related(
                message.logo_png, maintype="image", subtype="png", cid="<organizer-logo>"
            )
        html_part.add_related(message.qr_png, maintype="image", subtype="png", cid="<ticket-qr>")
        with smtplib.SMTP(self.host, self.port, timeout=10) as smtp:
            smtp.send_message(outgoing)
        return f"local-{message.intent_id}"


def render_qr(credential: str) -> bytes:
    qrcode = import_module("qrcode")
    image = qrcode.make(credential, error_correction=qrcode.constants.ERROR_CORRECT_M, border=4)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def ticket_message(
    *,
    intent_id: UUID,
    recipient: str,
    credential: str,
    event_name: str,
    starts_at: datetime,
    timezone: str,
    venue: str | None = None,
    organizer_name: str,
    sender_name: str,
    primary_color: str | None = None,
    logo_png: bytes | None = None,
) -> TicketMessage:
    local_start = starts_at.astimezone(ZoneInfo(timezone))
    date_label = local_start.strftime("%A %d %B %Y, %H:%M") + f" ({timezone})"
    title = escape(event_name)
    organizer = escape(organizer_name)
    clean_sender = _sender_label(sender_name, organizer_name)
    date_html = escape(date_label)
    venue_label = venue.strip() if venue else "Venue to be confirmed"
    brand_rule = (
        primary_color if primary_color and BRAND_COLOR.fullmatch(primary_color) else "#205b4a"
    )
    logo_html = (
        '<img src="cid:organizer-logo" alt="" width="120" '
        'style="display:block;max-width:120px;max-height:64px;object-fit:contain;'
        'margin:0 0 16px" />'
        if logo_png is not None
        else ""
    )
    text = (
        f"Your ticket for {event_name}\n"
        f"{date_label}\n"
        f"Venue: {venue_label}\n"
        f"Presented by {organizer_name}\n\n"
        "Present the QR code in this email at the gate. Keep it private; "
        "the first valid scan uses it. "
        "For delivery or ticket help, contact the organizer.\n"
    )
    html = (
        '<!doctype html><html><body style="font-family:Inter,Arial,sans-serif;'
        'background:#f7f7f4;color:#171816;margin:0;padding:24px">'
        '<main style="max-width:560px;margin:auto;background:white;padding:32px;border-radius:8px;'
        f'border-top:6px solid {brand_rule}">'
        f"{logo_html}"
        f'<p style="font-size:14px;margin:0 0 24px">{organizer}</p>'
        f'<h1 style="font-size:28px;line-height:1.2;margin:0 0 12px">{title}</h1>'
        f'<p style="margin:0 0 24px">{date_html}</p>'
        f'<p style="margin:0 0 24px">Venue: {escape(venue_label)}</p>'
        '<img src="cid:ticket-qr" alt="Entry QR code" width="240" height="240" '
        'style="display:block;max-width:100%;height:auto;margin:24px 0" />'
        "<p>Present this QR code at the gate. Keep it private; the first valid scan uses it.</p>"
        "<p>For delivery or ticket help, contact the organizer.</p>"
        "</main></body></html>"
    )
    return TicketMessage(
        recipient=single_email_address(recipient),
        sender_name=clean_sender,
        subject=f"Your ticket for {event_name}",
        text=text,
        html=html,
        qr_png=render_qr(credential),
        logo_png=logo_png,
        intent_id=intent_id,
    )
