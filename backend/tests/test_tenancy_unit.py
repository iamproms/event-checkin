"""M2-01 host and provider boundaries without network dependencies."""

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from starlette.requests import Request

from app.core.config import Settings
from app.db.models import TenantDomain
from app.db.session import TenantResolutionError, normalize_hostname
from app.tenancy.authority import AuthorityDenied, canonical_authority, trusted_client_address
from app.tenancy.domains import FixtureDomainProvider, observe, route_eligible


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("BÜCHER.Example.", "xn--bcher-kva.example"),
        ("Tenant.Example.TEST", "tenant.example.test"),
    ],
)
def test_idna_canonical_hostname(raw: str, expected: str) -> None:
    assert normalize_hostname(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "bad host.example",
        "*.example.test",
        "user@host.test",
        "xn--.example",
        "example.test:443",
        "host",
        "host.test/path",
    ],
)
def test_invalid_hostname_rejected(raw: str) -> None:
    with pytest.raises(TenantResolutionError):
        normalize_hostname(raw)


def request(
    host: str, path: str, peer: str = "203.0.113.10", extra: list[tuple[bytes, bytes]] | None = None
) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "scheme": "https",
        "path": path,
        "query_string": b"",
        "server": (host, 443),
        "client": (peer, 50000),
        "headers": [(b"host", host.encode())] + (extra or []),
    }
    return Request(scope)


def test_platform_host_and_forwarded_spoofing_fail_closed() -> None:
    settings = Settings(
        app_env="test",
        database_url="postgresql+psycopg://runtime:local@localhost/test",
        platform_host="platform.example.test",
        fallback_domain_suffix="example.test",
    )
    assert (
        canonical_authority(
            request("platform.example.test", "/api/v1/platform/auth/session"), settings
        )[0]
        == "platform.example.test"
    )
    with pytest.raises(AuthorityDenied):
        canonical_authority(
            request("tenant.example.test", "/api/v1/platform/auth/session"), settings
        )
    assert (
        canonical_authority(request("platform.example.test", "/api/v1/auth/session"), settings)[0]
        == "platform.example.test"
    )
    with pytest.raises(AuthorityDenied):
        canonical_authority(request(" tenant.example.test", "/api/v1/auth/session"), settings)
    with pytest.raises(AuthorityDenied):
        canonical_authority(
            request(
                "tenant.example.test",
                "/api/v1/auth/session",
                extra=[(b"x-forwarded-host", b"platform.example.test")],
            ),
            settings,
        )
    with pytest.raises(AuthorityDenied):
        canonical_authority(
            request(
                "tenant.example.test",
                "/api/v1/auth/session",
                extra=[(b"host", b"other.example.test")],
            ),
            settings,
        )


def test_local_https_platform_origin_is_explicit_and_host_bound() -> None:
    settings = Settings(
        app_env="local",
        database_url="postgresql+psycopg://runtime:local@localhost/test",
        platform_host="platform.local.example.test",
        fallback_domain_suffix="local.example.test",
        local_public_origin="https://platform.local.example.test:8443",
    )
    assert canonical_authority(
        request("platform.local.example.test:8443", "/api/v1/platform/auth/csrf"),
        settings,
    ) == ("platform.local.example.test", "https://platform.local.example.test:8443")
    with pytest.raises(AuthorityDenied):
        canonical_authority(
            request("other.local.example.test:8443", "/api/v1/platform/auth/csrf"),
            settings,
        )
    with pytest.raises(ValueError):
        Settings(
            app_env="staging",
            database_url="postgresql+psycopg://runtime:local@db.example.test/app?sslmode=require",
            platform_host="platform.local.example.test",
            fallback_domain_suffix="local.example.test",
            local_public_origin="https://platform.local.example.test:8443",
        )


def test_untrusted_remote_peer_rejected() -> None:
    settings = Settings(
        app_env="staging",
        database_url="postgresql+psycopg://runtime:local@db.example.test/app?sslmode=require",
        platform_host="platform.example.test",
        fallback_domain_suffix="example.test",
        ingress_proxy_ips="192.0.2.5",
    )
    with pytest.raises(AuthorityDenied):
        canonical_authority(request("tenant.example.test", "/api/v1/auth/session"), settings)
    assert (
        canonical_authority(
            request("tenant.example.test", "/api/v1/auth/session", peer="192.0.2.5"), settings
        )[0]
        == "tenant.example.test"
    )
    trusted = request(
        "tenant.example.test",
        "/api/v1/public/events/demo",
        peer="192.0.2.5",
        extra=[(b"x-forwarded-for", b"203.0.113.42")],
    )
    assert trusted_client_address(trusted, settings) == "203.0.113.42"
    with pytest.raises(AuthorityDenied):
        trusted_client_address(
            request(
                "tenant.example.test",
                "/api/v1/public/events/demo",
                peer="198.51.100.9",
                extra=[(b"x-forwarded-for", b"203.0.113.42")],
            ),
            settings,
        )
    for extra in (
        [],
        [(b"x-forwarded-for", b"203.0.113.42, 198.51.100.1")],
        [(b"x-forwarded-for", b"203.0.113.42"), (b"x-forwarded-for", b"198.51.100.1")],
    ):
        with pytest.raises(AuthorityDenied):
            trusted_client_address(
                request(
                    "tenant.example.test",
                    "/api/v1/public/events/demo",
                    peer="192.0.2.5",
                    extra=extra,
                ),
                settings,
            )


def test_testclient_peer_is_only_accepted_in_test_environment() -> None:
    test_settings = Settings(
        app_env="test",
        database_url="postgresql+psycopg://runtime:local@localhost/test",
    )
    synthetic = request("testserver", "/api/v1/auth/csrf", peer="testclient")
    assert trusted_client_address(synthetic, test_settings) == "127.0.0.1"
    local_settings = Settings(
        app_env="local",
        database_url="postgresql+psycopg://runtime:local@localhost/test",
    )
    with pytest.raises(AuthorityDenied):
        trusted_client_address(synthetic, local_settings)


def test_fixture_observation_is_tenant_bound_and_fail_closed(tmp_path: object) -> None:
    from pathlib import Path

    path = Path(str(tmp_path)) / "domains.json"
    tenant_id = uuid4()
    proof = "synthetic-public-proof"
    expiry = datetime.now(UTC) + timedelta(hours=4)
    path.write_text(
        json.dumps(
            {
                "_eventcheckin-verify.claim.example.test": {"txt": [proof]},
                "claim.example.test": {
                    "tenant_id": str(tenant_id),
                    "edge_ready": True,
                    "smoke_ok": True,
                    "certificate_valid_until": expiry.isoformat(),
                },
            }
        ),
        encoding="utf-8",
    )
    from app.auth.security import token_digest

    domain = TenantDomain(
        id=uuid4(),
        tenant_id=tenant_id,
        hostname="claim.example.test",
        kind="custom",
        verification_state="pending",
        tls_state="pending",
        routing_state="reserved",
        claim_digest=token_digest(proof),
        claim_expires_at=expiry,
    )
    result = observe(domain, FixtureDomainProvider(str(path)))
    assert result.ownership_ok and result.edge_ready and result.smoke_ok
    assert result.certificate_until == expiry
    domain.tenant_id = uuid4()
    assert not observe(domain, FixtureDomainProvider(str(path))).edge_ready
    domain.routing_state = "active"
    domain.verification_state = "verified"
    domain.tls_state = "active"
    domain.edge_ready = True
    domain.ownership_valid_until = datetime.now(UTC) - timedelta(seconds=1)
    domain.tls_valid_until = expiry
    domain.smoke_checked_at = datetime.now(UTC)
    assert not route_eligible(domain, datetime.now(UTC))
