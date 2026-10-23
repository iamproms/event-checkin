"""Validate a single staff mailbox before storing or delivering secret links."""

from email.utils import getaddresses


def single_email_address(value: str) -> str:
    address = value.strip()
    local, separator, domain = address.rpartition("@")
    parsed = getaddresses([address])
    if (
        len(address) > 254
        or not local
        or not separator
        or not domain
        or "." not in domain
        or any(not label for label in domain.split("."))
        or any(char.isspace() or ord(char) < 32 for char in address)
        or parsed != [("", address)]
    ):
        raise ValueError("Enter a single valid email address")
    return address
