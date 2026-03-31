/**
 * Cross-platform link discovery.
 *
 * Scans the current profile page for links to other social platforms.
 * Returns an array of {platform, handle, url} objects that can be sent
 * to the backend for scraping via the Playwright pool.
 */

"use strict";

/* eslint-disable no-unused-vars */

const SOCIAL_LINK_PATTERNS = [
  { platform: "twitter",    regex: /(?:twitter|x)\.com\/([A-Za-z0-9_]{1,30})(?:[/?#]|$)/i,         blocked: new Set(["home", "search", "explore", "settings", "i", "intent", "share", "hashtag"]) },
  { platform: "github",     regex: /github\.com\/([A-Za-z0-9_-]{1,39})(?:[/?#]|$)/i,               blocked: new Set(["settings", "marketplace", "explore", "features", "pricing", "enterprise", "topics", "trending", "login", "join", "about", "security", "orgs", "pulls", "issues", "notifications"]) },
  { platform: "linkedin",   regex: /linkedin\.com\/in\/([A-Za-z0-9_-]+?)(?:[/?#]|$)/i,              blocked: new Set([]) },
  { platform: "instagram",  regex: /instagram\.com\/([A-Za-z0-9_.]{1,30})(?:[/?#]|$)/i,             blocked: new Set(["explore", "reels", "stories", "direct", "accounts", "p", "tv", "reel"]) },
  { platform: "youtube",    regex: /youtube\.com\/@([A-Za-z0-9_-]+?)(?:[/?#]|$)/i,                  blocked: new Set([]) },
  { platform: "reddit",     regex: /reddit\.com\/user\/([A-Za-z0-9_-]+?)(?:[/?#]|$)/i,              blocked: new Set([]) },
  { platform: "bluesky",    regex: /bsky\.app\/profile\/([A-Za-z0-9._-]+?)(?:[/?#]|$)/i,            blocked: new Set([]) },
  { platform: "hackernews", regex: /news\.ycombinator\.com\/user\?id=([A-Za-z0-9_-]+)/i,            blocked: new Set([]) },
  { platform: "polymarket",    regex: /polymarket\.com\/profile\/([A-Za-z0-9_-]+?)(?:[/?#]|$)/i,       blocked: new Set([]) },
  { platform: "stackoverflow", regex: /stackoverflow\.com\/users\/(\d+)/i,                            blocked: new Set([]) },
  { platform: "quora",         regex: /quora\.com\/profile\/([A-Za-z0-9_-]+?)(?:[/?#]|$)/i,           blocked: new Set([]) },
];

/**
 * Scan the page for social media links.
 * @param {string} currentPlatform - The platform of the page we're on (to skip self-links)
 * @param {string} currentHandle - The handle on the current page
 * @returns {Array<{platform: string, handle: string, url: string}>}
 */
function discoverSocialLinks(currentPlatform, currentHandle) {
  const discovered = new Map(); // key: "platform:handle" → value: {platform, handle, url}

  // Strategy 1: Scan all <a> tags on the page
  const allLinks = document.querySelectorAll("a[href]");
  for (const link of allLinks) {
    const href = link.href || "";
    _matchUrl(href, currentPlatform, currentHandle, discovered);
  }

  // Strategy 2: Scan visible text content for URLs in bio/about sections
  const bioSelectors = [
    // LinkedIn
    ".pv-about__summary-text", "#about ~ div .inline-show-more-text",
    // Twitter
    '[data-testid="UserDescription"]', '[data-testid="UserUrl"]',
    // GitHub
    ".user-profile-bio", ".p-note", ".vcard-details",
    // Reddit
    "[data-testid='profile-description']",
    // Instagram
    "header section span",
    // Bluesky
    "[data-testid='profileHeaderDescription']",
    // Generic
    ".bio", ".about", ".description", "[class*='bio']", "[class*='about']",
  ];

  for (const sel of bioSelectors) {
    const els = document.querySelectorAll(sel);
    for (const el of els) {
      const text = el.textContent || "";
      // Find URLs in text
      const urlMatches = text.match(/https?:\/\/[^\s<>"']+/gi) || [];
      for (const url of urlMatches) {
        _matchUrl(url, currentPlatform, currentHandle, discovered);
      }
      // Find @handles that might be Twitter/Instagram
      const handleMatches = text.match(/@([A-Za-z0-9_]{1,30})/g) || [];
      for (const h of handleMatches) {
        const cleanHandle = h.replace("@", "");
        // Don't add if it's the current handle
        if (cleanHandle.toLowerCase() === currentHandle.toLowerCase()) continue;
        // Heuristic: if we're on LinkedIn/GitHub, @handle is likely Twitter
        if (currentPlatform === "linkedin" || currentPlatform === "github") {
          const key = `twitter:${cleanHandle.toLowerCase()}`;
          if (!discovered.has(key)) {
            discovered.set(key, {
              platform: "twitter",
              handle: cleanHandle,
              url: `https://x.com/${cleanHandle}`,
            });
          }
        }
      }
    }
  }

  return Array.from(discovered.values());
}

function _matchUrl(url, currentPlatform, currentHandle, discovered) {
  for (const pattern of SOCIAL_LINK_PATTERNS) {
    const match = url.match(pattern.regex);
    if (!match) continue;

    const handle = match[1];
    if (!handle) continue;
    if (pattern.blocked.has(handle.toLowerCase())) continue;

    // Skip self-links (same platform & handle)
    if (pattern.platform === currentPlatform && handle.toLowerCase() === currentHandle.toLowerCase()) continue;

    const key = `${pattern.platform}:${handle.toLowerCase()}`;
    if (!discovered.has(key)) {
      discovered.set(key, {
        platform: pattern.platform,
        handle: handle,
        url: url,
      });
    }
  }
}
