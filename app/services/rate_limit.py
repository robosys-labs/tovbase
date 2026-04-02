"""Redis-backed sliding window rate limiter with in-memory fallback.

Uses Redis sorted sets for distributed rate limiting across workers.
Falls back to in-memory defaultdict when Redis is unavailable.

Key pattern: ratelimit:{client_ip}:{endpoint_prefix}
"""

from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict

import redis

from app.config import settings

logger = logging.getLogger("tovbase.ratelimit")


class RedisRateLimiter:
    """Sliding window rate limiter backed by Redis sorted sets.

    On each request:
      1. ZREMRANGEBYSCORE removes expired entries outside the window
      2. ZCARD counts remaining entries
      3. If under limit, ZADD adds current timestamp
    All three steps run in a pipeline for atomicity.

    If Redis is unavailable, falls back to an in-memory sliding window
    (equivalent to the original implementation).
    """

    LIMITS: dict[str, tuple[int, int]] = {
        "/v1/score/":  (120, 60),
        "/v1/report/": (10, 60),
        "/v1/ingest/": (30, 60),
        "/v1/enrich/": (10, 60),
        "/v1/profile/claim": (30, 60),
        "/v1/profile/verify": (30, 60),
    }
    DEFAULT_LIMIT: tuple[int, int] = (60, 60)  # 60 req per 60 seconds

    EXEMPT_PATHS = ("/admin/", "/health")
    EXEMPT_IPS = ("127.0.0.1", "::1", "localhost")

    def __init__(self, redis_url: str | None = None):
        self._url = redis_url or settings.redis_url
        self._client: redis.Redis | None = None
        self._redis_available: bool | None = None
        # In-memory fallback
        self._hits: dict[str, list[float]] = defaultdict(list)

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(self._url, decode_responses=True)
        return self._client

    def _resolve_limit(self, path: str) -> tuple[int, int]:
        """Return (max_requests, window_seconds) for the given path."""
        for prefix, (limit, window) in self.LIMITS.items():
            if path.startswith(prefix):
                return limit, window
        return self.DEFAULT_LIMIT

    def _make_key(self, ip: str, path: str) -> str:
        """Build the rate limit key from IP and endpoint prefix."""
        parts = path.split("/")
        prefix = parts[2] if len(parts) > 2 else "other"
        return f"ratelimit:{ip}:{prefix}"

    def is_exempt(self, path: str, ip: str) -> bool:
        """Check if the request should bypass rate limiting."""
        if ip in self.EXEMPT_IPS:
            return True
        for exempt in self.EXEMPT_PATHS:
            if exempt in path:
                return True
        return False

    def check(self, ip: str, path: str) -> tuple[bool, int]:
        """Check rate limit for a request.

        Returns:
            (allowed, retry_after) — allowed is True if under limit,
            retry_after is the window in seconds (used for Retry-After header).
        """
        max_requests, window = self._resolve_limit(path)
        key = self._make_key(ip, path)

        try:
            return self._check_redis(key, max_requests, window)
        except (redis.ConnectionError, redis.TimeoutError, OSError) as e:
            if self._redis_available is not False:
                logger.debug("Redis unavailable for rate limiting, using in-memory fallback: %s", e)
                self._redis_available = False
            return self._check_memory(key, max_requests, window)

    def _check_redis(self, key: str, max_requests: int, window: int) -> tuple[bool, int]:
        """Sliding window check using Redis sorted sets + pipeline."""
        now = time.time()
        window_start = now - window

        pipe = self.client.pipeline(transaction=True)
        pipe.zremrangebyscore(key, "-inf", window_start)
        pipe.zcard(key)
        pipe.zadd(key, {f"{now}:{uuid.uuid4().hex[:8]}": now})
        pipe.expire(key, window + 1)
        results = pipe.execute()

        current_count = results[1]  # ZCARD result (before ZADD)

        if current_count >= max_requests:
            # Over limit — remove the entry we just added
            try:
                self.client.zremrangebyscore(key, now, now + 0.001)
            except (redis.ConnectionError, redis.TimeoutError, OSError):
                pass
            self._redis_available = True
            return False, window

        self._redis_available = True
        return True, window

    def _check_memory(self, key: str, max_requests: int, window: int) -> tuple[bool, int]:
        """In-memory fallback using the same sliding window approach."""
        now = time.time()
        self._hits[key] = [t for t in self._hits[key] if now - t < window]

        if len(self._hits[key]) >= max_requests:
            return False, window

        self._hits[key].append(now)
        return True, window
