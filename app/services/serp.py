"""SERP enrichment — extract structured signals from public web search results.

Closes the open-data gap when paid platforms (LinkedIn, X, Instagram) block
direct API access. Their public profile *snippets* are still indexed by every
search engine, and those snippets carry follower counts, role/org strings, and
URLs that reveal real handles.

Three signal types flow out of this module:

  1. discovered_handles  — platform → handle, extracted from URL paths.
     Replaces the brittle "guess handle from display name" heuristic.

  2. audience_signals    — platform → follower count, parsed from snippet
     text via regex ("21.4K+ followers", "1.2M subscribers").

  3. institutional_anchors — set of authoritative domains naming the person
     (Wikipedia, Crunchbase, .edu, .gov). Each anchor counts toward the
     external-credential bonus in `compute_trust_score`.

Plus a derived `reference_density` — count of distinct domains referencing
the person — that acts as a multiplicative score boost similar to PPR.

Backends are pluggable; production should use a paid API (Brave Search,
Google Custom Search, Bing) for reliability. The default `DuckDuckGoBackend`
scrapes HTML for the OSS-launch zero-config experience.
"""

from __future__ import annotations

import logging
import math
import os
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Protocol
from urllib.parse import parse_qs, unquote, urlparse

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result + fingerprint dataclasses
# ---------------------------------------------------------------------------


@dataclass
class SerpResult:
    title: str
    url: str
    snippet: str

    @property
    def domain(self) -> str:
        try:
            host = urlparse(self.url).netloc.lower()
            return host.removeprefix("www.")
        except Exception:
            return ""


@dataclass
class SerpFingerprint:
    """Aggregate of SERP signals for one person."""

    query: str
    n_results: int = 0
    # platform -> handle, e.g. {"linkedin": "opeyemiawoyemi", "x": "opeawo"}
    discovered_handles: dict[str, str] = field(default_factory=dict)
    # platform -> follower count parsed from snippets
    audience_signals: dict[str, int] = field(default_factory=dict)
    # set of distinct authoritative domains referencing the name
    institutional_anchors: set[str] = field(default_factory=set)
    # set of education anchors named in snippets (Wharton, Harvard, ...)
    education_anchors: set[str] = field(default_factory=set)
    # all distinct domains referencing (used for reference_density boost)
    reference_domains: set[str] = field(default_factory=set)
    # claimed roles found in snippets: "Founder of X", "Partner @ Y"
    claimed_roles: list[str] = field(default_factory=list)
    # red-flag terms found in snippets (fraud, deplatform, court, etc.)
    red_flags: list[str] = field(default_factory=list)
    # Maximum "N+ years of experience" found in any snippet (0 if none).
    declared_years_of_experience: int = 0
    # Earliest founding-year mentioned (e.g. 2004 from "founded in 2004")
    earliest_founding_year: int | None = None
    raw_results: list[SerpResult] = field(default_factory=list)

    @property
    def reference_density(self) -> float:
        """Log-scaled in [0, 1]. Saturates at ~30 distinct referencing domains."""
        n = len(self.reference_domains)
        if n <= 1:
            return 0.0
        return min(1.0, math.log1p(n) / math.log1p(30))

    @property
    def institutional_credential_count(self) -> int:
        """Number of distinct authoritative domains found — feeds the
        external-credential bonus curve. Each Wikipedia / Crunchbase / .edu /
        .gov hit acts like a self-claim credential. Education anchors
        (Wharton, Harvard, ...) count too."""
        return len(self.institutional_anchors) + len(self.education_anchors)


# ---------------------------------------------------------------------------
# Backend protocol + implementations
# ---------------------------------------------------------------------------


class SerpSearchBackend(Protocol):
    name: str

    def search(self, query: str, n: int = 10) -> list[SerpResult]: ...


class _BraveSearchBackend:
    """Brave Search API — recommended production backend. Free tier 2K/mo,
    paid plans from $3/CPM. Requires BRAVE_SEARCH_API_KEY env var."""

    name = "brave"
    endpoint = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, query: str, n: int = 10) -> list[SerpResult]:
        try:
            resp = httpx.get(
                self.endpoint,
                params={"q": query, "count": n},
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": self.api_key,
                },
                timeout=10.0,
            )
        except httpx.HTTPError as exc:
            logger.warning("serp.brave.http_error", extra={"error": str(exc)})
            return []
        if resp.status_code != 200:
            logger.warning("serp.brave.bad_status", extra={"status": resp.status_code})
            return []
        web = (resp.json().get("web") or {}).get("results") or []
        return [
            SerpResult(title=r.get("title", ""), url=r.get("url", ""), snippet=r.get("description", ""))
            for r in web
        ]


class _GoogleCustomSearchBackend:
    """Google Programmable Search Engine JSON API. Free tier 100/day."""

    name = "google_cse"
    endpoint = "https://www.googleapis.com/customsearch/v1"

    def __init__(self, api_key: str, cx: str):
        self.api_key = api_key
        self.cx = cx

    def search(self, query: str, n: int = 10) -> list[SerpResult]:
        try:
            resp = httpx.get(
                self.endpoint,
                params={"q": query, "key": self.api_key, "cx": self.cx, "num": min(n, 10)},
                timeout=10.0,
            )
        except httpx.HTTPError as exc:
            logger.warning("serp.google_cse.http_error", extra={"error": str(exc)})
            return []
        if resp.status_code != 200:
            logger.warning("serp.google_cse.bad_status", extra={"status": resp.status_code})
            return []
        items = resp.json().get("items") or []
        return [
            SerpResult(title=r.get("title", ""), url=r.get("link", ""), snippet=r.get("snippet", ""))
            for r in items
        ]


class _FixtureBackend:
    """Replay-from-fixture backend. Reads SERP results from a JSON fixture
    file when `TRUSTGATE_SERP_FIXTURE` env var points to one. Lets the
    algorithm be exercised against real Google SERP data captured manually
    (e.g. from a browser snapshot) without depending on a paid backend.

    Falls back to live DDG when a query is not present in the fixture, so a
    fixture covering one person still allows other queries through.
    """

    name = "fixture"

    def __init__(self, fixture_path: str):
        import json
        from pathlib import Path

        self.fixture_path = Path(fixture_path)
        with self.fixture_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        # Map query (lowercased) -> list of {title, url, snippet}
        self._by_query: dict[str, list[dict]] = {}
        for entry in data.get("queries", []):
            self._by_query[entry["query"].lower()] = entry.get("results", [])
        self._fallback: SerpSearchBackend | None = None

    def _match(self, query: str) -> list[dict] | None:
        q = query.lower()
        if q in self._by_query:
            return self._by_query[q]
        unquoted = q.strip('"').strip()
        if unquoted in self._by_query:
            return self._by_query[unquoted]
        # Try matching with quotes added back
        with_quotes = f'"{unquoted}"'
        if with_quotes in self._by_query:
            return self._by_query[with_quotes]
        return None

    def search(self, query: str, n: int = 10) -> list[SerpResult]:
        rows = self._match(query)
        if rows is not None:
            return [
                SerpResult(title=r.get("title", ""), url=r.get("url", ""), snippet=r.get("snippet", ""))
                for r in rows[:n]
            ]
        if self._fallback is None:
            self._fallback = _DuckDuckGoHtmlBackend()
        return self._fallback.search(query, n=n)


class _DuckDuckGoHtmlBackend:
    """Free fallback — scrapes the lite HTML endpoint. No auth; rate-limited.

    Use as a default for the OSS-launch zero-config demo. Production
    deployments should configure a paid backend.
    """

    name = "duckduckgo_html"
    endpoint = "https://html.duckduckgo.com/html/"

    def search(self, query: str, n: int = 10) -> list[SerpResult]:
        try:
            resp = httpx.post(
                self.endpoint,
                data={"q": query},
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; Trustgate/1.2; +https://trustgate.io)",
                },
                timeout=15.0,
            )
        except httpx.HTTPError as exc:
            logger.warning("serp.ddg.http_error", extra={"error": str(exc)})
            return []
        if resp.status_code != 200:
            logger.warning("serp.ddg.bad_status", extra={"status": resp.status_code})
            return []
        parser = _DDGHtmlParser()
        parser.feed(resp.text)
        return parser.results[:n]


# ---------------------------------------------------------------------------
# DDG HTML parser — extracts (title, url, snippet) triples
# ---------------------------------------------------------------------------


class _DDGHtmlParser(HTMLParser):
    """Minimal parser over the DuckDuckGo lite HTML layout. The lite page
    nests each result in `<div class="result__body">` with anchor + snippet."""

    def __init__(self):
        super().__init__()
        self.results: list[SerpResult] = []
        self._in_title_a = False
        self._in_snippet = False
        self._cur_title = ""
        self._cur_url = ""
        self._cur_snippet = ""

    def handle_starttag(self, tag, attrs):
        attrs_d = dict(attrs)
        cls = attrs_d.get("class", "")
        if tag == "a" and "result__a" in cls:
            self._in_title_a = True
            # DDG wraps the real URL in a redirect: /l/?uddg=<encoded>
            raw_href = attrs_d.get("href", "")
            self._cur_url = self._decode_ddg_redirect(raw_href)
            self._cur_title = ""
        elif tag == "a" and "result__snippet" in cls:
            self._in_snippet = True
            self._cur_snippet = ""

    def handle_endtag(self, tag):
        if tag == "a" and self._in_title_a:
            self._in_title_a = False
        elif tag == "a" and self._in_snippet:
            self._in_snippet = False
            if self._cur_url and (self._cur_title or self._cur_snippet):
                self.results.append(
                    SerpResult(
                        title=self._cur_title.strip(),
                        url=self._cur_url.strip(),
                        snippet=self._cur_snippet.strip(),
                    )
                )
                self._cur_title = self._cur_url = self._cur_snippet = ""

    def handle_data(self, data):
        if self._in_title_a:
            self._cur_title += data
        elif self._in_snippet:
            self._cur_snippet += data

    @staticmethod
    def _decode_ddg_redirect(href: str) -> str:
        # DDG wraps targets in `//duckduckgo.com/l/?uddg=<encoded>&...`
        if not href:
            return ""
        if href.startswith("//"):
            href = "https:" + href
        try:
            parsed = urlparse(href)
            if "duckduckgo.com" in (parsed.netloc or "") and parsed.path.endswith("/l/"):
                q = parse_qs(parsed.query)
                if "uddg" in q and q["uddg"]:
                    return unquote(q["uddg"][0])
        except Exception:
            pass
        return href


def get_serp_backend() -> SerpSearchBackend:
    """Pick the best-configured backend from env. Order:
      TRUSTGATE_SERP_FIXTURE (replay file) > BRAVE_SEARCH_API_KEY
      > (GOOGLE_CSE_API_KEY+GOOGLE_CSE_CX) > DDG fallback.
    """
    fixture = os.environ.get("TRUSTGATE_SERP_FIXTURE")
    if fixture and os.path.exists(fixture):
        return _FixtureBackend(fixture)
    brave = os.environ.get("BRAVE_SEARCH_API_KEY")
    if brave:
        return _BraveSearchBackend(brave)
    gkey = os.environ.get("GOOGLE_CSE_API_KEY")
    gcx = os.environ.get("GOOGLE_CSE_CX")
    if gkey and gcx:
        return _GoogleCustomSearchBackend(gkey, gcx)
    return _DuckDuckGoHtmlBackend()


# ---------------------------------------------------------------------------
# Signal extraction
# ---------------------------------------------------------------------------


# URL → platform handle. Each entry is (regex, platform). Order matters:
# more-specific patterns first.
_HANDLE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^(?:https?://)?(?:www\.)?linkedin\.com/in/([A-Za-z0-9\-_.]+)/?", re.IGNORECASE), "linkedin"),
    (re.compile(r"^(?:https?://)?(?:www\.)?(?:x|twitter)\.com/([A-Za-z0-9_]{1,15})(?:/|\?|$)", re.IGNORECASE), "x"),
    (re.compile(r"^(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9._]{1,30})/?", re.IGNORECASE), "instagram"),
    (re.compile(r"^(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9\-]{1,39})/?$", re.IGNORECASE), "github"),
    (re.compile(r"^(?:https?://)?(?:www\.)?medium\.com/@([A-Za-z0-9\-_.]+)/?", re.IGNORECASE), "medium"),
    (re.compile(r"^(?:https?://)?([A-Za-z0-9\-_.]+)\.medium\.com/?", re.IGNORECASE), "medium"),
    (re.compile(r"^(?:https?://)?(?:www\.)?reddit\.com/user/([A-Za-z0-9_\-]{3,20})/?", re.IGNORECASE), "reddit"),
    (re.compile(r"^(?:https?://)?(?:www\.)?youtube\.com/(?:@|c/|channel/|user/)?([A-Za-z0-9\-_.]+)/?", re.IGNORECASE), "youtube"),
    (re.compile(r"^(?:https?://)?(?:[a-z0-9.\-]+\.)?bsky\.(?:app|social)/profile/([A-Za-z0-9.\-]+)/?", re.IGNORECASE), "bluesky"),
    (re.compile(r"^(?:https?://)?(?:www\.)?facebook\.com/([A-Za-z0-9.\-]+)/?", re.IGNORECASE), "facebook"),
]

# Snippet text → audience count. Matches "21.4K+ followers", "14.2K followers",
# "1.2M subscribers", "4,800 fans".
_AUDIENCE_RE = re.compile(
    r"(\d[\d,.]*)\s*([KMB])?\+?\s*(followers|subscribers|fans)",
    re.IGNORECASE,
)

# Snippet → role/org. Loose but useful: "Founder of X", "CEO at Y", "GP @ Z".
_ROLE_RE = re.compile(
    r"\b(Founder|Co-?Founder|CEO|CTO|COO|CFO|Founding\s+Engineer|VP|Director|Partner|"
    r"Managing\s+Partner|General\s+Partner|GP|Principal|Lead|Head)\s+(?:of|at|@)\s+"
    r"([A-Z][A-Za-z0-9&.,'\- ]{1,60})",
    re.IGNORECASE,
)

# Domains that constitute an "institutional anchor". The presence of a person
# in these properties is a strong existence + verification signal.
_INSTITUTIONAL_DOMAINS: set[str] = {
    "en.wikipedia.org",
    "wikipedia.org",
    "wikidata.org",
    "crunchbase.com",
    "linkedin.com",          # public LinkedIn URL is institutional even if profile is paywalled
    "scholar.google.com",
    "orcid.org",
    "dblp.org",
    "ieee.org",
    "acm.org",
    "ted.com",
}
_INSTITUTIONAL_TLDS: tuple[str, ...] = (".edu", ".ac.uk", ".ac.jp", ".gov", ".mil")

# Red-flag terms — appearance in snippet text suggests adverse public record.
_RED_FLAG_RE = re.compile(
    r"\b(arrested|indicted|convicted|fraud|scam|sentenced|deplatformed|banned\s+from|"
    r"sued\s+for|class\s+action|investigation\s+into|disbarred|sanctions)\b",
    re.IGNORECASE,
)

# "16+ years of experience" / "20 years driving" — proxy for tenure when API
# data doesn't expose account age (LinkedIn, X gated).
_YEARS_EXPERIENCE_RE = re.compile(
    r"\b(\d{1,2})\+?\s+years?\s+(?:of\s+)?(?:experience|driving|in|at|of)\b",
    re.IGNORECASE,
)
# "founded in 2004 at age 16" / "founded ennovateNIGERIA in 2004"
_FOUNDED_YEAR_RE = re.compile(r"\bfound(?:ed|ing|er)\b[^.]{0,80}?\b(19\d{2}|20\d{2})\b", re.IGNORECASE)
# Educational anchors — top-tier institutions whose mention provides a
# credential-equivalent signal even when not from .edu/.gov domains.
_EDUCATION_ANCHORS = re.compile(
    r"\b(Wharton|Harvard|Stanford|MIT|Yale|Princeton|Columbia|Oxford|Cambridge|"
    r"Berkeley|CMU|Caltech|IIT|NUS|INSEAD|LBS)\b(?:\s+(?:MBA|School|University|Business))?",
    re.IGNORECASE,
)


def _platform_handle_from_url(url: str) -> tuple[str, str] | None:
    for pat, platform in _HANDLE_PATTERNS:
        m = pat.match(url)
        if not m:
            continue
        handle = m.group(1)
        # Filter obvious non-handle paths
        if handle.lower() in {
            "search", "home", "explore", "about", "help", "intent", "share",
            "watch", "results", "posts", "share-with",
        }:
            continue
        return platform, handle
    return None


def _parse_audience(text: str) -> dict[str, int]:
    """Extract follower counts keyed by the *unit* (just "followers" /
    "subscribers" / "fans"). Caller multiplies by URL-derived platform."""
    out: dict[str, int] = {}
    for m in _AUDIENCE_RE.finditer(text or ""):
        raw, suffix, kind = m.group(1), m.group(2), m.group(3)
        try:
            n = float(raw.replace(",", ""))
        except ValueError:
            continue
        if suffix:
            n *= {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[suffix.upper()]
        kind_l = kind.lower()
        if n > 0:
            # Keep the max observed for this unit type
            if out.get(kind_l, 0) < int(n):
                out[kind_l] = int(n)
    return out


def _is_institutional(domain: str) -> bool:
    if domain in _INSTITUTIONAL_DOMAINS:
        return True
    return domain.endswith(_INSTITUTIONAL_TLDS)


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------


# Platforms worth a dedicated `site:<domain>` SERP fan-out. Each pass narrows
# the search to a specific domain so we catch handles that wouldn't surface
# in the generic name search. The cost is one extra search per platform.
SITE_SCOPED_PLATFORMS: dict[str, str] = {
    "x":              "x.com",
    "linkedin":       "linkedin.com",
    "github":         "github.com",
    "gist.github":    "gist.github.com",
    "stackexchange":  "stackexchange.com",
    "stackoverflow":  "stackoverflow.com",
    "medium":         "medium.com",
    "dev.to":         "dev.to",
    "hashnode":       "hashnode.com",
    "instagram":      "instagram.com",
    "youtube":        "youtube.com",
    "bluesky":        "bsky.app",
    "wikipedia":      "en.wikipedia.org",
    "crunchbase":     "crunchbase.com",
}


def fingerprint_person(
    display_name: str,
    extra_terms: list[str] | None = None,
    backend: SerpSearchBackend | None = None,
    n: int = 12,
    site_scoped: bool = True,
) -> SerpFingerprint:
    """Build a SerpFingerprint for a named person.

    `extra_terms`: optional disambiguators (e.g. ["founder", "Nigeria"]) that
    narrow the search.
    `site_scoped`: when True (default), runs an additional `site:<domain>`
    search per platform in SITE_SCOPED_PLATFORMS. Catches handles that a
    generic name search wouldn't surface — especially valuable for X.com
    where the API is paywalled and SERP is the only public-data path.
    """
    backend = backend or get_serp_backend()
    parts = [f'"{display_name}"']
    if extra_terms:
        parts.extend(extra_terms)
    query = " ".join(parts)

    results = backend.search(query, n=n)
    fp = SerpFingerprint(query=query, n_results=len(results), raw_results=list(results))
    seen_urls: set[str] = {r.url for r in results if r.url}

    # First pass: extract from the generic search so we know which platforms
    # are already covered and don't need a `site:` fan-out.
    _extract_into_fingerprint(fp, results)

    # Site-scoped fan-out — adaptive. Skip platforms already represented to
    # save API calls and dodge rate limits. Throttle the free DDG backend.
    if site_scoped:
        import time as _time
        is_ddg = getattr(backend, "name", "") == "duckduckgo_html"
        already = set(fp.discovered_handles.keys())
        extra_results: list[SerpResult] = []
        for tag, domain in SITE_SCOPED_PLATFORMS.items():
            if tag in already:
                continue
            try:
                scoped_q = f'"{display_name}" site:{domain}'
                scoped = backend.search(scoped_q, n=5)
                if is_ddg:
                    _time.sleep(1.0)
            except Exception as exc:
                logger.debug("serp.site_scoped.error", extra={"site": domain, "error": str(exc)})
                continue
            for r in scoped:
                if not r.url or r.url in seen_urls:
                    continue
                seen_urls.add(r.url)
                extra_results.append(r)

        if extra_results:
            fp.raw_results.extend(extra_results)
            fp.n_results = len(fp.raw_results)
            _extract_into_fingerprint(fp, extra_results)

    return fp


def _extract_into_fingerprint(fp: SerpFingerprint, results: list[SerpResult]) -> None:
    """Apply all per-result signal extraction into `fp`. Idempotent — calling
    multiple times with overlapping results updates rather than duplicates.
    """
    for r in results:
        domain = r.domain
        if not domain:
            continue
        fp.reference_domains.add(domain)
        if _is_institutional(domain):
            fp.institutional_anchors.add(domain)

        # Handle extraction from URL — first-seen wins so the top-ranked
        # search result decides the canonical handle (mitigates impersonators).
        url_handle = _platform_handle_from_url(r.url)
        if url_handle:
            platform, handle = url_handle
            fp.discovered_handles.setdefault(platform, handle)

        combined_text = f"{r.title} {r.snippet}"
        for kind, n_followers in _parse_audience(combined_text).items():
            tag = url_handle[0] if url_handle else f"_{kind}"
            if fp.audience_signals.get(tag, 0) < n_followers:
                fp.audience_signals[tag] = n_followers
        for m in _ROLE_RE.finditer(combined_text):
            role, org = m.group(1), m.group(2)
            entry = f"{role} of {org.strip()}"
            if entry not in fp.claimed_roles:
                fp.claimed_roles.append(entry)
        for m in _RED_FLAG_RE.finditer(combined_text):
            term = m.group(1)
            if term.lower() not in [rf.lower() for rf in fp.red_flags]:
                fp.red_flags.append(term)
        for m in _YEARS_EXPERIENCE_RE.finditer(combined_text):
            try:
                years = int(m.group(1))
                if 0 < years < 70:
                    fp.declared_years_of_experience = max(
                        fp.declared_years_of_experience, years
                    )
            except ValueError:
                continue
        for m in _FOUNDED_YEAR_RE.finditer(combined_text):
            try:
                year = int(m.group(1))
                if 1900 < year < 2100:
                    if fp.earliest_founding_year is None or year < fp.earliest_founding_year:
                        fp.earliest_founding_year = year
            except ValueError:
                continue
        for m in _EDUCATION_ANCHORS.finditer(combined_text):
            fp.education_anchors.add(m.group(1).title())


# ---------------------------------------------------------------------------
# Scoring contributions derived from a fingerprint
# ---------------------------------------------------------------------------


@dataclass
class SerpScoreContribution:
    """Numbers ready to plug into compute_trust_score(). Designed to leave
    the existing 6 sub-score algorithm untouched and ride alongside as:
      • an extra credential count (institutional anchors add to credential_bonus)
      • an extra multiplicative boost (reference density adds up to +10%)
      • an optional dampening lift (cross-source name agreement)
    """

    reference_boost: float       # multiplier ≥ 1.0
    extra_credentials: int       # adds to credential_count for _credential_bonus
    red_flag_penalty: float      # multiplier ≤ 1.0
    # Audience hints — caller can use these to seed an IdentityProfile when
    # no platform API would otherwise expose the number.
    audience_by_platform: dict[str, int]
    discovered_handles: dict[str, str]
    # Phase D8 — cross-source name agreement raises the dampening floor when
    # ≥3 distinct authoritative sources name the same person.
    dampening_lift: float = 1.0


def fingerprint_to_score_contribution(
    fp: SerpFingerprint,
    *,
    reference_boost_cap: float = 0.10,
    red_flag_penalty_cap: float = 0.40,
) -> SerpScoreContribution:
    """Translate a SerpFingerprint into numbers the scoring engine consumes.

    `reference_boost_cap` (default 0.10): a person referenced across ~30+
    distinct domains gets the full +10% multiplicative boost.

    `red_flag_penalty_cap` (default 0.40): each unique red-flag term in
    snippets multiplies the score by (1 - cap/n_terms), capping demotion
    at 40% so the algorithm doesn't permanently zero anyone.
    """
    boost = 1.0 + reference_boost_cap * fp.reference_density
    if fp.red_flags:
        # Diminishing penalty per term, capped.
        penalty = red_flag_penalty_cap * (1.0 - math.exp(-len(fp.red_flags) / 2))
        red_flag_factor = max(1.0 - penalty, 1.0 - red_flag_penalty_cap)
    else:
        red_flag_factor = 1.0
    return SerpScoreContribution(
        reference_boost=boost,
        extra_credentials=fp.institutional_credential_count,
        red_flag_penalty=red_flag_factor,
        audience_by_platform=dict(fp.audience_signals),
        discovered_handles=dict(fp.discovered_handles),
    )
