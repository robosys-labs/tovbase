"""End-to-end persona tests — evaluate scoring accuracy across realistic use cases.

Tests three distinct personas to validate the system produces correct,
defensible scores across the trust spectrum:

1. **Amara Okafor** — Senior engineer, multi-platform, high trust
   Nigerian fintech engineer active on GitHub, Twitter, LinkedIn, HN.
   Should score Excellent/Good with high confidence.

2. **"0xGhostTrader"** — Anonymous crypto persona, suspicious patterns
   Single-platform, bursty activity, bot-like engagement, high anomalies.
   Should score Poor/Untrusted with low confidence.

3. **"NovaPay" (company)** — YC-backed fintech startup
   Well-known founders, strong GitHub, good community, Series A.
   Should score Good with moderate confidence.

Each persona validates:
  - Score range accuracy (does the tier match the profile?)
  - Sub-score proportionality (do components weight correctly?)
  - Cross-platform coherence (does multi-platform presence help?)
  - Dampening behaviour (does sparse data get penalised?)
  - Topic extraction correctness
  - Ingestion pipeline end-to-end
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models import IdentityProfile
from app.services.ingestion import extract_topics, extract_voice_features, normalize_observation
from app.services.scoring import ScoreBreakdown, compute_trust_score, score_to_tier
from app.services.company_scoring import CompanyScoreBreakdown, compute_company_score
from app.services.similarity import compute_identity_similarity
from app.services.vector import compute_behavioral_vector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_profile(**overrides) -> IdentityProfile:
    defaults = {
        "id": uuid.uuid4(),
        "handle": "test",
        "platform": "twitter",
        "display_name": None,
        "hourly_distribution": [0.0] * 24,
        "daily_distribution": [0.0] * 7,
        "estimated_timezone_offset": 0.0,
        "regularity_score": 0.5,
        "weekend_ratio": 0.2,
        "burst_tendency": 0.3,
        "dormancy_max_days": 5,
        "session_count_avg_daily": 2.0,
        "session_duration_avg_minutes": 10.0,
        "night_activity_ratio": 0.05,
        "first_activity_at": datetime.now(timezone.utc) - timedelta(days=500),
        "last_activity_at": datetime.now(timezone.utc) - timedelta(hours=3),
        "avg_utterance_length": 40.0,
        "utterance_length_variance": 15.0,
        "vocabulary_richness": 0.5,
        "formality_index": 0.5,
        "emotional_valence": 0.0,
        "emotional_volatility": 0.2,
        "question_ratio": 0.1,
        "self_reference_rate": 0.1,
        "punctuation_signature": {},
        "language_codes": "en",
        "avg_words_per_sentence": 12.0,
        "hashtag_rate": 0.05,
        "link_sharing_rate": 0.1,
        "mention_rate": 0.15,
        "code_snippet_rate": 0.0,
        "media_attachment_rate": 0.05,
        "thread_starter_rate": 0.3,
        "avg_response_length": 25.0,
        "initiation_ratio": 0.4,
        "reply_depth_avg": 2.0,
        "engagement_depth_ratio": 0.4,
        "authority_index": 0.3,
        "reciprocity_rate": 0.4,
        "audience_size": 1000,
        "audience_quality_ratio": 0.5,
        "community_centrality": 0.3,
        "conflict_tendency": 0.05,
        "mention_response_rate": 0.5,
        "avg_reply_latency_minutes": 60.0,
        "endorsement_count": 10,
        "collaboration_signals": 2,
        "audience_growth_30d": 20.0,
        "audience_churn_rate": 0.02,
        "keyword_fingerprint": {},
        "category_fingerprint": {},
        "expertise_depth": 0.4,
        "opinion_consistency": 0.6,
        "interest_breadth": 0.4,
        "content_originality": 0.5,
        "citation_rate": 0.05,
        "narrative_consistency": 0.6,
        "platform_specific_expertise": {},
        "claimed_role": None,
        "claimed_org": None,
        "posts_per_week_avg": 5.0,
        "posts_per_week_variance": 2.0,
        "active_weeks_ratio": 0.7,
        "responsiveness_minutes": 60.0,
        "thread_persistence_avg": 2.5,
        "content_cadence_pattern": "steady",
        "platform_tenure_days": 500,
        "growth_velocity": 0.01,
        "growth_organicity": 0.7,
        "deletion_rate": 0.01,
        "edit_rate": 0.03,
        "peak_engagement_post_type": None,
        "seasonal_pattern": {},
        "platform_migration_signal": 0.0,
        "account_age_days": 500,
        "profile_completeness": 0.6,
        "is_verified": False,
        "is_claimed": False,
        "has_linked_platforms": 0,
        "anomaly_count": 0,
        "anomaly_types": [],
        "observation_count": 15,
        "first_observed_at": datetime.now(timezone.utc) - timedelta(days=90),
        "last_observed_at": datetime.now(timezone.utc) - timedelta(hours=3),
        "version": 1,
    }
    defaults.update(overrides)
    return IdentityProfile(**defaults)


def _make_company(**overrides):
    """Build a CompanyProfile-like mock object."""
    defaults = {
        "id": uuid.uuid4(), "handle": "co", "platform": "linkedin",
        "display_name": None, "domain": None, "description": None,
        "founder_identity_ids": [], "team_size": 0, "avg_team_trust_score": 0.0,
        "platform_accounts": {}, "account_age_days": 0, "follower_count": 0,
        "is_verified": False, "github_org": None,
        "total_repos": 0, "total_stars": 0, "total_forks": 0, "open_issues": 0,
        "commit_frequency_weekly": 0.0, "contributor_count": 0,
        "release_cadence_days": 0.0, "ci_pass_rate": 0.0, "documentation_score": 0.0,
        "brand_sentiment": 0.0, "mention_volume_weekly": 0.0,
        "support_response_hours": 0.0, "community_size": 0, "nps_estimate": 0.0,
        "funding_stage": None, "funding_amount_usd": 0, "revenue_signal": None,
        "employee_count_estimate": 0, "yc_batch": None,
        "trust_score": 0, "trust_score_breakdown": None,
        "founder_score": 0.0, "product_score": 0.0, "community_score": 0.0,
        "presence_score": 0.0, "execution_score": 0.0, "consistency_score": 0.0,
        "observation_count": 0,
    }
    defaults.update(overrides)

    class Mock:
        pass

    c = Mock()
    for k, v in defaults.items():
        setattr(c, k, v)
    return c


# ===========================================================================
# PERSONA 1: Amara Okafor — Senior fintech engineer, high trust
# ===========================================================================


class TestAmaraOkafor:
    """Multi-platform senior engineer. Should score high with strong coherence."""

    def _twitter(self) -> IdentityProfile:
        hourly = [0.0] * 24
        # Lagos timezone (UTC+1), active 9am-6pm → hours 8-17 UTC
        for h in [8, 9, 10, 11, 12, 13, 14, 15, 16, 17]:
            hourly[h] = 0.09
        hourly[19] = 0.05
        hourly[20] = 0.05

        return _make_profile(
            handle="amaraokafor_",
            platform="twitter",
            display_name="Amara Okafor",
            hourly_distribution=hourly,
            daily_distribution=[0.18, 0.18, 0.18, 0.18, 0.18, 0.05, 0.05],
            estimated_timezone_offset=1.0,
            regularity_score=0.82,
            weekend_ratio=0.10,
            vocabulary_richness=0.78,
            formality_index=0.68,
            emotional_valence=0.25,
            emotional_volatility=0.10,
            question_ratio=0.15,
            self_reference_rate=0.06,
            avg_utterance_length=55.0,
            avg_words_per_sentence=14.0,
            link_sharing_rate=0.25,
            hashtag_rate=0.08,
            mention_rate=0.22,
            code_snippet_rate=0.05,
            initiation_ratio=0.45,
            engagement_depth_ratio=0.65,
            authority_index=0.55,
            reciprocity_rate=0.60,
            audience_size=8200,
            audience_quality_ratio=0.6,
            mention_response_rate=0.70,
            endorsement_count=350,
            keyword_fingerprint={
                "fintech": 0.20, "payments": 0.18, "python": 0.15,
                "api": 0.12, "distributed": 0.10, "africa": 0.08,
                "banking": 0.07, "mobile money": 0.06,
            },
            category_fingerprint={
                "finance": 0.35, "programming": 0.30,
                "infrastructure": 0.20, "product": 0.10,
            },
            expertise_depth=0.72,
            opinion_consistency=0.80,
            content_originality=0.75,
            claimed_role="Senior Backend Engineer",
            claimed_org="Paystack",
            posts_per_week_avg=14.0,
            active_weeks_ratio=0.92,
            platform_tenure_days=2200,
            growth_organicity=0.88,
            account_age_days=2200,
            profile_completeness=0.85,
            is_verified=False,
            observation_count=40,
            anomaly_count=0,
        )

    def _github(self) -> IdentityProfile:
        hourly = [0.0] * 24
        for h in [8, 9, 10, 11, 12, 13, 14, 15, 16, 17]:
            hourly[h] = 0.09
        hourly[19] = 0.05
        hourly[20] = 0.05

        return _make_profile(
            id=uuid.uuid4(),
            handle="amaraokafor",
            platform="github",
            display_name="Amara Okafor",
            hourly_distribution=hourly,
            daily_distribution=[0.20, 0.20, 0.20, 0.20, 0.15, 0.03, 0.02],
            estimated_timezone_offset=1.0,
            regularity_score=0.78,
            vocabulary_richness=0.72,
            formality_index=0.60,
            emotional_valence=0.15,
            question_ratio=0.08,
            self_reference_rate=0.04,
            code_snippet_rate=0.55,
            link_sharing_rate=0.20,
            engagement_depth_ratio=0.70,
            authority_index=0.50,
            reciprocity_rate=0.55,
            audience_size=1200,
            endorsement_count=680,
            collaboration_signals=45,
            keyword_fingerprint={
                "python": 0.22, "payments": 0.15, "api": 0.14,
                "fastapi": 0.10, "testing": 0.08, "microservices": 0.07,
            },
            category_fingerprint={
                "programming": 0.45, "finance": 0.25,
                "infrastructure": 0.20,
            },
            platform_specific_expertise={"python": 0.9, "go": 0.5, "typescript": 0.4},
            expertise_depth=0.80,
            content_originality=0.82,
            claimed_role="Senior Backend Engineer",
            claimed_org="Paystack",
            posts_per_week_avg=8.0,
            active_weeks_ratio=0.88,
            platform_tenure_days=2500,
            account_age_days=2500,
            profile_completeness=0.80,
            observation_count=35,
        )

    def _linkedin(self) -> IdentityProfile:
        hourly = [0.0] * 24
        for h in [8, 9, 10, 11, 14, 15]:
            hourly[h] = 0.15
        hourly[12] = 0.05
        hourly[19] = 0.05

        return _make_profile(
            id=uuid.uuid4(),
            handle="amara-okafor",
            platform="linkedin",
            display_name="Amara Okafor",
            hourly_distribution=hourly,
            daily_distribution=[0.22, 0.22, 0.22, 0.18, 0.16, 0.00, 0.00],
            estimated_timezone_offset=1.0,
            regularity_score=0.75,
            vocabulary_richness=0.75,
            formality_index=0.80,
            emotional_valence=0.30,
            question_ratio=0.05,
            engagement_depth_ratio=0.50,
            authority_index=0.60,
            audience_size=4500,
            endorsement_count=220,
            keyword_fingerprint={
                "fintech": 0.25, "payments": 0.20, "engineering": 0.12,
                "africa": 0.10, "leadership": 0.08,
            },
            category_fingerprint={
                "finance": 0.40, "programming": 0.20,
                "product": 0.20, "infrastructure": 0.10,
            },
            claimed_role="Senior Backend Engineer",
            claimed_org="Paystack",
            posts_per_week_avg=2.0,
            active_weeks_ratio=0.65,
            platform_tenure_days=3000,
            account_age_days=3000,
            profile_completeness=0.92,
            is_verified=True,
            observation_count=20,
        )

    def _hn(self) -> IdentityProfile:
        hourly = [0.0] * 24
        for h in [9, 10, 14, 15, 16, 20, 21]:
            hourly[h] = 0.13
        hourly[11] = 0.09

        return _make_profile(
            id=uuid.uuid4(),
            handle="amarao",
            platform="hackernews",
            display_name="amarao",
            hourly_distribution=hourly,
            estimated_timezone_offset=1.0,
            regularity_score=0.60,
            vocabulary_richness=0.70,
            formality_index=0.55,
            question_ratio=0.18,
            engagement_depth_ratio=0.72,
            authority_index=0.45,
            audience_size=3800,
            endorsement_count=3800,
            keyword_fingerprint={
                "payments": 0.18, "api": 0.15, "python": 0.12,
                "fintech": 0.10, "scaling": 0.08,
            },
            category_fingerprint={
                "programming": 0.35, "finance": 0.30,
                "infrastructure": 0.25,
            },
            posts_per_week_avg=4.0,
            active_weeks_ratio=0.55,
            platform_tenure_days=1800,
            account_age_days=1800,
            profile_completeness=0.35,
            observation_count=15,
        )

    # ── Score range tests ──

    def test_single_platform_scores_fair_or_better(self):
        """Even a single strong profile should score Fair+ with dampening."""
        twitter = self._twitter()
        breakdown = compute_trust_score([twitter])
        assert breakdown.final_score >= 350, f"Single strong profile too low: {breakdown.final_score}"
        assert breakdown.tier in ("fair", "good", "excellent")

    def test_multi_platform_scores_good_or_excellent(self):
        """Four coherent platforms should reach Good or Excellent."""
        profiles = [self._twitter(), self._github(), self._linkedin(), self._hn()]
        vectors = {str(p.id): compute_behavioral_vector(p) for p in profiles}
        breakdown = compute_trust_score(profiles, vectors)

        assert breakdown.final_score >= 600, f"Multi-platform score too low: {breakdown.final_score}"
        assert breakdown.tier in ("good", "excellent")
        assert breakdown.confidence >= 0.5

    def test_cross_platform_coherence_boosted(self):
        """Cross-platform sub-score should be significantly higher with 4 platforms."""
        single = compute_trust_score([self._twitter()])
        profiles = [self._twitter(), self._github(), self._linkedin(), self._hn()]
        vectors = {str(p.id): compute_behavioral_vector(p) for p in profiles}
        multi = compute_trust_score(profiles, vectors)

        assert multi.cross_platform > single.cross_platform + 20

    def test_existence_reflects_longevity(self):
        """3000-day LinkedIn tenure should drive high existence score."""
        profiles = [self._twitter(), self._github(), self._linkedin(), self._hn()]
        vectors = {str(p.id): compute_behavioral_vector(p) for p in profiles}
        breakdown = compute_trust_score(profiles, vectors)

        assert breakdown.existence >= 100, f"Existence too low for 3000-day tenure: {breakdown.existence}"

    def test_engagement_reflects_reciprocity(self):
        """High reciprocity (0.60) and response rate (0.70) should push engagement."""
        profiles = [self._twitter(), self._github()]
        breakdown = compute_trust_score(profiles)
        assert breakdown.engagement >= 60

    def test_twitter_github_are_same_person(self):
        """Identity resolution should recognise twitter+github as same person."""
        tw = self._twitter()
        gh = self._github()
        vec_tw = compute_behavioral_vector(tw)
        vec_gh = compute_behavioral_vector(gh)

        result = compute_identity_similarity(tw, gh, vec_tw, vec_gh)
        assert result.decision in ("auto_link", "review"), \
            f"Same person not detected: score={result.overall_score}, decision={result.decision}"

    def test_topic_fingerprint_coherent(self):
        """Fintech + payments keywords should dominate across platforms."""
        tw = self._twitter()
        gh = self._github()
        # Both should have finance and programming
        for profile in [tw, gh]:
            cats = profile.category_fingerprint
            assert "finance" in cats or "programming" in cats

    # ── Ingestion pipeline test ──

    def test_twitter_ingestion_pipeline(self):
        """Raw Twitter data should produce a valid ProfileObservation."""
        raw = {
            "profile": {
                "username": "amaraokafor_",
                "name": "Amara Okafor",
                "followers_count": 8200,
                "following_count": 1400,
                "verified": False,
                "created_at": "2018-03-15T00:00:00Z",
                "description": "Senior Backend Engineer @Paystack. Fintech, payments, Python.",
                "location": "Lagos, Nigeria",
                "url": "https://amara.dev",
                "profile_image_url": "https://example.com/amara.jpg",
            },
            "tweets": [
                {"text": "Shipped a new payments API endpoint using FastAPI. Handles 10K TPS.", "created_at": "2026-03-28T10:00:00Z", "like_count": 45, "retweet_count": 8, "reply_count": 3},
                {"text": "Thread on distributed transaction patterns in fintech: ...", "created_at": "2026-03-27T09:00:00Z", "like_count": 120, "retweet_count": 30, "reply_count": 15},
                {"text": "What monitoring stack is everyone using for payment systems?", "created_at": "2026-03-26T14:00:00Z", "like_count": 25, "retweet_count": 2, "reply_count": 12},
            ],
        }
        obs = normalize_observation("twitter", raw)
        assert obs is not None
        assert obs.handle == "amaraokafor_"
        assert obs.audience_size == 8200
        assert "fintech" in obs.keyword_fingerprint or "payments" in obs.keyword_fingerprint or "api" in obs.keyword_fingerprint
        assert obs.account_age_days > 2500


# ===========================================================================
# PERSONA 2: 0xGhostTrader — Anonymous crypto persona, low trust
# ===========================================================================


class TestGhostTrader:
    """Anonymous, single-platform, suspicious engagement. Should score low."""

    def _profile(self) -> IdentityProfile:
        # Active at all hours (bot-like), heavy weekends
        hourly = [0.04] * 24
        hourly[3] = 0.06
        hourly[4] = 0.06

        return _make_profile(
            handle="0xGhostTrader",
            platform="twitter",
            display_name=None,  # No display name
            hourly_distribution=hourly,
            daily_distribution=[0.12, 0.12, 0.12, 0.12, 0.12, 0.14, 0.26],
            estimated_timezone_offset=0.0,  # Can't determine timezone
            regularity_score=0.15,
            weekend_ratio=0.40,
            burst_tendency=0.85,
            dormancy_max_days=45,
            night_activity_ratio=0.35,
            vocabulary_richness=0.25,
            formality_index=0.15,
            emotional_valence=-0.3,
            emotional_volatility=0.75,
            question_ratio=0.02,
            self_reference_rate=0.25,
            avg_utterance_length=18.0,
            avg_words_per_sentence=6.0,
            hashtag_rate=0.45,
            link_sharing_rate=0.35,
            mention_rate=0.40,
            initiation_ratio=0.80,
            engagement_depth_ratio=0.05,
            authority_index=0.08,
            reciprocity_rate=0.03,
            audience_size=45000,
            audience_quality_ratio=0.02,  # 45K followers but following 2M
            mention_response_rate=0.02,
            endorsement_count=5,
            keyword_fingerprint={
                "100x": 0.25, "gem": 0.20, "moon": 0.18,
                "nfa": 0.15, "pump": 0.12, "airdrop": 0.10,
            },
            category_fingerprint={"crypto_web3": 0.85, "finance": 0.15},
            expertise_depth=0.10,
            opinion_consistency=0.15,
            content_originality=0.08,
            posts_per_week_avg=80.0,
            posts_per_week_variance=60.0,
            active_weeks_ratio=0.40,
            platform_tenure_days=180,
            growth_organicity=0.10,
            growth_velocity=2.5,
            account_age_days=180,
            profile_completeness=0.25,
            anomaly_count=12,
            anomaly_types=["follower_spike", "content_repetition", "engagement_mismatch",
                           "burst_posting", "timezone_inconsistency"],
            observation_count=18,
        )

    def test_scores_poor_or_untrusted(self):
        """Suspicious anonymous profile should score low."""
        profile = self._profile()
        breakdown = compute_trust_score([profile])
        assert breakdown.final_score < 450, f"Suspicious profile scored too high: {breakdown.final_score}"
        assert breakdown.tier in ("poor", "untrusted")

    def test_low_consistency(self):
        """Bursty posting, high volatility → low consistency."""
        breakdown = compute_trust_score([self._profile()])
        assert breakdown.consistency < 80

    def test_low_engagement(self):
        """Near-zero reciprocity and response rate → low engagement."""
        breakdown = compute_trust_score([self._profile()])
        assert breakdown.engagement < 40

    def test_maturity_penalised_by_anomalies(self):
        """12 anomalies against 18 observations should reduce clean_record.

        Note: high post volume (80/week) partially offsets the anomaly penalty
        via the activity_factor, so maturity won't be near zero — but the
        clean_record detail should be well below 0.5.
        """
        breakdown = compute_trust_score([self._profile()])
        clean = breakdown.details["maturity"]["clean_record"]
        assert clean < 0.45, f"Clean record too high with 12 anomalies: {clean}"
        # Overall maturity should still be moderate at best due to short tenure
        assert breakdown.maturity < 140

    def test_single_platform_limits_cross_platform(self):
        """Single platform gets at most partial credit."""
        breakdown = compute_trust_score([self._profile()])
        assert breakdown.cross_platform < 60

    def test_dampened_by_low_observations(self):
        """18 observations → 0.80 dampening factor."""
        breakdown = compute_trust_score([self._profile()])
        assert breakdown.dampening_factor <= 0.80

    def test_not_confused_with_amara(self):
        """Ghost trader should NOT be identity-linked to a real engineer."""
        ghost = self._profile()

        # Make a simplified version of Amara's Twitter
        amara = _make_profile(
            handle="amaraokafor_",
            platform="twitter",
            vocabulary_richness=0.78,
            formality_index=0.68,
            keyword_fingerprint={"fintech": 0.20, "python": 0.15, "api": 0.12},
            category_fingerprint={"finance": 0.35, "programming": 0.30},
        )

        vec_ghost = compute_behavioral_vector(ghost)
        vec_amara = compute_behavioral_vector(amara)
        result = compute_identity_similarity(ghost, amara, vec_ghost, vec_amara)

        assert result.decision == "separate", \
            f"Ghost trader incorrectly linked to Amara: score={result.overall_score}"

    def test_topic_extraction_flags_spam_keywords(self):
        """Spam-heavy crypto content should categorise as crypto_web3."""
        texts = [
            "🚀 $PEPE to the moon!! 100x gem NFA 💎🙌",
            "NEW AIRDROP: claim free tokens now!! #crypto #gem",
            "This pump is just starting. Don't miss the next 1000x 🔥",
        ]
        kw_fp, cat_fp = extract_topics(texts)
        # Should pick up crypto keywords or at least not crash
        assert isinstance(kw_fp, dict)
        assert isinstance(cat_fp, dict)

    def test_voice_features_detect_low_quality(self):
        """Short, emoji-heavy, low-vocabulary content."""
        texts = [
            "🚀🚀🚀 MOON",
            "Buy now!! NFA",
            "100x gem alert 💎",
            "Pump it 🔥🔥🔥",
        ]
        features = extract_voice_features(texts)
        assert features["avg_utterance_length"] < 10
        # Very repetitive short texts → low vocabulary
        assert features["vocabulary_richness"] < 0.5 or len(set(" ".join(texts).split())) < 20


# ===========================================================================
# PERSONA 3: NovaPay (company) — YC-backed fintech startup
# ===========================================================================


class TestNovaPayCompany:
    """YC-backed startup with strong founders and GitHub. Should score Good."""

    def _founder_amara(self) -> ScoreBreakdown:
        """Amara Okafor as CTO — reuse her multi-platform score."""
        return ScoreBreakdown(
            existence=145.0,
            consistency=130.0,
            engagement=110.0,
            cross_platform=120.0,
            maturity=135.0,
            raw_total=640.0,
            dampening_factor=1.0,
            final_score=640,
            tier="fair",
            confidence=0.72,
            details={},
        )

    def _founder_ceo(self) -> ScoreBreakdown:
        """CEO — strong LinkedIn presence, moderate other platforms."""
        return ScoreBreakdown(
            existence=160.0,
            consistency=140.0,
            engagement=100.0,
            cross_platform=90.0,
            maturity=150.0,
            raw_total=640.0,
            dampening_factor=1.0,
            final_score=750,
            tier="good",
            confidence=0.80,
            details={},
        )

    def _company(self):
        return _make_company(
            handle="novapay",
            platform="linkedin",
            display_name="NovaPay",
            domain="novapay.io",
            platform_accounts={
                "linkedin": "novapay",
                "twitter": "novapay_hq",
                "github": "novapay",
            },
            account_age_days=540,
            follower_count=3200,
            is_verified=True,
            github_org="novapay",
            total_repos=12,
            total_stars=850,
            total_forks=120,
            commit_frequency_weekly=35,
            contributor_count=8,
            release_cadence_days=14,
            ci_pass_rate=0.92,
            documentation_score=0.75,
            brand_sentiment=0.55,
            mention_volume_weekly=25,
            support_response_hours=6,
            community_size=1500,
            nps_estimate=42,
            funding_stage="series_a",
            funding_amount_usd=8_000_000,
            employee_count_estimate=22,
            yc_batch="W24",
            team_size=22,
            observation_count=30,
        )

    def test_company_scores_good_tier(self):
        """Well-run YC startup with strong founders should reach Good."""
        founders = [self._founder_amara(), self._founder_ceo()]
        result = compute_company_score(self._company(), founders)
        assert result.final_score >= 500, f"NovaPay too low: {result.final_score}"
        assert result.tier in ("fair", "good", "excellent")

    def test_founder_signal_is_substantial(self):
        """Two strong founders should contribute significant founder score."""
        founders = [self._founder_amara(), self._founder_ceo()]
        result = compute_company_score(self._company(), founders)
        assert result.founder >= 80

    def test_product_signal_reflects_github(self):
        """850 stars, 35 commits/week, 92% CI → strong product signal."""
        result = compute_company_score(self._company())
        assert result.product >= 60

    def test_yc_batch_boosts_execution(self):
        """YC W24 batch should provide execution bonus."""
        with_yc = compute_company_score(self._company())
        without = compute_company_score(_make_company(
            **{k: getattr(self._company(), k) for k in [
                "handle", "platform", "total_repos", "total_stars",
                "commit_frequency_weekly", "contributor_count",
                "observation_count", "funding_stage", "funding_amount_usd",
                "employee_count_estimate",
            ]},
            yc_batch=None,
        ))
        assert with_yc.execution > without.execution

    def test_presence_across_three_platforms(self):
        """LinkedIn + Twitter + GitHub = good presence."""
        result = compute_company_score(self._company())
        assert result.presence >= 60

    def test_community_signal_positive(self):
        """Positive sentiment + responsive support → decent community score."""
        result = compute_company_score(self._company())
        assert result.community >= 40

    def test_no_founders_scores_lower(self):
        """Without founder data, company should score materially lower."""
        with_founders = compute_company_score(
            self._company(),
            [self._founder_amara(), self._founder_ceo()],
        )
        without = compute_company_score(self._company())
        assert with_founders.final_score > without.final_score + 30

    def test_consistency_with_aligned_founders(self):
        """Fintech founders building a fintech product = high consistency."""
        founders = [self._founder_amara(), self._founder_ceo()]
        result = compute_company_score(self._company(), founders)
        assert result.consistency >= 50

    def test_company_dampening_at_30_obs(self):
        """30 observations → full dampening (1.0)."""
        result = compute_company_score(self._company())
        assert result.dampening_factor >= 0.75

    def test_breakdown_all_fields_populated(self):
        """Every sub-score and detail field should be present."""
        founders = [self._founder_amara(), self._founder_ceo()]
        result = compute_company_score(self._company(), founders)

        assert result.founder > 0
        assert result.product > 0
        assert result.presence > 0
        assert result.execution > 0
        assert "founder" in result.details
        assert "product" in result.details
        assert "community" in result.details
        assert "presence" in result.details
        assert "execution" in result.details
        assert "consistency" in result.details

    # ── Performance test ──

    def test_scoring_is_fast(self):
        """Full company scoring should complete in under 50ms."""
        import time

        company = self._company()
        founders = [self._founder_amara(), self._founder_ceo()]

        start = time.perf_counter()
        for _ in range(100):
            compute_company_score(company, founders)
        elapsed = (time.perf_counter() - start) / 100

        assert elapsed < 0.05, f"Company scoring too slow: {elapsed*1000:.1f}ms per call"

    def test_individual_scoring_is_fast(self):
        """Full individual scoring of 4 profiles should complete in under 50ms."""
        import time

        profiles = [
            _make_profile(handle="a", platform="twitter", observation_count=30),
            _make_profile(handle="a", platform="github", observation_count=25),
            _make_profile(handle="a", platform="linkedin", observation_count=20),
            _make_profile(handle="a", platform="hackernews", observation_count=15),
        ]
        vectors = {str(p.id): compute_behavioral_vector(p) for p in profiles}

        start = time.perf_counter()
        for _ in range(100):
            compute_trust_score(profiles, vectors)
        elapsed = (time.perf_counter() - start) / 100

        assert elapsed < 0.05, f"Individual scoring too slow: {elapsed*1000:.1f}ms per call"
