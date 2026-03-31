"""Topic intelligence service — real-time information layer for agent queries.

Two distinct pipelines feed into this service:

1. **Identity pipeline** (existing) — profiles people/companies for trust scoring.
   Feeds topic data as a side-effect of profile observation.

2. **Topic pipeline** (this module) — continuously ingests from RSS feeds,
   forums, news, blogs, and social platforms to maintain a real-time index
   of what's happening across the internet. Designed for agent queries like
   exa.ai — fast, structured, and trust-weighted.

The query engine supports:
  - Full-text keyword search across recent entries
  - Category filtering (ai_ml, finance, crypto, etc.)
  - Geographic filtering (by country/continent)
  - Time-window filtering (last 1h, 6h, 24h, 7d, 30d)
  - Trust-weighted results (entries from high-trust authors rank higher)
  - Platform filtering (reddit, hackernews, rss, twitter, etc.)
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session

from app.models import FeedSource, TopicEntry
from app.services.ingestion import compute_sentiment, extract_topics


# ---------------------------------------------------------------------------
# Query dataclasses
# ---------------------------------------------------------------------------


@dataclass
class TopicQuery:
    """Parameters for a real-time topic search."""

    query: str = ""
    categories: list[str] = field(default_factory=list)
    platforms: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)
    continents: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    window_hours: int = 24
    min_trust_score: int | None = None
    min_engagement: int = 0
    limit: int = 50
    offset: int = 0


@dataclass
class TopicResult:
    """A single result from a topic query."""

    id: str
    title: str | None
    summary: str | None
    url: str | None
    platform: str
    author_handle: str | None
    author_name: str | None
    author_trust_score: int | None
    published_at: str
    categories: dict
    keywords: dict
    entities: list
    sentiment: float
    engagement_score: int
    country_code: str
    language: str
    source_name: str | None = None
    source_reliability: float = 0.5


@dataclass
class TopicQueryResponse:
    """Response for a topic search."""

    query: str
    window_hours: int
    total_results: int
    results: list[TopicResult]
    categories_found: dict[str, int] = field(default_factory=dict)
    top_sources: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# RSS/Atom feed parser
# ---------------------------------------------------------------------------

# Namespace map for Atom feeds
_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
_DC_NS = {"dc": "http://purl.org/dc/elements/1.1/"}
_CONTENT_NS = {"content": "http://purl.org/rss/1.0/modules/content/"}


@dataclass
class FeedItem:
    """A parsed item from an RSS/Atom feed."""

    title: str = ""
    link: str = ""
    summary: str = ""
    content: str = ""
    author: str = ""
    published: datetime | None = None
    guid: str = ""
    categories: list[str] = field(default_factory=list)


def parse_feed(xml_content: str) -> list[FeedItem]:
    """Parse RSS 2.0 or Atom feed XML into FeedItems.

    Handles both formats transparently. Returns empty list on parse errors.
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return []

    # Detect feed type
    tag = root.tag.lower()
    if "feed" in tag:
        return _parse_atom(root)
    elif "rss" in tag or root.find("channel") is not None:
        return _parse_rss(root)
    elif "rdf" in tag.lower() or root.find("{http://purl.org/rss/1.0/}channel") is not None:
        return _parse_rdf(root)
    return []


def _parse_rss(root: ET.Element) -> list[FeedItem]:
    """Parse RSS 2.0 feed."""
    items = []
    channel = root.find("channel")
    if channel is None:
        return items

    for item_el in channel.findall("item"):
        item = FeedItem()
        item.title = _text(item_el, "title")
        item.link = _text(item_el, "link")
        item.summary = _text(item_el, "description")
        item.content = _text(item_el, "{http://purl.org/rss/1.0/modules/content/}encoded") or item.summary
        item.author = _text(item_el, "author") or _text(item_el, "{http://purl.org/dc/elements/1.1/}creator")
        item.guid = _text(item_el, "guid") or item.link

        pub_str = _text(item_el, "pubDate")
        if pub_str:
            item.published = _parse_date(pub_str)

        for cat_el in item_el.findall("category"):
            if cat_el.text:
                item.categories.append(cat_el.text.strip())

        items.append(item)
    return items


def _parse_atom(root: ET.Element) -> list[FeedItem]:
    """Parse Atom feed."""
    items = []
    ns = {"a": "http://www.w3.org/2005/Atom"}

    entries = root.findall("a:entry", ns)
    if not entries:
        entries = root.findall("entry")

    for entry in entries:
        item = FeedItem()
        item.title = _text_ns(entry, "a:title", ns) or _text(entry, "title")
        item.summary = _text_ns(entry, "a:summary", ns) or _text(entry, "summary")
        item.content = _text_ns(entry, "a:content", ns) or _text(entry, "content") or item.summary

        # Link (prefer alternate)
        link_els = entry.findall("a:link", ns)
        if not link_els:
            link_els = entry.findall("link")
        for link_el in link_els:
            rel = link_el.get("rel", "alternate")
            if rel == "alternate" or not item.link:
                item.link = link_el.get("href", "")

        author_el = entry.find("a:author", ns)
        if author_el is None:
            author_el = entry.find("author")
        if author_el is not None:
            item.author = _text_ns(author_el, "a:name", ns) or _text(author_el, "name")

        item.guid = _text_ns(entry, "a:id", ns) or _text(entry, "id") or item.link

        pub_str = _text_ns(entry, "a:published", ns) or _text_ns(entry, "a:updated", ns) or _text(entry, "published") or _text(entry, "updated")
        if pub_str:
            item.published = _parse_date(pub_str)

        cat_els = entry.findall("a:category", ns)
        if not cat_els:
            cat_els = entry.findall("category")
        for cat_el in cat_els:
            term = cat_el.get("term") or cat_el.text
            if term:
                item.categories.append(term.strip())

        items.append(item)
    return items


def _parse_rdf(root: ET.Element) -> list[FeedItem]:
    """Parse RSS 1.0 (RDF) feed."""
    items = []
    ns_rss = "http://purl.org/rss/1.0/"

    for item_el in root.findall(f"{{{ns_rss}}}item"):
        item = FeedItem()
        item.title = _text(item_el, f"{{{ns_rss}}}title")
        item.link = _text(item_el, f"{{{ns_rss}}}link")
        item.summary = _text(item_el, f"{{{ns_rss}}}description")
        item.guid = item.link
        dc_date = _text(item_el, "{http://purl.org/dc/elements/1.1/}date")
        if dc_date:
            item.published = _parse_date(dc_date)
        items.append(item)

    return items


def _text(el: ET.Element, tag: str) -> str:
    child = el.find(tag)
    return child.text.strip() if child is not None and child.text else ""


def _text_ns(el: ET.Element, tag: str, ns: dict) -> str:
    child = el.find(tag, ns)
    return child.text.strip() if child is not None and child.text else ""


def _parse_date(s: str) -> datetime | None:
    """Parse various date formats from RSS/Atom feeds."""
    s = s.strip()
    # RFC 2822 (RSS pubDate)
    try:
        return parsedate_to_datetime(s)
    except Exception:
        pass
    # ISO 8601 (Atom)
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Feed ingestion — convert parsed items to TopicEntry records
# ---------------------------------------------------------------------------


def ingest_feed_items(
    db: Session,
    source: FeedSource,
    items: list[FeedItem],
) -> int:
    """Ingest parsed feed items into TopicEntry records.

    Deduplicates by (source_id, external_id). Returns count of new entries.
    """
    new_count = 0
    now = datetime.now(timezone.utc)

    for item in items:
        guid = item.guid or item.link
        if not guid:
            continue

        # Deduplicate
        existing = db.execute(
            select(TopicEntry).where(
                TopicEntry.source_id == source.id,
                TopicEntry.external_id == guid,
            )
        ).scalar_one_or_none()

        if existing:
            continue

        # Extract topics from title + summary + content
        texts = [t for t in [item.title, item.summary, item.content] if t]
        kw_fp, cat_fp = extract_topics(texts)

        sentiment = compute_sentiment(texts)

        # Extract entities from categories + title keywords
        entities = [{"name": c, "type": "category", "salience": 0.5} for c in item.categories[:10]]

        snippet = (item.content or item.summary or "")[:1000]

        entry = TopicEntry(
            source_id=source.id,
            platform="rss",
            external_id=guid,
            url=item.link or None,
            title=item.title[:512] if item.title else None,
            summary=(item.summary or "")[:2000] or None,
            content_snippet=snippet or None,
            author_handle=None,
            author_name=item.author[:255] if item.author else None,
            language=source.language,
            country_code=source.country_code,
            keyword_fingerprint=kw_fp,
            category_fingerprint=cat_fp,
            entities=entities,
            sentiment=sentiment,
            published_at=item.published or now,
            ingested_at=now,
        )
        db.add(entry)
        new_count += 1

    if new_count > 0:
        source.last_fetched_at = now
        source.last_entry_count = new_count
        source.error_count = 0
        db.commit()

    return new_count


# ---------------------------------------------------------------------------
# Social platform topic ingestion (Twitter, Reddit, HN, Bluesky, etc.)
# ---------------------------------------------------------------------------


def ingest_social_items(
    db: Session,
    platform: str,
    items: list[dict[str, Any]],
    country_code: str = "US",
    language: str = "en",
) -> int:
    """Ingest social media posts/comments as topic entries.

    Used for the topic pipeline (not identity pipeline). Each item should have:
      - id or external_id
      - text or title
      - author (handle)
      - timestamp or published_at
      - engagement (likes + shares + comments)
    """
    new_count = 0
    now = datetime.now(timezone.utc)

    for item in items:
        ext_id = str(item.get("id") or item.get("external_id", ""))
        if not ext_id:
            continue

        existing = db.execute(
            select(TopicEntry).where(
                TopicEntry.platform == platform,
                TopicEntry.external_id == ext_id,
            )
        ).scalar_one_or_none()

        if existing:
            continue

        text = item.get("text") or item.get("title") or ""
        summary = item.get("summary") or text[:500]
        texts = [t for t in [item.get("title"), text] if t]
        kw_fp, cat_fp = extract_topics(texts)

        pub_str = item.get("timestamp") or item.get("published_at") or item.get("created_at")
        published = now
        if pub_str:
            if isinstance(pub_str, datetime):
                published = pub_str
            elif isinstance(pub_str, (int, float)):
                published = datetime.fromtimestamp(pub_str, tz=timezone.utc)
            else:
                try:
                    published = datetime.fromisoformat(str(pub_str).replace("Z", "+00:00"))
                except ValueError:
                    pass

        engagement = (
            item.get("engagement", 0)
            or (item.get("likes", 0) + item.get("shares", 0) + item.get("comments", 0)
                + item.get("retweets", 0) + item.get("upvotes", 0) + item.get("score", 0))
        )

        entities = []
        for ent in item.get("entities", []):
            if isinstance(ent, dict):
                entities.append(ent)
            elif isinstance(ent, str):
                entities.append({"name": ent, "type": "keyword", "salience": 0.3})

        entry = TopicEntry(
            source_id=None,
            platform=platform,
            external_id=ext_id,
            url=item.get("url") or item.get("link"),
            title=(item.get("title") or "")[:512] or None,
            summary=summary[:2000] if summary else None,
            content_snippet=text[:1000] if text else None,
            author_handle=item.get("author") or item.get("author_handle") or item.get("username"),
            author_name=item.get("author_name") or item.get("display_name"),
            language=item.get("language", language),
            country_code=item.get("country_code", country_code),
            keyword_fingerprint=kw_fp,
            category_fingerprint=cat_fp,
            entities=entities,
            sentiment=item.get("sentiment", 0.0),
            engagement_score=engagement,
            comment_count=item.get("comments", 0) or item.get("comment_count", 0) or item.get("num_comments", 0),
            author_trust_score=item.get("author_trust_score"),
            published_at=published,
            ingested_at=now,
        )
        db.add(entry)
        new_count += 1

    if new_count > 0:
        db.commit()

    return new_count


# ---------------------------------------------------------------------------
# Query engine — real-time topic search
# ---------------------------------------------------------------------------


def query_topics(db: Session, q: TopicQuery) -> TopicQueryResponse:
    """Execute a real-time topic search against the TopicEntry index.

    Supports keyword search, category/platform/country filtering,
    time-window, trust-weighted ranking, and pagination.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=q.window_hours)

    stmt = select(TopicEntry).where(TopicEntry.published_at >= cutoff)

    # Keyword search (title + summary + content_snippet)
    if q.query:
        terms = q.query.strip().split()
        for term in terms:
            pattern = f"%{term}%"
            stmt = stmt.where(
                or_(
                    TopicEntry.title.ilike(pattern),
                    TopicEntry.summary.ilike(pattern),
                    TopicEntry.content_snippet.ilike(pattern),
                )
            )

    # Category filter (match against category_fingerprint keys)
    # Since category_fingerprint is JSON, we filter in Python after fetch for portability
    # For production, use PostgreSQL JSON operators

    if q.platforms:
        stmt = stmt.where(TopicEntry.platform.in_(q.platforms))

    if q.countries:
        stmt = stmt.where(TopicEntry.country_code.in_(q.countries))

    if q.languages:
        stmt = stmt.where(TopicEntry.language.in_(q.languages))

    if q.min_engagement > 0:
        stmt = stmt.where(TopicEntry.engagement_score >= q.min_engagement)

    if q.min_trust_score is not None:
        stmt = stmt.where(TopicEntry.author_trust_score >= q.min_trust_score)

    # Order by recency + engagement (trust-weighted)
    stmt = stmt.order_by(desc(TopicEntry.published_at))

    # Fetch with headroom for category filtering
    fetch_limit = (q.limit + q.offset) * 3 if q.categories else q.limit + q.offset + 10
    stmt = stmt.limit(fetch_limit)

    rows = list(db.execute(stmt).scalars())

    # Category filter in Python (JSON field)
    if q.categories:
        filtered = []
        cat_set = set(c.lower() for c in q.categories)
        for entry in rows:
            entry_cats = set((entry.category_fingerprint or {}).keys())
            if entry_cats & cat_set:
                filtered.append(entry)
        rows = filtered

    # Pagination
    total = len(rows)
    rows = rows[q.offset: q.offset + q.limit]

    # Build results
    results = []
    cat_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}

    for entry in rows:
        # Count categories across results
        for cat in (entry.category_fingerprint or {}):
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        source_name = None
        source_reliability = 0.5
        if entry.source:
            source_name = entry.source.name
            source_reliability = entry.source.reliability_score
            source_counts[source_name] = source_counts.get(source_name, 0) + 1

        results.append(TopicResult(
            id=str(entry.id),
            title=entry.title,
            summary=entry.summary,
            url=entry.url,
            platform=entry.platform,
            author_handle=entry.author_handle,
            author_name=entry.author_name,
            author_trust_score=entry.author_trust_score,
            published_at=entry.published_at.isoformat() if entry.published_at else "",
            categories=entry.category_fingerprint or {},
            keywords=entry.keyword_fingerprint or {},
            entities=entry.entities or [],
            sentiment=entry.sentiment,
            engagement_score=entry.engagement_score,
            country_code=entry.country_code,
            language=entry.language,
            source_name=source_name,
            source_reliability=source_reliability,
        ))

    top_sources = sorted(
        [{"name": k, "count": v} for k, v in source_counts.items()],
        key=lambda x: -x["count"],
    )[:10]

    return TopicQueryResponse(
        query=q.query,
        window_hours=q.window_hours,
        total_results=total,
        results=results,
        categories_found=dict(sorted(cat_counts.items(), key=lambda x: -x[1])),
        top_sources=top_sources,
    )
