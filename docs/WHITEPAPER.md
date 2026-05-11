# Trustgate: A Deterministic Trust Graph for Public Online Identities

**Whitepaper v1 — May 2026**

> "There is no FICO of the internet."

## Abstract

We describe Trustgate, an open-source system that computes a deterministic trust score (0–1000) for any public online identity — a person, an organization, or an autonomous AI agent — from observable behavior across multiple platforms. The score is the composition of six explicit sub-scores: five that describe an identity in isolation (existence, behavioral consistency, engagement quality, cross-platform coherence, reputational maturity) and one that captures the identity's standing in a trust graph (Personalized PageRank from a hand-curated, governance-managed seed set). All inputs are public; no inputs are machine-learned; no part of the pipeline requires a GPU. The architecture runs at $135–370/mo for a population in the low millions, and every score response includes the algorithm version that produced it, the seed-list version, and a permanent audit URL. Trustgate's adversarial-robustness story rests on three composable defenses: Sybil-resistant PPR with seed-mass leakage, Leiden community detection for ring demotion, and multi-signal corroboration of audience-size claims. We argue this design is necessary precisely because the alternative — opaque, ML-driven, single-platform reputation systems — cannot be cross-checked by the people they score.

## 1. Why this exists

Three things have become simultaneously true in 2026.

**Trust online has eroded.** Bot farms, AI-generated content, deepfakes, and coordinated inauthentic behavior have raised the cost of every micro-decision that depends on "is the person on the other end of this profile real, durable, and acting in good faith?" Recruiters, founders, freelancers, investors, and increasingly AI agents acting on behalf of humans face this decision dozens of times per day. None of the existing primitives address it.

**The primitives don't compose.** Credit bureaus score financial behavior in narrow jurisdictions. People-search aggregators sell who-someone-is but not whether they're trustworthy. Review platforms are easily gamed and slow. Web3 identity systems (ENS, Bluesky, World ID) solve fragments — does this wallet exist, does this DID resolve, is this a unique human — but not "should I trust this person *based on their behavior*." Reputation systems inside individual platforms (LinkedIn endorsements, GitHub stars, X verified) work *only* on that platform.

**The signals are now legible.** Behavioral fingerprints — chronotype, voice, social posture, topical interest, presence patterns — are extractable from public data without ML models. Cross-platform identity resolution at scale, an open research problem five years ago, is solvable today with multi-signal evidence at ~95% precision-recall. Graph algorithms scale to billions of edges on commodity hardware.

Trustgate is the synthesis of those three observations: build the unified trust score the internet should have had a decade ago, build it on math anyone can audit, ship it under an open license with public governance.

## 2. Prior art

Trustgate's algorithm draws from a long literature on reputation in distributed systems. We summarize the relevant work and where we depart from it.

**PageRank and EigenTrust.** The two canonical recursive-reputation algorithms (Brin & Page 1998; Kamvar et al. 2003). Both compute equilibrium probability mass on a random walk over a directed graph. EigenTrust is famously *not* Sybil-resistant absent a strong pre-trusted seed (Berkeley EECS-2007-75; Jansen 2008). OpenRank operationalizes EigenTrust on Farcaster and Lens at production scale (OpenRank, 2024). We use Personalized PageRank — mathematically equivalent to EigenTrust under a relabeling — because the personalization-vector formulation makes the Sybil-resistance argument explicit: trust mass leaks back to seeds every iteration, so Sybil subgraphs cannot accumulate mass without exporting it.

**Sybil defenses on social graphs.** SybilGuard (Yu et al. 2006), SybilLimit (Yu et al. 2008), SybilRank (Cao et al. NSDI 2012), SybilSCAR (Wang et al. 2018). All rely on the empirical observation that real social graphs are fast-mixing in their honest region but slow to mix across the honest-Sybil cut. Modern variants (SybilFlyover 2022, SybilSAN AAMAS 2025) layer GNN features on top. We deploy a simpler defense — Leiden community detection (Traag et al. Nature 2019) over the same edge set used for PPR — flagging communities whose member metadata is suspiciously homogeneous. This is the technique platform safety teams use to catch coordinated farms; it is interpretable, cheap on commodity hardware, and composes with PPR rather than competing.

**Cross-platform user identification.** The 2024 UIL survey (Yu et al. arXiv:2409.08966) enumerates three approach families: feature-based, embedding-based, GNN/transformer. SOTA GNN methods (TransLink, GSMUA) edge out tuned feature methods by 1–2% AUC at the cost of labeled training pairs. For a small team without a labeled training set, the explicit multi-signal scoring approach (vector cosine 35% + voice 25% + chronotype 20% + name 15% + topic 5%) is competitive, explainable, and the right starting point. Time-decay on edges (Wang et al. 2022) provides a free accuracy boost we adopt.

**Decentralized identity.** W3C DID Core, ATProto's `did:plc`, ENS, Worldcoin. As infrastructure, these are real and increasingly useful: 40M+ DIDs exist by 2026. As *signal*, they're each one bit. Trustgate treats DIDs as one credential type among several (composable Passport pattern), not as the trust source.

**Commercial analogs.** Pipl, Spokeo, BeenVerified, Maltego, Hunter, Apollo. These are data aggregators — they answer *who* — not trust scorers. Clearview AI's surveillance application is legally radioactive and ethically distinct from what we build. The closest live trust-scorer in 2026 is Gitcoin Passport (composable-credential pattern in Web3) — useful but Web3-only.

**Open-source launch templates.** Sigstore (key ceremony + multi-vendor backing + public-good non-profit), Let's Encrypt (free service + transparent governance + ACME standard). Both teach the same lesson: credibility comes from boring, public, auditable process. We follow that template (see `GOVERNANCE.md`).

## 3. The algorithm

### 3.1 Sub-scores

Each sub-score is in [0, 200] and is computed deterministically from the profile fields and observed behavior.

**Existence (0–200)** — How real and established is this identity?

```
existence = 200 × clamp[
    0.25 · log₁(account_age_days, 1825)
  + 0.20 · profile_completeness
  + 0.20 · clamp(num_platforms / 4)
  + 0.15 · log₁(observation_count, 50)
  + 0.10 · is_verified
  + 0.10 · audience_factor × corroboration
]
```

Where `log₁(x, cap) = log(1 + x) / log(1 + cap)` and `corroboration ∈ {0.5, 1.0}` halves the audience contribution unless at least one of {is_verified, observation_count ≥ 5, linked_platforms ≥ 1} is true. The corroboration term is the audience-gaming defense; raw follower counts on platforms with cheap follower markets are not by themselves evidence of established identity.

**Consistency (0–200)** — How stable is behavior across time?

```
consistency = 200 × Σᵢ wᵢ · (
    0.30 · regularity_score
  + 0.25 · (1 − emotional_volatility / 0.5)
  + 0.25 · active_weeks_ratio
  + 0.20 · (1 − post_rate_variance / post_rate)
)
```

with weights wᵢ proportional to per-platform observation count. Bots, sock-puppets, and inactive accounts all surface here.

**Engagement (0–200)** — Are interactions organic?

```
engagement = 200 × Σᵢ wᵢ · (
    0.30 · engagement_depth
  + 0.25 · reciprocity
  + 0.25 · growth_organicity
  + 0.20 · mention_response_rate
)
```

The four terms together separate "real human interacting with other real humans" from "broadcast-only bot."

**Cross-platform (0–200)** — How coherent is the identity across platforms?

For multi-platform identities (n ≥ 2), with vectors v computed locally if not cached:

```
cross_platform = 200 × (
    0.50 · mean_pairwise_cosine(vᵢ, vⱼ)
  + 0.30 · clamp(n / 3)
  + 0.20 · mean_pairwise_name_similarity
)
```

For single-platform identities, `max(SINGLE_PLATFORM_FLOOR=30, 200·0.30·clamp(n/3))`. The named floor prevents legitimately single-platform profiles (specialists who only use GitHub or Mastodon, say) from being pushed below scores they earn elsewhere.

**Maturity (0–200)** — How deep and clean is the track record?

```
maturity = 200 × clamp[
    0.25 · log₁(platform_tenure, 730)
  + 0.20 · log₁(total_posts, 500)
  + 0.20 · authority_index
  + 0.20 · (1 − anomaly_count / observations)
  + 0.15 · audience_factor × corroboration
]
```

**Network Trust (0–200)** — Personalized PageRank standing.

Given an interaction graph G = (V, E) where V is the set of canonical identities, E is the set of mention/reply/co-occurrence edges, edge weight w_{u,v} = log(1 + count) · exp(−Δdays · ln2 / 365), and a seed set S ⊂ V:

```
PPR(v) = (1 − α) · 𝟙[v ∈ S] / |S| + α · Σ_{u → v} w_{u,v} · PPR(u) / Σ_{w} w_{u,w}
```

with α = 0.85 (standard PageRank damping). The raw PPR mass is log-normalized against a [10⁻⁷, 10⁻³] interval and scaled to [0, 200].

### 3.2 Composite score

```
network_boost   = 1 + 0.10 · (network_trust / 200)
sybil_factor    = 1 − 0.5 · sybil_suspicion
dampening_floor = piecewise_observation_floor (0.33, 0.55, 0.80, 1.0)
credential_bonus = 50 · (1 − exp(−n_credentials / 2.5))     # capped at 50

raw_total = existence + consistency + engagement + cross_platform + maturity

final = clamp(0, 1000,
    raw_total × dampening_floor × network_boost × sybil_factor
  + credential_bonus
)
```

Three things to notice about this composition.

**Network trust is a bonus, not a base.** When the trust graph has not yet been computed for an identity (Phase B-1 first-deploy state), `network_trust = 0` and `network_boost = 1`, so the formula collapses to the v1.1 5-sub-score baseline. This preserves backward compatibility — existing seed scores do not shift the moment v1.2 ships.

**Sybil suspicion demotes multiplicatively.** A community flagged by Leiden as a likely Sybil ring multiplies the entire score by up to 0.5. The penalty is large because the alarm condition is narrow (homogeneous metadata across ≥3 members).

**Credentials are additive and bounded.** A user with a verified GitHub + Bluesky + ENS gets +43 points — enough to lift a borderline-Fair into Good but not enough to turn an Untrusted profile Trusted. No single credential is dispositive.

### 3.3 Confidence dampening

For identities with few observations, the algorithm's confidence is low. Rather than emit a score with no caveat, we multiply by a floor:

```
total_obs < 5  → 0.33
total_obs < 15 → 0.55
total_obs < 30 → 0.80
total_obs ≥ 30 → 1.00
```

A large audience can raise the floor by one step *if and only if* corroborated by verification, observations, or linked platforms — same anti-gaming gate as in Existence/Maturity.

### 3.4 Tiers

| Score | Tier | Color |
|-------|------|-------|
| 850–1000 | Excellent | green |
| 700–849 | Good | green |
| 550–699 | Fair | orange |
| 350–549 | Poor | red |
| 0–349 | Untrusted | red |

Tier boundaries are calibrated against the OSS adversarial corpus (Phase D1). Boundary changes follow the algorithm-change governance process.

## 4. Adversarial properties

### 4.1 Sybil resistance via seed-mass leakage

The standard EigenTrust failure mode is that a sufficiently dense Sybil subgraph accumulates trust mass faster than honest nodes endorse it. PPR with a personalization vector concentrated on a hand-curated seed set defeats this in the following sense: at every iteration, mass `(1−α) = 0.15` *leaves* the random walk and re-enters at the seeds. A Sybil subgraph that does not contain a seed cannot retain mass — even if internally dense, it bleeds 15% per iteration to seeds. Mass reaching the Sybils only via edges *from* the honest region, and the honest-to-Sybil cut is by hypothesis narrow.

We do not claim this is *sufficient* Sybil resistance. It is necessary; layered with Leiden community demotion (§4.2) and corroboration-gated audience scoring (§3.1), it is the practical line of defense.

### 4.2 Sybil-ring detection via Leiden

Sybil rings — coordinated networks of fake accounts — typically share metadata: created within the same week, similar account-age distribution, mutual-only follow graphs. We run Leiden community detection (resolution=1.0) nightly on the same edge set used for PPR. For each community of ≥3 members, we compute homogeneity along two axes:

```
homogeneity = 0.5 · (1 − norm_std(account_ages, 180_days))
            + 0.5 · (1 − norm_std(join_weeks, 8_weeks))
```

Higher → more suspicious. A community of 50 accounts all created within the same week of each other will score near 1.0; a community of organic followers spanning years will score near 0.

`sybil_suspicion` directly multiplies the final score by `(1 − 0.5·suspicion)`. Maximum demotion is 50%.

The trade-off with this defense: it has nonzero false-positive rate (e.g. an authentic conference cohort joining a platform together). The conservative mitigation is the 0.5x cap on demotion (no community gets pushed all the way to Untrusted by Sybil-suspicion alone) plus a public appeal path (`docs/ADVERSE_ACTIONS.md`).

### 4.3 Audience-gaming defense

Audience-size signals are gameable: cheap follower markets exist on every major platform. Without a defense, a 0-observation profile with 1M purchased followers would get a free boost on Existence and Maturity.

Our defense is **corroboration**: audience contributes 50% of its raw weight unless at least one independent signal exists (verified flag, observation_count ≥ 5, or a linked external credential). The audience-based dampening floor lift also requires corroboration. This means a bot account with no observations and no credentials cannot escape the 0.33 dampening floor regardless of follower count.

### 4.4 Vector poisoning bounded by multi-signal agreement

An attacker who controls a profile can manipulate the 32-dim behavioral vector through posting patterns. But vector similarity is one of five signals in identity resolution (35% weight) and one of three terms in cross-platform sub-score (50% weight within that sub-score, which itself is 20% of the composite). An attack on the vector alone moves the composite by at most ~7% — Wei Zhang's attack budget is large enough to matter but not large enough to flip tiers.

### 4.5 Determinism as a robustness property

Trustgate runs no ML at the scoring layer. This is by design. Prompt injection attacks on LLM-based reputation classifiers (OWASP LLM01:2025) and adversarial examples for GNN-based reputation models are active research problems with no general defense. Trustgate is immune to those classes of attacks because the algorithm contains no learned weights and no LLM evaluation. The cost is that we cannot pick up subtle patterns an ML model might; the benefit is that the algorithm is, in fact, the algorithm we publish.

## 5. Implementation

### 5.1 Architecture

```
                                ┌─────────────────────┐
                                │  PostgreSQL         │
                                │  - canonical_id     │
                                │  - identity_profile │
                                │  - identity_link    │
                                │  - interaction_edge │
                                │  - external_cred    │
                                └────────┬────────────┘
                                         │
   ┌───────────────┐   ┌──────────────┐  │   ┌────────────────┐
   │ Chrome ext    │──▶│ FastAPI      │──┼──▶│ Qdrant (32-dim │
   │ MV3, ≤5KB     │   │ /v1 API      │  │   │ HNSW vectors)  │
   │ ambient score │   │ port 8001    │  │   └────────────────┘
   └───────────────┘   └──────────────┘  │
                              ▲          │   ┌────────────────┐
   ┌───────────────┐          │          ├──▶│ Redis (cache + │
   │ Next.js site  │──────────┘          │   │ rate limiting) │
   │ port 3002     │                     │   └────────────────┘
   │ report pages  │                     │
   └───────────────┘                     │   ┌────────────────┐
                                         ├──▶│ Celery workers │
                                         │   │ PPR weekly     │
                                         │   │ Leiden nightly │
                                         │   │ scrape/enrich  │
                                         │   └────────────────┘
```

No GPU instances. No graph database. The trust graph lives in Postgres rows; PPR and Leiden run in-memory on the Celery worker via `networkx` / `python-igraph`. The 32-dim behavioral vectors live in Qdrant (HNSW indexing for billion-scale similarity search).

### 5.2 Cost envelope

| Component | Hosting | Monthly cost |
|-----------|---------|--------------|
| API + Celery (4 vCPU, 8GB RAM) | DigitalOcean / Fly.io | $48–96 |
| Postgres 16 (managed, 4GB RAM) | Same provider | $32–60 |
| Redis 7 (managed, 2GB RAM) | Same provider | $20–40 |
| Qdrant (1 vCPU, 4GB RAM) | Self-hosted | $24–48 |
| Object storage (raw observations) | R2 / S3 | $5–20 |
| DNS + cert | Cloudflare | $0–10 |
| Monitoring | Grafana Cloud free | $0 |
| **Total** | | **$135–370/mo** |

This is achievable because of the deterministic-math non-negotiable. A single GPU instance would more than double the bill.

### 5.3 Performance

| Operation | Latency | Notes |
|-----------|---------|-------|
| `GET /v1/score/{platform}/{handle}` (cached) | < 100 ms | Redis hit |
| `GET /v1/score/{platform}/{handle}` (cold) | 200–600 ms | Compute + persist |
| `POST /v1/profile/observe` | 50–150 ms | DB write + vector upsert |
| `POST /v1/report/generate` | 2–6 s | Includes Qdrant search + summary |
| PPR batch (1M nodes, 15M edges) | 4–8 min | Weekly Celery job |
| Leiden batch (same scale) | 2–5 min | Nightly Celery job |

### 5.4 Algorithm version pinning

Every score response carries `algorithm_version`. We follow semver:

- **Patch** (1.2.0 → 1.2.1): bug fix that changes output but not the documented formula.
- **Minor** (1.2 → 1.3): new sub-score, new verifier, new edge type.
- **Major** (1.x → 2.0): incompatible change. 90-day notice + public migration guide.

The permanent score-audit URL (`trustgate.io/score/{canonical_id}/v/{version}`) returns the exact inputs and computation behind a specific score, for any version we've ever shipped. This is the public audit log.

## 6. Empirical evaluation

*(This section will be populated in v0.3 once the public adversarial corpus ships. Draft placeholder.)*

We are building a public adversarial test corpus:

- **1000 known-good profiles** — public figures with documented track records, labeled with target score ranges.
- **1000 known-bad profiles** — disclosed bot accounts, deplatformed scammers, Sybil rings from journalism investigations, labeled as Untrusted.
- **200 edge cases** — new but legitimate accounts, dormant historical accounts, claim/real-name mismatches.

`scripts/run_corpus.py` will reproduce the published precision/recall numbers. Algorithm changes must report the delta against this corpus in the PR description.

Targets for v0.3:
- **Tier-Untrusted recall on labeled-bad set: ≥ 95%**
- **Tier-Excellent precision on labeled-good set: ≥ 90%**
- **Cross-platform identity resolution F1 on labeled pairs: ≥ 0.92**
- **Sybil-ring detection: ≥ 95% recall at < 1% false-positive on a synthetic-but-plausible cohort**

## 7. Open problems

**Agent-to-agent trust delegation.** When agent A delegates a task to agent B, does B inherit A's trust standing? Should B's score be a function of A's? The NANDA/AgentFacts work (MIT 2025) gives us a cryptographic identity for agents but does not yet propose a propagation model. We claim no answer here; the schema is ready (`canonical_identity.agent_kind`, `agent_passport_did`) when the standards stabilize.

**Multilingual voice fingerprinting.** The voice features in `app/services/ingestion.py` assume English-centric tokens (question ratios, formality cues). Non-English speakers may underscore on Voice. We need parameterized extractors per language with documented coverage.

**Coordinated authentic behavior.** Genuine communities (conference cohorts, fandoms, professional associations) often look superficially like Sybil rings: created together, similar tenure, mutual follows. Our homogeneity score's 50% demotion cap and public appeal process are partial mitigations; a better solution is welcome.

**Cross-cultural seed selection.** The current seed list (`seeds/trust_seeds.yaml`) is heavily English-language and tech-industry-skewed. A globally credible algorithm needs seeds across cultures, languages, and professional domains. Contributions welcome via the governance-managed PR process.

**Adversarial corpus completeness.** The corpus described in §6 is unavoidably partial. We expect adversarial researchers to find profiles where the algorithm misclassifies; we commit to publishing those findings and the resulting algorithm updates.

## 8. Conclusion

Trust on the internet is a coordination problem, and like other coordination problems, it benefits from a public, auditable schelling point rather than a proliferation of private opinions. We're not the first to argue this — credit bureaus made the analogous argument for lending in the 1950s. But credit bureaus closed: opaque math, regulatory capture, private records. Trustgate aims to demonstrate that the score-everyone-on-public-behavior idea works *better* when the math is open, the seed list is contestable, and the failure modes are documented.

The algorithm in this paper is the algorithm in the repository. If you want to challenge it, the code is here; the tests are here; the governance process is here. That is the bargain.

## Bibliography

- Brin, S., & Page, L. (1998). *The anatomy of a large-scale hypertextual web search engine.*
- Kamvar, S. D., Schlosser, M. T., & Garcia-Molina, H. (2003). *The EigenTrust algorithm for reputation management in P2P networks.* WWW 2003.
- Cheng, A., & Friedman, E. (2007). *EigenTrust under sybil attack.* Berkeley EECS-2007-75.
- Jansen, R. (2008). *Vulnerabilities to a priori trust in computer-mediated networks.*
- Yu, H., Kaminsky, M., Gibbons, P. B., & Flaxman, A. (2006). *SybilGuard: defending against sybil attacks via social networks.* SIGCOMM.
- Cao, Q., Sirivianos, M., Yang, X., & Pregueiro, T. (2012). *Aiding the detection of fake accounts in large-scale social online services.* NSDI.
- Wang, B., Zhang, L., & Gong, N. Z. (2018). *SybilSCAR: sybil detection in online social networks via local rule based propagation.*
- Traag, V. A., Waltman, L., & van Eck, N. J. (2019). *From Louvain to Leiden: guaranteeing well-connected communities.* Nature 9:5233.
- Yu, S. et al. (2024). *User identity linkage across online social networks: a survey.* arXiv:2409.08966.
- Wang, J. et al. (2022). *Time-decay enhanced user identification linkage.* PMC9689741.
- MIT NANDA Project. (2025). *NANDA Index: DNS for autonomous agents.* arXiv:2507.14263.
- Sigstore community. (2023). *Governance and contribution lessons.* liatrio.com.
- OpenRank Labs. (2024). *EigenTrust reputation algorithm documentation.*
- W3C. (2024). *Decentralized identifiers (DIDs) v1.0.*
- ATProto / Bluesky. (2024–2026). *did:plc method specification.*

---

*Trustgate is open source under the MIT license. Source: https://github.com/<org>/tovbase. Issues, discussions, and pull requests are open to anyone.*
