"""Platform ingestion adapters — normalize raw platform data into behavioral observations.

Each adapter converts platform-specific scrape data into the canonical
observation format consumed by the scoring engine. Adapters handle:

1. Profile metadata extraction (handle, display name, account age, etc.)
2. Behavioral signal extraction (posting patterns, engagement, voice)
3. Topic/interest extraction (keyword fingerprint, category mapping)

Supported platforms:
  - Twitter/X    (tweets, followers, engagement patterns)
  - LinkedIn     (profile, endorsements, posts)
  - GitHub       (repos, commits, contributions)
  - Reddit       (posts, comments, karma, subreddits)
  - Hacker News  (stories, comments, karma)
  - Instagram    (posts, followers, engagement timing)
  - Polymarket   (bets, accuracy, market participation)
  - 4chan         (board participation, post patterns — archive-based)
  - YCombinator  (company profiles, founder connections)
"""

from __future__ import annotations

import math
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Canonical observation format
# ---------------------------------------------------------------------------


@dataclass
class ProfileObservation:
    """Normalized observation data extracted from a platform scrape."""

    handle: str
    platform: str
    display_name: str | None = None
    entity_type: str = "individual"  # "individual" | "company"

    # Identity
    account_age_days: int = 0
    profile_completeness: float = 0.0
    is_verified: bool = False
    audience_size: int = 0
    following_count: int = 0

    # Chronotype
    activity_hours: list[int] = field(default_factory=list)
    activity_days: list[int] = field(default_factory=list)
    timezone_offset: float = 0.0

    # Voice
    post_texts: list[str] = field(default_factory=list)
    avg_utterance_length: float = 0.0
    vocabulary_richness: float = 0.0
    formality_index: float = 0.5
    question_ratio: float = 0.0
    hashtag_rate: float = 0.0
    link_sharing_rate: float = 0.0

    # Social
    engagement_depth_ratio: float = 0.0
    reciprocity_rate: float = 0.0
    endorsement_count: int = 0
    collaboration_signals: int = 0

    # Topics
    keyword_fingerprint: dict[str, float] = field(default_factory=dict)
    category_fingerprint: dict[str, float] = field(default_factory=dict)
    claimed_role: str | None = None
    claimed_org: str | None = None

    # Presence
    posts_per_week_avg: float = 0.0
    active_weeks_ratio: float = 0.0
    growth_organicity: float = 0.0

    # Scoring engine fields (computed by adapters for the scoring pipeline)
    regularity_score: float = 0.0
    emotional_volatility: float = 0.0
    posts_per_week_variance: float = 0.0
    platform_tenure_days: int = 0
    authority_index: float = 0.0
    anomaly_count: int = 0
    mention_response_rate: float = 0.0

    # Company-specific
    github_org: str | None = None
    total_repos: int = 0
    total_stars: int = 0
    funding_stage: str | None = None
    yc_batch: str | None = None
    founder_handles: list[dict] = field(default_factory=list)

    # Raw data (preserved for debugging)
    raw_payload: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Topic extraction helpers
# ---------------------------------------------------------------------------

# Hand-curated category keywords (no ML, deterministic)
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "programming": [
        "python", "javascript", "typescript", "rust", "golang", "java", "cpp",
        "react", "vue", "angular", "node", "django", "flask", "fastapi",
        "code", "coding", "programming", "developer", "software", "engineer",
        "algorithm", "data structure", "api", "framework", "library",
    ],
    "ai_ml": [
        "machine learning", "deep learning", "neural network", "transformer",
        "llm", "gpt", "claude", "ai", "artificial intelligence", "nlp",
        "computer vision", "reinforcement learning", "diffusion", "bert",
        "fine-tuning", "prompt engineering", "rag", "embedding", "agent",
    ],
    "crypto_web3": [
        "blockchain", "cryptocurrency", "bitcoin", "ethereum", "solana",
        "defi", "nft", "web3", "smart contract", "token", "dao", "dex",
        "staking", "mining", "wallet", "ledger", "consensus", "layer2",
    ],
    "finance": [
        "investing", "stock", "market", "trading", "portfolio", "hedge fund",
        "venture capital", "startup", "fintech", "payment", "banking",
        "revenue", "valuation", "ipo", "funding", "seed", "series",
    ],
    "infrastructure": [
        "kubernetes", "docker", "aws", "gcp", "azure", "devops", "ci/cd",
        "terraform", "cloud", "serverless", "microservice", "distributed",
        "database", "redis", "postgres", "kafka", "scaling", "observability",
    ],
    "security": [
        "security", "vulnerability", "exploit", "pentest", "encryption",
        "authentication", "authorization", "oauth", "ssl", "tls", "firewall",
        "malware", "phishing", "zero-day", "cve", "bug bounty",
    ],
    "product": [
        "product management", "ux", "ui", "design", "user research",
        "roadmap", "sprint", "agile", "scrum", "feature", "mvp",
        "a/b test", "conversion", "retention", "churn", "onboarding",
    ],
    "science": [
        "research", "paper", "study", "experiment", "hypothesis", "data",
        "statistics", "biology", "physics", "chemistry", "mathematics",
        "peer review", "citation", "journal", "arxiv", "preprint",
    ],
    "politics": [
        "election", "policy", "government", "political", "democrat",
        "republican", "congress", "senate", "legislation", "regulation",
        "vote", "campaign", "partisan", "liberal", "conservative",
    ],
    "prediction_markets": [
        "polymarket", "prediction", "forecast", "odds", "probability",
        "bet", "wager", "market maker", "liquidity", "resolution",
        "calibration", "metaculus", "manifold", "superforecaster",
    ],
}


def extract_topics(texts: list[str]) -> tuple[dict[str, float], dict[str, float]]:
    """Extract keyword and category fingerprints from a collection of texts.

    Uses deterministic keyword matching — no ML models. Returns:
      - keyword_fingerprint: dict of keyword → weight (0-1)
      - category_fingerprint: dict of category → weight (0-1)
    """
    if not texts:
        return {}, {}

    combined = " ".join(texts).lower()
    word_count = len(combined.split()) or 1

    # Build keyword frequency
    keyword_counts: dict[str, int] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            count = combined.count(kw.lower())
            if count > 0:
                keyword_counts[kw] = count

    if not keyword_counts:
        return {}, {}

    # Normalize keyword weights to [0, 1]
    max_count = max(keyword_counts.values())
    keyword_fingerprint = {
        kw: round(count / max_count, 4) for kw, count in sorted(keyword_counts.items(), key=lambda x: -x[1])[:50]
    }

    # Build category fingerprint
    category_scores: dict[str, float] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        total = sum(keyword_counts.get(kw, 0) for kw in keywords)
        if total > 0:
            category_scores[category] = total

    if not category_scores:
        return keyword_fingerprint, {}

    total_cat = sum(category_scores.values())
    category_fingerprint = {
        cat: round(score / total_cat, 4) for cat, score in sorted(category_scores.items(), key=lambda x: -x[1])
    }

    return keyword_fingerprint, category_fingerprint


# ---------------------------------------------------------------------------
# Deterministic sentiment analysis
# ---------------------------------------------------------------------------

# Lexicon-based sentiment — curated word lists (no ML)
_POSITIVE_WORDS = frozenset([
    "good", "great", "excellent", "amazing", "awesome", "fantastic", "wonderful",
    "love", "loved", "best", "better", "happy", "glad", "excited", "impressive",
    "beautiful", "brilliant", "perfect", "success", "successful", "win", "winning",
    "strong", "growth", "profit", "gain", "bullish", "innovation", "innovative",
    "breakthrough", "progress", "positive", "optimistic", "recommend", "reliable",
    "trusted", "secure", "efficient", "effective", "useful", "helpful", "solved",
    "improved", "upgrade", "launched", "achieved", "congrats", "congratulations",
    "thank", "thanks", "grateful", "appreciate", "agree", "correct", "right",
    "fast", "clean", "elegant", "solid", "robust", "stable", "powerful",
])

_NEGATIVE_WORDS = frozenset([
    "bad", "terrible", "awful", "horrible", "worst", "hate", "hated", "ugly",
    "broken", "bug", "crash", "fail", "failed", "failure", "loss", "lost",
    "scam", "fraud", "fake", "spam", "malware", "hack", "hacked", "breach",
    "vulnerability", "exploit", "attack", "threat", "risk", "danger", "warning",
    "bearish", "decline", "drop", "dump", "collapse", "bankrupt", "debt",
    "slow", "laggy", "bloated", "overpriced", "expensive", "useless", "waste",
    "angry", "frustrated", "disappointed", "annoyed", "worried", "concerned",
    "wrong", "incorrect", "mistake", "error", "problem", "issue", "critical",
    "dead", "kill", "toxic", "racist", "sexist", "lawsuit", "sued", "banned",
    "censored", "shutdown", "layoff", "fired", "resign", "scandal", "corrupt",
])

_INTENSIFIERS = frozenset([
    "very", "extremely", "incredibly", "absolutely", "totally", "completely",
    "highly", "really", "truly", "super", "utterly", "deeply",
])

_NEGATORS = frozenset([
    "not", "no", "never", "neither", "nor", "none", "nothing", "nobody",
    "nowhere", "hardly", "barely", "scarcely", "don't", "doesn't", "didn't",
    "won't", "wouldn't", "can't", "couldn't", "shouldn't", "isn't", "aren't",
])


def compute_sentiment(texts: list[str]) -> float:
    """Compute deterministic sentiment score from text content.

    Uses a curated lexicon with negation handling and intensity modifiers.
    Returns a score in [-1.0, 1.0] where:
      -1.0 = strongly negative
       0.0 = neutral
       1.0 = strongly positive

    No ML models — pure word-counting with context awareness.
    """
    if not texts:
        return 0.0

    total_score = 0.0
    total_tokens = 0

    for text in texts:
        words = text.lower().split()
        if not words:
            continue

        negated = False
        intensified = False
        text_score = 0.0

        for word in words:
            # Strip common punctuation
            clean = word.strip(".,!?;:\"'()[]{}")

            if clean in _NEGATORS:
                negated = True
                continue

            if clean in _INTENSIFIERS:
                intensified = True
                continue

            multiplier = 1.5 if intensified else 1.0
            if negated:
                multiplier *= -1.0

            if clean in _POSITIVE_WORDS:
                text_score += 1.0 * multiplier
            elif clean in _NEGATIVE_WORDS:
                text_score -= 1.0 * multiplier

            # Reset modifiers after applying
            negated = False
            intensified = False

        # Normalise by word count to avoid length bias
        if words:
            text_score = text_score / len(words)

        total_score += text_score
        total_tokens += 1

    if total_tokens == 0:
        return 0.0

    # Average across texts and clamp to [-1, 1]
    raw = total_score / total_tokens
    return max(-1.0, min(1.0, raw * 10))  # Scale up (word-level scores are tiny)


def extract_voice_features(texts: list[str]) -> dict[str, float]:
    """Extract linguistic features from a collection of texts.

    Deterministic statistical analysis — no ML.
    """
    if not texts:
        return {}

    all_words = []
    sentence_lengths = []
    question_count = 0
    hashtag_count = 0
    link_count = 0
    total_chars = 0

    for text in texts:
        words = text.split()
        all_words.extend(words)
        total_chars += len(text)

        # Sentence splitting (rough)
        sentences = re.split(r'[.!?]+', text)
        for s in sentences:
            sw = s.split()
            if sw:
                sentence_lengths.append(len(sw))

        if text.strip().endswith("?"):
            question_count += 1

        hashtag_count += text.count("#")
        link_count += len(re.findall(r'https?://', text))

    num_texts = len(texts)
    total_words = len(all_words) or 1
    unique_words = len(set(w.lower() for w in all_words))

    avg_utterance = total_words / num_texts
    vocab_richness = min(unique_words / total_words, 1.0) if total_words > 50 else 0.0

    # Formality heuristic: longer sentences + fewer contractions + fewer emojis = more formal
    avg_sentence_len = sum(sentence_lengths) / len(sentence_lengths) if sentence_lengths else 0
    contraction_count = sum(1 for w in all_words if "'" in w and w.lower() in {
        "i'm", "don't", "can't", "won't", "it's", "that's", "there's",
        "i've", "we've", "they've", "isn't", "aren't", "wasn't", "weren't",
        "couldn't", "shouldn't", "wouldn't", "he's", "she's", "you're",
    })
    formality = min(avg_sentence_len / 25, 1.0) * (1.0 - min(contraction_count / total_words * 10, 0.5))

    return {
        "avg_utterance_length": round(avg_utterance, 1),
        "vocabulary_richness": round(vocab_richness, 4),
        "formality_index": round(max(0, min(formality, 1.0)), 4),
        "question_ratio": round(question_count / num_texts, 4),
        "hashtag_rate": round(hashtag_count / num_texts, 4),
        "link_sharing_rate": round(link_count / num_texts, 4),
        "avg_words_per_sentence": round(avg_sentence_len, 1),
    }


# ---------------------------------------------------------------------------
# Base adapter
# ---------------------------------------------------------------------------


class PlatformAdapter(ABC):
    """Base class for platform-specific data normalization."""

    platform: str

    @abstractmethod
    def normalize(self, raw_data: dict[str, Any]) -> ProfileObservation:
        """Convert raw platform scrape data into canonical observation."""
        ...

    def _extract_activity_hours(self, timestamps: list) -> list[int]:
        """Extract hour-of-day from a list of timestamps (ISO strings, datetime, or Unix epoch)."""
        hours = []
        for ts in timestamps:
            dt = self._parse_timestamp(ts)
            if dt:
                hours.append(dt.hour)
        return hours

    def _extract_activity_days(self, timestamps: list) -> list[int]:
        """Extract day-of-week (0=Mon) from timestamps (ISO strings, datetime, or Unix epoch)."""
        days = []
        for ts in timestamps:
            dt = self._parse_timestamp(ts)
            if dt:
                days.append(dt.weekday())
        return days

    @staticmethod
    def _parse_timestamp(ts) -> datetime | None:
        """Parse a timestamp in any common format into a datetime."""
        if isinstance(ts, datetime):
            return ts
        if isinstance(ts, (int, float)):
            if ts <= 0:
                return None
            try:
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            except (ValueError, OSError):
                return None
        if isinstance(ts, str):
            if not ts:
                return None
            try:
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None

    # ── Scoring field helpers ──────────────────────────────────────

    def _compute_regularity(self, activity_hours: list[int]) -> float:
        """Shannon entropy of hourly activity distribution, normalized to [0,1].

        Perfectly uniform activity across 24 hours = 1.0 (maximally regular).
        All activity in one hour = 0.0 (maximally irregular/bursty).
        """
        if len(activity_hours) < 3:
            return 0.0
        counts = [0] * 24
        for h in activity_hours:
            if 0 <= h < 24:
                counts[h] += 1
        total = sum(counts) or 1
        max_entropy = math.log(24)
        entropy = 0.0
        for c in counts:
            if c > 0:
                p = c / total
                entropy -= p * math.log(p)
        return min(entropy / max_entropy, 1.0)

    def _compute_emotional_volatility(self, texts: list[str]) -> float:
        """Variance in per-text emotional intensity, normalized to [0,1].

        Measures how much the emotional tone swings between posts.
        Stable communicator → low volatility. Erratic → high volatility.
        """
        if len(texts) < 3:
            return 0.0
        intensities = []
        for text in texts[:50]:
            words = text.lower().split()
            if not words:
                continue
            caps_ratio = sum(1 for w in text.split() if w.isupper() and len(w) > 1) / max(len(words), 1)
            exclaim_ratio = text.count("!") / max(len(words), 1)
            question_ratio = text.count("?") / max(len(words), 1)
            intensity = caps_ratio + exclaim_ratio * 2 + question_ratio
            intensities.append(intensity)
        if len(intensities) < 2:
            return 0.0
        mean = sum(intensities) / len(intensities)
        variance = sum((x - mean) ** 2 for x in intensities) / len(intensities)
        std_dev = math.sqrt(variance)
        return min(std_dev / 0.3, 1.0)

    def _compute_weekly_variance(self, timestamps: list, account_age_days: int) -> float:
        """Variance in per-week post counts."""
        if len(timestamps) < 3 or account_age_days < 14:
            return 0.0
        week_counts: dict[str, int] = {}
        for ts in timestamps:
            dt = self._parse_timestamp(ts)
            if dt:
                week_key = dt.strftime("%Y-%W")
                week_counts[week_key] = week_counts.get(week_key, 0) + 1
        if len(week_counts) < 2:
            return 0.0
        vals = list(week_counts.values())
        mean = sum(vals) / len(vals)
        variance = sum((v - mean) ** 2 for v in vals) / len(vals)
        return variance

    def _compute_active_weeks(self, timestamps: list, account_age_days: int) -> float:
        """Fraction of weeks with at least one activity."""
        if not timestamps or account_age_days < 7:
            return 0.0
        weeks_with_activity: set[str] = set()
        for ts in timestamps:
            dt = self._parse_timestamp(ts)
            if dt:
                weeks_with_activity.add(dt.strftime("%Y-%W"))
        total_weeks = max(account_age_days / 7, 1)
        return min(len(weeks_with_activity) / total_weeks, 1.0)


# ---------------------------------------------------------------------------
# Twitter/X adapter
# ---------------------------------------------------------------------------


class TwitterAdapter(PlatformAdapter):
    platform = "twitter"

    def normalize(self, raw: dict[str, Any]) -> ProfileObservation:
        profile = raw.get("profile", {})
        tweets = raw.get("tweets", [])
        timestamps = [t.get("created_at", "") for t in tweets if t.get("created_at")]
        texts = [t.get("text", "") for t in tweets if t.get("text")]

        voice = extract_voice_features(texts)
        kw_fp, cat_fp = extract_topics(texts)

        # Engagement analysis
        total_engagement = 0
        reply_count = 0
        for t in tweets:
            total_engagement += t.get("like_count", 0) + t.get("retweet_count", 0) + t.get("reply_count", 0)
            if t.get("in_reply_to_user_id"):
                reply_count += 1

        avg_engagement = total_engagement / len(tweets) if tweets else 0
        reply_ratio = reply_count / len(tweets) if tweets else 0

        return ProfileObservation(
            handle=profile.get("username", raw.get("handle", "")),
            platform=self.platform,
            display_name=profile.get("name"),
            account_age_days=self._calc_age(profile.get("created_at")),
            audience_size=profile.get("followers_count", 0),
            following_count=profile.get("following_count", 0),
            is_verified=profile.get("verified", False),
            profile_completeness=self._calc_completeness(profile),
            activity_hours=self._extract_activity_hours(timestamps),
            activity_days=self._extract_activity_days(timestamps),
            post_texts=texts[:100],
            avg_utterance_length=voice.get("avg_utterance_length", 0),
            vocabulary_richness=voice.get("vocabulary_richness", 0),
            formality_index=voice.get("formality_index", 0.5),
            question_ratio=voice.get("question_ratio", 0),
            hashtag_rate=voice.get("hashtag_rate", 0),
            link_sharing_rate=voice.get("link_sharing_rate", 0),
            engagement_depth_ratio=min(avg_engagement / 100, 1.0),
            reciprocity_rate=reply_ratio,
            keyword_fingerprint=kw_fp,
            category_fingerprint=cat_fp,
            claimed_role=profile.get("description", "")[:255] if profile.get("description") else None,
            posts_per_week_avg=len(tweets) / max(self._calc_age(profile.get("created_at")) / 7, 1),
            # Scoring fields
            platform_tenure_days=self._calc_age(profile.get("created_at")),
            regularity_score=self._compute_regularity(self._extract_activity_hours(timestamps)),
            emotional_volatility=self._compute_emotional_volatility(texts),
            posts_per_week_variance=self._compute_weekly_variance(timestamps, self._calc_age(profile.get("created_at"))),
            active_weeks_ratio=self._compute_active_weeks(timestamps, self._calc_age(profile.get("created_at"))),
            authority_index=min(math.log1p(profile.get("followers_count", 0)) / math.log1p(100000), 1.0),
            mention_response_rate=reply_ratio,
            anomaly_count=0,
            raw_payload=raw,
        )

    def _calc_age(self, created_at: str | None) -> int:
        if not created_at:
            return 0
        try:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            return max((datetime.now(timezone.utc) - dt).days, 0)
        except ValueError:
            return 0

    def _calc_completeness(self, profile: dict) -> float:
        fields = ["name", "description", "location", "url", "profile_image_url"]
        filled = sum(1 for f in fields if profile.get(f))
        return filled / len(fields)


# ---------------------------------------------------------------------------
# GitHub adapter
# ---------------------------------------------------------------------------


class GitHubAdapter(PlatformAdapter):
    platform = "github"

    def normalize(self, raw: dict[str, Any]) -> ProfileObservation:
        profile = raw.get("profile", {})
        repos = raw.get("repos", [])
        events = raw.get("events", [])
        timestamps = [e.get("created_at", "") for e in events if e.get("created_at")]

        # Extract language/topic signals from repos
        languages: dict[str, int] = {}
        total_stars = 0
        total_forks = 0
        for repo in repos:
            lang = repo.get("language")
            if lang:
                languages[lang] = languages.get(lang, 0) + 1
            total_stars += repo.get("stargazers_count", 0)
            total_forks += repo.get("forks_count", 0)

        # Build keyword fingerprint from repo topics and languages
        topics: list[str] = []
        for repo in repos:
            topics.extend(repo.get("topics", []))
            if repo.get("language"):
                topics.append(repo["language"].lower())
            if repo.get("description"):
                topics.append(repo["description"])

        kw_fp, cat_fp = extract_topics(topics)

        # Platform-specific expertise from languages
        total_lang = sum(languages.values()) or 1
        platform_expertise = {
            lang.lower(): round(count / total_lang, 3) for lang, count in languages.items()
        }

        age = self._calc_age(profile.get("created_at"))
        followers = profile.get("followers", 0)
        total_repos = profile.get("public_repos", len(repos))
        pr_count = sum(1 for e in events if e.get("type") in ("PullRequestEvent", "PullRequestReviewEvent"))

        return ProfileObservation(
            handle=profile.get("login", raw.get("handle", "")),
            platform=self.platform,
            display_name=profile.get("name"),
            account_age_days=age,
            audience_size=followers,
            following_count=profile.get("following", 0),
            profile_completeness=self._calc_completeness(profile),
            activity_hours=self._extract_activity_hours(timestamps),
            activity_days=self._extract_activity_days(timestamps),
            endorsement_count=total_stars,
            collaboration_signals=pr_count,
            # Engagement: factor in repo count, stars, forks, PRs, followers — all signs of platform engagement
            engagement_depth_ratio=min(
                math.log1p(total_repos + total_stars * 5 + total_forks * 3 + pr_count * 10) / math.log1p(5000), 1.0
            ),
            reciprocity_rate=min(pr_count / max(len(events), 1), 1.0) if events else 0.0,
            growth_organicity=min(followers / max(profile.get("following", 1), 1) / 5, 1.0) if followers > 0 else 0.0,
            keyword_fingerprint=kw_fp,
            category_fingerprint=cat_fp,
            claimed_role=profile.get("bio", "")[:255] if profile.get("bio") else None,
            claimed_org=profile.get("company"),
            total_repos=total_repos,
            total_stars=total_stars,
            posts_per_week_avg=max(len(events) / max(age / 7, 1), total_repos / max(age / 7, 1)),
            # Scoring fields
            platform_tenure_days=age,
            regularity_score=self._compute_regularity(self._extract_activity_hours(timestamps)),
            emotional_volatility=0.0,
            posts_per_week_variance=self._compute_weekly_variance(timestamps, age),
            active_weeks_ratio=self._compute_active_weeks(timestamps, age) if events else min(total_repos / max(age / 7, 1), 1.0),
            authority_index=min(math.log1p(total_stars + followers * 2 + total_repos) / math.log1p(50000), 1.0),
            anomaly_count=0,
            raw_payload=raw,
        )

    def _calc_age(self, created_at: str | None) -> int:
        if not created_at:
            return 0
        try:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            return max((datetime.now(timezone.utc) - dt).days, 0)
        except ValueError:
            return 0

    def _calc_completeness(self, profile: dict) -> float:
        fields = ["name", "bio", "company", "location", "blog", "email"]
        filled = sum(1 for f in fields if profile.get(f))
        return filled / len(fields)


# ---------------------------------------------------------------------------
# Reddit adapter
# ---------------------------------------------------------------------------


class RedditAdapter(PlatformAdapter):
    platform = "reddit"

    def normalize(self, raw: dict[str, Any]) -> ProfileObservation:
        profile = raw.get("profile", {})
        comments = raw.get("comments", [])
        posts = raw.get("posts", [])

        all_content = comments + posts
        timestamps = [c.get("created_utc", "") for c in all_content if c.get("created_utc")]
        texts = [c.get("body", c.get("selftext", "")) for c in all_content if c.get("body") or c.get("selftext")]

        voice = extract_voice_features(texts)
        kw_fp, cat_fp = extract_topics(texts)

        # Subreddit analysis for topic categorization
        subreddits: dict[str, int] = {}
        for item in all_content:
            sr = item.get("subreddit", "")
            if sr:
                subreddits[sr] = subreddits.get(sr, 0) + 1

        karma = profile.get("link_karma", 0) + profile.get("comment_karma", 0)
        age = self._calc_age(profile.get("created_utc"))

        return ProfileObservation(
            handle=profile.get("name", raw.get("handle", "")),
            platform=self.platform,
            display_name=profile.get("name"),
            account_age_days=age,
            audience_size=karma,
            profile_completeness=0.5,  # Reddit has minimal profile fields
            activity_hours=self._extract_activity_hours(timestamps),
            activity_days=self._extract_activity_days(timestamps),
            post_texts=texts[:100],
            avg_utterance_length=voice.get("avg_utterance_length", 0),
            vocabulary_richness=voice.get("vocabulary_richness", 0),
            formality_index=voice.get("formality_index", 0.5),
            question_ratio=voice.get("question_ratio", 0),
            endorsement_count=karma,
            keyword_fingerprint=kw_fp,
            category_fingerprint=cat_fp,
            posts_per_week_avg=len(all_content) / max(age / 7, 1),
            # Scoring fields
            platform_tenure_days=age,
            regularity_score=self._compute_regularity(self._extract_activity_hours(timestamps)),
            emotional_volatility=self._compute_emotional_volatility(texts),
            posts_per_week_variance=self._compute_weekly_variance(timestamps, age),
            active_weeks_ratio=self._compute_active_weeks(timestamps, age),
            authority_index=min(math.log1p(karma) / math.log1p(500000), 1.0),
            anomaly_count=0,
            engagement_depth_ratio=min(math.log1p(karma + len(all_content) * 5) / math.log1p(100000), 1.0),
            reciprocity_rate=len(comments) / max(len(all_content), 1),
            growth_organicity=min(karma / max(len(all_content) * 10, 1), 1.0),
            mention_response_rate=len(comments) / max(len(all_content), 1),
            raw_payload=raw,
        )

    def _calc_age(self, created_utc: Any) -> int:
        if not created_utc:
            return 0
        try:
            if isinstance(created_utc, (int, float)):
                dt = datetime.fromtimestamp(created_utc, tz=timezone.utc)
            else:
                dt = datetime.fromisoformat(str(created_utc).replace("Z", "+00:00"))
            return max((datetime.now(timezone.utc) - dt).days, 0)
        except (ValueError, OSError):
            return 0


# ---------------------------------------------------------------------------
# Hacker News adapter
# ---------------------------------------------------------------------------


class HackerNewsAdapter(PlatformAdapter):
    platform = "hackernews"

    def normalize(self, raw: dict[str, Any]) -> ProfileObservation:
        profile = raw.get("profile", {})
        items = raw.get("items", [])

        timestamps = [i.get("time", "") for i in items if i.get("time")]
        texts = []
        for item in items:
            if item.get("text"):
                texts.append(item["text"])
            elif item.get("title"):
                texts.append(item["title"])

        voice = extract_voice_features(texts)
        kw_fp, cat_fp = extract_topics(texts)

        stories = [i for i in items if i.get("type") == "story"]
        comments = [i for i in items if i.get("type") == "comment"]

        age = self._calc_age(profile.get("created"))

        return ProfileObservation(
            handle=profile.get("id", raw.get("handle", "")),
            platform=self.platform,
            display_name=profile.get("id"),
            account_age_days=age,
            audience_size=profile.get("karma", 0),
            profile_completeness=0.3 + (0.3 if profile.get("about") else 0.0),
            activity_hours=self._extract_activity_hours(timestamps),
            activity_days=self._extract_activity_days(timestamps),
            post_texts=texts[:100],
            avg_utterance_length=voice.get("avg_utterance_length", 0),
            vocabulary_richness=voice.get("vocabulary_richness", 0),
            formality_index=voice.get("formality_index", 0.5),
            question_ratio=voice.get("question_ratio", 0),
            endorsement_count=profile.get("karma", 0),
            engagement_depth_ratio=min(math.log1p(profile.get("karma", 0) + len(items) * 10) / math.log1p(50000), 1.0),
            reciprocity_rate=len(comments) / max(len(items), 1),
            growth_organicity=min(profile.get("karma", 0) / max(len(items) * 10, 1), 1.0),
            keyword_fingerprint=kw_fp,
            category_fingerprint=cat_fp,
            posts_per_week_avg=len(items) / max(age / 7, 1),
            # Scoring fields
            platform_tenure_days=age,
            regularity_score=self._compute_regularity(self._extract_activity_hours(timestamps)),
            emotional_volatility=self._compute_emotional_volatility(texts),
            posts_per_week_variance=self._compute_weekly_variance(timestamps, age),
            active_weeks_ratio=self._compute_active_weeks(timestamps, age),
            authority_index=min(math.log1p(profile.get("karma", 0)) / math.log1p(50000), 1.0),
            anomaly_count=0,
            mention_response_rate=len(comments) / max(len(items), 1),
            raw_payload=raw,
        )

    def _calc_age(self, created: Any) -> int:
        if not created:
            return 0
        try:
            if isinstance(created, (int, float)):
                dt = datetime.fromtimestamp(created, tz=timezone.utc)
            else:
                return 0
            return max((datetime.now(timezone.utc) - dt).days, 0)
        except (ValueError, OSError):
            return 0


# ---------------------------------------------------------------------------
# LinkedIn adapter
# ---------------------------------------------------------------------------


class LinkedInAdapter(PlatformAdapter):
    platform = "linkedin"

    def normalize(self, raw: dict[str, Any]) -> ProfileObservation:
        profile = raw.get("profile", {})
        posts = raw.get("posts", [])
        timestamps = [p.get("created_at", "") for p in posts if p.get("created_at")]
        texts = [p.get("text", "") for p in posts if p.get("text")]

        voice = extract_voice_features(texts)
        kw_fp, cat_fp = extract_topics(texts)

        # LinkedIn-specific completeness
        completeness_fields = [
            "firstName", "lastName", "headline", "summary", "location",
            "profilePicture", "industry", "experience", "education",
        ]
        filled = sum(1 for f in completeness_fields if profile.get(f))
        completeness = filled / len(completeness_fields)

        experience = profile.get("experience", [])
        education = profile.get("education", [])
        # Use the larger of follower count vs connection count (followers is uncapped)
        followers = profile.get("followerCount", 0)
        connections = max(profile.get("connectionCount", 0), followers)
        endorsements = profile.get("endorsementCount", 0)

        age = self._estimate_age(experience, education)

        return ProfileObservation(
            handle=profile.get("vanityName", raw.get("handle", "")),
            platform=self.platform,
            display_name=f"{profile.get('firstName', '')} {profile.get('lastName', '')}".strip() or None,
            account_age_days=age,
            audience_size=profile.get("connectionCount", 0),
            is_verified=profile.get("premium", False),
            profile_completeness=completeness,
            activity_hours=self._extract_activity_hours(timestamps),
            activity_days=self._extract_activity_days(timestamps),
            post_texts=texts[:100],
            avg_utterance_length=voice.get("avg_utterance_length", 0),
            vocabulary_richness=voice.get("vocabulary_richness", 0),
            formality_index=voice.get("formality_index", 0.5),
            endorsement_count=endorsements,
            # Engagement: connections + endorsements + posts + experience depth
            engagement_depth_ratio=min(
                math.log1p(connections + endorsements * 5 + len(posts) * 20 + len(experience) * 50) / math.log1p(10000), 1.0
            ),
            reciprocity_rate=min(len(posts) / 10, 1.0) if posts else min(connections / 500, 0.5),
            growth_organicity=min(connections / 500, 1.0),
            keyword_fingerprint=kw_fp,
            category_fingerprint=cat_fp,
            claimed_role=profile.get("headline"),
            claimed_org=experience[0].get("companyName") if experience else None,
            posts_per_week_avg=len(posts) / 4 if posts else 0,
            # Scoring fields
            platform_tenure_days=age,
            regularity_score=self._compute_regularity(self._extract_activity_hours(timestamps)),
            emotional_volatility=self._compute_emotional_volatility(texts),
            posts_per_week_variance=self._compute_weekly_variance(timestamps, age),
            active_weeks_ratio=self._compute_active_weeks(timestamps, age) if timestamps else min(len(experience) / 5, 1.0),
            authority_index=min(math.log1p(connections + endorsements * 5) / math.log1p(5000), 1.0),
            anomaly_count=0,
            raw_payload=raw,
        )

    def _estimate_age(self, experience: list, education: list) -> int:
        """Estimate LinkedIn tenure from earliest experience/education date."""
        earliest = datetime.now(timezone.utc)
        for exp in experience:
            start = exp.get("startDate", {})
            if start.get("year"):
                try:
                    dt = datetime(start["year"], start.get("month", 1), 1, tzinfo=timezone.utc)
                    earliest = min(earliest, dt)
                except ValueError:
                    pass
        return max((datetime.now(timezone.utc) - earliest).days, 0)


# ---------------------------------------------------------------------------
# Instagram adapter
# ---------------------------------------------------------------------------


class InstagramAdapter(PlatformAdapter):
    platform = "instagram"

    def normalize(self, raw: dict[str, Any]) -> ProfileObservation:
        profile = raw.get("profile", {})
        posts = raw.get("posts", [])
        timestamps = [p.get("timestamp", "") for p in posts if p.get("timestamp")]

        # Instagram captions as text
        texts = [p.get("caption", "") for p in posts if p.get("caption")]
        voice = extract_voice_features(texts)
        kw_fp, cat_fp = extract_topics(texts)

        # Engagement analysis
        total_likes = sum(p.get("like_count", 0) for p in posts)
        total_comments = sum(p.get("comment_count", 0) for p in posts)
        avg_engagement = (total_likes + total_comments) / len(posts) if posts else 0

        # Estimate account age from earliest post timestamp
        age = self._estimate_age_from_timestamps(timestamps)

        return ProfileObservation(
            handle=profile.get("username", raw.get("handle", "")),
            platform=self.platform,
            display_name=profile.get("full_name"),
            audience_size=profile.get("follower_count", 0),
            following_count=profile.get("following_count", 0),
            is_verified=profile.get("is_verified", False),
            profile_completeness=self._calc_completeness(profile),
            activity_hours=self._extract_activity_hours(timestamps),
            activity_days=self._extract_activity_days(timestamps),
            post_texts=texts[:50],
            avg_utterance_length=voice.get("avg_utterance_length", 0),
            hashtag_rate=voice.get("hashtag_rate", 0),
            engagement_depth_ratio=min(math.log1p(profile.get("follower_count", 0) + total_likes + total_comments) / math.log1p(100000), 1.0),
            reciprocity_rate=min(total_comments / max(total_likes, 1), 1.0),
            keyword_fingerprint=kw_fp,
            category_fingerprint=cat_fp,
            posts_per_week_avg=len(posts) / 4 if posts else 0,
            growth_organicity=self._estimate_organicity(profile),
            # Scoring fields
            platform_tenure_days=age,
            regularity_score=self._compute_regularity(self._extract_activity_hours(timestamps)),
            emotional_volatility=self._compute_emotional_volatility(texts),
            posts_per_week_variance=self._compute_weekly_variance(timestamps, age),
            active_weeks_ratio=self._compute_active_weeks(timestamps, age),
            authority_index=min(math.log1p(profile.get("follower_count", 0)) / math.log1p(1000000), 1.0),
            anomaly_count=0,
            raw_payload=raw,
        )

    def _estimate_age_from_timestamps(self, timestamps: list) -> int:
        """Estimate account age from the earliest available post timestamp."""
        if not timestamps:
            return 0
        for ts in timestamps:
            try:
                dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                earliest = dt
                for ts2 in timestamps[1:]:
                    try:
                        dt2 = datetime.fromisoformat(str(ts2).replace("Z", "+00:00"))
                        if dt2 < earliest:
                            earliest = dt2
                    except (ValueError, TypeError):
                        continue
                return max((datetime.now(timezone.utc) - earliest).days, 0)
            except (ValueError, TypeError):
                continue
        return 0

    def _calc_completeness(self, profile: dict) -> float:
        fields = ["full_name", "biography", "external_url", "profile_pic_url", "category"]
        filled = sum(1 for f in fields if profile.get(f))
        return filled / len(fields)

    def _estimate_organicity(self, profile: dict) -> float:
        """Estimate growth organicity from follower/following ratio."""
        followers = profile.get("follower_count", 0)
        following = profile.get("following_count", 1) or 1
        ratio = followers / following
        # Very high ratio with low posts = suspicious
        posts = profile.get("media_count", 0) or 1
        engagement_per_post = followers / posts
        if ratio > 100 and engagement_per_post > 10000:
            return 0.3  # suspicious
        return min(ratio / 10, 1.0)


# ---------------------------------------------------------------------------
# Polymarket adapter
# ---------------------------------------------------------------------------


class PolymarketAdapter(PlatformAdapter):
    platform = "polymarket"

    def normalize(self, raw: dict[str, Any]) -> ProfileObservation:
        profile = raw.get("profile", {})
        positions = raw.get("positions", [])
        trades = raw.get("trades", [])

        timestamps = [t.get("timestamp", "") for t in trades if t.get("timestamp")]

        # Build topic fingerprint from market categories
        market_texts = [p.get("market_title", "") for p in positions if p.get("market_title")]
        kw_fp, cat_fp = extract_topics(market_texts)

        # Prediction accuracy
        resolved = [p for p in positions if p.get("resolved")]
        correct = sum(1 for p in resolved if p.get("outcome_correct"))
        accuracy = correct / len(resolved) if resolved else 0.0

        total_volume = sum(t.get("amount", 0) for t in trades)

        # Estimate age from earliest trade
        age = self._estimate_age_from_timestamps(timestamps)

        return ProfileObservation(
            handle=profile.get("username", raw.get("handle", "")),
            platform=self.platform,
            display_name=profile.get("display_name"),
            audience_size=0,
            profile_completeness=0.5,
            activity_hours=self._extract_activity_hours(timestamps),
            activity_days=self._extract_activity_days(timestamps),
            endorsement_count=int(total_volume),
            engagement_depth_ratio=min(accuracy * 0.5 + math.log1p(total_volume) / math.log1p(1000000) * 0.5, 1.0),
            reciprocity_rate=min(len(positions) / max(len(trades), 1), 1.0),
            growth_organicity=accuracy,
            keyword_fingerprint=kw_fp,
            category_fingerprint={**cat_fp, "prediction_markets": max(cat_fp.get("prediction_markets", 0), 0.5)},
            posts_per_week_avg=len(trades) / 4 if trades else 0,
            # Scoring fields
            platform_tenure_days=age,
            regularity_score=self._compute_regularity(self._extract_activity_hours(timestamps)),
            emotional_volatility=self._compute_emotional_volatility(market_texts),
            posts_per_week_variance=self._compute_weekly_variance(timestamps, age),
            active_weeks_ratio=self._compute_active_weeks(timestamps, age),
            authority_index=min(math.log1p(total_volume) / math.log1p(1000000), 1.0),
            anomaly_count=0,
            raw_payload=raw,
        )

    def _estimate_age_from_timestamps(self, timestamps: list) -> int:
        """Estimate account age from the earliest available timestamp."""
        if not timestamps:
            return 0
        for ts in timestamps:
            try:
                dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                earliest = dt
                for ts2 in timestamps[1:]:
                    try:
                        dt2 = datetime.fromisoformat(str(ts2).replace("Z", "+00:00"))
                        if dt2 < earliest:
                            earliest = dt2
                    except (ValueError, TypeError):
                        continue
                return max((datetime.now(timezone.utc) - earliest).days, 0)
            except (ValueError, TypeError):
                continue
        return 0


# ---------------------------------------------------------------------------
# 4chan adapter (archive-based)
# ---------------------------------------------------------------------------


class FourChanAdapter(PlatformAdapter):
    platform = "4chan"

    def normalize(self, raw: dict[str, Any]) -> ProfileObservation:
        """4chan is anonymous — we track posting patterns per tripcode/ID.

        Only useful when a tripcode or persistent ID is available from archives.
        Confidence is inherently low due to anonymity.
        """
        tripcode = raw.get("tripcode", raw.get("handle", ""))
        posts = raw.get("posts", [])
        timestamps = [p.get("time", "") for p in posts if p.get("time")]
        texts = [p.get("com", "") for p in posts if p.get("com")]

        # Clean HTML from 4chan posts
        clean_texts = [re.sub(r'<[^>]+>', '', t) for t in texts]

        voice = extract_voice_features(clean_texts)
        kw_fp, cat_fp = extract_topics(clean_texts)

        # Board participation
        boards: dict[str, int] = {}
        for p in posts:
            board = p.get("board", "")
            if board:
                boards[board] = boards.get(board, 0) + 1

        # Estimate age from earliest post timestamp
        age = self._estimate_age_from_timestamps(timestamps)

        return ProfileObservation(
            handle=tripcode,
            platform=self.platform,
            profile_completeness=0.1,  # Anonymous = low completeness
            activity_hours=self._extract_activity_hours(timestamps),
            activity_days=self._extract_activity_days(timestamps),
            post_texts=clean_texts[:100],
            avg_utterance_length=voice.get("avg_utterance_length", 0),
            vocabulary_richness=voice.get("vocabulary_richness", 0),
            formality_index=voice.get("formality_index", 0.5),
            keyword_fingerprint=kw_fp,
            category_fingerprint=cat_fp,
            posts_per_week_avg=len(posts) / 4 if posts else 0,
            # Scoring fields
            platform_tenure_days=age,
            regularity_score=self._compute_regularity(self._extract_activity_hours(timestamps)),
            emotional_volatility=self._compute_emotional_volatility(clean_texts),
            posts_per_week_variance=self._compute_weekly_variance(timestamps, age),
            active_weeks_ratio=self._compute_active_weeks(timestamps, age),
            authority_index=0.0,  # Anonymous — no authority signal
            anomaly_count=0,
            raw_payload=raw,
        )

    def _estimate_age_from_timestamps(self, timestamps: list) -> int:
        """Estimate age from the earliest available post timestamp."""
        if not timestamps:
            return 0
        earliest = None
        for ts in timestamps:
            try:
                if isinstance(ts, (int, float)):
                    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                else:
                    dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                if earliest is None or dt < earliest:
                    earliest = dt
            except (ValueError, TypeError, OSError):
                continue
        if earliest is None:
            return 0
        return max((datetime.now(timezone.utc) - earliest).days, 0)


# ---------------------------------------------------------------------------
# YCombinator adapter (company-focused)
# ---------------------------------------------------------------------------


class YCombinatorAdapter(PlatformAdapter):
    platform = "hackernews"

    def normalize(self, raw: dict[str, Any]) -> ProfileObservation:
        """Normalize YC company data into a company-type observation."""
        company = raw.get("company", {})
        founders = raw.get("founders", [])

        return ProfileObservation(
            handle=company.get("slug", raw.get("handle", "")),
            platform="hackernews",
            display_name=company.get("name"),
            entity_type="company",
            claimed_org=company.get("name"),
            funding_stage="seed" if company.get("batch") else None,
            yc_batch=company.get("batch"),
            founder_handles=[
                {"handle": f.get("hn_username", f.get("linkedin", "")), "platform": "hackernews"}
                for f in founders if f.get("hn_username") or f.get("linkedin")
            ],
            total_repos=company.get("github_repos", 0),
            total_stars=company.get("github_stars", 0),
            github_org=company.get("github_url", "").split("/")[-1] if company.get("github_url") else None,
            anomaly_count=0,
            raw_payload=raw,
        )


# ---------------------------------------------------------------------------
# YouTube adapter
# ---------------------------------------------------------------------------


class YouTubeAdapter(PlatformAdapter):
    platform = "youtube"

    def normalize(self, raw: dict[str, Any]) -> ProfileObservation:
        channel = raw.get("channel", {})
        videos = raw.get("videos", [])
        timestamps = [v.get("published_at", "") for v in videos if v.get("published_at")]

        # Extract topics from video titles and descriptions
        texts = []
        for v in videos:
            if v.get("title"):
                texts.append(v["title"])
            if v.get("description"):
                texts.append(v["description"][:500])

        kw_fp, cat_fp = extract_topics(texts)

        # Engagement analysis
        total_views = sum(v.get("view_count", 0) for v in videos)
        total_likes = sum(v.get("like_count", 0) for v in videos)
        total_comments = sum(v.get("comment_count", 0) for v in videos)

        avg_views = total_views / len(videos) if videos else 0
        avg_engagement = (total_likes + total_comments) / max(total_views, 1) if videos else 0

        subscribers = channel.get("subscriber_count", 0)
        video_count = channel.get("video_count", len(videos))

        age = self._calc_age(channel.get("published_at"))

        return ProfileObservation(
            handle=channel.get("custom_url", channel.get("id", raw.get("handle", ""))),
            platform=self.platform,
            display_name=channel.get("title"),
            account_age_days=age,
            audience_size=subscribers,
            is_verified=channel.get("is_verified", False),
            profile_completeness=self._calc_completeness(channel),
            activity_hours=self._extract_activity_hours(timestamps),
            activity_days=self._extract_activity_days(timestamps),
            engagement_depth_ratio=min(math.log1p(subscribers + total_likes + total_views / 100) / math.log1p(500000), 1.0),
            reciprocity_rate=min(total_comments / max(total_likes, 1), 1.0),
            endorsement_count=total_likes,
            keyword_fingerprint=kw_fp,
            category_fingerprint=cat_fp,
            claimed_role=channel.get("description", "")[:255] if channel.get("description") else None,
            posts_per_week_avg=video_count / max(age / 7, 1),
            growth_organicity=self._estimate_organicity(channel, videos),
            # Scoring fields
            platform_tenure_days=age,
            regularity_score=self._compute_regularity(self._extract_activity_hours(timestamps)),
            emotional_volatility=self._compute_emotional_volatility(texts),
            posts_per_week_variance=self._compute_weekly_variance(timestamps, age),
            active_weeks_ratio=self._compute_active_weeks(timestamps, age),
            authority_index=min(math.log1p(subscribers) / math.log1p(500000), 1.0),
            anomaly_count=0,
            raw_payload=raw,
        )

    def _calc_age(self, published_at: str | None) -> int:
        if not published_at:
            return 0
        try:
            dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            return max((datetime.now(timezone.utc) - dt).days, 0)
        except ValueError:
            return 0

    def _calc_completeness(self, channel: dict) -> float:
        fields = ["title", "description", "custom_url", "country", "banner_url"]
        filled = sum(1 for f in fields if channel.get(f))
        return filled / len(fields)

    def _estimate_organicity(self, channel: dict, videos: list) -> float:
        """Estimate growth organicity based on subscriber-to-view ratio."""
        subs = channel.get("subscriber_count", 0)
        total_views = sum(v.get("view_count", 0) for v in videos) or 1
        if subs > 0 and total_views > 0:
            ratio = total_views / subs
            if ratio < 0.1:  # Very few views per subscriber = suspicious
                return 0.3
            return min(ratio / 100, 1.0)
        return 0.5


# ---------------------------------------------------------------------------
# Bluesky adapter
# ---------------------------------------------------------------------------


class BlueskyAdapter(PlatformAdapter):
    platform = "bluesky"

    def normalize(self, raw: dict[str, Any]) -> ProfileObservation:
        profile = raw.get("profile", {})
        posts = raw.get("posts", [])
        timestamps = [p.get("created_at", p.get("indexedAt", "")) for p in posts if p.get("created_at") or p.get("indexedAt")]
        texts = [p.get("text", p.get("record", {}).get("text", "")) for p in posts]
        texts = [t for t in texts if t]

        voice = extract_voice_features(texts)
        kw_fp, cat_fp = extract_topics(texts)

        # Engagement
        total_likes = sum(p.get("like_count", p.get("likeCount", 0)) for p in posts)
        total_reposts = sum(p.get("repost_count", p.get("repostCount", 0)) for p in posts)
        total_replies = sum(p.get("reply_count", p.get("replyCount", 0)) for p in posts)
        reply_posts = sum(1 for p in posts if p.get("reply") or p.get("record", {}).get("reply"))

        avg_engagement = (total_likes + total_reposts + total_replies) / len(posts) if posts else 0

        age = self._calc_age(profile.get("createdAt", profile.get("indexedAt")))

        return ProfileObservation(
            handle=profile.get("handle", raw.get("handle", "")),
            platform=self.platform,
            display_name=profile.get("displayName"),
            account_age_days=age,
            audience_size=profile.get("followersCount", profile.get("followers_count", 0)),
            following_count=profile.get("followsCount", profile.get("following_count", 0)),
            profile_completeness=self._calc_completeness(profile),
            activity_hours=self._extract_activity_hours(timestamps),
            activity_days=self._extract_activity_days(timestamps),
            post_texts=texts[:100],
            avg_utterance_length=voice.get("avg_utterance_length", 0),
            vocabulary_richness=voice.get("vocabulary_richness", 0),
            formality_index=voice.get("formality_index", 0.5),
            question_ratio=voice.get("question_ratio", 0),
            hashtag_rate=voice.get("hashtag_rate", 0),
            link_sharing_rate=voice.get("link_sharing_rate", 0),
            engagement_depth_ratio=min(math.log1p(profile.get("followersCount", profile.get("followers_count", 0)) + total_likes + total_reposts) / math.log1p(50000), 1.0),
            reciprocity_rate=reply_posts / len(posts) if posts else 0,
            growth_organicity=min(profile.get("followersCount", profile.get("followers_count", 0)) / max(profile.get("followsCount", profile.get("following_count", 1)) or 1, 1) / 10, 1.0),
            endorsement_count=total_likes,
            keyword_fingerprint=kw_fp,
            category_fingerprint=cat_fp,
            claimed_role=profile.get("description", "")[:255] if profile.get("description") else None,
            posts_per_week_avg=len(posts) / max(age / 7, 1),
            # Scoring fields
            platform_tenure_days=age,
            regularity_score=self._compute_regularity(self._extract_activity_hours(timestamps)),
            emotional_volatility=self._compute_emotional_volatility(texts),
            posts_per_week_variance=self._compute_weekly_variance(timestamps, age),
            active_weeks_ratio=self._compute_active_weeks(timestamps, age),
            authority_index=min(math.log1p(profile.get("followersCount", profile.get("followers_count", 0))) / math.log1p(50000), 1.0),
            anomaly_count=0,
            raw_payload=raw,
        )

    def _calc_age(self, created_at: str | None) -> int:
        if not created_at:
            return 0
        try:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            return max((datetime.now(timezone.utc) - dt).days, 0)
        except ValueError:
            return 0

    def _calc_completeness(self, profile: dict) -> float:
        fields = ["displayName", "description", "avatar", "banner"]
        filled = sum(1 for f in fields if profile.get(f))
        return filled / len(fields)


# ---------------------------------------------------------------------------
# StackOverflow / StackExchange adapter
# ---------------------------------------------------------------------------


class StackExchangeAdapter(PlatformAdapter):
    platform = "stackexchange"

    def normalize(self, raw: dict[str, Any]) -> ProfileObservation:
        profile = raw.get("profile", {})
        answers = raw.get("answers", [])
        tags = raw.get("tags", [])

        # Extract texts from answers for voice analysis
        texts = [a.get("body", "") for a in answers if a.get("body")]
        timestamps = [a.get("creation_date", "") for a in answers if a.get("creation_date")]

        voice = extract_voice_features(texts)
        kw_fp, cat_fp = extract_topics(texts)

        # Enrich topic fingerprint from top tags
        if tags:
            total_count = sum(t.get("count", 0) for t in tags) or 1
            for t in tags:
                tag_name = t.get("name", "").lower()
                if tag_name:
                    kw_fp[tag_name] = max(kw_fp.get(tag_name, 0), t.get("count", 0) / total_count)

        reputation = profile.get("reputation", 0)
        badges = profile.get("badge_counts", {})
        badge_score = badges.get("gold", 0) * 100 + badges.get("silver", 0) * 10 + badges.get("bronze", 0)

        # Accepted answer ratio
        accepted = sum(1 for a in answers if a.get("is_accepted"))
        answer_quality = accepted / len(answers) if answers else 0

        age = self._calc_age(profile.get("creation_date"))
        total_posts = profile.get("answer_count", 0) + profile.get("question_count", 0)

        return ProfileObservation(
            handle=str(profile.get("user_id", raw.get("handle", ""))),
            platform=self.platform,
            display_name=profile.get("display_name"),
            account_age_days=age,
            audience_size=reputation,
            profile_completeness=self._calc_completeness(profile),
            activity_hours=self._extract_activity_hours(timestamps),
            activity_days=self._extract_activity_days(timestamps),
            post_texts=texts[:100],
            avg_utterance_length=voice.get("avg_utterance_length", 0),
            vocabulary_richness=voice.get("vocabulary_richness", 0),
            formality_index=voice.get("formality_index", 0.5),
            question_ratio=voice.get("question_ratio", 0),
            endorsement_count=reputation + badge_score,
            # Engagement: rep + answers + quality + badges all signal deep engagement
            engagement_depth_ratio=min(
                math.log1p(reputation + total_posts * 10 + badge_score) / math.log1p(50000), 1.0
            ),
            reciprocity_rate=answer_quality,  # answering questions is reciprocal engagement
            growth_organicity=min(reputation / max(total_posts * 20, 1), 1.0) if total_posts else 0.5,
            mention_response_rate=min(total_posts / max(age / 30, 1) / 10, 1.0) if total_posts else 0.0,
            keyword_fingerprint=kw_fp,
            category_fingerprint={**cat_fp, "programming": max(cat_fp.get("programming", 0), 0.5)},
            claimed_role=profile.get("about_me", "")[:255] if profile.get("about_me") else None,
            posts_per_week_avg=total_posts / max(age / 7, 1),
            # Scoring fields
            platform_tenure_days=age,
            regularity_score=self._compute_regularity(self._extract_activity_hours(timestamps)),
            emotional_volatility=self._compute_emotional_volatility(texts),
            posts_per_week_variance=self._compute_weekly_variance(timestamps, age),
            active_weeks_ratio=self._compute_active_weeks(timestamps, age) if timestamps else min(total_posts / max(age / 7, 1), 1.0),
            authority_index=min(math.log1p(reputation) / math.log1p(100000), 1.0),
            anomaly_count=0,
            raw_payload=raw,
        )

    def _calc_age(self, created: Any) -> int:
        if not created:
            return 0
        try:
            if isinstance(created, (int, float)):
                dt = datetime.fromtimestamp(created, tz=timezone.utc)
            else:
                return 0
            return max((datetime.now(timezone.utc) - dt).days, 0)
        except (ValueError, OSError):
            return 0

    def _calc_completeness(self, profile: dict) -> float:
        fields = ["display_name", "about_me", "location", "website_url", "profile_image"]
        filled = sum(1 for f in fields if profile.get(f))
        return filled / len(fields)


# ---------------------------------------------------------------------------
# Quora adapter (web-scraped, no public API)
# ---------------------------------------------------------------------------


class QuoraAdapter(PlatformAdapter):
    platform = "quora"

    def normalize(self, raw: dict[str, Any]) -> ProfileObservation:
        profile = raw.get("profile", {})
        answers = raw.get("answers", [])
        texts = [a.get("text", "") for a in answers if a.get("text")]
        timestamps = [a.get("created_at", a.get("timestamp", "")) for a in answers if a.get("created_at") or a.get("timestamp")]

        voice = extract_voice_features(texts)
        kw_fp, cat_fp = extract_topics(texts)

        # Estimate age from earliest answer timestamp
        age = self._estimate_age_from_timestamps(timestamps)

        return ProfileObservation(
            handle=profile.get("username", raw.get("handle", "")),
            platform=self.platform,
            display_name=profile.get("name"),
            audience_size=profile.get("follower_count", 0),
            following_count=profile.get("following_count", 0),
            profile_completeness=0.5 + (0.2 if profile.get("bio") else 0.0),
            activity_hours=self._extract_activity_hours(timestamps),
            activity_days=self._extract_activity_days(timestamps),
            post_texts=texts[:100],
            avg_utterance_length=voice.get("avg_utterance_length", 0),
            vocabulary_richness=voice.get("vocabulary_richness", 0),
            formality_index=voice.get("formality_index", 0.5),
            question_ratio=voice.get("question_ratio", 0),
            endorsement_count=profile.get("answer_views", 0),
            keyword_fingerprint=kw_fp,
            category_fingerprint=cat_fp,
            claimed_role=profile.get("bio", "")[:255] if profile.get("bio") else None,
            posts_per_week_avg=len(answers) / 4 if answers else 0,
            # Scoring fields
            platform_tenure_days=age,
            regularity_score=self._compute_regularity(self._extract_activity_hours(timestamps)),
            emotional_volatility=self._compute_emotional_volatility(texts),
            posts_per_week_variance=self._compute_weekly_variance(timestamps, age),
            active_weeks_ratio=self._compute_active_weeks(timestamps, age),
            authority_index=min(math.log1p(profile.get("follower_count", 0) + profile.get("answer_views", 0)) / math.log1p(100000), 1.0),
            anomaly_count=0,
            raw_payload=raw,
        )

    def _estimate_age_from_timestamps(self, timestamps: list) -> int:
        """Estimate account age from the earliest available timestamp."""
        if not timestamps:
            return 0
        earliest = None
        for ts in timestamps:
            try:
                dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                if earliest is None or dt < earliest:
                    earliest = dt
            except (ValueError, TypeError):
                continue
        if earliest is None:
            return 0
        return max((datetime.now(timezone.utc) - earliest).days, 0)


# ---------------------------------------------------------------------------
# Adapter registry
# ---------------------------------------------------------------------------

ADAPTERS: dict[str, PlatformAdapter] = {
    "twitter": TwitterAdapter(),
    "github": GitHubAdapter(),
    "reddit": RedditAdapter(),
    "hackernews": HackerNewsAdapter(),
    "linkedin": LinkedInAdapter(),
    "instagram": InstagramAdapter(),
    "polymarket": PolymarketAdapter(),
    "4chan": FourChanAdapter(),
    "ycombinator": YCombinatorAdapter(),
    "youtube": YouTubeAdapter(),
    "bluesky": BlueskyAdapter(),
    "stackoverflow": StackExchangeAdapter(),
    "stackexchange": StackExchangeAdapter(),
    "quora": QuoraAdapter(),
}


def get_adapter(platform: str) -> PlatformAdapter | None:
    return ADAPTERS.get(platform)


def normalize_observation(platform: str, raw_data: dict[str, Any]) -> ProfileObservation | None:
    """Convenience function: normalize raw platform data into canonical observation."""
    adapter = get_adapter(platform)
    if not adapter:
        return None
    return adapter.normalize(raw_data)
