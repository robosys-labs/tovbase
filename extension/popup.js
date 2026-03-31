"use strict";

const TIERS = {
  excellent: { color: "#10b981", label: "Excellent" },
  good:      { color: "#22c55e", label: "Good" },
  fair:      { color: "#f59e0b", label: "Fair" },
  poor:      { color: "#ef4444", label: "Poor" },
  untrusted: { color: "#6b7280", label: "Untrusted" },
};

const SUB_SCORES = {
  existence:      "Existence",
  consistency:    "Consistency",
  engagement:     "Engagement",
  cross_platform: "Cross-Platform",
  maturity:       "Maturity",
};

const contentEl = document.getElementById("tg-content");
const actionsEl = document.getElementById("tg-actions");
const reportBtn = document.getElementById("tg-report-btn");

let currentProfile = null;

function tierInfo(tier) {
  return TIERS[tier] || TIERS.fair;
}

function tierClass(tier) {
  return TIERS[tier] ? tier : "fair";
}

function escapeHtml(str) {
  const el = document.createElement("span");
  el.textContent = str;
  return el.innerHTML;
}

function svgRing(size, sw, score, max, strokeColor) {
  const r = (size - sw) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.min(score / max, 1);
  const offset = c * (1 - pct);
  const cx = size / 2;
  return `
    <svg viewBox="0 0 ${size} ${size}" width="${size}" height="${size}">
      <circle class="tg-card__ring-track" cx="${cx}" cy="${cx}" r="${r}" />
      <circle class="tg-card__ring-fill" cx="${cx}" cy="${cx}" r="${r}"
        stroke="${strokeColor}" stroke-dasharray="${c}" stroke-dashoffset="${offset}" />
      <text class="tg-card__ring-score" x="${cx}" y="${cx}">${score}</text>
    </svg>
  `;
}

function renderEmpty() {
  actionsEl.style.display = "none";
  contentEl.innerHTML = `
    <div class="tg-empty">
      Navigate to a profile page on<br>
      LinkedIn, Twitter/X, GitHub,<br>
      Reddit, or Hacker News<br>
      to see a trust score.
    </div>
  `;
}

function renderScore(profile, data) {
  const { color, label } = tierInfo(data.tier);
  const tc = tierClass(data.tier);
  const score = data.trust_score ?? 0;
  const breakdown = data.breakdown || {};
  const confidence = data.confidence ?? 0;
  const activeDots = Math.round(confidence * 5);

  let barsHtml = "";
  for (const [key, lbl] of Object.entries(SUB_SCORES)) {
    const val = breakdown[key] ?? 0;
    const pct = Math.round((val / 200) * 100);
    barsHtml += `
      <div class="tg-bar-row">
        <div class="tg-bar-header">
          <span class="tg-bar-label">${lbl}</span>
          <span class="tg-bar-value">${Math.round(val)}/200</span>
        </div>
        <div class="tg-bar-track">
          <div class="tg-bar-fill fill-${tc}" style="width:${pct}%"></div>
        </div>
      </div>
    `;
  }

  let dotsHtml = "";
  for (let i = 0; i < 5; i++) {
    dotsHtml += `<div class="tg-conf__dot${i < activeDots ? " tg-conf__dot--on" : ""}"></div>`;
  }

  const displayName = data.display_name
    ? escapeHtml(data.display_name)
    : `@${escapeHtml(profile.handle)}`;

  contentEl.innerHTML = `
    <div class="tg-card">
      <div class="tg-card__top">
        <div class="tg-card__ring">
          ${svgRing(56, 4, score, 1000, color)}
        </div>
        <div class="tg-card__meta">
          <div class="tg-card__handle">${displayName}</div>
          <div class="tg-card__platform">${escapeHtml(profile.platform)}</div>
          <span class="tg-card__tier tier-${tc}">${label}</span>
        </div>
      </div>
      <div class="tg-bars">${barsHtml}</div>
      <div class="tg-conf">
        <span class="tg-conf__label">Confidence</span>
        <div class="tg-conf__dots">${dotsHtml}</div>
        <span class="tg-conf__pct">${Math.round(confidence * 100)}%</span>
      </div>
    </div>
  `;

  actionsEl.style.display = "flex";
  reportBtn.disabled = false;
}

function renderError(profile, message) {
  contentEl.innerHTML = `
    <div class="tg-card">
      <div class="tg-card__top">
        <div class="tg-card__ring">
          ${svgRing(56, 4, 0, 1000, "#6b7280")}
        </div>
        <div class="tg-card__meta">
          <div class="tg-card__handle">@${escapeHtml(profile.handle)}</div>
          <div class="tg-card__platform">${escapeHtml(profile.platform)}</div>
          <span class="tg-card__tier tier-untrusted">Unavailable</span>
        </div>
      </div>
      <div style="text-align:center;color:#6b7280;font-size:11px;padding:12px 0 0">
        ${escapeHtml(message)}
      </div>
    </div>
  `;
  actionsEl.style.display = "flex";
  reportBtn.disabled = false;
}

/* Ask content script for current profile */
function init() {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (!tabs[0]) return renderEmpty();

    chrome.tabs.sendMessage(tabs[0].id, { type: "QUERY_PROFILE" }, (resp) => {
      if (chrome.runtime.lastError || !resp || !resp.handle) {
        return renderEmpty();
      }
      currentProfile = resp;
      fetchAndRender(resp);
    });
  });
}

function fetchAndRender(profile) {
  chrome.runtime.sendMessage(
    { type: "GET_SCORE", platform: profile.platform, handle: profile.handle },
    (response) => {
      if (chrome.runtime.lastError || !response || response.error) {
        renderError(profile, response?.error || "Score unavailable");
        return;
      }
      renderScore(profile, response);
    }
  );
}

/* Full report button */
reportBtn.addEventListener("click", () => {
  if (!currentProfile) return;
  chrome.runtime.sendMessage({
    type: "OPEN_REPORT",
    platform: currentProfile.platform,
    handle: currentProfile.handle,
  });
});

init();
