"""Tests for topic intelligence service — feed parsing, ingestion, and query."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.services.topics import (
    FeedItem,
    TopicQuery,
    TopicQueryResponse,
    TopicResult,
    ingest_social_items,
    parse_feed,
)


# ---------------------------------------------------------------------------
# Feed parsing tests
# ---------------------------------------------------------------------------


class TestRSSParsing:
    def test_parse_rss2(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <title>Test Feed</title>
            <item>
              <title>Test Article</title>
              <link>https://example.com/article1</link>
              <description>This is about machine learning and AI.</description>
              <pubDate>Mon, 28 Mar 2026 14:00:00 GMT</pubDate>
              <guid>https://example.com/article1</guid>
              <category>Technology</category>
            </item>
            <item>
              <title>Another Article</title>
              <link>https://example.com/article2</link>
              <description>Python programming best practices.</description>
              <pubDate>Sun, 27 Mar 2026 10:00:00 GMT</pubDate>
            </item>
          </channel>
        </rss>"""
        items = parse_feed(xml)
        assert len(items) == 2
        assert items[0].title == "Test Article"
        assert items[0].link == "https://example.com/article1"
        assert items[0].published is not None
        assert "Technology" in items[0].categories

    def test_parse_atom(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <title>Atom Feed</title>
          <entry>
            <title>Atom Entry</title>
            <link href="https://example.com/atom1" rel="alternate"/>
            <summary>Kubernetes deployment strategies.</summary>
            <published>2026-03-28T12:00:00Z</published>
            <id>urn:uuid:test-atom-1</id>
            <author><name>John Doe</name></author>
          </entry>
        </feed>"""
        items = parse_feed(xml)
        assert len(items) == 1
        assert items[0].title == "Atom Entry"
        assert items[0].link == "https://example.com/atom1"
        assert items[0].author == "John Doe"
        assert items[0].published is not None

    def test_parse_invalid_xml(self):
        items = parse_feed("this is not xml at all")
        assert items == []

    def test_parse_empty_feed(self):
        xml = """<?xml version="1.0"?><rss version="2.0"><channel><title>Empty</title></channel></rss>"""
        items = parse_feed(xml)
        assert items == []


class TestFeedItem:
    def test_defaults(self):
        item = FeedItem()
        assert item.title == ""
        assert item.link == ""
        assert item.published is None
        assert item.categories == []


# ---------------------------------------------------------------------------
# Adapter tests for new platforms
# ---------------------------------------------------------------------------


class TestYouTubeAdapter:
    def test_basic_normalization(self):
        from app.services.ingestion import normalize_observation

        raw = {
            "channel": {
                "id": "UC123",
                "custom_url": "@techchannel",
                "title": "Tech Channel",
                "published_at": "2020-01-01T00:00:00Z",
                "subscriber_count": 50000,
                "video_count": 200,
                "description": "We talk about programming and AI",
                "country": "US",
            },
            "videos": [
                {
                    "title": "Rust programming tutorial",
                    "description": "Learn Rust from scratch",
                    "published_at": "2026-03-28T10:00:00Z",
                    "view_count": 5000,
                    "like_count": 200,
                    "comment_count": 30,
                },
                {
                    "title": "Python vs JavaScript comparison",
                    "description": "Which language should you learn?",
                    "published_at": "2026-03-27T14:00:00Z",
                    "view_count": 12000,
                    "like_count": 500,
                    "comment_count": 80,
                },
            ],
        }
        obs = normalize_observation("youtube", raw)
        assert obs is not None
        assert obs.handle == "@techchannel"
        assert obs.platform == "youtube"
        assert obs.audience_size == 50000
        assert obs.endorsement_count == 700  # total likes
        assert len(obs.keyword_fingerprint) > 0


class TestBlueskyAdapter:
    def test_basic_normalization(self):
        from app.services.ingestion import normalize_observation

        raw = {
            "profile": {
                "handle": "alice.bsky.social",
                "displayName": "Alice",
                "followersCount": 1200,
                "followsCount": 300,
                "description": "Software engineer interested in distributed systems",
                "createdAt": "2023-06-15T00:00:00Z",
                "avatar": "https://example.com/avatar.jpg",
            },
            "posts": [
                {
                    "text": "Just deployed a new Kubernetes cluster for our AI pipeline",
                    "created_at": "2026-03-28T09:00:00Z",
                    "likeCount": 15,
                    "repostCount": 3,
                    "replyCount": 2,
                },
                {
                    "text": "What's everyone using for observability these days?",
                    "created_at": "2026-03-27T16:00:00Z",
                    "likeCount": 8,
                    "repostCount": 1,
                    "replyCount": 5,
                    "reply": True,
                },
            ],
        }
        obs = normalize_observation("bluesky", raw)
        assert obs is not None
        assert obs.handle == "alice.bsky.social"
        assert obs.platform == "bluesky"
        assert obs.audience_size == 1200
        assert obs.account_age_days > 0
        assert obs.endorsement_count == 23  # total likes
        assert len(obs.keyword_fingerprint) > 0


# ---------------------------------------------------------------------------
# Adapter registry completeness
# ---------------------------------------------------------------------------


class TestAdapterRegistry:
    def test_all_platforms_registered(self):
        from app.services.ingestion import ADAPTERS

        expected = {
            "twitter", "github", "reddit", "hackernews", "linkedin",
            "instagram", "polymarket", "4chan", "ycombinator",
            "youtube", "bluesky",
        }
        assert expected.issubset(set(ADAPTERS.keys()))
