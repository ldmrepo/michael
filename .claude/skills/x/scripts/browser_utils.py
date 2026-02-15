"""
Browser Utilities for X/Twitter Skill
Handles browser launching with anti-detection features
"""

from patchright.async_api import async_playwright, Playwright, BrowserContext

from config import BROWSER_PROFILE_DIR, BROWSER_ARGS, USER_AGENT


async def launch_persistent_context(
    playwright: Playwright,
    headless: bool = True,
    user_data_dir: str = str(BROWSER_PROFILE_DIR),
) -> BrowserContext:
    """Launch a persistent browser context with anti-detection features"""
    context = await playwright.chromium.launch_persistent_context(
        user_data_dir=user_data_dir,
        channel="chrome",
        headless=headless,
        no_viewport=True,
        ignore_default_args=["--enable-automation"],
        user_agent=USER_AGENT,
        args=BROWSER_ARGS,
    )
    return context
