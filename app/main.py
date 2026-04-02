from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes import router
from app.config import settings
from app.db import Base, engine
from app.services.rate_limit import RedisRateLimiter
from app.services.vector import VectorService


# ---------------------------------------------------------------------------
# Rate limiting middleware (Redis-backed with in-memory fallback)
# ---------------------------------------------------------------------------

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter per client IP.

    Backed by Redis sorted sets for distributed state across workers.
    Falls back to in-memory when Redis is unavailable.

    Limits:
      /v1/score/         — 120 req/min (extension hot path)
      /v1/report/        — 10 req/min (expensive computation)
      /v1/ingest/        — 30 req/min
      /v1/enrich/        — 10 req/min
      /v1/admin/         — exempt
      everything else    — 60 req/min
    """

    def __init__(self, app):
        super().__init__(app)
        self._limiter = RedisRateLimiter()

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        ip = request.client.host if request.client else "unknown"

        if self._limiter.is_exempt(path, ip):
            return await call_next(request)

        allowed, retry_after = self._limiter.check(ip, path)

        if not allowed:
            return Response(
                content='{"detail":"Rate limit exceeded. Try again later."}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)


app = FastAPI(
    title="Tovbase",
    description="Statistical identity profiling and trust scoring engine",
    version="0.1.0",
)

app.add_middleware(RateLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
def startup():
    import logging
    log = logging.getLogger("tovbase")

    Base.metadata.create_all(bind=engine)

    try:
        vs = VectorService()
        vs.ensure_collection()
    except Exception as e:
        log.info("Qdrant not available at startup: %s", e)

    # Log browser session status for authenticated scraping
    try:
        from app.services.scraper import get_scraper_pool
        pool = get_scraper_pool()
        statuses = pool.get_all_status_sync()
        configured = [s["platform"] for s in statuses if s["profile_exists"]]
        missing = [s["platform"] for s in statuses if not s["profile_exists"]]
        if configured:
            log.info("Browser sessions configured: %s", ", ".join(configured))
        if missing:
            log.info("Browser sessions missing: %s — use POST /v1/admin/auth/login/{platform} to set up", ", ".join(missing))
    except Exception:
        pass  # Playwright may not be installed
