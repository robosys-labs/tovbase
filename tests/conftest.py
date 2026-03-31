"""Test fixtures for tovbase."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest

from app.models import CanonicalIdentity, IdentityProfile


def _make_profile(**overrides) -> IdentityProfile:
    """Create an IdentityProfile with sensible defaults for testing."""
    defaults = {
        "id": uuid.uuid4(),
        "handle": "testuser",
        "platform": "twitter",
        "display_name": "Test User",
        # Chronotype
        "hourly_distribution": [0.0] * 24,
        "daily_distribution": [0.0] * 7,
        "estimated_timezone_offset": -5.0,
        "regularity_score": 0.7,
        "weekend_ratio": 0.25,
        "burst_tendency": 0.3,
        "dormancy_max_days": 5,
        "session_count_avg_daily": 3.0,
        "session_duration_avg_minutes": 15.0,
        "night_activity_ratio": 0.05,
        "first_activity_at": datetime.utcnow() - timedelta(days=1000),
        "last_activity_at": datetime.utcnow() - timedelta(hours=2),
        # Voice
        "avg_utterance_length": 45.0,
        "utterance_length_variance": 20.0,
        "vocabulary_richness": 0.65,
        "formality_index": 0.6,
        "emotional_valence": 0.2,
        "emotional_volatility": 0.15,
        "question_ratio": 0.12,
        "self_reference_rate": 0.08,
        "punctuation_signature": {"emoji_rate": 0.02, "exclamation_rate": 0.05},
        "language_codes": "en",
        "avg_words_per_sentence": 12.0,
        "hashtag_rate": 0.1,
        "link_sharing_rate": 0.15,
        "mention_rate": 0.2,
        "code_snippet_rate": 0.0,
        "media_attachment_rate": 0.1,
        "thread_starter_rate": 0.3,
        "avg_response_length": 30.0,
        # Social
        "initiation_ratio": 0.4,
        "reply_depth_avg": 2.5,
        "engagement_depth_ratio": 0.5,
        "authority_index": 0.3,
        "reciprocity_rate": 0.45,
        "audience_size": 5000,
        "audience_quality_ratio": 0.5,
        "community_centrality": 0.4,
        "conflict_tendency": 0.05,
        "mention_response_rate": 0.6,
        "avg_reply_latency_minutes": 60.0,
        "endorsement_count": 20,
        "collaboration_signals": 5,
        "audience_growth_30d": 50.0,
        "audience_churn_rate": 0.01,
        # Topics
        "keyword_fingerprint": {"python": 0.15, "api": 0.1, "data": 0.08},
        "category_fingerprint": {"programming": 0.4, "data_science": 0.3, "devops": 0.15},
        "expertise_depth": 0.6,
        "opinion_consistency": 0.7,
        "interest_breadth": 0.4,
        "content_originality": 0.65,
        "citation_rate": 0.1,
        "narrative_consistency": 0.8,
        "platform_specific_expertise": {},
        "claimed_role": "Software Engineer",
        "claimed_org": "Acme Corp",
        # Presence
        "posts_per_week_avg": 12.0,
        "posts_per_week_variance": 4.0,
        "active_weeks_ratio": 0.85,
        "responsiveness_minutes": 45.0,
        "thread_persistence_avg": 3.0,
        "content_cadence_pattern": "steady",
        "platform_tenure_days": 1200,
        "growth_velocity": 0.02,
        "growth_organicity": 0.8,
        "deletion_rate": 0.01,
        "edit_rate": 0.05,
        "peak_engagement_post_type": "thread",
        "seasonal_pattern": {},
        "platform_migration_signal": 0.0,
        # Trust
        "account_age_days": 1200,
        "profile_completeness": 0.75,
        "is_verified": False,
        "is_claimed": False,
        "has_linked_platforms": 0,
        "anomaly_count": 0,
        "anomaly_types": [],
        "observation_count": 25,
        "first_observed_at": datetime.utcnow() - timedelta(days=90),
        "last_observed_at": datetime.utcnow() - timedelta(hours=2),
        # Meta
        "version": 1,
    }

    # Set realistic hourly distribution (peak during work hours)
    hourly = [0.0] * 24
    for h in [9, 10, 11, 12, 13, 14, 15, 16, 17]:
        hourly[h] = 0.1
    hourly[18] = 0.05
    hourly[20] = 0.03
    hourly[21] = 0.02
    defaults["hourly_distribution"] = hourly

    # Set daily distribution (weekday-heavy)
    daily = [0.18, 0.18, 0.18, 0.18, 0.18, 0.05, 0.05]
    defaults["daily_distribution"] = daily

    defaults.update(overrides)
    profile = IdentityProfile(**defaults)
    return profile


@pytest.fixture
def established_profile() -> IdentityProfile:
    """A well-established profile with 1200 days, 25 observations."""
    return _make_profile()


@pytest.fixture
def new_profile() -> IdentityProfile:
    """A brand-new profile with minimal data."""
    return _make_profile(
        handle="newbie",
        observation_count=2,
        account_age_days=30,
        platform_tenure_days=30,
        audience_size=50,
        posts_per_week_avg=1.0,
        active_weeks_ratio=0.3,
        profile_completeness=0.3,
        vocabulary_richness=0.3,
        regularity_score=0.2,
    )


@pytest.fixture
def bot_profile() -> IdentityProfile:
    """A bot-like profile with suspicious patterns."""
    # Uniform hourly distribution (active 24/7 — not human)
    hourly = [1 / 24] * 24
    return _make_profile(
        handle="bot_account",
        hourly_distribution=hourly,
        regularity_score=0.05,
        emotional_volatility=0.0,
        engagement_depth_ratio=0.02,
        reciprocity_rate=0.01,
        growth_organicity=0.1,
        mention_response_rate=0.0,
        audience_size=100000,
        audience_quality_ratio=0.01,
        content_originality=0.05,
        anomaly_count=8,
        observation_count=20,
    )


@pytest.fixture
def same_person_github() -> IdentityProfile:
    """A GitHub profile for the same person as established_profile."""
    hourly = [0.0] * 24
    for h in [9, 10, 11, 12, 13, 14, 15, 16, 17]:
        hourly[h] = 0.1
    hourly[18] = 0.05
    hourly[20] = 0.03
    hourly[21] = 0.02

    return _make_profile(
        id=uuid.uuid4(),
        handle="testuser",
        platform="github",
        display_name="Test User",
        hourly_distribution=hourly,
        estimated_timezone_offset=-5.0,
        vocabulary_richness=0.62,
        formality_index=0.55,
        emotional_valence=0.15,
        question_ratio=0.10,
        self_reference_rate=0.07,
        keyword_fingerprint={"python": 0.18, "api": 0.12, "testing": 0.06},
        category_fingerprint={"programming": 0.45, "data_science": 0.25, "devops": 0.20},
        audience_size=800,
        code_snippet_rate=0.4,
    )


@pytest.fixture
def different_person() -> IdentityProfile:
    """A completely different person's profile."""
    # Night owl, different timezone, different topics
    hourly = [0.0] * 24
    for h in [20, 21, 22, 23, 0, 1, 2]:
        hourly[h] = 0.13
    hourly[3] = 0.09

    return _make_profile(
        id=uuid.uuid4(),
        handle="nightowl_chef",
        platform="twitter",
        display_name="Maria Rodriguez",
        hourly_distribution=hourly,
        estimated_timezone_offset=1.0,
        regularity_score=0.5,
        vocabulary_richness=0.45,
        formality_index=0.3,
        emotional_valence=0.6,
        question_ratio=0.05,
        self_reference_rate=0.15,
        keyword_fingerprint={"recipe": 0.2, "cooking": 0.15, "restaurant": 0.1},
        category_fingerprint={"food": 0.5, "lifestyle": 0.3, "travel": 0.1},
        audience_size=12000,
    )
