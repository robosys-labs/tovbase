"""Public API enrichment — discover cross-platform profiles without auth.

Queries free public APIs to find profiles for a given handle/name across
platforms. Returns raw_data dicts that feed directly into the existing
adapter pipeline via normalize_observation().

No API keys required for GitHub and HN. YouTube requires an optional key.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger("tovbase.enrichment")

_CLIENT: httpx.Client | None = None


def _http() -> httpx.Client:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = httpx.Client(
            timeout=10.0,
            headers={"User-Agent": "Tovbase/1.0 (Identity Enrichment)"},
            follow_redirects=True,
        )
    return _CLIENT


# ---------------------------------------------------------------------------
# GitHub (public, no auth, 60 req/hour)
# ---------------------------------------------------------------------------


def search_github_by_name(display_name: str, location: str | None = None) -> dict[str, Any] | None:
    """Search GitHub for a user by display name (not handle).

    Uses GitHub's search API with plain text query (the fullname: qualifier
    doesn't work reliably). Also tries reversed name order since some cultures
    use family-name-first.
    """
    client = _http()
    name_variants = [display_name]
    parts = display_name.split()
    if len(parts) >= 2:
        name_variants.append(f"{parts[-1]} {' '.join(parts[:-1])}")  # reversed

    for name in name_variants:
        try:
            query = name
            if location:
                query += f" location:{location}"
            resp = client.get(
                "https://api.github.com/search/users",
                params={"q": query, "per_page": 3},
            )
            if resp.status_code != 200:
                continue
            items = resp.json().get("items", [])
            if items:
                return fetch_github_profile(items[0]["login"])
        except httpx.HTTPError:
            continue
    return None


def fetch_github_profile(handle: str) -> dict[str, Any] | None:
    """Fetch GitHub profile + repos via public API."""
    client = _http()
    try:
        resp = client.get(f"https://api.github.com/users/{handle}")
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            logger.debug("GitHub API %d for %s", resp.status_code, handle)
            return None

        profile_data = resp.json()

        # Fetch top repos (sorted by stars)
        repos_resp = client.get(
            f"https://api.github.com/users/{handle}/repos",
            params={"sort": "stars", "per_page": 30, "type": "owner"},
        )
        repos = repos_resp.json() if repos_resp.status_code == 200 else []

        # Fetch recent events for activity timing
        events_resp = client.get(
            f"https://api.github.com/users/{handle}/events/public",
            params={"per_page": 30},
        )
        events = events_resp.json() if events_resp.status_code == 200 else []

        # Format for GitHubAdapter
        return {
            "profile": {
                "login": profile_data.get("login", handle),
                "name": profile_data.get("name"),
                "created_at": profile_data.get("created_at"),
                "followers": profile_data.get("followers", 0),
                "following": profile_data.get("following", 0),
                "bio": profile_data.get("bio"),
                "company": profile_data.get("company"),
                "location": profile_data.get("location"),
                "blog": profile_data.get("blog"),
                "email": profile_data.get("email"),
                "public_repos": profile_data.get("public_repos", 0),
                "avatar_url": profile_data.get("avatar_url"),
            },
            "repos": [
                {
                    "name": r.get("name"),
                    "language": r.get("language"),
                    "stargazers_count": r.get("stargazers_count", 0),
                    "forks_count": r.get("forks_count", 0),
                    "topics": r.get("topics", []),
                    "description": r.get("description"),
                }
                for r in repos
                if isinstance(r, dict)
            ],
            "events": [
                {
                    "created_at": e.get("created_at"),
                    "type": e.get("type"),
                }
                for e in events
                if isinstance(e, dict)
            ],
        }
    except httpx.HTTPError as e:
        logger.debug("GitHub API error for %s: %s", handle, e)
        return None


# ---------------------------------------------------------------------------
# Hacker News (public, no auth, no rate limit)
# ---------------------------------------------------------------------------


def fetch_hn_profile(handle: str) -> dict[str, Any] | None:
    """Fetch HN user profile + recent items via Firebase API."""
    client = _http()
    try:
        resp = client.get(f"https://hacker-news.firebaseio.com/v0/user/{handle}.json")
        if resp.status_code != 200:
            return None

        data = resp.json()
        if not data:
            return None

        # Fetch recent items for activity analysis
        submitted = data.get("submitted", [])[:30]
        items = []
        for item_id in submitted[:15]:  # limit to avoid too many requests
            item_resp = client.get(f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json")
            if item_resp.status_code == 200:
                item = item_resp.json()
                if item:
                    items.append({
                        "id": item.get("id"),
                        "type": item.get("type"),
                        "time": item.get("time"),
                        "text": item.get("text", ""),
                        "title": item.get("title", ""),
                    })

        return {
            "profile": {
                "id": data.get("id", handle),
                "karma": data.get("karma", 0),
                "about": data.get("about", ""),
                "created": data.get("created", 0),
            },
            "items": items,
        }
    except httpx.HTTPError as e:
        logger.debug("HN API error for %s: %s", handle, e)
        return None


# ---------------------------------------------------------------------------
# Reddit (public JSON endpoint, no auth for basic profile)
# ---------------------------------------------------------------------------


def fetch_reddit_profile(handle: str) -> dict[str, Any] | None:
    """Fetch Reddit user profile via public JSON endpoint."""
    client = _http()
    try:
        resp = client.get(
            f"https://www.reddit.com/user/{handle}/about.json",
            headers={"User-Agent": "Tovbase/1.0 (Identity Enrichment)"},
        )
        if resp.status_code != 200:
            return None

        data = resp.json().get("data", {})
        if not data or not data.get("name"):
            return None

        # Fetch recent comments
        comments_resp = client.get(
            f"https://www.reddit.com/user/{handle}/comments.json?limit=20",
            headers={"User-Agent": "Tovbase/1.0 (Identity Enrichment)"},
        )
        comments = []
        if comments_resp.status_code == 200:
            for child in comments_resp.json().get("data", {}).get("children", []):
                c = child.get("data", {})
                comments.append({
                    "body": c.get("body", ""),
                    "created_utc": c.get("created_utc", 0),
                    "subreddit": c.get("subreddit", ""),
                })

        return {
            "profile": {
                "name": data.get("name", handle),
                "link_karma": data.get("link_karma", 0),
                "comment_karma": data.get("comment_karma", 0),
                "created_utc": data.get("created_utc", 0),
            },
            "comments": comments,
            "posts": [],
        }
    except httpx.HTTPError as e:
        logger.debug("Reddit API error for %s: %s", handle, e)
        return None


# ---------------------------------------------------------------------------
# StackExchange (all sites — SO, ServerFault, SuperUser, AskUbuntu, etc.)
# ---------------------------------------------------------------------------

# Supported StackExchange sites for enrichment
STACKEXCHANGE_SITES = [
    "stackoverflow",
    "serverfault",
    "superuser",
    "askubuntu",
    "math",
    "stats",
    "electronics",
    "security",
    "dba",
    "unix",
    "cs",
    "datascience",
]


def fetch_stackexchange_profile(handle: str, site: str = "stackoverflow") -> dict[str, Any] | None:
    """Fetch a StackExchange user profile from any SE site.

    The StackExchange API (api.stackexchange.com) is unified across all sites.
    Pass `site` to query a specific community (e.g., "serverfault", "askubuntu").
    Public, no auth needed (300 req/day without key).
    """
    client = _http()
    try:
        if handle.isdigit():
            resp = client.get(
                f"https://api.stackexchange.com/2.3/users/{handle}",
                params={"site": site, "filter": "!9_bDE(fI5"},
            )
        else:
            resp = client.get(
                "https://api.stackexchange.com/2.3/users",
                params={
                    "site": site,
                    "inname": handle,
                    "sort": "reputation",
                    "order": "desc",
                    "pagesize": 3,
                    "filter": "!9_bDE(fI5",
                },
            )

        if resp.status_code != 200:
            logger.debug("SE API %d for %s on %s", resp.status_code, handle, site)
            return None

        data = resp.json()
        users = data.get("items", [])
        if not users:
            return None

        user = users[0]
        user_id = user.get("user_id")
        answers = []
        tags = []

        if user_id:
            ans_resp = client.get(
                f"https://api.stackexchange.com/2.3/users/{user_id}/answers",
                params={
                    "site": site,
                    "sort": "votes",
                    "order": "desc",
                    "pagesize": 20,
                    "filter": "withbody",
                },
            )
            if ans_resp.status_code == 200:
                for a in ans_resp.json().get("items", []):
                    answers.append({
                        "body": _strip_html(a.get("body", "")),
                        "creation_date": a.get("creation_date", 0),
                        "score": a.get("score", 0),
                        "is_accepted": a.get("is_accepted", False),
                    })

            tags_resp = client.get(
                f"https://api.stackexchange.com/2.3/users/{user_id}/top-tags",
                params={"site": site, "pagesize": 20},
            )
            if tags_resp.status_code == 200:
                tags = [
                    {"name": t.get("tag_name", ""), "count": t.get("answer_count", 0)}
                    for t in tags_resp.json().get("items", [])
                ]

        return {
            "profile": {
                "user_id": user.get("user_id"),
                "display_name": user.get("display_name"),
                "reputation": user.get("reputation", 0),
                "creation_date": user.get("creation_date", 0),
                "location": user.get("location"),
                "website_url": user.get("website_url"),
                "profile_image": user.get("profile_image"),
                "badge_counts": user.get("badge_counts", {}),
                "answer_count": user.get("answer_count", 0),
                "question_count": user.get("question_count", 0),
                "about_me": _strip_html(user.get("about_me", "")),
                "site": site,
            },
            "answers": answers,
            "tags": tags,
        }
    except httpx.HTTPError as e:
        logger.debug("SE API error for %s on %s: %s", handle, site, e)
        return None


def fetch_stackexchange_all_sites(handle: str) -> list[dict[str, Any]]:
    """Search for a user across all major StackExchange sites.

    Returns a list of {platform, handle, raw_data} for each site where the user is found.
    Uses the StackExchange /users/associated endpoint when possible.
    """
    results = []

    # Strategy 1: If we have a numeric ID from SO, use /associated to find all accounts
    if handle.isdigit():
        client = _http()
        try:
            resp = client.get(
                f"https://api.stackexchange.com/2.3/users/{handle}/associated",
                params={"pagesize": 30},
            )
            if resp.status_code == 200:
                for acct in resp.json().get("items", []):
                    site_url = acct.get("site_url", "")
                    site_name = site_url.replace("https://", "").split(".")[0] if site_url else ""
                    if site_name and site_name in STACKEXCHANGE_SITES:
                        acct_id = acct.get("user_id")
                        if acct_id:
                            raw = fetch_stackexchange_profile(str(acct_id), site=site_name)
                            if raw:
                                results.append({
                                    "platform": "stackexchange",
                                    "handle": str(acct_id),
                                    "site": site_name,
                                    "raw_data": raw,
                                })
                return results
        except Exception:
            pass

    # Strategy 2: Try the handle on the top SE sites
    for site in ["stackoverflow", "serverfault", "superuser", "askubuntu"]:
        raw = fetch_stackexchange_profile(handle, site=site)
        if raw:
            user_id = raw["profile"].get("user_id", handle)
            results.append({
                "platform": "stackexchange",
                "handle": str(user_id),
                "site": site,
                "raw_data": raw,
            })

    return results


def _strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    import re
    return re.sub(r"<[^>]+>", "", text).strip()


# ---------------------------------------------------------------------------
# Handle URL probing — check if a handle exists on platforms without auth
# ---------------------------------------------------------------------------

PROBE_URLS = {
    "twitter":   "https://publish.twitter.com/oembed?url=https://twitter.com/{handle}",
    "youtube":   "https://www.youtube.com/@{handle}",
    "instagram": "https://www.instagram.com/{handle}/",
}


def probe_handle_exists(platform: str, handle: str) -> bool:
    """Check if a profile handle exists on a platform via HTTP probe.

    Uses lightweight HTTP requests (no auth, no browser). Returns True if
    the profile likely exists, False if confirmed non-existent.
    """
    url_template = PROBE_URLS.get(platform)
    if not url_template:
        return False

    client = _http()
    try:
        url = url_template.format(handle=handle)

        if platform == "twitter":
            # Twitter oembed: 200 = exists, 404 = doesn't
            resp = client.get(url)
            return resp.status_code == 200

        elif platform == "youtube":
            # YouTube: 200 = channel exists, 404 = doesn't
            resp = client.head(url, follow_redirects=True)
            return resp.status_code == 200

        elif platform == "instagram":
            # Instagram: check if redirected to login vs profile content
            resp = client.get(url, follow_redirects=False)
            # 301/302 to the profile = exists; 302 to /accounts/login = doesn't
            if resp.status_code in (200, 301):
                return True
            location = resp.headers.get("location", "")
            return "/accounts/login" not in location

        return False
    except httpx.HTTPError:
        return False


def probe_all_platforms(handle: str, exclude_platform: str | None = None,
                        already_found: set[str] | None = None) -> list[dict]:
    """Probe the handle on all supported platforms and return those where it exists."""
    already_found = already_found or set()
    found = []

    for platform, _ in PROBE_URLS.items():
        if platform == exclude_platform:
            continue
        if platform in already_found:
            continue

        if probe_handle_exists(platform, handle):
            found.append({
                "platform": platform,
                "handle": handle,
                "url": f"https://x.com/{handle}" if platform == "twitter"
                       else f"https://www.youtube.com/@{handle}" if platform == "youtube"
                       else f"https://www.instagram.com/{handle}/",
            })
            logger.info("Probe confirmed: %s/%s exists", platform, handle)

    return found


# ---------------------------------------------------------------------------
# Public data fetching for platforms without traditional APIs
# ---------------------------------------------------------------------------


def fetch_bluesky_public(handle: str) -> dict[str, Any] | None:
    """Fetch Bluesky profile via the public AT Protocol API (no auth needed)."""
    client = _http()
    # Try with .bsky.social suffix if not already present
    actor = handle if "." in handle else f"{handle}.bsky.social"

    try:
        resp = client.get(
            "https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile",
            params={"actor": actor},
        )
        if resp.status_code != 200:
            return None

        data = resp.json()
        if not data.get("handle"):
            return None

        return {
            "profile": {
                "handle": data.get("handle", handle),
                "displayName": data.get("displayName"),
                "description": data.get("description"),
                "followersCount": data.get("followersCount", 0),
                "followsCount": data.get("followsCount", 0),
                "postsCount": data.get("postsCount", 0),
                "createdAt": data.get("createdAt"),
                "avatar": data.get("avatar"),
            },
            "posts": [],
        }
    except httpx.HTTPError as e:
        logger.debug("Bluesky API error for %s: %s", handle, e)
        return None


def fetch_twitter_probe_data(handle: str) -> dict[str, Any] | None:
    """Create a minimal Twitter profile from a confirmed-existing handle.

    Twitter has no public API for profile data, but the oembed endpoint
    confirms existence. We create a stub profile that identity resolution
    can link. The Playwright pool fills in full data later.
    """
    # We already know the handle exists (probe_handle_exists confirmed it)
    return {
        "profile": {
            "username": handle,
            "name": None,   # Unknown without auth — Playwright fills this in later
            "description": None,
            "followers_count": 0,  # Will be updated by Playwright scrape
            "following_count": 0,
        },
        "tweets": [],
    }


# ---------------------------------------------------------------------------
# Cross-platform discovery
# ---------------------------------------------------------------------------

# Map of platform → enrichment function (public API-based)
ENRICHMENT_FUNCTIONS: dict[str, Any] = {
    "github": fetch_github_profile,
    "hackernews": fetch_hn_profile,
    "reddit": fetch_reddit_profile,
    "stackoverflow": lambda h: fetch_stackexchange_profile(h, "stackoverflow"),
    "bluesky": fetch_bluesky_public,
}


def discover_and_fetch(
    handle: str,
    display_name: str | None = None,
    exclude_platform: str | None = None,
) -> list[dict[str, Any]]:
    """Try to find this person's profiles on other platforms.

    Strategy:
    1. Try the exact handle on every platform with a public API
    2. If handle search fails and display_name is available, search by name
    3. Search StackExchange by display name (SO uses display names, not handles)

    Returns list of {platform, handle, raw_data} dicts ready for ingestion.
    """
    results = []
    found_platforms: set[str] = set()

    # Handle variations to try (exact handle + common transformations)
    handle_variants = _generate_handle_variants(handle, display_name)

    # ── Phase 1: Search by handle on each platform ────────────
    for platform, fetch_fn in ENRICHMENT_FUNCTIONS.items():
        if platform == exclude_platform:
            continue

        # Only try exact handle + very close variants (not full name-based variants)
        # Name-based variants cause false positives (e.g., "thomasd" matching wrong person on HN)
        variants_to_try = [handle]  # exact handle only for initial search

        for variant in variants_to_try:
            raw = fetch_fn(variant)
            if raw and _is_substantive_profile(platform, raw):
                # Verify the discovered profile name matches the source
                disc_name = raw.get("profile", {}).get("display_name") or raw.get("profile", {}).get("name")
                if _names_compatible(display_name, disc_name):
                    results.append({
                        "platform": platform,
                        "handle": variant,
                        "raw_data": raw,
                    })
                    found_platforms.add(platform)
                    break
                else:
                    logger.debug("Rejected %s/%s: name '%s' doesn't match '%s'", platform, variant, disc_name, display_name)

    # ── Phase 2: Name-based search for platforms not found ────
    if display_name:
        # GitHub: search by full name if handle search missed or found empty profile
        if "github" not in found_platforms and exclude_platform != "github":
            gh = search_github_by_name(display_name)
            if gh and _is_substantive_profile("github", gh):
                gh_name = gh["profile"].get("name")
                if _names_compatible(display_name, gh_name):
                    gh_handle = gh["profile"].get("login", "")
                    results.append({
                        "platform": "github",
                        "handle": gh_handle,
                        "raw_data": gh,
                    })
                    found_platforms.add("github")
                else:
                    logger.debug("Rejected GitHub name search: '%s' doesn't match '%s'", gh_name, display_name)

        # StackExchange: search by display name + reversed name
        if "stackoverflow" not in found_platforms and exclude_platform not in ("stackoverflow", "stackexchange"):
            so = fetch_stackexchange_profile(display_name, "stackoverflow")
            # Also try reversed name order
            if not so:
                parts = display_name.split()
                if len(parts) >= 2:
                    reversed_name = f"{parts[-1]} {' '.join(parts[:-1])}"
                    so = fetch_stackexchange_profile(reversed_name, "stackoverflow")
            if so:
                so_id = str(so["profile"].get("user_id", ""))
                results.append({
                    "platform": "stackexchange",
                    "handle": so_id,
                    "raw_data": so,
                })
                found_platforms.add("stackoverflow")

    # ── Phase 3: SE cross-site discovery ──────────────────────
    if exclude_platform not in ("stackoverflow", "stackexchange"):
        so_ids = [r["handle"] for r in results if r["platform"] == "stackexchange" and r["handle"].isdigit()]
        if so_ids:
            se_results = fetch_stackexchange_all_sites(so_ids[0])
            for se in se_results:
                if se.get("site") != "stackoverflow":
                    results.append({
                        "platform": "stackexchange",
                        "handle": se["handle"],
                        "raw_data": se["raw_data"],
                    })

    # ── Phase 4: Handle URL probing (Twitter, YouTube, Instagram) ──
    already_found = {r["platform"] for r in results} | {exclude_platform or ""}
    probed = probe_all_platforms(handle, exclude_platform, already_found)
    for entry in probed:
        plat = entry["platform"]
        raw = None
        if plat == "twitter":
            raw = fetch_twitter_probe_data(entry["handle"])
        # YouTube and Instagram: probe confirms existence but no public data
        # Mark for browser scraping later
        if raw:
            results.append({"platform": plat, "handle": entry["handle"], "raw_data": raw})
        else:
            results.append({"platform": plat, "handle": entry["handle"], "raw_data": None, "probe_only": True})

    return results


def _names_compatible(source_name: str | None, discovered_name: str | None) -> bool:
    """Check if two display names could plausibly be the same person.

    Used to filter false positives: if we discover a GitHub profile by searching
    for "Thomas Dubendorfer" but it returns someone named "Thomas Davis", reject it.
    """
    if not source_name or not discovered_name:
        return True  # Can't verify — give benefit of the doubt

    import unicodedata

    def _normalize(n: str) -> set[str]:
        n = unicodedata.normalize("NFKD", n)
        n = "".join(c for c in n if not unicodedata.combining(c))
        return set(n.lower().replace("'", "").replace("-", " ").replace(".", " ").split())

    src = _normalize(source_name)
    disc = _normalize(discovered_name)
    if not src or not disc:
        return True

    overlap = src & disc
    # Need at least 1 meaningful token in common (last name match is strong signal)
    # Single-token names: exact match required
    if len(src) == 1 or len(disc) == 1:
        return bool(overlap)
    return len(overlap) >= 1


def _is_substantive_profile(platform: str, raw: dict) -> bool:
    """Check if a fetched profile has enough data to be worth ingesting.

    Filters out empty/placeholder accounts that match by handle but
    aren't the real person (e.g., a GitHub account with 0 repos and 0 followers).
    """
    profile = raw.get("profile", raw.get("channel", {}))
    if platform == "github":
        repos = len(raw.get("repos", []))
        followers = profile.get("followers", 0)
        public_repos = profile.get("public_repos", 0)
        # Needs at least some activity
        return public_repos >= 3 or followers >= 5 or repos >= 1
    if platform == "hackernews":
        return profile.get("karma", 0) >= 10
    if platform == "reddit":
        karma = profile.get("link_karma", 0) + profile.get("comment_karma", 0)
        return karma >= 10
    if platform == "stackoverflow":
        return profile.get("reputation", 0) >= 50
    if platform == "twitter":
        # Probe-confirmed profiles are always substantive
        return True
    if platform == "youtube":
        channel = raw.get("channel", {})
        return channel.get("subscriber_count", 0) >= 5 or bool(channel.get("title"))
    if platform == "bluesky":
        return bool(profile.get("displayName") or profile.get("description"))
    if platform == "instagram":
        return True  # Probe-confirmed = exists
    # Default: accept any non-empty profile
    return bool(profile)


def _generate_handle_variants(handle: str, display_name: str | None = None) -> list[str]:
    """Generate handle variations to search across platforms.

    e.g., "opatachibueze" might also be "opata-chibueze", "opata_chibueze",
    "opatachibueze-dev", etc.
    """
    variants = [handle]

    # Common suffixes/prefixes used across platforms
    if not any(c in handle for c in ["-", "_", "."]):
        # Handle is a single slug — try splitting at common points
        # but keep the original as primary
        pass

    # Name-based variants
    if display_name:
        name_parts = display_name.lower().split()
        if len(name_parts) >= 2:
            first, last = name_parts[0], name_parts[-1]
            name_variants = [
                f"{first}{last}",           # opatachibueze
                f"{first}-{last}",          # opata-chibueze
                f"{first}_{last}",          # opata_chibueze
                f"{first}.{last}",          # opata.chibueze
                f"{first[0]}{last}",        # ochibueze
                f"{first}{last[0]}",        # opatac
                f"{last}{first}",           # chibuezeopata
            ]
            for v in name_variants:
                if v.lower() not in [x.lower() for x in variants]:
                    variants.append(v)

    return variants[:8]  # Cap at 8 variants to avoid excessive API calls
