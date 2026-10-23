"""Private S3-compatible object primitive; no public file API is exposed."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib import import_module
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Environment, Settings
from app.db.models import PrivateObject

MAX_TEST_BYTES = 5 * 1024 * 1024
TEST_MIME_TYPES = frozenset({"text/plain", "application/pdf"})


class StorageDenied(ValueError):
    pass


@dataclass(frozen=True)
class UploadGrant:
    object_id: UUID
    url: str
    fields: Mapping[str, str]
    expires_at: datetime


class PrivateStorage(Protocol):
    def upload_post(
        self, key: str, mime_type: str, max_bytes: int, lifetime_seconds: int
    ) -> tuple[str, Mapping[str, str]]: ...

    def download_url(self, key: str, lifetime_seconds: int) -> str: ...

    def metadata(self, key: str) -> tuple[str, int, str]: ...

    def promote(self, source_key: str, final_key: str, etag: str) -> None: ...

    def delete(self, key: str) -> None: ...


class S3PrivateStorage:
    def __init__(self, client: object, bucket: str) -> None:
        self.client = client
        self.bucket = bucket

    def upload_post(
        self, key: str, mime_type: str, max_bytes: int, lifetime_seconds: int
    ) -> tuple[str, Mapping[str, str]]:
        result = self.client.generate_presigned_post(  # type: ignore[attr-defined]
            self.bucket,
            key,
            Fields={"Content-Type": mime_type, "acl": "private"},
            Conditions=[
                {"Content-Type": mime_type},
                {"acl": "private"},
                ["content-length-range", 1, max_bytes],
            ],
            ExpiresIn=lifetime_seconds,
        )
        return str(result["url"]), dict(result["fields"])

    def download_url(self, key: str, lifetime_seconds: int) -> str:
        return str(
            self.client.generate_presigned_url(  # type: ignore[attr-defined]
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=lifetime_seconds,
            )
        )

    def metadata(self, key: str) -> tuple[str, int, str]:
        head = self.client.head_object(Bucket=self.bucket, Key=key)  # type: ignore[attr-defined]
        return str(head["ContentType"]), int(head["ContentLength"]), str(head["ETag"])

    def promote(self, source_key: str, final_key: str, etag: str) -> None:
        self.client.copy_object(  # type: ignore[attr-defined]
            Bucket=self.bucket,
            Key=final_key,
            CopySource={"Bucket": self.bucket, "Key": source_key},
            CopySourceIfMatch=etag,
        )

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)  # type: ignore[attr-defined]


def s3_storage(settings: Settings) -> S3PrivateStorage:
    if (
        not settings.storage_bucket
        or not settings.storage_access_key
        or not settings.storage_secret_key
    ):
        raise StorageDenied("Private storage is not configured")
    boto3 = import_module("boto3")
    signing_config = import_module("botocore.config").Config(
        signature_version="s3v4", s3={"addressing_style": "path"}
    )
    client = boto3.client(
        "s3",
        endpoint_url=settings.storage_endpoint_url,
        region_name=settings.storage_region,
        aws_access_key_id=settings.storage_access_key.get_secret_value(),
        aws_secret_access_key=settings.storage_secret_key.get_secret_value(),
        config=signing_config,
    )
    return S3PrivateStorage(client, settings.storage_bucket)


class InternalTestArtifactService:
    """Internal test-harness contract, disabled outside local/test.

    The caller must already hold an authorized tenant transaction. There is no
    FastAPI route to this service; a future purpose needs its own authorization.
    """

    def __init__(self, settings: Settings, storage: PrivateStorage) -> None:
        self.settings = settings
        self.storage = storage

    def _require_test(self) -> None:
        if self.settings.app_env not in {Environment.LOCAL, Environment.TEST}:
            raise StorageDenied("Test artifacts are disabled")

    def request_upload(
        self, session: Session, tenant_id: UUID, mime_type: str, max_bytes: int
    ) -> UploadGrant:
        self._require_test()
        if mime_type not in TEST_MIME_TYPES or not 1 <= max_bytes <= MAX_TEST_BYTES:
            raise StorageDenied("Unsupported test artifact")
        now = datetime.now(UTC)
        object_id = uuid4()
        key = f"tenants/{tenant_id}/internal-test/upload/{object_id}"
        expiry = now + timedelta(hours=23)
        obj = PrivateObject(
            id=object_id,
            tenant_id=tenant_id,
            purpose="internal_test_artifact",
            object_key=key,
            status="pending",
            mime_type=mime_type,
            max_size_bytes=max_bytes,
            expires_at=expiry,
        )
        session.add(obj)
        session.flush()
        lifetime = min(self.settings.upload_url_seconds, int((expiry - now).total_seconds()))
        url, fields = self.storage.upload_post(key, mime_type, max_bytes, lifetime)
        return UploadGrant(object_id, url, fields, expiry)

    def complete_upload(self, session: Session, object_id: UUID) -> bool:
        self._require_test()
        obj = session.scalar(
            select(PrivateObject).where(PrivateObject.id == object_id).with_for_update()
        )
        if obj is None or obj.purpose != "internal_test_artifact" or obj.status != "pending":
            raise StorageDenied("Object unavailable")
        if obj.expires_at <= datetime.now(UTC):
            raise StorageDenied("Object expired")
        mime_type, size, etag = self.storage.metadata(obj.object_key)
        if mime_type != obj.mime_type or not 1 <= size <= obj.max_size_bytes:
            self.storage.delete(obj.object_key)
            obj.status = "deleted"
            obj.deleted_at = datetime.now(UTC)
            return False
        final_key = f"tenants/{obj.tenant_id}/internal-test/complete/{obj.id}"
        self.storage.promote(obj.object_key, final_key, etag)
        obj.object_key = final_key
        obj.actual_size_bytes = size
        obj.status = "available"
        obj.completed_at = datetime.now(UTC)
        return True

    def download(self, session: Session, object_id: UUID) -> str:
        self._require_test()
        obj = session.scalar(select(PrivateObject).where(PrivateObject.id == object_id))
        if obj is None or obj.purpose != "internal_test_artifact" or obj.status != "available":
            raise StorageDenied("Object unavailable")
        remaining = int((obj.expires_at - datetime.now(UTC)).total_seconds())
        if remaining <= 0:
            raise StorageDenied("Object expired")
        return self.storage.download_url(
            obj.object_key, min(self.settings.download_url_seconds, remaining)
        )

    def cleanup_expired(self, session: Session, limit: int = 100) -> int:
        self._require_test()
        objects = list(
            session.scalars(
                select(PrivateObject)
                .where(
                    PrivateObject.purpose == "internal_test_artifact",
                    PrivateObject.status != "deleted",
                    PrivateObject.expires_at <= datetime.now(UTC),
                )
                .order_by(PrivateObject.expires_at)
                .with_for_update(skip_locked=True)
                .limit(limit)
            )
        )
        for obj in objects:
            self.storage.delete(obj.object_key)
            staging_key = f"tenants/{obj.tenant_id}/internal-test/upload/{obj.id}"
            if staging_key != obj.object_key:
                self.storage.delete(staging_key)
            final_key = f"tenants/{obj.tenant_id}/internal-test/complete/{obj.id}"
            if final_key != obj.object_key:
                self.storage.delete(final_key)
            obj.status = "deleted"
            obj.deleted_at = datetime.now(UTC)
        return len(objects)
