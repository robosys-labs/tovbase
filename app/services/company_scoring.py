"""Company trust scoring engine — 6 sub-scores summing to 0-1200.

Company scoring is more complex than individual scoring because it
incorporates founder credibility, product execution, and organizational
behavior. The engine computes 6 sub-scores (0-200 each):

  1. Founder Signal    — credibility of founding team
  2. Product Signal    — repository quality, release cadence, code health
  3. Community Signal  — brand sentiment, community engagement, support
  4. Presence Signal   — consistency across official accounts
  5. Execution Signal  — shipping velocity, team stability
  6. Consistency Signal — alignment between claims and observable behavior

The final score is normalized to 0-1000 and dampened for sparse data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.models import ScoreTier
from app.services.scoring import ScoreBreakdown as IndividualBreakdown

if TYPE_CHECKING:
    from app.models import CompanyProfile


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _weighted_avg(components: list[tuple[float, float | None]]) -> float:
    """Compute weighted average, skipping None (unknown) values.

    Args:
        components: list of (weight, value) where value is 0-1 or None.
            None means "no data" — the weight is redistributed to known factors.

    Returns:
        Weighted average in [0, 1]. Returns 0.5 (neutral) if all values are None.
    """
    known = [(w, v) for w, v in components if v is not None]
    if not known:
        return 0.5  # no data at all → neutral
    total_weight = sum(w for w, _ in known)
    if total_weight <= 0:
        return 0.5
    return sum(w * v for w, v in known) / total_weight


# ---------------------------------------------------------------------------
# Company score breakdown
# ---------------------------------------------------------------------------


@dataclass
class CompanyScoreBreakdown:
    founder: float = 0.0
    product: float = 0.0
    community: float = 0.0
    presence: float = 0.0
    execution: float = 0.0
    consistency: float = 0.0
    raw_total: float = 0.0
    dampening_factor: float = 1.0
    final_score: int = 0
    tier: str = ScoreTier.untrusted.value
    confidence: float = 0.0
    details: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Sub-score 1: Founder Signal (0-200)
# ---------------------------------------------------------------------------


def _score_founder(
    company: CompanyProfile,
    founder_scores: list[IndividualBreakdown] | None = None,
) -> tuple[float, dict]:
    """How credible is the founding team?

    Aggregates individual trust scores of known founders. Higher-scoring
    founders boost company credibility, especially for early-stage companies.
    """
    founder_scores = founder_scores or []

    if not founder_scores:
        # No linked founders — partial credit based on team signals
        team_factor = _clamp(company.team_size / 10)
        avg_trust = _clamp(company.avg_team_trust_score / 1000)
        score = 200 * 0.3 * (0.5 * team_factor + 0.5 * avg_trust)
        return score, {"num_founders": 0, "team_size": company.team_size, "note": "no_linked_founders"}

    num_founders = len(founder_scores)
    avg_score = sum(b.final_score for b in founder_scores) / num_founders
    max_score = max(b.final_score for b in founder_scores)
    avg_confidence = sum(b.confidence for b in founder_scores) / num_founders

    # Weight: best founder matters most (prevents one bad apple dragging down)
    score_factor = _clamp((0.6 * max_score + 0.4 * avg_score) / 1000)
    confidence_factor = _clamp(avg_confidence)
    diversity_factor = _clamp(num_founders / 3)  # 3+ founders = full credit

    # Founder cross-platform coherence (do founders have consistent identities?)
    avg_cross_plat = sum(b.cross_platform for b in founder_scores) / num_founders
    coherence_factor = _clamp(avg_cross_plat / 200)

    raw = (
        0.40 * score_factor
        + 0.25 * confidence_factor
        + 0.20 * coherence_factor
        + 0.15 * diversity_factor
    )

    score = _clamp(raw) * 200

    return score, {
        "num_founders": num_founders,
        "avg_founder_score": round(avg_score, 1),
        "max_founder_score": round(max_score, 1),
        "avg_confidence": round(avg_confidence, 3),
        "coherence_factor": round(coherence_factor, 3),
    }


# ---------------------------------------------------------------------------
# Sub-score 2: Product Signal (0-200)
# ---------------------------------------------------------------------------


def _score_product(company: CompanyProfile) -> tuple[float, dict]:
    """How strong is the product execution evidence?

    Evaluates code quality, release cadence, community adoption (stars/forks),
    documentation, and CI health. Fields with no data (None) are skipped and
    their weight is redistributed to known factors.
    """
    # Repository activity — these use integer fields that default to 0 (always known)
    repo_factor = _clamp(math.log1p(company.total_repos or 0) / math.log1p(50))
    star_factor = _clamp(math.log1p(company.total_stars or 0) / math.log1p(10000))
    fork_factor = _clamp(math.log1p(company.total_forks or 0) / math.log1p(1000))

    # Code health — commit/contributor are integers (always known)
    commit_factor = _clamp(math.log1p(company.commit_frequency_weekly or 0) / math.log1p(100))
    contributor_factor = _clamp(math.log1p(company.contributor_count or 0) / math.log1p(50))

    # These fields are nullable — None means "no data", not "zero"
    ci_factor = _clamp(company.ci_pass_rate) if company.ci_pass_rate is not None else None
    doc_factor = _clamp(company.documentation_score) if company.documentation_score is not None else None

    # Release cadence — None means unknown, > 0 means real data
    if company.release_cadence_days is not None and company.release_cadence_days > 0:
        release_factor: float | None = _clamp(1.0 - math.log1p(company.release_cadence_days) / math.log1p(90))
    elif company.release_cadence_days is not None:
        release_factor = 0.0  # explicitly set to 0 = no releases
    else:
        release_factor = None  # unknown

    # Weighted average with unknown-field skipping
    raw = _weighted_avg([
        (0.10, repo_factor),
        (0.20, star_factor),
        (0.05, fork_factor),
        (0.15, commit_factor),
        (0.15, contributor_factor),
        (0.10, ci_factor),
        (0.10, doc_factor),
        (0.15, release_factor),
    ])

    score = _clamp(raw) * 200

    return score, {
        "total_repos": company.total_repos,
        "total_stars": company.total_stars,
        "commit_frequency_weekly": round(company.commit_frequency_weekly or 0, 1),
        "contributor_count": company.contributor_count,
        "ci_pass_rate": round(company.ci_pass_rate, 3) if company.ci_pass_rate is not None else None,
        "release_cadence_days": round(company.release_cadence_days, 1) if company.release_cadence_days is not None else None,
    }


# ---------------------------------------------------------------------------
# Sub-score 3: Community Signal (0-200)
# ---------------------------------------------------------------------------


def _score_community(company: CompanyProfile) -> tuple[float, dict]:
    """How does the community perceive this company?

    Evaluates brand sentiment, community size, support responsiveness,
    and overall engagement quality. Fields with no data (None) are skipped
    and their weight is redistributed to known factors.
    """
    # Sentiment — None means "no data", not "neutral"
    if company.brand_sentiment is not None:
        sentiment_factor: float | None = _clamp((company.brand_sentiment + 1) / 2)
    else:
        sentiment_factor = None

    # Community size — always known (integer default 0, but also use follower_count)
    effective_community = max(company.community_size or 0, company.follower_count or 0)
    size_factor = _clamp(math.log1p(effective_community) / math.log1p(100000))

    # Mention volume — None means unknown
    if company.mention_volume_weekly is not None:
        mention_factor: float | None = _clamp(math.log1p(company.mention_volume_weekly) / math.log1p(500))
    else:
        mention_factor = None

    # Support responsiveness — None means unknown, > 0 means real data
    if company.support_response_hours is not None and company.support_response_hours > 0:
        support_factor: float | None = _clamp(1.0 - math.log1p(company.support_response_hours) / math.log1p(168))
    elif company.support_response_hours is not None:
        support_factor = 0.0  # explicitly set to 0 = no support
    else:
        support_factor = None  # unknown

    # NPS estimate — None means unknown
    if company.nps_estimate is not None:
        nps_factor: float | None = _clamp((company.nps_estimate + 100) / 200)
    else:
        nps_factor = None

    raw = _weighted_avg([
        (0.30, sentiment_factor),
        (0.20, size_factor),
        (0.15, mention_factor),
        (0.15, support_factor),
        (0.20, nps_factor),
    ])

    score = _clamp(raw) * 200

    return score, {
        "brand_sentiment": round(company.brand_sentiment, 3) if company.brand_sentiment is not None else None,
        "community_size": company.community_size,
        "mention_volume_weekly": round(company.mention_volume_weekly, 1) if company.mention_volume_weekly is not None else None,
        "support_response_hours": round(company.support_response_hours, 1) if company.support_response_hours is not None else None,
        "nps_estimate": round(company.nps_estimate, 1) if company.nps_estimate is not None else None,
    }


# ---------------------------------------------------------------------------
# Sub-score 4: Presence Signal (0-200)
# ---------------------------------------------------------------------------


def _score_presence(company: CompanyProfile) -> tuple[float, dict]:
    """How established is the company's online presence?

    Evaluates platform coverage, account age, verification status,
    and follower base. Followers are the strongest signal — a company
    with 100K+ followers across platforms has significant social proof.
    """
    platforms = company.platform_accounts or {}
    platform_count = len(platforms)
    followers = company.follower_count or 0

    coverage_factor = _clamp(platform_count / 4)  # 4+ platforms = full credit
    age_factor = _clamp(math.log1p(company.account_age_days or 0) / math.log1p(1825))
    # Followers: logarithmic scale, 100K = full credit
    follower_factor = _clamp(math.log1p(followers) / math.log1p(100000))
    verified_bonus = 0.10 if company.is_verified else 0.0

    raw = (
        0.20 * coverage_factor
        + 0.15 * age_factor
        + 0.40 * follower_factor  # Strongest presence signal
        + verified_bonus
        + 0.10  # base credit for existing — ensures unverified companies can reach ~190/200
    )

    # Bonus for massive social proof (10K+ followers = additional credit)
    if followers >= 10000:
        raw += 0.05 * _clamp(math.log1p(followers / 10000) / math.log1p(100))

    score = _clamp(raw) * 200

    return score, {
        "platform_count": platform_count,
        "account_age_days": company.account_age_days or 0,
        "follower_count": followers,
        "is_verified": company.is_verified,
    }


# ---------------------------------------------------------------------------
# Sub-score 5: Execution Signal (0-200)
# ---------------------------------------------------------------------------


def _score_execution(company: CompanyProfile) -> tuple[float, dict]:
    """Is this company shipping and growing?

    Evaluates funding stage, team growth, and overall execution velocity.
    """
    FUNDING_WEIGHTS = {
        "pre_seed": 0.1, "seed": 0.2, "series_a": 0.4,
        "series_b": 0.6, "series_c": 0.75, "growth": 0.85,
        "public": 0.95, "profitable": 1.0,
    }

    funding_factor = FUNDING_WEIGHTS.get(company.funding_stage or "", 0.0)
    funding_amount_factor = _clamp(math.log1p(company.funding_amount_usd or 0) / math.log1p(100_000_000))

    team_factor = _clamp(math.log1p(company.employee_count_estimate or 0) / math.log1p(500))

    # YC/accelerator credibility bonus (within the weighted sum, not standalone)
    accelerator_factor = 1.0 if company.yc_batch else 0.0

    raw = (
        0.25 * funding_factor
        + 0.20 * funding_amount_factor
        + 0.25 * team_factor
        + 0.10 * accelerator_factor  # YC/accelerator credit — non-YC companies still reach 0.90 max
        + 0.20 * _clamp((company.commit_frequency_weekly or 0) / 50)  # shipping velocity
    )

    score = _clamp(raw) * 200

    return score, {
        "funding_stage": company.funding_stage,
        "funding_amount_usd": company.funding_amount_usd,
        "employee_count_estimate": company.employee_count_estimate,
        "yc_batch": company.yc_batch,
    }


# ---------------------------------------------------------------------------
# Sub-score 6: Consistency Signal (0-200)
# ---------------------------------------------------------------------------


def _score_consistency(
    company: CompanyProfile,
    founder_scores: list[IndividualBreakdown] | None = None,
) -> tuple[float, dict]:
    """Do company claims align with observable behavior?

    Checks founder-product alignment: if founders claim expertise in X
    but the company's product/community shows Y, trust is dampened.
    Also checks if company signals are consistent across platforms.
    """
    founder_scores = founder_scores or []

    # Founder-product alignment
    # If we have founder data, check if their expertise aligns with company domain
    if founder_scores:
        avg_founder_consistency = sum(b.consistency for b in founder_scores) / len(founder_scores)
        founder_align = _clamp(avg_founder_consistency / 200)
    else:
        founder_align = 0.5  # neutral without data

    # Brand consistency: does the company look the same across platforms?
    platforms = company.platform_accounts or {}
    cross_plat = _clamp(len(platforms) / 3) if len(platforms) >= 2 else 0.3

    # Claim vs. reality: funding claimed vs. observable signals
    if company.funding_stage and company.employee_count_estimate > 0:
        # Companies with claimed funding should have matching team size
        expected_team = {
            "pre_seed": 3, "seed": 8, "series_a": 25, "series_b": 80,
            "series_c": 200, "growth": 500, "public": 2000, "profitable": 500,
        }
        expected = expected_team.get(company.funding_stage or "", 5)
        team_ratio = company.employee_count_estimate / max(expected, 1)
        claim_align = _clamp(min(team_ratio, 1.0 / max(team_ratio, 0.01)))
    else:
        claim_align = 0.5

    raw = (
        0.40 * founder_align
        + 0.30 * cross_plat
        + 0.30 * claim_align
    )

    score = _clamp(raw) * 200

    return score, {
        "founder_alignment": round(founder_align, 3),
        "cross_platform_consistency": round(cross_plat, 3),
        "claim_alignment": round(claim_align, 3),
    }


# ---------------------------------------------------------------------------
# Confidence dampening
# ---------------------------------------------------------------------------


def _compute_dampening(company: CompanyProfile) -> float:
    """Dampen company scores based on observation count.

    Company dampening is less aggressive than individual dampening because
    a single website scrape captures 20+ structured fields (social links,
    team size, funding info, GitHub stats) — far more informative than a
    single individual profile visit. The curve is intentionally flattened
    so that companies with even 1-2 observations can score in the "fair"
    range if their signals are strong.
    """
    total_obs = company.observation_count or 0
    if total_obs < 1:
        return 0.40  # no data at all
    elif total_obs < 3:
        return 0.65  # 1-2 observations — reasonable for structured company data
    elif total_obs < 10:
        return 0.85
    return 1.0


def _compute_confidence(
    company: CompanyProfile,
    founder_scores: list[IndividualBreakdown] | None = None,
) -> float:
    founder_scores = founder_scores or []
    total_obs = company.observation_count
    platforms = company.platform_accounts or {}

    obs_conf = _clamp(math.log1p(total_obs) / math.log1p(50))
    platform_conf = _clamp(len(platforms) / 5)
    founder_conf = _clamp(len(founder_scores) / 3) if founder_scores else 0.0
    verified_bonus = 0.1 if company.is_verified else 0.0

    return _clamp(0.30 * obs_conf + 0.25 * platform_conf + 0.25 * founder_conf + 0.10 * (total_obs / (total_obs + 10)) + verified_bonus)


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------


def score_to_tier(score: int) -> str:
    if score >= 850:
        return ScoreTier.excellent.value
    elif score >= 700:
        return ScoreTier.good.value
    elif score >= 550:
        return ScoreTier.fair.value
    elif score >= 350:
        return ScoreTier.poor.value
    return ScoreTier.untrusted.value


def compute_company_score(
    company: CompanyProfile,
    founder_scores: list[IndividualBreakdown] | None = None,
) -> CompanyScoreBreakdown:
    """Compute the composite trust score for a company.

    Args:
        company: The CompanyProfile record.
        founder_scores: Pre-computed individual ScoreBreakdowns for each founder.

    Returns:
        CompanyScoreBreakdown with sub-scores, dampening, final score, and tier.
    """
    founder, founder_detail = _score_founder(company, founder_scores)
    product, product_detail = _score_product(company)
    community, community_detail = _score_community(company)
    presence, presence_detail = _score_presence(company)
    execution, execution_detail = _score_execution(company)
    consistency, consistency_detail = _score_consistency(company, founder_scores)

    raw_total = founder + product + community + presence + execution + consistency
    # Normalize from 0-1200 to 0-1000
    normalized = raw_total * (1000 / 1200)
    dampening = _compute_dampening(company)
    final = int(round(normalized * dampening))
    final = max(0, min(1000, final))

    return CompanyScoreBreakdown(
        founder=round(founder, 1),
        product=round(product, 1),
        community=round(community, 1),
        presence=round(presence, 1),
        execution=round(execution, 1),
        consistency=round(consistency, 1),
        raw_total=round(raw_total, 1),
        dampening_factor=dampening,
        final_score=final,
        tier=score_to_tier(final),
        confidence=round(_compute_confidence(company, founder_scores), 3),
        details={
            "founder": founder_detail,
            "product": product_detail,
            "community": community_detail,
            "presence": presence_detail,
            "execution": execution_detail,
            "consistency": consistency_detail,
        },
    )
