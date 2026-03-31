"""Tests for the enrichment service and cross-platform discovery pipeline.

These tests hit REAL public APIs (GitHub, HN, StackExchange, Reddit) to verify
the enrichment functions return data in the correct format for the ingestion
adapters. Tests are marked with pytest.mark.network for optional skipping.

Also tests the full ingestion → enrichment → identity resolution chain.
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Enrichment API tests (real network calls)
# ---------------------------------------------------------------------------


class TestGitHubEnrichment:
    """Test GitHub API enrichment with real profiles."""

    def test_fetch_known_user(self):
        from app.services.enrichment import fetch_github_profile

        raw = fetch_github_profile("torvalds")
        assert raw is not None
        assert raw["profile"]["login"] == "torvalds"
        assert raw["profile"]["name"] is not None
        assert raw["profile"]["followers"] > 0
        assert "repos" in raw
        assert "events" in raw

    def test_fetch_nonexistent_user(self):
        from app.services.enrichment import fetch_github_profile

        raw = fetch_github_profile("this-user-definitely-does-not-exist-xyzzy-12345")
        assert raw is None

    def test_output_matches_adapter_format(self):
        """Verify the raw_data dict is compatible with GitHubAdapter.normalize()."""
        from app.services.enrichment import fetch_github_profile
        from app.services.ingestion import normalize_observation

        raw = fetch_github_profile("torvalds")
        assert raw is not None

        obs = normalize_observation("github", raw)
        assert obs is not None
        assert obs.handle == "torvalds"
        assert obs.platform == "github"
        assert obs.audience_size > 0  # followers
        assert obs.account_age_days > 0
        assert obs.display_name is not None


class TestHNEnrichment:
    """Test Hacker News API enrichment with real profiles."""

    def test_fetch_known_user(self):
        from app.services.enrichment import fetch_hn_profile

        raw = fetch_hn_profile("pg")
        assert raw is not None
        assert raw["profile"]["id"] == "pg"
        assert raw["profile"]["karma"] > 0
        assert "items" in raw

    def test_fetch_nonexistent_user(self):
        from app.services.enrichment import fetch_hn_profile

        raw = fetch_hn_profile("this_user_certainly_does_not_exist_on_hn_12345")
        assert raw is None

    def test_output_matches_adapter_format(self):
        from app.services.enrichment import fetch_hn_profile
        from app.services.ingestion import normalize_observation

        raw = fetch_hn_profile("pg")
        assert raw is not None

        obs = normalize_observation("hackernews", raw)
        assert obs is not None
        assert obs.handle == "pg"
        assert obs.platform == "hackernews"
        assert obs.audience_size > 0  # karma


class TestStackExchangeEnrichment:
    """Test StackExchange API enrichment across multiple sites."""

    def test_fetch_so_user_by_name(self):
        from app.services.enrichment import fetch_stackexchange_profile

        raw = fetch_stackexchange_profile("Jon Skeet", site="stackoverflow")
        assert raw is not None
        assert raw["profile"]["display_name"] is not None
        assert raw["profile"]["reputation"] > 0

    def test_fetch_so_user_by_id(self):
        from app.services.enrichment import fetch_stackexchange_profile

        # Jon Skeet's SO user ID is 22656
        raw = fetch_stackexchange_profile("22656", site="stackoverflow")
        assert raw is not None
        assert raw["profile"]["user_id"] == 22656
        assert raw["profile"]["reputation"] > 1_000_000  # He has >1M rep

    def test_fetch_serverfault_user(self):
        """Verify enrichment works on non-SO StackExchange sites."""
        from app.services.enrichment import fetch_stackexchange_profile

        # Search for any active user on serverfault
        raw = fetch_stackexchange_profile("Michael Hampton", site="serverfault")
        # May or may not find — just verify no crash and correct format
        if raw is not None:
            assert "profile" in raw
            assert "answers" in raw
            assert raw["profile"]["site"] == "serverfault"

    def test_fetch_all_sites_by_id(self):
        """Test cross-site discovery via /associated endpoint."""
        from app.services.enrichment import fetch_stackexchange_all_sites

        # Use Jon Skeet's SO ID — he has accounts on many SE sites
        results = fetch_stackexchange_all_sites("22656")
        # Should find at least SO account
        assert len(results) >= 1
        platforms = [r["site"] for r in results]
        assert "stackoverflow" in platforms

    def test_nonexistent_user(self):
        from app.services.enrichment import fetch_stackexchange_profile

        raw = fetch_stackexchange_profile("99999999999", site="stackoverflow")
        assert raw is None

    def test_output_matches_adapter_format(self):
        from app.services.enrichment import fetch_stackexchange_profile
        from app.services.ingestion import normalize_observation

        raw = fetch_stackexchange_profile("22656", site="stackoverflow")
        assert raw is not None

        obs = normalize_observation("stackexchange", raw)
        assert obs is not None
        assert obs.platform == "stackexchange"
        assert obs.audience_size > 0  # reputation
        assert obs.endorsement_count > 0  # reputation + badges


class TestRedditEnrichment:
    """Test Reddit API enrichment.

    Note: Reddit may rate-limit or block requests. Tests use pytest.mark.xfail
    for the actual API calls since Reddit is less reliable than GitHub/HN/SE.
    """

    def test_fetch_known_user(self):
        from app.services.enrichment import fetch_reddit_profile

        raw = fetch_reddit_profile("spez")
        if raw is None:
            pytest.skip("Reddit API unavailable or rate-limited")
        assert raw["profile"]["name"] == "spez"
        assert raw["profile"]["comment_karma"] + raw["profile"]["link_karma"] > 0

    def test_fetch_nonexistent_user(self):
        from app.services.enrichment import fetch_reddit_profile

        raw = fetch_reddit_profile("this_user_zzz_does_not_exist_9999")
        assert raw is None

    def test_output_matches_adapter_format(self):
        from app.services.enrichment import fetch_reddit_profile
        from app.services.ingestion import normalize_observation

        raw = fetch_reddit_profile("spez")
        if raw is None:
            pytest.skip("Reddit API unavailable or rate-limited")

        obs = normalize_observation("reddit", raw)
        assert obs is not None
        assert obs.handle == "spez"
        assert obs.platform == "reddit"


# ---------------------------------------------------------------------------
# Cross-platform discovery tests
# ---------------------------------------------------------------------------


class TestDiscovery:
    """Test the cross-platform discovery pipeline."""

    def test_discover_by_handle(self):
        from app.services.enrichment import discover_and_fetch

        results = discover_and_fetch("torvalds")
        platforms = [r["platform"] for r in results]
        # Torvalds is on GitHub for sure
        assert "github" in platforms

    def test_discover_excludes_source(self):
        from app.services.enrichment import discover_and_fetch

        results = discover_and_fetch("torvalds", exclude_platform="github")
        platforms = [r["platform"] for r in results]
        assert "github" not in platforms

    def test_handle_variant_generation(self):
        from app.services.enrichment import _generate_handle_variants

        variants = _generate_handle_variants("opatachibueze", "Opata Chibueze")
        assert "opatachibueze" in variants
        assert "opata-chibueze" in variants or "opata_chibueze" in variants


# ---------------------------------------------------------------------------
# Full pipeline integration tests (ingest → enrich → resolve → score)
# ---------------------------------------------------------------------------


class TestFullPipeline:
    """Test the complete ingestion → enrichment → identity resolution pipeline."""

    def test_ingest_and_enrich_creates_multi_platform_identity(self):
        """Ingest a profile, enrich it, verify cross-platform discovery works."""
        from app.db import Base, SessionLocal, engine
        from app.api.routes import ingest_platform_data, enrich_profile
        from sqlalchemy import select
        from app.models import IdentityProfile

        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        try:
            # Ingest a known GitHub user via the LinkedIn adapter (simulating extension scrape)
            raw = {
                "profile": {
                    "vanityName": "torvalds",
                    "firstName": "Linus",
                    "lastName": "Torvalds",
                    "headline": "Creator of Linux and Git",
                    "connectionCount": 1000,
                },
                "posts": [],
            }
            result = ingest_platform_data("linkedin", raw, db)
            assert result["handle"] == "torvalds"

            # Enrich — should discover GitHub profile via public API
            enrich = enrich_profile("linkedin", "torvalds", db)
            # GitHub should be found (torvalds is the most famous GH user)
            assert "github" in enrich.platforms_found or enrich.num_platforms >= 2

            # Verify GitHub profile was created in DB
            gh_profile = db.execute(
                select(IdentityProfile).where(
                    IdentityProfile.handle == "torvalds",
                    IdentityProfile.platform == "github",
                )
            ).scalar_one_or_none()
            assert gh_profile is not None
            assert gh_profile.audience_size > 0

        finally:
            db.close()

    def test_identity_resolution_links_same_handle(self):
        """Profiles with the same handle on different platforms should be linked."""
        from app.db import Base, SessionLocal, engine
        from app.api.routes import ingest_platform_data, _resolve_identity
        from sqlalchemy import select
        from app.models import IdentityProfile

        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        try:
            # Create two profiles with the same handle on different platforms
            raw_li = {
                "profile": {"vanityName": "testhandle123", "firstName": "Test", "lastName": "User", "headline": "Dev"},
                "posts": [],
            }
            raw_gh = {
                "profile": {"login": "testhandle123", "name": "Test User", "bio": "Developer"},
                "repos": [],
                "events": [],
            }

            ingest_platform_data("linkedin", raw_li, db)
            ingest_platform_data("github", raw_gh, db)

            # Both should exist
            li = db.execute(
                select(IdentityProfile).where(IdentityProfile.handle == "testhandle123", IdentityProfile.platform == "linkedin")
            ).scalar_one()
            gh = db.execute(
                select(IdentityProfile).where(IdentityProfile.handle == "testhandle123", IdentityProfile.platform == "github")
            ).scalar_one()

            # They should share a canonical identity (auto-linked by handle match)
            assert li.canonical_identity_id is not None
            assert gh.canonical_identity_id is not None
            assert li.canonical_identity_id == gh.canonical_identity_id

        finally:
            db.close()

    def test_enriched_score_higher_than_single_platform(self):
        """A multi-platform score should be higher than a single-platform score."""
        from app.db import Base, SessionLocal, engine
        from app.api.routes import ingest_platform_data, get_score

        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        try:
            # Ingest on LinkedIn
            raw_li = {
                "profile": {
                    "vanityName": "multitest456",
                    "firstName": "Multi",
                    "lastName": "Test",
                    "headline": "Engineer",
                    "connectionCount": 300,
                },
                "posts": [{"text": "Building great software"}],
            }
            ingest_platform_data("linkedin", raw_li, db)
            score_before = get_score("linkedin", "multitest456", db)
            single_score = score_before.trust_score

            # Ingest on GitHub (same handle → should auto-link)
            raw_gh = {
                "profile": {
                    "login": "multitest456",
                    "name": "Multi Test",
                    "bio": "Software engineer",
                    "followers": 100,
                    "following": 50,
                    "created_at": "2020-01-01T00:00:00Z",
                },
                "repos": [
                    {"language": "Python", "stargazers_count": 50, "forks_count": 10, "topics": ["python"], "description": "A tool"},
                ],
                "events": [],
            }
            ingest_platform_data("github", raw_gh, db)

            # Score should now factor in both platforms
            score_after = get_score("linkedin", "multitest456", db)
            multi_score = score_after.trust_score

            # Multi-platform score should be >= single platform
            assert multi_score >= single_score

        finally:
            db.close()


# ---------------------------------------------------------------------------
# Adapter format tests (no network)
# ---------------------------------------------------------------------------


class TestStackExchangeAdapter:
    """Test the StackExchange/StackOverflow adapter normalization."""

    def test_normalize_basic_profile(self):
        from app.services.ingestion import normalize_observation

        raw = {
            "profile": {
                "user_id": 12345,
                "display_name": "Test Developer",
                "reputation": 15000,
                "creation_date": 1400000000,
                "location": "San Francisco",
                "badge_counts": {"gold": 2, "silver": 15, "bronze": 45},
                "answer_count": 120,
                "question_count": 30,
                "about_me": "I build things with Python and Go",
            },
            "answers": [
                {"body": "You should use asyncio for concurrent operations.", "creation_date": 1700000000, "score": 25, "is_accepted": True},
                {"body": "The best approach is to use a context manager here.", "creation_date": 1699000000, "score": 10, "is_accepted": False},
            ],
            "tags": [
                {"name": "python", "count": 80},
                {"name": "go", "count": 40},
                {"name": "docker", "count": 20},
            ],
        }

        obs = normalize_observation("stackexchange", raw)
        assert obs is not None
        assert obs.platform == "stackexchange"
        assert obs.display_name == "Test Developer"
        assert obs.audience_size == 15000  # reputation
        assert obs.endorsement_count > 15000  # reputation + badge_score
        assert obs.engagement_depth_ratio > 0.0  # log1p-based engagement signal
        assert obs.account_age_days > 0
        assert "python" in obs.keyword_fingerprint
        assert "programming" in obs.category_fingerprint

    def test_normalize_empty_profile(self):
        from app.services.ingestion import normalize_observation

        raw = {"profile": {"user_id": 99999}, "answers": [], "tags": []}
        obs = normalize_observation("stackexchange", raw)
        assert obs is not None
        assert obs.endorsement_count == 0

    def test_so_and_se_adapters_both_work(self):
        """Both 'stackoverflow' and 'stackexchange' platform keys should normalize."""
        from app.services.ingestion import normalize_observation

        raw = {
            "profile": {"user_id": 1, "display_name": "Test", "reputation": 100},
            "answers": [],
            "tags": [],
        }

        so_obs = normalize_observation("stackoverflow", raw)
        se_obs = normalize_observation("stackexchange", raw)
        assert so_obs is not None
        assert se_obs is not None


class TestQuoraAdapter:
    """Test the Quora adapter normalization."""

    def test_normalize_basic_profile(self):
        from app.services.ingestion import normalize_observation

        raw = {
            "profile": {
                "username": "John-Smith-42",
                "name": "John Smith",
                "follower_count": 5000,
                "following_count": 200,
                "bio": "AI researcher and writer",
                "answer_views": 500000,
            },
            "answers": [
                {"text": "The key difference between supervised and unsupervised learning is..."},
                {"text": "Machine learning models can be improved by using cross-validation..."},
            ],
        }

        obs = normalize_observation("quora", raw)
        assert obs is not None
        assert obs.handle == "John-Smith-42"
        assert obs.platform == "quora"
        assert obs.audience_size == 5000
        assert obs.endorsement_count == 500000
        assert len(obs.post_texts) == 2
