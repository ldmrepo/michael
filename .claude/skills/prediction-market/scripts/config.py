"""
Configuration for Prediction Market skill
Loads environment variables and defines constants
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Project root → .env loading
_project_root = Path(__file__).parent.parent.parent.parent.parent
load_dotenv(_project_root / ".env")

# Skill paths
SKILL_DIR = Path(__file__).parent.parent
DATA_DIR = SKILL_DIR / "data"
SCRIPTS_DIR = SKILL_DIR / "scripts"

# Shared DB (project-level memory.db)
PROJECT_DATA_DIR = _project_root / "data"
DB_PATH = PROJECT_DATA_DIR / "memory.db"

# === Polymarket Credentials ===
POLYMARKET_PRIVATE_KEY = os.getenv("POLYMARKET_PRIVATE_KEY", "")
POLYMARKET_API_KEY = os.getenv("POLYMARKET_API_KEY", "")
POLYMARKET_API_SECRET = os.getenv("POLYMARKET_API_SECRET", "")
POLYMARKET_PASSPHRASE = os.getenv("POLYMARKET_PASSPHRASE", "")
POLYMARKET_PROXY_WALLET = os.getenv("POLYMARKET_PROXY_WALLET", "")

# === API Endpoints ===
GAMMA_API_BASE = "https://gamma-api.polymarket.com"
CLOB_API_BASE = "https://clob.polymarket.com"
DATA_API_BASE = "https://data-api.polymarket.com"
CLOB_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/"

# === Polygon Chain ===
POLYGON_CHAIN_ID = 137
POLYGON_RPC_URL = os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com")
POLYGON_RPC_FALLBACKS = [
    "https://1rpc.io/matic",
    "https://polygon-bor-rpc.publicnode.com",
    "https://polygon.llamarpc.com",
]
# Legacy alias
POLYGON_RPC_FALLBACK = POLYGON_RPC_FALLBACKS[0]

# USDC.e (bridged, 6 decimals) — Polymarket's collateral token
USDC_E_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
# Native USDC (Circle, 6 decimals) — NOT used by Polymarket CLOB
NATIVE_USDC_ADDRESS = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
# Legacy alias (wallet_utils uses this for Native USDC operations)
USDC_CONTRACT_ADDRESS = NATIVE_USDC_ADDRESS
USDC_DECIMALS = 6

# === Polymarket Contracts ===
PROXY_FACTORY_ADDRESS = "0xaB45c5A4B0c941a2F231C04C3f49182e1A254052"
CTF_EXCHANGE_ADDRESS = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
NEG_RISK_CTF_EXCHANGE_ADDRESS = "0xC5d563A36AE78145C45a50134d48A1215220f80a"
NEG_RISK_ADAPTER_ADDRESS = "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"
CONDITIONAL_TOKENS_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"

# Minimal ERC20 ABI for balance/transfer/approve operations
ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}],
     "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}],
     "type": "function"},
    {"constant": True, "inputs": [], "name": "decimals",
     "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
    {"constant": False,
     "inputs": [{"name": "_to", "type": "address"}, {"name": "_value", "type": "uint256"}],
     "name": "transfer", "outputs": [{"name": "", "type": "bool"}],
     "type": "function"},
    {"constant": False,
     "inputs": [{"name": "_spender", "type": "address"}, {"name": "_value", "type": "uint256"}],
     "name": "approve", "outputs": [{"name": "", "type": "bool"}],
     "type": "function"},
    {"constant": True,
     "inputs": [{"name": "_owner", "type": "address"}, {"name": "_spender", "type": "address"}],
     "name": "allowance", "outputs": [{"name": "", "type": "uint256"}],
     "type": "function"},
]

# Proxy Factory ABI — for executing transactions through proxy wallet
PROXY_FACTORY_ABI = [{
    "constant": False,
    "inputs": [{"components": [
        {"name": "typeCode", "type": "uint8"},
        {"name": "to", "type": "address"},
        {"name": "value", "type": "uint256"},
        {"name": "data", "type": "bytes"}
    ], "name": "calls", "type": "tuple[]"}],
    "name": "proxy",
    "outputs": [{"name": "returnValues", "type": "bytes[]"}],
    "payable": True, "stateMutability": "payable", "type": "function"
}]

# ERC1155 ABI — for conditional token approvals
ERC1155_APPROVAL_ABI = [{
    "constant": False,
    "inputs": [{"name": "_operator", "type": "address"}, {"name": "_approved", "type": "bool"}],
    "name": "setApprovalForAll", "outputs": [], "type": "function"
}]

# === Paraswap DEX (Native USDC → USDC.e swap) ===
PARASWAP_AUGUSTUS_ROUTER = "0xDEF171Fe48CF0115B1d80b88dc8eAB59176FEe57"
PARASWAP_TOKEN_TRANSFER_PROXY = "0x216b4b4ba9f3e719726886d34a177484278bfcae"
PARASWAP_API_BASE = "https://apiv5.paraswap.io"

# === Limits & Constants ===
API_TIMEOUT_SECONDS = 30
DEFAULT_MARKET_LIMIT = 100
MAX_POSITION_USD = float(os.getenv("POLYMARKET_MAX_POSITION_USD", "1000"))

# === Kalshi (for arbitrage comparison) ===
KALSHI_API_BASE = "https://api.elections.kalshi.com/trade-api/v2"

# === Validation ===
def has_trading_credentials() -> bool:
    """Check if trading credentials are configured"""
    return bool(POLYMARKET_PRIVATE_KEY)

def has_l2_credentials() -> bool:
    """Check if L2 API credentials are configured"""
    return all([POLYMARKET_API_KEY, POLYMARKET_API_SECRET, POLYMARKET_PASSPHRASE])
