#!/usr/bin/env python3
"""Collect news from RSS feeds"""

import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import feedparser
from config import RSS_FEEDS
from db_utils import get_connection, insert_research
from output_format import success, error


def parse_feed(name: str, url: str, max_items: int = 10) -> list:
    """Parse an RSS feed and return articles"""
    feed = feedparser.parse(url)
    articles = []
    for entry in feed.entries[:max_items]:
        published = entry.get("published_parsed")
        ts = int(time.mktime(published)) if published else int(time.time())
        articles.append({
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "summary": entry.get("summary", "")[:500],
            "source": name,
            "published_at": ts,
        })
    return articles


def main():
    try:
        conn = get_connection()
        all_articles = []
        results = {}

        for name, url in RSS_FEEDS.items():
            try:
                articles = parse_feed(name, url)
                all_articles.extend(articles)
                results[name] = len(articles)
            except Exception as e:
                results[f"{name}_error"] = str(e)

        if all_articles:
            # Sort by time, take top 30
            all_articles.sort(key=lambda a: a["published_at"], reverse=True)
            all_articles = all_articles[:30]
            insert_research(conn, "rss", "news",
                            json.dumps(all_articles, ensure_ascii=False))

        conn.close()
        success(results, f"Collected {len(all_articles)} news articles")

    except Exception as e:
        error(str(e), "COLLECT_NEWS_ERROR")


if __name__ == "__main__":
    main()
