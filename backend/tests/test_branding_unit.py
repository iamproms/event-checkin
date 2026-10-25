from io import BytesIO

import pytest
from PIL import Image

from app.branding.assets import AssetInvalid, sanitize_logo
from app.branding.contrast import ColorInvalid, ratio, validate_brand_color
from app.branding.service import BrandingInvalid, clean_label


def image_bytes(format_name: str = "PNG") -> bytes:
    output = BytesIO()
    Image.new("RGB", (128, 128), "#46806a").save(output, format=format_name)
    return output.getvalue()


def test_logo_is_decoded_and_reencoded_to_private_png() -> None:
    source = image_bytes("JPEG")
    result = sanitize_logo(source, "image/jpeg")
    with Image.open(BytesIO(result)) as image:
        assert image.format == "PNG"
        assert image.size == (128, 128)
    assert result != source


@pytest.mark.parametrize(
    ("payload", "mime"),
    [
        (b"<svg><script>alert(1)</script></svg>", "image/svg+xml"),
        (b"not a logo", "image/png"),
        (image_bytes("PNG"), "image/jpeg"),
        (b"x" * (2 * 1024 * 1024 + 1), "image/png"),
    ],
)
def test_invalid_logo_rejected(payload: bytes, mime: str) -> None:
    with pytest.raises(AssetInvalid):
        sanitize_logo(payload, mime)


def test_small_image_rejected() -> None:
    output = BytesIO()
    Image.new("RGB", (32, 32), "red").save(output, format="PNG")
    with pytest.raises(AssetInvalid, match="dimensions"):
        sanitize_logo(output.getvalue(), "image/png")


def test_brand_colors_require_contrast_in_both_themes() -> None:
    assert validate_brand_color("#46806a", "Primary") == "#46806A"
    assert ratio("#46806A", "#ffffff") >= 3
    assert ratio("#46806A", "#21231f") >= 3
    for candidate in ("red", "#ffffff", "#111111", "#fff", "#12GGGG"):
        with pytest.raises(ColorInvalid):
            validate_brand_color(candidate, "Primary")


def test_plain_text_identity_validation() -> None:
    assert clean_label("  Àjọ Events  ", "Display name", 120) == "Àjọ Events"
    for value in ("", "<img src=x>", "Name\nother", "x" * 121):
        with pytest.raises(BrandingInvalid):
            clean_label(value, "Display name", 120)
