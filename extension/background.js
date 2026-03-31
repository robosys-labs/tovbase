"use strict";

const SERVERS = {
  dev:        "http://localhost:8001/v1",
  production: "https://api.tovbase.com/v1",
};

const CACHE_TTL_MS = 60 * 60 * 1000; // 1 hour

/* ── Resolve API base from settings ──────────────────────────── */

async function getApiBase() {
  return new Promise((resolve) => {
    chrome.storage.sync.get(["tg_server", "tg_custom_url"], (result) => {
      const server = result.tg_server || "dev";
      if (server === "custom" && result.tg_custom_url) {
        resolve(result.tg_custom_url.replace(/\/+$/, ""));
      } else {
        resolve(SERVERS[server] || SERVERS.dev);
      }
    });
  });
}

/* ── Cache helpers (chrome.storage.local) ─────────────────────── */

function cacheKey(prefix, handle) {
  return `tg_${prefix}_${handle.toLowerCase()}`;
}

async function getCached(prefix, handle) {
  const key = cacheKey(prefix, handle);
  return new Promise((resolve) => {
    chrome.storage.local.get(key, (result) => {
      const entry = result[key];
      if (!entry) return resolve(null);
      if (Date.now() - entry.ts > CACHE_TTL_MS) {
        chrome.storage.local.remove(key);
        return resolve(null);
      }
      resolve(entry.data);
    });
  });
}

async function setCache(prefix, handle, data) {
  const key = cacheKey(prefix, handle);
  return new Promise((resolve) => {
    chrome.storage.local.set({ [key]: { data, ts: Date.now() } }, resolve);
  });
}

/* ── API fetch ────────────────────────────────────────────────── */

async function ingestProfile(platform, rawData) {
  const base = await getApiBase();
  const url = `${base}/ingest/${encodeURIComponent(platform)}`;
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Accept": "application/json" },
    body: JSON.stringify(rawData),
  });
  if (!resp.ok) throw new Error(`Ingest API ${resp.status}`);
  return resp.json();
}

async function enqueueScrape(platform, handle, profileUrl) {
  const base = await getApiBase();
  const url = `${base}/scrape/enqueue`;
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Accept": "application/json" },
    body: JSON.stringify({ platform, handle, url: profileUrl }),
  });
  if (!resp.ok) throw new Error(`Scrape enqueue API ${resp.status}`);
  return resp.json();
}

async function enrichProfile(platform, handle) {
  const base = await getApiBase();
  const url = `${base}/enrich/${encodeURIComponent(platform)}/${encodeURIComponent(handle)}`;
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Accept": "application/json" },
  });
  if (!resp.ok) throw new Error(`Enrich API ${resp.status}`);
  return resp.json();
}

async function fetchScore(platform, handle) {
  const base = await getApiBase();
  const url = `${base}/score/${encodeURIComponent(platform)}/${encodeURIComponent(handle)}`;
  const resp = await fetch(url, {
    method: "GET",
    headers: { "Accept": "application/json" },
  });
  if (!resp.ok) throw new Error(`API ${resp.status}`);
  return resp.json();
}

async function fetchCompanyScore(domain) {
  const base = await getApiBase();
  // Try company score endpoint first
  const url = `${base}/company/score/linkedin/${encodeURIComponent(domain)}`;
  const resp = await fetch(url, {
    method: "GET",
    headers: { "Accept": "application/json" },
  });
  if (!resp.ok) throw new Error(`API ${resp.status}`);
  return resp.json();
}

/* ── Message handler ──────────────────────────────────────────── */

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === "GET_SCORE") {
    handleGetScore(msg.platform, msg.handle).then(sendResponse);
    return true;
  }

  if (msg.type === "GET_COMPANY_SCORE") {
    handleGetCompanyScore(msg.domain).then(sendResponse);
    return true;
  }

  if (msg.type === "OPEN_REPORT") {
    const url = `https://tovbase.com/report/${encodeURIComponent(msg.handle)}?platform=${encodeURIComponent(msg.platform)}`;
    chrome.tabs.create({ url });
    return false;
  }

  if (msg.type === "INGEST_PROFILE") {
    handleIngestProfile(msg.platform, msg.handle, msg.raw_data).then(sendResponse);
    return true;
  }

  if (msg.type === "DISCOVER_PROFILES") {
    handleDiscoverProfiles(msg.links, msg.source_platform, msg.source_handle).then(sendResponse);
    return true;
  }

  if (msg.type === "INGEST_COMPANY") {
    handleIngestCompany(msg.domain, msg.data).then(sendResponse);
    return true;
  }

  if (msg.type === "GET_CURRENT_PROFILE") {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (!tabs[0]) return sendResponse(null);
      chrome.tabs.sendMessage(tabs[0].id, { type: "QUERY_PROFILE" }, (resp) => {
        sendResponse(resp || null);
      });
    });
    return true;
  }
});

async function handleGetScore(platform, handle) {
  try {
    const cached = await getCached("score", `${platform}_${handle}`);
    if (cached) return cached;

    const data = await fetchScore(platform, handle);
    await setCache("score", `${platform}_${handle}`, data);
    return data;
  } catch {
    return { error: "Score unavailable" };
  }
}

async function handleGetCompanyScore(domain) {
  try {
    const cached = await getCached("company", domain);
    if (cached) return cached;

    const data = await fetchCompanyScore(domain);
    await setCache("company", domain, data);
    return data;
  } catch {
    return { error: "Company score unavailable" };
  }
}

async function handleIngestProfile(platform, handle, rawData) {
  try {
    const result = await ingestProfile(platform, rawData);
    // Invalidate the score cache so next GET_SCORE fetches fresh
    const key = cacheKey("score", `${platform}_${handle}`);
    await new Promise((resolve) => chrome.storage.local.remove(key, resolve));

    // Trigger cross-platform enrichment (discovers profiles on GitHub, HN, Reddit, etc.)
    try {
      const enrichResult = await enrichProfile(platform, handle);
      result.enrichment = enrichResult;
    } catch {
      // Enrichment is best-effort — don't fail the ingest
    }

    return result;
  } catch (e) {
    return { error: "Ingestion failed: " + e.message };
  }
}

async function handleDiscoverProfiles(links, sourcePlatform, sourceHandle) {
  if (!links || links.length === 0) return { discovered: 0 };

  let enqueued = 0;
  for (const link of links) {
    try {
      // Check if we already have a score for this profile
      const existing = await getCached("score", `${link.platform}_${link.handle}`);
      if (existing) continue;

      // Try to fetch score — if 404, enqueue for scraping
      try {
        const score = await fetchScore(link.platform, link.handle);
        await setCache("score", `${link.platform}_${link.handle}`, score);
      } catch {
        // Profile doesn't exist yet — enqueue for backend scraping
        try {
          await enqueueScrape(link.platform, link.handle, link.url);
          enqueued++;
        } catch { /* scrape endpoint may not be available yet */ }
      }
    } catch { /* skip this link */ }
  }

  return { discovered: links.length, enqueued };
}

async function handleIngestCompany(domain, websiteData) {
  try {
    const base = await getApiBase();

    // Submit company observation with website-scraped social links
    const payload = {
      handle: domain,
      platform: "website",
      display_name: websiteData.name || domain,
      domain: domain,
      description: websiteData.description || "",
      platform_accounts: {},
      raw_payload: websiteData,
    };

    // Map social links to platform accounts
    for (const link of (websiteData.social_links || [])) {
      payload.platform_accounts[link.platform] = link.handle;
    }

    const resp = await fetch(`${base}/company/observe`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!resp.ok) return { error: "Company ingest failed" };

    const result = await resp.json();

    // Invalidate company score cache
    const key = cacheKey("company", domain);
    await new Promise((resolve) => chrome.storage.local.remove(key, resolve));

    return result;
  } catch (e) {
    return { error: "Company ingest error: " + e.message };
  }
}
