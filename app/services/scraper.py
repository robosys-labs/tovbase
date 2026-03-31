"""Playwright-based scraping pool with persistent browser profiles.

Uses persistent Chromium contexts so sessions survive restarts.
Each platform has its own browser profile directory — log in once via
scripts/setup_browsers.py, then scrape authenticated pages headlessly.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

logger = logging.getLogger("tovbase.scraper")

PROFILE_DIR = Path(os.getenv("BROWSER_PROFILE_DIR", "data/browser_profiles"))

# Platform login URLs for setup_browsers.py
PLATFORM_LOGIN_URLS = {
    "twitter": "https://x.com/login",
    "linkedin": "https://www.linkedin.com/login",
    "github": "https://github.com/login",
    "instagram": "https://www.instagram.com/accounts/login/",
    "reddit": "https://www.reddit.com/login/",
    "youtube": "https://accounts.google.com/ServiceLogin?service=youtube",
    "bluesky": "https://bsky.app/",
    "polymarket": "https://polymarket.com/",
}

# Platform profile URL templates
PLATFORM_PROFILE_URLS = {
    "twitter": "https://x.com/{handle}",
    "linkedin": "https://www.linkedin.com/in/{handle}",
    "github": "https://github.com/{handle}",
    "instagram": "https://www.instagram.com/{handle}/",
    "reddit": "https://www.reddit.com/user/{handle}/",
    "hackernews": "https://news.ycombinator.com/user?id={handle}",
    "youtube": "https://www.youtube.com/@{handle}",
    "bluesky": "https://bsky.app/profile/{handle}",
    "polymarket": "https://polymarket.com/profile/{handle}",
    "stackoverflow": "https://stackoverflow.com/users/{handle}",
    "quora": "https://www.quora.com/profile/{handle}",
}

# Search URL templates for cross-platform discovery
SEARCH_TEMPLATES = {
    "twitter": '"{name}" site:x.com OR site:twitter.com',
    "github": '"{name}" site:github.com',
    "linkedin": '"{name}" site:linkedin.com/in/',
    "instagram": '"{name}" site:instagram.com',
    "reddit": '"{name}" site:reddit.com/user/',
}


# URLs to test if a session is authenticated (navigates here, checks for login redirect)
SESSION_TEST = {
    "twitter":   {"url": "https://x.com/home",                          "login_indicator": "/login",          "auth_indicator": "/home"},
    "linkedin":  {"url": "https://www.linkedin.com/feed/",              "login_indicator": "/login",          "auth_indicator": "/feed"},
    "instagram": {"url": "https://www.instagram.com/accounts/activity/","login_indicator": "/accounts/login", "auth_indicator": "activity"},
    "reddit":    {"url": "https://www.reddit.com/settings/",            "login_indicator": "/login",          "auth_indicator": "settings"},
    "youtube":   {"url": "https://studio.youtube.com/",                 "login_indicator": "accounts.google", "auth_indicator": "studio"},
    "github":    {"url": "https://github.com/settings/profile",         "login_indicator": "/login",          "auth_indicator": "settings"},
    "bluesky":   {"url": "https://bsky.app/notifications",              "login_indicator": "/login",          "auth_indicator": "notifications"},
}


class ScraperPool:
    """Manages persistent Playwright browser contexts for scraping and auth.

    Each async operation creates its own Playwright instance because Playwright
    is not thread-safe and different operations may run in different threads
    (e.g., admin auth from API thread vs scrape from Celery worker).
    The persistent browser profile on disk is the shared state.
    """

    def __init__(self):
        self._login_contexts: dict[str, object] = {}
        self._login_pw: dict[str, object] = {}  # playwright instances for login browsers

    async def _new_playwright(self):
        from playwright.async_api import async_playwright
        pw_manager = async_playwright()
        return await pw_manager.start(), pw_manager

    async def get_context(self, platform: str):
        """Create a persistent browser context for a platform.

        Each call creates a fresh Playwright + context pair. The caller is
        responsible for closing both when done. The persistent profile on
        disk is the shared state across calls.
        """
        pw, _mgr = await self._new_playwright()
        profile_path = str(PROFILE_DIR / platform)
        os.makedirs(profile_path, exist_ok=True)

        ctx = await pw.chromium.launch_persistent_context(
            user_data_dir=profile_path,
            headless=True,
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )
        return ctx

    async def scrape_profile(self, platform: str, handle: str, url: str | None = None) -> dict | None:
        """Scrape a profile page and return raw data dict for the ingest pipeline."""
        if not url:
            template = PLATFORM_PROFILE_URLS.get(platform)
            if not template:
                logger.warning("No URL template for platform: %s", platform)
                return None
            url = template.format(handle=handle)

        ctx = None
        try:
            ctx = await self.get_context(platform)
            page = await ctx.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)

            scraper_func = PLAYWRIGHT_SCRAPERS.get(platform)
            if not scraper_func:
                logger.warning("No Playwright scraper for platform: %s", platform)
                return None

            raw_data = await scraper_func(page, handle)
            return raw_data

        except Exception as e:
            logger.error("Scrape failed for %s/%s: %s", platform, handle, e)
            return None
        finally:
            if ctx:
                try:
                    await ctx.close()
                except Exception:
                    pass

    async def discover_profiles(self, display_name: str, exclude_platform: str | None = None) -> list[dict]:
        """Search for a person's profiles across platforms using Google search."""
        discovered = []

        for platform, template in SEARCH_TEMPLATES.items():
            if platform == exclude_platform:
                continue

            query = template.format(name=display_name)
            ctx = None
            try:
                ctx = await self.get_context("google")
                page = await ctx.new_page()
                search_url = f"https://www.google.com/search?q={query}"
                await page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
                await page.wait_for_timeout(2000)

                results = await page.query_selector_all("div.g a[href]")
                for result in results[:3]:
                    href = await result.get_attribute("href")
                    if href and _extract_handle_from_url(href, platform):
                        handle = _extract_handle_from_url(href, platform)
                        discovered.append({
                            "platform": platform,
                            "handle": handle,
                            "url": href,
                            "confidence": 0.6,
                        })
                        break
            except Exception as e:
                logger.debug("Discovery search failed for %s on %s: %s", display_name, platform, e)
            finally:
                if ctx:
                    try:
                        await ctx.close()
                    except Exception:
                        pass

        return discovered

    # ── Auth management ──────────────────────────────────────────

    async def open_login_browser(self, platform: str) -> dict:
        """Open a visible (headful) browser at the platform's login page.

        The admin logs in manually in this browser. Call confirm_login()
        when done to validate and persist the session.
        """
        login_url = PLATFORM_LOGIN_URLS.get(platform)
        if not login_url:
            return {"status": "error", "message": f"Unknown platform: {platform}"}

        # Close any existing login browser for this platform
        if platform in self._login_contexts:
            try:
                await self._login_contexts[platform].close()
            except Exception:
                pass
            del self._login_contexts[platform]

        pw, _mgr = await self._new_playwright()
        profile_path = str(PROFILE_DIR / platform)
        os.makedirs(profile_path, exist_ok=True)

        # Launch VISIBLE browser so admin can interact
        ctx = await pw.chromium.launch_persistent_context(
            user_data_dir=profile_path,
            headless=False,
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )
        page = await ctx.new_page()
        await page.goto(login_url, wait_until="domcontentloaded", timeout=30000)

        self._login_contexts[platform] = ctx
        self._login_pw[platform] = pw

        return {
            "status": "login_browser_opened",
            "platform": platform,
            "login_url": login_url,
            "message": f"Browser opened at {login_url}. Complete login, then call POST /v1/admin/auth/confirm/{platform}",
        }

    async def confirm_login(self, platform: str) -> dict:
        """Verify the admin has logged in, then close the visible browser.

        Navigates to a test URL in the login browser to check if
        the session is authenticated.
        """
        ctx = self._login_contexts.get(platform)
        if not ctx:
            return {"status": "error", "message": f"No login browser open for {platform}. Call login first."}

        test = SESSION_TEST.get(platform)
        if not test:
            # No test URL — just trust that login happened and close
            try:
                await ctx.close()
            except Exception:
                pass
            del self._login_contexts[platform]
            return {"status": "confirmed", "platform": platform, "validated": False, "message": "Session saved (no validation available for this platform)."}

        # Navigate to test URL and check if authenticated
        try:
            # The login browser may have been closed by the user — try to get a page
            try:
                page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            except Exception:
                # Context died — open a fresh headless one to validate the saved profile
                try:
                    await ctx.close()
                except Exception:
                    pass
                del self._login_contexts[platform]
                # The profile is already saved on disk from the login session
                return await self.validate_session(platform)

            await page.goto(test["url"], wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(2000)

            final_url = page.url
            is_authenticated = test["login_indicator"] not in final_url

            await ctx.close()
            del self._login_contexts[platform]

            if is_authenticated:
                return {
                    "status": "authenticated",
                    "platform": platform,
                    "validated": True,
                    "message": f"Session verified and saved for {platform}.",
                }
            else:
                return {
                    "status": "login_required",
                    "platform": platform,
                    "validated": True,
                    "message": f"Login not detected — redirected to {final_url}. Try again.",
                }
        except Exception as e:
            # Close the browser regardless
            try:
                await ctx.close()
            except Exception:
                pass
            if platform in self._login_contexts:
                del self._login_contexts[platform]
            return {"status": "error", "message": f"Validation failed: {e}"}

    async def validate_session(self, platform: str) -> dict:
        """Check if a platform session is still valid without opening a visible browser."""
        from datetime import datetime, timezone as tz

        profile_path = PROFILE_DIR / platform
        if not profile_path.exists():
            return {"platform": platform, "status": "not_configured", "profile_exists": False, "valid": False}

        test = SESSION_TEST.get(platform)
        if not test:
            return {
                "platform": platform,
                "status": "unknown",
                "profile_exists": True,
                "valid": None,
                "message": "No validation test available for this platform.",
            }

        try:
            pw, _mgr = await self._new_playwright()
            ctx = await pw.chromium.launch_persistent_context(
                user_data_dir=str(profile_path),
                headless=True,
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            )
            page = await ctx.new_page()
            await page.goto(test["url"], wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(2000)

            final_url = page.url
            is_authenticated = test["login_indicator"] not in final_url

            await ctx.close()
            await pw.stop()

            status = "authenticated" if is_authenticated else "expired"
            return {
                "platform": platform,
                "status": status,
                "profile_exists": True,
                "valid": is_authenticated,
                "checked_at": datetime.now(tz.utc).isoformat(),
            }
        except Exception as e:
            return {
                "platform": platform,
                "status": "error",
                "profile_exists": True,
                "valid": None,
                "message": str(e),
            }

    async def clear_profile(self, platform: str) -> dict:
        """Delete the browser profile for a platform (logs out)."""
        import shutil

        # Close any active contexts
        for ctx_dict in (self._login_contexts,):
            if platform in ctx_dict:
                try:
                    await ctx_dict[platform].close()
                except Exception:
                    pass
                del ctx_dict[platform]

        profile_path = PROFILE_DIR / platform
        if profile_path.exists():
            shutil.rmtree(profile_path, ignore_errors=True)
            return {"status": "cleared", "platform": platform, "message": f"Browser profile deleted for {platform}."}
        return {"status": "not_found", "platform": platform, "message": f"No profile found for {platform}."}

    def get_all_status_sync(self) -> list[dict]:
        """Get status of all platform browser profiles (sync, no validation)."""
        from datetime import datetime, timezone as tz

        results = []
        for platform in PLATFORM_LOGIN_URLS:
            profile_path = PROFILE_DIR / platform
            exists = profile_path.exists()
            last_modified = None
            if exists:
                try:
                    mtime = profile_path.stat().st_mtime
                    last_modified = datetime.fromtimestamp(mtime, tz=tz.utc).isoformat()
                except Exception:
                    pass

            has_login_browser = platform in self._login_contexts
            results.append({
                "platform": platform,
                "profile_exists": exists,
                "last_modified": last_modified,
                "login_url": PLATFORM_LOGIN_URLS[platform],
                "has_active_login": has_login_browser,
                "status": "configured" if exists else "not_configured",
            })
        return results

    async def close(self):
        """Close all active login browser contexts."""
        for platform, ctx in self._login_contexts.items():
            try:
                await ctx.close()
            except Exception:
                pass
            pw = self._login_pw.get(platform)
            if pw:
                try:
                    await pw.stop()
                except Exception:
                    pass
        self._login_contexts.clear()
        self._login_pw.clear()


def _extract_handle_from_url(url: str, platform: str) -> str | None:
    """Extract handle from a platform URL."""
    import re
    patterns = {
        "twitter": r"(?:twitter|x)\.com/([A-Za-z0-9_]{1,30})(?:[/?#]|$)",
        "github": r"github\.com/([A-Za-z0-9_-]{1,39})(?:[/?#]|$)",
        "linkedin": r"linkedin\.com/in/([A-Za-z0-9_-]+?)(?:[/?#]|$)",
        "instagram": r"instagram\.com/([A-Za-z0-9_.]{1,30})(?:[/?#]|$)",
        "reddit": r"reddit\.com/user/([A-Za-z0-9_-]+?)(?:[/?#]|$)",
    }
    pattern = patterns.get(platform)
    if not pattern:
        return None
    match = re.search(pattern, url, re.IGNORECASE)
    return match.group(1) if match else None


# ---------------------------------------------------------------------------
# Playwright page scrapers (run inside browser context)
# ---------------------------------------------------------------------------


async def _scrape_linkedin(page, handle: str) -> dict:
    """Extract LinkedIn profile data from a loaded page (requires login)."""
    profile = {"vanityName": handle}

    profile["firstName"] = await _page_text(page, "h1.text-heading-xlarge, h1") or ""
    name_parts = profile["firstName"].split()
    if len(name_parts) > 1:
        profile["firstName"] = name_parts[0]
        profile["lastName"] = " ".join(name_parts[1:])

    profile["headline"] = await _page_text(page, ".text-body-medium.break-words") or ""
    profile["location"] = await _page_text(page, ".text-body-small.inline.t-black--light.break-words") or ""
    profile["summary"] = await _page_text(page, "#about ~ div .inline-show-more-text") or ""

    conn_el = await page.query_selector("li.text-body-small span.t-bold")
    if conn_el:
        conn_text = await conn_el.text_content()
        profile["connectionCount"] = _parse_count(conn_text or "0")

    # Endorsement count
    endorsement_el = await page.query_selector("[data-field='skill_card_skill_topic'] .pv-skill-endorsement-count")
    if endorsement_el:
        profile["endorsementCount"] = _parse_count(await endorsement_el.text_content() or "0")

    # Experience
    profile["experience"] = []
    exp_items = await page.query_selector_all("#experience ~ .pvs-list__outer-container li.artdeco-list__item")
    for item in exp_items[:5]:
        company_el = await item.query_selector(".t-14.t-normal span")
        company = (await company_el.text_content()).strip() if company_el else ""
        if company:
            profile["experience"].append({"companyName": company})

    # Navigate to activity section for posts
    posts = []
    try:
        activity_url = f"https://www.linkedin.com/in/{handle}/recent-activity/all/"
        await page.goto(activity_url, wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(2000)

        post_els = await page.query_selector_all(".feed-shared-update-v2 .feed-shared-text, .feed-shared-inline-show-more-text")
        for el in post_els[:10]:
            text = (await el.text_content() or "").strip()
            if text:
                posts.append({"text": text[:1000]})
    except Exception:
        pass  # Activity page may not be accessible

    return {"profile": profile, "posts": posts}


async def _scrape_twitter(page, handle: str) -> dict:
    """Extract Twitter/X profile data from a loaded page (requires login for full data)."""
    profile = {"username": handle}

    profile["name"] = await _page_text(page, '[data-testid="UserName"] > div > div > span') or ""
    profile["description"] = await _page_text(page, '[data-testid="UserDescription"]') or ""
    profile["location"] = await _page_text(page, '[data-testid="UserLocation"]') or ""
    profile["verified"] = bool(await page.query_selector('[data-testid="icon-verified"]'))

    # Follower/following
    follow_links = await page.query_selector_all('a[href$="/followers"], a[href$="/following"], a[href$="/verified_followers"]')
    for link in follow_links:
        href = await link.get_attribute("href") or ""
        text = await link.text_content() or ""
        count = _parse_count(text)
        if "/following" in href:
            profile["following_count"] = count
        elif "/followers" in href or "/verified_followers" in href:
            profile["followers_count"] = profile.get("followers_count", 0) + count

    # Join date
    join_el = await page.query_selector('[data-testid="UserJoinDate"]')
    if join_el:
        profile["created_at_text"] = (await join_el.text_content() or "").strip()

    # Recent tweets with engagement metrics
    tweets = []
    tweet_els = await page.query_selector_all('[data-testid="tweet"]')
    for el in tweet_els[:20]:
        text_el = await el.query_selector('[data-testid="tweetText"]')
        time_el = await el.query_selector("time")
        if text_el:
            text = await text_el.text_content() or ""
            created = ""
            if time_el:
                created = await time_el.get_attribute("datetime") or ""

            # Engagement counts
            like_el = await el.query_selector('[data-testid="like"] span, [data-testid="unlike"] span')
            rt_el = await el.query_selector('[data-testid="retweet"] span, [data-testid="unretweet"] span')
            reply_el = await el.query_selector('[data-testid="reply"] span')
            reply_to = await el.query_selector('[data-testid="Tweet-User-Avatar"]')

            tweets.append({
                "text": text[:500],
                "created_at": created,
                "like_count": _parse_count(await like_el.text_content() if like_el else "0"),
                "retweet_count": _parse_count(await rt_el.text_content() if rt_el else "0"),
                "reply_count": _parse_count(await reply_el.text_content() if reply_el else "0"),
            })

    return {"profile": profile, "tweets": tweets}


async def _scrape_github(page, handle: str) -> dict:
    """Extract GitHub profile data from a loaded page."""
    profile = {"login": handle}

    profile["name"] = await _page_text(page, ".vcard-fullname, .p-name") or ""
    profile["bio"] = await _page_text(page, ".user-profile-bio, .p-note") or ""
    profile["company"] = await _page_text(page, ".vcard-details [itemprop='worksFor']") or ""
    profile["location"] = await _page_text(page, ".vcard-details [itemprop='homeLocation']") or ""

    repos = []
    repo_els = await page.query_selector_all(".pinned-item-list-item-content")
    for el in repo_els:
        name_el = await el.query_selector(".repo, a span")
        desc_el = await el.query_selector(".pinned-item-desc, p")
        lang_el = await el.query_selector("[itemprop='programmingLanguage']")
        repos.append({
            "name": await name_el.text_content() if name_el else "",
            "description": (await desc_el.text_content() if desc_el else "").strip(),
            "language": (await lang_el.text_content() if lang_el else "").strip(),
            "stargazers_count": 0,
            "forks_count": 0,
            "topics": [],
        })

    return {"profile": profile, "repos": repos, "events": []}


async def _scrape_hackernews(page, handle: str) -> dict:
    """Extract HN user data from a loaded page."""
    profile = {"id": handle}

    rows = await page.query_selector_all("table tr")
    for row in rows:
        cells = await row.query_selector_all("td")
        if len(cells) >= 2:
            label = (await cells[0].text_content() or "").strip().rstrip(":")
            value = (await cells[1].text_content() or "").strip()
            if label == "karma":
                profile["karma"] = int(value) if value.isdigit() else 0
            elif label == "about":
                profile["about"] = value
            elif label == "created":
                try:
                    from datetime import datetime
                    profile["created"] = datetime.strptime(value, "%Y-%m-%d").timestamp()
                except Exception:
                    pass

    return {"profile": profile, "items": []}


async def _scrape_instagram(page, handle: str) -> dict:
    """Extract Instagram profile data from a loaded page (requires login for posts)."""
    profile = {"username": handle}
    profile["full_name"] = await _page_text(page, "header section h1, header section h2") or ""
    profile["is_verified"] = bool(await page.query_selector('[aria-label="Verified"]'))

    # Bio
    bio_el = await page.query_selector("header section [class*='_ap3a'], header section span[class*='_aacl']")
    if bio_el:
        profile["biography"] = (await bio_el.text_content() or "").strip()

    # Stats: posts, followers, following
    stat_els = await page.query_selector_all("header section ul li, header section [class*='_ac2a']")
    for el in stat_els:
        text = (await el.text_content() or "").strip().lower()
        span = await el.query_selector("span span, span")
        count = _parse_count(await span.text_content() if span else "0")
        if "post" in text:
            profile["media_count"] = count
        elif "follower" in text:
            profile["follower_count"] = count
        elif "following" in text:
            profile["following_count"] = count

    # Recent post captions (requires being logged in)
    posts = []
    post_links = await page.query_selector_all("article a[href*='/p/']")
    for link in post_links[:6]:
        try:
            href = await link.get_attribute("href")
            if not href:
                continue
            post_page = await page.context.new_page()
            await post_page.goto(f"https://www.instagram.com{href}", wait_until="domcontentloaded", timeout=10000)
            await post_page.wait_for_timeout(1500)
            caption_el = await post_page.query_selector("h1, [class*='_a9zs'] span")
            if caption_el:
                caption = (await caption_el.text_content() or "").strip()
                if caption:
                    posts.append({"caption": caption[:500]})
            await post_page.close()
        except Exception:
            pass

    return {"profile": profile, "posts": posts}


async def _scrape_reddit(page, handle: str) -> dict:
    """Extract Reddit profile data from a loaded page."""
    profile = {"name": handle}
    return {"profile": profile, "comments": [], "posts": []}


async def _scrape_bluesky(page, handle: str) -> dict:
    """Extract Bluesky profile data from a loaded page."""
    profile = {"handle": handle}
    profile["displayName"] = await _page_text(page, "[data-testid='profileHeaderDisplayName'], h1") or ""
    profile["description"] = await _page_text(page, "[data-testid='profileHeaderDescription']") or ""
    return {"profile": profile, "posts": []}


async def _scrape_youtube(page, handle: str) -> dict:
    """Extract YouTube channel data from a loaded page."""
    channel = {"custom_url": handle}
    channel["title"] = await _page_text(page, "#channel-name yt-formatted-string") or ""
    sub_el = await page.query_selector("#subscriber-count")
    if sub_el:
        channel["subscriber_count"] = _parse_count(await sub_el.text_content() or "0")
    return {"channel": channel, "videos": []}


# Helpers

async def _page_text(page, selector: str) -> str | None:
    el = await page.query_selector(selector)
    if el:
        return (await el.text_content() or "").strip()
    return None


def _parse_count(text: str) -> int:
    import re
    clean = text.replace(",", "").strip()
    m = re.search(r"([\d.]+)\s*([KkMmBb])?", clean)
    if not m:
        return 0
    n = float(m.group(1))
    suffix = (m.group(2) or "").upper()
    if suffix == "K":
        n *= 1000
    elif suffix == "M":
        n *= 1_000_000
    elif suffix == "B":
        n *= 1_000_000_000
    return round(n)


PLAYWRIGHT_SCRAPERS = {
    "linkedin": _scrape_linkedin,
    "twitter": _scrape_twitter,
    "github": _scrape_github,
    "hackernews": _scrape_hackernews,
    "instagram": _scrape_instagram,
    "reddit": _scrape_reddit,
    "bluesky": _scrape_bluesky,
    "youtube": _scrape_youtube,
}


# Singleton
_pool: ScraperPool | None = None


def get_scraper_pool() -> ScraperPool:
    global _pool
    if _pool is None:
        _pool = ScraperPool()
    return _pool
