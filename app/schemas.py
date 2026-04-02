"""Pydantic schemas for API request/response models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Score response
# ---------------------------------------------------------------------------


class ScoreResponse(BaseModel):
    handle: str
    platform: str | None = None
    trust_score: int = 0
    tier: str = "untrusted"
    confidence: float = 0.0
    breakdown: dict = Field(default_factory=dict)
    canonical_id: str | None = None
    display_name: str | None = None
    num_platforms: int = 0
    cached: bool = False


# ---------------------------------------------------------------------------
# Identity response
# ---------------------------------------------------------------------------


class PlatformProfile(BaseModel):
    handle: str
    platform: str
    display_name: str | None = None
    account_age_days: int = 0
    audience_size: int = 0
    is_verified: bool = False
    observation_count: int = 0
    last_observed_at: datetime | None = None


class IdentityResponse(BaseModel):
    canonical_id: str
    primary_handle: str
    primary_platform: str
    display_name: str | None = None
    trust_score: int = 0
    tier: str = "untrusted"
    confidence: float = 0.0
    breakdown: dict = Field(default_factory=dict)
    profiles: list[PlatformProfile] = Field(default_factory=list)
    profile_url: str | None = None


# ---------------------------------------------------------------------------
# Observation submission
# ---------------------------------------------------------------------------


class ObservationRequest(BaseModel):
    """Submit observed profile data from a scraper or extension."""

    handle: str
    platform: str
    display_name: str | None = None

    # Chronotype observations
    activity_hours: list[int] = Field(default_factory=list, description="Hours (0-23) when activity was observed")
    activity_days: list[int] = Field(default_factory=list, description="Weekdays (0=Mon) when activity was observed")

    # Voice observations
    post_texts: list[str] = Field(default_factory=list, description="Sample post texts for linguistic analysis")

    # Social observations
    audience_size: int | None = None
    following_count: int | None = None
    endorsement_count: int | None = None

    # Topical observations
    claimed_role: str | None = None
    claimed_org: str | None = None

    # Presence observations
    recent_post_count: int | None = None
    account_created_at: datetime | None = None
    is_verified: bool = False

    # Platform-specific raw payload
    raw_payload: dict = Field(default_factory=dict)


class ObservationResponse(BaseModel):
    profile_id: str
    handle: str
    platform: str
    canonical_id: str | None = None
    trust_score: int = 0
    is_new_profile: bool = False
    observation_count: int = 0


# ---------------------------------------------------------------------------
# Similarity response
# ---------------------------------------------------------------------------


class SimilarIdentity(BaseModel):
    handle: str
    platform: str
    display_name: str | None = None
    similarity_score: float = 0.0
    canonical_id: str | None = None


class SimilarityResponse(BaseModel):
    query_handle: str
    query_platform: str
    results: list[SimilarIdentity] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


class ReportRequest(BaseModel):
    """Generate a full due diligence report from a profile URL or handle."""

    query: str  # profile URL, handle, or search term
    platform: str | None = None  # if not provided, auto-detect from URL


class ActivityEntry(BaseModel):
    timestamp: str
    platform: str
    description: str


class NetworkConnection(BaseModel):
    name: str
    role: str | None = None
    trust_score: int = 0
    initials: str = ""


class KeyFinding(BaseModel):
    type: str  # "positive", "warning", "negative"
    title: str
    description: str


class ReportResponse(BaseModel):
    report_id: str
    handle: str
    display_name: str | None = None
    platform: str
    platforms: list[str] = Field(default_factory=list)
    trust_score: int = 0
    tier: str = "untrusted"
    confidence: float = 0.0
    claimed_role: str | None = None
    claimed_org: str | None = None
    is_claimed: bool = False

    # Score breakdown (0-200 each)
    existence_score: float = 0.0
    consistency_score: float = 0.0
    engagement_score: float = 0.0
    cross_platform_score: float = 0.0
    maturity_score: float = 0.0

    # AI Summary
    summary: str = ""
    key_findings: list[KeyFinding] = Field(default_factory=list)
    ai_assessment: str = ""

    # Signal bars (0-100 normalized)
    signals: dict = Field(default_factory=dict)

    # Activity timeline
    recent_activity: list[ActivityEntry] = Field(default_factory=list)

    # Network
    connections: list[NetworkConnection] = Field(default_factory=list)
    network_quality: str = ""


# ---------------------------------------------------------------------------
# Company scoring
# ---------------------------------------------------------------------------


class CompanyScoreResponse(BaseModel):
    handle: str
    platform: str | None = None
    entity_type: str = "company"
    trust_score: int = 0
    tier: str = "untrusted"
    confidence: float = 0.0
    display_name: str | None = None
    breakdown: dict = Field(default_factory=dict)
    founder_score: float = 0.0
    product_score: float = 0.0
    community_score: float = 0.0
    presence_score: float = 0.0
    execution_score: float = 0.0
    consistency_score: float = 0.0
    founders: list[dict] = Field(default_factory=list)
    cached: bool = False


class CompanyObservationRequest(BaseModel):
    """Submit observed company data."""

    handle: str
    platform: str
    display_name: str | None = None
    domain: str | None = None
    description: str | None = None

    # Team
    founder_handles: list[dict] = Field(
        default_factory=list,
        description="List of {handle, platform} dicts for founders",
    )
    team_size: int | None = None

    # Product signals
    github_org: str | None = None
    total_repos: int | None = None
    total_stars: int | None = None
    total_forks: int | None = None
    commit_frequency_weekly: float | None = None
    contributor_count: int | None = None
    release_cadence_days: float | None = None
    ci_pass_rate: float | None = None
    documentation_score: float | None = None

    # Presence
    platform_accounts: dict | None = None
    follower_count: int | None = None
    is_verified: bool = False
    account_age_days: int | None = None

    # Business
    funding_stage: str | None = None
    funding_amount_usd: int | None = None
    employee_count_estimate: int | None = None
    yc_batch: str | None = None

    # Community
    brand_sentiment: float | None = None
    community_size: int | None = None
    nps_estimate: float | None = None
    support_response_hours: float | None = None
    mention_volume_weekly: float | None = None

    raw_payload: dict = Field(default_factory=dict)


class CompanyObservationResponse(BaseModel):
    company_id: str
    handle: str
    platform: str
    trust_score: int = 0
    is_new: bool = False
    observation_count: int = 0


# ---------------------------------------------------------------------------
# Topic intelligence — real-time query API
# ---------------------------------------------------------------------------


class TopicSearchRequest(BaseModel):
    """Query for real-time topic search (agent-facing)."""

    query: str = ""
    categories: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)
    continents: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    window_hours: int = Field(default=24, ge=1, le=720)
    min_trust_score: int | None = None
    min_engagement: int = 0
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class TopicEntryResponse(BaseModel):
    id: str
    title: str | None = None
    summary: str | None = None
    url: str | None = None
    platform: str
    author_handle: str | None = None
    author_name: str | None = None
    author_trust_score: int | None = None
    published_at: str
    categories: dict = Field(default_factory=dict)
    keywords: dict = Field(default_factory=dict)
    entities: list = Field(default_factory=list)
    sentiment: float = 0.0
    engagement_score: int = 0
    country_code: str = "US"
    language: str = "en"
    source_name: str | None = None
    source_reliability: float = 0.5


class TopicSearchResponse(BaseModel):
    query: str
    window_hours: int
    total_results: int
    results: list[TopicEntryResponse] = Field(default_factory=list)
    categories_found: dict = Field(default_factory=dict)
    top_sources: list[dict] = Field(default_factory=list)


class FeedSourceResponse(BaseModel):
    id: str
    name: str
    url: str
    feed_type: str
    source_type: str
    category: str
    language: str
    country_code: str
    continent: str
    reliability_score: float
    is_active: bool
    last_fetched_at: str | None = None


class FeedIngestRequest(BaseModel):
    """Request to ingest items from a specific feed or social platform."""

    platform: str
    items: list[dict] = Field(default_factory=list)
    country_code: str = "US"
    language: str = "en"


class FeedIngestResponse(BaseModel):
    platform: str
    new_entries: int
    total_items: int


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str = "ok"
    database: bool = False
    redis: bool = False
    qdrant: bool = False


# ---------------------------------------------------------------------------
# Scraping / Discovery
# ---------------------------------------------------------------------------


class ScrapeRequest(BaseModel):
    """Request to enqueue a profile for backend scraping via Playwright."""

    platform: str
    handle: str
    url: str | None = None
    priority: int = Field(default=0, ge=0, le=1, description="0=normal, 1=high")


class ScrapeResponse(BaseModel):
    job_id: str
    platform: str
    handle: str
    status: str = "queued"


class DiscoveredProfile(BaseModel):
    platform: str
    handle: str
    url: str
    confidence: float = 0.0


class DiscoverRequest(BaseModel):
    """Request to discover related profiles across platforms."""

    handle: str
    display_name: str | None = None
    source_platform: str | None = None


class DiscoverResponse(BaseModel):
    handle: str
    discovered: list[DiscoveredProfile] = Field(default_factory=list)


class PlatformAuthStatus(BaseModel):
    platform: str
    profile_exists: bool = False
    status: str = "not_configured"
    last_modified: str | None = None
    login_url: str | None = None
    has_active_login: bool = False
    valid: bool | None = None
    checked_at: str | None = None


class AuthStatusResponse(BaseModel):
    platforms: list[PlatformAuthStatus] = Field(default_factory=list)


class AuthActionResponse(BaseModel):
    status: str
    platform: str
    message: str = ""
    login_url: str | None = None
    validated: bool | None = None


class EnrichResponse(BaseModel):
    """Response from the enrichment pipeline."""

    handle: str
    platform: str
    trust_score: int = 0
    tier: str = "untrusted"
    confidence: float = 0.0
    num_platforms: int = 0
    platforms_found: list[str] = Field(default_factory=list)
    profiles_ingested: int = 0
    profiles_linked: int = 0


# ---------------------------------------------------------------------------
# Profile claiming
# ---------------------------------------------------------------------------


class ClaimRequest(BaseModel):
    """Initiate a profile ownership claim."""

    handle: str
    platform: str
    verification_method: str = Field(
        ...,
        description="One of: platform_bio, dns_txt, oauth_token",
    )


class ClaimResponse(BaseModel):
    claim_id: str
    challenge: str
    verification_method: str
    expires_at: str


class VerifyRequest(BaseModel):
    """Submit proof for a pending claim."""

    claim_id: str
    proof: str


class VerifyResponse(BaseModel):
    verified: bool
    canonical_id: str | None = None
    message: str
