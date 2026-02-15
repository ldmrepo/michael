#!/usr/bin/env python3
"""
Monitor Trending Keywords on X/Twitter
Searches for market-related keywords and performs simple sentiment analysis.
"""

import sys
import json
import asyncio
from pathlib import Path

from config import (
    MARKET_KEYWORDS, X_SEARCH_LIVE_URL,
    BROWSER_PROFILE_DIR,
    PAGE_LOAD_TIMEOUT, TWEET_LOAD_TIMEOUT,
    TWEET_ARTICLE_SELECTOR, TWEET_TEXT_SELECTOR,
    POSITIVE_KEYWORDS, NEGATIVE_KEYWORDS,
    MAX_TWEETS_PER_KEYWORD, MAX_SCROLL_ATTEMPTS,
)
from output_format import success, error, report
from db_utils import get_connection, insert_research
from browser_utils import launch_persistent_context


def classify_sentiment(text: str) -> str:
    """Simple keyword-based sentiment classification"""
    text_lower = text.lower()
    pos_count = sum(1 for kw in POSITIVE_KEYWORDS if kw in text_lower)
    neg_count = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text_lower)

    if pos_count > neg_count:
        return "positive"
    elif neg_count > pos_count:
        return "negative"
    return "neutral"


async def search_keyword(page, keyword: str, max_tweets: int) -> dict:
    """Search X for a keyword and collect tweets"""
    url = X_SEARCH_LIVE_URL.format(query=keyword)
    tweets = []

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
        await page.wait_for_selector(TWEET_ARTICLE_SELECTOR, timeout=TWEET_LOAD_TIMEOUT)
    except Exception as e:
        print(f"⚠️ Search failed for '{keyword}': {e}", file=sys.stderr)
        return {
            "keyword": keyword,
            "tweet_count": 0,
            "sentiment": "unknown",
            "sentiment_breakdown": {"positive": 0, "negative": 0, "neutral": 0},
            "sample_tweets": [],
        }

    for scroll in range(MAX_SCROLL_ATTEMPTS):
        tweet_elements = await page.query_selector_all(TWEET_TEXT_SELECTOR)
        for el in tweet_elements:
            text = await el.inner_text()
            text = text.strip()
            if text and text not in [t["text"] for t in tweets]:
                sentiment = classify_sentiment(text)
                tweets.append({"text": text, "sentiment": sentiment})
                if len(tweets) >= max_tweets:
                    break
        if len(tweets) >= max_tweets:
            break
        await page.evaluate("window.scrollBy(0, 1000)")
        await page.wait_for_timeout(2000)

    tweets = tweets[:max_tweets]

    # Aggregate sentiment
    breakdown = {"positive": 0, "negative": 0, "neutral": 0}
    for t in tweets:
        breakdown[t["sentiment"]] += 1

    if breakdown["positive"] > breakdown["negative"]:
        overall = "positive"
    elif breakdown["negative"] > breakdown["positive"]:
        overall = "negative"
    else:
        overall = "neutral"

    return {
        "keyword": keyword,
        "tweet_count": len(tweets),
        "sentiment": overall,
        "sentiment_breakdown": breakdown,
        "sample_tweets": [t["text"][:200] for t in tweets[:5]],
    }


async def run(keywords: list = None):
    """Main monitoring routine"""
    from patchright.async_api import async_playwright

    targets = keywords if keywords else MARKET_KEYWORDS

    BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    results = []

    async with async_playwright() as p:
        browser = await launch_persistent_context(p, headless=True)

        page = await browser.new_page()

        for keyword in targets:
            print(f"🔍 Searching '{keyword}'...", file=sys.stderr)
            result = await search_keyword(page, keyword, MAX_TWEETS_PER_KEYWORD)
            results.append(result)

        await browser.close()

    # Save to DB
    try:
        conn = get_connection()
        insert_research(conn, source="x_trending", category="keyword_monitor",
                        data_json=json.dumps(results, ensure_ascii=False))
        conn.close()
    except Exception as e:
        print(f"⚠️ DB save failed: {e}", file=sys.stderr)

    # Build report
    total_tweets = sum(r["tweet_count"] for r in results)
    lines = [f"Monitored {len(results)} keywords, {total_tweets} tweets total\n"]
    for r in results:
        s = r["sentiment_breakdown"]
        lines.append(
            f"'{r['keyword']}': {r['tweet_count']} tweets, "
            f"sentiment={r['sentiment']} "
            f"(+{s['positive']}/-{s['negative']}/~{s['neutral']})"
        )
        if r["sample_tweets"]:
            preview = r["sample_tweets"][0][:100] + ("..." if len(r["sample_tweets"][0]) > 100 else "")
            lines.append(f"  sample: {preview}")
        lines.append("")

    report_text = "\n".join(lines)
    report(report_text, data={"keywords": results, "total_tweets": total_tweets})


def main():
    keywords = sys.argv[1:] if len(sys.argv) > 1 else None
    try:
        asyncio.run(run(keywords))
    except Exception as e:
        error(f"monitor_trending failed: {e}")


if __name__ == "__main__":
    main()
