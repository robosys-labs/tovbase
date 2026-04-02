import time
from collections import defaultdict

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes import router
from app.db import Base, engine
from app.services.vector import VectorService


# ---------------------------------------------------------------------------
# Rate limiting middleware (in-memory, per-IP)
# ---------------------------------------------------------------------------

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple sliding-window rate limiter per client IP.

    Limits:
      /v1/score/         — 120 req/min (extension hot path)
      /v1/report/        — 10 req/min (expensive computation)
      /v1/ingest/        — 30 req/min
      /v1/enrich/        — 10 req/min
      /v1/admin/         — exempt
      everything else    — 60 req/min
    """

    LIMITS: dict[str, tuple[int, int]] = {
        "/v1/score/":   (120, 60),
        "/v1/report/":  (10, 60),
        "/v1/ingest/":  (30, 60),
        "/v1/enrich/":  (10, 60),
        "/v1/profile/claim": (30, 60),
        "/v1/profile/verify": (30, 60),
    }
    DEFAULT_LIMIT = (60, 60)  # 60 req per 60 seconds

    def __init__(self, app):
        super().__init__(app)
        self._hits: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Admin endpoints are exempt
        if "/admin/" in path:
            return await call_next(request)

        # Health endpoint is exempt
        if path.endswith("/health"):
            return await call_next(request)

        # Localhost/loopback is exempt (Next.js SSR server-to-server calls)
        ip = request.client.host if request.client else "unknown"
        if ip in ("127.0.0.1", "::1", "localhost"):
            return await call_next(request)

        # Find matching limit
        max_requests, window = self.DEFAULT_LIMIT
        for prefix, (limit, win) in self.LIMITS.items():
            if path.startswith(prefix):
                max_requests, window = limit, win
                break

        key = f"{ip}:{path.split('/')[2] if len(path.split('/')) > 2 else 'other'}"
        now = time.time()

        # Clean old entries
        self._hits[key] = [t for t in self._hits[key] if now - t < window]

        if len(self._hits[key]) >= max_requests:
            return Response(
                content='{"detail":"Rate limit exceeded. Try again later."}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(window)},
            )

        self._hits[key].append(now)
        return await call_next(request)


app = FastAPI(
    title="Tovbase",
    description="Statistical identity profiling and trust scoring engine",
    version="0.1.0",
)

app.add_middleware(RateLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3002", "http://localhost:3000"],
    allow_origin_regex=r"^chrome-extension://.*$",
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
