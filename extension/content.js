(function () {
  "use strict";

  /* ── Platform detection ─────────────────────────────────────────── */

  const PLATFORM_CONFIGS = {
    linkedin: {
      hostPattern: /linkedin\.com$/,
      pathPattern: /^\/in\/([^/]+)/,
      extract(url) {
        const m = url.pathname.match(this.pathPattern);
        return m ? m[1] : null;
      },
      anchorSelector: "h1.text-heading-xlarge, h1.top-card-layout__title, .pv-top-card .text-heading-xlarge",
    },
    twitter: {
      hostPattern: /(twitter|x)\.com$/,
      pathPattern: /^\/([^/]+)\/?$/,
      blocked: new Set(["home", "search", "explore", "settings", "notifications", "messages", "i", "compose"]),
      extract(url) {
        const m = url.pathname.match(this.pathPattern);
        if (!m) return null;
        const handle = m[1];
        return this.blocked.has(handle.toLowerCase()) ? null : handle;
      },
      anchorSelector: '[data-testid="UserName"], header [role="heading"]',
    },
    github: {
      hostPattern: /github\.com$/,
      pathPattern: /^\/([^/]+)\/?$/,
      blocked: new Set([
        "settings", "marketplace", "explore", "notifications",
        "new", "login", "join", "features", "pricing", "enterprise",
        "sponsors", "topics", "trending", "collections", "events",
        "about", "security", "customer-stories",
      ]),
      extract(url) {
        const m = url.pathname.match(this.pathPattern);
        if (!m) return null;
        const handle = m[1];
        return this.blocked.has(handle.toLowerCase()) ? null : handle;
      },
      anchorSelector: ".vcard-fullname, .p-name, [itemprop='name']",
    },
    reddit: {
      hostPattern: /reddit\.com$/,
      pathPattern: /^\/user\/([^/]+)/,
      extract(url) {
        const m = url.pathname.match(this.pathPattern);
        return m ? m[1] : null;
      },
      anchorSelector: "#profile--id-card h2, [data-testid='profile-header'] h1",
    },
    hackernews: {
      hostPattern: /news\.ycombinator\.com$/,
      pathPattern: /^\/user$/,
      extract(url) {
        if (!this.pathPattern.test(url.pathname)) return null;
        return url.searchParams.get("id") || null;
      },
      anchorSelector: ".hnuser, td.subtext a",
    },
    instagram: {
      hostPattern: /instagram\.com$/,
      pathPattern: /^\/([^/]+)\/?$/,
      blocked: new Set([
        "explore", "reels", "stories", "direct", "accounts",
        "p", "tv", "reel", "about", "legal", "privacy",
      ]),
      extract(url) {
        const m = url.pathname.match(this.pathPattern);
        if (!m) return null;
        const handle = m[1];
        return this.blocked.has(handle.toLowerCase()) ? null : handle;
      },
      anchorSelector: "header section h2, header section h1, [data-testid='user-name']",
    },
    polymarket: {
      hostPattern: /polymarket\.com$/,
      pathPattern: /^\/profile\/([^/]+)/,
      extract(url) {
        const m = url.pathname.match(this.pathPattern);
        return m ? m[1] : null;
      },
      anchorSelector: "[class*='ProfileHeader'] h1, [class*='profile'] h1",
    },
    linkedin_company: {
      hostPattern: /linkedin\.com$/,
      pathPattern: /^\/company\/([^/]+)/,
      extract(url) {
        const m = url.pathname.match(this.pathPattern);
        return m ? m[1] : null;
      },
      anchorSelector: ".org-top-card-summary__title, h1.top-card-layout__title",
      entityType: "company",
    },
    bluesky: {
      hostPattern: /bsky\.app$/,
      pathPattern: /^\/profile\/([^/]+)/,
      extract(url) {
        const m = url.pathname.match(this.pathPattern);
        return m ? m[1] : null;
      },
      anchorSelector: "[data-testid='profileHeaderDisplayName'], h1",
    },
    youtube: {
      hostPattern: /youtube\.com$/,
      pathPattern: /^\/@([^/]+)/,
      extract(url) {
        const m = url.pathname.match(this.pathPattern);
        if (m) return m[1];
        const ch = url.pathname.match(/^\/channel\/([^/]+)/);
        return ch ? ch[1] : null;
      },
      anchorSelector: "#channel-name yt-formatted-string, #channel-header ytd-channel-name",
    },
    stackoverflow: {
      hostPattern: /stackoverflow\.com$/,
      pathPattern: /^\/users\/(\d+)/,
      extract(url) {
        const m = url.pathname.match(this.pathPattern);
        return m ? m[1] : null;
      },
      anchorSelector: ".fs-headline2, .profile-user--name, [class*='user-name']",
    },
    stackexchange: {
      hostPattern: /(?:serverfault|superuser|askubuntu|mathoverflow|stackexchange)\.com$/,
      pathPattern: /^\/users\/(\d+)/,
      extract(url) {
        const m = url.pathname.match(this.pathPattern);
        return m ? m[1] : null;
      },
      anchorSelector: ".fs-headline2, .profile-user--name, [class*='user-name']",
    },
    quora: {
      hostPattern: /quora\.com$/,
      pathPattern: /^\/profile\/([^/]+)/,
      extract(url) {
        const m = url.pathname.match(this.pathPattern);
        return m ? m[1] : null;
      },
      anchorSelector: ".profile_name, [class*='ProfileName']",
    },
  };

  function detectProfile() {
    const url = new URL(window.location.href);
    for (const [platform, cfg] of Object.entries(PLATFORM_CONFIGS)) {
      if (!cfg.hostPattern.test(url.hostname)) continue;
      const handle = cfg.extract(url);
      if (handle) {
        return {
          platform,
          handle,
          anchorSelector: cfg.anchorSelector,
          entityType: cfg.entityType || "individual",
        };
      }
    }
    return null;
  }

  /* ── Dark-mode detection ────────────────────────────────────────── */

  function isDarkMode() {
    if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) return true;
    const bg = getComputedStyle(document.body).backgroundColor;
    if (!bg || bg === "transparent") return false;
    const m = bg.match(/\d+/g);
    if (!m) return false;
    const luminance = (0.299 * +m[0] + 0.587 * +m[1] + 0.114 * +m[2]) / 255;
    return luminance < 0.4;
  }

  /* ── Tier configuration ─────────────────────────────────────────── */

  const TIERS = {
    excellent: { color: "#10b981", label: "Excellent", stroke: "#10b981" },
    good:      { color: "#22c55e", label: "Good",      stroke: "#22c55e" },
    fair:      { color: "#f59e0b", label: "Fair",       stroke: "#f59e0b" },
    poor:      { color: "#ef4444", label: "Poor",       stroke: "#ef4444" },
    untrusted: { color: "#6b7280", label: "Untrusted",  stroke: "#6b7280" },
  };

  function tierInfo(tier) {
    return TIERS[tier] || TIERS.fair;
  }

  function tierClass(tier) {
    return TIERS[tier] ? tier : "fair";
  }

  /* ── SVG arc helpers ────────────────────────────────────────────── */

  function svgRing(size, strokeWidth, score, maxScore, strokeColor, scoreText, scoreClass) {
    const radius = (size - strokeWidth) / 2;
    const circumference = 2 * Math.PI * radius;
    const pct = Math.min(score / maxScore, 1);
    const offset = circumference * (1 - pct);
    const center = size / 2;

    return `
      <svg viewBox="0 0 ${size} ${size}" width="${size}" height="${size}">
        <circle class="${scoreClass}-track" cx="${center}" cy="${center}" r="${radius}" />
        <circle class="${scoreClass}-fill"
          cx="${center}" cy="${center}" r="${radius}"
          stroke="${strokeColor}"
          stroke-dasharray="${circumference}"
          stroke-dashoffset="${offset}" />
        <text class="${scoreClass}-score" x="${center}" y="${center}">${scoreText}</text>
      </svg>
    `;
  }

  /* ── Sub-score labels ───────────────────────────────────────────── */

  const SUB_SCORE_LABELS = {
    existence:       "Existence",
    consistency:     "Consistency",
    engagement:      "Engagement",
    cross_platform:  "Cross-Platform",
    maturity:        "Maturity",
  };

  const SUB_SCORE_MAX = 200;

  /* ── Utility ────────────────────────────────────────────────────── */

  function escapeHtml(str) {
    const el = document.createElement("span");
    el.textContent = str;
    return el.innerHTML;
  }

  /* ══════════════════════════════════════════════════════════════════
     SITE LOGO DETECTION — intelligent logo finder for any website
     ══════════════════════════════════════════════════════════════════ */

  /**
   * Find the site logo element using multiple heuristics, scored by confidence.
   * Returns { element, position } or null.
   */
  function findSiteLogo() {
    const candidates = [];

    // Heuristic 1: Elements with logo-related class/id (highest signal)
    const logoSelectors = [
      '[class*="logo" i]:not(script):not(style)',
      '[id*="logo" i]:not(script):not(style)',
      '[class*="brand" i] img',
      '[id*="brand" i] img',
      '[aria-label*="logo" i]',
      '[aria-label*="home" i] img',
      '[class*="site-title" i]',
      '[class*="navbar-brand" i]',
    ];

    for (const sel of logoSelectors) {
      try {
        const els = document.querySelectorAll(sel);
        for (const el of els) {
          if (_isVisible(el) && _isInHeader(el)) {
            const img = el.tagName === "IMG" ? el : el.querySelector("img") || el.querySelector("svg");
            candidates.push({ element: img || el, confidence: 0.9 });
          }
        }
      } catch { /* Invalid selector on some pages */ }
    }

    // Heuristic 2: First <img> or <svg> inside <header> or <nav>
    for (const container of document.querySelectorAll("header, nav, [role='banner']")) {
      const img = container.querySelector("img, svg");
      if (img && _isVisible(img)) {
        // Prefer images that link to homepage
        const link = img.closest("a");
        const isHomeLink = link && (link.pathname === "/" || link.getAttribute("href") === "/" || link.getAttribute("href") === "#");
        candidates.push({ element: img, confidence: isHomeLink ? 0.85 : 0.6 });
      }
    }

    // Heuristic 3: First <a href="/"> containing an image in the top 200px
    for (const link of document.querySelectorAll('a[href="/"], a[href="./"], a[href="#"]')) {
      const img = link.querySelector("img, svg");
      if (img && _isVisible(img)) {
        const rect = img.getBoundingClientRect();
        if (rect.top < 200) {
          candidates.push({ element: img, confidence: 0.8 });
        }
      }
    }

    // Heuristic 4: First visible <img> in the top 120px of the page that's reasonably sized
    for (const img of document.querySelectorAll("img")) {
      if (!_isVisible(img)) continue;
      const rect = img.getBoundingClientRect();
      if (rect.top > 120) break; // Stop scanning below header area
      const w = rect.width;
      const h = rect.height;
      // Logo-like dimensions: not too big (banner), not too small (icon)
      if (w >= 20 && w <= 300 && h >= 16 && h <= 120) {
        candidates.push({ element: img, confidence: 0.4 });
      }
    }

    if (candidates.length === 0) return null;

    // Sort by confidence descending, take the best
    candidates.sort((a, b) => b.confidence - a.confidence);

    // Deduplicate (same element through different heuristics)
    const seen = new Set();
    for (const c of candidates) {
      if (seen.has(c.element)) continue;
      seen.add(c.element);

      const rect = c.element.getBoundingClientRect();
      // Determine badge position: if logo is on the left half, place badge top-right of it; else top-left
      const position = rect.left < window.innerWidth / 2 ? "right" : "left";
      return { element: c.element, position, confidence: c.confidence };
    }

    return null;
  }

  function _isVisible(el) {
    if (!el) return false;
    const style = getComputedStyle(el);
    if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") return false;
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function _isInHeader(el) {
    // Walk up max 8 parents looking for header/nav/banner
    let node = el;
    for (let i = 0; i < 8 && node; i++) {
      const tag = node.tagName?.toLowerCase();
      if (tag === "header" || tag === "nav") return true;
      const role = node.getAttribute?.("role");
      if (role === "banner" || role === "navigation") return true;
      // Check if element is in the top 150px
      const rect = node.getBoundingClientRect?.();
      if (rect && rect.top < 150 && rect.bottom < 250) return true;
      node = node.parentElement;
    }
    return false;
  }

  /**
   * Extract a clean domain handle from the current URL for company lookup.
   * e.g. "www.stripe.com" -> "stripe", "docs.github.com" -> "github"
   */
  function extractDomainHandle() {
    const hostname = window.location.hostname.toLowerCase();
    // Remove common prefixes
    const clean = hostname.replace(/^(www|app|docs|blog|api|m|mobile|web)\./i, "");
    // Take the domain name (before TLD)
    const parts = clean.split(".");
    if (parts.length >= 2) {
      return parts[parts.length - 2]; // "stripe" from "stripe.com"
    }
    return parts[0];
  }

  /* ══════════════════════════════════════════════════════════════════
     SITE BADGE — compact score indicator placed near site logo
     ══════════════════════════════════════════════════════════════════ */

  let currentSiteBadge = null;

  function removeSiteBadge() {
    if (currentSiteBadge) {
      currentSiteBadge.remove();
      currentSiteBadge = null;
    }
  }

  function createSiteBadge(logoInfo, domain) {
    removeSiteBadge();

    const dark = isDarkMode();
    const badge = document.createElement("div");
    badge.className = "tg-site-badge";
    if (dark) badge.classList.add("tg-dark");
    badge.setAttribute("data-tg-domain", domain);

    // Loading state — small ring
    badge.innerHTML = `
      <div class="tg-site-badge__ring">
        ${svgRing(28, 2.5, 0, 1000, "#e5e7eb", "", "tg-badge__ring")}
        <div class="tg-site-spinner"></div>
      </div>
      <div class="tg-site-badge__tooltip tg-hidden">
        <div class="tg-site-badge__tooltip-score"></div>
        <div class="tg-site-badge__tooltip-name"></div>
        <div class="tg-site-badge__tooltip-brand">Tovbase</div>
      </div>
    `;

    // Position relative to the logo element
    const logoEl = logoInfo.element;
    const wrapper = logoEl.closest("a") || logoEl.parentElement;
    if (wrapper) {
      const pos = getComputedStyle(wrapper).position;
      if (pos === "static") wrapper.style.position = "relative";

      badge.classList.add(
        logoInfo.position === "right" ? "tg-site-badge--right" : "tg-site-badge--left"
      );
      wrapper.appendChild(badge);
    } else {
      // Fallback: fixed position
      badge.classList.add("tg-site-badge--fixed");
      document.body.appendChild(badge);
    }

    currentSiteBadge = badge;
    return badge;
  }

  function renderSiteBadgeScore(badge, data) {
    const { color, label, stroke } = tierInfo(data.tier);
    const score = data.trust_score ?? 0;

    const ring = badge.querySelector(".tg-site-badge__ring");
    const spinner = badge.querySelector(".tg-site-spinner");
    if (spinner) spinner.remove();
    ring.innerHTML = svgRing(28, 2.5, score, 1000, stroke, score, "tg-badge__ring");

    // Populate tooltip
    const tooltip = badge.querySelector(".tg-site-badge__tooltip");
    tooltip.classList.remove("tg-hidden");
    badge.querySelector(".tg-site-badge__tooltip-score").innerHTML =
      `<span style="color:${color};font-weight:700">${score}</span> <span style="color:#6b7280">/ 1000</span>`;
    badge.querySelector(".tg-site-badge__tooltip-name").textContent =
      `${data.display_name || data.handle} — ${label}`;
  }

  function renderSiteBadgeError(badge) {
    const ring = badge.querySelector(".tg-site-badge__ring");
    const spinner = badge.querySelector(".tg-site-spinner");
    if (spinner) spinner.remove();
    ring.innerHTML = svgRing(28, 2.5, 0, 1000, "#d1d5db", "", "tg-badge__ring");
    // No tooltip — silently show empty ring (unscored site)
    badge.style.opacity = "0.35";
  }

  /* ══════════════════════════════════════════════════════════════════
     PROFILE OVERLAY — full overlay for known platform profile pages
     ══════════════════════════════════════════════════════════════════ */

  let currentRoot = null;

  function removeOverlay() {
    if (currentRoot) {
      currentRoot.remove();
      currentRoot = null;
    }
  }

  function createOverlay(profile) {
    removeOverlay();

    const dark = isDarkMode();
    const root = document.createElement("div");
    root.className = "tg-root";
    if (dark) root.classList.add("tg-dark");
    root.setAttribute("data-tg-handle", profile.handle);
    root.setAttribute("data-tg-platform", profile.platform);

    root.innerHTML = `
      <div class="tg-badge tg-badge--loading" role="status" aria-label="Tovbase trust score loading">
        <div class="tg-badge__ring">
          ${svgRing(36, 3, 0, 1000, "#e5e7eb", "", "tg-badge__ring")}
          <div class="tg-spinner"></div>
        </div>
        <div class="tg-badge__info">
          <span class="tg-badge__tier" style="color:#9ca3af">Loading...</span>
          <span class="tg-badge__brand">Tovbase</span>
        </div>
      </div>
      <div class="tg-modal">
        <div class="tg-modal__header">
          <div class="tg-modal__ring">
            ${svgRing(64, 4, 0, 1000, "#e5e7eb", "...", "tg-modal__ring")}
          </div>
          <div class="tg-modal__meta">
            <div class="tg-modal__handle">@${escapeHtml(profile.handle)}</div>
            <div class="tg-modal__platform">${escapeHtml(profile.platform)}</div>
            <span class="tg-modal__tier-pill tg-tier-bg--untrusted">Loading</span>
          </div>
        </div>
        <div class="tg-modal__divider"></div>
        <div class="tg-modal__scores" id="tg-scores"></div>
        <div class="tg-modal__divider"></div>
        <div class="tg-modal__confidence" id="tg-confidence"></div>
        <div class="tg-modal__footer">
          <a class="tg-modal__cta"
             href="https://tovbase.com/report/${encodeURIComponent(profile.handle)}?platform=${profile.platform}"
             target="_blank" rel="noopener">
            View Full Report
            <span class="tg-modal__cta-arrow">&rarr;</span>
          </a>
        </div>
      </div>
    `;

    let positioned = false;
    if (profile.anchorSelector) {
      const anchor = document.querySelector(profile.anchorSelector);
      if (anchor) {
        const wrapper = anchor.closest("div, section, header") || anchor.parentElement;
        if (wrapper) {
          const pos = getComputedStyle(wrapper).position;
          if (pos === "static") wrapper.style.position = "relative";
          wrapper.appendChild(root);
          root.classList.add("tg-root--anchored");
          positioned = true;
        }
      }
    }
    if (!positioned) {
      root.classList.add("tg-root--fixed");
      document.body.appendChild(root);
    }

    currentRoot = root;
    return root;
  }

  function renderScore(root, data) {
    const badge = root.querySelector(".tg-badge");
    badge.classList.remove("tg-badge--loading");

    const { color, label, stroke } = tierInfo(data.tier);
    const tc = tierClass(data.tier);
    const score = data.trust_score ?? 0;

    const badgeRing = badge.querySelector(".tg-badge__ring");
    const spinner = badge.querySelector(".tg-spinner");
    if (spinner) spinner.remove();
    badgeRing.innerHTML = svgRing(36, 3, score, 1000, stroke, score, "tg-badge__ring");

    const tierEl = badge.querySelector(".tg-badge__tier");
    tierEl.textContent = label;
    tierEl.style.color = color;
    badge.setAttribute("aria-label", `Trust score: ${score}, tier: ${label}`);

    const modalRing = root.querySelector(".tg-modal__ring");
    modalRing.innerHTML = svgRing(64, 4, score, 1000, stroke, score, "tg-modal__ring");

    const handleEl = root.querySelector(".tg-modal__handle");
    if (data.display_name) {
      handleEl.textContent = data.display_name;
    }

    const pill = root.querySelector(".tg-modal__tier-pill");
    pill.textContent = label;
    pill.className = `tg-modal__tier-pill tg-tier-bg--${tc}`;

    const scoresContainer = root.querySelector("#tg-scores");
    const breakdown = data.breakdown || {};
    let barsHtml = "";

    for (const [key, maxLabel] of Object.entries(SUB_SCORE_LABELS)) {
      const val = breakdown[key] ?? 0;
      const pct = Math.round((val / SUB_SCORE_MAX) * 100);
      barsHtml += `
        <div class="tg-score-row">
          <div class="tg-score-row__header">
            <span class="tg-score-row__label">${maxLabel}</span>
            <span class="tg-score-row__value">${Math.round(val)}/${SUB_SCORE_MAX}</span>
          </div>
          <div class="tg-score-row__track">
            <div class="tg-score-row__fill tg-fill--${tc}" style="width:${pct}%"></div>
          </div>
        </div>
      `;
    }
    scoresContainer.innerHTML = barsHtml;

    const confidence = data.confidence ?? 0;
    const confContainer = root.querySelector("#tg-confidence");
    const activeDots = Math.round(confidence * 5);
    let dotsHtml = `<span class="tg-modal__confidence-label">Confidence</span><div class="tg-modal__confidence-dots">`;
    for (let i = 0; i < 5; i++) {
      dotsHtml += `<div class="tg-modal__confidence-dot${i < activeDots ? " tg-modal__confidence-dot--active" : ""}"></div>`;
    }
    dotsHtml += `</div><span class="tg-modal__confidence-value">${Math.round(confidence * 100)}%</span>`;
    confContainer.innerHTML = dotsHtml;
  }

  function renderError(root, message) {
    const badge = root.querySelector(".tg-badge");
    badge.classList.remove("tg-badge--loading");

    const badgeRing = badge.querySelector(".tg-badge__ring");
    const spinner = badge.querySelector(".tg-spinner");
    if (spinner) spinner.remove();
    badgeRing.innerHTML = svgRing(36, 3, 0, 1000, "#9ca3af", "?", "tg-badge__ring");

    const tierEl = badge.querySelector(".tg-badge__tier");
    tierEl.textContent = "Unavailable";
    tierEl.style.color = "#9ca3af";

    const scoresContainer = root.querySelector("#tg-scores");
    scoresContainer.innerHTML = `<div class="tg-modal__error">${escapeHtml(message)}</div>`;

    const confContainer = root.querySelector("#tg-confidence");
    confContainer.innerHTML = "";
  }

  /* ══════════════════════════════════════════════════════════════════
     MAIN FLOW — profile pages get full overlay, other sites get logo badge
     ══════════════════════════════════════════════════════════════════ */

  /* ── Score fetch helper ────────────────────────────────────────── */

  function _fetchAndRenderScore(root, profile) {
    chrome.runtime.sendMessage(
      { type: "GET_SCORE", platform: profile.platform, handle: profile.handle },
      (response) => {
        if (chrome.runtime.lastError) {
          renderError(root, "Score unavailable — extension error.");
          return;
        }
        if (!response || response.error) {
          renderError(root, response?.error || "Score unavailable.");
          return;
        }
        renderScore(root, response);
      }
    );
  }

  /* ── Scrape throttling — only scrape once per handle per session ── */

  const _scrapedThisSession = new Set();

  function run() {
    // Priority 1: Known platform profile page → full overlay
    const profile = detectProfile();
    if (profile) {
      removeSiteBadge();

      if (currentRoot &&
          currentRoot.getAttribute("data-tg-handle") === profile.handle &&
          currentRoot.getAttribute("data-tg-platform") === profile.platform) {
        return;
      }

      const root = createOverlay(profile);

      const scrapeKey = `${profile.platform}:${profile.handle}`;
      const alreadyScraped = _scrapedThisSession.has(scrapeKey);

      if (!alreadyScraped) {
        _scrapedThisSession.add(scrapeKey);

        // Scrape profile data from the DOM (slight delay for page to settle)
        setTimeout(() => {
          const rawData = (typeof scrapeCurrentProfile === "function")
            ? scrapeCurrentProfile(profile.platform, profile.handle)
            : null;

          if (rawData) {
            // Send scraped data to background for ingestion
            chrome.runtime.sendMessage(
              { type: "INGEST_PROFILE", platform: profile.platform, handle: profile.handle, raw_data: rawData },
              (ingestResp) => {
                if (chrome.runtime.lastError) return;
                // After ingestion completes, fetch the fresh score
                _fetchAndRenderScore(root, profile);
              }
            );
          } else {
            // No scraper or scrape failed — just try to get existing score
            _fetchAndRenderScore(root, profile);
          }

          // Discover cross-platform links
          if (typeof discoverSocialLinks === "function") {
            const links = discoverSocialLinks(profile.platform, profile.handle);
            if (links && links.length > 0) {
              chrome.runtime.sendMessage(
                { type: "DISCOVER_PROFILES", source_platform: profile.platform, source_handle: profile.handle, links },
                () => { /* fire and forget */ }
              );
            }
          }
        }, 1500);
      } else {
        // Already scraped this session — just fetch existing score
        _fetchAndRenderScore(root, profile);
      }
      return;
    }

    // Priority 2: Any website → scrape for company signals, then show badge
    removeOverlay();

    const domain = extractDomainHandle();
    if (!domain || domain.length < 2) return;

    // Don't re-render for same domain
    if (currentSiteBadge && currentSiteBadge.getAttribute("data-tg-domain") === domain) return;

    // Wait for page to settle, then scrape + show badge
    setTimeout(() => {
      const logoInfo = findSiteLogo();
      if (!logoInfo) return;

      const badge = createSiteBadge(logoInfo, domain);

      // Scrape website for social links and company signals
      const websiteData = (typeof scrapeWebsite === "function") ? scrapeWebsite() : null;

      // Fetch company score (auto-creates stub if not found)
      function fetchCompanyBadge() {
        chrome.runtime.sendMessage(
          { type: "GET_COMPANY_SCORE", domain: domain },
          (response) => {
            if (chrome.runtime.lastError || !response || response.error) {
              renderSiteBadgeError(badge);
              return;
            }
            renderSiteBadgeScore(badge, response);
          }
        );
      }

      if (websiteData && websiteData.social_links && websiteData.social_links.length > 0) {
        // Send discovered social links to backend for company enrichment, then refresh badge
        chrome.runtime.sendMessage(
          { type: "INGEST_COMPANY", domain, data: websiteData },
          () => {
            // After ingestion, re-fetch the now-updated company score
            fetchCompanyBadge();
          }
        );
      } else {
        // No social links found — just fetch whatever score exists
        fetchCompanyBadge();
      }
    }, 800);
  }

  /* ── Message listener (popup queries current profile) ─────────── */

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg.type === "QUERY_PROFILE") {
      const profile = detectProfile();
      if (profile) {
        sendResponse(profile);
      } else {
        // Return domain info for site badge mode
        sendResponse({
          platform: "website",
          handle: extractDomainHandle(),
          entityType: "company",
        });
      }
    }
  });

  /* Run on load and on SPA navigation */
  run();

  let lastUrl = location.href;
  const observer = new MutationObserver(() => {
    if (location.href !== lastUrl) {
      lastUrl = location.href;
      run();
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });
  window.addEventListener("popstate", run);
})();
