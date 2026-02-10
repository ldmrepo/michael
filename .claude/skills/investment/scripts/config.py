"""
Configuration for Investment Skill
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
STATE_FILE = BROWSER_STATE_DIR / "state.json"
AUTH_INFO_FILE = DATA_DIR / "auth_info.json"

# Project data directory (SQLite DB location)
PROJECT_DATA_DIR = _project_root / "data"
DB_PATH = PROJECT_DATA_DIR / "memory.db"

# === Binance API ===
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")

BINANCE_SPOT_BASE = "https://api.binance.com"
BINANCE_FUTURES_BASE = "https://fapi.binance.com"

# === External APIs ===
COINGECKO_BASE = "https://api.coingecko.com/api/v3"
FEAR_GREED_URL = "https://api.alternative.me/fng/"
FRED_API_KEY = os.getenv("FRED_API_KEY", "")
FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

# === Browser URLs ===
BINANCE_LOGIN_URL = "https://accounts.binance.com/en/login"
BINANCE_SMART_MONEY_URL = "https://www.binance.com/en/copy-trading/lead-details"
FARSIDE_ETF_URL = "https://farside.co.uk/bitcoin-etf-flow-all-data/"
FARSIDE_ETH_ETF_URL = "https://farside.co.uk/ethereum-etf-flow-all-data/"
DERIBIT_OPTIONS_URL = "https://metrics.deribit.com/options"
CME_FEDWATCH_URL = "https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html"

# === Browser Selectors ===
BINANCE_AUTH_CHECK_SELECTOR = '[data-testid="user-center-icon"]'
BINANCE_SMART_MONEY_TABLE = ".smart-money-table, .copy-trading-table"
FARSIDE_ETF_TABLE = "table.etf"
DERIBIT_IV_SELECTOR = ".iv-chart, .options-data"

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
LOGIN_TIMEOUT_MINUTES = 10
PAGE_LOAD_TIMEOUT = 30000
API_TIMEOUT_SECONDS = 30

# === Investment Limits ===
MAX_ORDER_USD = float(os.getenv("INVESTMENT_MAX_ORDER_USD", "10000"))
PROPOSAL_EXPIRY_MIN = int(os.getenv("INVESTMENT_PROPOSAL_EXPIRY_MIN", "30"))

# === RSS Feeds ===
RSS_FEEDS = {
    "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "cointelegraph": "https://cointelegraph.com/rss",
    "theblock": "https://www.theblock.co/rss.xml",
}

# === FRED Series IDs ===
FRED_SERIES = {
    "DXY": "DTWEXBGS",      # Trade Weighted US Dollar Index
    "FED_RATE": "FEDFUNDS",  # Federal Funds Rate
    "US10Y": "DGS10",        # 10-Year Treasury
    "US02Y": "DGS2",         # 2-Year Treasury
    "M2": "M2SL",            # M2 Money Supply
    "CPI": "CPIAUCSL",       # CPI
}

# === DefiLlama ===
DEFILLAMA_TVL_URL = "https://api.llama.fi/v2/protocols"
DEFILLAMA_CHAINS_URL = "https://api.llama.fi/v2/chains"

# === Tracked Symbols (default) ===
DEFAULT_TRACKED_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
