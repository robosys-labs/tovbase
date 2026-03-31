"""Tests for platform ingestion adapters."""

from __future__ import annotations

import pytest

from app.services.ingestion import (
    ADAPTERS,
    extract_topics,
    extract_voice_features,
    normalize_observation,
)


class TestAdapterRegistry:
    def test_all_platforms_registered(self):
        expected = {"twitter", "github", "reddit", "hackernews", "linkedin", "instagram", "polymarket", "4chan", "ycombinator"}
        assert expected.issubset(set(ADAPTERS.keys()))

    def test_unknown_platform_returns_none(self):
        assert normalize_observation("unknown_platform", {}) is None


class TestTwitterAdapter:
    def test_basic_normalization(self):
        raw = {
            "profile": {
                "username": "testuser",
                "name": "Test User",
                "followers_count": 5000,
                "following_count": 200,
                "verified": True,
                "created_at": "2020-01-15T00:00:00Z",
                "description": "Software engineer",
                "location": "San Francisco",
            },
            "tweets": [
                {"text": "Building a new Python project with FastAPI", "created_at": "2026-03-28T14:00:00Z", "like_count": 10, "retweet_count": 2, "reply_count": 1},
                {"text": "What do you think about Rust for systems programming?", "created_at": "2026-03-27T10:00:00Z", "like_count": 25, "retweet_count": 5, "reply_count": 3},
            ],
        }
        obs = normalize_observation("twitter", raw)
        assert obs is not None
        assert obs.handle == "testuser"
        assert obs.platform == "twitter"
        assert obs.audience_size == 5000
        assert obs.is_verified is True
        assert obs.account_age_days > 0
        assert len(obs.keyword_fingerprint) > 0
        assert len(obs.activity_hours) == 2


class TestGitHubAdapter:
    def test_basic_normalization(self):
        raw = {
            "profile": {
                "login": "devuser",
                "name": "Dev User",
                "followers": 200,
                "following": 50,
                "created_at": "2018-06-01T00:00:00Z",
                "bio": "Full-stack developer",
                "company": "TechCo",
            },
            "repos": [
                {"language": "Python", "stargazers_count": 100, "forks_count": 20, "topics": ["fastapi", "web"], "description": "A web framework"},
                {"language": "Rust", "stargazers_count": 50, "forks_count": 5, "topics": ["systems"], "description": "Systems tool"},
            ],
            "events": [
                {"type": "PushEvent", "created_at": "2026-03-28T09:00:00Z"},
                {"type": "PullRequestEvent", "created_at": "2026-03-27T15:00:00Z"},
            ],
        }
        obs = normalize_observation("github", raw)
        assert obs is not None
        assert obs.handle == "devuser"
        assert obs.total_stars == 150
        assert obs.total_repos == 2
        assert obs.collaboration_signals >= 1
        assert obs.claimed_org == "TechCo"


class TestRedditAdapter:
    def test_basic_normalization(self):
        raw = {
            "profile": {
                "name": "redditor42",
                "link_karma": 5000,
                "comment_karma": 12000,
                "created_utc": 1500000000,
            },
            "comments": [
                {"body": "Machine learning is transforming the industry", "subreddit": "MachineLearning", "created_utc": "2026-03-28T12:00:00Z"},
                {"body": "I agree with this analysis of the market", "subreddit": "investing", "created_utc": "2026-03-27T08:00:00Z"},
            ],
            "posts": [],
        }
        obs = normalize_observation("reddit", raw)
        assert obs is not None
        assert obs.handle == "redditor42"
        assert obs.audience_size == 17000  # combined karma


class TestHackerNewsAdapter:
    def test_basic_normalization(self):
        raw = {
            "profile": {
                "id": "pg",
                "karma": 150000,
                "created": 1160000000,
                "about": "Y Combinator founder",
            },
            "items": [
                {"type": "story", "title": "How to start a startup", "time": "2026-03-28T10:00:00Z"},
                {"type": "comment", "text": "Great point about AI agents", "time": "2026-03-27T16:00:00Z"},
            ],
        }
        obs = normalize_observation("hackernews", raw)
        assert obs is not None
        assert obs.handle == "pg"
        assert obs.endorsement_count == 150000


class TestPolymarketAdapter:
    def test_basic_normalization(self):
        raw = {
            "profile": {"username": "forecaster1", "display_name": "Sharp Forecaster"},
            "positions": [
                {"market_title": "Will AI pass the bar exam?", "resolved": True, "outcome_correct": True},
                {"market_title": "Bitcoin above 100K by June?", "resolved": True, "outcome_correct": False},
            ],
            "trades": [
                {"timestamp": "2026-03-28T14:00:00Z", "amount": 500},
                {"timestamp": "2026-03-27T09:00:00Z", "amount": 200},
            ],
        }
        obs = normalize_observation("polymarket", raw)
        assert obs is not None
        assert obs.handle == "forecaster1"
        assert 0.0 < obs.engagement_depth_ratio <= 1.0  # accuracy + volume blended
        assert "prediction_markets" in obs.category_fingerprint


class TestYCombinatorAdapter:
    def test_company_observation(self):
        raw = {
            "company": {
                "slug": "stripe",
                "name": "Stripe",
                "one_liner": "Payments infrastructure for the internet",
                "batch": "S09",
                "github_url": "https://github.com/stripe",
            },
            "founders": [
                {"hn_username": "pc", "linkedin": "patrickc"},
                {"hn_username": "jcollison", "linkedin": "johncollison"},
            ],
        }
        obs = normalize_observation("ycombinator", raw)
        assert obs is not None
        assert obs.handle == "stripe"
        assert obs.entity_type == "company"
        assert obs.yc_batch == "S09"
        assert len(obs.founder_handles) == 2


class TestTopicExtraction:
    def test_categorizes_ai_content(self):
        texts = ["Training a transformer model with deep learning", "Fine-tuning LLMs for NLP"]
        kw, cat = extract_topics(texts)
        assert "ai_ml" in cat

    def test_categorizes_crypto_content(self):
        texts = ["Ethereum smart contract deployed on Solana blockchain"]
        kw, cat = extract_topics(texts)
        assert "crypto_web3" in cat

    def test_multiple_categories(self):
        texts = [
            "Using Python to build a machine learning pipeline on AWS",
            "Deploying the model with Kubernetes and Docker",
        ]
        kw, cat = extract_topics(texts)
        assert len(cat) >= 2

    def test_keyword_weights_normalized(self):
        texts = ["Python Python Python Rust Rust JavaScript"]
        kw, _ = extract_topics(texts)
        if kw:
            assert max(kw.values()) == 1.0  # max is normalized to 1


class TestSentimentAnalysis:
    def test_positive_text(self):
        from app.services.ingestion import compute_sentiment

        texts = ["This is a great product, absolutely amazing and wonderful"]
        score = compute_sentiment(texts)
        assert score > 0.1, f"Positive text scored {score}"

    def test_negative_text(self):
        from app.services.ingestion import compute_sentiment

        texts = ["This is terrible, a complete failure and waste of time"]
        score = compute_sentiment(texts)
        assert score < -0.1, f"Negative text scored {score}"

    def test_neutral_text(self):
        from app.services.ingestion import compute_sentiment

        texts = ["The meeting is scheduled for Tuesday at 3pm in the conference room"]
        score = compute_sentiment(texts)
        assert -0.3 <= score <= 0.3, f"Neutral text scored {score}"

    def test_negation_flips_sentiment(self):
        from app.services.ingestion import compute_sentiment

        positive = compute_sentiment(["This is great"])
        negated = compute_sentiment(["This is not great"])
        assert negated < positive

    def test_empty_returns_zero(self):
        from app.services.ingestion import compute_sentiment

        assert compute_sentiment([]) == 0.0
        assert compute_sentiment([""]) == 0.0

    def test_mixed_sentiment(self):
        from app.services.ingestion import compute_sentiment

        texts = [
            "Great progress on the project!",
            "But the security vulnerability is terrible.",
        ]
        score = compute_sentiment(texts)
        # Mixed content — should be somewhere near zero
        assert -0.8 <= score <= 0.8


class TestVoiceExtraction:
    def test_detects_questions(self):
        texts = [
            "What is the best approach?",
            "This is a statement.",
            "How should we handle this?",
        ]
        features = extract_voice_features(texts)
        assert features["question_ratio"] > 0.5

    def test_detects_links(self):
        texts = [
            "Check out https://example.com for more",
            "No links here",
        ]
        features = extract_voice_features(texts)
        assert features["link_sharing_rate"] == 0.5

    def test_empty_input(self):
        features = extract_voice_features([])
        assert features == {}
