"""Tests for company trust scoring engine."""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest

from app.models import CompanyProfile
from app.services.company_scoring import (
    CompanyScoreBreakdown,
    compute_company_score,
    score_to_tier,
)
from app.services.scoring import ScoreBreakdown


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_company(**overrides) -> CompanyProfile:
    """Build a CompanyProfile-like object for testing."""
    defaults = {
        "id": uuid.uuid4(),
        "handle": "testcorp",
        "platform": "linkedin",
        "display_name": "TestCorp Inc",
        "domain": "testcorp.com",
        "founder_identity_ids": [],
        "team_size": 0,
        "avg_team_trust_score": 0.0,
        "platform_accounts": {},
        "account_age_days": 0,
        "follower_count": 0,
        "is_verified": False,
        "github_org": None,
        "total_repos": 0,
        "total_stars": 0,
        "total_forks": 0,
        "open_issues": 0,
        "commit_frequency_weekly": 0.0,
        "contributor_count": 0,
        "release_cadence_days": 0.0,
        "ci_pass_rate": 0.0,
        "documentation_score": 0.0,
        "brand_sentiment": 0.0,
        "mention_volume_weekly": 0.0,
        "support_response_hours": 0.0,
        "community_size": 0,
        "nps_estimate": 0.0,
        "funding_stage": None,
        "funding_amount_usd": 0,
        "revenue_signal": None,
        "employee_count_estimate": 0,
        "yc_batch": None,
        "trust_score": 0,
        "observation_count": 0,
    }
    defaults.update(overrides)

    class MockCompany:
        pass

    c = MockCompany()
    for k, v in defaults.items():
        setattr(c, k, v)
    return c


def _make_founder_breakdown(**overrides) -> ScoreBreakdown:
    defaults = {
        "existence": 120.0,
        "consistency": 100.0,
        "engagement": 90.0,
        "cross_platform": 80.0,
        "maturity": 110.0,
        "raw_total": 500.0,
        "dampening_factor": 1.0,
        "final_score": 500,
        "tier": "fair",
        "confidence": 0.6,
        "details": {},
    }
    defaults.update(overrides)
    return ScoreBreakdown(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTierClassification:
    def test_excellent(self):
        assert score_to_tier(900) == "excellent"

    def test_good(self):
        assert score_to_tier(750) == "good"

    def test_fair(self):
        assert score_to_tier(600) == "fair"

    def test_poor(self):
        assert score_to_tier(400) == "poor"

    def test_untrusted(self):
        assert score_to_tier(200) == "untrusted"


class TestCompanyScoring:
    def test_empty_company_scores_low(self):
        company = _make_company()
        result = compute_company_score(company)
        assert isinstance(result, CompanyScoreBreakdown)
        assert result.final_score < 200

    def test_well_funded_company(self):
        company = _make_company(
            funding_stage="series_a",
            funding_amount_usd=10_000_000,
            employee_count_estimate=30,
            team_size=5,
            total_repos=20,
            total_stars=500,
            commit_frequency_weekly=30,
            contributor_count=15,
            ci_pass_rate=0.95,
            documentation_score=0.8,
            platform_accounts={"linkedin": "co", "twitter": "co", "github": "co"},
            account_age_days=730,
            follower_count=5000,
            brand_sentiment=0.6,
            community_size=2000,
            observation_count=30,
        )
        result = compute_company_score(company)
        assert result.final_score > 300
        assert result.product > 0
        assert result.execution > 0

    def test_founder_boost(self):
        company = _make_company(
            observation_count=30,
            platform_accounts={"linkedin": "co", "twitter": "co"},
            account_age_days=365,
        )
        low_result = compute_company_score(company)

        high_founders = [
            _make_founder_breakdown(final_score=900, confidence=0.9, cross_platform=160),
            _make_founder_breakdown(final_score=850, confidence=0.85, cross_platform=140),
        ]
        high_result = compute_company_score(company, high_founders)

        assert high_result.founder > low_result.founder
        assert high_result.final_score > low_result.final_score

    def test_yc_batch_bonus(self):
        base = _make_company(observation_count=30)
        no_yc = compute_company_score(base)

        yc_company = _make_company(yc_batch="W24", observation_count=30)
        with_yc = compute_company_score(yc_company)

        assert with_yc.execution > no_yc.execution

    def test_dampening_low_observations(self):
        company = _make_company(
            total_stars=1000,
            commit_frequency_weekly=20,
            observation_count=2,  # Very few observations
        )
        result = compute_company_score(company)
        assert result.dampening_factor < 1.0

    def test_dampening_high_observations(self):
        company = _make_company(observation_count=50)
        result = compute_company_score(company)
        assert result.dampening_factor == 1.0

    def test_score_capped_at_1000(self):
        company = _make_company(
            total_repos=100,
            total_stars=50000,
            total_forks=10000,
            commit_frequency_weekly=200,
            contributor_count=100,
            ci_pass_rate=1.0,
            documentation_score=1.0,
            release_cadence_days=7,
            brand_sentiment=0.95,
            community_size=500000,
            mention_volume_weekly=1000,
            support_response_hours=1,
            nps_estimate=80,
            platform_accounts={"linkedin": "x", "twitter": "x", "github": "x", "reddit": "x", "hn": "x"},
            account_age_days=3650,
            follower_count=500000,
            is_verified=True,
            funding_stage="public",
            funding_amount_usd=500_000_000,
            employee_count_estimate=5000,
            yc_batch="W15",
            observation_count=100,
        )
        founders = [_make_founder_breakdown(final_score=950, confidence=0.95, cross_platform=190)] * 3
        result = compute_company_score(company, founders)
        assert result.final_score <= 1000

    def test_breakdown_fields_populated(self):
        company = _make_company(
            total_repos=5,
            total_stars=100,
            observation_count=30,
            platform_accounts={"linkedin": "co"},
        )
        result = compute_company_score(company)
        assert "founder" in result.details
        assert "product" in result.details
        assert "community" in result.details
        assert "presence" in result.details
        assert "execution" in result.details
        assert "consistency" in result.details


class TestTopicExtraction:
    def test_extract_topics_from_texts(self):
        from app.services.ingestion import extract_topics

        texts = [
            "Building a new machine learning pipeline in Python",
            "Deep learning transformers for NLP tasks",
            "Using FastAPI and React for the web dashboard",
        ]
        kw_fp, cat_fp = extract_topics(texts)
        assert len(kw_fp) > 0
        assert "ai_ml" in cat_fp or "programming" in cat_fp

    def test_empty_texts(self):
        from app.services.ingestion import extract_topics

        kw_fp, cat_fp = extract_topics([])
        assert kw_fp == {}
        assert cat_fp == {}

    def test_voice_extraction(self):
        from app.services.ingestion import extract_voice_features

        texts = [
            "This is a formal technical document about distributed systems.",
            "We implemented the algorithm using Rust for performance.",
            "What are the implications of this architecture decision?",
        ]
        features = extract_voice_features(texts)
        assert "avg_utterance_length" in features
        assert "vocabulary_richness" in features
        assert "question_ratio" in features
        assert features["question_ratio"] > 0  # One question in 3 texts
