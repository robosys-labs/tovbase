"""Celery background workers for profile refresh, identity resolution, and vector recomputation."""

from __future__ import annotations

from datetime import datetime

from celery import Celery
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import CanonicalIdentity, FeedSource, IdentityLink, IdentityProfile, LinkType
from app.services.cache import CacheService
from app.services.scoring import compute_trust_score
from app.services.similarity import compute_identity_similarity
from app.services.vector import VectorService, compute_behavioral_vector

celery_app = Celery("tovbase", broker=settings.redis_url, backend=settings.redis_url)

_cache = CacheService()
_vector = VectorService()


@celery_app.task(name="tovbase.recompute_vector")
def recompute_vector_task(profile_id: str) -> dict:
    """Recompute the behavioral vector for a profile and upsert to Qdrant."""
    db = SessionLocal()
    try:
        from uuid import UUID

        profile = db.get(IdentityProfile, UUID(profile_id))
        if not profile:
            return {"status": "not_found", "profile_id": profile_id}

        vec = compute_behavioral_vector(profile)
        _vector.upsert_profile(profile, vec)

        return {"status": "ok", "profile_id": profile_id}
    finally:
        db.close()


@celery_app.task(name="tovbase.resolve_identity")
def resolve_identity_task(profile_id: str) -> dict:
    """Attempt cross-platform identity resolution for a profile.

    Searches Qdrant for similar profiles on other platforms, computes
    multi-signal similarity, and auto-links or flags for review.
    """
    db = SessionLocal()
    try:
        from uuid import UUID

        profile = db.get(IdentityProfile, UUID(profile_id))
        if not profile:
            return {"status": "not_found"}

        vec = compute_behavioral_vector(profile)

        # Search for candidates on other platforms
        candidates = _vector.search_similar(vec, exclude_platform=profile.platform, limit=10)

        linked = []
        flagged = []

        for candidate in candidates:
            cand_profile = db.execute(
                select(IdentityProfile).where(
                    IdentityProfile.handle == candidate["handle"],
                    IdentityProfile.platform == candidate["platform"],
                )
            ).scalar_one_or_none()

            if not cand_profile:
                continue

            cand_vec = compute_behavioral_vector(cand_profile)
            result = compute_identity_similarity(profile, cand_profile, vec, cand_vec)

            if result.decision == "auto_link":
                # Create identity link
                link = IdentityLink(
                    source_profile_id=profile.id,
                    target_profile_id=cand_profile.id,
                    link_type=LinkType.same_person.value,
                    similarity_score=result.overall_score,
                    confidence=result.overall_score,
                )
                db.merge(link)

                # Ensure both profiles share a canonical identity
                _ensure_shared_canonical(db, profile, cand_profile)

                linked.append({
                    "handle": cand_profile.handle,
                    "platform": cand_profile.platform,
                    "similarity": result.overall_score,
                })

            elif result.decision == "review":
                flagged.append({
                    "handle": cand_profile.handle,
                    "platform": cand_profile.platform,
                    "similarity": result.overall_score,
                })

        db.commit()

        return {"status": "ok", "linked": linked, "flagged": flagged}
    finally:
        db.close()


def _ensure_shared_canonical(
    db, profile_a: IdentityProfile, profile_b: IdentityProfile
) -> None:
    """Ensure two profiles that are the same person share a canonical identity."""
    if profile_a.canonical_identity_id and profile_b.canonical_identity_id:
        if profile_a.canonical_identity_id == profile_b.canonical_identity_id:
            return  # Already linked
        # Merge: move all of B's canonical profiles to A's canonical
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
        # Neither has a canonical — create one
        canonical = CanonicalIdentity(
            primary_handle=profile_a.handle,
            primary_platform=profile_a.platform,
            display_name=profile_a.display_name or profile_b.display_name,
        )
        db.add(canonical)
        db.flush()
        profile_a.canonical_identity_id = canonical.id
        profile_b.canonical_identity_id = canonical.id


@celery_app.task(name="tovbase.refresh_score")
def refresh_score_task(canonical_id: str) -> dict:
    """Recompute and cache the trust score for a canonical identity."""
    db = SessionLocal()
    try:
        from uuid import UUID

        canonical = db.get(CanonicalIdentity, UUID(canonical_id))
        if not canonical:
            return {"status": "not_found"}

        profiles = list(
            db.execute(
                select(IdentityProfile).where(
                    IdentityProfile.canonical_identity_id == canonical.id
                )
            ).scalars()
        )

        vectors = {str(p.id): compute_behavioral_vector(p) for p in profiles}
        breakdown = compute_trust_score(profiles, vectors)

        canonical.trust_score = breakdown.final_score
        canonical.trust_score_breakdown = breakdown.details
        canonical.trust_score_computed_at = datetime.utcnow()
        db.commit()

        # Cache
        _cache.set_score(
            canonical_id,
            {
                "final_score": breakdown.final_score,
                "tier": breakdown.tier,
                "confidence": breakdown.confidence,
                "existence": breakdown.existence,
                "consistency": breakdown.consistency,
                "engagement": breakdown.engagement,
                "cross_platform": breakdown.cross_platform,
                "maturity": breakdown.maturity,
                "details": breakdown.details,
            },
        )

        return {"status": "ok", "score": breakdown.final_score, "tier": breakdown.tier}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Topic pipeline workers
# ---------------------------------------------------------------------------


@celery_app.task(name="tovbase.fetch_feed")
def fetch_feed_task(source_id: str) -> dict:
    """Fetch and ingest a single RSS/Atom feed source."""
    import urllib.request

    from app.services.topics import ingest_feed_items, parse_feed

    db = SessionLocal()
    try:
        from uuid import UUID

        source = db.get(FeedSource, UUID(source_id))
        if not source or not source.is_active:
            return {"status": "skipped", "reason": "inactive or not found"}

        # Fetch feed content
        try:
            req = urllib.request.Request(source.url, headers={"User-Agent": "Tovbase/1.0 (Feed Fetcher)"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                xml_content = resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            source.error_count += 1
            db.commit()
            return {"status": "error", "error": str(e), "error_count": source.error_count}

        # Parse and ingest
        items = parse_feed(xml_content)
        new_count = ingest_feed_items(db, source, items)

        return {
            "status": "ok",
            "source": source.name,
            "items_parsed": len(items),
            "new_entries": new_count,
        }
    finally:
        db.close()


@celery_app.task(name="tovbase.fetch_all_feeds")
def fetch_all_feeds_task() -> dict:
    """Fetch all active feed sources that are due for refresh."""
    from datetime import timedelta, timezone

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        sources = list(db.execute(
            select(FeedSource).where(FeedSource.is_active == True)
        ).scalars())

        queued = 0
        skipped = 0

        for source in sources:
            # Check if source is due for fetch
            if source.last_fetched_at:
                next_fetch = source.last_fetched_at + timedelta(minutes=source.fetch_interval_minutes)
                if now < next_fetch:
                    skipped += 1
                    continue

            fetch_feed_task.delay(str(source.id))
            queued += 1

        return {"status": "ok", "queued": queued, "skipped": skipped, "total_sources": len(sources)}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Profile scraping via Playwright
# ---------------------------------------------------------------------------


@celery_app.task(name="tovbase.scrape_profile")
def scrape_profile_task(platform: str, handle: str, url: str = "") -> dict:
    """Scrape a profile using the 3-tier crawler fallback (API → Lightpanda → Playwright)."""
    import asyncio
    from app.services.crawler import crawl_profile
    from app.services.ingestion import normalize_observation

    async def _run():
        result = await crawl_profile(platform, handle)
        return result.raw_data, result.source

    try:
        raw_data, source = asyncio.run(_run())
    except Exception as e:
        return {"status": "error", "error": f"Scrape failed: {e}"}

    if not raw_data:
        return {"status": "error", "error": "No data scraped"}

    # Run through the normalization + ingestion pipeline
    observation = normalize_observation(platform, raw_data)
    if not observation:
        return {"status": "error", "error": f"Normalization failed for {platform}"}

    db = SessionLocal()
    try:
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
            )
            db.add(profile)

        # Apply signals
        if observation.display_name:
            profile.display_name = observation.display_name
        if observation.account_age_days:
            profile.account_age_days = observation.account_age_days
        if observation.audience_size:
            profile.audience_size = observation.audience_size
        if observation.profile_completeness:
            profile.profile_completeness = observation.profile_completeness
        if observation.is_verified:
            profile.is_verified = True
        if observation.claimed_role:
            profile.claimed_role = observation.claimed_role[:255]
        if observation.claimed_org:
            profile.claimed_org = observation.claimed_org[:255]
        if observation.keyword_fingerprint:
            profile.keyword_fingerprint = observation.keyword_fingerprint
        if observation.category_fingerprint:
            profile.category_fingerprint = observation.category_fingerprint
        if observation.endorsement_count:
            profile.endorsement_count = observation.endorsement_count

        profile.observation_count += 1
        profile.last_observed_at = datetime.utcnow()
        profile.version += 1

        db.flush()

        # Compute vector
        vec = compute_behavioral_vector(profile)
        try:
            _vector.upsert_profile(profile, vec)
        except Exception:
            pass

        # Invalidate caches
        _cache.invalidate_profile(observation.handle, observation.platform)
        if profile.canonical_identity_id:
            _cache.invalidate_score(str(profile.canonical_identity_id))

        db.commit()

        return {
            "status": "ok",
            "profile_id": str(profile.id),
            "handle": profile.handle,
            "platform": profile.platform,
            "is_new": is_new,
        }
    finally:
        db.close()


@celery_app.task(name="tovbase.discover_profiles")
def discover_profiles_task(handle: str, display_name: str, exclude_platform: str | None = None) -> dict:
    """Search for related profiles across platforms using the Playwright pool."""
    import asyncio
    from app.services.scraper import get_scraper_pool

    async def _run():
        pool = get_scraper_pool()
        return await pool.discover_profiles(display_name, exclude_platform)

    try:
        discovered = asyncio.run(_run())
    except Exception as e:
        return {"status": "error", "error": str(e)}

    # For each discovered profile, enqueue a scrape
    enqueued = 0
    for profile in discovered:
        try:
            scrape_profile_task.delay(profile["platform"], profile["handle"], profile.get("url", ""))
            enqueued += 1
        except Exception:
            pass

    return {"status": "ok", "discovered": len(discovered), "enqueued": enqueued}
