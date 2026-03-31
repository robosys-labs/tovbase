# Tovbase — Project Status & Pending Tasks

Last updated: 2026-03-28

## Completion Status

### DONE — Core Backend (100%)
- [x] Trust scoring engine — 5 sub-scores (existence, consistency, engagement, cross-platform, maturity)
- [x] Company scoring engine — 6 sub-scores (founder, product, community, presence, execution, consistency)
- [x] Behavioral vector system — 32-dimensional, deterministic, Qdrant-backed
- [x] Cross-platform identity resolution — 5-signal similarity (vector, chronotype, voice, name, topic)
- [x] Database models — CanonicalIdentity, IdentityProfile, IdentityLink, CompanyProfile, FeedSource, TopicEntry
- [x] Redis cache layer — scores (1h), profiles (24h), resolution (24h)
- [x] Celery background workers — vector recompute, identity resolve, score refresh, feed fetch
- [x] Confidence dampening — observation-count-based multiplier (0.25–1.0)
- [x] Sentiment analysis — lexicon-based with negation/intensifier handling

### DONE — API Endpoints (100%)
- [x] GET /v1/score/{platform}/{handle} — individual trust score
- [x] GET /v1/identity/{handle} — full cross-platform identity
- [x] POST /v1/profile/observe — submit observation (now analyses post_texts for voice/topics)
- [x] GET /v1/similar/{platform}/{handle} — behavioral vector search
- [x] POST /v1/report/generate — due diligence report (data-driven assessment, activity, network)
- [x] GET /v1/health — service health check
- [x] GET /v1/company/score/{platform}/{handle} — company trust score
- [x] POST /v1/company/observe — company observation
- [x] POST /v1/ingest/{platform} — identity pipeline ingestion
- [x] POST /v1/topics/search — real-time topic query (agent-facing)
- [x] POST /v1/topics/ingest — topic pipeline ingestion
- [x] GET /v1/topics/sources — list feed sources
- [x] GET /v1/topics/categories — category summary

### DONE — Ingestion Pipeline (100%)
- [x] Twitter/X adapter
- [x] GitHub adapter
- [x] Reddit adapter
- [x] Hacker News adapter
- [x] LinkedIn adapter
- [x] Instagram adapter
- [x] Polymarket adapter
- [x] 4chan adapter (archive-based)
- [x] YCombinator adapter (company-type)
- [x] YouTube adapter
- [x] Bluesky adapter
- [x] Topic extraction — deterministic keyword matching, 10 categories
- [x] Voice feature extraction — statistical linguistic analysis
- [x] RSS/Atom feed parser — RSS 2.0, Atom, RSS 1.0 (RDF)

### DONE — Feed Source Database (100%)
- [x] ~140 feeds across 6 continents, 30+ countries
- [x] Categories: technology, ai_ml, finance, crypto_web3, security, programming, infrastructure, product, science, politics
- [x] Source types: news, blog, forum, academic, gov, social
- [x] Reliability scores calibrated per source
- [x] Per-source fetch intervals

### DONE — Chrome Extension (100%)
- [x] Platform detection: LinkedIn, Twitter/X, GitHub, Reddit, HN, Instagram, Polymarket, LinkedIn Company, Bluesky, YouTube
- [x] Score overlay — glassmorphism pill with SVG arc ring
- [x] Hover-expand modal — sub-score bars, confidence dots, CTA
- [x] Popup UI — matching dark theme with full breakdown
- [x] Options page — dev/production/custom API server toggle
- [x] Dark mode support
- [x] SPA navigation detection (MutationObserver)

### DONE — Web Frontend (90%)
- [x] Homepage with search bar
- [x] Report page — renders all 4 tabs (AI Summary, Trust Signals, Timeline, Network)
- [x] Report page handles null/missing data gracefully
- [x] API client uses Next.js rewrite proxy for SSR, direct for client
- [x] Removed all mock data (Sarah Chen hardcoded fallback)
- [x] ScoreBadge, TierLabel, PlatformBadge, SignalBar, TabPanel components

### DONE — Tests (116 passing)
- [x] test_scoring.py — 10 tests (individual scoring engine)
- [x] test_similarity.py — 11 tests (identity resolution)
- [x] test_vector.py — 9 tests (behavioral vectors)
- [x] test_company_scoring.py — 16 tests (company scoring + topic extraction)
- [x] test_ingestion.py — 37 tests (all adapters + sentiment + voice)
- [x] test_topics.py — 8 tests (RSS parsing, YouTube/Bluesky adapters)
- [x] test_personas.py — 29 tests (Amara Okafor, GhostTrader, NovaPay end-to-end)
- [x] Performance: individual scoring <0.2ms, company scoring <0.05ms

---

## PENDING — Requires Implementation

### P0 — Needed for MVP launch

#### Scraper Execution Layer
The ingestion adapters normalise data but there's no code that actually fetches
data from platform APIs. Each platform needs a scheduled job:
- [ ] Twitter/X API client (OAuth 2.0 bearer token, rate limiting)
- [ ] GitHub API client (REST v3, pagination)
- [ ] Reddit API client (PRAW or direct OAuth)
- [ ] Hacker News API client (Firebase-based, trivial)
- [ ] LinkedIn scraping strategy (no public API — requires approach decision)
- [ ] Bluesky AT Protocol client (public firehose available)
- [ ] Instagram scraping strategy (highly restricted API)
- [ ] RSS feed fetcher worker scheduling (Celery beat config for `fetch_all_feeds`)

#### Database Migrations
- [ ] Set up Alembic with `alembic init` and `alembic revision --autogenerate`
- [ ] Generate initial migration from current models
- [ ] Current approach (`Base.metadata.create_all`) won't handle schema changes

#### OAuth Claiming Flow
- [ ] OAuth integration (Google, GitHub, LinkedIn, Twitter)
- [ ] Profile verification endpoint
- [ ] Claim status update logic
- [ ] Claimed profile trust bonus in scoring

### P1 — Important for Quality

#### Web Frontend Gaps
- [ ] Profile page (`/profile/[handle]`) — needs rewrite to use actual API fields
- [ ] SearchBar error state handling
- [ ] Tailwind custom colours (`trust-excellent`, `trust-fair`, etc.) — need to verify in tailwind config or replace with inline styles
- [ ] Loading states and skeleton screens
- [ ] Mobile responsiveness audit

#### Monitoring & Observability
- [ ] Structured logging (currently using basic `logging.debug`)
- [ ] Request tracing (correlation IDs)
- [ ] Metrics endpoint (Prometheus)
- [ ] Error reporting (Sentry integration)

#### Rate Limiting
- [ ] Add FastAPI rate limiting middleware (slowapi or custom)
- [ ] Per-IP and per-API-key limits
- [ ] Extension API key authentication

### P2 — Nice to Have

#### Enhanced Topic Intelligence
- [ ] Entity extraction from topic entries (NER for people, companies, products)
- [ ] Trending topic detection (velocity-based)
- [ ] Topic alert webhooks (notify when topic volume spikes)
- [ ] Topic-to-identity enrichment (link topic authors to identity graph)

#### Agent Scoring
- [ ] Agent wallet registration system
- [ ] Agent-specific scoring dimensions (uptime, transaction completion, dispute rate)
- [ ] Agent identity verification via principal linking

#### Enterprise Features
- [ ] Team dashboard
- [ ] ATS integration (Greenhouse, Lever)
- [ ] Bulk report generation
- [ ] PDF export
- [ ] Score change alerts

#### Infrastructure
- [ ] Dockerfile for API server
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Celery beat configuration for periodic tasks
- [ ] Production Redis persistence configuration
- [ ] Qdrant backup strategy

---

## Architecture Decisions Made

1. **No ML models** — All scoring is deterministic statistical math. Cost target: $135-370/mo.
2. **Qdrant for vectors** (not pgvector) — billion-scale similarity search.
3. **Two distinct pipelines** — Identity (profiles people) vs Topic (indexes content for real-time query).
4. **Lexicon-based sentiment** — Curated word lists with negation handling, no GPU needed.
5. **Company scoring as composite** — Founder individual scores feed into company score.
6. **Feed-by-country organisation** — Geographic coverage for global topic intelligence.
