"""Unified crawling interface with automatic 3-tier fallback.

Fallback chain:
  1. httpx (public APIs)   — GitHub, HN, SO, Reddit. Fastest, free, no browser.
  2. Lightpanda (headless) — Fast DOM scraping for simple pages. 10x faster than Chrome.
  3. Playwright (full)     — Authenticated SPA scraping. LinkedIn, Twitter, Instagram.

Each tier is tried in order. If a tier fails or returns no data, the next one
is attempted. The caller gets the result + which source provided it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("tovbase.crawler")


@dataclass
class CrawlResult:
    """Result from crawling a profile."""

    raw_data: dict[str, Any] | None = None
    source: str = "none"  # "api", "lightpanda", "playwright", "none"
    platform: str = ""
    handle: str = ""
    error: str | None = None


# Platforms that have free public API endpoints (no auth needed)
API_PLATFORMS = {"github", "hackernews", "reddit", "stackoverflow", "stackexchange"}

# Platforms that work with simple headless DOM (no login required, no heavy JS)
LIGHTPANDA_PLATFORMS = {"hackernews", "stackoverflow", "github", "reddit", "bluesky"}

# Platforms that need full authenticated browser (login + SPA rendering)
PLAYWRIGHT_PLATFORMS = {"twitter", "linkedin", "instagram", "youtube", "polymarket"}


async def crawl_profile(platform: str, handle: str, display_name: str | None = None) -> CrawlResult:
    """Crawl a profile using the best available method with automatic fallback.

    Args:
        platform: Target platform identifier
        handle: Profile handle/username
        display_name: Optional name for cross-platform search

    Returns:
        CrawlResult with raw_data (or None if all methods failed)
    """
    result = CrawlResult(platform=platform, handle=handle)

    # ── Tier 1: Public API (httpx) ─────────────────────────────
    if platform in API_PLATFORMS:
        try:
            data = _try_api(platform, handle, display_name)
            if data:
                result.raw_data = data
                result.source = "api"
                logger.info("Crawled %s/%s via API", platform, handle)
                return result
        except Exception as e:
            logger.debug("API crawl failed for %s/%s: %s", platform, handle, e)

    # ── Tier 2: Lightpanda (fast headless) ─────────────────────
    if platform in LIGHTPANDA_PLATFORMS:
        try:
            data = await _try_lightpanda(platform, handle)
            if data:
                result.raw_data = data
                result.source = "lightpanda"
                logger.info("Crawled %s/%s via Lightpanda", platform, handle)
                return result
        except Exception as e:
            logger.debug("Lightpanda crawl failed for %s/%s: %s", platform, handle, e)

    # ── Tier 3: Playwright (authenticated full browser) ────────
    try:
        data = await _try_playwright(platform, handle)
        if data:
            result.raw_data = data
            result.source = "playwright"
            logger.info("Crawled %s/%s via Playwright", platform, handle)
            return result
    except Exception as e:
        logger.debug("Playwright crawl failed for %s/%s: %s", platform, handle, e)

    result.error = "All crawl methods failed"
    logger.warning("All crawl methods failed for %s/%s", platform, handle)
    return result


def _try_api(platform: str, handle: str, display_name: str | None = None) -> dict | None:
    """Try to fetch profile data via public API (synchronous httpx)."""
    from app.services.enrichment import (
        ENRICHMENT_FUNCTIONS,
        fetch_stackexchange_profile,
        search_github_by_name,
        _is_substantive_profile,
    )

    # Direct handle lookup
    fetch_fn = ENRICHMENT_FUNCTIONS.get(platform)
    if fetch_fn:
        raw = fetch_fn(handle)
        if raw and _is_substantive_profile(platform, raw):
            return raw

    # Name-based search fallback (GitHub, StackExchange)
    if display_name:
        if platform == "github":
            raw = search_github_by_name(display_name)
            if raw and _is_substantive_profile("github", raw):
                return raw
        elif platform in ("stackoverflow", "stackexchange"):
            raw = fetch_stackexchange_profile(display_name, "stackoverflow")
            if raw:
                return raw

    return None


async def _try_lightpanda(platform: str, handle: str) -> dict | None:
    """Try to scrape via Lightpanda's CDP endpoint.

    Lightpanda runs as a separate service (Docker or local binary) on port 9222.
    We connect via Playwright's connect_over_cdp() to reuse the same scraper
    functions but with Lightpanda's faster headless engine.
    """
    from app.config import settings

    lightpanda_url = getattr(settings, "lightpanda_url", "")
    if not lightpanda_url:
        return None

    try:
        from playwright.async_api import async_playwright
        from app.services.scraper import PLAYWRIGHT_SCRAPERS, PLATFORM_PROFILE_URLS

        template = PLATFORM_PROFILE_URLS.get(platform)
        if not template:
            return None
        url = template.format(handle=handle)

        scraper_func = PLAYWRIGHT_SCRAPERS.get(platform)
        if not scraper_func:
            return None

        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(lightpanda_url)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            )
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(2000)

            raw_data = await scraper_func(page, handle)

            await context.close()
            await browser.close()
            return raw_data

    except ImportError:
        logger.debug("Playwright not installed — skipping Lightpanda tier")
        return None
    except Exception as e:
        logger.debug("Lightpanda connection failed: %s", e)
        return None


async def _try_playwright(platform: str, handle: str) -> dict | None:
    """Try to scrape via Playwright with authenticated persistent browser profiles."""
    try:
        from app.services.scraper import get_scraper_pool
        pool = get_scraper_pool()
        return await pool.scrape_profile(platform, handle)
    except ImportError:
        logger.debug("Playwright not installed — skipping Playwright tier")
        return None
    except Exception as e:
        logger.debug("Playwright scrape failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Batch crawling for cross-platform discovery
# ---------------------------------------------------------------------------


async def crawl_and_discover(
    handle: str,
    display_name: str | None = None,
    source_platform: str | None = None,
) -> list[CrawlResult]:
    """Discover and crawl profiles across all platforms.

    Combines API enrichment discovery with browser-based crawling as fallback.
    Returns a list of CrawlResults for each discovered profile.
    """
    from app.services.enrichment import discover_and_fetch

    results: list[CrawlResult] = []

    # Phase 1: API-based discovery (fast, no browser)
    discovered = discover_and_fetch(handle, display_name, exclude_platform=source_platform)
    for entry in discovered:
        results.append(CrawlResult(
            raw_data=entry["raw_data"],
            source="api",
            platform=entry["platform"],
            handle=entry["handle"],
        ))

    # Phase 2: For platforms not found via API, try browser crawling
    found_platforms = {r.platform for r in results}
    remaining = PLAYWRIGHT_PLATFORMS - found_platforms - {source_platform or ""}

    for platform in remaining:
        # Try handle-based crawl on auth-required platforms
        result = await crawl_profile(platform, handle, display_name)
        if result.raw_data:
            results.append(result)

    return results
