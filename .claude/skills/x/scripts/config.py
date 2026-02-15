"""
Configuration for X/Twitter Skill
Centralizes constants, selectors, URLs, and paths
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
_project_root = Path(__file__).parent.parent.parent.parent.parent
load_dotenv(_project_root / ".env")

# === Paths ===
SKILL_DIR = Path(__file__).parent.parent
DATA_DIR = SKILL_DIR / "data"
BROWSER_STATE_DIR = DATA_DIR / "browser_state"
BROWSER_PROFILE_DIR = BROWSER_STATE_DIR / "browser_profile"

# Project data directory (SQLite DB location)
PROJECT_DATA_DIR = _project_root / "data"
DB_PATH = PROJECT_DATA_DIR / "memory.db"

# === X/Twitter URLs ===
X_HOME_URL = "https://x.com/home"
X_EXPLORE_URL = "https://x.com/explore"
X_PROFILE_URL = "https://x.com/{username}"
X_SEARCH_URL = "https://x.com/search?q={query}&src=typed_query"
X_SEARCH_LIVE_URL = "https://x.com/search?q={query}&f=live"

# === Browser Selectors (data-testid) ===
TWEET_TEXTAREA_SELECTOR = '[data-testid="tweetTextarea_0"]'
TWEET_POST_BUTTON = '[data-testid="tweetButtonInline"]'
FOLLOW_BUTTON_SELECTOR = '[data-testid$="-follow"]'
TWEET_ARTICLE_SELECTOR = '[data-testid="tweet"]'
TWEET_TEXT_SELECTOR = '[data-testid="tweetText"]'
USER_NAME_SELECTOR = '[data-testid="User-Name"]'

# === Browser Configuration ===
BROWSER_ARGS = [
    '--disable-blink-features=AutomationControlled',
    '--disable-dev-shm-usage',
    '--no-sandbox',
    '--no-first-run',
    '--no-default-browser-check',
]

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

# === Timeouts ===
PAGE_LOAD_TIMEOUT = 30000      # 30s
TWEET_LOAD_TIMEOUT = 15000     # 15s
SCROLL_PAUSE_MS = 2000         # 2s between scrolls

# === Influencers (from SKILL.md) ===
INFLUENCERS = [
    {"username": "karpathy", "category": "AI/Deep Learning"},
    {"username": "rauchg", "category": "Vercel/Next.js"},
    {"username": "youyuxi", "category": "Vue.js/Vite"},
    {"username": "dan_abramov", "category": "React"},
    {"username": "addyosmani", "category": "Chrome Engineering"},
    {"username": "levelsio", "category": "Indie Hacker"},
    {"username": "ThePrimeagen", "category": "Dev Content"},
    {"username": "kentcdodds", "category": "React/Testing"},
    {"username": "swyx", "category": "DX/AI"},
    {"username": "t3dotgg", "category": "TypeScript Fullstack"},
    {"username": "elonmusk", "category": "Tech/X"},
]

# === Market Keywords ===
MARKET_KEYWORDS = [
    "bitcoin", "BTC", "ethereum", "ETH", "crypto",
    "AI", "artificial intelligence", "LLM",
    "fed rate", "interest rate",
    "solana", "SOL",
]

# === Sentiment Keywords (simple keyword matching) ===
POSITIVE_KEYWORDS = [
    "bullish", "moon", "surge", "rally", "breakout", "pump",
    "all-time high", "ATH", "adoption", "partnership", "launch",
    "upgrade", "milestone", "record", "growth", "gain",
]

NEGATIVE_KEYWORDS = [
    "bearish", "crash", "dump", "plunge", "sell-off", "selloff",
    "hack", "exploit", "rug", "scam", "fraud", "ban",
    "regulation", "lawsuit", "sec", "fine", "collapse",
]

# === Limits ===
MAX_TWEETS_PER_PROFILE = 10     # tweets to collect per influencer
MAX_TWEETS_PER_KEYWORD = 15     # tweets per keyword search
MAX_SCROLL_ATTEMPTS = 3         # scrolls per page
