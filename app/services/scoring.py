"""Trust scoring engine — 5 sub-scores summing to 0-1000.

Each sub-score ranges 0-200 and captures a distinct psychological/social
dimension of trustworthiness:

  1. Existence     — how real and established is this identity?
  2. Consistency   — how stable is their behavior over time?
  3. Engagement    — are their interactions genuine and organic?
  4. Cross-platform — are they the same person across platforms?
  5. Maturity      — how deep and clean is their track record?

The final score is dampened for immature profiles (low observation count).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from app.models import ScoreTier

if TYPE_CHECKING:
    from app.models import IdentityProfile


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


# ---------------------------------------------------------------------------
# Score breakdown
# ---------------------------------------------------------------------------


@dataclass
class ScoreBreakdown:
    existence: float = 0.0
    consistency: float = 0.0
    engagement: float = 0.0
    cross_platform: float = 0.0
    maturity: float = 0.0
    raw_total: float = 0.0
    dampening_factor: float = 1.0
    final_score: int = 0
    tier: str = ScoreTier.untrusted.value
    confidence: float = 0.0
    details: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Sub-score 1: Existence (0-200)
# ---------------------------------------------------------------------------


def _score_existence(profiles: list[IdentityProfile]) -> tuple[float, dict]:
    """How real and established is this identity across all platforms?"""
    if not profiles:
        return 0.0, {}

    # Aggregate across all platform profiles (guard every field against None)
    max_age = max((p.account_age_days or 0) for p in profiles)
    avg_completeness = sum((p.profile_completeness or 0) for p in profiles) / len(profiles)
    num_platforms = len(profiles)
    total_observations = sum((p.observation_count or 0) for p in profiles)
    any_verified = any(p.is_verified for p in profiles)
    any_claimed = any(p.is_claimed for p in profiles)

    age_factor = _clamp(math.log1p(max_age) / math.log1p(1825))  # 5 years
    completeness_factor = _clamp(avg_completeness)
    platform_factor = _clamp(num_platforms / 4)
    observation_factor = _clamp(math.log1p(total_observations) / math.log1p(50))
    # Verification/claim are bonuses within the weighted sum (not standalone)
    # so unverified profiles can still reach ~170/200 with strong other signals
    verification_factor = 1.0 if any_verified else 0.0
    claim_factor = 1.0 if any_claimed else 0.0

    raw = (
        0.25 * age_factor
        + 0.20 * completeness_factor
        + 0.20 * platform_factor
        + 0.15 * observation_factor
        + 0.10 * verification_factor
        + 0.10 * claim_factor
    )

    score = _clamp(raw) * 200

    return score, {
        "account_age_days": max_age,
        "avg_completeness": round(avg_completeness, 3),
        "num_platforms": num_platforms,
        "total_observations": total_observations,
        "is_verified": any_verified,
        "is_claimed": any_claimed,
    }


# ---------------------------------------------------------------------------
# Sub-score 2: Consistency (0-200)
# ---------------------------------------------------------------------------


def _score_consistency(profiles: list[IdentityProfile]) -> tuple[float, dict]:
    """How stable is behavior across time?"""
    if not profiles:
        return 0.0, {}

    # Weight by observation count so well-observed profiles contribute more
    total_obs = sum((p.observation_count or 0) for p in profiles) or 1

    chronotype_vals = []
    voice_vals = []
    presence_vals = []
    cadence_vals = []

    for p in profiles:
        w = (p.observation_count or 1) / total_obs
        chronotype_vals.append(w * _clamp(p.regularity_score or 0))
        voice_vals.append(w * _clamp(1.0 - min((p.emotional_volatility or 0) / 0.5, 1.0)))
        presence_vals.append(w * _clamp(p.active_weeks_ratio or 0))
        ppw = (p.posts_per_week_avg or 0) + 1
        cadence_vals.append(w * _clamp(1.0 - min((p.posts_per_week_variance or 0) / ppw, 1.0)))

    chrono = sum(chronotype_vals)
    voice = sum(voice_vals)
    presence = sum(presence_vals)
    cadence = sum(cadence_vals)

    score = 200 * (0.30 * chrono + 0.25 * voice + 0.25 * presence + 0.20 * cadence)

    return _clamp(score, 0, 200), {
        "chronotype_stability": round(chrono, 3),
        "voice_stability": round(voice, 3),
        "presence_stability": round(presence, 3),
        "cadence_stability": round(cadence, 3),
    }


# ---------------------------------------------------------------------------
# Sub-score 3: Engagement Quality (0-200)
# ---------------------------------------------------------------------------


def _score_engagement(profiles: list[IdentityProfile]) -> tuple[float, dict]:
    """Are interactions genuine and organic?"""
    if not profiles:
        return 0.0, {}

    total_obs = sum((p.observation_count or 0) for p in profiles) or 1

    depth_vals = []
    reciprocity_vals = []
    growth_vals = []
    response_vals = []

    for p in profiles:
        w = (p.observation_count or 1) / total_obs
        depth_vals.append(w * _clamp(p.engagement_depth_ratio or 0))
        reciprocity_vals.append(w * _clamp(p.reciprocity_rate or 0))
        growth_vals.append(w * _clamp(p.growth_organicity or 0))
        response_vals.append(w * _clamp(p.mention_response_rate or 0))

    depth = sum(depth_vals)
    reciprocity = sum(reciprocity_vals)
    growth = sum(growth_vals)
    response = sum(response_vals)

    score = 200 * (0.30 * depth + 0.25 * reciprocity + 0.25 * growth + 0.20 * response)

    return _clamp(score, 0, 200), {
        "depth": round(depth, 3),
        "reciprocity": round(reciprocity, 3),
        "growth_organicity": round(growth, 3),
        "response_rate": round(response, 3),
    }


# ---------------------------------------------------------------------------
# Sub-score 4: Cross-Platform Coherence (0-200)
# ---------------------------------------------------------------------------


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors."""
    a_arr = np.array(a, dtype=np.float64)
    b_arr = np.array(b, dtype=np.float64)
    dot = np.dot(a_arr, b_arr)
    norm_a = np.linalg.norm(a_arr)
    norm_b = np.linalg.norm(b_arr)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def _name_similarity(a: str | None, b: str | None) -> float:
    """Simple Jaro-like name similarity (case-insensitive)."""
    if not a or not b:
        return 0.0
    a_lower = a.strip().lower()
    b_lower = b.strip().lower()
    if a_lower == b_lower:
        return 1.0

    # Token overlap
    tokens_a = set(a_lower.split())
    tokens_b = set(b_lower.split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    return len(intersection) / max(len(tokens_a), len(tokens_b))


def _score_cross_platform(
    profiles: list[IdentityProfile],
    vectors: dict[str, list[float]] | None = None,
) -> tuple[float, dict]:
    """How coherent is the identity across platforms?

    Args:
        profiles: All platform profiles for this canonical identity.
        vectors: Pre-computed behavioral vectors keyed by profile ID string.
    """
    num_platforms = len(profiles)
    if num_platforms < 2:
        # Single platform — partial credit based on coverage and profile strength
        coverage = _clamp(num_platforms / 3)
        score = 200 * 0.30 * coverage + 200 * 0.10  # base credit + coverage
        return _clamp(score, 0, 200), {"num_platforms": num_platforms, "note": "single_platform"}

    vectors = vectors or {}

    # Pairwise vector similarity
    pair_sims = []
    name_sims = []
    for i in range(len(profiles)):
        for j in range(i + 1, len(profiles)):
            vec_i = vectors.get(str(profiles[i].id))
            vec_j = vectors.get(str(profiles[j].id))
            if vec_i and vec_j:
                pair_sims.append(_cosine_similarity(vec_i, vec_j))
            name_sims.append(_name_similarity(profiles[i].display_name, profiles[j].display_name))

    avg_vec_sim = sum(pair_sims) / len(pair_sims) if pair_sims else 0.0
    avg_name_sim = sum(name_sims) / len(name_sims) if name_sims else 0.0
    coverage = _clamp(num_platforms / 3)

    score = 200 * (0.50 * avg_vec_sim + 0.30 * coverage + 0.20 * avg_name_sim)

    return _clamp(score, 0, 200), {
        "num_platforms": num_platforms,
        "avg_vector_similarity": round(avg_vec_sim, 3),
        "avg_name_similarity": round(avg_name_sim, 3),
        "pairs_compared": len(pair_sims),
    }


# ---------------------------------------------------------------------------
# Sub-score 5: Reputation Maturity (0-200)
# ---------------------------------------------------------------------------


def _score_maturity(profiles: list[IdentityProfile]) -> tuple[float, dict]:
    """How established and clean is their record?"""
    if not profiles:
        return 0.0, {}

    max_tenure = max((p.platform_tenure_days or 0) for p in profiles)
    total_posts = sum(
        (p.posts_per_week_avg or 0) * max((p.active_weeks_ratio or 0) * ((p.platform_tenure_days or 0) / 7), 1)
        for p in profiles
    )
    avg_authority = sum((p.authority_index or 0) for p in profiles) / len(profiles)
    total_anomalies = sum((p.anomaly_count or 0) for p in profiles)
    total_obs = sum((p.observation_count or 0) for p in profiles) or 1

    tenure_factor = _clamp(math.log1p(max_tenure) / math.log1p(730))  # 2 years
    activity_factor = _clamp(math.log1p(total_posts) / math.log1p(500))
    authority_factor = _clamp(avg_authority)
    clean_record = _clamp(1.0 - (total_anomalies / (total_obs + 1)))

    score = 200 * (0.25 * tenure_factor + 0.25 * activity_factor + 0.25 * authority_factor + 0.25 * clean_record)

    return _clamp(score, 0, 200), {
        "max_tenure_days": max_tenure,
        "estimated_total_posts": round(total_posts, 0),
        "avg_authority": round(avg_authority, 3),
        "clean_record": round(clean_record, 3),
    }


# ---------------------------------------------------------------------------
# Confidence dampening
# ---------------------------------------------------------------------------


def _compute_dampening(profiles: list[IdentityProfile]) -> float:
    """Dampen scores for profiles with insufficient observation data."""
    total_obs = sum((p.observation_count or 0) for p in profiles)
    if total_obs < 5:
        return 0.33  # almost no data
    elif total_obs < 15:
        return 0.55  # some data but unreliable
    elif total_obs < 30:
        return 0.80  # moderate confidence
    return 1.0


def _compute_confidence(profiles: list[IdentityProfile]) -> float:
    """Overall confidence in the score based on data quality."""
    total_obs = sum((p.observation_count or 0) for p in profiles)
    num_platforms = len(profiles)
    any_verified = any(p.is_verified for p in profiles)

    obs_conf = _clamp(math.log1p(total_obs) / math.log1p(50))
    platform_conf = _clamp(num_platforms / 4)
    verified_bonus = 0.1 if any_verified else 0.0

    return _clamp(0.4 * obs_conf + 0.3 * platform_conf + 0.2 * (total_obs / (total_obs + 10)) + verified_bonus)


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


def compute_trust_score(
    profiles: list[IdentityProfile],
    vectors: dict[str, list[float]] | None = None,
) -> ScoreBreakdown:
    """Compute the composite trust score for a canonical identity.

    Args:
        profiles: All IdentityProfile records for this person (one per platform).
        vectors: Pre-computed 32-dim behavioral vectors keyed by str(profile.id).

    Returns:
        ScoreBreakdown with sub-scores, dampening, final score, and tier.
    """
    if not profiles:
        return ScoreBreakdown()

    existence, existence_detail = _score_existence(profiles)
    consistency, consistency_detail = _score_consistency(profiles)
    engagement, engagement_detail = _score_engagement(profiles)
    cross_plat, cross_plat_detail = _score_cross_platform(profiles, vectors)
    maturity, maturity_detail = _score_maturity(profiles)

    raw_total = existence + consistency + engagement + cross_plat + maturity
    dampening = _compute_dampening(profiles)
    final = int(round(raw_total * dampening))
    final = max(0, min(1000, final))

    return ScoreBreakdown(
        existence=round(existence, 1),
        consistency=round(consistency, 1),
        engagement=round(engagement, 1),
        cross_platform=round(cross_plat, 1),
        maturity=round(maturity, 1),
        raw_total=round(raw_total, 1),
        dampening_factor=dampening,
        final_score=final,
        tier=score_to_tier(final),
        confidence=round(_compute_confidence(profiles), 3),
        details={
            "existence": existence_detail,
            "consistency": consistency_detail,
            "engagement": engagement_detail,
            "cross_platform": cross_plat_detail,
            "maturity": maturity_detail,
        },
    )
