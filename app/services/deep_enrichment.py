"""Identity-shape deep enrichment — beyond the basic-API tier.

Each function takes a discovered handle / URL / name and pulls signals the
free APIs don't expose. Used downstream of `enrichment.discover_and_fetch`
and `serp.fingerprint_person` to lift scoring fidelity for identity shapes
that don't show up via GitHub/HN/Reddit/StackExchange:

  • fetch_wikidata_person       — structured facts (employer, school, awards)
  • fetch_personal_site_relme   — confirms rel="me" links from a personal site
  • fetch_crunchbase_public     — basic role + history from a Crunchbase URL
  • cross_source_name_agreement — confidence that all discovered sources
                                  point at the same person

All endpoints are unauthenticated. Failures are silent (return empty) so
the scoring pipeline keeps moving even when one source breaks.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Wikidata — structured facts about a named person
# ---------------------------------------------------------------------------

WIKIDATA_API = "https://www.wikidata.org/w/api.php"

# Wikidata property codes we care about.
_WIKIDATA_PROPS = {
    "P31":   "instance_of",         # should be Q5 (human) for a person
    "P21":   "gender",
    "P27":   "country_of_citizenship",
    "P19":   "place_of_birth",
    "P569":  "date_of_birth",
    "P108":  "employer",
    "P69":   "educated_at",
    "P39":   "position_held",
    "P106":  "occupation",
    "P800":  "notable_work",
    "P166":  "award_received",
    "P856":  "official_website",
    "P2002": "twitter_handle",
    "P2003": "instagram_handle",
    "P2013": "facebook_username",
    "P2671": "google_knowledge_graph_id",
}


@dataclass
class WikidataPerson:
    qid: str
    label: str
    description: str = ""
    facts: dict[str, list[str]] = field(default_factory=dict)  # prop_name -> list of values
    raw_claims: dict[str, Any] = field(default_factory=dict)

    @property
    def is_person(self) -> bool:
        return "Q5" in (self.facts.get("instance_of") or [])

    @property
    def has_credentials(self) -> int:
        """Each well-formed structured fact counts as an institutional anchor."""
        count = 0
        for key in ("employer", "educated_at", "position_held", "award_received", "notable_work"):
            if self.facts.get(key):
                count += 1
        return count


def _wikidata_get(params: dict) -> dict | None:
    """Wrapper for Wikidata API calls with timeout + user-agent."""
    try:
        resp = httpx.get(
            WIKIDATA_API,
            params=params,
            headers={"User-Agent": "Trustgate/1.2 (research; +https://trustgate.io)"},
            timeout=10.0,
        )
    except httpx.HTTPError as exc:
        logger.debug("wikidata.http_error", extra={"error": str(exc), "params": params})
        return None
    if resp.status_code != 200:
        return None
    try:
        return resp.json()
    except ValueError:
        return None


def fetch_wikidata_person(display_name: str) -> WikidataPerson | None:
    """Search Wikidata for an entity by name; return a structured fact dump
    for the first matching human (`instance_of = Q5`).

    Returns None when no human entity matches. Doesn't synthesize facts —
    only reports what Wikidata actually has.
    """
    search = _wikidata_get(
        {
            "action": "wbsearchentities",
            "search": display_name,
            "language": "en",
            "format": "json",
            "limit": 5,
        }
    )
    if not search:
        return None
    candidates = search.get("search") or []
    if not candidates:
        return None

    for cand in candidates:
        qid = cand.get("id")
        if not qid:
            continue
        # Fetch the entity to inspect its claims.
        entity_resp = _wikidata_get(
            {
                "action": "wbgetentities",
                "ids": qid,
                "format": "json",
                "props": "labels|descriptions|claims",
                "languages": "en",
            }
        )
        if not entity_resp:
            continue
        entity = (entity_resp.get("entities") or {}).get(qid)
        if not entity:
            continue
        claims = entity.get("claims") or {}

        # Translate claims to readable facts.
        facts: dict[str, list[str]] = {}
        for prop_code, prop_name in _WIKIDATA_PROPS.items():
            values = []
            for claim in claims.get(prop_code, []):
                main = ((claim.get("mainsnak") or {}).get("datavalue") or {}).get("value")
                if isinstance(main, dict):
                    # Object value (entity reference or time)
                    if "id" in main:
                        values.append(main["id"])  # follow-up: resolve QID to label
                    elif "time" in main:
                        values.append(main["time"])
                    elif "amount" in main:
                        values.append(str(main["amount"]))
                elif main is not None:
                    values.append(str(main))
            if values:
                facts[prop_name] = values

        person = WikidataPerson(
            qid=qid,
            label=(entity.get("labels", {}).get("en") or {}).get("value", display_name),
            description=(entity.get("descriptions", {}).get("en") or {}).get("value", ""),
            facts=facts,
            raw_claims=claims,
        )
        # Only return if it's actually a human.
        if person.is_person:
            return person

    return None


def resolve_qid_labels(qids: list[str]) -> dict[str, str]:
    """Bulk-resolve a list of Wikidata QIDs to their English labels."""
    if not qids:
        return {}
    # Wikidata caps at 50 entities per wbgetentities call.
    out: dict[str, str] = {}
    for batch_start in range(0, len(qids), 50):
        batch = qids[batch_start : batch_start + 50]
        resp = _wikidata_get(
            {
                "action": "wbgetentities",
                "ids": "|".join(batch),
                "format": "json",
                "props": "labels",
                "languages": "en",
            }
        )
        if not resp:
            continue
        for qid, entity in (resp.get("entities") or {}).items():
            label = (entity.get("labels", {}).get("en") or {}).get("value")
            if label:
                out[qid] = label
    return out


# ---------------------------------------------------------------------------
# rel="me" / Web1.0 personal-site crawl
# ---------------------------------------------------------------------------


class _RelMeHTMLParser(HTMLParser):
    """Extract rel="me" links (IndieAuth-style identity verification) and
    a handful of social meta tags from a personal-site HTML page."""

    def __init__(self):
        super().__init__()
        self.rel_me_links: list[str] = []
        self.meta_socials: dict[str, str] = {}
        self.title: str = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("a", "link"):
            rel = (a.get("rel") or "").lower()
            if "me" in rel.split():
                href = a.get("href")
                if href and href not in self.rel_me_links:
                    self.rel_me_links.append(href)
        if tag == "meta":
            prop = (a.get("property") or a.get("name") or "").lower()
            content = a.get("content")
            if not content:
                return
            if prop in {
                "og:profile:username",
                "og:profile:first_name",
                "og:profile:last_name",
                "twitter:creator",
                "twitter:site",
                "twitter:username",
                "linkedin:profile",
                "github:user",
                "author",
            }:
                self.meta_socials.setdefault(prop, content)
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


@dataclass
class PersonalSiteFingerprint:
    url: str
    title: str = ""
    rel_me: list[str] = field(default_factory=list)
    meta_socials: dict[str, str] = field(default_factory=dict)


def fetch_personal_site_relme(
    url: str, *, max_redirects: int = 3, timeout: float = 10.0
) -> PersonalSiteFingerprint | None:
    """Fetch a personal site (HTTP/HTTPS) and extract its rel="me" + social
    meta links. Used for identity-binding: a `rel="me"` link from
    opata.dev → twitter.com/opata IS the same person *by the personal-
    site author's explicit declaration*. IndieAuth pattern.
    """
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        resp = httpx.get(
            url,
            headers={"User-Agent": "Trustgate/1.2 (+https://trustgate.io)"},
            timeout=timeout,
            follow_redirects=True,
        )
    except httpx.HTTPError as exc:
        logger.debug("personal_site.http_error", extra={"url": url, "error": str(exc)})
        return None
    if resp.status_code != 200:
        return None
    # Be polite: don't process anything that isn't HTML.
    content_type = resp.headers.get("content-type", "").lower()
    if "html" not in content_type and not resp.text.lstrip().startswith("<"):
        return None
    parser = _RelMeHTMLParser()
    try:
        parser.feed(resp.text[:512_000])  # cap parsing at 500KB
    except Exception as exc:
        logger.debug("personal_site.parse_error", extra={"url": url, "error": str(exc)})
        return None
    return PersonalSiteFingerprint(
        url=url,
        title=parser.title.strip(),
        rel_me=parser.rel_me_links,
        meta_socials=parser.meta_socials,
    )


# ---------------------------------------------------------------------------
# Crunchbase — public-page extraction
# ---------------------------------------------------------------------------


# Crunchbase exposes a person/organization slug in URL paths. Public profile
# pages contain a JSON-LD <script> with structured Schema.org data — far
# more reliable than scraping the rendered HTML.
class _CrunchbaseHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._in_jsonld = False
        self.jsonld_payloads: list[str] = []
        self._buf = ""

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            a = dict(attrs)
            if a.get("type") == "application/ld+json":
                self._in_jsonld = True
                self._buf = ""

    def handle_endtag(self, tag):
        if tag == "script" and self._in_jsonld:
            self._in_jsonld = False
            if self._buf.strip():
                self.jsonld_payloads.append(self._buf.strip())
            self._buf = ""

    def handle_data(self, data):
        if self._in_jsonld:
            self._buf += data


@dataclass
class CrunchbaseFacts:
    url: str
    name: str = ""
    description: str = ""
    job_title: str = ""
    works_for: str = ""
    schools: list[str] = field(default_factory=list)
    awards: list[str] = field(default_factory=list)


def fetch_crunchbase_public(url: str, *, timeout: float = 10.0) -> CrunchbaseFacts | None:
    """Fetch a Crunchbase person URL and extract the JSON-LD facts.

    Best-effort — Crunchbase serves JS-rendered pages to anonymous visitors,
    but the JSON-LD blocks ARE included in the initial HTML. Returns the
    facts we can extract or None on any error.
    """
    if "crunchbase.com" not in url:
        return None
    try:
        resp = httpx.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; Trustgate/1.2; +https://trustgate.io)",
                "Accept": "text/html,application/xhtml+xml",
            },
            timeout=timeout,
            follow_redirects=True,
        )
    except httpx.HTTPError as exc:
        logger.debug("crunchbase.http_error", extra={"url": url, "error": str(exc)})
        return None
    if resp.status_code != 200:
        return None
    parser = _CrunchbaseHTMLParser()
    try:
        parser.feed(resp.text[:512_000])
    except Exception:
        return None
    if not parser.jsonld_payloads:
        return None

    import json

    facts = CrunchbaseFacts(url=url)
    for blob in parser.jsonld_payloads:
        try:
            data = json.loads(blob)
        except json.JSONDecodeError:
            continue
        # JSON-LD can be a list, dict, or @graph wrapping. Flatten:
        items = data if isinstance(data, list) else [data]
        flat: list[dict] = []
        for item in items:
            if isinstance(item, dict):
                graph = item.get("@graph")
                flat.extend(graph if isinstance(graph, list) else [item])
        for item in flat:
            if not isinstance(item, dict):
                continue
            t = item.get("@type")
            types = t if isinstance(t, list) else [t]
            if "Person" in types:
                facts.name = item.get("name", "") or facts.name
                facts.description = item.get("description", "") or facts.description
                facts.job_title = item.get("jobTitle", "") or facts.job_title
                wf = item.get("worksFor")
                if isinstance(wf, dict):
                    facts.works_for = wf.get("name", "") or facts.works_for
                elif isinstance(wf, str):
                    facts.works_for = wf or facts.works_for
                alumnis = item.get("alumniOf")
                if isinstance(alumnis, list):
                    for a in alumnis:
                        name = a.get("name") if isinstance(a, dict) else a
                        if isinstance(name, str) and name not in facts.schools:
                            facts.schools.append(name)
                elif isinstance(alumnis, dict):
                    n = alumnis.get("name")
                    if n and n not in facts.schools:
                        facts.schools.append(n)
                awards = item.get("award")
                if isinstance(awards, list):
                    facts.awards.extend(a for a in awards if isinstance(a, str))
                elif isinstance(awards, str):
                    facts.awards.append(awards)
    if not (facts.name or facts.job_title or facts.works_for):
        return None
    return facts


# ---------------------------------------------------------------------------
# Cross-source name agreement
# ---------------------------------------------------------------------------


# Apostrophes get stripped, NOT split on. "O'Connor" → "oconnor", preserving
# the full surname. All other separators split.
_TOKEN_SPLIT = re.compile(r"[\s.\-_,\"()]+")


def _normalize_name_tokens(name: str) -> set[str]:
    """Lowercase + strip diacritics + tokenize for set-overlap comparison."""
    import unicodedata

    if not name:
        return set()
    n = unicodedata.normalize("NFKD", name)
    n = "".join(c for c in n if not unicodedata.combining(c))
    n = n.lower().replace("'", "").replace("’", "")  # strip ASCII + curly apostrophe
    return {t for t in _TOKEN_SPLIT.split(n) if len(t) >= 2}


@dataclass
class NameAgreement:
    target: str
    n_sources: int = 0
    n_agreeing: int = 0
    mean_jaccard: float = 0.0

    @property
    def fraction_agreeing(self) -> float:
        return self.n_agreeing / self.n_sources if self.n_sources else 0.0

    @property
    def is_high_confidence(self) -> bool:
        """≥3 sources agree AND mean Jaccard ≥ 0.5 → high confidence the
        discovered profiles are all the same person."""
        return self.n_agreeing >= 3 and self.mean_jaccard >= 0.5


def cross_source_name_agreement(
    target_name: str, discovered_names: list[str]
) -> NameAgreement:
    """Compute how strongly the discovered profile-names corroborate the
    target name.

    Each source's display_name is compared to `target_name` by Jaccard
    overlap of normalized tokens. A source counts as "agreeing" when its
    overlap with the target is ≥ 0.5 (typically: shares a first or last name).
    """
    target_tokens = _normalize_name_tokens(target_name)
    if not target_tokens:
        return NameAgreement(target=target_name)

    n_sources = 0
    n_agreeing = 0
    jaccard_sum = 0.0
    for nm in discovered_names:
        toks = _normalize_name_tokens(nm)
        if not toks:
            continue
        n_sources += 1
        union = target_tokens | toks
        inter = target_tokens & toks
        jaccard = len(inter) / len(union) if union else 0.0
        jaccard_sum += jaccard
        if jaccard >= 0.5:
            n_agreeing += 1
    return NameAgreement(
        target=target_name,
        n_sources=n_sources,
        n_agreeing=n_agreeing,
        mean_jaccard=jaccard_sum / n_sources if n_sources else 0.0,
    )


def name_agreement_dampening_lift(agreement: NameAgreement) -> float:
    """When ≥3 distinct profile-bearing sources name the same person,
    that's stronger evidence-of-realness than any single API hit. Reflect
    that by raising the floor of `_compute_dampening`.

    Returns a multiplier in [1.0, 1.25] to apply to the existing dampening
    factor. Capped so we never push past 1.0 in compute_trust_score (the
    final clamp still applies).
    """
    if not agreement.is_high_confidence:
        return 1.0
    # Logistic in (agreement.n_agreeing - 3), saturating near 5+ sources.
    extra = max(0, agreement.n_agreeing - 3)
    lift = 1.0 + min(0.25, 0.08 * (1 + extra))
    return lift
