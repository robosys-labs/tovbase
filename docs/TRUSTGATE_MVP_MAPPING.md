# TrustGate MVP — what's built vs. what's needed

This document maps the current `tovbase` codebase to the TrustGate MVP scope
defined in **TrustGate_Strategic_Direction.docx** and **TrustGate_MVP_Investor_Proposal.pdf**. It identifies which MVP features already exist as reusable modules, which need extension, and which need to be built from scratch.

The verdict, before the detail: **~60–70% of the platform-layer infrastructure is already in `tovbase`.** The missing pieces cluster in three areas — (1) business-specific risk data sources, (2) transaction-routing + financial accounting, (3) merchant-facing UX. Together, these are ~12 weeks of focused product work, not another whole platform.

---

## 1. The TrustGate MVP — the 6 features

Per the Strategic Direction doc §3:

| # | Feature | One-line definition |
|---|---------|---------------------|
| F1 | **Business Reputation Scoring** | Management risk + business risk score before any payment |
| F2 | **Dynamic Revenue Caps** | Monthly transaction limit tied to risk score; lifts with verified track record |
| F3 | **Unified Global Checkout** | One payment link / API; TrustGate routes through licensed EMI rails |
| F4 | **Real-time Limit Engine** | Per-transaction cap check before approving the payment |
| F5 | **Business Registry (Beta)** | KYB API serving banks/underwriters who need business risk data |
| F6 | **Merchant Dashboard** | Transaction history, current cap + utilisation, score breakdown |

Plus the underlying revenue + protection model from Investor Proposal §2–3:

- **Approve/reject/tier decision** before any payment rail is touched
- **Per-transaction limit engine** governing max volume in real time
- **Fraud reserve pool** (0.5% per txn, 90-day rolling escrow)
- **Fraud indemnity insurance** (Lloyd's-syndicate-class policy)
- **EMI partner contracts** with capped liability above defined monthly volume
- **Registry API** as a separate B2B product to banks

---

## 2. What `tovbase` already provides

### 2.1 Scoring engine — directly reusable for F1

| MVP requirement | Existing module | Notes |
|-----------------|-----------------|-------|
| Composite risk score 0-1000 | [`app/services/scoring.py:compute_trust_score`](../app/services/scoring.py) | 6 sub-scores + modifiers; deterministic, auditable, versioned |
| Tier classification (Excellent/Good/Fair/Poor/Untrusted) | `score_to_tier()` + `ScoreTier` enum | Reusable directly for approve/reject/tier decisions |
| Per-tenant tunable weights | [`app/services/config_management.py`](../app/services/config_management.py) + `ScoringConstants` | Already supports per-tenant scoring weights with hot reload |
| Algorithm version pinning | `ScoreBreakdown.algorithm_version` + `score_version` column | Required for audit + regulatory traceability |
| **Founder background scoring** | `compute_trust_score(profiles=...)` over IdentityProfile rows | Person-level scoring is feature-complete |
| **Cross-platform identity resolution** | [`app/services/similarity.py`](../app/services/similarity.py) | Founders' real identity across LinkedIn / X / GitHub / etc. |
| **Digital footprint analysis** | [`app/services/serp.py`](../app/services/serp.py) + [`app/services/deep_enrichment.py`](../app/services/deep_enrichment.py) | SERP fingerprint, Wikidata, Crunchbase, rel="me" |
| Network-trust propagation (PPR) | [`app/services/graph_trust.py`](../app/services/graph_trust.py) | Maps "founders endorse / co-found with other founders" → trust propagation |
| Sybil-ring detection (Leiden) | `compute_sybil_suspicions()` | Catches coordinated fake-merchant rings |
| Adversarial robustness | [`scripts/audit_robustness.py`](../scripts/audit_robustness.py) | 6/6 attack shapes scored correctly Untrusted |

### 2.2 Company scoring — needs extension for F1's *business risk* axis

| MVP axis | Existing module | Status |
|----------|-----------------|--------|
| Founder credibility | [`app/services/company_scoring.py:_score_founder`](../app/services/company_scoring.py) | ✅ Built; uses founder IdentityProfile.trust_score |
| Product signal (GitHub repos / health) | `_score_product` | ✅ Built; relevant for SaaS/tech businesses, less so for service firms |
| Community signal (brand sentiment) | `_score_community` | ✅ Built; needs richer sentiment ingestion |
| Presence signal (multi-platform consistency) | `_score_presence` | ✅ Built |
| Execution signal (YC, funding, releases) | `_score_execution` | ✅ Built |
| Consistency signal (claims vs behaviour) | `_score_consistency` | ✅ Built |
| **Sector risk** (gambling/crypto/adult = high) | — | ❌ MISSING — needs sector → baseline-risk mapping |
| **Jurisdiction risk** (per-country fraud baseline) | — | ❌ MISSING — country-level risk LUT |
| **Revenue signals** (bank statements, processor history) | — | ❌ MISSING — needs file-upload + OCR / API ingestion |
| **Business-registration verification** (GLEIF, CAC, RGD, BRS) | — | ❌ MISSING — adapter layer per registry |
| **Founder PEP / sanctions screening** | — | ❌ MISSING — OFAC / UK HMT / EU list adapters |
| **Domain WHOIS + SSL + age** | `app/services/link_analysis.py` (staged) | ⚠️ Partial — staged but not wired |
| **Court / litigation history** | — | ❌ MISSING — needs PACER (US) / local court-records adapters |

### 2.3 Data + API surface — directly reusable

| MVP requirement | Existing | Notes |
|-----------------|----------|-------|
| Canonical identity / entity model | `CanonicalIdentity` + `CompanyProfile` + `IdentityProfile` + `IdentityLink` | Schema accommodates persons, companies, agents |
| Forward-compatible agent identity | `CanonicalIdentity.agent_kind` ∈ {human, organization, agent} | TrustGate's future "AI agent commerce" line items |
| Audit URL for every score | [`/v1/score/audit/{canonical_id}`](../app/api/routes.py) | Whitepaper-grade auditability for regulators |
| Embeddable score badges | [`app/services/badge.py`](../app/services/badge.py) + `/v1/badge/{platform}/{handle}.svg` | TrustGate-branded merchant trust badges |
| Iframe embed | [`/v1/embed/{platform}/{handle}.html`](../app/api/routes.py) | Drop-into-checkout-page widget |
| OG link preview card | `og_card_svg()` 1200x630 | Sharable score snapshots |
| Rate limiting (Redis) | `app/middleware/rate_limit.py` | Per-endpoint, per-tenant limits |
| Worker queue (Celery) | `app/workers.py` | Already runs PPR / Leiden / scrape / refresh jobs |
| Cache (Redis) | `app/services/cache.py` | Hot-path 100ms responses |

### 2.4 OSS launch infrastructure — directly reusable

| Need | Existing |
|------|----------|
| Algorithm whitepaper | [`docs/WHITEPAPER.md`](WHITEPAPER.md) — covers determinism, Sybil-resistance, audit model |
| Contributor governance | [`CONTRIBUTING.md`](../CONTRIBUTING.md), [`GOVERNANCE.md`](../GOVERNANCE.md) |
| Adversarial corpus | [`corpus/README.md`](../corpus/README.md), [`scripts/run_corpus.py`](../scripts/run_corpus.py) |
| Schema migration | [`scripts/migrate_v12.py`](../scripts/migrate_v12.py) (idempotent ALTER TABLE) |
| Versioned scoring config | `scoring_weights` table + `ConfigManagementService` |
| External credentials (GitHub OAuth, Bluesky did:plc, ENS) | [`app/services/credentials.py`](../app/services/credentials.py) |

---

## 3. What's missing — concrete build list

### Group A — Business risk data sources (the *business risk* half of F1)

| # | Module to build | Effort | Dependency |
|---|-----------------|--------|------------|
| A1 | `app/services/risk_sector.py` — sector → baseline-risk LUT (gambling, crypto, adult, healthcare = high; SaaS, services, education = low) | 1 week | Author the LUT; ~50 sectors covered |
| A2 | `app/services/risk_jurisdiction.py` — country → baseline-risk LUT (FATF grey-list, Transparency Intl CPI, World Bank governance) | 1 week | Public data sources |
| A3 | `app/services/registry_verify.py` — adapters for GLEIF, NG CAC, GH RGD, KE BRS | 2–3 weeks | Each has a different API / web scrape |
| A4 | `app/services/sanctions_check.py` — OFAC SDN, UK HMT, EU consolidated list lookup | 1 week | XML/CSV feeds, daily refresh |
| A5 | `app/services/revenue_signals.py` — bank-statement OCR (Plaid-equivalent for EM markets, or manual PDF upload with table extract) | 2 weeks | OCR engine choice |
| A6 | Wire A1–A5 into a new `_score_business_risk()` in `company_scoring.py` returning a 0-200 sub-score | 1 week | Depends on A1–A5 |
| A7 | Extend [`scripts/audit_robustness.py`](../scripts/audit_robustness.py) with business-side adversarial cases (sanctioned founder, sector mismatch, fake registry entry) | 1 week | — |

**Total Group A: ~9–11 weeks of focused work.** Many tasks parallelizable.

### Group B — Transaction-level features (F2, F4, fraud reserve)

| # | Module to build | Effort | Dependency |
|---|-----------------|--------|------------|
| B1 | `app/models.py` additions — `MerchantAccount`, `Transaction`, `Chargeback`, `EscrowEntry`, `MonthlyCapUsage` tables | 1 week | Schema design |
| B2 | `app/services/cap_engine.py` — `compute_monthly_cap(score, tier, tenure_days)` + `check_cap(merchant, amount)` | 1 week | Depends on B1 |
| B3 | `POST /v1/payments/check_cap` and `POST /v1/payments/route` endpoints | 1 week | — |
| B4 | `app/services/emi_adapters/` — Railsr, Nium, dLocal adapter classes (auth, txn submit, status webhook) | 3–4 weeks per adapter (1 first, 1 week each for follow-ups) | EMI partner sandboxes |
| B5 | `app/workers.py` additions — `reconcile_emi_status_task`, `release_escrow_after_window_task` | 1 week | Depends on B4 |
| B6 | Feedback loop — chargebacks recorded against merchant → trigger `refresh_score_task` with negative signal | 1 week | Depends on B1, B5 |
| B7 | Fraud-reserve ledger reports + dashboard | 1 week | Depends on B1 |

**Total Group B: ~8–10 weeks.** EMI adapter work dominates; sandbox access is the gating dependency.

### Group C — Merchant-facing + Bank-facing UX (F3, F5, F6)

| # | Module to build | Effort | Dependency |
|---|-----------------|--------|------------|
| C1 | Onboarding portal — extend `web/app/onboard/` (multi-step KYB form, document upload, identity-verify integration via Persona / Veriff) | 3 weeks | Identity-verify vendor choice |
| C2 | Merchant dashboard — extend `web/app/dashboard/` (txn history, cap utilisation, score breakdown, request-cap-increase) | 2 weeks | Depends on B1 |
| C3 | Single payment link generator — `web/app/p/{merchant_slug}` + signed JWT for amount/expiry | 1 week | — |
| C4 | Bank-side KYB portal — `web/app/kyb/` for institutional access (subscription tier display, API key issuance, usage analytics) | 2 weeks | — |
| C5 | `GET /v1/kyb/{business_canonical_id}` endpoint — auth-gated, tenant-scoped, rate-limited | 1 week | Reuse existing tenant infra in `config_management.py` |
| C6 | "Powered by Trustgate" checkout widget — `web/components/CheckoutBadge.tsx` consuming `/v1/badge` | 0.5 week | Badge service already built ✅ |

**Total Group C: ~9–10 weeks.** Mostly Next.js frontend work.

### Group D — Compliance + Risk infra

| # | Module to build | Effort | Dependency |
|---|-----------------|--------|------------|
| D1 | Fraud-indemnity insurance integration — contract with Lloyd's-class underwriter, claim-filing workflow | 4–8 weeks (legal + procurement, not code) | External |
| D2 | Regulatory pre-engagement — NG/UK/SG informal letters with regulators | 4–8 weeks (legal) | External |
| D3 | Audit-log export — every score + decision exportable to CSV/JSON for compliance audit | 1 week | Reuse `/v1/score/audit` |
| D4 | Disclosure / TOS / Privacy Policy for merchant + bank tiers | 2 weeks (legal) | — |

**Total Group D:** mostly external; not engineering-bound.

---

## 4. Recommended 12-week MVP sprint plan

Sequenced so engineering does NOT block on partnership signoff. The first 4 weeks deliver a usable demo to take to EMI partners; partnerships and insurance happen in parallel with deeper engineering.

### Weeks 1–4 — Demo-ready core
- **A1 + A2 + A4**: sector + jurisdiction LUTs, sanctions check. Quickest signals to wire.
- **A6**: combined business risk sub-score landing in `company_scoring.py`.
- **B1 + B2**: merchant + transaction + cap tables + cap engine.
- **C5 + C6**: KYB API endpoint + TrustGate checkout badge.
- **Outcome**: a working `POST /v1/business/score → tier + monthly_cap`. Partner deck demo runs end-to-end.

### Weeks 5–8 — Pilot infrastructure
- **A3**: business-registration adapters (start with NG CAC, the founder's home market).
- **B3 + B4**: payment routing endpoint + first EMI adapter (Railsr or Nium per investor pitch).
- **C1 + C2**: onboarding portal + merchant dashboard.
- **Outcome**: 5–10 pilot merchants onboarded end-to-end through TrustGate → EMI sandbox.

### Weeks 9–12 — Production-ready
- **A5**: revenue-signal ingestion (manual PDF upload + table extract suffices for v1).
- **B5 + B6 + B7**: reconciliation worker + chargeback feedback loop + escrow accounting.
- **B4 second adapter**: dLocal for EM corridor coverage.
- **C3 + C4**: payment links + bank KYB portal.
- **D3**: audit-log export.
- **Outcome**: live MVP processing real transactions for the pilot cohort; bank KYB API in closed beta.

External work (D1 + D2 + D4) runs in parallel: 12–16 weeks legal + procurement, but does not block engineering.

---

## 5. Existing engine maps to TrustGate's three success outcomes

The Strategic Direction defines three outcomes that define success. Map of what `tovbase` *already* delivers against each:

### Outcome 1 — "Any legitimate business can collect global payments through one verified account"

| Required capability | What `tovbase` has | What's missing |
|---------------------|---------------------|----------------|
| One-time business verification | ✅ `CompanyProfile` schema + `compute_company_score` | Document upload + sanctions check (A4, A5) |
| Approval decision before payment | ✅ `score_to_tier` returns approve / review / reject signal | Wrap in `POST /v1/business/decide` endpoint (1 day) |
| Unified payment account | — | EMI integration (B4) |

### Outcome 2 — "Trust is earned, not assumed; limits anchored to score, lift with track record"

| Required capability | What `tovbase` has | What's missing |
|---------------------|---------------------|----------------|
| Live, queryable score | ✅ `GET /v1/score/{platform}/{handle}` | Generalize to `/v1/business/score/{canonical_id}` (4 hours) |
| Score updates on observed behaviour | ✅ `refresh_score_task` runs on observation | Chargeback → score-down feedback (B6) |
| Tier-driven monthly cap | — | Cap engine (B2) |
| Auto-lift over time | ✅ Existing score increases as observation_count grows + dampening lifts | Wire `cap_engine.compute_monthly_cap` to read both score AND tenure |

### Outcome 3 — "Data compounds; registry becomes an independent B2B product"

| Required capability | What `tovbase` has | What's missing |
|---------------------|---------------------|----------------|
| Every business indexed | ✅ `CompanyProfile` is the registry table | Bulk-ingest tooling for first 1M businesses |
| Per-business risk + quality score | ✅ Score + breakdown JSON | — |
| API-accessible | ✅ `/v1/company/score/{platform}/{handle}` already exists | Tenant-gated bank access (C5) |
| Webhook on score change | ✅ `refresh_score_task` triggers cache invalidate | Add explicit `webhook_url` per tenant + delivery worker (1 week) |
| Audit log per business | ✅ `/v1/score/audit/{canonical_id}` | — |

---

## 6. Bottom line

The trust-scoring core that the TrustGate MVP needs **already exists** in `tovbase` and is adversarially tested (6/6 attack shapes correctly Untrusted in [`scripts/audit_robustness.py`](../scripts/audit_robustness.py); 235 unit tests passing). What separates today's `tovbase` from the TrustGate MVP described in the docs is mostly **business-data plumbing** (sector, jurisdiction, sanctions, registry adapters) and **payment-routing infrastructure** (EMI adapters, cap engine, escrow ledger) — not algorithm work.

A focused 12-week build (sequenced as in §4) closes the gap. The first 4 weeks deliver a demo-ready end-to-end flow that can take partnerships and pilots while the deeper EMI / dashboard work continues in parallel.

The OSS work on `tovbase` to date is not a separate effort from TrustGate — it **is** the platform layer underneath TrustGate's MVP. Every adversarial test that passes, every algorithm-version pin, every embeddable badge, every audit URL is directly load-bearing for the regulatory + investor story.
