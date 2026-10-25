"""Private logo storage and strict raster decoding. SVG is intentionally unsupported."""

from collections.abc import Mapping
from importlib import import_module
from io import BytesIO
from typing import Protocol

from app.worker.storage import S3PrivateStorage

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_STORED_BYTES = 4 * 1024 * 1024
MIN_SIDE = 64
MAX_SIDE = 2048
MIME_FORMATS: Mapping[str, str] = {
    "image/png": "PNG",
    "image/jpeg": "JPEG",
    "image/webp": "WEBP",
}


class AssetInvalid(ValueError):
    pass


class BrandingStorage(Protocol):
    def put(self, key: str, data: bytes) -> None: ...

    def get(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...


class UnavailableBrandingStorage:
    def put(self, key: str, data: bytes) -> None:
        raise AssetInvalid("Private logo storage is unavailable.")

    def get(self, key: str) -> bytes:
        raise AssetInvalid("Private logo storage is unavailable.")

    def delete(self, key: str) -> None:
        raise AssetInvalid("Private logo storage is unavailable.")


class S3BrandingStorage:
    def __init__(self, private: S3PrivateStorage) -> None:
        self.private = private

    def put(self, key: str, data: bytes) -> None:
        self.private.client.put_object(  # type: ignore[attr-defined]
            Bucket=self.private.bucket, Key=key, Body=data, ContentType="image/png"
        )

    def get(self, key: str) -> bytes:
        response = self.private.client.get_object(  # type: ignore[attr-defined]
            Bucket=self.private.bucket, Key=key
        )
        result: bytes = response["Body"].read(MAX_STORED_BYTES + 1)
        if len(result) > MAX_STORED_BYTES:
            raise AssetInvalid("Logo is unavailable")
        return result

    def delete(self, key: str) -> None:
        self.private.delete(key)


def sanitize_logo(data: bytes, declared_mime: str) -> bytes:
    """Decode then re-encode one raster frame, stripping metadata and active content."""
    if declared_mime not in MIME_FORMATS:
        raise AssetInvalid("Use a PNG, JPEG or WebP image. SVG is not supported.")
    if not 1 <= len(data) <= MAX_UPLOAD_BYTES:
        raise AssetInvalid("Logo must be smaller than 2 MB.")
    try:
        image_module = import_module("PIL.Image")
        image_ops = import_module("PIL.ImageOps")
        unidentified = import_module("PIL").UnidentifiedImageError
    except ImportError as exc:
        raise AssetInvalid("Logo processing is unavailable.") from exc
    try:
        with image_module.open(BytesIO(data)) as image:
            if image.format != MIME_FORMATS[declared_mime]:
                raise AssetInvalid("File content does not match its image type.")
            if getattr(image, "n_frames", 1) != 1:
                raise AssetInvalid("Animated images are not supported.")
            width, height = image.size
            if not (MIN_SIDE <= width <= MAX_SIDE and MIN_SIDE <= height <= MAX_SIDE):
                raise AssetInvalid("Logo dimensions must be 64–2048 pixels on each side.")
            if width * height > 4_194_304:
                raise AssetInvalid("Logo has too many pixels.")
            normalized = image_ops.exif_transpose(image)
            normalized.load()
            output = BytesIO()
            normalized.convert("RGBA").save(output, format="PNG", optimize=True)
            result = output.getvalue()
    except (
        unidentified,
        OSError,
        ValueError,
        image_module.DecompressionBombError,
    ) as exc:
        if isinstance(exc, AssetInvalid):
            raise
        raise AssetInvalid("Logo image is malformed or unsupported.") from exc
    if len(result) > MAX_STORED_BYTES:
        raise AssetInvalid("Decoded logo is too large. Use a simpler image.")
    return result
