"""Tests for Redis-backed rate limiter with in-memory fallback."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import redis

from app.services.rate_limit import RedisRateLimiter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_limiter_memory_only() -> RedisRateLimiter:
    """Create a limiter that always falls back to in-memory."""
    limiter = RedisRateLimiter(redis_url="redis://nonexistent:9999/0")
    # Force the Redis client to raise on any operation
    mock_client = MagicMock()
    mock_client.pipeline.side_effect = redis.ConnectionError("test: redis unavailable")
    limiter._client = mock_client
    return limiter


def _make_limiter_redis_mock() -> tuple[RedisRateLimiter, MagicMock]:
    """Create a limiter with a mocked Redis that simulates sorted set ops."""
    limiter = RedisRateLimiter()
    mock_client = MagicMock()

    # Track call count per key for ZCARD simulation
    _counts: dict[str, int] = {}

    def _pipeline_factory(transaction=True):
        pipe = MagicMock()
        _pipe_key = [None]
        _pipe_count = [0]

        def _zremrangebyscore(key, *args):
            _pipe_key[0] = key

        def _zcard(key):
            _pipe_count[0] = _counts.get(key, 0)

        def _zadd(key, mapping):
            pass

        def _expire(key, ttl):
            pass

        def _execute():
            key = _pipe_key[0]
            count = _pipe_count[0]
            # Increment count after execute (simulates ZADD)
            _counts[key] = count + 1
            return [None, count, None, None]

        pipe.zremrangebyscore = _zremrangebyscore
        pipe.zcard = _zcard
        pipe.zadd = _zadd
        pipe.expire = _expire
        pipe.execute = _execute
        return pipe

    mock_client.pipeline = _pipeline_factory
    mock_client.zremrangebyscore = MagicMock()
    limiter._client = mock_client
    return limiter, mock_client


# ---------------------------------------------------------------------------
# Tests: Exemptions
# ---------------------------------------------------------------------------

class TestExemptions:
    def test_admin_path_exempt(self):
        limiter = RedisRateLimiter()
        assert limiter.is_exempt("/v1/admin/settings", "8.8.8.8") is True

    def test_health_path_exempt(self):
        limiter = RedisRateLimiter()
        assert limiter.is_exempt("/v1/health", "8.8.8.8") is True

    def test_localhost_exempt(self):
        limiter = RedisRateLimiter()
        assert limiter.is_exempt("/v1/score/twitter/alice", "127.0.0.1") is True
        assert limiter.is_exempt("/v1/score/twitter/alice", "::1") is True
        assert limiter.is_exempt("/v1/score/twitter/alice", "localhost") is True

    def test_normal_path_not_exempt(self):
        limiter = RedisRateLimiter()
        assert limiter.is_exempt("/v1/score/twitter/alice", "8.8.8.8") is False


# ---------------------------------------------------------------------------
# Tests: Endpoint-specific limits
# ---------------------------------------------------------------------------

class TestEndpointLimits:
    def test_score_endpoint_limit_120(self):
        limiter = RedisRateLimiter()
        max_req, window = limiter._resolve_limit("/v1/score/twitter/alice")
        assert max_req == 120
        assert window == 60

    def test_report_endpoint_limit_10(self):
        limiter = RedisRateLimiter()
        max_req, window = limiter._resolve_limit("/v1/report/generate")
        assert max_req == 10
        assert window == 60

    def test_ingest_endpoint_limit_30(self):
        limiter = RedisRateLimiter()
        max_req, window = limiter._resolve_limit("/v1/ingest/profile")
        assert max_req == 30
        assert window == 60

    def test_enrich_endpoint_limit_10(self):
        limiter = RedisRateLimiter()
        max_req, window = limiter._resolve_limit("/v1/enrich/profile")
        assert max_req == 10
        assert window == 60

    def test_default_limit_60(self):
        limiter = RedisRateLimiter()
        max_req, window = limiter._resolve_limit("/v1/identity/alice")
        assert max_req == 60
        assert window == 60


# ---------------------------------------------------------------------------
# Tests: Rate limiting triggers after threshold (in-memory fallback)
# ---------------------------------------------------------------------------

class TestInMemoryLimiting:
    def test_allows_under_limit(self):
        limiter = _make_limiter_memory_only()
        for _ in range(10):
            allowed, _ = limiter.check("1.2.3.4", "/v1/report/generate")
            assert allowed is True

    def test_blocks_at_limit(self):
        limiter = _make_limiter_memory_only()
        ip = "1.2.3.4"
        path = "/v1/report/generate"  # 10 req/min limit

        for i in range(10):
            allowed, _ = limiter.check(ip, path)
            assert allowed is True, f"Request {i+1} should be allowed"

        # 11th request should be blocked
        allowed, retry_after = limiter.check(ip, path)
        assert allowed is False
        assert retry_after == 60

    def test_different_ips_independent(self):
        limiter = _make_limiter_memory_only()
        path = "/v1/report/generate"  # 10 req/min

        # Exhaust limit for IP A
        for _ in range(10):
            limiter.check("1.1.1.1", path)

        # IP B should still be allowed
        allowed, _ = limiter.check("2.2.2.2", path)
        assert allowed is True

    def test_different_endpoints_independent(self):
        limiter = _make_limiter_memory_only()
        ip = "1.2.3.4"

        # Exhaust report limit (10 req)
        for _ in range(10):
            limiter.check(ip, "/v1/report/generate")

        # Score endpoint should still be allowed (different key prefix)
        allowed, _ = limiter.check(ip, "/v1/score/twitter/alice")
        assert allowed is True


# ---------------------------------------------------------------------------
# Tests: Redis-backed limiting
# ---------------------------------------------------------------------------

class TestRedisLimiting:
    def test_allows_under_limit_redis(self):
        limiter, mock = _make_limiter_redis_mock()
        allowed, _ = limiter.check("1.2.3.4", "/v1/score/twitter/alice")
        assert allowed is True

    def test_blocks_at_limit_redis(self):
        limiter, mock = _make_limiter_redis_mock()
        ip = "1.2.3.4"
        path = "/v1/report/generate"  # 10 req/min

        for i in range(10):
            allowed, _ = limiter.check(ip, path)
            assert allowed is True, f"Request {i+1} should be allowed"

        # 11th should be blocked
        allowed, retry_after = limiter.check(ip, path)
        assert allowed is False
        assert retry_after == 60


# ---------------------------------------------------------------------------
# Tests: Fallback to in-memory when Redis unavailable
# ---------------------------------------------------------------------------

class TestFallback:
    def test_falls_back_on_connection_error(self):
        limiter = _make_limiter_memory_only()
        # Should still work via in-memory
        allowed, _ = limiter.check("1.2.3.4", "/v1/score/twitter/alice")
        assert allowed is True
        assert limiter._redis_available is False

    def test_fallback_still_enforces_limits(self):
        limiter = _make_limiter_memory_only()
        ip = "1.2.3.4"
        path = "/v1/report/generate"  # 10 req/min

        for _ in range(10):
            limiter.check(ip, path)

        allowed, _ = limiter.check(ip, path)
        assert allowed is False


# ---------------------------------------------------------------------------
# Tests: Retry-After header value
# ---------------------------------------------------------------------------

class TestRetryAfter:
    def test_retry_after_matches_window(self):
        limiter = _make_limiter_memory_only()
        ip = "1.2.3.4"
        path = "/v1/report/generate"  # window = 60s

        for _ in range(10):
            limiter.check(ip, path)

        _, retry_after = limiter.check(ip, path)
        assert retry_after == 60

    def test_retry_after_default_endpoint(self):
        limiter = _make_limiter_memory_only()
        ip = "1.2.3.4"
        path = "/v1/identity/someone"  # default: 60 req, window=60s

        for _ in range(60):
            limiter.check(ip, path)

        _, retry_after = limiter.check(ip, path)
        assert retry_after == 60
