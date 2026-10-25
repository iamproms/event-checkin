"""Distributed, fail-closed public registration throttling."""

import hashlib
import hmac
import time
from typing import Protocol
from uuid import UUID

from redis import Redis
from redis.exceptions import RedisError


class RegistrationRateLimiter(Protocol):
    def allow(self, tenant_id: UUID, event_id: UUID, peer: str) -> bool: ...


class DenyRegistrationLimiter:
    def allow(self, tenant_id: UUID, event_id: UUID, peer: str) -> bool:
        return False


class RedisRegistrationLimiter:
    """Limits both one ingress peer and total event traffic in each UTC minute.

    Peer identifiers are HMACed before writing Redis keys. Loss of Redis denies
    new public submissions rather than silently disabling abuse protection.
    """

    _SCRIPT = """
    local peer = redis.call('INCR', KEYS[1])
    if peer == 1 then redis.call('EXPIRE', KEYS[1], 120) end
    local event = redis.call('INCR', KEYS[2])
    if event == 1 then redis.call('EXPIRE', KEYS[2], 120) end
    return {peer, event}
    """

    def __init__(
        self, url: str, hmac_key: bytes, peer_per_minute: int = 8, event_per_minute: int = 300
    ):
        if len(hmac_key) < 32 or peer_per_minute < 1 or event_per_minute < 1:
            raise ValueError("Registration limiter is not configured")
        self.redis: Redis = Redis.from_url(url, socket_timeout=2, socket_connect_timeout=2)
        self.key = hmac_key
        self.peer_limit = peer_per_minute
        self.event_limit = event_per_minute

    def allow(self, tenant_id: UUID, event_id: UUID, peer: str) -> bool:
        minute = int(time.time() // 60)
        identity = hmac.new(self.key, peer.encode("utf-8"), hashlib.sha256).hexdigest()
        prefix = f"registration:{tenant_id}:{event_id}:{minute}"
        try:
            counts = self.redis.eval(self._SCRIPT, 2, f"{prefix}:{identity}", f"{prefix}:all")
            return (
                isinstance(counts, list)
                and len(counts) == 2
                and (int(counts[0]) <= self.peer_limit and int(counts[1]) <= self.event_limit)
            )
        except (RedisError, ValueError, TypeError):
            return False
