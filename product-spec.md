# Trustgate Product Specification

## Vision

Trustgate is the FICO score of the internet — a universal, portable trust measurement for people, businesses, and AI agents. It compresses the 10-30 minute manual trust assessment (Google them, check LinkedIn, read reviews, gut call) into 30 seconds of objective, data-driven analysis.

## Problem

Every day, millions of people make trust decisions about strangers online:
- Should I take this investor meeting?
- Is this freelancer legitimate?
- Can I trust this seller?
- Is this candidate who they say they are?

There is no standard. No portable score. No universal answer. People do manual detective work across multiple platforms, and most skip it entirely — making decisions on vibes.

## Solution

A trust score (0-1000) computed from public behavioral data across every platform someone exists on. Not self-reported. Not pay-to-play. Computed from how someone actually behaves online — their communication patterns, temporal rhythms, social relationships, topical expertise, and presence consistency.

Delivered through two surfaces that feed each other.

## Two-Surface GTM

### Surface 1: Chrome Extension — "Trust scores everywhere you browse"

The extension is the **net**. It captures attention and builds data.

- Ambient, passive overlay on LinkedIn, Twitter/X, GitHub, Reddit, Hacker News
- Shows instant trust score badge (0-1000, color-coded by tier)
- Quick signal breakdown on hover/click
- "Full report" link drives users to the website
- Every profile view enriches the identity graph at zero infrastructure cost

### Surface 2: Website (trustgate.io) — "Due diligence in 30 seconds"

The website is the **trident**. It delivers deep value and generates revenue.

- Paste any profile URL or handle into a search bar
- Get a full AI-powered trust report in 30 seconds
- Cross-platform identity resolution, behavioral analysis, timeline, network analysis
- No sign-up required for first report
- Claim your profile to control your narrative and boost your score

### The Flywheel

```
Extension user sees score on LinkedIn
  → Wants detail → clicks "Full report"
    → Lands on trustgate.io → checks own score → claims profile
      → Shares trustgate.io/their-name on LinkedIn
        → Others see it → install extension → cycle repeats
```

## Target Users

| User | Trust Decision | Frequency |
|------|---------------|-----------|
| Recruiters | Is this candidate real and credible? | Daily |
| Founders | Should I take this investor/partner meeting? | Weekly |
| Freelancers | Is this client going to pay / be reasonable? | Weekly |
| VCs | Preliminary screening on founders | Daily |
| Marketplace operators | Is this seller legitimate? | Continuous |
| Consumers | Can I trust this online seller/service? | Ad hoc |
| AI agents | Should I transact with this agent/wallet? | Continuous |

## Trust Score

### 5 Sub-Scores (0-200 each, total 0-1000)

| Sub-Score | Question | Key Signals |
|-----------|----------|-------------|
| **Existence** | How real and established? | Account age, profile completeness, platform count, observation count |
| **Consistency** | How stable is behavior? | Chronotype regularity, voice stability, presence consistency, cadence stability |
| **Engagement** | Are interactions genuine? | Depth (comments > likes), reciprocity, breadth, organic growth |
| **Cross-Platform** | Same person everywhere? | Behavioral vector similarity, chronotype overlap, voice fingerprint, name matching |
| **Maturity** | How established and clean? | Tenure, activity volume, authority index, clean anomaly record |

### Confidence Dampening

Scores are dampened when data is thin. This is transparent to the user.

| Observations | Multiplier | Label |
|-------------|-----------|-------|
| < 5 | 0.33x | Insufficient data |
| 5-14 | 0.55x | Low confidence |
| 15-29 | 0.80x | Moderate confidence |
| 30+ | 1.0x | High confidence |

### Tier System

| Score | Tier | Color | Meaning |
|-------|------|-------|---------|
| 850-1000 | Excellent | #0F6E56 | Highly consistent, well-regarded across platforms |
| 700-849 | Good | #0F6E56 | Solid reputation with good consistency |
| 550-699 | Fair | #BA7517 | Moderate presence, some inconsistencies |
| 350-549 | Poor | #DC2626 | Significant gaps or very new |
| 0-349 | Untrusted | #DC2626 | Major red flags or insufficient data |

## 6 Behavioral Dimensions

The profiling is designed from **psychology, sociology, and communication science** — not transactional fraud detection. Each dimension captures a distinct facet of how a person shows up online.

1. **Chronotype** — When they exist online. Circadian digital signature. Timezone inference. Session patterns.
2. **Voice** — How they communicate. Vocabulary richness, formality, emotional tone, linguistic fingerprint.
3. **Social Posture** — How they relate to others. Leader/peer/lurker. Reciprocity. Authority. Audience quality.
4. **Topical Identity** — What they care about. Knowledge domains. Expertise depth. Consistency of claims.
5. **Presence Pattern** — How consistently they show up. Posting cadence. Growth organicity. Responsiveness.
6. **Trust Signals** — Authenticity markers. Verification status. Profile completeness. Anomaly record.

## The Report

The due diligence report is the core product. It answers: "Should I trust this person?"

### Report Structure

**Header Card:**
- Trust score (0-1000) in circular badge, color-coded by tier
- Display name, claimed role/org
- Tier label (Excellent/Good/Fair/Poor/Untrusted)
- Claimed/Unclaimed status
- Platform badges with verification status
- Action buttons: Share report, Track changes, Claim profile

**Tab 1 — AI Summary:**
- Natural language paragraph summarizing who they are and why the score is what it is
- Key findings list (positive findings and warnings, flagged with icons)
- AI assessment with confidence level and recommendation

**Tab 2 — Trust Signals:**
- 6 horizontal signal bars (0-100 each):
  - Identity Consistency
  - Account Longevity
  - Community Standing
  - Behavioral Stability
  - Content Quality
  - Profile Completeness
- Color-coded: green (strong), orange (moderate), red (weak)

**Tab 3 — Activity Timeline:**
- Recent cross-platform activity chronologically
- Platform badge + timestamp + description for each entry
- Shows behavioral evidence behind the score

**Tab 4 — Network:**
- Connected identities with their trust scores and roles
- Network quality summary (average trust score of connections)
- Visual: avatar initials, color-coded by tier

## Profile Claiming

Users can claim their profile to:
- Get a permanent URL: trustgate.io/your-name
- Boost their score (claimed profiles have higher existence scores)
- Get "Verified" badge
- Control their narrative (add bio, credentials)
- Receive notifications when their profile is viewed
- Connect additional platforms (each connection boosts score)

## Chrome Extension

### Supported Platforms
- LinkedIn (`/in/*` profiles)
- Twitter / X (user profiles)
- GitHub (user profiles)
- Reddit (`/user/*`)
- Hacker News (`/user?id=*`)

### Behavior
- Detects profile page via URL pattern matching
- Sends score request to background service worker
- Renders badge overlay near profile name
- Expandable card shows: score, tier, confidence, display name
- "Full report" link to trustgate.io/report/{handle}
- Supports dark mode (detects via `prefers-color-scheme` + background luminance)
- 1-hour cache in `chrome.storage.local`
- SPA navigation detection via MutationObserver

## Website (trustgate.io)

### Pages

**Homepage:**
- Hero: "Due diligence in 30 seconds." + search bar
- No sign-up required for first report
- Extension CTA: "Get trust scores everywhere you browse"
- Claim CTA: "Your trust score already exists."

**Report page** (`/report/[id]`):
- Full report with 4-tab layout (described above)

**Profile page** (`/profile/[handle]`):
- Public profile for claimed identities

### Design Language
- Clean, professional, minimal
- Inter font
- White background, gray-900 text
- Green (#0F6E56) for positive, orange (#BA7517) for warnings, red (#DC2626) for danger
- No feature tours, pricing tables, or "trusted by" logos on homepage

## Monetization

### Free (Permanent)
- 3 full reports/day (website)
- Unlimited basic score overlay (extension)
- Claim your profile
- Share report links

### Pro ($12/month)
- Unlimited reports
- Score change alerts for bookmarked profiles
- Side-by-side comparison
- PDF export
- "Who viewed my profile" notifications
- Enhanced extension overlay with signal breakdown

### Team ($39/month per seat)
- Everything in Pro
- Team dashboard for hiring pipelines
- Bulk report generation
- ATS integration (Greenhouse, Lever)
- Shared bookmarks and notes

### API ($0.05-$0.50 per call)
- Programmatic access to scores and reports
- Webhook alerts
- Bulk processing

### Enterprise (Custom)
- Private deployment
- Custom scoring models
- SLA guarantees
- Compliance and audit

## Identity Resolution

Cross-platform identity matching uses 5 weighted signals:

| Signal | Weight | Method |
|--------|--------|--------|
| Behavioral vector | 35% | Cosine similarity of 32-dim vectors in Qdrant |
| Voice fingerprint | 25% | Cosine similarity of linguistic features |
| Chronotype overlap | 20% | Pearson correlation of hourly distributions + timezone proximity |
| Name/handle match | 15% | Jaro-Winkler on display name + exact/fuzzy handle match |
| Topic overlap | 5% | Cosine similarity of keyword fingerprints |

Decision thresholds: >=0.75 auto-link, 0.55-0.75 flag for review, <0.55 separate.

## Tone and Positioning

**We are:**
- "Due diligence in 30 seconds" (the tagline)
- Professional, data-driven, transparent
- Infrastructure for trust decisions
- Objective (computed from public data, not self-reported)

**We are NOT:**
- A surveillance tool ("only uses public data")
- A social credit system (no punishment mechanism)
- A "people search" engine (trust, not identity)
- A replacement for human judgment (we inform, not decide)
- Creepy or invasive (transparent about signals, user can claim and control)

## Key Differentiators

1. **Zero cold-start**: Extension generates scores on-demand from live data. Day-one value.
2. **Users are the ingestion engine**: Every profile view enriches the graph at zero infrastructure cost. 1,000 users x 50 profiles/day = 50K data points daily.
3. **Inherent viral loop**: "What's my score?" drives installs. Claiming drives engagement. Sharing drives acquisition.
4. **Meets users where they decide**: Score appears RIGHT THERE on the LinkedIn/Twitter profile being evaluated, not on a separate website.
5. **Cross-platform identity resolution**: No competitor resolves the same person across 5+ platforms with behavioral vector matching.
6. **AI agent support**: Trust infrastructure for the emerging agent economy (wallet addresses, transaction history, behavioral consistency).
7. **Compounding data moat**: Every report enriches the graph. The graph makes future reports better. Competitors would be years behind.

## Infrastructure Cost Target

$135-370/month total. This is 90% below the original GPU+Neo4j architecture ($2,300/mo). Achieved by replacing ML models with deterministic statistical profiling and Neo4j with PostgreSQL + Qdrant.

| Component | Cost/mo |
|-----------|---------|
| API server (Fly.io) | $30-60 |
| Frontend (Vercel) | $0-20 |
| PostgreSQL (Supabase/Neon) | $25-50 |
| Qdrant (self-hosted or cloud) | $0-30 |
| Redis (Upstash) | $10-25 |
| Background workers (Fly.io) | $15-30 |
| Anthropic API (reports only) | $50-150 |
| Storage (Cloudflare R2) | $5 |

## Execution Phases

**Phase 1 (Months 0-3):** Extension + on-demand scoring + website + claiming
**Phase 2 (Months 3-6):** Firefox extension, mobile apps, Pro tier, more platforms
**Phase 3 (Months 6-12):** Public API, agent registration, topic intelligence, webhooks
**Phase 4 (Months 9-18):** Simulation sandbox, synthetic population generation, industry templates
