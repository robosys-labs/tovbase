# Tovbase Chrome Extension — Install Guide

The Tovbase extension overlays a live trust score on every profile you visit across LinkedIn, X/Twitter, GitHub, Reddit, Hacker News, Instagram, Bluesky, YouTube, Stack Overflow, Quora, Polymarket, and more. It also surfaces a small badge near the site logo of any company website so you can spot risky vendors at a glance.

Until the extension lands in the Chrome Web Store (under review), it installs as an **unpacked** extension. Takes 60 seconds.

## Download

Latest signed build (v0.4.0):

- **https://tovbase.com/v1/download/extension/tovbase-extension-latest.zip** — always the newest release
- **https://tovbase.com/v1/download/extension/tovbase-extension-v0.4.0.zip** — pinned version

Both files are byte-identical to what users would receive through the Chrome Web Store when that channel opens.

## Install (Chrome / Brave / Edge / Arc)

1. **Download** [`tovbase-extension-latest.zip`](https://tovbase.com/v1/download/extension/tovbase-extension-latest.zip).
2. **Unzip** it into a folder you'll keep on disk (e.g. `~/tovbase-ext/`). The folder needs to stick around — Chrome loads files from it every time the browser starts.
3. In Chrome, open `chrome://extensions/` (or click ☰ → **More tools** → **Extensions**).
4. Toggle **Developer mode** ON (top-right corner).
5. Click **Load unpacked**.
6. Select the folder you unzipped to in step 2.

The Tovbase icon appears in your toolbar. Pin it (click the 🧩 puzzle icon → pin Tovbase) for one-click access to scores.

## Install (Firefox)

Firefox uses a different extension format (`.xpi`). The Tovbase WebExtensions port lands in v0.5 — until then, Firefox isn't supported.

## Verify it's working

1. After install, visit a profile that has a Tovbase score, e.g. **https://github.com/torvalds**.
2. Wait 1–2 seconds. A circular badge should appear near the profile name showing the trust score (0–1000) and tier (Excellent / Good / Fair / Poor / Untrusted).
3. Click the badge to expand. The toolbar icon also shows the score for the active tab.

If you don't see a badge, open `chrome://extensions/`, find Tovbase, click **service worker** to view background logs, and check for API errors.

## Switching API endpoint

By default the extension points at the live `https://tovbase.com/v1` API. To run against your own backend:

1. Right-click the Tovbase toolbar icon → **Options**.
2. Pick **Dev** (`http://localhost:8001/v1`), **Production**, or **Custom**.
3. For Custom: enter a base URL like `https://your-server.example.com/v1`.
4. Click **Save**. The new endpoint takes effect immediately — no extension reload needed.

## Privacy + permissions

The extension requests these permissions:

| Permission | Why |
|------------|-----|
| `activeTab` | Read the profile URL / handle on the page you're viewing |
| `storage` | Cache scores locally (1-hour TTL) + remember your settings |
| `<all_urls>` host access | Inject the score badge on any social profile or company site |

We **do not** read content outside profile pages. The content script's behavior:
- Detects platform + handle from the URL only on known profile-shaped routes (`linkedin.com/in/X`, `github.com/X`, `x.com/X`, etc.).
- Sends only `{platform, handle}` to the API — never the page's HTML, never your other tabs.
- All caches and settings live in your local browser storage; nothing is shipped to a third party.

The extension is open source. Source: [github.com/cloudspacetechs/tovbase/tree/main/extension](https://github.com/cloudspacetechs/tovbase/tree/main/extension).

## Reporting an issue

If a score looks wrong, click the badge → **View report**. The report page has a "Dispute this score" link that opens an issue with the canonical-id and current breakdown pre-filled.

Bugs / feature requests: [github.com/cloudspacetechs/tovbase/issues](https://github.com/cloudspacetechs/tovbase/issues).

## Updating

Until the Chrome Web Store version ships, updates are manual:

1. Download the latest zip.
2. Unzip *over* your existing folder (or into a new folder and re-pick it in `chrome://extensions/`).
3. Click the refresh icon next to Tovbase on `chrome://extensions/` to reload the new code.

## Uninstall

`chrome://extensions/` → find Tovbase → click **Remove**. Cached scores in local storage are cleared with it.
