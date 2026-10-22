import pytest

from app.db.session import TenantResolutionError, normalize_hostname


def test_hostname_is_normalized_for_verified_domain_lookup() -> None:
    assert normalize_hostname("  Tenant.Example.TEST. ") == "tenant.example.test"
    assert normalize_hostname("BÜCHER.example") == "xn--bcher-kva.example"


@pytest.mark.parametrize(
    "hostname", ["", "tenant.example:443", "https://tenant.example", "a..example"]
)
def test_invalid_hostname_fails_closed(hostname: str) -> None:
    with pytest.raises(TenantResolutionError):
        normalize_hostname(hostname)
