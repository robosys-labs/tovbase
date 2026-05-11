# Governance

Trustgate produces numbers — trust scores between 0 and 1000 — that real people, companies, and (soon) AI agents will rely on. The credibility of those numbers depends on the credibility of the process that produces them. This document describes that process.

Governance is deliberately lightweight at v0.x. It will grow in formality as the project does. The principle behind every rule below is: **anyone should be able to audit how a score was produced and challenge it.**

## Current state (v0.x)

- **Single project maintainer** with override authority for emergencies (broken algorithm in production, security disclosure).
- **2-of-N maintainer reviews** required for algorithm-touching changes (see CONTRIBUTING.md).
- **Public seed list** in `seeds/trust_seeds.yaml`, governance-managed with a 14-day comment window.
- **Discussions open** on GitHub for design proposals. Significant changes get an RFC pull request before implementation.

The next governance milestone is **v0.3 — multi-maintainer**, where the project gains 3-5 maintainers with shared authority. The milestone after that is **v1.0 — foundation-aligned**, modeled on Sigstore: a public-good non-profit umbrella that handles legal entity, infrastructure trust roots, and conflict-of-interest disclosures.

## Decision-making

### Routine changes
Bug fixes, refactors, doc updates, new tests, new platform adapters, new external credential verifiers, infrastructure work.

- **Required approvals:** 1 maintainer
- **Process:** PR, review, merge.

### Algorithm changes
Anything that changes the output of `compute_trust_score`, `compute_identity_similarity`, `compute_ppr_scores`, `compute_sybil_suspicions`, or modifies weights/thresholds/constants.

- **Required approvals:** 2 maintainers
- **Required artifacts:** before/after corpus eval, updated whitepaper section if drift, before/after tests pinning behavior.
- **Process:** PR → review → corpus eval reproduced by a second maintainer → merge.

### Seed-list changes (`seeds/trust_seeds.yaml`)
Adding, removing, or modifying a PPR anchor.

- **Required approvals:** 2 maintainers
- **Required artifacts:** documented justification linking to platform-verifiable evidence (verified account, archived public history). For *removals*, the justification must be a documented reputational incident, not subjective disagreement.
- **14-day public comment window** before merge. Comments above a defined seriousness bar block the merge until resolved.
- **Process:** PR → public comment period → review → merge.

### Disputes and challenges

If you believe a Trustgate score is wrong or unfair — yours or someone else's — open a public Issue with the canonical id, the score, and what you believe is incorrect. A maintainer will:

1. Re-run the score against the published algorithm version and confirm the output.
2. Identify the sub-score(s) responsible for the value.
3. Either show the inputs that produced the value, or open an issue to fix the algorithm.

We don't lower or raise scores out of band. The algorithm is the algorithm. Disputes can change the algorithm (via the normal process) but not individual scores.

### Adverse actions

Removing a profile from the database, marking a profile as `untrusted` outside the algorithm, or refusing to score a profile is an **adverse action**. It must be:

- Documented in a public record (`docs/ADVERSE_ACTIONS.md`, planned for v0.3).
- Reversible — the action removes data, not appends to a deny-list. Re-adding the profile via the normal ingest path is allowed.
- Justified by either a court order, a security incident, or a clear policy violation enumerated in this document.

The current policy violations triggering adverse action are:
1. **Submitting forged observations** to `/v1/profile/observe`. Trust on the data side is the same problem as trust on the score side.
2. **Doxxing private individuals.** Trustgate scores public online identities. Personal-data records (home addresses, phone numbers, family relations) are out of scope and will be removed on request.

## Roles

### Contributor
Anyone who opens a PR. No commit access. PRs get reviewed, just like everyone else's.

### Maintainer
Has commit access and review authority. Responsibilities:

- Review and merge PRs against the rules above.
- Triage incoming issues within 7 days.
- Show up for at least one release cycle (~quarterly) of planning discussions.

Maintainers are added when:
- A contributor has had a meaningful body of work merged (rule of thumb: 6+ PRs across 3+ months).
- Existing maintainers consent (2-of-N).
- The candidate accepts the responsibilities above.

Maintainers can step down at any time. We will say thank you in the release notes.

### Steward (planned for v0.3)
A maintainer with additional authority over governance changes themselves. Adding a steward, changing this document, or moving to v1.0 foundation governance requires a 2-of-N steward vote with public RFC.

## Conflict of interest

Maintainers and stewards must disclose if they:
- Work for a platform whose adapter ships in this repo, or
- Have financial interest in a profile whose score we publish, or
- Are a seed-list entry, or are family/business-partners-with a seed-list entry.

Disclosed conflicts don't disqualify someone — but they recuse from votes on the conflicted matter.

## Algorithm versioning

`compute_trust_score` returns an `algorithm_version` field on every breakdown. The pinning rules are:

- **Patch** (1.2.0 → 1.2.1): bug fix that adjusts behavior but doesn't change the documented formula.
- **Minor** (1.2 → 1.3): a new sub-score, a new verifier, a new edge type. Existing scores may shift.
- **Major** (1.x → 2.0): incompatible change. We commit to giving at least 90 days' notice via the repo + a public migration guide.

Every algorithm release ships with a public **changelog** entry showing the score shift on a held-out subset of canonicals — the user-visible diff between v_n and v_{n+1}.

## Security

Security disclosures: email `security@trustgate.io` (or, until the org is incorporated, the lead maintainer's address listed in `MAINTAINERS.md`). Don't open public issues for security holes.

We commit to:
- Initial response within 72 hours.
- Public disclosure timeline negotiated with the reporter, with a 90-day default.
- Credit in the disclosure unless you ask us not to.

## Funding & financial transparency

Trustgate operating costs are public. When the project takes funding (grants, donations, corporate sponsorship), the source and amount go in `docs/FUNDING.md`. No code change is ever made *because* a sponsor asked for it — sponsors get the same PR process as anyone else.

## Reference

- [Sigstore governance](https://github.com/sigstore/community/blob/main/GOVERNANCE.md) — model for v1.0 foundation governance.
- [Contributor Covenant](https://www.contributor-covenant.org/) — code of conduct.

## Amending this document

Changes to GOVERNANCE.md require a steward vote (v0.3+) or unanimous maintainer consent (v0.x). Either way, public RFC pull request, 14-day comment window, then merge.
