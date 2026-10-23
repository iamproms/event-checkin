"""Pure contract checks that do not substitute for PostgreSQL integration tests."""

from datetime import timedelta
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.worker.jobs import retry_delay
from app.worker.storage import InternalTestArtifactService, S3PrivateStorage, StorageDenied
from app.worker.storage_bootstrap import ensure_test_bucket


class SigningClient:
    def __init__(self) -> None:
        self.post: dict[str, object] = {}
        self.get: dict[str, object] = {}
        self.copy: dict[str, object] = {}

    def generate_presigned_post(self, bucket: str, key: str, **kwargs: object) -> dict[str, object]:
        self.post = {"bucket": bucket, "key": key, **kwargs}
        return {"url": "https://private.example.test/upload", "fields": {"key": key}}

    def generate_presigned_url(self, method: str, **kwargs: object) -> str:
        self.get = {"method": method, **kwargs}
        return "https://private.example.test/download"

    def copy_object(self, **kwargs: object) -> None:
        self.copy = kwargs


@pytest.mark.parametrize("attempt", [1, 2, 3, 5, 20])
def test_retry_delay_is_bounded(attempt: int) -> None:
    delay = retry_delay(attempt)
    cap = min(3600, 2 ** min(attempt, 12))
    assert timedelta(seconds=cap) <= delay <= timedelta(seconds=cap + max(1, cap // 4))


def test_signed_post_has_type_and_size_conditions() -> None:
    client = SigningClient()
    storage = S3PrivateStorage(client, "private")
    _, fields = storage.upload_post("tenants/test/upload", "text/plain", 100, 600)
    assert fields == {"key": "tenants/test/upload"}
    assert client.post["ExpiresIn"] == 600
    assert client.post["Conditions"] == [
        {"Content-Type": "text/plain"},
        {"acl": "private"},
        ["content-length-range", 1, 100],
    ]
    storage.download_url("tenants/test/complete", 300)
    assert client.get["ExpiresIn"] == 300
    assert client.get["Params"] == {
        "Bucket": "private",
        "Key": "tenants/test/complete",
    }
    storage.promote("tenants/test/upload", "tenants/test/complete", '"etag"')
    assert client.copy["CopySourceIfMatch"] == '"etag"'


def test_test_purpose_rejects_production_and_unsupported_inputs() -> None:
    client = SigningClient()
    storage = S3PrivateStorage(client, "private")
    production = InternalTestArtifactService(
        Settings(
            app_env="production",
            database_url="postgresql+psycopg://u:p@db.example.test/x?sslmode=verify-full",
        ),
        storage,
    )
    with pytest.raises(StorageDenied):
        production.request_upload(None, uuid4(), "text/plain", 10)  # type: ignore[arg-type]
    local = InternalTestArtifactService(
        Settings(app_env="test", database_url="postgresql+psycopg://u:p@localhost/x"), storage
    )
    for mime, size in (("image/png", 10), ("text/plain", 0), ("text/plain", 5242881)):
        with pytest.raises(StorageDenied):
            local.request_upload(None, uuid4(), mime, size)  # type: ignore[arg-type]


def test_local_bucket_bootstrap_requires_lifecycle() -> None:
    class Client:
        def __init__(self) -> None:
            self.created = False
            self.lifecycle: dict[str, object] | None = None

        def head_bucket(self, **kwargs: object) -> None:
            if not self.created:
                raise LookupError("missing bucket")

        def create_bucket(self, **kwargs: object) -> None:
            self.created = True

        def put_bucket_lifecycle_configuration(self, **kwargs: object) -> None:
            self.lifecycle = kwargs

    client = Client()
    ensure_test_bucket(client, "private", attempts=1)
    assert client.created
    assert client.lifecycle is not None
    assert client.lifecycle["Bucket"] == "private"

    class NoLifecycle(Client):
        def put_bucket_lifecycle_configuration(self, **kwargs: object) -> None:
            raise RuntimeError("unsupported")

    with pytest.raises(RuntimeError, match="lifecycle"):
        ensure_test_bucket(NoLifecycle(), "private", attempts=1)
