"""Cross-platform identity resolution via multi-signal similarity.

Combines behavioral vector similarity (Qdrant), chronotype correlation,
voice fingerprint matching, name/handle matching, and topic overlap to
determine whether two profiles belong to the same person.

Decision thresholds (configurable):
  > 0.75  → auto-link as same person
  0.55-0.75 → flag for review
  < 0.55  → treat as separate identity
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from app.config import settings

if TYPE_CHECKING:
    from app.models import IdentityProfile


# ---------------------------------------------------------------------------
# Similarity result
# ---------------------------------------------------------------------------


@dataclass
class SimilarityResult:
    overall_score: float
    vector_similarity: float
    chronotype_similarity: float
    voice_similarity: float
    name_similarity: float
    topic_similarity: float
    decision: str  # "auto_link", "review", "separate"


# ---------------------------------------------------------------------------
# Component similarity functions
# ---------------------------------------------------------------------------


def _cosine(a: list[float] | np.ndarray, b: list[float] | np.ndarray) -> float:
    a_arr = np.asarray(a, dtype=np.float64)
    b_arr = np.asarray(b, dtype=np.float64)
    dot = np.dot(a_arr, b_arr)
    na = np.linalg.norm(a_arr)
    nb = np.linalg.norm(b_arr)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.clip(dot / (na * nb), 0.0, 1.0))


def vector_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Full 32-dim behavioral vector cosine similarity."""
    return _cosine(vec_a, vec_b)


def chronotype_similarity(profile_a: IdentityProfile, profile_b: IdentityProfile) -> float:
    """Compare when two people are active online.

    Uses Pearson correlation of hourly distributions (captures shape)
    plus timezone offset proximity.
    """
    h_a = profile_a.hourly_distribution
    h_b = profile_b.hourly_distribution

    if not h_a or not h_b or len(h_a) != 24 or len(h_b) != 24:
        return 0.0

    arr_a = np.array(h_a, dtype=np.float64)
    arr_b = np.array(h_b, dtype=np.float64)

    # Pearson correlation of hourly activity distributions
    if arr_a.std() == 0 or arr_b.std() == 0:
        hourly_corr = 0.0
    else:
        hourly_corr = float(np.corrcoef(arr_a, arr_b)[0, 1])
        hourly_corr = max(0.0, hourly_corr)  # negative correlation = dissimilar

    # Timezone proximity (max diff is 26 hours)
    tz_diff = abs(profile_a.estimated_timezone_offset - profile_b.estimated_timezone_offset)
    tz_sim = max(0.0, 1.0 - tz_diff / 6.0)  # >6h offset = very different

    return 0.7 * hourly_corr + 0.3 * tz_sim


def voice_similarity(profile_a: IdentityProfile, profile_b: IdentityProfile) -> float:
    """Compare communication style fingerprints.

    Voice is the strongest single signal for identity resolution because
    it's very difficult to fake consistently across platforms.

    Returns 0.5 (neutral) for sparse profiles with < 3 observations,
    since unreliable voice data should not penalize or boost matching.
    """
    obs_a = profile_a.observation_count or 0
    obs_b = profile_b.observation_count or 0
    if obs_a < 3 or obs_b < 3:
        return 0.5  # Insufficient voice data — neutral score

    def _safe(val, default=0.0):
        return val if val is not None else default

    features_a = [
        _safe(profile_a.vocabulary_richness),
        _safe(profile_a.formality_index),
        (_safe(profile_a.emotional_valence) + 1) / 2,
        min(_safe(profile_a.avg_utterance_length) / 500, 1.0),
        _safe(profile_a.question_ratio),
        _safe(profile_a.self_reference_rate),
        _safe(profile_a.hashtag_rate),
        _safe(profile_a.link_sharing_rate),
        _safe(profile_a.mention_rate),
        min(_safe(profile_a.avg_words_per_sentence) / 30, 1.0),
    ]
    features_b = [
        _safe(profile_b.vocabulary_richness),
        _safe(profile_b.formality_index),
        (_safe(profile_b.emotional_valence) + 1) / 2,
        min(_safe(profile_b.avg_utterance_length) / 500, 1.0),
        _safe(profile_b.question_ratio),
        _safe(profile_b.self_reference_rate),
        _safe(profile_b.hashtag_rate),
        _safe(profile_b.link_sharing_rate),
        _safe(profile_b.mention_rate),
        min(_safe(profile_b.avg_words_per_sentence) / 30, 1.0),
    ]
    return _cosine(features_a, features_b)


def _normalize_name_sim(name: str) -> str:
    """Normalize name for similarity comparison."""
    import unicodedata
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = name.lower().replace("'", "").replace("-", " ").replace(".", " ").replace("_", " ")
    return " ".join(name.split())


def name_similarity(profile_a: IdentityProfile, profile_b: IdentityProfile) -> float:
    """Compare display names and handles.

    Uses Unicode-normalized token overlap for display names and
    exact/prefix/substring matching for handles.
    """
    score = 0.0

    # Handle match
    ha = (profile_a.handle or "").strip().lower()
    hb = (profile_b.handle or "").strip().lower()
    if ha and hb:
        if ha == hb:
            score += 0.5
        elif ha.startswith(hb) or hb.startswith(ha):
            score += 0.3
        else:
            # Check if handle is a slug of the other's name
            na_slug = _normalize_name_sim(profile_b.display_name or "").replace(" ", "")
            nb_slug = _normalize_name_sim(profile_a.display_name or "").replace(" ", "")
            if na_slug and (ha in na_slug or na_slug in ha):
                score += 0.35
            elif nb_slug and (hb in nb_slug or nb_slug in hb):
                score += 0.35
            else:
                common = sum(1 for c in ha if c in hb)
                score += 0.15 * (common / max(len(ha), len(hb)))

    # Display name match (Unicode-normalized)
    na = _normalize_name_sim(profile_a.display_name or "")
    nb = _normalize_name_sim(profile_b.display_name or "")
    if na and nb:
        if na == nb:
            score += 0.5
        else:
            tokens_a = set(na.split())
            tokens_b = set(nb.split())
            if tokens_a and tokens_b:
                overlap = len(tokens_a & tokens_b) / max(len(tokens_a), len(tokens_b))
                score += 0.5 * overlap

    return min(score, 1.0)


def topic_similarity(profile_a: IdentityProfile, profile_b: IdentityProfile) -> float:
    """Compare topical interests via keyword fingerprint cosine similarity."""
    kf_a = profile_a.keyword_fingerprint or {}
    kf_b = profile_b.keyword_fingerprint or {}

    if not kf_a or not kf_b:
        return 0.0

    all_keys = set(kf_a.keys()) | set(kf_b.keys())
    vec_a = [kf_a.get(k, 0.0) for k in all_keys]
    vec_b = [kf_b.get(k, 0.0) for k in all_keys]

    return _cosine(vec_a, vec_b)


# ---------------------------------------------------------------------------
# Composite similarity
# ---------------------------------------------------------------------------


# Signal weights — voice and behavioral vector are the strongest signals
WEIGHTS = {
    "vector": 0.35,
    "chronotype": 0.20,
    "voice": 0.25,
    "name": 0.15,
    "topic": 0.05,
}


def compute_identity_similarity(
    profile_a: IdentityProfile,
    profile_b: IdentityProfile,
    vec_a: list[float] | None = None,
    vec_b: list[float] | None = None,
) -> SimilarityResult:
    """Compute multi-signal similarity between two identity profiles.

    Args:
        profile_a: First profile.
        profile_b: Second profile.
        vec_a: Pre-computed behavioral vector for profile_a.
        vec_b: Pre-computed behavioral vector for profile_b.

    Returns:
        SimilarityResult with per-signal scores, overall score, and decision.
    """
    vec_sim = vector_similarity(vec_a, vec_b) if vec_a and vec_b else 0.0
    chrono_sim = chronotype_similarity(profile_a, profile_b)
    voice_sim = voice_similarity(profile_a, profile_b)
    name_sim = name_similarity(profile_a, profile_b)
    topic_sim = topic_similarity(profile_a, profile_b)

    overall = (
        WEIGHTS["vector"] * vec_sim
        + WEIGHTS["chronotype"] * chrono_sim
        + WEIGHTS["voice"] * voice_sim
        + WEIGHTS["name"] * name_sim
        + WEIGHTS["topic"] * topic_sim
    )

    if overall >= settings.similarity_auto_link_threshold:
        decision = "auto_link"
    elif overall >= settings.similarity_review_threshold:
        decision = "review"
    else:
        decision = "separate"

    return SimilarityResult(
        overall_score=round(overall, 4),
        vector_similarity=round(vec_sim, 4),
        chronotype_similarity=round(chrono_sim, 4),
        voice_similarity=round(voice_sim, 4),
        name_similarity=round(name_sim, 4),
        topic_similarity=round(topic_sim, 4),
        decision=decision,
    )
