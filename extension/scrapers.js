/**
 * Platform-specific DOM scrapers.
 *
 * Each scraper extracts visible profile data from the current page and returns
 * a raw_data dict matching the format expected by the corresponding backend
 * adapter in app/services/ingestion.py.
 *
 * Called by content.js after detectProfile() identifies the current page.
 */

/* eslint-disable no-unused-vars */
"use strict";

/* ── Utility helpers ───────────────────────────────────────────── */

function _txt(selector) {
  const el = document.querySelector(selector);
  return el ? el.textContent.trim() : "";
}

function _txtAll(selector) {
  return Array.from(document.querySelectorAll(selector))
    .map(el => el.textContent.trim())
    .filter(Boolean);
}

function _parseCount(text) {
  if (!text) return 0;
  const clean = text.replace(/,/g, "").trim();
  const m = clean.match(/([\d.]+)\s*([KkMmBb])?/);
  if (!m) return 0;
  let n = parseFloat(m[1]);
  const suffix = (m[2] || "").toUpperCase();
  if (suffix === "K") n *= 1000;
  else if (suffix === "M") n *= 1_000_000;
  else if (suffix === "B") n *= 1_000_000_000;
  return Math.round(n);
}

function _attr(selector, attr) {
  const el = document.querySelector(selector);
  return el ? el.getAttribute(attr) || "" : "";
}

/* ── LinkedIn ──────────────────────────────────────────────────── */

function scrapeLinkedIn(handle) {
  const profile = {};
  profile.vanityName = handle;

  // Name
  const nameEl = document.querySelector("h1.text-heading-xlarge, h1.top-card-layout__title, .pv-top-card .text-heading-xlarge, h1");
  if (nameEl) {
    const full = nameEl.textContent.trim();
    const parts = full.split(/\s+/);
    profile.firstName = parts[0] || "";
    profile.lastName = parts.slice(1).join(" ") || "";
  }

  // Headline (role/title)
  profile.headline = _txt(".text-body-medium.break-words, .top-card-layout__headline, [data-generated-suggestion-target='urn:li:fsu_profileActionDelegate'] + div");

  // Location
  profile.location = _txt(".text-body-small.inline.t-black--light.break-words, .top-card__subline-item, .pv-text-details__left-panel .text-body-small");

  // Follower count (separate from connections — "16,812 followers")
  const allSmallText = document.querySelectorAll(".text-body-small, .pv-top-card--list-bullet span, [class*='t-black--light']");
  for (const el of allSmallText) {
    const text = el.textContent.trim().toLowerCase();
    if (text.includes("follower")) {
      profile.followerCount = _parseCount(text);
      break;
    }
  }

  // Connection count ("500+ connections")
  for (const el of allSmallText) {
    const text = el.textContent.trim().toLowerCase();
    if (text.includes("connection")) {
      profile.connectionCount = _parseCount(text);
      break;
    }
  }

  // Use the higher of followers vs connections as the audience signal
  if (!profile.connectionCount && !profile.followerCount) {
    const connEl = document.querySelector("li.text-body-small span.t-bold");
    if (connEl) profile.connectionCount = _parseCount(connEl.textContent);
  }

  // Summary / About
  const aboutSection = document.querySelector("#about ~ .display-flex .inline-show-more-text, .pv-about__summary-text, [data-generated-suggestion-target] .inline-show-more-text, .pv-shared-text-with-see-more span[aria-hidden='true']");
  if (aboutSection) {
    profile.summary = aboutSection.textContent.trim().slice(0, 2000);
  }

  // Premium / Verified badge
  profile.premium = !!document.querySelector(".premium-icon, .pv-member-badge--premium, [data-control-name='premium_badge'], .pv-top-card-profile-picture__container .verified-icon, svg[data-test-icon='premium-bug-icon']");

  // Experience — extract company, role, and date ranges
  profile.experience = [];
  const expItems = document.querySelectorAll("#experience ~ .pvs-list__outer-container li.artdeco-list__item, .experience-section li, .pv-profile-section__list-item, #experience ~ div ul > li");
  for (const item of Array.from(expItems).slice(0, 8)) {
    const spans = item.querySelectorAll("span[aria-hidden='true'], .t-14 span, .visually-hidden");
    const texts = Array.from(spans).map(s => s.textContent.trim()).filter(Boolean);

    // Try to find company name, role, and date range from the text content
    let company = "";
    let role = "";
    let dateRange = "";
    for (const t of texts) {
      if (t.match(/\d{4}\s*[-–]\s*(\d{4}|Present)/i)) {
        dateRange = t;
      } else if (!role && t.length > 3 && t.length < 100) {
        role = t;
      }
    }
    // Fallback selectors for company
    const compEl = item.querySelector(".t-14.t-normal span, .pv-entity__secondary-title, .hoverable-link-text span");
    if (compEl) company = compEl.textContent.trim();

    if (company || role) {
      const entry = { companyName: company };
      if (dateRange) entry.dateRange = dateRange;
      if (role) entry.role = role;

      // Parse start year from date range
      const yearMatch = dateRange.match(/(\d{4})/);
      if (yearMatch) {
        entry.startDate = { year: parseInt(yearMatch[1], 10), month: 1 };
      }
      profile.experience.push(entry);
    }
  }

  // Education
  profile.education = [];
  const eduItems = document.querySelectorAll("#education ~ .pvs-list__outer-container li.artdeco-list__item, #education ~ div ul > li");
  for (const item of Array.from(eduItems).slice(0, 3)) {
    const school = item.querySelector(".t-bold span, .hoverable-link-text span")?.textContent?.trim() || "";
    if (school) {
      profile.education.push({ schoolName: school });
    }
  }

  // Endorsement count (from skills section)
  let endorsementCount = 0;
  const skillEls = document.querySelectorAll("#skills ~ .pvs-list__outer-container li, .pv-skill-category-entity__endorsement-count, #skills ~ div .pvs-list__item--line-separated");
  for (const el of skillEls) {
    const countEl = el.querySelector("span.t-bold, .pv-skill-category-entity__endorsement-count");
    if (countEl) {
      endorsementCount += _parseCount(countEl.textContent) || 0;
    }
  }
  if (endorsementCount > 0) {
    profile.endorsementCount = endorsementCount;
  }

  // Recent posts from activity feed (if visible on the profile page)
  const posts = [];
  const postEls = document.querySelectorAll(".feed-shared-update-v2 .feed-shared-text, .feed-shared-inline-show-more-text, .update-components-text span[dir='ltr']");
  for (const el of Array.from(postEls).slice(0, 10)) {
    const text = el.textContent.trim();
    if (text.length > 10) {
      posts.push({ text: text.slice(0, 1000) });
    }
  }

  // Also scrape post engagement signals (reactions) from visible activity
  const reactionEls = document.querySelectorAll(".social-details-social-counts__reactions-count, .feed-shared-social-action-bar span[aria-hidden='true']");
  let totalReactions = 0;
  for (const el of reactionEls) {
    totalReactions += _parseCount(el.textContent) || 0;
  }

  // Build a richer profile by merging follower + connection counts
  // LinkedIn API adapter uses connectionCount, but followers is often larger and more meaningful
  if (profile.followerCount && profile.followerCount > (profile.connectionCount || 0)) {
    profile.connectionCount = profile.followerCount;
  }

  return { profile, posts, _meta: { totalReactions, endorsementCount, followerCount: profile.followerCount || 0 } };
}

/* ── Twitter / X ───────────────────────────────────────────────── */

function scrapeTwitter(handle) {
  const profile = {};
  profile.username = handle;

  // Name
  profile.name = _txt('[data-testid="UserName"] > div > div > span, header [role="heading"] span');

  // Bio
  profile.description = _txt('[data-testid="UserDescription"]');

  // Location, URL, join date
  const metaLinks = document.querySelectorAll('[data-testid="UserProfileHeader_Items"] span, [data-testid="UserUrl"], [data-testid="UserJoinDate"]');
  for (const el of metaLinks) {
    const text = el.textContent.trim();
    if (text.startsWith("Joined ")) {
      profile.created_at_text = text;
    }
    if (el.querySelector("a")) {
      profile.url = el.querySelector("a")?.href || "";
    }
  }
  profile.location = _txt('[data-testid="UserLocation"]');

  // Follower/following counts
  const followLinks = document.querySelectorAll('a[href$="/followers"], a[href$="/following"], a[href$="/verified_followers"]');
  for (const link of followLinks) {
    const text = link.textContent.trim();
    const count = _parseCount(text);
    if (link.href.includes("/following")) {
      profile.following_count = count;
    } else if (link.href.includes("/followers") || link.href.includes("/verified_followers")) {
      profile.followers_count = (profile.followers_count || 0) + count;
    }
  }

  // Verification
  profile.verified = !!document.querySelector('[data-testid="icon-verified"], [aria-label="Verified account"]');

  // Recent tweets
  const tweets = [];
  const tweetEls = document.querySelectorAll('[data-testid="tweet"]');
  for (const el of Array.from(tweetEls).slice(0, 20)) {
    const textEl = el.querySelector('[data-testid="tweetText"]');
    const timeEl = el.querySelector("time");
    if (textEl) {
      tweets.push({
        text: textEl.textContent.trim().slice(0, 500),
        created_at: timeEl?.getAttribute("datetime") || "",
        like_count: _parseCount(el.querySelector('[data-testid="like"] span, [data-testid="unlike"] span')?.textContent || "0"),
        retweet_count: _parseCount(el.querySelector('[data-testid="retweet"] span, [data-testid="unretweet"] span')?.textContent || "0"),
        reply_count: _parseCount(el.querySelector('[data-testid="reply"] span')?.textContent || "0"),
      });
    }
  }

  return { profile, tweets };
}

/* ── GitHub ─────────────────────────────────────────────────────── */

function scrapeGitHub(handle) {
  const profile = {};
  profile.login = handle;

  profile.name = _txt(".vcard-fullname, .p-name, [itemprop='name']");
  profile.bio = _txt(".user-profile-bio, .p-note, [data-bio-text]");
  profile.company = _txt(".vcard-details [itemprop='worksFor'], .p-org");
  profile.location = _txt(".vcard-details [itemprop='homeLocation'], .p-label");
  profile.blog = _attr(".vcard-details a[rel='nofollow me']", "href");

  // Follower/following
  const followEls = document.querySelectorAll("a.Link--secondary span.text-bold, .js-profile-editable-area a span.text-bold");
  const followLinks = document.querySelectorAll("a.Link--secondary, .js-profile-editable-area a[href*='tab=followers'], .js-profile-editable-area a[href*='tab=following']");
  for (const link of followLinks) {
    const count = _parseCount(link.querySelector("span.text-bold, span")?.textContent || "0");
    if (link.href.includes("tab=followers")) {
      profile.followers = count;
    } else if (link.href.includes("tab=following")) {
      profile.following = count;
    }
  }

  // Repos (pinned)
  const repos = [];
  const repoEls = document.querySelectorAll(".pinned-item-list-item-content, .js-pinned-items-reorder-list li, [data-testid='pinned-item']");
  for (const el of repoEls) {
    const nameEl = el.querySelector(".repo, a span, [data-testid='pinned-item-name']");
    const descEl = el.querySelector(".pinned-item-desc, p");
    const langEl = el.querySelector("[itemprop='programmingLanguage'], span[class*='language']");
    const starEl = el.querySelector("a[href*='stargazers'] span, svg.octicon-star + span");

    repos.push({
      name: nameEl?.textContent?.trim() || "",
      description: descEl?.textContent?.trim() || "",
      language: langEl?.textContent?.trim() || "",
      stargazers_count: _parseCount(starEl?.textContent || "0"),
      forks_count: 0,
      topics: [],
    });
  }

  // Popular repos from repo tab (if visible)
  const repoListItems = document.querySelectorAll("#user-repositories-list li, [data-filterable-for='your-repos-filter'] li");
  for (const el of Array.from(repoListItems).slice(0, 10)) {
    const nameEl = el.querySelector("a[itemprop='name codeRepository'], h3 a");
    const descEl = el.querySelector("p[itemprop='description'], p");
    const langEl = el.querySelector("[itemprop='programmingLanguage']");
    const starEl = el.querySelector("a[href*='stargazers']");
    const forkEl = el.querySelector("a[href*='forks'], a[href*='network']");

    if (nameEl) {
      repos.push({
        name: nameEl.textContent.trim(),
        description: descEl?.textContent?.trim() || "",
        language: langEl?.textContent?.trim() || "",
        stargazers_count: _parseCount(starEl?.textContent || "0"),
        forks_count: _parseCount(forkEl?.textContent || "0"),
        topics: [],
      });
    }
  }

  return { profile, repos, events: [] };
}

/* ── Reddit ─────────────────────────────────────────────────────── */

function scrapeReddit(handle) {
  const profile = {};
  profile.name = handle;

  // Karma (new Reddit)
  const karmaEl = document.querySelector("#profile--id-card--highlight-tooltip--karma, [data-testid='karma'] span");
  if (karmaEl) {
    const total = _parseCount(karmaEl.textContent);
    profile.comment_karma = Math.round(total * 0.6);
    profile.link_karma = Math.round(total * 0.4);
  }

  // Account age
  const ageEl = document.querySelector("#profile--id-card--highlight-tooltip--cakeday, time, [data-testid='profile-cakeday']");
  if (ageEl) {
    const dateStr = ageEl.getAttribute("datetime") || ageEl.textContent;
    try {
      profile.created_utc = new Date(dateStr).getTime() / 1000;
    } catch { /* ignore */ }
  }

  // Recent posts and comments
  const comments = [];
  const posts = [];
  const postEls = document.querySelectorAll("shreddit-post, .Post, [data-testid='post-container']");
  for (const el of Array.from(postEls).slice(0, 15)) {
    const textEl = el.querySelector("[slot='text-body'], .RichTextJSON-root, [data-testid='post-text-content']");
    const text = textEl?.textContent?.trim() || "";
    const timeEl = el.querySelector("time, faceplate-timeago");
    const subredditEl = el.querySelector("a[href*='/r/']");
    const subreddit = subredditEl?.textContent?.replace("r/", "").trim() || "";

    if (text) {
      posts.push({
        selftext: text.slice(0, 500),
        subreddit,
        created_utc: timeEl?.getAttribute("datetime") ? new Date(timeEl.getAttribute("datetime")).getTime() / 1000 : 0,
      });
    }
  }

  return { profile, comments, posts };
}

/* ── Hacker News ───────────────────────────────────────────────── */

function scrapeHackerNews(handle) {
  const profile = {};
  profile.id = handle;

  // User page table rows
  const rows = document.querySelectorAll(".hnuser, table tr");
  for (const row of rows) {
    const cells = row.querySelectorAll("td");
    if (cells.length >= 2) {
      const label = cells[0]?.textContent?.trim()?.replace(":", "") || "";
      const value = cells[1]?.textContent?.trim() || "";
      if (label === "karma") profile.karma = parseInt(value, 10) || 0;
      if (label === "about") profile.about = value;
      if (label === "created") {
        try { profile.created = new Date(value).getTime() / 1000; } catch { /* ignore */ }
      }
    }
  }

  return { profile, items: [] };
}

/* ── Instagram ─────────────────────────────────────────────────── */

function scrapeInstagram(handle) {
  const profile = {};
  profile.username = handle;

  // Name
  profile.full_name = _txt("header section h1, header section h2, [data-testid='user-name']");

  // Stats (followers, following, posts)
  const statEls = document.querySelectorAll("header section ul li, header section [class*='_ac2a']");
  for (const el of statEls) {
    const text = el.textContent.trim().toLowerCase();
    const count = _parseCount(el.querySelector("span span, span")?.textContent || "0");
    if (text.includes("post")) profile.media_count = count;
    else if (text.includes("follower")) profile.follower_count = count;
    else if (text.includes("following")) profile.following_count = count;
  }

  // Bio
  const bioEl = document.querySelector("header section [class*='_ap3a'], header section span[class*='_aacl']");
  if (bioEl) profile.biography = bioEl.textContent.trim();

  // Verification
  profile.is_verified = !!document.querySelector('[aria-label="Verified"], [title="Verified"]');

  return { profile, posts: [] };
}

/* ── Polymarket ────────────────────────────────────────────────── */

function scrapePolymarket(handle) {
  const profile = {};
  profile.username = handle;

  profile.display_name = _txt("[class*='ProfileHeader'] h1, [class*='profile'] h1");

  // Volume and positions
  const statsEls = document.querySelectorAll("[class*='ProfileStats'] span, [class*='stat'] span");
  for (const el of statsEls) {
    const text = el.textContent.trim();
    if (text.includes("$")) {
      profile.volume = _parseCount(text.replace("$", ""));
    }
  }

  return { profile, positions: [], trades: [] };
}

/* ── Bluesky ───────────────────────────────────────────────────── */

function scrapeBluesky(handle) {
  const profile = {};
  profile.handle = handle;

  profile.displayName = _txt("[data-testid='profileHeaderDisplayName'], h1");
  profile.description = _txt("[data-testid='profileHeaderDescription']");

  // Follower/following
  const statLinks = document.querySelectorAll("a[href*='/followers'], a[href*='/follows']");
  for (const link of statLinks) {
    const count = _parseCount(link.textContent);
    if (link.href.includes("/followers")) {
      profile.followersCount = count;
    } else if (link.href.includes("/follows")) {
      profile.followsCount = count;
    }
  }

  // Recent posts
  const posts = [];
  const postEls = document.querySelectorAll("[data-testid='feedItem'], [data-testid='postThreadItem']");
  for (const el of Array.from(postEls).slice(0, 20)) {
    const textEl = el.querySelector("[data-testid='postText']");
    const timeEl = el.querySelector("time");
    if (textEl) {
      posts.push({
        text: textEl.textContent.trim().slice(0, 500),
        created_at: timeEl?.getAttribute("datetime") || "",
      });
    }
  }

  return { profile, posts };
}

/* ── YouTube ───────────────────────────────────────────────────── */

function scrapeYouTube(handle) {
  const channel = {};
  channel.custom_url = handle;

  channel.title = _txt("#channel-name yt-formatted-string, #channel-header ytd-channel-name yt-formatted-string");
  channel.description = _txt("#description-container .content, #about-description");

  // Subscriber count
  const subEl = document.querySelector("#subscriber-count, yt-formatted-string#subscriber-count");
  if (subEl) {
    channel.subscriber_count = _parseCount(subEl.textContent);
  }

  // Video count from tab
  const videoCountEl = document.querySelector("yt-formatted-string.ytd-c4-tabbed-header-renderer");
  if (videoCountEl && videoCountEl.textContent.toLowerCase().includes("video")) {
    channel.video_count = _parseCount(videoCountEl.textContent);
  }

  // Verification
  channel.is_verified = !!document.querySelector("[badge-style='BADGE_STYLE_TYPE_VERIFIED'], .badge-style-type-verified");

  // Recent videos
  const videos = [];
  const videoEls = document.querySelectorAll("ytd-rich-item-renderer, ytd-grid-video-renderer");
  for (const el of Array.from(videoEls).slice(0, 10)) {
    const titleEl = el.querySelector("#video-title, a#video-title-link");
    const viewEl = el.querySelector("#metadata-line span:first-child, .inline-metadata-item:first-child");
    videos.push({
      title: titleEl?.textContent?.trim() || "",
      view_count: _parseCount(viewEl?.textContent || "0"),
    });
  }

  return { channel, videos };
}

/* ── LinkedIn Company ──────────────────────────────────────────── */

function scrapeLinkedInCompany(handle) {
  const profile = {};
  profile.name = _txt(".org-top-card-summary__title, h1.top-card-layout__title");
  profile.industry = _txt(".org-top-card-summary-info-list__info-item:first-child");
  profile.description = _txt(".org-about-us-organization-description__text, .org-page-details__definition-text");

  const followersEl = document.querySelector(".org-top-card-summary-info-list__info-item");
  if (followersEl) {
    const text = followersEl.textContent;
    if (text.toLowerCase().includes("follower")) {
      profile.follower_count = _parseCount(text);
    }
  }

  return { profile, posts: [] };
}

/* ── 4chan (archive-based, limited) ─────────────────────────────── */

function scrape4chan() {
  // 4chan is anonymous — minimal scraping possible
  return null;
}

/* ── YCombinator ───────────────────────────────────────────────── */

function scrapeYCombinator() {
  // YC profiles are typically scraped server-side
  return null;
}

/* ── StackOverflow ─────────────────────────────────────────────── */

function scrapeStackOverflow(handle) {
  const profile = {};
  profile.user_id = handle; // numeric ID from URL

  profile.display_name = _txt(".fs-headline2, .profile-user--name, [class*='user-name']");
  profile.reputation = _parseCount(_txt("[title*='reputation'], .reputation, [class*='reputation']") || "0");
  profile.location = _txt("[class*='user-location'], .d-flex .fc-light");

  // About me
  const aboutEl = document.querySelector("#user-about-me, .profile-user--bio, [class*='bio']");
  if (aboutEl) profile.about_me = aboutEl.textContent.trim().slice(0, 2000);

  // Badge counts
  const badges = {};
  const goldEl = document.querySelector("[title*='gold'], .badge1 + .badgecount");
  const silverEl = document.querySelector("[title*='silver'], .badge2 + .badgecount");
  const bronzeEl = document.querySelector("[title*='bronze'], .badge3 + .badgecount");
  badges.gold = parseInt(goldEl?.textContent?.trim() || "0", 10);
  badges.silver = parseInt(silverEl?.textContent?.trim() || "0", 10);
  badges.bronze = parseInt(bronzeEl?.textContent?.trim() || "0", 10);
  profile.badge_counts = badges;

  // Stats
  const statEls = document.querySelectorAll(".user-stats .stat, [class*='stat'] .number, .fs-body3");
  profile.answer_count = 0;
  profile.question_count = 0;

  // Top tags
  const tags = [];
  const tagEls = document.querySelectorAll("#top-tags .post-tag, [class*='top-tags'] a");
  for (const el of Array.from(tagEls).slice(0, 20)) {
    tags.push({ name: el.textContent.trim(), count: 1 });
  }

  return { profile, answers: [], tags };
}

/* ── Quora ─────────────────────────────────────────────────────── */

function scrapeQuora(handle) {
  const profile = {};
  profile.username = handle;

  profile.name = _txt(".profile_name, [class*='ProfileName']");
  profile.bio = _txt("[class*='ProfileDescription'], [class*='bio']");

  // Follower counts
  const followerEl = document.querySelector("[class*='follower'] span, [class*='Follower']");
  if (followerEl) profile.follower_count = _parseCount(followerEl.textContent);

  // Recent answers
  const answers = [];
  const answerEls = document.querySelectorAll("[class*='Answer'] .content, .qu-truncatedText");
  for (const el of Array.from(answerEls).slice(0, 10)) {
    answers.push({ text: el.textContent.trim().slice(0, 1000) });
  }

  return { profile, answers };
}

/* ── Website / Company ──────────────────────────────────────────── */

/**
 * Scrape a generic website for company signals: social links, reviews, team info.
 * Called when the extension visits a non-platform website (e.g., venmail.io).
 */
function scrapeWebsite() {
  const data = {};
  const domain = window.location.hostname.replace(/^www\./, "");
  data.domain = domain;
  data.name = "";
  data.social_links = [];
  data.review_signals = {};

  // 1. Extract company name from title/meta
  const ogSiteName = document.querySelector('meta[property="og:site_name"]');
  const ogTitle = document.querySelector('meta[property="og:title"]');
  data.name = ogSiteName?.content || ogTitle?.content || document.title?.split(/[|–—-]/)[0]?.trim() || domain;

  // 2. Scan ENTIRE page for social media links (prioritize footer/header)
  const socialPatterns = [
    { platform: "twitter", regex: /(?:twitter|x)\.com\/([A-Za-z0-9_]{1,30})(?:[/?#]|$)/i },
    { platform: "linkedin", regex: /linkedin\.com\/(?:company|in)\/([A-Za-z0-9_-]+)/i },
    { platform: "github", regex: /github\.com\/([A-Za-z0-9_-]+)/i },
    { platform: "instagram", regex: /instagram\.com\/([A-Za-z0-9_.]+)/i },
    { platform: "youtube", regex: /youtube\.com\/(?:@|channel\/|c\/)([A-Za-z0-9_-]+)/i },
    { platform: "facebook", regex: /facebook\.com\/([A-Za-z0-9_.]+)/i },
    { platform: "tiktok", regex: /tiktok\.com\/@([A-Za-z0-9_.]+)/i },
  ];

  const blocked = new Set(["share", "sharer", "intent", "search", "explore", "login", "signup", "help", "about", "privacy", "terms"]);
  const seen = new Set();

  // Scan all links on the page
  for (const link of document.querySelectorAll("a[href]")) {
    const href = link.href || "";
    for (const { platform, regex } of socialPatterns) {
      const m = href.match(regex);
      if (m) {
        const handle = m[1];
        if (blocked.has(handle.toLowerCase())) continue;
        const key = `${platform}:${handle.toLowerCase()}`;
        if (seen.has(key)) continue;
        seen.add(key);
        data.social_links.push({ platform, handle, url: href });
      }
    }
  }

  // 3. Check for review/trust signals in the page
  const pageText = document.body?.innerText?.toLowerCase() || "";

  // Trustpilot badge
  if (document.querySelector("[data-trustpilot-uid], .trustpilot-widget, iframe[src*='trustpilot']") || pageText.includes("trustpilot")) {
    data.review_signals.trustpilot = true;
  }

  // Google reviews
  if (pageText.includes("google review") || document.querySelector("[data-google-review]")) {
    data.review_signals.google_reviews = true;
  }

  // Security/compliance badges
  if (pageText.includes("soc 2") || pageText.includes("soc2")) data.review_signals.soc2 = true;
  if (pageText.includes("gdpr")) data.review_signals.gdpr = true;
  if (pageText.includes("iso 27001")) data.review_signals.iso27001 = true;
  if (document.querySelector("img[src*='ssl'], img[alt*='secure'], img[src*='comodo'], img[src*='norton']")) {
    data.review_signals.ssl_badge = true;
  }

  // 4. Extract description from meta
  const metaDesc = document.querySelector('meta[name="description"], meta[property="og:description"]');
  if (metaDesc) data.description = metaDesc.content?.slice(0, 500);

  // 5. Team page detection
  const teamLinks = document.querySelectorAll("a[href*='team'], a[href*='about'], a[href*='people']");
  data.has_team_page = teamLinks.length > 0;

  return data;
}

/* ── Scraper registry ──────────────────────────────────────────── */

const SCRAPERS = {
  linkedin:         scrapeLinkedIn,
  twitter:          scrapeTwitter,
  github:           scrapeGitHub,
  reddit:           scrapeReddit,
  hackernews:       scrapeHackerNews,
  instagram:        scrapeInstagram,
  polymarket:       scrapePolymarket,
  bluesky:          scrapeBluesky,
  youtube:          scrapeYouTube,
  linkedin_company: scrapeLinkedInCompany,
  stackoverflow:    scrapeStackOverflow,
  stackexchange:    scrapeStackOverflow,  // Same DOM structure across all SE sites
  quora:            scrapeQuora,
};

/**
 * Run the platform-specific scraper for the current page.
 * @param {string} platform - Platform identifier from detectProfile()
 * @param {string} handle - Handle extracted from URL
 * @returns {object|null} Raw data dict matching backend adapter format, or null
 */
function scrapeCurrentProfile(platform, handle) {
  const scraper = SCRAPERS[platform];
  if (!scraper) return null;
  try {
    return scraper(handle);
  } catch (e) {
    console.debug("[Tovbase] Scrape error:", e);
    return null;
  }
}
