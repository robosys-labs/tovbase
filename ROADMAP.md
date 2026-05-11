# Roadmap

Where Trustgate is, where it's going, and what we need help on.

This document is the public version of the work board. It captures the *direction*; specific tasks live in GitHub issues. Anything not on this roadmap is either out of scope or hasn't been thought through yet — both are good reasons to open a discussion.

## Where we are: v0.2 — algorithm v1.2

- **The math works.** 6 sub-scores (Existence, Consistency, Engagement, Cross-Platform, Maturity, Network Trust) feed a deterministic composite score 0–1000.
- **The graph layer ships.** Personalized PageRank over a curated seed list, Leiden community detection for Sybil rings, time-decay on edges — all running on CPU, no GPU instances, no Neo4j.
- **External credentials ship.** GitHub OAuth, Bluesky `did:plc`, and ENS verifiers with diminishing-returns bonus (max +50 points).
- **The infra fits the budget.** FastAPI + Postgres + Redis + Qdrant + Celery. $135–370/mo target.
- **OSS scaffolding is in place.** Algorithm whitepaper, CONTRIBUTING, GOVERNANCE, seed-list with public-comment process.

## Where we're going

### v0.3 — Public corpus + multi-maintainer
**Target: Q3 2026**

- [ ] **Adversarial test corpus.** 1000 known-good + 1000 known-bad + 200 edge-case profiles with target score ranges. `scripts/run_corpus.py` reproduces precision/recall numbers from the whitepaper.
- [ ] **Multi-maintainer transition.** 3-5 maintainers, formal review responsibilities, public RFC process for algorithm changes.
- [ ] **Versioned scoring weights.** Scoring engine reads weights from the `scoring_weights` table at request time; every score response includes `algorithm_version`.
- [ ] **Permanent score audit URL.** `trustgate.io/score/{canonical_id}/v/{version}` returns the exact inputs and computation behind that score — an audit log the public can inspect.
- [ ] **Recall on Sybil benchmark.** Synthetic Sybil-ring fixtures showing ≥95% recall at <1% false-positive on a hand-labeled cohort.

### v0.4 — Whitepaper v2 + agent identity
**Target: Q4 2026**

- [ ] **Whitepaper v2 on arXiv.** Empirical section grounded in v0.3 corpus eval. Formal section explores Sybil-resistance bounds for PPR with seed mass.
- [ ] **Agent identity hooks.** `canonical_identity.agent_kind` and optional `agent_passport_did` for NANDA / AgentFacts integration when those standards stabilize. Agent scores weight recent behavior heavier (90d decay vs 365d for humans).
- [ ] **Explicit endorsement layer.** Claimed users can vouch for other claimed users. Endorsement edges feed PPR with weight proportional to endorser trust.
- [ ] **Mastodon, Threads, more platforms.** Adapter PRs welcome.

### v1.0 — Foundation + public launch
**Target: H1 2027**

- [ ] **Non-profit / foundation governance.** Sigstore-style umbrella; legal entity holds infrastructure trust roots and signing material.
- [ ] **Public production endpoint.** Rate-limited free tier, hosted score API, claimed profile pages.
- [ ] **Worldcoin / PoP verifier.** Behind a config flag; political controversy is a feature flag, not a default.
- [ ] **Score migration tooling.** Anyone running a private deployment can run a downstream-safe migration when the algorithm versions.

### v2.0 — Federation
**Beyond 2027 — depends on adoption**

- Multiple independent Trustgate instances cross-attesting scores via signed attestations.
- A canonical score becomes the median (or weighted median) across federation members.
- Each member publishes its own seed list, transparency report, and algorithm version; the federation contract is the *interface*, not the math.

## What we're explicitly **not** building

- **ML-learned weights.** Determinism is a feature. The trust math has to be auditable.
- **GPU inference paths.** Same reason. Also a budget reason.
- **Private-data scoring.** Trustgate uses only public observable data. Email content, DMs, phone records — out of scope forever.
- **Pay-to-improve.** No one buys a higher score. Pro features are about *speed and depth of access*, not about altering the math.
- **Removal-as-a-service.** Adverse actions follow the documented policy. We do not sell delisting.
- **Surveillance tooling.** Trustgate scores public identities for trust decisions. It is not a stalking-aid, and we will reject features whose primary use case is targeted monitoring of private individuals.

## How to help

| If you want to… | Look here |
|------------------|-----------|
| Fix a small bug | `good-first-issue` label |
| Add a platform (Mastodon, Threads, Letterboxd) | `platform-adapter` label, see CONTRIBUTING.md |
| Improve cross-platform identity resolution | `app/services/similarity.py` — recent UIL papers in the whitepaper bibliography |
| Help with the corpus | Open an issue describing what labeled data you have access to |
| Run a private deployment | `docs/SELF_HOSTING.md` (coming with v0.3) |
| Sponsor a maintainer / fund corpus work | See `docs/FUNDING.md` (coming with v0.3) |
| Challenge an algorithm choice | Open a discussion. Bring data. We're listening. |

Updated: 2026-05-10
