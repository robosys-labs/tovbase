# Tovbase — Trustgate Backend

Trustgate is a real-time trust scoring engine for online identities. Tovbase is the codebase. It computes trust scores (0-1000) from statistical behavioral profiling across multiple platforms — no ML models, no GPUs, pure deterministic math.

## Architecture

Three-layer stack:

1. **FastAPI backend** (`app/`) — API, scoring engine, vector search, caching
2. **Next.js website** (`web/`) — Report pages, search, profile claiming
3. **Chrome extension** (`extension/`) — MV3, ambient score overlay on social profiles

## Tech Stack

| Layer | Stack |
|-------|-------|
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2.0, Pydantic 2.0 |
| Vector DB | Qdrant (dedicated, NOT pgvector) |
| Cache | Redis |
| Workers | Celery with Redis broker |
| Database | SQLite (dev), PostgreSQL 16 (prod) |
| Frontend | Next.js 15, React 19, Tailwind 4, pnpm |
| Extension | Chrome Manifest V3 |

## Directory Structure

```
tovbase/
  app/
    config.py              # Pydantic settings (ports, URLs, weights, thresholds)
    models.py              # SQLAlchemy ORM: IdentityProfile, CanonicalIdentity, IdentityLink
    schemas.py             # Pydantic request/response models
    main.py                # FastAPI app init, CORS, Qdrant collection setup
    db.py                  # Engine, SessionLocal, Base, get_db()
    workers.py             # Celery tasks (vector recompute, identity resolve, score refresh)
    api/
      routes.py            # All endpoints under /v1 prefix
    services/
      scoring.py           # 5 sub-score functions + compute_trust_score()
      vector.py            # 32-dim behavioral vector + Qdrant client
      similarity.py        # Cross-platform identity resolution (5 signals)
      cache.py             # Redis cache layer
  web/                     # Next.js 15 app
    app/
      page.tsx             # Homepage with SearchBar hero
      layout.tsx           # Root layout, header, footer
      report/[id]/page.tsx # Full report (4 tabs: Summary, Signals, Activity, Network)
      profile/[handle]/page.tsx
    components/            # ScoreBadge, SignalBar, TierLabel, PlatformBadge, TabPanel, SearchBar
    lib/api.ts             # Typed API client + Sarah Chen mock data fallback
  extension/               # Chrome MV3
    manifest.json
    content.js             # Profile detection + badge overlay for 6 platforms
    background.js          # Score fetching + 1h chrome.storage cache
    popup.html / popup.js  # Current page score display
    styles.css             # Scoped .tg- prefix, dark mode support
  tests/
    conftest.py            # 5 fixtures: established, new, bot, same_person, different_person
    test_scoring.py        # 14 tests
    test_similarity.py     # 11 tests
    test_vector.py         # 9 tests
  scripts/
    seed.py                # Seeds Sarah Chen (5 platforms, score ~815)
  docker-compose.yml       # Postgres 16, Redis 7, Qdrant 1.9
  pyproject.toml
  .env
```

## Non-Negotiable Design Decisions

These are fundamental to the project identity. Do not change them.

1. **Deterministic statistical profiling only.** No ML models, no GPU instances, no learned weights, no neural networks. All scoring is mathematical: clamping, log normalization, weighted sums, cosine similarity. This is what makes the $135-370/mo cost target possible.

2. **6 behavioral dimensions from psychology/social science, NOT transactional fraud.** The dimensions are: Chronotype (when), Voice (how they communicate), Social Posture (how they relate), Topical Identity (what they care about), Presence Pattern (how consistently they show up), Trust Signals (authenticity markers). These were designed from scratch — not adapted from DebitProfile or fraud detection.

3. **Qdrant for vector search, NOT pgvector.** PostgreSQL is not built for billion-scale vector similarity search. Qdrant with HNSW indexing is purpose-built for this. Collection: `identity_vectors`, 32-dim, cosine distance.

4. **5-sub-score trust engine (0-1000) with confidence dampening.** Each sub-score is 0-200: Existence, Consistency, Engagement, Cross-Platform, Maturity. Confidence dampening: <5 obs → 0.33x, <15 obs → 0.55x, <30 obs → 0.80x, 30+ → 1.0x.

5. **Multi-signal identity resolution.** No single signal is sufficient. Weights: vector 35%, voice 25%, chronotype 20%, name 15%, topic 5%. Thresholds: >=0.75 auto-link, 0.55-0.75 review, <0.55 separate.

6. **SQLite for dev, Postgres for prod.** Use `JSON` column type everywhere (not `ARRAY(Float)` or `JSONB`) for SQLite compatibility. The `.env` file controls which database is used.

7. **API runs on port 8001** (not 8000 — conflicts with another service on the developer's machine). Web dev server runs on port 3002.

## Development Commands

```bash
# Backend
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8001

# Seed demo data (Sarah Chen, 5 platforms, score ~815)
python scripts/seed.py

# Tests (42 tests)
python -m pytest tests/ -v --tb=short

# Web frontend
cd web && pnpm install && pnpm dev    # runs on port 3002

# Docker services (Postgres, Redis, Qdrant)
docker compose up -d

# Lint
ruff check app/ tests/
```

## API Endpoints

All under `/v1` prefix:

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/v1/score/{platform}/{handle}` | Extension hot path (<100ms cached) |
| GET | `/v1/identity/{handle}` | Full cross-platform profile lookup |
| POST | `/v1/profile/observe` | Submit observation data from scrapers/extension |
| GET | `/v1/similar/{platform}/{handle}` | Find similar identities via Qdrant |
| POST | `/v1/report/generate` | Generate full due diligence report |
| GET | `/v1/health` | Health check (DB, Redis, Qdrant) |

## Code Conventions

- **Service functions** return `(float, dict)` tuples — the float is the sub-score, the dict contains detail breakdown for transparency.
- **Schemas** live in `app/schemas.py` — Pydantic models for all request/response types.
- **Routes** live in `app/api/routes.py` — all endpoints in one file under the `/v1` prefix.
- **Tests** use fixtures from `conftest.py`. Create profiles with `_make_profile(**overrides)` helper. One test file per service module.
- **Vector values** are always normalized to [0, 1] range using `_clamp()`.
- **Config** is centralized in `app/config.py` via pydantic-settings. All thresholds, weights, and TTLs are configurable via env vars.

## Behavioral Vector Layout (32 dimensions)

```
Dims 0-3:   Chronotype  (sin/cos peak hour, regularity, weekend_ratio)
Dims 4-9:   Voice       (vocabulary, formality, emotion, utterance length, Q-ratio, self-ref)
Dims 10-15: Social      (initiation, depth, authority, reciprocity, audience, quality)
Dims 16-21: Topics      (top 4 category weights, expertise, originality)
Dims 22-27: Presence    (posts/week, activity weeks, growth, responsiveness, tenure, persistence)
Dims 28-31: Trust       (account age, completeness, linked platforms, clean record)
```

## Score Tiers

| Range | Tier | Color |
|-------|------|-------|
| 850-1000 | Excellent | #0F6E56 (green) |
| 700-849 | Good | #0F6E56 (green) |
| 550-699 | Fair | #BA7517 (orange) |
| 350-549 | Poor | #DC2626 (red) |
| 0-349 | Untrusted | #DC2626 (red) |

## Cache Keys (Redis)

| Pattern | TTL | Content |
|---------|-----|---------|
| `score:{canonical_id}` | 1h | Trust score + breakdown |
| `profile:{handle}:{platform}` | 24h | Serialized profile |
| `resolve:{handle}` | 24h | Canonical identity ID |

## Infrastructure Cost Target

$135-370/mo total. This is 90% below the original GPU+Neo4j architecture ($2,300/mo). Do not introduce dependencies that significantly increase this (no GPU instances, no expensive managed services).

## CORS

Backend allows origins: `http://localhost:3002`, `http://localhost:3000`, `chrome-extension://*`.

## Extension Platforms

Content scripts detect profiles on: LinkedIn (`/in/*`), Twitter/X, GitHub, Reddit (`/user/*`), Hacker News (`/user?id=*`). Badge overlays are positioned near profile names with `.tg-` prefixed CSS classes.
