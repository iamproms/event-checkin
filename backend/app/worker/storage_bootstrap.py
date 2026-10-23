"""Create the local/test private bucket and its one-day orphan cleanup rule."""

import os
import time
from importlib import import_module
from typing import Any


def ensure_test_bucket(client: Any, bucket: str, attempts: int = 30) -> None:
    """Retry startup races; fail closed if bucket or lifecycle cannot be configured."""
    for attempt in range(attempts):
        try:
            try:
                client.head_bucket(Bucket=bucket)
            except Exception:
                client.create_bucket(Bucket=bucket)
            client.put_bucket_lifecycle_configuration(
                Bucket=bucket,
                LifecycleConfiguration={
                    "Rules": [
                        {
                            "ID": "internal-test-orphan-expiry",
                            "Status": "Enabled",
                            "Filter": {"Prefix": "tenants/"},
                            "Expiration": {"Days": 1},
                        }
                    ]
                },
            )
            return
        except Exception:
            if attempt + 1 < attempts:
                time.sleep(1)
    raise RuntimeError("Private test bucket or lifecycle could not be configured")


def main() -> None:
    if os.environ.get("APP_ENV") not in {"local", "test"}:
        raise RuntimeError("Private test bucket setup is disabled")
    required = (
        "STORAGE_ENDPOINT_URL",
        "STORAGE_BUCKET",
        "STORAGE_ACCESS_KEY",
        "STORAGE_SECRET_KEY",
    )
    if any(not os.environ.get(name) for name in required):
        raise RuntimeError("Private test storage configuration is incomplete")
    boto3 = import_module("boto3")
    signing_config = import_module("botocore.config").Config(
        signature_version="s3v4", s3={"addressing_style": "path"}
    )
    client = boto3.client(
        "s3",
        endpoint_url=os.environ["STORAGE_ENDPOINT_URL"],
        region_name="us-east-1",
        aws_access_key_id=os.environ["STORAGE_ACCESS_KEY"],
        aws_secret_access_key=os.environ["STORAGE_SECRET_KEY"],
        config=signing_config,
    )
    ensure_test_bucket(client, os.environ["STORAGE_BUCKET"])


if __name__ == "__main__":
    main()
