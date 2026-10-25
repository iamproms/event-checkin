"""WCAG contrast checks for the actual branded surfaces in both approved themes."""

import re

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
LIGHT_SURFACE = "#ffffff"
DARK_SURFACE = "#21231f"


class ColorInvalid(ValueError):
    pass


def luminance(value: str) -> float:
    if HEX.fullmatch(value) is None:
        raise ColorInvalid("Use a six-digit color such as #46806A.")
    channels = [int(value[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [
        channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def ratio(first: str, second: str) -> float:
    high, low = sorted((luminance(first), luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def action_text(color: str) -> str:
    return "#ffffff" if ratio(color, "#ffffff") >= 4.5 else "#111817"


def validate_brand_color(value: str | None, label: str) -> str | None:
    if value is None:
        return None
    if HEX.fullmatch(value) is None:
        raise ColorInvalid(f"{label}: use a six-digit color such as #46806A.")
    canonical = value.upper()
    if ratio(canonical, LIGHT_SURFACE) < 3 or ratio(canonical, DARK_SURFACE) < 3:
        raise ColorInvalid(
            f"{label}: choose a color visible against both light and dark surfaces (3:1)."
        )
    if ratio(canonical, action_text(canonical)) < 4.5:
        raise ColorInvalid(f"{label}: button text needs at least 4.5:1 contrast.")
    return canonical
