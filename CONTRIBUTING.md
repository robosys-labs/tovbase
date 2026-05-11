# Contributing to Trustgate (tovbase)

Trustgate is an open algorithm. We believe the only way "trust score for the internet" works is if anyone can read the code, run the algorithm against a public test corpus, and challenge the numbers. That means contribution rules need to be unambiguous, even when the work is small.

## TL;DR

1. **Find an issue.** Look for `good-first-issue` for new contributors, `algorithm-change` for math, `platform-adapter` for new social platforms, `infra` for service / deployment work. If your idea is bigger than a single issue, open a discussion first.
2. **Branch from `main`.** Name it `<kind>/<short-slug>` — e.g. `fix/timezone-wrap`, `feat/ens-credential`, `docs/governance-clarify`.
3. **Write tests first.** No algorithm change ships without a corpus eval before/after. See *Algorithm Changes* below.
4. **Open a PR** with the template. Two maintainer approvals required for algorithm or seed-list changes; one for tests, docs, or infra.

## Quick local setup

```bash
git clone https://github.com/<org>/tovbase.git
cd tovbase
python -m venv .venv && source .venv/bin/activate    # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"

# Start dependencies (Postgres, Redis, Qdrant)
docker compose up -d

# Run the test suite
python -m pytest tests/ -v

# Run the local API
uvicorn app.main:app --reload --port 8001

# Seed a demo identity
python scripts/seed.py
```

If `python -m pytest tests/` is green, you have a working environment.

## Repository layout

| Path | What lives there |
|------|------------------|
| `app/services/scoring.py` | The 5 base sub-scores + composite |
| `app/services/graph_trust.py` | PPR, Leiden, time-decay (Phase B) |
| `app/services/similarity.py` | Cross-platform identity resolution |
| `app/services/credentials.py` | External credential verifiers |
| `app/api/routes.py` | All HTTP endpoints under `/v1` |
| `seeds/trust_seeds.yaml` | PPR seed list (governance-managed) |
| `tests/` | pytest suite. One file per service module. |
| `corpus/` | Adversarial test corpus (planned; D1) |
| `docs/` | Long-form design and architecture notes |

## Pull request expectations

Every PR description must answer **three questions**:

1. **What is this change?** One sentence.
2. **Why now?** Link to the issue, discussion, or production incident that motivates the change.
3. **What did you verify?** The exact commands you ran and what you observed. For algorithm changes, include the corpus-eval delta (see below).

PRs without these get a polite ask-for-more before review. We try to merge well-described small PRs the same day.

## Algorithm changes — extra rules

Anything that changes the *output* of `compute_trust_score`, `compute_identity_similarity`, `compute_ppr_scores`, or `compute_sybil_suspicions` is an algorithm change. This includes:

- Tweaking weights, thresholds, or scaling constants
- Adding or removing sub-scores
- Changing how an existing sub-score is computed
- Modifying the seed list

Required for these PRs:

1. **Test before & after.** Add or update tests that pin both the old and new behavior. The PR body must include the diff in test outcomes.
2. **Corpus eval.** Run `python scripts/run_corpus.py` (D1, ships with v0.2) and paste the precision / recall / per-tier delta into the PR description.
3. **Justification in the whitepaper section.** If the algorithm doc no longer matches reality, you ship the doc update in the same PR. We never let `ALGORITHM.md` and the code drift.
4. **Two maintainer approvals.** One is not enough — algorithm changes affect every score in the database.

For seed-list changes, see `GOVERNANCE.md`. Seed-list PRs have an additional 14-day public comment window before merge.

## Adding a platform adapter

`app/services/ingestion.py` and `extension/content.js` together define which platforms Trustgate understands. Adding one is a great first contribution.

Required:

1. An ingestion adapter that turns raw scraped data into `IdentityProfile` field values. Mirror an existing adapter (Twitter, GitHub) for shape.
2. A test fixture in `tests/test_ingestion.py` against a real (anonymized) profile dump from the platform.
3. An entry in `extension/manifest.json` content-script matches and a platform-detection branch in `content.js`.
4. Documentation: one paragraph in `docs/PLATFORMS.md` explaining what the adapter can and cannot extract.

Not required (yet): a Playwright scraper. Public APIs or RSS-style feeds are preferred when available — they're cheaper, more reliable, and don't fight rate limits.

## Adding an external credential verifier

`app/services/credentials.py` has the pattern. Each verifier:

- Has a `verify_<name>(...)` function returning `VerificationResult`.
- Raises `CredentialError` on any verification failure (invalid format, expired token, identifier mismatch).
- Persists *only the verification outcome* — never the raw secret. Token fingerprints are OK; raw tokens are not.
- Ships with unit tests that monkeypatch the network call.

When in doubt, smaller bonuses are better: each credential should add a few points, not change the tier. The bonus curve diminishes deliberately (`_credential_bonus(n)` caps at +50).

## Coding conventions

- **Service functions** return either a value or a `(value, detail_dict)` tuple. The dict makes the breakdown auditable in API responses.
- **Schemas** live in `app/schemas.py`. Don't define request/response bodies inline.
- **Routes** live in `app/api/routes.py` under the `/v1` prefix. Long endpoint bodies can move into a service.
- **Tests** use the fixtures in `tests/conftest.py`. Add a fixture before duplicating profile-construction boilerplate.
- **Vectors** are always 32 floats in `[0, 1]`. Use `_clamp()` everywhere.
- **No new long-lived secrets.** OAuth tokens, API keys, and signing material live in env vars or hashed-and-discarded.
- **Lint:** `ruff check app/ tests/`. We're tolerant of legacy warnings, strict on new code.

## Commits and messages

- One logical change per commit. Squash before merge if your PR ended up with messy WIPs.
- Subject line ≤ 50 characters, imperative ("Fix timezone wrap", not "Fixed").
- Body should answer *why*, not *what* — the diff is the *what*.

## Issue triage

`good-first-issue` — Small, well-scoped, no special context needed. New contributors get first dibs.
`help-wanted` — We want this; we don't have time. Open to anyone.
`algorithm-change` — Touches the math. Read this CONTRIBUTING + GOVERNANCE before starting.
`platform-adapter` — Adding a social platform. See above.
`infra` — Service, deployment, CI work.
`security` — Report privately to security@trustgate.io (or whatever the maintainer org address is). Don't open public issues for security holes.

## Code of conduct

We follow the [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). Be kind, assume good faith, give specific feedback. Maintainers will enforce this — privately when possible, publicly when necessary.

## Questions

Open a Discussion on GitHub if you want to talk through an idea before coding. For sensitive topics (security, governance), email the maintainers directly.

Welcome aboard.
