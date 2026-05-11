# Trustgate — an open trust graph for online identities

> Paste a profile URL. Get a 30-second, auditable, **deterministic** trust score for any human, organization, or AI agent on the public web.

Trustgate computes a number between 0 and 1000 from public behavioral data across multiple platforms. The math is open, the seed list is contestable, and every score has a permanent audit URL. There are no learned weights, no GPU instances, and no proprietary signals — by design.

[![tests](https://img.shields.io/badge/tests-196%20passing-brightgreen)](#) [![algorithm](https://img.shields.io/badge/algorithm-v1.2.0-blue)](docs/WHITEPAPER.md) [![cost](https://img.shields.io/badge/infra-%24135--370%2Fmo-green)](docs/WHITEPAPER.md)

- **Whitepaper:** [docs/WHITEPAPER.md](docs/WHITEPAPER.md) (12 pages, technical-practical)
- **Algorithm:** 6 sub-scores + multiplicative graph boost + Sybil demotion + composable credentials, all deterministic
- **Graph layer:** Personalized PageRank from a public seed list ([seeds/trust_seeds.yaml](seeds/trust_seeds.yaml)), Leiden community detection for Sybil rings
- **Adversarial corpus:** [corpus/README.md](corpus/README.md) (1000 good + 1000 bad + 200 edge targeted; v0.2 ships seed entries)
- **Governance:** [GOVERNANCE.md](GOVERNANCE.md) — public maintainer rules, 14-day seed-list comment window
- **Contributing:** [CONTRIBUTING.md](CONTRIBUTING.md)
- **Roadmap:** [ROADMAP.md](ROADMAP.md)

## 5-minute local setup

```bash
git clone https://github.com/<org>/tovbase.git
cd tovbase
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Postgres / Redis / Qdrant (in Docker)
docker compose up -d

# Seed Sarah Chen — a 5-platform demo identity, score ~815
python scripts/seed.py

# Run the API
uvicorn app.main:app --reload --port 8001

# Hit it
curl http://localhost:8001/v1/score/twitter/sarahchen
```

## What does the algorithm do?

Six sub-scores feed a composite, each grounded in a different psychological / social signal:

| Sub-score        | Range | What it measures |
|------------------|-------|------------------|
| **Existence**       | 0–200 | Account age, profile completeness, platforms, observations, verification, *corroborated* audience |
| **Consistency**     | 0–200 | Chronotype regularity, voice stability, presence, cadence |
| **Engagement**      | 0–200 | Depth, reciprocity, growth organicity, response rate |
| **Cross-platform**  | 0–200 | Mean pairwise behavioral-vector cosine + coverage + name similarity |
| **Maturity**        | 0–200 | Tenure, activity volume, authority, clean record, *corroborated* audience |
| **Network trust** *(B1)* | 0–200 | Personalized PageRank from the public seed set, with time-decayed edges |

Composite:

```
final = clamp(0, 1000,
    raw_total × dampening × network_boost × sybil_factor
  + credential_bonus
)
```

Full derivation: [docs/WHITEPAPER.md §3](docs/WHITEPAPER.md). Source: [app/services/scoring.py](app/services/scoring.py).

## Why open?

A trust score is only as credible as the process that produces it. Closed scoring systems — credit bureaus, platform-internal reputation — make the same numbers people are forced to live by but cannot inspect, challenge, or rebuild from scratch. Trustgate is the bet that the *opposite* approach works better at internet scale: a deterministic algorithm anyone can audit, run, fork, or improve.

If you publish a score for someone, the whole computation that produced it is reachable from a permanent URL. If you disagree with a score, the way to change it is to change the algorithm — and the algorithm-change process is documented, two-maintainer-gated, and corpus-evaluated.

## Architecture

```
   Chrome ext   →                                  → Postgres (canonicals, edges, creds)
                    FastAPI /v1   ─ Celery jobs ┤
   Next.js site →                                  → Qdrant (32-dim behavioral vectors)
                                                   → Redis (cache + rate limiting)
```

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy 2.0, Pydantic 2.0 — [`app/`](app/)
- **Vector DB:** Qdrant (NOT pgvector — purpose-built for billion-scale HNSW)
- **Graph layer:** networkx (PPR) + python-igraph (Leiden), CPU-only, in-process on Celery — [`app/services/graph_trust.py`](app/services/graph_trust.py)
- **Frontend:** Next.js 15 / React 19 on port 3002 — [`web/`](web/)
- **Extension:** Chrome MV3, ambient score badges on 6 platforms — [`extension/`](extension/)

Total infra cost target: **$135–370/mo** for a population in the low millions. ([Cost breakdown](docs/WHITEPAPER.md#52-cost-envelope))

## API surface

All endpoints under `/v1`. Hot-path extension calls return in < 100 ms when cached.

| Method | Path | Purpose |
|--------|------|---------|
| `GET`  | `/v1/score/{platform}/{handle}` | Trust score for a profile |
| `GET`  | `/v1/score/audit/{canonical_id}` | Permanent audit log for a score |
| `GET`  | `/v1/identity/{handle}` | Full cross-platform identity |
| `POST` | `/v1/profile/observe` | Ingest observation data |
| `GET`  | `/v1/similar/{platform}/{handle}` | Vector-similar profiles |
| `POST` | `/v1/report/generate` | Full due-diligence report |
| `POST` | `/v1/credentials/attach` | Attach a verified external credential |
| `GET`  | `/v1/credentials/{canonical_id}` | List active credentials |
| `GET`  | `/v1/health` | DB / Redis / Qdrant health check |

Plus topic, scrape, enrich, company, and admin endpoints. See [`app/api/routes.py`](app/api/routes.py).

## Reproducing whitepaper numbers

```bash
# Score the bootstrapped adversarial corpus
python scripts/run_corpus.py

# Re-score every canonical identity in the DB (run after algorithm changes)
python scripts/recompute_all_scores.py

# Compute PPR + Leiden communities (normally weekly / nightly Celery jobs)
python -c "from app.workers import compute_ppr_task, compute_communities_task; \
           print(compute_ppr_task()); print(compute_communities_task())"
```

Every score response includes `algorithm_version` and `weights_version`. Pin them in any benchmark you publish.

## What this isn't

- **Not a surveillance tool.** Public behavioral data only. No DMs, no emails, no purchased data.
- **Not a credit score.** No financial signals. No regulatory reporting. No adverse actions outside the documented process.
- **Not ML.** Determinism is the moat. Prompt-injection and adversarial-example attacks on ML reputation classifiers don't apply.
- **Not a final word.** The score is one input. We say so on every report.

## License

MIT. See [LICENSE](LICENSE).

## Maintainers

See [MAINTAINERS.md](MAINTAINERS.md) (placeholder for v0.3). For security disclosures, email the address listed there.
