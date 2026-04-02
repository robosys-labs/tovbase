"""API routes for identity scoring, lookup, observation, and similarity."""

from __future__ import annotations

import logging
import uuid as _uuid
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("tovbase")

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import CanonicalIdentity, CompanyProfile, FeedSource, IdentityLink, IdentityProfile, PendingClaim, TopicEntry
from app.schemas import (
    ActivityEntry,
    AuthActionResponse,
    AuthStatusResponse,
    ClaimRequest,
    ClaimResponse,
    CompanyObservationRequest,
    CompanyObservationResponse,
    CompanyScoreResponse,
    DiscoverRequest,
    DiscoverResponse,
    DiscoveredProfile,
    EnrichResponse,
    FeedIngestRequest,
    FeedIngestResponse,
    FeedSourceResponse,
    HealthResponse,
    IdentityResponse,
    KeyFinding,
    NetworkConnection,
    ObservationRequest,
    ObservationResponse,
    PlatformProfile,
    ReportRequest,
    ReportResponse,
    ScrapeRequest,
    ScrapeResponse,
    ScoreResponse,
    SimilarIdentity,
    SimilarityResponse,
    TopicEntryResponse,
    TopicSearchRequest,
    TopicSearchResponse,
    VerifyRequest,
    VerifyResponse,
)
from app.services.cache import CacheService
from app.services.company_scoring import CompanyScoreBreakdown, compute_company_score
from app.services.ingestion import compute_sentiment, extract_topics, extract_voice_features, normalize_observation
from app.services.scoring import compute_trust_score, score_to_tier
from app.services.similarity import compute_identity_similarity
from app.services.topics import TopicQuery, ingest_social_items, query_topics
from app.services.vector import VectorService, compute_behavioral_vector

router = APIRouter(prefix="/v1")

# Service singletons (will be replaced with proper DI later)
_cache = CacheService()
_vector = VectorService()


# ---------------------------------------------------------------------------
# GET /v1/score/{platform}/{handle}
# ---------------------------------------------------------------------------


@router.get("/score/{platform}/{handle}", response_model=ScoreResponse)
def get_score(platform: str, handle: str, db: Session = Depends(get_db)):
    """Get the trust score for a handle on a specific platform.

    This is the primary endpoint for the Chrome extension — designed for
    sub-100ms cached responses.
    """
    # Try cache first
    profile = db.execute(
        select(IdentityProfile).where(
            IdentityProfile.handle == handle,
            IdentityProfile.platform == platform,
        )
    ).scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail=f"No profile found for {handle} on {platform}")

    canonical_id = str(profile.canonical_identity_id) if profile.canonical_identity_id else None

    # Check score cache
    if canonical_id:
        cached = _cache.get_score(canonical_id)
        if cached:
            return ScoreResponse(
                handle=handle,
                platform=platform,
                trust_score=cached.get("final_score", 0),
                tier=cached.get("tier", "untrusted"),
                confidence=cached.get("confidence", 0),
                breakdown=cached,
                canonical_id=canonical_id,
                display_name=profile.display_name,
                num_platforms=cached.get("details", {}).get("existence", {}).get("num_platforms", 1),
                cached=True,
            )

    # Compute fresh score
    if canonical_id:
        profiles = list(
            db.execute(
                select(IdentityProfile).where(IdentityProfile.canonical_identity_id == profile.canonical_identity_id)
            ).scalars()
        )
    else:
        profiles = [profile]

    # Compute vectors for cross-platform scoring
    vectors = {}
    for p in profiles:
        vec = compute_behavioral_vector(p)
        vectors[str(p.id)] = vec

    breakdown = compute_trust_score(profiles, vectors)

    # Cache the result
    breakdown_dict = {
        "final_score": breakdown.final_score,
        "tier": breakdown.tier,
        "confidence": breakdown.confidence,
        "existence": breakdown.existence,
        "consistency": breakdown.consistency,
        "engagement": breakdown.engagement,
        "cross_platform": breakdown.cross_platform,
        "maturity": breakdown.maturity,
        "dampening_factor": breakdown.dampening_factor,
        "details": breakdown.details,
    }
    if canonical_id:
        _cache.set_score(canonical_id, breakdown_dict)

    return ScoreResponse(
        handle=handle,
        platform=platform,
        trust_score=breakdown.final_score,
        tier=breakdown.tier,
        confidence=breakdown.confidence,
        breakdown=breakdown_dict,
        canonical_id=canonical_id,
        display_name=profile.display_name,
        num_platforms=len(profiles),
        cached=False,
    )


# ---------------------------------------------------------------------------
# GET /v1/identity/{handle}
# ---------------------------------------------------------------------------


@router.get("/identity/{handle}", response_model=IdentityResponse)
def get_identity(handle: str, db: Session = Depends(get_db)):
    """Get the full identity profile for a handle across all platforms."""
    profiles = list(
        db.execute(select(IdentityProfile).where(IdentityProfile.handle == handle)).scalars()
    )

    if not profiles:
        raise HTTPException(status_code=404, detail=f"No profiles found for {handle}")

    # Find canonical identity
    canonical = None
    for p in profiles:
        if p.canonical_identity_id:
            canonical = db.get(CanonicalIdentity, p.canonical_identity_id)
            if canonical:
                # Load all profiles for this canonical identity
                profiles = list(
                    db.execute(
                        select(IdentityProfile).where(
                            IdentityProfile.canonical_identity_id == canonical.id
                        )
                    ).scalars()
                )
                break

    # Compute score
    vectors = {str(p.id): compute_behavioral_vector(p) for p in profiles}
    breakdown = compute_trust_score(profiles, vectors)

    platform_profiles = [
        PlatformProfile(
            handle=p.handle,
            platform=p.platform,
            display_name=p.display_name,
            account_age_days=p.account_age_days,
            audience_size=p.audience_size,
            is_verified=p.is_verified,
            observation_count=p.observation_count,
            last_observed_at=p.last_observed_at,
        )
        for p in profiles
    ]

    breakdown_dict = {
        "final_score": breakdown.final_score,
        "tier": breakdown.tier,
        "confidence": breakdown.confidence,
        "existence": breakdown.existence,
        "consistency": breakdown.consistency,
        "engagement": breakdown.engagement,
        "cross_platform": breakdown.cross_platform,
        "maturity": breakdown.maturity,
        "dampening_factor": breakdown.dampening_factor,
        "details": breakdown.details,
    }

    return IdentityResponse(
        canonical_id=str(canonical.id) if canonical else str(profiles[0].id),
        primary_handle=canonical.primary_handle if canonical else handle,
        primary_platform=canonical.primary_platform if canonical else profiles[0].platform,
        display_name=canonical.display_name if canonical else profiles[0].display_name,
        trust_score=breakdown.final_score,
        tier=breakdown.tier,
        confidence=breakdown.confidence,
        breakdown=breakdown_dict,
        profiles=platform_profiles,
        profile_url=canonical.profile_url if canonical else None,
    )


# ---------------------------------------------------------------------------
# POST /v1/profile/observe
# ---------------------------------------------------------------------------


@router.post("/profile/observe", response_model=ObservationResponse)
def submit_observation(obs: ObservationRequest, db: Session = Depends(get_db)):
    """Submit observation data for a profile (from scrapers or extension).

    Creates a new IdentityProfile if one doesn't exist, or updates
    the existing one incrementally.
    """
    profile = db.execute(
        select(IdentityProfile).where(
            IdentityProfile.handle == obs.handle,
            IdentityProfile.platform == obs.platform,
        )
    ).scalar_one_or_none()

    is_new = profile is None

    if is_new:
        profile = IdentityProfile(
            handle=obs.handle,
            platform=obs.platform,
            display_name=obs.display_name,
            first_observed_at=datetime.utcnow(),
        )
        db.add(profile)

    # Update fields from observation
    if obs.display_name:
        profile.display_name = obs.display_name
    if obs.audience_size is not None:
        profile.audience_size = obs.audience_size
    if obs.following_count is not None and obs.audience_size is not None:
        following = max(obs.following_count, 1)
        profile.audience_quality_ratio = min(obs.audience_size / following, 10.0) / 10.0
    if obs.endorsement_count is not None:
        profile.endorsement_count = obs.endorsement_count
    if obs.claimed_role:
        profile.claimed_role = obs.claimed_role
    if obs.claimed_org:
        profile.claimed_org = obs.claimed_org
    if obs.is_verified:
        profile.is_verified = True
    if obs.account_created_at:
        profile.account_age_days = (datetime.utcnow() - obs.account_created_at).days

    # Analyse submitted post texts for voice features and topics
    if obs.post_texts:
        voice = extract_voice_features(obs.post_texts)
        if voice:
            profile.avg_utterance_length = voice.get("avg_utterance_length", profile.avg_utterance_length)
            profile.vocabulary_richness = voice.get("vocabulary_richness", profile.vocabulary_richness)
            profile.formality_index = voice.get("formality_index", profile.formality_index)
            profile.question_ratio = voice.get("question_ratio", profile.question_ratio)
            profile.hashtag_rate = voice.get("hashtag_rate", profile.hashtag_rate)
            profile.link_sharing_rate = voice.get("link_sharing_rate", profile.link_sharing_rate)
            profile.avg_words_per_sentence = voice.get("avg_words_per_sentence", profile.avg_words_per_sentence)
            profile.emotional_valence = compute_sentiment(obs.post_texts)

        kw_fp, cat_fp = extract_topics(obs.post_texts)
        if kw_fp:
            profile.keyword_fingerprint = kw_fp
        if cat_fp:
            profile.category_fingerprint = cat_fp

    # Build hourly/daily distributions from activity timestamps
    if obs.activity_hours:
        hourly = [0.0] * 24
        for h in obs.activity_hours:
            if 0 <= h < 24:
                hourly[h] += 1
        total = sum(hourly) or 1
        profile.hourly_distribution = [round(v / total, 4) for v in hourly]

    if obs.activity_days:
        daily = [0.0] * 7
        for d in obs.activity_days:
            if 0 <= d < 7:
                daily[d] += 1
        total = sum(daily) or 1
        profile.daily_distribution = [round(v / total, 4) for v in daily]
        weekend = daily[5] + daily[6]
        profile.weekend_ratio = round(weekend / total, 4) if total else 0.0

    profile.observation_count += 1
    profile.last_observed_at = datetime.utcnow()
    profile.version += 1

    db.flush()

    # Compute and upsert behavioral vector
    vec = compute_behavioral_vector(profile)
    try:
        _vector.upsert_profile(profile, vec)
    except Exception as e:
        import logging
        logging.getLogger("tovbase").debug("Qdrant upsert skipped: %s", e)

    # Run identity resolution
    _resolve_identity(db, profile)

    # Invalidate caches
    _cache.invalidate_profile(obs.handle, obs.platform)
    if profile.canonical_identity_id:
        _cache.invalidate_score(str(profile.canonical_identity_id))

    db.commit()

    return ObservationResponse(
        profile_id=str(profile.id),
        handle=profile.handle,
        platform=profile.platform,
        canonical_id=str(profile.canonical_identity_id) if profile.canonical_identity_id else None,
        trust_score=0,  # will be computed on next score request
        is_new_profile=is_new,
        observation_count=profile.observation_count,
    )


# ---------------------------------------------------------------------------
# GET /v1/similar/{platform}/{handle}
# ---------------------------------------------------------------------------


@router.get("/similar/{platform}/{handle}", response_model=SimilarityResponse)
def find_similar(platform: str, handle: str, limit: int = 20, db: Session = Depends(get_db)):
    """Find similar identities across platforms using behavioral vector search."""
    profile = db.execute(
        select(IdentityProfile).where(
            IdentityProfile.handle == handle,
            IdentityProfile.platform == platform,
        )
    ).scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail=f"No profile found for {handle} on {platform}")

    vec = compute_behavioral_vector(profile)

    try:
        results = _vector.search_similar(vec, exclude_platform=platform, limit=limit)
    except Exception:
        results = []

    return SimilarityResponse(
        query_handle=handle,
        query_platform=platform,
        results=[
            SimilarIdentity(
                handle=r["handle"],
                platform=r["platform"],
                display_name=r.get("display_name"),
                similarity_score=r["similarity_score"],
                canonical_id=r.get("canonical_id"),
            )
            for r in results
        ],
    )


# ---------------------------------------------------------------------------
# POST /v1/report/generate
# ---------------------------------------------------------------------------


def _parse_query(query: str) -> tuple[str, str | None]:
    """Extract handle and platform from a query string (URL or handle)."""
    q = query.strip().rstrip("/")
    if "linkedin.com/in/" in q:
        return q.split("/in/")[-1].split("/")[0].split("?")[0], "linkedin"
    if "twitter.com/" in q or "x.com/" in q:
        parts = q.split(".com/")[-1].split("/")[0].split("?")[0]
        return parts, "twitter"
    if "github.com/" in q:
        return q.split("github.com/")[-1].split("/")[0].split("?")[0], "github"
    if "reddit.com/user/" in q:
        return q.split("/user/")[-1].split("/")[0].split("?")[0], "reddit"
    if "news.ycombinator.com/user" in q:
        if "id=" in q:
            return q.split("id=")[-1].split("&")[0], "hackernews"
    return q, None


@router.post("/report/generate", response_model=ReportResponse)
def generate_report(req: ReportRequest, db: Session = Depends(get_db)):
    """Generate a full due diligence report for a profile."""
    handle, detected_platform = _parse_query(req.query)
    platform = req.platform or detected_platform

    # Find all profiles for this handle
    if platform:
        profile = db.execute(
            select(IdentityProfile).where(
                IdentityProfile.handle == handle,
                IdentityProfile.platform == platform,
            )
        ).scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=404, detail=f"No profile found for {handle} on {platform}")
        # Get all linked profiles
        if profile.canonical_identity_id:
            profiles = list(
                db.execute(
                    select(IdentityProfile).where(
                        IdentityProfile.canonical_identity_id == profile.canonical_identity_id
                    )
                ).scalars()
            )
        else:
            profiles = [profile]
    else:
        profiles = list(
            db.execute(select(IdentityProfile).where(IdentityProfile.handle == handle)).scalars()
        )
        if not profiles:
            raise HTTPException(status_code=404, detail=f"No profiles found for {handle}")
        profile = profiles[0]
        platform = profile.platform
        # Resolve canonical identity to include all linked profiles
        if profile.canonical_identity_id:
            canonical_profiles = list(
                db.execute(
                    select(IdentityProfile).where(
                        IdentityProfile.canonical_identity_id == profile.canonical_identity_id
                    )
                ).scalars()
            )
            if len(canonical_profiles) > len(profiles):
                profiles = canonical_profiles

    # Compute score
    vectors = {str(p.id): compute_behavioral_vector(p) for p in profiles}
    breakdown = compute_trust_score(profiles, vectors)

    # Build signal bars (normalized to 0-100)
    signals = {
        "identity_consistency": round(breakdown.cross_platform / 2, 0),
        "account_longevity": round(breakdown.existence / 2, 0),
        "community_standing": round(breakdown.engagement / 2, 0),
        "behavioral_stability": round(breakdown.consistency / 2, 0),
        "content_quality": round(breakdown.maturity / 2, 0),
        "profile_completeness": round(
            (sum(p.profile_completeness for p in profiles) / len(profiles)) * 100, 0
        ),
    }

    # Build key findings
    findings = []
    if breakdown.cross_platform >= 100:
        findings.append(KeyFinding(
            type="positive",
            title="Identity consistent.",
            description=f"Behavioral fingerprint matches across {len(profiles)} platform(s). "
            f"Posting patterns and communication style are coherent.",
        ))
    if breakdown.existence >= 100:
        findings.append(KeyFinding(
            type="positive",
            title="Long track record.",
            description=f"Oldest account active for {max(p.account_age_days for p in profiles)} days. "
            f"Continuous, regular activity observed.",
        ))
    if not any(p.is_claimed for p in profiles):
        findings.append(KeyFinding(
            type="warning",
            title="Note.",
            description="Profile is unclaimed. Trust score is based on public data only. "
            "Score would likely increase if owner claims and verifies additional credentials.",
        ))
    if breakdown.engagement < 60:
        findings.append(KeyFinding(
            type="warning",
            title="Low engagement quality.",
            description="Interactions appear shallow or one-directional. "
            "Genuine reciprocal engagement would improve this score.",
        ))

    # Build summary
    display = profile.display_name or handle
    role_text = f" ({profile.claimed_role}, {profile.claimed_org})" if profile.claimed_role else ""
    summary = (
        f"{'High' if breakdown.final_score >= 700 else 'Moderate' if breakdown.final_score >= 400 else 'Low'}"
        f"-trust profile. {display}{role_text} presents "
        f"{'a consistent' if breakdown.cross_platform >= 80 else 'an'} identity across "
        f"{len(profiles)} platform(s) spanning {max(p.account_age_days for p in profiles)} days of activity."
    )

    confidence_label = (
        "High" if breakdown.confidence >= 0.7
        else "Moderate" if breakdown.confidence >= 0.4
        else "Low" if breakdown.confidence >= 0.2
        else "Insufficient"
    )

    # Build data-driven assessment from actual sub-score analysis
    strengths = []
    weaknesses = []
    if breakdown.existence >= 120:
        strengths.append("well-established accounts with significant history")
    elif breakdown.existence < 60:
        weaknesses.append("limited account history or recent account creation")
    if breakdown.consistency >= 120:
        strengths.append("highly stable behavioral patterns across time")
    elif breakdown.consistency < 60:
        weaknesses.append("inconsistent posting patterns or behavioral irregularities")
    if breakdown.engagement >= 100:
        strengths.append("genuine reciprocal engagement with the community")
    elif breakdown.engagement < 50:
        weaknesses.append("shallow or one-directional engagement")
    if breakdown.cross_platform >= 100:
        strengths.append(f"coherent identity verified across {len(profiles)} platform(s)")
    elif len(profiles) == 1:
        weaknesses.append("presence limited to a single platform")
    if breakdown.maturity >= 120:
        strengths.append("deep track record with clean anomaly history")
    elif breakdown.maturity < 60:
        weaknesses.append("limited content history or flagged anomalies")

    strength_text = ""
    if strengths:
        strength_text = f" Key strengths: {'; '.join(strengths)}."
    weakness_text = ""
    if weaknesses:
        weakness_text = f" Areas of concern: {'; '.join(weaknesses)}."

    max_age = max(p.account_age_days for p in profiles)
    total_obs = sum(p.observation_count for p in profiles)

    ai_assessment = (
        f"Behavioral analysis across {len(profiles)} platform(s) based on "
        f"{total_obs} observations spanning {max_age} days of activity. "
        f"Overall trust level: {breakdown.tier} ({breakdown.final_score}/1000) "
        f"with {confidence_label.lower()} confidence ({breakdown.confidence:.0%})."
        f"{strength_text}{weakness_text} "
        f"Recommendation: {confidence_label} confidence for professional engagement."
    )

    # Populate recent activity from TopicEntry records for this identity
    recent_activity_entries = []
    for p in profiles:
        topic_entries = list(db.execute(
            select(TopicEntry).where(
                TopicEntry.author_handle == p.handle,
                TopicEntry.platform == p.platform,
            ).order_by(TopicEntry.published_at.desc()).limit(5)
        ).scalars())
        for te in topic_entries:
            recent_activity_entries.append(ActivityEntry(
                timestamp=te.published_at.isoformat() if te.published_at else "",
                platform=te.platform,
                description=te.title or te.summary or "Activity observed",
            ))

    # Sort by timestamp descending and take top 10
    recent_activity_entries.sort(key=lambda x: x.timestamp, reverse=True)
    recent_activity_entries = recent_activity_entries[:10]

    # Populate network connections from IdentityLink records
    connections_list = []
    seen_handles = set()
    for p in profiles:
        links = list(db.execute(
            select(IdentityLink).where(
                IdentityLink.source_profile_id == p.id,
                IdentityLink.link_type == "interacts_with",
            ).limit(10)
        ).scalars())
        for link in links:
            target = link.target_profile
            if target and target.handle not in seen_handles:
                seen_handles.add(target.handle)
                # Get target's trust score
                target_score = 0
                if target.canonical_identity_id:
                    target_canon = db.get(CanonicalIdentity, target.canonical_identity_id)
                    if target_canon:
                        target_score = target_canon.trust_score
                initials = ""
                if target.display_name:
                    parts = target.display_name.split()
                    initials = "".join(w[0].upper() for w in parts[:2])
                connections_list.append(NetworkConnection(
                    name=target.display_name or target.handle,
                    role=target.claimed_role,
                    trust_score=target_score,
                    initials=initials,
                ))

    # Compute network quality
    network_quality = ""
    if connections_list:
        avg_net_score = sum(c.trust_score for c in connections_list) / len(connections_list)
        net_tier = score_to_tier(int(avg_net_score))
        network_quality = (
            f"{len(connections_list)} connections identified. "
            f"Average network trust score: {int(avg_net_score)} ({net_tier}). "
        )
        if avg_net_score >= 700:
            network_quality += "Strong professional network corroborates claimed identity."
        elif avg_net_score >= 400:
            network_quality += "Moderate network quality with mixed trust signals."
        else:
            network_quality += "Weak network — connections have limited established trust."

    return ReportResponse(
        report_id=str(profile.id),
        handle=handle,
        display_name=profile.display_name,
        platform=platform,
        platforms=[p.platform for p in profiles],
        trust_score=breakdown.final_score,
        tier=breakdown.tier,
        confidence=breakdown.confidence,
        claimed_role=profile.claimed_role,
        claimed_org=profile.claimed_org,
        is_claimed=any(p.is_claimed for p in profiles),
        existence_score=breakdown.existence,
        consistency_score=breakdown.consistency,
        engagement_score=breakdown.engagement,
        cross_platform_score=breakdown.cross_platform,
        maturity_score=breakdown.maturity,
        summary=summary,
        key_findings=findings,
        ai_assessment=ai_assessment,
        signals=signals,
        recent_activity=recent_activity_entries,
        connections=connections_list,
        network_quality=network_quality,
    )


# ---------------------------------------------------------------------------
# GET /v1/health
# ---------------------------------------------------------------------------


@router.get("/health", response_model=HealthResponse)
def health_check(db: Session = Depends(get_db)):
    db_ok = False
    redis_ok = False
    qdrant_ok = False

    try:
        db.execute(select(1))
        db_ok = True
    except Exception:
        pass

    redis_ok = _cache.ping()

    try:
        _vector.client.get_collections()
        qdrant_ok = True
    except Exception:
        pass

    return HealthResponse(
        status="ok" if all([db_ok, redis_ok, qdrant_ok]) else "degraded",
        database=db_ok,
        redis=redis_ok,
        qdrant=qdrant_ok,
    )


# ---------------------------------------------------------------------------
# GET /v1/company/score/{platform}/{handle}
# ---------------------------------------------------------------------------


@router.get("/company/score/{platform}/{handle}", response_model=CompanyScoreResponse)
def get_company_score(platform: str, handle: str, db: Session = Depends(get_db)):
    """Get the trust score for a company on a specific platform.

    Company scoring includes founder scores, product signals, community
    reception, and organizational consistency.
    """
    # Find the best company profile: search by handle, domain, and website platform
    # Pick the one with the most observation data
    candidates = list(db.execute(
        select(CompanyProfile).where(
            (CompanyProfile.handle == handle) | (CompanyProfile.domain == handle)
        )
    ).scalars())

    if candidates:
        # Pick the candidate with the most observations (most data)
        company = max(candidates, key=lambda c: (c.observation_count or 0))
    else:
        company = None

    if not company:
        company = CompanyProfile(
            handle=handle,
            platform=platform,
            domain=handle,
            display_name=handle.capitalize(),
            first_observed_at=datetime.utcnow(),
            observation_count=0,
        )
        db.add(company)
        db.commit()

        # Return a minimal score (will be updated after website scraping)
        return CompanyScoreResponse(
            handle=handle,
            platform=platform,
            entity_type="company",
            trust_score=0,
            tier="untrusted",
            confidence=0.0,
            display_name=handle.capitalize(),
            cached=False,
        )

    # Resolve founder scores
    founder_breakdowns = []
    founders_info = []
    for founder_id in (company.founder_identity_ids or []):
        canon = db.get(CanonicalIdentity, founder_id)
        if not canon:
            continue
        profiles = list(
            db.execute(
                select(IdentityProfile).where(IdentityProfile.canonical_identity_id == canon.id)
            ).scalars()
        )
        if profiles:
            vectors = {str(p.id): compute_behavioral_vector(p) for p in profiles}
            breakdown = compute_trust_score(profiles, vectors)
            founder_breakdowns.append(breakdown)
            founders_info.append({
                "handle": canon.primary_handle,
                "platform": canon.primary_platform,
                "display_name": canon.display_name,
                "trust_score": breakdown.final_score,
                "tier": breakdown.tier,
            })

    result = compute_company_score(company, founder_breakdowns or None)

    # Update stored scores
    company.trust_score = result.final_score
    company.trust_score_breakdown = result.details
    company.founder_score = result.founder
    company.product_score = result.product
    company.community_score = result.community
    company.presence_score = result.presence
    company.execution_score = result.execution
    company.consistency_score = result.consistency
    db.commit()

    return CompanyScoreResponse(
        handle=handle,
        platform=platform,
        trust_score=result.final_score,
        tier=result.tier,
        confidence=result.confidence,
        display_name=company.display_name,
        breakdown={
            "founder": result.founder,
            "product": result.product,
            "community": result.community,
            "presence": result.presence,
            "execution": result.execution,
            "consistency": result.consistency,
            "dampening_factor": result.dampening_factor,
            "details": result.details,
        },
        founder_score=result.founder,
        product_score=result.product,
        community_score=result.community,
        presence_score=result.presence,
        execution_score=result.execution,
        consistency_score=result.consistency,
        founders=founders_info,
    )


# ---------------------------------------------------------------------------
# POST /v1/company/observe
# ---------------------------------------------------------------------------


def _validate_and_enrich_social_links(
    domain: str, platform_accounts: dict
) -> tuple[dict | None, int]:
    """Validate social links belong to this domain and fetch follower counts.

    Anti-phishing: checks that the social account references the domain
    (in bio, website field, or handle). Also enriches with follower data
    from public APIs.

    Returns (validated_accounts, total_followers).
    """
    import httpx

    validated = {}
    total_followers = 0
    domain_clean = domain.lower().replace("www.", "").split(".")[0]  # "venmail" from "venmail.io"

    for platform, handle in platform_accounts.items():
        if not handle:
            continue

        followers = 0
        is_valid = False

        try:
            if platform == "github":
                from app.services.enrichment import fetch_github_profile
                raw = fetch_github_profile(handle)
                if raw:
                    p = raw["profile"]
                    followers = p.get("followers", 0)
                    # Validate: GitHub bio/website/company mentions the domain
                    bio = (p.get("bio") or "").lower()
                    blog = (p.get("blog") or "").lower()
                    company = (p.get("company") or "").lower()
                    login = (p.get("login") or "").lower()
                    is_valid = (
                        domain_clean in bio or domain_clean in blog
                        or domain_clean in company or domain_clean in login
                        or login == domain_clean
                    )

            elif platform == "twitter":
                # Validate by handle similarity to domain (no probe needed)
                is_valid = (
                    domain_clean in handle.lower()
                    or handle.lower().replace("_", "") == domain_clean
                    or handle.lower().startswith(domain_clean)
                )

            elif platform == "linkedin":
                # LinkedIn company handle should match or contain domain
                is_valid = (
                    domain_clean in handle.lower()
                    or handle.lower() == domain_clean
                )

            elif platform in ("youtube", "instagram", "facebook", "tiktok"):
                # Handle should relate to domain name
                handle_clean = handle.lower().replace("_", "").replace("-", "")
                is_valid = (
                    domain_clean in handle_clean
                    or handle_clean.startswith(domain_clean)
                    or domain_clean.startswith(handle_clean)
                )

            else:
                # Unknown platform — accept if handle matches domain
                is_valid = domain_clean in handle.lower()

        except Exception:
            pass

        if is_valid:
            validated[platform] = handle
            total_followers += followers
        else:
            logger.debug("Rejected social link %s/%s for domain %s (not validated)", platform, handle, domain)

    return validated, total_followers


@router.post("/company/observe", response_model=CompanyObservationResponse)
def submit_company_observation(obs: CompanyObservationRequest, db: Session = Depends(get_db)):
    """Submit observation data for a company entity."""
    company = db.execute(
        select(CompanyProfile).where(
            CompanyProfile.handle == obs.handle,
            CompanyProfile.platform == obs.platform,
        )
    ).scalar_one_or_none()

    is_new = company is None

    if is_new:
        company = CompanyProfile(
            handle=obs.handle,
            platform=obs.platform,
            display_name=obs.display_name,
            domain=obs.domain,
            first_observed_at=datetime.utcnow(),
            observation_count=0,
        )
        db.add(company)

    # Update fields from observation
    if obs.display_name:
        company.display_name = obs.display_name
    if obs.domain:
        company.domain = obs.domain
    if obs.description:
        company.description = obs.description
    if obs.team_size is not None:
        company.team_size = obs.team_size
    if obs.github_org:
        company.github_org = obs.github_org
    if obs.total_repos is not None:
        company.total_repos = obs.total_repos
    if obs.total_stars is not None:
        company.total_stars = obs.total_stars
    if obs.total_forks is not None:
        company.total_forks = obs.total_forks
    if obs.commit_frequency_weekly is not None:
        company.commit_frequency_weekly = obs.commit_frequency_weekly
    if obs.contributor_count is not None:
        company.contributor_count = obs.contributor_count
    # platform_accounts is written AFTER validation (below), not here
    if obs.follower_count is not None:
        company.follower_count = obs.follower_count
    if obs.is_verified:
        company.is_verified = True
    if obs.account_age_days is not None:
        company.account_age_days = obs.account_age_days
    if obs.funding_stage:
        company.funding_stage = obs.funding_stage
    if obs.funding_amount_usd is not None:
        company.funding_amount_usd = obs.funding_amount_usd
    if obs.employee_count_estimate is not None:
        company.employee_count_estimate = obs.employee_count_estimate
    if obs.yc_batch:
        company.yc_batch = obs.yc_batch
    if obs.brand_sentiment is not None:
        company.brand_sentiment = obs.brand_sentiment
    if obs.community_size is not None:
        company.community_size = obs.community_size
    if obs.release_cadence_days is not None:
        company.release_cadence_days = obs.release_cadence_days
    if obs.ci_pass_rate is not None:
        company.ci_pass_rate = obs.ci_pass_rate
    if obs.documentation_score is not None:
        company.documentation_score = obs.documentation_score
    if obs.nps_estimate is not None:
        company.nps_estimate = obs.nps_estimate
    if obs.support_response_hours is not None:
        company.support_response_hours = obs.support_response_hours
    if obs.mention_volume_weekly is not None:
        company.mention_volume_weekly = obs.mention_volume_weekly

    # Auto-sync team_size from employee_count when team_size not explicitly set
    if obs.team_size is None and obs.employee_count_estimate is not None:
        company.team_size = obs.employee_count_estimate

    # Resolve founder links
    if obs.founder_handles:
        founder_ids = []
        for fh in obs.founder_handles:
            profile = db.execute(
                select(IdentityProfile).where(
                    IdentityProfile.handle == fh.get("handle", ""),
                    IdentityProfile.platform == fh.get("platform", ""),
                )
            ).scalar_one_or_none()
            if profile and profile.canonical_identity_id:
                founder_ids.append(str(profile.canonical_identity_id))
        if founder_ids:
            company.founder_identity_ids = founder_ids

    # Validate + enrich social links
    if obs.platform_accounts:
        validated = {}
        total_social_followers = 0
        if obs.domain:
            validated, total_social_followers = _validate_and_enrich_social_links(
                obs.domain, obs.platform_accounts
            )
            company.platform_accounts = validated  # Only store validated accounts (empty = phishing)
            if total_social_followers > (company.follower_count or 0):
                company.follower_count = total_social_followers
        else:
            # No domain to validate against — store as-is
            company.platform_accounts = obs.platform_accounts
            validated = obs.platform_accounts
        # Use social account count for community size estimate
        if len(validated or {}) > (company.community_size or 0):
            company.community_size = max(company.community_size or 0, total_social_followers // 10)

    company.observation_count = (company.observation_count or 0) + 1
    company.last_observed_at = datetime.utcnow()

    db.flush()
    db.commit()

    return CompanyObservationResponse(
        company_id=str(company.id),
        handle=company.handle,
        platform=company.platform,
        trust_score=company.trust_score,
        is_new=is_new,
        observation_count=company.observation_count,
    )


# ---------------------------------------------------------------------------
# POST /v1/ingest/{platform}
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Identity resolution helper (synchronous — no Celery needed)
# ---------------------------------------------------------------------------


def _normalize_name(name: str) -> str:
    """Normalize a name for comparison: lowercase, strip accents, remove punctuation."""
    import unicodedata
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = name.lower().replace("'", "").replace("-", " ").replace(".", " ").replace("_", " ")
    return " ".join(name.split())


def _resolve_identity(db: Session, profile: IdentityProfile) -> list[dict]:
    """Run cross-platform identity resolution for a profile.

    Uses three strategies:
    1. Qdrant vector search for behaviorally similar profiles
    2. Direct DB handle-match (same handle on different platforms)
    3. Fuzzy display name match (token overlap, Unicode-normalized)

    Auto-links profiles above threshold or with strong name/handle signal.
    """
    vec = compute_behavioral_vector(profile)

    # Strategy 1: Qdrant vector search
    qdrant_candidates = []
    try:
        qdrant_candidates = _vector.search_similar(vec, exclude_platform=profile.platform, limit=10)
    except Exception:
        pass

    # Strategy 2: Direct handle match in DB (works without Qdrant)
    handle_matches = list(
        db.execute(
            select(IdentityProfile).where(
                IdentityProfile.handle == profile.handle,
                IdentityProfile.platform != profile.platform,
            )
        ).scalars()
    )

    # Also search by display name (fuzzy — Unicode-normalized, token overlap, any order)
    name_matches = []
    other_profiles = list(
        db.execute(
            select(IdentityProfile).where(
                IdentityProfile.platform != profile.platform,
                IdentityProfile.handle != profile.handle,
            )
        ).scalars()
    )

    if profile.display_name:
        name_tokens = set(_normalize_name(profile.display_name).split())
        if name_tokens:
            for op in other_profiles:
                if not op.display_name:
                    continue
                op_tokens = set(_normalize_name(op.display_name).split())
                overlap = name_tokens & op_tokens
                # Match if: exact same tokens (any order, any count), OR significant overlap
                if overlap and (
                    name_tokens == op_tokens
                    or (len(overlap) >= 2)
                    or (len(overlap) >= 1 and len(overlap) / max(len(name_tokens), len(op_tokens)) >= 0.6)
                ):
                    name_matches.append(op)
    else:
        # No display name — try matching handle as substring of other profiles' names
        handle_slug = _normalize_name(profile.handle).replace(" ", "")
        if len(handle_slug) >= 4:
            for op in other_profiles:
                if op.display_name:
                    op_slug = _normalize_name(op.display_name).replace(" ", "")
                    if handle_slug in op_slug or op_slug in handle_slug:
                        name_matches.append(op)

    # Merge candidates — collect unique profiles to evaluate
    seen = set()
    candidates_to_check: list[IdentityProfile] = []

    for match in handle_matches:
        key = (match.handle, match.platform)
        if key not in seen:
            seen.add(key)
            candidates_to_check.append(match)

    for match in name_matches:
        key = (match.handle, match.platform)
        if key not in seen:
            seen.add(key)
            candidates_to_check.append(match)

    for cand in qdrant_candidates:
        key = (cand["handle"], cand["platform"])
        if key not in seen:
            seen.add(key)
            cand_profile = db.execute(
                select(IdentityProfile).where(
                    IdentityProfile.handle == cand["handle"],
                    IdentityProfile.platform == cand["platform"],
                )
            ).scalar_one_or_none()
            if cand_profile:
                candidates_to_check.append(cand_profile)

    linked = []
    for cand_profile in candidates_to_check:
        # Skip if already linked to same canonical
        if (profile.canonical_identity_id and cand_profile.canonical_identity_id
                and profile.canonical_identity_id == cand_profile.canonical_identity_id):
            continue

        cand_vec = compute_behavioral_vector(cand_profile)
        result = compute_identity_similarity(profile, cand_profile, vec, cand_vec)

        # Strong signals that lower the auto-link threshold
        exact_handle = profile.handle.lower() == cand_profile.handle.lower()
        exact_name = (profile.display_name and cand_profile.display_name
                      and profile.display_name.lower() == cand_profile.display_name.lower())
        # Same name tokens in any order (e.g., "Opata Chibueze" == "Chibueze Opata")
        name_tokens_match = False
        if profile.display_name and cand_profile.display_name:
            a_tokens = set(_normalize_name(profile.display_name).split())
            b_tokens = set(_normalize_name(cand_profile.display_name).split())
            overlap = a_tokens & b_tokens
            name_tokens_match = (
                (a_tokens == b_tokens and len(a_tokens) >= 1)  # exact match including single names
                or (len(overlap) >= 2)  # 2+ common tokens
                or (len(a_tokens) >= 2 and len(overlap) / max(len(a_tokens), len(b_tokens)) >= 0.6)
            )

        # Handle-in-name match (e.g., handle="opatachibueze", name="Chibueze Opata" on other profile)
        handle_name_match = False
        if not name_tokens_match:
            h_slug = _normalize_name(profile.handle).replace(" ", "")
            if len(h_slug) >= 4:
                if cand_profile.display_name:
                    c_slug = _normalize_name(cand_profile.display_name).replace(" ", "")
                    handle_name_match = h_slug in c_slug or c_slug in h_slug

        should_link = result.decision == "auto_link"
        if not should_link and (exact_handle or exact_name or name_tokens_match or handle_name_match) and result.overall_score >= 0.40:
            should_link = True

        if should_link:
            from app.models import LinkType
            link = IdentityLink(
                source_profile_id=profile.id,
                target_profile_id=cand_profile.id,
                link_type=LinkType.same_person.value,
                similarity_score=result.overall_score,
                confidence=result.overall_score,
            )
            db.merge(link)
            _ensure_shared_canonical(db, profile, cand_profile)
            linked.append({"handle": cand_profile.handle, "platform": cand_profile.platform, "similarity": result.overall_score})

    return linked


def _ensure_shared_canonical(db: Session, profile_a: IdentityProfile, profile_b: IdentityProfile) -> None:
    """Ensure two profiles share a canonical identity."""
    if profile_a.canonical_identity_id and profile_b.canonical_identity_id:
        if profile_a.canonical_identity_id == profile_b.canonical_identity_id:
            return
        db.execute(
            IdentityProfile.__table__.update()
            .where(IdentityProfile.canonical_identity_id == profile_b.canonical_identity_id)
            .values(canonical_identity_id=profile_a.canonical_identity_id)
        )
    elif profile_a.canonical_identity_id:
        profile_b.canonical_identity_id = profile_a.canonical_identity_id
    elif profile_b.canonical_identity_id:
        profile_a.canonical_identity_id = profile_b.canonical_identity_id
    else:
        canonical = CanonicalIdentity(
            primary_handle=profile_a.handle,
            primary_platform=profile_a.platform,
            display_name=profile_a.display_name or profile_b.display_name,
        )
        db.add(canonical)
        db.flush()
        profile_a.canonical_identity_id = canonical.id
        profile_b.canonical_identity_id = canonical.id


# ---------------------------------------------------------------------------
# POST /v1/ingest/{platform}
# ---------------------------------------------------------------------------


@router.post("/ingest/{platform}")
def ingest_platform_data(platform: str, raw_data: dict, db: Session = Depends(get_db)):
    """Ingest raw platform data through the normalization pipeline.

    Accepts raw scrape data for any supported platform, normalizes it
    through the appropriate adapter, and creates/updates the profile
    with extracted behavioral signals and topic fingerprints.
    """
    observation = normalize_observation(platform, raw_data)
    if not observation:
        raise HTTPException(status_code=400, detail=f"Unsupported platform: {platform}")

    # Route to company or individual observation
    if observation.entity_type == "company":
        company_obs = CompanyObservationRequest(
            handle=observation.handle,
            platform=observation.platform,
            display_name=observation.display_name,
            github_org=observation.github_org,
            total_repos=observation.total_repos,
            total_stars=observation.total_stars,
            funding_stage=observation.funding_stage,
            yc_batch=observation.yc_batch,
            founder_handles=observation.founder_handles,
        )
        return submit_company_observation(company_obs, db)

    # Individual observation
    profile = db.execute(
        select(IdentityProfile).where(
            IdentityProfile.handle == observation.handle,
            IdentityProfile.platform == observation.platform,
        )
    ).scalar_one_or_none()

    is_new = profile is None
    if is_new:
        profile = IdentityProfile(
            handle=observation.handle,
            platform=observation.platform,
            display_name=observation.display_name,
            first_observed_at=datetime.utcnow(),
            observation_count=0,
            version=0,
        )
        db.add(profile)

    # Apply normalized signals to profile
    if observation.display_name:
        profile.display_name = observation.display_name
    if observation.account_age_days:
        profile.account_age_days = observation.account_age_days
    if observation.profile_completeness:
        profile.profile_completeness = observation.profile_completeness
    if observation.is_verified:
        profile.is_verified = True
    if observation.audience_size:
        profile.audience_size = observation.audience_size
    if observation.following_count and observation.audience_size:
        profile.audience_quality_ratio = min(observation.audience_size / max(observation.following_count, 1), 10.0) / 10.0

    # Voice signals
    if observation.avg_utterance_length:
        profile.avg_utterance_length = observation.avg_utterance_length
    if observation.vocabulary_richness:
        profile.vocabulary_richness = observation.vocabulary_richness
    if observation.formality_index != 0.5:
        profile.formality_index = observation.formality_index
    if observation.question_ratio:
        profile.question_ratio = observation.question_ratio
    if observation.hashtag_rate:
        profile.hashtag_rate = observation.hashtag_rate
    if observation.link_sharing_rate:
        profile.link_sharing_rate = observation.link_sharing_rate

    # Social signals
    if observation.engagement_depth_ratio:
        profile.engagement_depth_ratio = observation.engagement_depth_ratio
    if observation.reciprocity_rate:
        profile.reciprocity_rate = observation.reciprocity_rate
    if observation.endorsement_count:
        profile.endorsement_count = observation.endorsement_count
    if observation.collaboration_signals:
        profile.collaboration_signals = observation.collaboration_signals

    # Topic signals
    if observation.keyword_fingerprint:
        profile.keyword_fingerprint = observation.keyword_fingerprint
    if observation.category_fingerprint:
        profile.category_fingerprint = observation.category_fingerprint
    if observation.claimed_role:
        profile.claimed_role = observation.claimed_role[:255]
    if observation.claimed_org:
        profile.claimed_org = observation.claimed_org[:255]

    # Presence
    if observation.posts_per_week_avg:
        profile.posts_per_week_avg = observation.posts_per_week_avg
    if observation.active_weeks_ratio:
        profile.active_weeks_ratio = observation.active_weeks_ratio
    if observation.growth_organicity:
        profile.growth_organicity = observation.growth_organicity

    # Scoring engine fields
    if observation.regularity_score:
        profile.regularity_score = observation.regularity_score
    if observation.emotional_volatility:
        profile.emotional_volatility = observation.emotional_volatility
    if observation.posts_per_week_variance:
        profile.posts_per_week_variance = observation.posts_per_week_variance
    if observation.platform_tenure_days:
        profile.platform_tenure_days = observation.platform_tenure_days
    if observation.authority_index:
        profile.authority_index = observation.authority_index
    if observation.mention_response_rate:
        profile.mention_response_rate = observation.mention_response_rate
    if observation.active_weeks_ratio:
        profile.active_weeks_ratio = observation.active_weeks_ratio
    profile.anomaly_count = observation.anomaly_count

    # Chronotype — build hourly distribution from activity hours
    if observation.activity_hours:
        hourly = [0.0] * 24
        for h in observation.activity_hours:
            if 0 <= h < 24:
                hourly[h] += 1
        total = sum(hourly) or 1
        profile.hourly_distribution = [round(v / total, 4) for v in hourly]

    if observation.activity_days:
        daily = [0.0] * 7
        for d in observation.activity_days:
            if 0 <= d < 7:
                daily[d] += 1
        total = sum(daily) or 1
        profile.daily_distribution = [round(v / total, 4) for v in daily]
        weekend = daily[5] + daily[6]
        profile.weekend_ratio = round(weekend / total, 4) if total else 0.0

    profile.observation_count += 1
    profile.last_observed_at = datetime.utcnow()
    profile.version += 1

    db.flush()

    # Compute and upsert behavioral vector
    vec = compute_behavioral_vector(profile)
    try:
        _vector.upsert_profile(profile, vec)
    except Exception as e:
        logger.debug("Qdrant upsert skipped (ingest): %s", e)

    # Run identity resolution (find and link cross-platform profiles)
    linked_profiles = _resolve_identity(db, profile)

    # Invalidate caches
    _cache.invalidate_profile(observation.handle, observation.platform)
    if profile.canonical_identity_id:
        _cache.invalidate_score(str(profile.canonical_identity_id))

    db.commit()

    return {
        "profile_id": str(profile.id),
        "handle": profile.handle,
        "platform": profile.platform,
        "entity_type": observation.entity_type,
        "is_new": is_new,
        "observation_count": profile.observation_count,
        "topics_extracted": len(observation.keyword_fingerprint),
        "categories": list(observation.category_fingerprint.keys()),
        "linked_profiles": linked_profiles,
    }


# ===========================================================================
# TOPIC INTELLIGENCE API — real-time information layer for agent queries
# ===========================================================================


# ---------------------------------------------------------------------------
# POST /v1/topics/search
# ---------------------------------------------------------------------------


@router.post("/topics/search", response_model=TopicSearchResponse)
def search_topics(req: TopicSearchRequest, db: Session = Depends(get_db)):
    """Real-time topic search across all ingested sources.

    Designed for agent consumption — returns structured results with
    trust-weighted ranking, category/country filtering, and time-window
    scoping. Similar to exa.ai but with Trustgate's identity layer.

    Example queries:
      - {"query": "semiconductor supply chain", "window_hours": 24}
      - {"query": "AI regulation", "countries": ["US", "GB"], "categories": ["politics"]}
      - {"query": "rust programming", "platforms": ["hackernews", "reddit"]}
    """
    q = TopicQuery(
        query=req.query,
        categories=req.categories,
        platforms=req.platforms,
        countries=req.countries,
        continents=req.continents,
        languages=req.languages,
        window_hours=req.window_hours,
        min_trust_score=req.min_trust_score,
        min_engagement=req.min_engagement,
        limit=req.limit,
        offset=req.offset,
    )

    result = query_topics(db, q)

    return TopicSearchResponse(
        query=result.query,
        window_hours=result.window_hours,
        total_results=result.total_results,
        results=[
            TopicEntryResponse(
                id=r.id,
                title=r.title,
                summary=r.summary,
                url=r.url,
                platform=r.platform,
                author_handle=r.author_handle,
                author_name=r.author_name,
                author_trust_score=r.author_trust_score,
                published_at=r.published_at,
                categories=r.categories,
                keywords=r.keywords,
                entities=r.entities,
                sentiment=r.sentiment,
                engagement_score=r.engagement_score,
                country_code=r.country_code,
                language=r.language,
                source_name=r.source_name,
                source_reliability=r.source_reliability,
            )
            for r in result.results
        ],
        categories_found=result.categories_found,
        top_sources=result.top_sources,
    )


# ---------------------------------------------------------------------------
# POST /v1/topics/ingest
# ---------------------------------------------------------------------------


@router.post("/topics/ingest", response_model=FeedIngestResponse)
def ingest_topic_items(req: FeedIngestRequest, db: Session = Depends(get_db)):
    """Ingest topic entries from a social platform or external source.

    This is the topic pipeline ingestion endpoint (distinct from
    /v1/ingest/{platform} which is the identity pipeline).

    Use this to push social media posts, forum threads, or news items
    into the topic index for real-time query.
    """
    new_count = ingest_social_items(
        db=db,
        platform=req.platform,
        items=req.items,
        country_code=req.country_code,
        language=req.language,
    )

    return FeedIngestResponse(
        platform=req.platform,
        new_entries=new_count,
        total_items=len(req.items),
    )


# ---------------------------------------------------------------------------
# GET /v1/topics/sources
# ---------------------------------------------------------------------------


@router.get("/topics/sources", response_model=list[FeedSourceResponse])
def list_feed_sources(
    country: str | None = None,
    continent: str | None = None,
    category: str | None = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    """List registered feed sources, optionally filtered by geography or category."""
    stmt = select(FeedSource)

    if active_only:
        stmt = stmt.where(FeedSource.is_active == True)
    if country:
        stmt = stmt.where(FeedSource.country_code == country.upper())
    if continent:
        stmt = stmt.where(FeedSource.continent == continent.upper())
    if category:
        stmt = stmt.where(FeedSource.category == category)

    stmt = stmt.order_by(FeedSource.continent, FeedSource.country_code, FeedSource.name)
    sources = list(db.execute(stmt).scalars())

    return [
        FeedSourceResponse(
            id=str(s.id),
            name=s.name,
            url=s.url,
            feed_type=s.feed_type,
            source_type=s.source_type,
            category=s.category,
            language=s.language,
            country_code=s.country_code,
            continent=s.continent,
            reliability_score=s.reliability_score,
            is_active=s.is_active,
            last_fetched_at=s.last_fetched_at.isoformat() if s.last_fetched_at else None,
        )
        for s in sources
    ]


# ---------------------------------------------------------------------------
# GET /v1/topics/categories
# ---------------------------------------------------------------------------


@router.get("/topics/categories")
def get_topic_categories(window_hours: int = 24, db: Session = Depends(get_db)):
    """Get a summary of active topic categories in the given time window.

    Returns category counts and trending signals for the specified period.
    """
    from datetime import timedelta, timezone as tz

    cutoff = datetime.now(tz.utc) - timedelta(hours=window_hours)

    entries = list(
        db.execute(
            select(TopicEntry).where(TopicEntry.published_at >= cutoff)
        ).scalars()
    )

    cat_counts: dict[str, int] = {}
    cat_engagement: dict[str, int] = {}
    platform_counts: dict[str, int] = {}
    country_counts: dict[str, int] = {}

    for entry in entries:
        for cat in (entry.category_fingerprint or {}):
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
            cat_engagement[cat] = cat_engagement.get(cat, 0) + entry.engagement_score
        platform_counts[entry.platform] = platform_counts.get(entry.platform, 0) + 1
        country_counts[entry.country_code] = country_counts.get(entry.country_code, 0) + 1

    return {
        "window_hours": window_hours,
        "total_entries": len(entries),
        "categories": dict(sorted(cat_counts.items(), key=lambda x: -x[1])),
        "category_engagement": dict(sorted(cat_engagement.items(), key=lambda x: -x[1])),
        "platforms": dict(sorted(platform_counts.items(), key=lambda x: -x[1])),
        "countries": dict(sorted(country_counts.items(), key=lambda x: -x[1])),
    }


# ===========================================================================
# SCRAPE & DISCOVERY API — backend-driven profile scraping via Playwright
# ===========================================================================


# ---------------------------------------------------------------------------
# POST /v1/scrape/enqueue
# ---------------------------------------------------------------------------


@router.post("/scrape/enqueue", response_model=ScrapeResponse)
def enqueue_scrape(req: ScrapeRequest, db: Session = Depends(get_db)):
    """Enqueue a profile for backend scraping via the Playwright pool.

    The extension calls this when it discovers a cross-platform link
    but the profile doesn't exist in the database yet.
    """
    import uuid

    # Check if profile already exists and was recently observed
    existing = db.execute(
        select(IdentityProfile).where(
            IdentityProfile.handle == req.handle,
            IdentityProfile.platform == req.platform,
        )
    ).scalar_one_or_none()

    if existing and existing.observation_count > 0:
        return ScrapeResponse(
            job_id="existing",
            platform=req.platform,
            handle=req.handle,
            status="already_exists",
        )

    job_id = str(uuid.uuid4())

    # Fire-and-forget Celery dispatch (non-blocking; degrades if Redis down)
    status = "queued"
    import threading

    def _dispatch():
        try:
            from app.workers import scrape_profile_task
            scrape_profile_task.apply_async(
                args=[req.platform, req.handle, req.url or ""],
                expires=300,
            )
        except Exception:
            pass

    threading.Thread(target=_dispatch, daemon=True).start()

    return ScrapeResponse(
        job_id=job_id,
        platform=req.platform,
        handle=req.handle,
        status=status,
    )


# ---------------------------------------------------------------------------
# POST /v1/discover/{handle}
# ---------------------------------------------------------------------------


@router.post("/discover/{handle}", response_model=DiscoverResponse)
def discover_profiles(handle: str, req: DiscoverRequest | None = None, db: Session = Depends(get_db)):
    """Discover related profiles across platforms for a given handle.

    First checks for linked profiles in the database, then falls back
    to enqueuing a Playwright-based search.
    """
    discovered = []

    # Strategy 1: Check database for existing linked profiles
    profiles = list(
        db.execute(select(IdentityProfile).where(IdentityProfile.handle == handle)).scalars()
    )

    if profiles:
        # If we have a canonical identity, find all linked profiles
        for p in profiles:
            if p.canonical_identity_id:
                linked = list(
                    db.execute(
                        select(IdentityProfile).where(
                            IdentityProfile.canonical_identity_id == p.canonical_identity_id,
                            IdentityProfile.handle != handle,
                        )
                    ).scalars()
                )
                for lp in linked:
                    from app.services.scraper import PLATFORM_PROFILE_URLS
                    url_template = PLATFORM_PROFILE_URLS.get(lp.platform, "")
                    discovered.append(DiscoveredProfile(
                        platform=lp.platform,
                        handle=lp.handle,
                        url=url_template.format(handle=lp.handle) if url_template else "",
                        confidence=0.9,
                    ))

    # Strategy 2: If we have a display name, try search-based discovery via Celery
    display_name = None
    if req and req.display_name:
        display_name = req.display_name
    elif profiles:
        display_name = profiles[0].display_name

    if display_name and len(discovered) < 3:
        import threading

        def _dispatch_discover():
            try:
                from app.workers import discover_profiles_task
                discover_profiles_task.apply_async(
                    args=[handle, display_name, req.source_platform if req else None],
                    expires=300,
                )
            except Exception:
                pass

        threading.Thread(target=_dispatch_discover, daemon=True).start()

    return DiscoverResponse(
        handle=handle,
        discovered=discovered,
    )


# ---------------------------------------------------------------------------
# POST /v1/enrich/{platform}/{handle}
# ---------------------------------------------------------------------------


@router.post("/enrich/{platform}/{handle}", response_model=EnrichResponse)
def enrich_profile(platform: str, handle: str, db: Session = Depends(get_db)):
    """Enrich a profile by discovering and ingesting cross-platform data.

    This is the main endpoint the extension calls after initial ingestion.
    It queries public APIs (GitHub, HN, Reddit) for the same handle,
    ingests any found profiles, runs identity resolution, and returns
    the updated cross-platform score.
    """
    from app.services.enrichment import discover_and_fetch

    # Get the source profile (must already be ingested)
    source = db.execute(
        select(IdentityProfile).where(
            IdentityProfile.handle == handle,
            IdentityProfile.platform == platform,
        )
    ).scalar_one_or_none()

    display_name = source.display_name if source else None

    # Discover profiles on other platforms via public APIs
    discovered = discover_and_fetch(handle, display_name, exclude_platform=platform)
    platforms_found = []
    profiles_ingested = 0
    total_linked = 0

    for entry in discovered:
        plat = entry["platform"]
        raw = entry.get("raw_data")
        platforms_found.append(plat)

        # Probe-only results (existence confirmed but no data) — create stub profile
        if entry.get("probe_only") or raw is None:
            stub_handle = entry["handle"]
            existing = db.execute(
                select(IdentityProfile).where(
                    IdentityProfile.handle == stub_handle,
                    IdentityProfile.platform == plat,
                )
            ).scalar_one_or_none()
            if not existing:
                stub = IdentityProfile(
                    handle=stub_handle, platform=plat,
                    display_name=display_name,
                    first_observed_at=datetime.utcnow(),
                    observation_count=0, version=0,
                )
                db.add(stub)
                db.flush()
                _resolve_identity(db, stub)
                profiles_ingested += 1
            # Enqueue Playwright scrape for full data
            import threading
            def _enqueue_scrape(p=plat, h=stub_handle):
                try:
                    from app.workers import scrape_profile_task
                    scrape_profile_task.apply_async(args=[p, h, ""], expires=300)
                except Exception:
                    pass
            threading.Thread(target=_enqueue_scrape, daemon=True).start()
            continue

        # Normal result with data — ingest through normalization pipeline
        obs = normalize_observation(plat, raw)
        if not obs:
            continue

        profile = db.execute(
            select(IdentityProfile).where(
                IdentityProfile.handle == obs.handle,
                IdentityProfile.platform == obs.platform,
            )
        ).scalar_one_or_none()

        is_new = profile is None
        if is_new:
            profile = IdentityProfile(
                handle=obs.handle,
                platform=obs.platform,
                display_name=obs.display_name,
                first_observed_at=datetime.utcnow(),
                observation_count=0,
                version=0,
            )
            db.add(profile)

        # Apply signals — inherit display_name from source if missing
        if obs.display_name:
            profile.display_name = obs.display_name
        elif not profile.display_name and display_name:
            profile.display_name = display_name
        if obs.account_age_days:
            profile.account_age_days = obs.account_age_days
        if obs.audience_size:
            profile.audience_size = obs.audience_size
        if obs.profile_completeness:
            profile.profile_completeness = obs.profile_completeness
        if obs.is_verified:
            profile.is_verified = True
        if obs.claimed_role:
            profile.claimed_role = obs.claimed_role[:255]
        if obs.claimed_org:
            profile.claimed_org = obs.claimed_org[:255]
        if obs.keyword_fingerprint:
            profile.keyword_fingerprint = obs.keyword_fingerprint
        if obs.category_fingerprint:
            profile.category_fingerprint = obs.category_fingerprint
        if obs.endorsement_count:
            profile.endorsement_count = obs.endorsement_count
        if obs.avg_utterance_length:
            profile.avg_utterance_length = obs.avg_utterance_length
        if obs.vocabulary_richness:
            profile.vocabulary_richness = obs.vocabulary_richness
        if obs.formality_index != 0.5:
            profile.formality_index = obs.formality_index
        if obs.engagement_depth_ratio:
            profile.engagement_depth_ratio = obs.engagement_depth_ratio
        if obs.collaboration_signals:
            profile.collaboration_signals = obs.collaboration_signals
        if obs.posts_per_week_avg:
            profile.posts_per_week_avg = obs.posts_per_week_avg
        # Scoring engine fields
        if obs.regularity_score:
            profile.regularity_score = obs.regularity_score
        if obs.emotional_volatility:
            profile.emotional_volatility = obs.emotional_volatility
        if obs.posts_per_week_variance:
            profile.posts_per_week_variance = obs.posts_per_week_variance
        if obs.platform_tenure_days:
            profile.platform_tenure_days = obs.platform_tenure_days
        if obs.authority_index:
            profile.authority_index = obs.authority_index
        if obs.mention_response_rate:
            profile.mention_response_rate = obs.mention_response_rate
        if obs.active_weeks_ratio:
            profile.active_weeks_ratio = obs.active_weeks_ratio
        profile.anomaly_count = obs.anomaly_count
        if obs.activity_hours:
            hourly = [0.0] * 24
            for h in obs.activity_hours:
                if 0 <= h < 24:
                    hourly[h] += 1
            total = sum(hourly) or 1
            profile.hourly_distribution = [round(v / total, 4) for v in hourly]
        if obs.activity_days:
            daily = [0.0] * 7
            for d in obs.activity_days:
                if 0 <= d < 7:
                    daily[d] += 1
            total = sum(daily) or 1
            profile.daily_distribution = [round(v / total, 4) for v in daily]

        profile.observation_count += 1
        profile.last_observed_at = datetime.utcnow()
        profile.version += 1

        db.flush()

        # Compute vector and upsert
        vec = compute_behavioral_vector(profile)
        try:
            _vector.upsert_profile(profile, vec)
        except Exception:
            pass

        profiles_ingested += 1

        # Run identity resolution for this newly ingested profile
        linked = _resolve_identity(db, profile)
        total_linked += len(linked)

    # Also re-run resolution for the source profile with new data in Qdrant
    if source:
        linked = _resolve_identity(db, source)
        total_linked += len(linked)

    db.commit()

    # Compute the updated score
    trust_score = 0
    tier = "untrusted"
    confidence = 0.0
    num_platforms = 1

    if source:
        if source.canonical_identity_id:
            all_profiles = list(
                db.execute(
                    select(IdentityProfile).where(
                        IdentityProfile.canonical_identity_id == source.canonical_identity_id
                    )
                ).scalars()
            )
        else:
            all_profiles = [source]

        num_platforms = len(all_profiles)
        vectors = {str(p.id): compute_behavioral_vector(p) for p in all_profiles}
        breakdown = compute_trust_score(all_profiles, vectors)
        trust_score = breakdown.final_score
        tier = breakdown.tier
        confidence = breakdown.confidence

        # Update cached score
        if source.canonical_identity_id:
            _cache.invalidate_score(str(source.canonical_identity_id))

    return EnrichResponse(
        handle=handle,
        platform=platform,
        trust_score=trust_score,
        tier=tier,
        confidence=confidence,
        num_platforms=num_platforms,
        platforms_found=platforms_found,
        profiles_ingested=profiles_ingested,
        profiles_linked=total_linked,
    )


# ===========================================================================
# ADMIN — Browser session management for authenticated scraping
# ===========================================================================


def _require_admin(x_admin_key: str = Header(...)):
    """Dependency: validates admin API key from X-Admin-Key header."""
    from app.config import settings
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Invalid admin key")


def _run_async(coro):
    """Run an async coroutine from a sync FastAPI endpoint.

    Uses a dedicated background thread with a persistent event loop so
    Playwright contexts survive between login → confirm calls.
    """
    import asyncio
    import concurrent.futures

    loop = _get_admin_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    try:
        return future.result(timeout=60)
    except concurrent.futures.TimeoutError:
        return {"status": "error", "message": "Operation timed out"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


_admin_loop = None
_admin_thread = None


def _get_admin_loop():
    """Get (or create) a persistent event loop running in a background thread.

    This loop stays alive for the lifetime of the process, so Playwright
    browser contexts created in one request are still accessible in the next.
    """
    import asyncio
    import threading

    global _admin_loop, _admin_thread

    if _admin_loop is not None and _admin_loop.is_running():
        return _admin_loop

    _admin_loop = asyncio.new_event_loop()

    def _run():
        asyncio.set_event_loop(_admin_loop)
        _admin_loop.run_forever()

    _admin_thread = threading.Thread(target=_run, daemon=True)
    _admin_thread.start()
    return _admin_loop


# ---------------------------------------------------------------------------
# GET /v1/admin/auth/status
# ---------------------------------------------------------------------------


@router.get("/admin/auth/status", response_model=AuthStatusResponse, dependencies=[Depends(_require_admin)])
def admin_auth_status():
    """List all platforms and their browser session status."""
    from app.services.scraper import get_scraper_pool

    pool = get_scraper_pool()
    platforms = pool.get_all_status_sync()
    return AuthStatusResponse(platforms=platforms)


# ---------------------------------------------------------------------------
# POST /v1/admin/auth/login/{platform}
# ---------------------------------------------------------------------------


@router.post("/admin/auth/login/{platform}", response_model=AuthActionResponse, dependencies=[Depends(_require_admin)])
def admin_auth_login(platform: str):
    """Open a visible browser for the admin to log into a platform.

    The browser window opens with the platform's login page. The admin
    completes login (including 2FA/captchas), then calls confirm.
    """
    from app.services.scraper import get_scraper_pool, PLATFORM_LOGIN_URLS

    if platform not in PLATFORM_LOGIN_URLS:
        raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}. Supported: {list(PLATFORM_LOGIN_URLS.keys())}")

    pool = get_scraper_pool()
    result = _run_async(pool.open_login_browser(platform))

    return AuthActionResponse(
        status=result.get("status", "error"),
        platform=platform,
        message=result.get("message", ""),
        login_url=result.get("login_url"),
    )


# ---------------------------------------------------------------------------
# POST /v1/admin/auth/confirm/{platform}
# ---------------------------------------------------------------------------


@router.post("/admin/auth/confirm/{platform}", response_model=AuthActionResponse, dependencies=[Depends(_require_admin)])
def admin_auth_confirm(platform: str):
    """Verify login succeeded in the visible browser, then close it.

    Call this after the admin has completed login in the browser window
    opened by the login endpoint.
    """
    from app.services.scraper import get_scraper_pool

    pool = get_scraper_pool()
    result = _run_async(pool.confirm_login(platform))

    return AuthActionResponse(
        status=result.get("status", "error"),
        platform=platform,
        message=result.get("message", ""),
        validated=result.get("validated"),
    )


# ---------------------------------------------------------------------------
# POST /v1/admin/auth/logout/{platform}
# ---------------------------------------------------------------------------


@router.post("/admin/auth/logout/{platform}", response_model=AuthActionResponse, dependencies=[Depends(_require_admin)])
def admin_auth_logout(platform: str):
    """Clear the browser profile for a platform (removes all session data)."""
    from app.services.scraper import get_scraper_pool

    pool = get_scraper_pool()
    result = _run_async(pool.clear_profile(platform))

    return AuthActionResponse(
        status=result.get("status", "error"),
        platform=platform,
        message=result.get("message", ""),
    )


# ---------------------------------------------------------------------------
# POST /v1/admin/auth/validate/{platform}
# ---------------------------------------------------------------------------


@router.post("/admin/auth/validate/{platform}", dependencies=[Depends(_require_admin)])
def admin_auth_validate(platform: str):
    """Test if a platform session is still valid (headless check)."""
    from app.services.scraper import get_scraper_pool

    pool = get_scraper_pool()
    return _run_async(pool.validate_session(platform))


# ---------------------------------------------------------------------------
# POST /v1/profile/claim — initiate profile ownership claim
# ---------------------------------------------------------------------------

_VALID_VERIFICATION_METHODS = {"platform_bio", "dns_txt", "oauth_token"}


@router.post("/profile/claim", response_model=ClaimResponse)
def create_claim(req: ClaimRequest, db: Session = Depends(get_db)):
    """Initiate a profile ownership claim.

    Generates a unique challenge string that the user must place in their
    platform bio (or prove via DNS/OAuth) within 1 hour.
    """
    if req.verification_method not in _VALID_VERIFICATION_METHODS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid verification_method. Must be one of: {', '.join(sorted(_VALID_VERIFICATION_METHODS))}",
        )

    # Look up the profile
    profile = db.execute(
        select(IdentityProfile).where(
            IdentityProfile.handle == req.handle,
            IdentityProfile.platform == req.platform,
        )
    ).scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail=f"No profile found for {req.handle} on {req.platform}")

    if profile.is_claimed:
        raise HTTPException(status_code=409, detail="This profile has already been claimed")

    # Generate challenge
    challenge_hex = _uuid.uuid4().hex[:12]
    challenge = f"trustgate-verify-{challenge_hex}"

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=1)

    claim = PendingClaim(
        handle=req.handle,
        platform=req.platform,
        canonical_identity_id=profile.canonical_identity_id,
        challenge=challenge,
        verification_method=req.verification_method,
        expires_at=expires_at,
        created_at=now,
        status="pending",
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)

    return ClaimResponse(
        claim_id=str(claim.id),
        challenge=challenge,
        verification_method=req.verification_method,
        expires_at=expires_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# POST /v1/profile/verify — verify a pending claim
# ---------------------------------------------------------------------------


@router.post("/profile/verify", response_model=VerifyResponse)
def verify_claim(req: VerifyRequest, db: Session = Depends(get_db)):
    """Verify a pending profile claim by submitting proof.

    For v1, proof must match the challenge string exactly (platform_bio method:
    the challenge string should appear in the profile's bio).
    """
    # Parse claim_id
    try:
        claim_uuid = _uuid.UUID(req.claim_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid claim_id format")

    claim = db.get(PendingClaim, claim_uuid)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    # Check if already verified
    if claim.status == "verified":
        return VerifyResponse(
            verified=True,
            canonical_id=str(claim.canonical_identity_id) if claim.canonical_identity_id else None,
            message="Claim was already verified",
        )

    # Check expiry
    now = datetime.now(timezone.utc)
    claim_expires = claim.expires_at
    if claim_expires.tzinfo is None:
        claim_expires = claim_expires.replace(tzinfo=timezone.utc)
    if now > claim_expires:
        claim.status = "expired"
        db.commit()
        raise HTTPException(status_code=410, detail="Claim has expired")

    # Validate proof — for v1, proof must equal the challenge
    if req.proof != claim.challenge:
        return VerifyResponse(
            verified=False,
            canonical_id=None,
            message="Proof does not match challenge",
        )

    # Proof matches — mark profile as claimed
    claim.status = "verified"

    profile = db.execute(
        select(IdentityProfile).where(
            IdentityProfile.handle == claim.handle,
            IdentityProfile.platform == claim.platform,
        )
    ).scalar_one_or_none()

    if profile:
        profile.is_claimed = True

        # Also mark canonical identity if linked
        if profile.canonical_identity_id:
            canonical = db.get(CanonicalIdentity, profile.canonical_identity_id)
            if canonical:
                canonical.claimed_by_user_id = claim.id

            # Invalidate score cache for this identity
            _cache.invalidate_score(str(profile.canonical_identity_id))

        # Invalidate profile cache
        _cache.invalidate_profile(claim.handle, claim.platform)

    db.commit()

    canonical_id = str(profile.canonical_identity_id) if profile and profile.canonical_identity_id else None

    return VerifyResponse(
        verified=True,
        canonical_id=canonical_id,
        message="Profile claimed successfully",
    )
