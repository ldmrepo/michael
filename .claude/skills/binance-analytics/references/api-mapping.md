# Binance Analytics — API Mapping Reference

## Table of Contents
- [Overview: API Availability](#overview-api-availability)
- [Smart Money](#smart-money)
- [Futures Trading Data](#futures-trading-data)
- [Arbitrage Data](#arbitrage-data)
- [Options Data](#options-data)
- [Heatmap](#heatmap)
- [Trading Insight](#trading-insight)
- [Futures Markets Overview](#futures-markets-overview)
- [Binance Research](#binance-research)
- [Other Data Pages](#other-data-pages)
- [Quick Reference Table](#quick-reference-table)

---

## Overview: API Availability

Most Binance analytics features are **browser-only** and not accessible via public REST API. This document maps each feature to its API status and provides alternative access methods.

| Feature Category | API Status | Access Method |
|-----------------|:----------:|---------------|
| Smart Money | None | Browser automation only |
| Futures Trading Data | Partial (5/8 charts) | API for some, browser for rest |
| Arbitrage Data | None | Browser automation only |
| Options Data | Partial (2/7 tabs) | API for some, browser for rest |
| Heatmap | None | Browser automation only |
| Trading Insight | Partial | Some data via existing APIs, most browser-only |
| Futures Markets Overview | Partial | Some widgets use existing APIs |
| Binance Research | None | Browser automation only |
| Other Data Pages | Partial | Some endpoints available |

---

## Smart Money

**API Status: None — Browser automation required**

All Smart Money features are proprietary and exclusive to the web UI.

| Feature | API | Notes |
|---------|:---:|-------|
| Top Traders Leaderboard | No | Subscription data, rankings, positions |
| Smart Signal List | No | Dominant Flow data |
| Smart Signal Detail (Traders) | No | Position breakdown, entry prices, PnL |
| Smart Signal Detail (Whales) | No | Same structure, whale-filtered data |
| Individual Trader History | No | Per-trader trade records |

**Automation approach:** Use Playwright to navigate to Smart Money pages, extract data from DOM elements. Signal detail pages support URL query parameters for filtering (timeRange, side, sortBy, sortOrder, page).

---

## Futures Trading Data

**API Status: Partial — 5 of 8 charts have public API endpoints**

### API-Available Charts

#### Open Interest
```
GET /fapi/v1/openInterest
```
| Param | Type | Required | Description |
|-------|------|:--------:|-------------|
| `symbol` | STRING | Yes | e.g., `BTCUSDT` |

Returns: `openInterest` (quantity), `symbol`, `time`

#### Open Interest Statistics (Historical)
```
GET /futures/data/openInterestHist
```
| Param | Type | Required | Description |
|-------|------|:--------:|-------------|
| `symbol` | STRING | Yes | |
| `period` | STRING | Yes | `5m`,`15m`,`30m`,`1h`,`2h`,`4h`,`6h`,`12h`,`1d` |
| `limit` | INT | No | Default 30, max 500 |
| `startTime` | LONG | No | |
| `endTime` | LONG | No | |

#### Top Trader Long/Short Ratio (Accounts)
```
GET /futures/data/topLongShortAccountRatio
```
| Param | Type | Required | Description |
|-------|------|:--------:|-------------|
| `symbol` | STRING | Yes | |
| `period` | STRING | Yes | `5m`,`15m`,`30m`,`1h`,`2h`,`4h`,`6h`,`12h`,`1d` |
| `limit` | INT | No | Default 30, max 500 |
| `startTime` | LONG | No | |
| `endTime` | LONG | No | |

Returns: `symbol`, `longShortRatio`, `longAccount`, `shortAccount`, `timestamp`

#### Top Trader Long/Short Ratio (Positions)
```
GET /futures/data/topLongShortPositionRatio
```
Same parameters and structure as Account ratio endpoint.

Returns: `symbol`, `longShortRatio`, `longPosition`, `shortPosition`, `timestamp`

#### Long/Short Ratio (Global)
```
GET /futures/data/globalLongShortAccountRatio
```
Same parameters as above.

Returns: `symbol`, `longShortRatio`, `longAccount`, `shortAccount`, `timestamp`

#### Taker Buy/Sell Volume
```
GET /futures/data/takerlongshortRatio
```
Same parameters as above.

Returns: `buySellRatio`, `buyVol`, `sellVol`, `timestamp`

### Browser-Only Charts

| Chart | Why No API | Alternative |
|-------|-----------|-------------|
| Basis | Proprietary calculation | Calculate manually: `futures_price - spot_price` using `GET /fapi/v1/ticker/price` and `GET /api/v3/ticker/price` |
| Funding Rate (chart view) | Chart format only | Use `GET /fapi/v1/fundingRate` for raw data, build chart locally |
| OI to Market Cap Ratio | Proprietary | Calculate: `openInterest / marketCap` using OI endpoint + external market cap data |

### Funding Rate (Raw Data)
```
GET /fapi/v1/fundingRate
```
| Param | Type | Required | Description |
|-------|------|:--------:|-------------|
| `symbol` | STRING | No | |
| `startTime` | LONG | No | |
| `endTime` | LONG | No | |
| `limit` | INT | No | Default 100, max 1000 |

Returns: `symbol`, `fundingRate`, `fundingTime`, `markPrice`

---

## Arbitrage Data

**API Status: None — Browser automation required**

| Feature | API | Notes |
|---------|:---:|-------|
| Funding Rate Arbitrage table | No | Includes revenue simulation |
| Spread Arbitrage table | No | Spread rate calculations |
| Position Size simulation | No | Server-side computation |
| APR calculations | No | Proprietary formula |

**Workaround for partial data:**
- Funding rates: Use `GET /fapi/v1/fundingRate` for raw rates, calculate APR manually
- Spread: Use `GET /fapi/v1/ticker/price` (futures) and `GET /api/v3/ticker/price` (spot) to calculate spread
- Full simulation with 3-day revenue projections requires browser scraping

---

## Options Data

**API Status: Partial — 2 of 7 tabs have public API endpoints**

### API-Available Tabs

#### Open Interest (Options)
```
GET /eapi/v1/openInterest
```
| Param | Type | Required | Description |
|-------|------|:--------:|-------------|
| `underlyingAsset` | STRING | Yes | e.g., `BTC` |
| `expiration` | STRING | No | e.g., `250228` (YYMMDD) |

Returns: Array of `{ symbol, sumOpenInterest, sumOpenInterestUsd, timestamp }`

#### Exercise History
```
GET /eapi/v1/exerciseHistory
```
| Param | Type | Required | Description |
|-------|------|:--------:|-------------|
| `underlyingAsset` | STRING | No | e.g., `BTC` |
| `startTime` | LONG | No | |
| `endTime` | LONG | No | |
| `limit` | INT | No | Default 100, max 100 |

Returns: `symbol`, `strikePrice`, `realStrikePrice`, `expiryDate`, `strikeResult` (EXERCISED/EXPIRED_OTM)

### Browser-Only Tabs

| Tab | Why No API | Notes |
|-----|-----------|-------|
| Overview | Aggregated proprietary view | Top 5 OI/Volume, Put/Call ratios, Taker Flow |
| Term Structure | Proprietary calculation | IV across different expirations |
| Implied Volatility | Proprietary model | IV surface, skew data |
| Max Pain | Proprietary calculation | Can be calculated from OI data if all strikes are available |
| Volatility Index (BVOL) | Proprietary index | Real-time BTC volatility index, no API |

**Workaround for Max Pain:**
Max Pain can be calculated locally if you have OI data per strike:
1. Get all option OI from `GET /eapi/v1/openInterest`
2. For each strike, calculate total pain (loss) to option sellers
3. Strike with minimum total pain = Max Pain price

---

## Heatmap

**API Status: None — Browser automation required**

| Feature | API | Notes |
|---------|:---:|-------|
| Treemap visualization | No | Browser-only rendering |
| Performance data | No | Aggregated from multiple sources |
| Filter options | No | Client-side only |

**Workaround:**
Build your own heatmap using:
- `GET /fapi/v1/ticker/24hr` for 24h performance of all futures symbols
- `GET /fapi/v1/openInterest` for OI data
- External market cap data for market cap metric

---

## Other Data Pages

### Real-Time Funding Rate
```
GET /fapi/v1/premiumIndex
```
| Param | Type | Required |
|-------|------|:--------:|
| `symbol` | STRING | No (returns all if omitted) |

Returns: `symbol`, `markPrice`, `indexPrice`, `estimatedSettlePrice`, `lastFundingRate`, `nextFundingTime`, `interestRate`

**Note:** This endpoint provides all real-time funding rate data shown on the web page.

### Funding Rate History
```
GET /fapi/v1/fundingRate
```
See [Futures Trading Data section](#funding-rate-raw-data) for parameters.

### Insurance Fund History
```
GET /fapi/v1/assetIndex
```
Partial data. Full insurance fund history chart requires browser scraping.

### Index Composition
No dedicated public API for index composition weights. Browser automation required.

### Delivery Data
```
GET /dapi/v1/deliveryPrice
```
| Param | Type | Required |
|-------|------|:--------:|
| `pair` | STRING | Yes |

Returns delivery price history for quarterly contracts.

---

## Trading Insight

**API Status: Partial — Futures Data charts overlap with existing APIs; most other features are browser-only**

### Exchange - Trading Data (16 charts)

| Feature | API | Notes |
|---------|:---:|-------|
| Price Index by Region | No | Regional price comparison, browser-only |
| Trade Volume by Region | No | Regional volume distribution, browser-only |
| Price Fluctuation by Region | No | Regional volatility, browser-only |
| Fund flow (all sizes) | No | Large/medium/small buy/sell + net inflow, browser-only |
| Margin Debt Growth (C/U) | No | Cross and USDT margin debt trends, browser-only |
| Margin L/S Positions Ratio (C/U) | No | Cross and USDT margin position ratios, browser-only |
| Isolated Margin Borrow Amount Ratio | No | Isolated margin borrowing ratio, browser-only |

### Exchange - Futures Data (7 charts)

Same data as [Futures Trading Data](#futures-trading-data) section — Open Interest, L/S Ratios, Taker Volume have API endpoints; Basis, Funding rate are browser-only.

### Binance Square Data (3 charts)

| Feature | API | Notes |
|---------|:---:|-------|
| Popularity Index (Posts) | No | Social post volume for token, browser-only |
| Popularity Index (Clicks) | No | Click engagement for token, browser-only |
| Fear and Greed Index | No | Market sentiment indicator, browser-only |

### Kline Pattern (19 patterns)

| Feature | API | Notes |
|---------|:---:|-------|
| All 19 candlestick patterns | No | Pattern recognition charts, browser-only |

**Workaround:** Kline patterns can be computed locally using candlestick data from `GET /fapi/v1/klines` with standard pattern recognition algorithms (e.g., TA-Lib).

### ETF

| Feature | API | Notes |
|---------|:---:|-------|
| ETF net inflow | No | Crypto ETF flow tracking, browser-only |

### Sidebar Widgets

| Feature | API | Notes |
|---------|:---:|-------|
| Fear & Greed Index | No | Yesterday + Last Week values, browser-only |
| Popular (trending tokens) | No | Top 30 by social mentions, browser-only |
| Smart Flow signals | No | Smart money signals (top holders/traders buying, large orders, rising stars), browser-only |

---

## Futures Markets Overview

**API Status: Partial — Some widgets use existing Futures API endpoints**

| Feature | API | Notes |
|---------|:---:|-------|
| Open Interest widget | Yes | Uses `GET /fapi/v1/openInterest` |
| 1h Long/Short Ratio widget | Yes | Uses `GET /futures/data/topLongShortAccountRatio` |
| Altcoin Week Index | No | Proprietary gauge, browser-only |
| News feed | No | Binance Square aggregation, browser-only |
| Highest Searched (24h) | No | Search trend data, browser-only |
| Highest Change (24h) | Partial | Change data available via `GET /fapi/v1/ticker/24hr` but ranking logic is proprietary |
| Market table + filters | Partial | Raw data via `GET /fapi/v1/ticker/24hr` + `GET /fapi/v1/premiumIndex`, but filter categories are proprietary |
| Ranking (Gainer/Loser/Volume/Funding) | Partial | Can be derived from ticker + funding endpoints |
| Binance Futures Index | No | Proprietary composite index, browser-only |
| Alpha (multi-chain tokens) | No | Multi-chain data, browser-only |

**Workaround for rankings:**
- Gainer/Loser: Sort `GET /fapi/v1/ticker/24hr` by `priceChangePercent`
- Volume: Sort by `quoteVolume`
- Funding Rate: Sort `GET /fapi/v1/premiumIndex` by `lastFundingRate`

---

## Binance Research

**API Status: None — Browser automation required**

| Feature | API | Notes |
|---------|:---:|-------|
| Insights & Analysis | No | Research articles, browser-only |
| Project Reports | No | Token evaluation reports, browser-only |
| Weekly/Monthly Commentary | No | Periodic market analysis, browser-only |

---

## Quick Reference Table

| Feature | API Endpoint | Status |
|---------|-------------|:------:|
| **Smart Money** | | |
| Top Traders | — | Browser only |
| Smart Signal | — | Browser only |
| **Trading Data** | | |
| Open Interest | `GET /fapi/v1/openInterest` | Available |
| OI Historical | `GET /futures/data/openInterestHist` | Available |
| Top L/S Accounts | `GET /futures/data/topLongShortAccountRatio` | Available |
| Top L/S Positions | `GET /futures/data/topLongShortPositionRatio` | Available |
| Global L/S Ratio | `GET /futures/data/globalLongShortAccountRatio` | Available |
| Taker Volume | `GET /futures/data/takerlongshortRatio` | Available |
| Basis | — | Browser only (calculable) |
| Funding Rate Chart | `GET /fapi/v1/fundingRate` (raw) | Partial |
| OI/Market Cap | — | Browser only (calculable) |
| **Arbitrage** | | |
| Funding Rate Arb | — | Browser only |
| Spread Arb | — | Browser only |
| **Options** | | |
| Options OI | `GET /eapi/v1/openInterest` | Available |
| Exercise History | `GET /eapi/v1/exerciseHistory` | Available |
| Overview | — | Browser only |
| Term Structure | — | Browser only |
| IV Surface | — | Browser only |
| Max Pain | — | Browser only (calculable) |
| BVOL | — | Browser only |
| **Heatmap** | — | Browser only |
| **Trading Insight** | | |
| Fund Flow (all types) | — | Browser only |
| Margin Debt/L/S Ratio | — | Browser only |
| Popularity Index | — | Browser only |
| Fear & Greed Index | — | Browser only |
| Kline Patterns | — | Browser only (calculable) |
| ETF net inflow | — | Browser only |
| Popular/Smart Flow | — | Browser only |
| **Futures Markets** | | |
| Altcoin Week Index | — | Browser only |
| Highest Searched/Change | — | Browser only (partial) |
| Binance Futures Index | — | Browser only |
| Alpha (multi-chain) | — | Browser only |
| Market Rankings | `GET /fapi/v1/ticker/24hr` | Partial (derivable) |
| **Research** | — | Browser only |
| **Other** | | |
| Real-Time Funding | `GET /fapi/v1/premiumIndex` | Available |
| Funding History | `GET /fapi/v1/fundingRate` | Available |
| Insurance Fund | — | Browser only |
| Index Composition | — | Browser only |
| Delivery Prices | `GET /dapi/v1/deliveryPrice` | Available |
