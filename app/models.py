from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Platform(str, Enum):
    linkedin = "linkedin"
    twitter = "twitter"
    github = "github"
    reddit = "reddit"
    hackernews = "hackernews"
    youtube = "youtube"
    medium = "medium"
    instagram = "instagram"
    polymarket = "polymarket"
    fourchan = "4chan"
    bluesky = "bluesky"


class EntityType(str, Enum):
    individual = "individual"
    company = "company"
    product = "product"


class LinkType(str, Enum):
    same_person = "same_person"
    interacts_with = "interacts_with"
    mentioned_by = "mentioned_by"
    founder_of = "founder_of"
    employee_of = "employee_of"
    product_of = "product_of"


class CadencePattern(str, Enum):
    unknown = "unknown"
    steady = "steady"
    bursty = "bursty"
    declining = "declining"
    growing = "growing"
    sporadic = "sporadic"


class ScoreTier(str, Enum):
    excellent = "excellent"  # 850-1000
    good = "good"  # 700-849
    fair = "fair"  # 550-699
    poor = "poor"  # 350-549
    untrusted = "untrusted"  # 0-349


# ---------------------------------------------------------------------------
# CanonicalIdentity — one row per resolved person
# ---------------------------------------------------------------------------


class CanonicalIdentity(Base):
    __tablename__ = "canonical_identities"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    primary_handle: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    primary_platform: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    trust_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    trust_score_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    trust_score_computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    profile_url: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    profiles: Mapped[list[IdentityProfile]] = relationship(back_populates="canonical_identity")


# ---------------------------------------------------------------------------
# IdentityProfile — one row per identity per platform
# ---------------------------------------------------------------------------


class IdentityProfile(Base):
    __tablename__ = "identity_profiles"
    __table_args__ = (
        UniqueConstraint("handle", "platform", name="uq_handle_platform"),
        Index("idx_ip_handle", "handle"),
        Index("idx_ip_platform", "platform"),
        Index("idx_ip_canonical", "canonical_identity_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    canonical_identity_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("canonical_identities.id"), nullable=True
    )
    handle: Mapped[str] = mapped_column(String(255), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # -----------------------------------------------------------------------
    # Dimension 1: Chronotype — when they exist online
    # -----------------------------------------------------------------------
    hourly_distribution: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
    daily_distribution: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
    estimated_timezone_offset: Mapped[float] = mapped_column(Float, default=0.0)
    regularity_score: Mapped[float] = mapped_column(Float, default=0.0)
    weekend_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    burst_tendency: Mapped[float] = mapped_column(Float, default=0.0)
    dormancy_max_days: Mapped[int] = mapped_column(Integer, default=0)
    session_count_avg_daily: Mapped[float] = mapped_column(Float, default=0.0)
    session_duration_avg_minutes: Mapped[float] = mapped_column(Float, default=0.0)
    night_activity_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    first_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # -----------------------------------------------------------------------
    # Dimension 2: Voice — how they communicate
    # -----------------------------------------------------------------------
    avg_utterance_length: Mapped[float] = mapped_column(Float, default=0.0)
    utterance_length_variance: Mapped[float] = mapped_column(Float, default=0.0)
    vocabulary_richness: Mapped[float] = mapped_column(Float, default=0.0)
    formality_index: Mapped[float] = mapped_column(Float, default=0.5)
    emotional_valence: Mapped[float] = mapped_column(Float, default=0.0)
    emotional_volatility: Mapped[float] = mapped_column(Float, default=0.0)
    question_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    self_reference_rate: Mapped[float] = mapped_column(Float, default=0.0)
    punctuation_signature: Mapped[dict | None] = mapped_column(JSON, default=dict)
    language_codes: Mapped[str] = mapped_column(String(64), default="")
    avg_words_per_sentence: Mapped[float] = mapped_column(Float, default=0.0)
    hashtag_rate: Mapped[float] = mapped_column(Float, default=0.0)
    link_sharing_rate: Mapped[float] = mapped_column(Float, default=0.0)
    mention_rate: Mapped[float] = mapped_column(Float, default=0.0)
    code_snippet_rate: Mapped[float] = mapped_column(Float, default=0.0)
    media_attachment_rate: Mapped[float] = mapped_column(Float, default=0.0)
    thread_starter_rate: Mapped[float] = mapped_column(Float, default=0.0)
    avg_response_length: Mapped[float] = mapped_column(Float, default=0.0)

    # -----------------------------------------------------------------------
    # Dimension 3: Social Posture — how they relate to others
    # -----------------------------------------------------------------------
    initiation_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    reply_depth_avg: Mapped[float] = mapped_column(Float, default=0.0)
    engagement_depth_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    authority_index: Mapped[float] = mapped_column(Float, default=0.0)
    reciprocity_rate: Mapped[float] = mapped_column(Float, default=0.0)
    audience_size: Mapped[int] = mapped_column(Integer, default=0)
    audience_quality_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    community_centrality: Mapped[float] = mapped_column(Float, default=0.0)
    conflict_tendency: Mapped[float] = mapped_column(Float, default=0.0)
    mention_response_rate: Mapped[float] = mapped_column(Float, default=0.0)
    avg_reply_latency_minutes: Mapped[float] = mapped_column(Float, default=0.0)
    endorsement_count: Mapped[int] = mapped_column(Integer, default=0)
    collaboration_signals: Mapped[int] = mapped_column(Integer, default=0)
    audience_growth_30d: Mapped[float] = mapped_column(Float, default=0.0)
    audience_churn_rate: Mapped[float] = mapped_column(Float, default=0.0)

    # -----------------------------------------------------------------------
    # Dimension 4: Topical Identity — what they care about
    # -----------------------------------------------------------------------
    keyword_fingerprint: Mapped[dict | None] = mapped_column(JSON, default=dict)
    category_fingerprint: Mapped[dict | None] = mapped_column(JSON, default=dict)
    expertise_depth: Mapped[float] = mapped_column(Float, default=0.0)
    opinion_consistency: Mapped[float] = mapped_column(Float, default=0.0)
    interest_breadth: Mapped[float] = mapped_column(Float, default=0.0)
    content_originality: Mapped[float] = mapped_column(Float, default=0.0)
    citation_rate: Mapped[float] = mapped_column(Float, default=0.0)
    narrative_consistency: Mapped[float] = mapped_column(Float, default=0.0)
    platform_specific_expertise: Mapped[dict | None] = mapped_column(JSON, default=dict)
    claimed_role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    claimed_org: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # -----------------------------------------------------------------------
    # Dimension 5: Presence Pattern — how consistently they show up
    # -----------------------------------------------------------------------
    posts_per_week_avg: Mapped[float] = mapped_column(Float, default=0.0)
    posts_per_week_variance: Mapped[float] = mapped_column(Float, default=0.0)
    active_weeks_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    responsiveness_minutes: Mapped[float] = mapped_column(Float, default=0.0)
    thread_persistence_avg: Mapped[float] = mapped_column(Float, default=0.0)
    content_cadence_pattern: Mapped[str] = mapped_column(String(32), default=CadencePattern.unknown.value)
    platform_tenure_days: Mapped[int] = mapped_column(Integer, default=0)
    growth_velocity: Mapped[float] = mapped_column(Float, default=0.0)
    growth_organicity: Mapped[float] = mapped_column(Float, default=0.0)
    deletion_rate: Mapped[float] = mapped_column(Float, default=0.0)
    edit_rate: Mapped[float] = mapped_column(Float, default=0.0)
    peak_engagement_post_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    seasonal_pattern: Mapped[dict | None] = mapped_column(JSON, default=dict)
    platform_migration_signal: Mapped[float] = mapped_column(Float, default=0.0)

    # -----------------------------------------------------------------------
    # Dimension 6: Trust Signals — authenticity markers
    # -----------------------------------------------------------------------
    account_age_days: Mapped[int] = mapped_column(Integer, default=0)
    profile_completeness: Mapped[float] = mapped_column(Float, default=0.0)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_claimed: Mapped[bool] = mapped_column(Boolean, default=False)
    has_linked_platforms: Mapped[int] = mapped_column(Integer, default=0)
    anomaly_count: Mapped[int] = mapped_column(Integer, default=0)
    anomaly_types: Mapped[list | None] = mapped_column(JSON, default=list)
    observation_count: Mapped[int] = mapped_column(Integer, default=0)
    first_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # -----------------------------------------------------------------------
    # Metadata
    # -----------------------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
    version: Mapped[int] = mapped_column(Integer, default=1)

    # Relationships
    canonical_identity: Mapped[CanonicalIdentity | None] = relationship(back_populates="profiles")
    source_links: Mapped[list[IdentityLink]] = relationship(
        foreign_keys="IdentityLink.source_profile_id", back_populates="source_profile"
    )
    target_links: Mapped[list[IdentityLink]] = relationship(
        foreign_keys="IdentityLink.target_profile_id", back_populates="target_profile"
    )


# ---------------------------------------------------------------------------
# IdentityLink — relationships between identity profiles
# ---------------------------------------------------------------------------


class IdentityLink(Base):
    __tablename__ = "identity_links"
    __table_args__ = (
        UniqueConstraint("source_profile_id", "target_profile_id", "link_type", name="uq_link_pair"),
        Index("idx_il_source", "source_profile_id"),
        Index("idx_il_target", "target_profile_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_profile_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("identity_profiles.id"), nullable=False)
    target_profile_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("identity_profiles.id"), nullable=False)
    link_type: Mapped[str] = mapped_column(String(32), nullable=False)
    similarity_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    source_profile: Mapped[IdentityProfile] = relationship(foreign_keys=[source_profile_id], back_populates="source_links")
    target_profile: Mapped[IdentityProfile] = relationship(foreign_keys=[target_profile_id], back_populates="target_links")


# ---------------------------------------------------------------------------
# CompanyProfile — one row per company entity
# ---------------------------------------------------------------------------


class CompanyProfile(Base):
    __tablename__ = "company_profiles"
    __table_args__ = (
        UniqueConstraint("handle", "platform", name="uq_company_handle_platform"),
        Index("idx_cp_handle", "handle"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    handle: Mapped[str] = mapped_column(String(255), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Founder / team links ──
    founder_identity_ids: Mapped[list | None] = mapped_column(JSON, default=list)
    team_size: Mapped[int] = mapped_column(Integer, default=0)
    avg_team_trust_score: Mapped[float] = mapped_column(Float, default=0.0)

    # ── Platform presence ──
    platform_accounts: Mapped[dict | None] = mapped_column(JSON, default=dict)
    # e.g. {"linkedin": "stripe", "twitter": "stripe", "github": "stripe"}
    account_age_days: Mapped[int] = mapped_column(Integer, default=0)
    follower_count: Mapped[int] = mapped_column(Integer, default=0)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── Product signals ──
    github_org: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total_repos: Mapped[int] = mapped_column(Integer, default=0)
    total_stars: Mapped[int] = mapped_column(Integer, default=0)
    total_forks: Mapped[int] = mapped_column(Integer, default=0)
    open_issues: Mapped[int] = mapped_column(Integer, default=0)
    commit_frequency_weekly: Mapped[float] = mapped_column(Float, default=0.0)
    contributor_count: Mapped[int] = mapped_column(Integer, default=0)
    release_cadence_days: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    ci_pass_rate: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    documentation_score: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)

    # ── Community signals ──
    brand_sentiment: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)  # -1 to 1
    mention_volume_weekly: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    support_response_hours: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    community_size: Mapped[int] = mapped_column(Integer, default=0)
    nps_estimate: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)  # -100 to 100

    # ── Business signals ──
    funding_stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    funding_amount_usd: Mapped[int] = mapped_column(Integer, default=0)
    revenue_signal: Mapped[str | None] = mapped_column(String(32), nullable=True)
    employee_count_estimate: Mapped[int] = mapped_column(Integer, default=0)
    yc_batch: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # ── Scores ──
    trust_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    trust_score_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    founder_score: Mapped[float] = mapped_column(Float, default=0.0)
    product_score: Mapped[float] = mapped_column(Float, default=0.0)
    community_score: Mapped[float] = mapped_column(Float, default=0.0)
    presence_score: Mapped[float] = mapped_column(Float, default=0.0)
    execution_score: Mapped[float] = mapped_column(Float, default=0.0)
    consistency_score: Mapped[float] = mapped_column(Float, default=0.0)

    # ── Metadata ──
    observation_count: Mapped[int] = mapped_column(Integer, default=0)
    first_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


# ---------------------------------------------------------------------------
# Topic Intelligence Layer — real-time information for agent queries
# ---------------------------------------------------------------------------


class FeedSource(Base):
    """An RSS/Atom/API feed source for topic ingestion.

    Organized by country and category to provide geographic coverage
    of news, blogs, forums, and social media.
    """

    __tablename__ = "feed_sources"
    __table_args__ = (
        Index("idx_fs_country", "country_code"),
        Index("idx_fs_category", "category"),
        Index("idx_fs_active", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    feed_type: Mapped[str] = mapped_column(String(32), default="rss")  # rss, atom, json, api, sitemap
    source_type: Mapped[str] = mapped_column(String(32), default="news")  # news, blog, forum, social, gov, academic
    category: Mapped[str] = mapped_column(String(64), default="general")
    language: Mapped[str] = mapped_column(String(8), default="en")
    country_code: Mapped[str] = mapped_column(String(4), default="US")  # ISO 3166-1 alpha-2
    continent: Mapped[str] = mapped_column(String(16), default="NA")  # NA, EU, AS, AF, SA, OC
    reliability_score: Mapped[float] = mapped_column(Float, default=0.5)  # 0-1 editorial quality
    fetch_interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_entry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    entries: Mapped[list[TopicEntry]] = relationship(back_populates="source")


class TopicEntry(Base):
    """A single content item ingested from a feed source.

    Represents an article, post, comment, or discussion item with
    extracted topics and entities for real-time query.
    """

    __tablename__ = "topic_entries"
    __table_args__ = (
        Index("idx_te_published", "published_at"),
        Index("idx_te_source", "source_id"),
        Index("idx_te_platform", "platform"),
        Index("idx_te_language", "language"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("feed_sources.id"), nullable=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)  # rss, twitter, reddit, etc.
    external_id: Mapped[str | None] = mapped_column(String(512), nullable=True)  # platform-specific ID
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Content
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)  # first 1000 chars
    author_handle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    author_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language: Mapped[str] = mapped_column(String(8), default="en")
    country_code: Mapped[str] = mapped_column(String(4), default="US")

    # Extracted signals
    keyword_fingerprint: Mapped[dict | None] = mapped_column(JSON, default=dict)
    category_fingerprint: Mapped[dict | None] = mapped_column(JSON, default=dict)
    entities: Mapped[list | None] = mapped_column(JSON, default=list)  # [{name, type, salience}]
    sentiment: Mapped[float] = mapped_column(Float, default=0.0)  # -1 to 1

    # Engagement signals
    engagement_score: Mapped[int] = mapped_column(Integer, default=0)  # likes + shares + comments
    comment_count: Mapped[int] = mapped_column(Integer, default=0)

    # Author trust (if linked)
    author_trust_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    canonical_identity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

    # Timestamps
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    source: Mapped[FeedSource | None] = relationship(back_populates="entries")


# ---------------------------------------------------------------------------
# PendingClaim — profile ownership verification requests
# ---------------------------------------------------------------------------


class PendingClaim(Base):
    """A pending profile claim awaiting verification.

    Lifecycle: pending -> verified | expired.
    Created by POST /v1/profile/claim, resolved by POST /v1/profile/verify.
    """

    __tablename__ = "pending_claims"
    __table_args__ = (
        Index("idx_pc_handle_platform", "handle", "platform"),
        Index("idx_pc_status", "status"),
        Index("idx_pc_expires", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    handle: Mapped[str] = mapped_column(String(255), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    canonical_identity_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("canonical_identities.id"), nullable=True
    )
    challenge: Mapped[str] = mapped_column(String(255), nullable=False)
    verification_method: Mapped[str] = mapped_column(String(32), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(16), default="pending")
