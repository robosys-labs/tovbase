"""Interactive browser login setup for the Playwright scraping pool.

Usage:
    python scripts/setup_browsers.py                  # Setup all platforms
    python scripts/setup_browsers.py twitter linkedin  # Setup specific platforms

Opens a visible browser window for each platform so you can log in manually.
The session is saved as a persistent Chromium profile in data/browser_profiles/{platform}/.
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, ".")

from app.services.scraper import PLATFORM_LOGIN_URLS, PROFILE_DIR


async def setup_platform(platform: str, login_url: str):
    """Open a visible browser for manual login. Saves persistent profile."""
    from playwright.async_api import async_playwright

    profile_path = str(PROFILE_DIR / platform)
    os.makedirs(profile_path, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  Setting up: {platform}")
    print(f"  Profile dir: {profile_path}")
    print(f"  Login URL: {login_url}")
    print(f"{'='*60}")

    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            user_data_dir=profile_path,
            headless=False,
            viewport={"width": 1280, "height": 800},
        )
        page = await ctx.new_page()
        await page.goto(login_url)

        print(f"\n  Browser opened. Log into {platform} now.")
        print(f"  Press Enter here when you're done logging in...")
        await asyncio.get_event_loop().run_in_executor(None, input)

        await ctx.close()
        print(f"  Session saved for {platform}.")


async def main():
    platforms = sys.argv[1:] if len(sys.argv) > 1 else list(PLATFORM_LOGIN_URLS.keys())

    print("Tovbase Browser Profile Setup")
    print("=" * 60)
    print(f"Platforms to configure: {', '.join(platforms)}")
    print(f"Profile directory: {PROFILE_DIR}")
    print()

    for platform in platforms:
        url = PLATFORM_LOGIN_URLS.get(platform)
        if not url:
            print(f"  Unknown platform: {platform} (skipping)")
            continue
        await setup_platform(platform, url)

    print(f"\nAll done. Browser profiles saved to {PROFILE_DIR}/")
    print("You can now run the scraper pool in headless mode.")


if __name__ == "__main__":
    asyncio.run(main())
