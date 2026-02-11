# Binance Copy Trading — API Mapping Reference

## Table of Contents
- [API Availability Summary](#api-availability-summary)
- [Official Copy Trading API](#official-copy-trading-api)
- [Read-Only API Access](#read-only-api-access)
- [Market Sentiment Data](#market-sentiment-data)
- [Browser-Only Operations](#browser-only-operations)
- [Internal BAPI Leaderboard Endpoints (Undocumented)](#internal-bapi-leaderboard-endpoints-undocumented)
- [Portfolio Margin API](#portfolio-margin-api)
- [Workarounds](#workarounds)

---

## API Availability Summary

**Binance Copy Trading has an extremely limited public API — only 2 official endpoints.**

| Operation | API Available | Alternative |
|-----------|:------------:|-------------|
| Check lead trader status | **Yes** | `/sapi/v1/copyTrading/futures/userStatus` |
| Get lead symbol whitelist | **Yes** | `/sapi/v1/copyTrading/futures/leadSymbol` |
| Browse leaderboard | No | Playwright browser automation |
| View trader profile | No | Playwright browser automation |
| Start copying | No | Playwright browser automation |
| Configure copy settings | No | Playwright browser automation |
| Stop copying | No | Playwright browser automation |
| View own copy positions | **Yes** | Standard Futures API |
| View own copy orders | **Yes** | Standard Futures API |
| View account balance | **Yes** | Standard Futures API |

---

## Official Copy Trading API

Base URL: `https://api.binance.com`

### Get Futures Lead Trader Status — `GET /sapi/v1/copyTrading/futures/userStatus`

Weight: 20 (UID)

| Param | Type | Required |
|-------|------|----------|
| `timestamp` | LONG | Yes |
| `recvWindow` | LONG | No |

**Response:** `{"isLeadTrader": true}`

### Get Futures Lead Trading Symbol Whitelist — `GET /sapi/v1/copyTrading/futures/leadSymbol`

Weight: 20 (IP)

| Param | Type | Required |
|-------|------|----------|
| `timestamp` | LONG | Yes |
| `recvWindow` | LONG | No |

**Response:**
```json
{
  "code": "000000",
  "message": "success",
  "data": [
    {"symbol": "BTCUSDT", "baseAsset": "BTC", "quoteAsset": "USDT"}
  ]
}
```

**Note:** Lead traders can create up to 2 API keys for their lead trading portfolios.

**Official npm package:** `@binance/copy-trading` (Node.js >= 22.12.0) — provides `CopyTrading` class with REST API module. Supports RSA/ED25519 key-based auth and proxy configuration.

---

## Read-Only API Access

Copy positions and orders are visible via standard Futures API. Copy-originated positions are **not** separately tagged.

### View Positions — `GET /fapi/v3/positionRisk`

Returns all positions including those created by copy trading.

### View Orders — `GET /fapi/v1/openOrders`

Returns all open orders including those placed by the copy trading system.

### Account Balance — `GET /fapi/v3/balance`

Returns account balance affected by copy trading activity.

### Income History — `GET /fapi/v1/income`

Returns income/expense records. Copy trading transactions appear as regular trading income/commission entries.

---

## Market Sentiment Data

These official endpoints provide actionable trading signals without relying on unstable internal APIs.

Base URL: `https://fapi.binance.com` | Rate limit: 1000/5min (IP)

| Endpoint | Description | Data Retention |
|----------|-------------|----------------|
| `GET /fapi/v1/openInterest` | Current open interest for a symbol | Real-time |
| `GET /futures/data/openInterestHist` | Historical open interest | Latest 1 month |
| `GET /futures/data/topLongShortAccountRatio` | Top 20% traders L/S by account count | Latest 30 days |
| `GET /futures/data/topLongShortPositionRatio` | Top 20% traders L/S by position size | Latest 30 days |
| `GET /futures/data/globalLongShortAccountRatio` | Global L/S ratio all traders | Latest 30 days |
| `GET /futures/data/takerlongshortRatio` | Taker buy vs sell volume ratio | Latest 30 days |

**Common Parameters:** `symbol`, `period` (5m/15m/30m/1h/2h/4h/6h/12h/1d), `limit` (max 500), `startTime`, `endTime`

**Response Example (topLongShortAccountRatio):**
```json
{
  "symbol": "BTCUSDT",
  "longShortRatio": "1.2345",
  "longAccount": "0.5524",
  "shortAccount": "0.4476",
  "timestamp": 1672515782136
}
```

---

## Browser-Only Operations

All copy trading management requires Playwright automation:

### Starting a Copy
1. Navigate to `https://www.binance.com/en/copy-trading`
2. Filter/search traders on leaderboard
3. Click "Copy" on trader card (opens new tab)
4. Configure: mode, amount, symbols, risk settings
5. Click "Copy" to confirm

### Stopping a Copy
1. Navigate to `https://www.binance.com/en/copy-trading/copy-management`
2. Find the trader in "Ongoing" tab
3. Click stop/close button
4. Confirm in dialog

### Modifying Copy Settings
1. Navigate to Copy Management
2. Click settings on trader row
3. Modify parameters
4. Confirm changes

---

## Internal BAPI Leaderboard Endpoints (Undocumented)

**WARNING:** NOT officially supported. Binance states: "the endpoints you're referring to are not public endpoints. It is not recommended to use them." May break at any time. The v1 public endpoints have been migrated to v2 private endpoints requiring cookie-based auth.

### Known Endpoints

| Endpoint | Version | Auth | Status |
|----------|---------|------|--------|
| `/bapi/futures/v1/public/future/leaderboard/getOtherPosition` | v1 | None | **DEPRECATED** |
| `/bapi/futures/v2/private/future/leaderboard/getOtherPosition` | v2 | Cookie required | Current |
| `/bapi/futures/v1/public/future/leaderboard/searchLeaderboard` | v1 | Unknown | Discovered via scrapers |
| `/bapi/futures/v1/public/future/leaderboard/getOtherLeaderboardBaseInfo` | v1 | Unknown | Discovered via scrapers |
| `/bapi/futures/v1/public/future/leaderboard/getOtherPerformance` | v1 | Unknown | Discovered via scrapers |
| `/bapi/futures/v1/public/future/leaderboard/searchNickname` | v1 | Unknown | Discovered via scrapers |

**`getOtherPosition` request (POST):**
```json
{
  "encryptedUid": "<trader_encrypted_uid>",
  "tradeType": "PERPETUAL"
}
```

**`searchLeaderboard` returns:** `encryptedUid`, `nickName`, `followerCount`, PNL, ROI, rank

### Third-Party Wrappers (reference only)
- RapidAPI proxy: `binance-futures-leaderboard1.p.rapidapi.com`
- Go wrapper: `github.com/rtunazzz/bfldb`
- Python scrapers: Multiple Apify actors available

---

## Portfolio Margin API

Base URL: `https://papi.binance.com` | Rate limits: IP 6000/min, Orders 1200/min

For accounts using Portfolio Margin mode, these endpoints provide cross-venue trading:

### Account Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/papi/v1/balance` | GET | Account balance |
| `/papi/v1/account` | GET | Account info (equity, margin rates, status) |
| `/papi/v1/um-position-info` | GET | USDS-M futures positions |
| `/papi/v1/cm-position-info` | GET | COIN-M futures positions |
| `/papi/v1/um-leverage` | POST | Adjust USDS-M leverage |
| `/papi/v1/cm-leverage` | POST | Adjust COIN-M leverage |
| `/papi/v1/um-commission-rate` | GET | USDS-M commission structure |
| `/papi/v1/income-history` | GET | Earnings across venues |
| `/sapi/v2/portfolio/collateralRate` | GET | Collateral rates |

### Trade Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/papi/v1/um/order` | POST | Place UM futures order |
| `/papi/v1/um/order` | DELETE | Cancel UM order |
| `/papi/v1/um/allOpenOrders` | DELETE | Cancel all UM open orders |
| `/papi/v1/um/order` | PUT | Modify UM order |
| `/papi/v1/um/openOrders` | GET | All current open UM orders |
| `/papi/v1/um/userTrades` | GET | UM trade list |

**Account status values:** `NORMAL`, `MARGIN_CALL`, `SUPPLY_MARGIN`, `REDUCE_ONLY`, `ACTIVE_LIQUIDATION`, `FORCE_LIQUIDATION`, `BANKRUPTED`

---

## Workarounds

### Leaderboard Data Scraping

Use Playwright to extract leaderboard data:
1. Navigate to leaderboard URL
2. Apply desired filters (time period, sort, advanced)
3. Use `browser_snapshot` to capture trader card data
4. Parse metrics: PNL, ROI, AUM, MDD, Sharpe Ratio, Copiers
5. Scroll/paginate for more results (up to 21 pages)

### Portfolio Monitoring

Combine API and browser automation:
- Use `GET /fapi/v3/positionRisk` for real-time position data
- Use Playwright to scrape Copy Management page for per-trader attribution
- Calculate per-trader PnL from position data

### Risk Management

Use standard Futures API for risk controls on copy positions:
- `POST /fapi/v1/algoOrder` (algoType=CONDITIONAL) — Place TP/SL on copy positions
- `DELETE /fapi/v1/allOpenOrders` — Emergency cancel all orders
- `POST /fapi/v1/order` with `type=MARKET` and `reduceOnly=true` — Force close position

### Market Sentiment for Trader Selection

Use official market sentiment endpoints to enhance trader evaluation:
- Compare trader's positions against `topLongShortPositionRatio` to gauge contrarian/consensus alignment
- Monitor `openInterest` changes to validate trader's entry timing
- Use `takerlongshortRatio` to assess market aggression context
