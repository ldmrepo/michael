#!/usr/bin/env python3
"""
Scan Influencer Recent Tweets
Visits each influencer's X profile and collects recent tweets via Playwright.
"""

import sys
import json
import asyncio
from pathlib import Path

from config import (
    INFLUENCERS, X_PROFILE_URL, BROWSER_PROFILE_DIR,
    PAGE_LOAD_TIMEOUT, TWEET_LOAD_TIMEOUT,
    TWEET_ARTICLE_SELECTOR, TWEET_TEXT_SELECTOR,
    MAX_TWEETS_PER_PROFILE, MAX_SCROLL_ATTEMPTS,
)
from output_format import success, error, report
from db_utils import get_connection, insert_research
from browser_utils import launch_persistent_context


async def collect_tweets_for_user(page, username: str, max_tweets: int) -> list:
    """Visit a user's profile and collect recent tweet texts"""
    url = X_PROFILE_URL.format(username=username)
    tweets = []

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
        # Wait for tweets to load
        await page.wait_for_selector(TWEET_ARTICLE_SELECTOR, timeout=TWEET_LOAD_TIMEOUT)
    except Exception as e:
        print(f"⚠️ Failed to load @{username}: {e}", file=sys.stderr)
        return tweets

    # Scroll and collect
    for scroll in range(MAX_SCROLL_ATTEMPTS):
        tweet_elements = await page.query_selector_all(TWEET_TEXT_SELECTOR)
        for el in tweet_elements:
            text = await el.inner_text()
            text = text.strip()
            if text and text not in [t["text"] for t in tweets]:
                tweets.append({"text": text})
                if len(tweets) >= max_tweets:
                    break
        if len(tweets) >= max_tweets:
            break
        # Scroll down for more
        await page.evaluate("window.scrollBy(0, 1000)")
        await page.wait_for_timeout(2000)

    return tweets[:max_tweets]


async def run(usernames: list = None):
    """Main scan routine"""
    from patchright.async_api import async_playwright

    targets = INFLUENCERS
    if usernames:
        targets = [inf for inf in INFLUENCERS if inf["username"] in usernames]
        # Also allow arbitrary usernames not in the default list
        known = {inf["username"] for inf in targets}
        for u in usernames:
            if u not in known:
                targets.append({"username": u, "category": "custom"})

    if not targets:
        error("No influencers to scan")

    BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    accounts = []

    async with async_playwright() as p:
        browser = await launch_persistent_context(p, headless=True)

        page = await browser.new_page()

        for inf in targets:
            username = inf["username"]
            print(f"📡 Scanning @{username}...", file=sys.stderr)
            tweets = await collect_tweets_for_user(page, username, MAX_TWEETS_PER_PROFILE)
            account_data = {
                "username": username,
                "category": inf.get("category", "unknown"),
                "tweet_count": len(tweets),
                "tweets": tweets,
            }
            accounts.append(account_data)

        await browser.close()

    # Save to DB
    try:
        conn = get_connection()
        insert_research(conn, source="x_influencers", category="influencer_scan",
                        data_json=json.dumps(accounts, ensure_ascii=False))
        conn.close()
    except Exception as e:
        print(f"⚠️ DB save failed: {e}", file=sys.stderr)

    # Build report
    total_tweets = sum(a["tweet_count"] for a in accounts)
    lines = [f"Scanned {len(accounts)} accounts, {total_tweets} tweets total\n"]
    for a in accounts:
        lines.append(f"@{a['username']} ({a['category']}): {a['tweet_count']} tweets")
        for t in a["tweets"][:3]:
            preview = t["text"][:100] + ("..." if len(t["text"]) > 100 else "")
            lines.append(f"  - {preview}")
        lines.append("")

    report_text = "\n".join(lines)
    report(report_text, data={"accounts": accounts, "total_tweets": total_tweets})


def main():
    usernames = sys.argv[1:] if len(sys.argv) > 1 else None
    try:
        asyncio.run(run(usernames))
    except Exception as e:
        error(f"scan_influencers failed: {e}")


if __name__ == "__main__":
    main()
