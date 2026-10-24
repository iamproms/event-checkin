"""Canonical request authority at the application ingress boundary."""

from ipaddress import ip_address

from fastapi import Request

from app.core.config import Environment, Settings
from app.db.session import TenantResolutionError, normalize_hostname


class AuthorityDenied(ValueError):
    pass


def canonical_authority(request: Request, settings: Settings) -> tuple[str, str]:
    """Return normalized hostname and public origin, never a forwarded host.

    Uvicorn must run with proxy-header processing disabled. In remote
    environments only configured ingress peers can reach application routes;
    the edge must strip forwarded authority headers and validate SNI/Host.
    """
    raw_headers = request.scope.get("headers", [])
    hosts = [value for key, value in raw_headers if key.lower() == b"host"]
    if len(hosts) != 1:
        raise AuthorityDenied("Invalid request authority")
    if any(key.lower() in {b"forwarded", b"x-forwarded-host"} for key, _ in raw_headers):
        raise AuthorityDenied("Forwarded authority is not accepted")
    if settings.app_env in {Environment.STAGING, Environment.PRODUCTION}:
        peer = request.scope.get("client")
        allowed = {
            ip_address(item.strip())
            for item in settings.ingress_proxy_ips.split(",")
            if item.strip()
        }
        try:
            if peer is None or ip_address(peer[0]) not in allowed:
                raise AuthorityDenied("Ingress peer is not trusted")
        except ValueError as exc:
            raise AuthorityDenied("Ingress peer is not trusted") from exc
    try:
        authority = hosts[0].decode("ascii", "strict")
    except UnicodeDecodeError as exc:
        raise AuthorityDenied("Invalid request authority") from exc
    if (
        not authority
        or authority != authority.strip()
        or any(character.isspace() for character in authority)
        or "," in authority
        or "@" in authority
        or "[" in authority
    ):
        raise AuthorityDenied("Invalid request authority")
    hostname, separator, port = authority.partition(":")
    if separator:
        if (
            settings.app_env not in {Environment.LOCAL, Environment.TEST}
            or not port.isascii()
            or not port.isdecimal()
            or not 1 <= int(port) <= 65535
        ):
            raise AuthorityDenied("Invalid request authority")
    try:
        host = (
            "testserver"
            if hostname == "testserver" and settings.app_env == Environment.TEST
            else normalize_hostname(hostname)
        )
    except TenantResolutionError as exc:
        raise AuthorityDenied("Invalid request authority") from exc
    if request.url.path.startswith("/api/v1/platform"):
        if settings.platform_host is None or host != settings.platform_host:
            raise AuthorityDenied("Platform host required")
    elif settings.platform_host is not None and host == settings.platform_host:
        raise AuthorityDenied("Tenant routes are unavailable on the platform host")
    origin = (
        (
            request.url.scheme
            if settings.app_env in {Environment.LOCAL, Environment.TEST}
            else "https"
        )
        + "://"
        + authority.lower()
    )
    return host, origin
