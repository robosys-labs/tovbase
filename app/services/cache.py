"""Redis cache layer for scores, profiles, and identity resolution.

All methods are resilient to Redis being unavailable — they return None/False
on connection errors so the application degrades gracefully without cache.

Key patterns:
  score:{canonical_id}           -> JSON ScoreBreakdown (TTL: 1h)
  profile:{handle}:{platform}    -> JSON IdentityProfile fields (TTL: 24h)
  resolve:{handle}               -> canonical_identity_id string (TTL: 24h)
"""

from __future__ import annotations

import json
import logging
from typing import Any

import redis

from app.config import settings

logger = logging.getLogger("tovbase.cache")


class CacheService:
    def __init__(self, url: str | None = None):
        self._url = url or settings.redis_url
        self._client: redis.Redis | None = None
        self._available: bool | None = None

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(self._url, decode_responses=True)
        return self._client

    def _safe(self, fn, *args, default=None):
        """Execute a Redis operation, returning default on connection error."""
        try:
            return fn(*args)
        except (redis.ConnectionError, redis.TimeoutError, OSError) as e:
            if self._available is not False:
                logger.debug("Redis unavailable: %s", e)
                self._available = False
            return default

    # -------------------------------------------------------------------
    # Score cache
    # -------------------------------------------------------------------

    def get_score(self, canonical_id: str) -> dict | None:
        key = f"score:{canonical_id}"
        data = self._safe(self.client.get, key)
        if data:
            return json.loads(data)
        return None

    def set_score(self, canonical_id: str, breakdown: dict) -> None:
        key = f"score:{canonical_id}"
        self._safe(self.client.setex, key, settings.cache_score_ttl, json.dumps(breakdown))

    def invalidate_score(self, canonical_id: str) -> None:
        self._safe(self.client.delete, f"score:{canonical_id}")

    # -------------------------------------------------------------------
    # Profile cache
    # -------------------------------------------------------------------

    def get_profile(self, handle: str, platform: str) -> dict | None:
        key = f"profile:{handle}:{platform}"
        data = self._safe(self.client.get, key)
        if data:
            return json.loads(data)
        return None

    def set_profile(self, handle: str, platform: str, profile_data: dict) -> None:
        key = f"profile:{handle}:{platform}"
        self._safe(self.client.setex, key, settings.cache_profile_ttl, json.dumps(profile_data))

    def invalidate_profile(self, handle: str, platform: str) -> None:
        self._safe(self.client.delete, f"profile:{handle}:{platform}")

    # -------------------------------------------------------------------
    # Identity resolution cache
    # -------------------------------------------------------------------

    def get_canonical_id(self, handle: str) -> str | None:
        return self._safe(self.client.get, f"resolve:{handle}")

    def set_canonical_id(self, handle: str, canonical_id: str) -> None:
        self._safe(self.client.setex, f"resolve:{handle}", settings.cache_resolve_ttl, canonical_id)

    def invalidate_resolution(self, handle: str) -> None:
        self._safe(self.client.delete, f"resolve:{handle}")

    # -------------------------------------------------------------------
    # Bulk invalidation
    # -------------------------------------------------------------------

    def invalidate_identity(self, canonical_id: str, handles: list[tuple[str, str]]) -> None:
        """Invalidate all caches for a canonical identity."""
        try:
            pipe = self.client.pipeline()
            pipe.delete(f"score:{canonical_id}")
            for handle, platform in handles:
                pipe.delete(f"profile:{handle}:{platform}")
                pipe.delete(f"resolve:{handle}")
            pipe.execute()
        except (redis.ConnectionError, redis.TimeoutError, OSError):
            pass

    # -------------------------------------------------------------------
    # Health check
    # -------------------------------------------------------------------

    def ping(self) -> bool:
        result = self._safe(self.client.ping, default=False)
        self._available = bool(result)
        return self._available
