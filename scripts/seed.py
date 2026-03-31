"""Seed the database with realistic demo data matching the Sarah Chen mockup."""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta

sys.path.insert(0, ".")

from sqlalchemy import select

from app.db import Base, SessionLocal, engine
from app.models import CanonicalIdentity, IdentityLink, IdentityProfile, LinkType
from app.services.vector import VectorService, compute_behavioral_vector


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Check if already seeded
    existing = db.execute(
        select(IdentityProfile).where(IdentityProfile.handle == "sarah-chen-stripe")
    ).scalar_one_or_none()
    if existing:
        print("Already seeded. Skipping.")
        db.close()
        return

    # --- Canonical Identity: Sarah Chen ---
    sarah_canonical = CanonicalIdentity(
        id=uuid.uuid4(),
        primary_handle="sarah-chen-stripe",
        primary_platform="linkedin",
        display_name="Sarah Chen",
        profile_url="sarah-chen",
    )
    db.add(sarah_canonical)
    db.flush()

    now = datetime.utcnow()

    # Work-hours chronotype (PST, 9am-6pm)
    work_hourly = [0.0] * 24
    for h in [9, 10, 11, 12, 13, 14, 15, 16, 17]:
        work_hourly[h] = 0.09
    work_hourly[18] = 0.06
    work_hourly[20] = 0.04
    work_hourly[21] = 0.03
    work_hourly[22] = 0.02
    weekday_daily = [0.18, 0.18, 0.18, 0.18, 0.18, 0.05, 0.05]

    shared_kwargs = dict(
        canonical_identity_id=sarah_canonical.id,
        # Chronotype
        hourly_distribution=work_hourly,
        daily_distribution=weekday_daily,
        estimated_timezone_offset=-8.0,
        regularity_score=0.82,
        weekend_ratio=0.12,
        burst_tendency=0.2,
        dormancy_max_days=3,
        session_count_avg_daily=4.5,
        session_duration_avg_minutes=22.0,
        night_activity_ratio=0.03,
        first_activity_at=now - timedelta(days=4380),
        last_activity_at=now - timedelta(hours=2),
        # Voice
        avg_utterance_length=65.0,
        utterance_length_variance=30.0,
        vocabulary_richness=0.78,
        formality_index=0.72,
        emotional_valence=0.25,
        emotional_volatility=0.12,
        question_ratio=0.08,
        self_reference_rate=0.06,
        punctuation_signature={"emoji_rate": 0.01, "exclamation_rate": 0.03, "ellipsis_rate": 0.01, "caps_rate": 0.02},
        language_codes="en",
        avg_words_per_sentence=15.0,
        hashtag_rate=0.05,
        link_sharing_rate=0.2,
        mention_rate=0.15,
        code_snippet_rate=0.12,
        media_attachment_rate=0.08,
        thread_starter_rate=0.35,
        avg_response_length=45.0,
        # Social
        initiation_ratio=0.45,
        reply_depth_avg=3.2,
        engagement_depth_ratio=0.65,
        authority_index=0.72,
        reciprocity_rate=0.55,
        community_centrality=0.68,
        conflict_tendency=0.02,
        mention_response_rate=0.7,
        avg_reply_latency_minutes=35.0,
        collaboration_signals=15,
        audience_churn_rate=0.005,
        # Topics
        keyword_fingerprint={
            "distributed": 0.08, "systems": 0.07, "rust": 0.06, "payments": 0.06,
            "latency": 0.05, "scale": 0.05, "infrastructure": 0.04, "api": 0.04,
            "reliability": 0.03, "microservices": 0.03, "performance": 0.03,
        },
        category_fingerprint={
            "programming": 0.35, "infrastructure": 0.25, "finance": 0.20, "management": 0.10, "open_source": 0.10,
        },
        expertise_depth=0.82,
        opinion_consistency=0.78,
        interest_breadth=0.35,
        content_originality=0.75,
        citation_rate=0.15,
        narrative_consistency=0.85,
        claimed_role="VP of Engineering",
        claimed_org="Stripe",
        # Presence
        posts_per_week_avg=8.0,
        posts_per_week_variance=3.0,
        active_weeks_ratio=0.92,
        responsiveness_minutes=35.0,
        thread_persistence_avg=4.0,
        content_cadence_pattern="steady",
        growth_velocity=0.015,
        growth_organicity=0.88,
        deletion_rate=0.005,
        edit_rate=0.03,
        peak_engagement_post_type="thread",
        seasonal_pattern={},
        platform_migration_signal=0.0,
        # Trust
        profile_completeness=0.85,
        is_verified=False,
        is_claimed=False,
        has_linked_platforms=4,
        anomaly_count=0,
        anomaly_types=[],
        observation_count=45,
        first_observed_at=now - timedelta(days=90),
        last_observed_at=now - timedelta(hours=2),
        version=1,
    )

    # LinkedIn profile
    sarah_linkedin = IdentityProfile(
        handle="sarah-chen-stripe",
        platform="linkedin",
        display_name="Sarah Chen",
        audience_size=12500,
        audience_quality_ratio=0.65,
        endorsement_count=180,
        audience_growth_30d=120.0,
        account_age_days=4380,
        platform_tenure_days=4380,
        platform_specific_expertise={"distributed_systems": 0.9, "engineering_management": 0.8, "payments": 0.85},
        **shared_kwargs,
    )
    db.add(sarah_linkedin)

    # Twitter profile
    sarah_twitter = IdentityProfile(
        handle="sarahchen_eng",
        platform="twitter",
        display_name="Sarah Chen",
        audience_size=28000,
        audience_quality_ratio=0.55,
        endorsement_count=0,
        audience_growth_30d=350.0,
        account_age_days=3650,
        platform_tenure_days=3650,
        platform_specific_expertise={},
        **shared_kwargs,
    )
    db.add(sarah_twitter)

    # GitHub profile
    github_kwargs = {**shared_kwargs, "formality_index": 0.65, "hashtag_rate": 0.0, "media_attachment_rate": 0.02, "code_snippet_rate": 0.45}
    sarah_github = IdentityProfile(
        handle="sarahchen",
        platform="github",
        display_name="Sarah Chen",
        audience_size=4200,
        audience_quality_ratio=0.8,
        endorsement_count=850,  # stars
        audience_growth_30d=45.0,
        account_age_days=4015,
        platform_tenure_days=4015,
        platform_specific_expertise={"rust": 0.9, "go": 0.7, "python": 0.6},
        **github_kwargs,
    )
    db.add(sarah_github)

    # Hacker News profile
    sarah_hn = IdentityProfile(
        handle="schen",
        platform="hackernews",
        display_name="schen",
        audience_size=0,
        audience_quality_ratio=0.0,
        endorsement_count=2800,  # karma
        audience_growth_30d=0.0,
        account_age_days=3800,
        platform_tenure_days=3800,
        platform_specific_expertise={},
        **{**shared_kwargs, "hashtag_rate": 0.0, "mention_rate": 0.0, "media_attachment_rate": 0.0, "formality_index": 0.6},
    )
    db.add(sarah_hn)

    # Medium profile
    sarah_medium = IdentityProfile(
        handle="sarah-chen",
        platform="medium",
        display_name="Sarah Chen",
        audience_size=6500,
        audience_quality_ratio=0.4,
        endorsement_count=0,
        audience_growth_30d=80.0,
        account_age_days=2500,
        platform_tenure_days=2500,
        platform_specific_expertise={},
        **{**shared_kwargs, "posts_per_week_avg": 0.5, "thread_starter_rate": 0.95, "avg_utterance_length": 450.0},
    )
    db.add(sarah_medium)

    db.flush()

    # Create identity links (same_person)
    profiles = [sarah_linkedin, sarah_twitter, sarah_github, sarah_hn, sarah_medium]
    for i in range(len(profiles)):
        for j in range(i + 1, len(profiles)):
            link = IdentityLink(
                source_profile_id=profiles[i].id,
                target_profile_id=profiles[j].id,
                link_type=LinkType.same_person.value,
                similarity_score=0.88,
                confidence=0.88,
                verified=False,
            )
            db.add(link)

    # --- Seed connected identities (for network tab) ---
    james_canonical = CanonicalIdentity(
        primary_handle="james-martinez",
        primary_platform="linkedin",
        display_name="James Martinez",
        trust_score=891,
    )
    db.add(james_canonical)
    db.flush()

    james = IdentityProfile(
        canonical_identity_id=james_canonical.id,
        handle="james-martinez",
        platform="linkedin",
        display_name="James Martinez",
        claimed_role="Staff Engineer",
        claimed_org="Stripe",
        audience_size=5000,
        audience_quality_ratio=0.6,
        account_age_days=3000,
        platform_tenure_days=3000,
        observation_count=30,
        first_observed_at=now - timedelta(days=60),
        last_observed_at=now - timedelta(days=1),
        **{k: v for k, v in {
            "hourly_distribution": work_hourly, "daily_distribution": weekday_daily,
            "regularity_score": 0.75, "weekend_ratio": 0.15, "vocabulary_richness": 0.7,
            "formality_index": 0.68, "emotional_valence": 0.3, "emotional_volatility": 0.1,
            "engagement_depth_ratio": 0.6, "authority_index": 0.65, "reciprocity_rate": 0.5,
            "growth_organicity": 0.85, "active_weeks_ratio": 0.88, "content_originality": 0.7,
            "profile_completeness": 0.8, "has_linked_platforms": 2, "version": 1,
        }.items()},
    )
    db.add(james)

    anika_canonical = CanonicalIdentity(
        primary_handle="anika-kumar",
        primary_platform="github",
        display_name="Anika Kumar",
        trust_score=912,
    )
    db.add(anika_canonical)
    db.flush()

    anika = IdentityProfile(
        canonical_identity_id=anika_canonical.id,
        handle="anika-kumar",
        platform="github",
        display_name="Anika Kumar",
        claimed_role="Rust core contributor",
        audience_size=15000,
        audience_quality_ratio=0.9,
        account_age_days=4500,
        platform_tenure_days=4500,
        observation_count=35,
        first_observed_at=now - timedelta(days=80),
        last_observed_at=now - timedelta(hours=8),
        **{k: v for k, v in {
            "hourly_distribution": work_hourly, "daily_distribution": weekday_daily,
            "regularity_score": 0.8, "vocabulary_richness": 0.82, "formality_index": 0.6,
            "emotional_valence": 0.15, "engagement_depth_ratio": 0.75, "authority_index": 0.85,
            "reciprocity_rate": 0.6, "growth_organicity": 0.92, "active_weeks_ratio": 0.95,
            "content_originality": 0.85, "profile_completeness": 0.9, "has_linked_platforms": 3,
            "expertise_depth": 0.95, "version": 1,
        }.items()},
    )
    db.add(anika)

    ryan_canonical = CanonicalIdentity(
        primary_handle="ryan-liu",
        primary_platform="linkedin",
        display_name="Ryan Liu",
        trust_score=723,
    )
    db.add(ryan_canonical)
    db.flush()

    ryan = IdentityProfile(
        canonical_identity_id=ryan_canonical.id,
        handle="ryan-liu",
        platform="linkedin",
        display_name="Ryan Liu",
        claimed_role="CTO",
        claimed_org="FinTech startup",
        audience_size=3200,
        audience_quality_ratio=0.5,
        account_age_days=2000,
        platform_tenure_days=2000,
        observation_count=18,
        first_observed_at=now - timedelta(days=45),
        last_observed_at=now - timedelta(days=3),
        **{k: v for k, v in {
            "hourly_distribution": work_hourly, "daily_distribution": weekday_daily,
            "regularity_score": 0.6, "vocabulary_richness": 0.55, "formality_index": 0.5,
            "engagement_depth_ratio": 0.4, "authority_index": 0.35, "reciprocity_rate": 0.4,
            "growth_organicity": 0.7, "active_weeks_ratio": 0.7, "content_originality": 0.5,
            "profile_completeness": 0.65, "has_linked_platforms": 1, "version": 1,
        }.items()},
    )
    db.add(ryan)

    # Compute trust score for Sarah
    vectors = {}
    for p in profiles:
        vec = compute_behavioral_vector(p)
        vectors[str(p.id)] = vec

    from app.services.scoring import compute_trust_score
    breakdown = compute_trust_score(profiles, vectors)
    sarah_canonical.trust_score = breakdown.final_score
    sarah_canonical.trust_score_breakdown = breakdown.details
    sarah_canonical.trust_score_computed_at = now

    db.commit()
    db.close()

    print(f"Seeded Sarah Chen (score: {breakdown.final_score}, tier: {breakdown.tier})")
    print(f"  LinkedIn: sarah-chen-stripe")
    print(f"  Twitter: sarahchen_eng")
    print(f"  GitHub: sarahchen")
    print(f"  HN: schen")
    print(f"  Medium: sarah-chen")
    print(f"  + 3 connected identities (James, Anika, Ryan)")


if __name__ == "__main__":
    seed()
