"""Behavioral vector computation and Qdrant integration.

Computes a 32-dimensional deterministic vector from an IdentityProfile's
six psychological/social dimensions. The vector is stored in Qdrant for
billion-scale similarity search.

Vector layout (32 dims):
  [0-1]   Chronotype: sin/cos circular encoding of peak activity hour
  [2-3]   Chronotype: regularity_score, weekend_ratio
  [4-7]   Voice: vocabulary_richness, formality_index, emotional_valence, avg_utterance_length (log-norm)
  [8-9]   Voice: question_ratio, self_reference_rate
  [10-13]  Social: initiation_ratio, engagement_depth_ratio, authority_index, reciprocity_rate
  [14-15]  Social: log(audience_size+1) (norm), audience_quality_ratio
  [16-19]  Topics: top 4 category weights (sorted desc, zero-padded)
  [20-21]  Topics: expertise_depth, content_originality
  [22-25]  Presence: log(posts_per_week_avg+1) (norm), active_weeks_ratio, growth_organicity, responsiveness (inv)
  [26-27]  Presence: platform_tenure_days (log-norm), thread_persistence_avg (norm)
  [28-31]  Trust: account_age_norm, profile_completeness, has_linked_platforms (norm), clean_record
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams

from app.config import settings

if TYPE_CHECKING:
    from app.models import IdentityProfile


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _log_norm(v: float, cap: float) -> float:
    """Log-normalize a positive value, capped."""
    return _clamp(math.log1p(v) / math.log1p(cap))


def _peak_hour(hourly: list[float] | None) -> float:
    """Find the hour with the highest activity probability."""
    if not hourly or len(hourly) != 24:
        return 12.0
    return float(max(range(24), key=lambda i: hourly[i]))


def compute_behavioral_vector(profile: IdentityProfile) -> list[float]:
    """Compute a 32-dimensional behavioral vector from profile fields.

    All values are normalized to [0, 1]. The vector is deterministic given
    the same profile state — no randomness, no learned weights.
    """
    vec = [0.0] * 32

    # --- Chronotype (dims 0-3) ---
    peak = _peak_hour(profile.hourly_distribution)
    angle = 2 * math.pi * peak / 24.0
    vec[0] = _clamp((math.sin(angle) + 1) / 2)  # sin mapped to [0,1]
    vec[1] = _clamp((math.cos(angle) + 1) / 2)  # cos mapped to [0,1]
    vec[2] = _clamp(profile.regularity_score)
    vec[3] = _clamp(profile.weekend_ratio)

    # --- Voice (dims 4-9) ---
    vec[4] = _clamp(profile.vocabulary_richness)
    vec[5] = _clamp(profile.formality_index)
    vec[6] = _clamp((profile.emotional_valence + 1) / 2)  # [-1,1] → [0,1]
    vec[7] = _log_norm(profile.avg_utterance_length, 500)  # cap at 500 words
    vec[8] = _clamp(profile.question_ratio)
    vec[9] = _clamp(profile.self_reference_rate)

    # --- Social Posture (dims 10-15) ---
    vec[10] = _clamp(profile.initiation_ratio)
    vec[11] = _clamp(profile.engagement_depth_ratio)
    vec[12] = _clamp(profile.authority_index)
    vec[13] = _clamp(profile.reciprocity_rate)
    vec[14] = _log_norm(profile.audience_size, 1_000_000)  # cap at 1M followers
    vec[15] = _clamp(profile.audience_quality_ratio)

    # --- Topical Identity (dims 16-21) ---
    cat_fp = profile.category_fingerprint or {}
    top_cats = sorted(cat_fp.values(), reverse=True)[:4]
    for i, w in enumerate(top_cats):
        vec[16 + i] = _clamp(w)
    vec[20] = _clamp(profile.expertise_depth)
    vec[21] = _clamp(profile.content_originality)

    # --- Presence (dims 22-27) ---
    vec[22] = _log_norm(profile.posts_per_week_avg, 200)  # cap at 200/week
    vec[23] = _clamp(profile.active_weeks_ratio)
    vec[24] = _clamp(profile.growth_organicity)
    # Responsiveness: lower is better, so invert. Cap at 1440 min (24h).
    resp = profile.responsiveness_minutes
    vec[25] = _clamp(1.0 - _log_norm(resp, 1440)) if resp > 0 else 0.5
    vec[26] = _log_norm(profile.platform_tenure_days, 3650)  # cap at 10 years
    vec[27] = _clamp(min(profile.thread_persistence_avg / 10.0, 1.0))  # cap at 10 exchanges

    # --- Trust Signals (dims 28-31) ---
    vec[28] = _log_norm(profile.account_age_days, 3650)  # cap at 10 years
    vec[29] = _clamp(profile.profile_completeness)
    vec[30] = _clamp(min(profile.has_linked_platforms / 5.0, 1.0))  # cap at 5 platforms
    obs = profile.observation_count or 1
    vec[31] = _clamp(1.0 - (profile.anomaly_count / (obs + 1)))

    return vec


# ---------------------------------------------------------------------------
# Qdrant client wrapper
# ---------------------------------------------------------------------------


class VectorService:
    """Manages the Qdrant collection and provides search/upsert operations."""

    def __init__(self, url: str | None = None, collection: str | None = None):
        self._url = url or settings.qdrant_url
        self._collection = collection or settings.qdrant_collection
        self._client: QdrantClient | None = None

    @property
    def client(self) -> QdrantClient:
        if self._client is None:
            self._client = QdrantClient(url=self._url)
        return self._client

    def ensure_collection(self) -> None:
        """Create the collection if it doesn't exist."""
        collections = [c.name for c in self.client.get_collections().collections]
        if self._collection not in collections:
            self.client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(
                    size=settings.vector_dimensions,
                    distance=Distance.COSINE,
                ),
            )

    def upsert_profile(self, profile: IdentityProfile, vector: list[float]) -> None:
        """Insert or update a profile's behavioral vector in Qdrant."""
        point = PointStruct(
            id=str(profile.id),
            vector=vector,
            payload={
                "profile_id": str(profile.id),
                "handle": profile.handle,
                "platform": profile.platform,
                "canonical_id": str(profile.canonical_identity_id) if profile.canonical_identity_id else None,
                "trust_score": 0,
                "display_name": profile.display_name,
            },
        )
        self.client.upsert(collection_name=self._collection, points=[point])

    def search_similar(
        self,
        vector: list[float],
        exclude_platform: str | None = None,
        limit: int = 20,
        score_threshold: float = 0.3,
    ) -> list[dict]:
        """Find the most similar identity profiles by behavioral vector.

        Args:
            vector: The 32-dim query vector.
            exclude_platform: Exclude results from this platform (for cross-platform resolution).
            limit: Max results to return.
            score_threshold: Minimum cosine similarity to include.

        Returns:
            List of dicts with profile_id, handle, platform, similarity_score, and payload.
        """
        query_filter = None
        if exclude_platform:
            query_filter = Filter(
                must_not=[FieldCondition(key="platform", match=MatchValue(value=exclude_platform))]
            )

        results = self.client.search(
            collection_name=self._collection,
            query_vector=vector,
            query_filter=query_filter,
            limit=limit,
            score_threshold=score_threshold,
        )

        return [
            {
                "profile_id": hit.payload.get("profile_id"),
                "handle": hit.payload.get("handle"),
                "platform": hit.payload.get("platform"),
                "canonical_id": hit.payload.get("canonical_id"),
                "display_name": hit.payload.get("display_name"),
                "similarity_score": hit.score,
            }
            for hit in results
        ]

    def delete_profile(self, profile_id: str) -> None:
        """Remove a profile's vector from Qdrant."""
        self.client.delete(collection_name=self._collection, points_selector=[profile_id])
