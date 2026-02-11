# Crypto Investment Sources — Data Access Reference

## Table of Contents
- [Overview](#overview)
- [News & Media](#news--media)
- [Social Media & Community](#social-media--community)
- [Macro Economics & Interest Rates](#macro-economics--interest-rates)
- [Regulation & Policy](#regulation--policy)
- [On-Chain Data & Analytics](#on-chain-data--analytics)
- [Market Data & Indicators](#market-data--indicators)
- [Derivatives & Funding Rates](#derivatives--funding-rates)
- [ETF & Institutional Flow](#etf--institutional-flow)
- [Research & Reports](#research--reports)
- [Calendars & Events](#calendars--events)
- [Traditional Assets](#traditional-assets)

---

## Overview

Each source is classified by access method:

| Method | Description | Automation |
|--------|-------------|------------|
| **REST API** | Official public API with JSON endpoints | Direct HTTP requests |
| **RSS** | RSS/Atom feed for news/articles | Feed parser (feedparser, etc.) |
| **WebSocket** | Real-time streaming data | WS client |
| **Browser** | No API — requires Playwright/Selenium | Browser automation |
| **GraphQL** | GraphQL API endpoint | GraphQL client |
| **CSV/Download** | Downloadable data files | HTTP download + parse |

---

## News & Media

| Source | Access Method | Details |
|--------|:------------:|---------|
| CoinDesk | RSS | `https://www.coindesk.com/arc/outboundfeeds/rss/` |
| CoinTelegraph | RSS | `https://cointelegraph.com/rss` |
| The Block | RSS | `https://www.theblock.co/rss` (partial — some paywalled) |
| Decrypt | RSS | `https://decrypt.co/feed` |
| DL News | Browser | No public API or RSS — browser automation required |
| Bloomberg Crypto | Browser | Paywalled — requires subscription + browser automation |
| Reuters Crypto | Browser | No public crypto-specific RSS — browser automation |
| Binance Square | Browser | No public API — see `binance-analytics` skill |

### News Aggregation Strategy
1. Primary: RSS feeds (CoinDesk, CoinTelegraph, The Block, Decrypt) — poll every 5-15 min
2. Secondary: Browser automation for Bloomberg, Reuters (if subscribed)
3. Supplementary: Binance Square via browser automation

---

## Social Media & Community

| Source | Access Method | Details |
|--------|:------------:|---------|
| X (Twitter) | REST API | X API v2 — requires developer account ($100/mo Basic tier). Endpoints: `GET /2/tweets/search/recent`, `GET /2/users/:id/tweets` |
| Reddit | REST API | Reddit API (free with OAuth). `GET /r/{subreddit}/new.json`, `GET /r/{subreddit}/hot.json` |
| LunarCrush | REST API | `https://lunarcrush.com/api` — free tier available. Social metrics, Galaxy Score, AltRank |
| Telegram | REST API | Telegram Bot API for channel monitoring. `getUpdates` or webhooks |
| Discord | REST API / WebSocket | Discord Bot API. Gateway WebSocket for real-time channel monitoring |

### X API v2 Key Endpoints

```
# Search recent tweets (last 7 days)
GET https://api.twitter.com/2/tweets/search/recent
  ?query=crypto OR bitcoin OR ethereum
  &max_results=100
  &tweet.fields=created_at,public_metrics,author_id

# User tweets
GET https://api.twitter.com/2/users/:id/tweets
  ?max_results=100
  &tweet.fields=created_at,public_metrics
```

### Reddit API Key Endpoints

```
# Subreddit posts (no auth needed for .json)
GET https://www.reddit.com/r/cryptocurrency/new.json?limit=100
GET https://www.reddit.com/r/bitcoin/hot.json?limit=100

# Search
GET https://www.reddit.com/r/cryptocurrency/search.json?q=bitcoin&sort=new&limit=100
```

### LunarCrush API v4

```
# Asset social metrics
GET https://lunarcrush.com/api4/public/coins/:symbol/v1
  Headers: Authorization: Bearer {API_KEY}

# Social mentions feed
GET https://lunarcrush.com/api4/public/coins/:symbol/feeds/v1
```

---

## Macro Economics & Interest Rates

| Source | Access Method | Details |
|--------|:------------:|---------|
| FRED | REST API | `https://api.stlouisfed.org/fred/series/observations` — free API key |
| CME FedWatch | Browser | No public API — browser automation for rate probabilities |
| Federal Reserve | RSS + CSV | Press releases RSS, data CSV downloads |
| Trading Economics | REST API | Paid API — `https://api.tradingeconomics.com` |
| Investing.com | Browser | No public API — browser automation for calendar |
| BLS | REST API | `https://api.bls.gov/publicAPI/v2/timeseries/data/` — free (limited) |
| BEA | REST API | `https://apps.bea.gov/api/data` — free API key |
| US Treasury | CSV/Download | Yield curve data downloadable as CSV |

### FRED API

```
# Get series observations
GET https://api.stlouisfed.org/fred/series/observations
  ?series_id=CPIAUCSL
  &api_key={FRED_API_KEY}
  &file_type=json
  &observation_start=2024-01-01
  &sort_order=desc
  &limit=12

# Key series for crypto analysis
# CPIAUCSL  — CPI
# FEDFUNDS  — Fed Funds Rate
# M2SL      — M2 Money Supply
# DGS10     — 10Y Treasury Yield
# DGS2      — 2Y Treasury Yield
# T10Y2Y    — 10Y-2Y Spread
# WALCL     — Fed Balance Sheet
# RRPONTSYD — Reverse Repo
# DTWEXBGS  — Dollar Index (trade-weighted)
# UNRATE    — Unemployment Rate
```

### BLS API v2

```
POST https://api.bls.gov/publicAPI/v2/timeseries/data/
Content-Type: application/json

{
  "seriesid": ["CUUR0000SA0", "CES0000000001"],
  "startyear": "2024",
  "endyear": "2025",
  "registrationkey": "{BLS_API_KEY}"
}

# CUUR0000SA0 — CPI-U All Items
# CES0000000001 — Total Non-Farm Payrolls
```

### BEA API

```
GET https://apps.bea.gov/api/data
  ?UserID={BEA_API_KEY}
  &method=GetData
  &DataSetName=NIPA
  &TableName=T10101
  &Frequency=Q
  &Year=2024
  &ResultFormat=JSON
```

### Federal Reserve RSS

```
# Press Releases
https://www.federalreserve.gov/feeds/press_all.xml

# FOMC Statements
https://www.federalreserve.gov/feeds/press_monetary.xml

# Speeches
https://www.federalreserve.gov/feeds/speeches.xml
```

---

## Regulation & Policy

| Source | Access Method | Details |
|--------|:------------:|---------|
| SEC EDGAR | REST API | `https://efts.sec.gov/LATEST/search-index` — free, rate-limited (10 req/sec) |
| SEC RSS | RSS | `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=&dateb=&owner=include&count=40&search_text=&action=getcompany&RSS` |
| CFTC | RSS | Press releases RSS available |
| Congress.gov | REST API | `https://api.congress.gov/v3/bill` — free API key |
| FATF | RSS | `https://www.fatf-gafi.org/en/rss.xml` |
| FSC Korea | Browser | No public API — browser automation for announcements |
| FSS Korea | Browser | No public API — browser automation |

### SEC EDGAR Full-Text Search

```
GET https://efts.sec.gov/LATEST/search-index
  ?q="bitcoin" OR "cryptocurrency" OR "digital asset"
  &dateRange=custom
  &startdt=2024-01-01
  &enddt=2025-01-01
  &forms=S-1,10-K,8-K

Headers:
  User-Agent: YourName your@email.com
```

### Congress.gov API

```
GET https://api.congress.gov/v3/bill
  ?api_key={CONGRESS_API_KEY}
  &query=cryptocurrency OR "digital asset" OR stablecoin
  &sort=updateDate+desc
  &limit=20
```

---

## On-Chain Data & Analytics

| Source | Access Method | Details |
|--------|:------------:|---------|
| Glassnode | REST API | `https://api.glassnode.com/v1/metrics` — paid plans (Starter $29/mo) |
| CryptoQuant | REST API | `https://api.cryptoquant.com/v1` — paid plans |
| Dune Analytics | REST API | `https://api.dune.com/api/v1` — free tier (community queries) |
| DefiLlama | REST API | `https://api.llama.fi` — free, no API key |
| Nansen | REST API | Paid API — institutional tier |
| Arkham Intelligence | REST API | `https://api.arkhamintel.com` — paid plans |
| Etherscan | REST API | `https://api.etherscan.io/api` — free tier (5 req/sec) |
| Blockchain.com | REST API | `https://blockchain.info/` — free |
| Santiment | GraphQL | `https://api.santiment.net/graphql` — free tier available |
| IntoTheBlock | REST API | Paid API |

### DefiLlama API (Free, No Key)

```
# All protocols TVL
GET https://api.llama.fi/protocols

# Protocol TVL history
GET https://api.llama.fi/protocol/{protocol-slug}

# Chain TVL
GET https://api.llama.fi/v2/chains

# Stablecoins
GET https://stablecoins.llama.fi/stablecoins

# Yields (DeFi pools)
GET https://yields.llama.fi/pools

# Token unlocks
GET https://api.llama.fi/unlocks
```

### Glassnode API

```
GET https://api.glassnode.com/v1/metrics/market/price_usd_close
  ?a=BTC
  &s=1609459200
  &u=1640995200
  &i=24h
  &api_key={GLASSNODE_KEY}

# Key metric paths:
# /v1/metrics/market/price_usd_close
# /v1/metrics/indicators/nupl
# /v1/metrics/indicators/sopr
# /v1/metrics/market/mvrv_z_score
# /v1/metrics/distribution/balance_exchanges
# /v1/metrics/supply/active_24h
# /v1/metrics/addresses/active_count
```

### Etherscan API

```
GET https://api.etherscan.io/api
  ?module=account
  &action=balance
  &address={ADDRESS}
  &tag=latest
  &apikey={ETHERSCAN_KEY}

# Useful modules:
# account — balances, transactions
# stats — total supply, ETH price
# contract — ABI, source code
# token — ERC20 transfers, balances
```

### Dune Analytics API

```
# Execute a query
POST https://api.dune.com/api/v1/query/{query_id}/execute
  Headers: X-DUNE-API-KEY: {DUNE_KEY}

# Get results
GET https://api.dune.com/api/v1/query/{query_id}/results
  Headers: X-DUNE-API-KEY: {DUNE_KEY}
```

---

## Market Data & Indicators

| Source | Access Method | Details |
|--------|:------------:|---------|
| CoinMarketCap | REST API | `https://pro-api.coinmarketcap.com/v1` — free tier (333 calls/day) |
| CoinGecko | REST API | `https://api.coingecko.com/api/v3` — free (10-30 calls/min) |
| TradingView | Browser + WebSocket | No public REST API — use TradingView widget/charting library |
| Alternative.me | REST API | `https://api.alternative.me/fng/` — free, no key |
| Coinglass | REST API | `https://open-api.coinglass.com/public/v2` — API key required |
| CryptoCompare | REST API | `https://min-api.cryptocompare.com` — free tier |
| Binance Analytics | Browser | See `binance-analytics` skill |

### CoinGecko API (Free)

```
# Coin price
GET https://api.coingecko.com/api/v3/simple/price
  ?ids=bitcoin,ethereum
  &vs_currencies=usd
  &include_market_cap=true
  &include_24hr_change=true

# Market data (top coins)
GET https://api.coingecko.com/api/v3/coins/markets
  ?vs_currency=usd
  &order=market_cap_desc
  &per_page=100

# Global market data
GET https://api.coingecko.com/api/v3/global

# Historical chart
GET https://api.coingecko.com/api/v3/coins/bitcoin/market_chart
  ?vs_currency=usd
  &days=365
```

### Alternative.me Fear & Greed Index

```
# Current value
GET https://api.alternative.me/fng/

# Historical (limit days)
GET https://api.alternative.me/fng/?limit=30&format=json

# Response: { value: "73", value_classification: "Greed", timestamp: "..." }
```

### CoinMarketCap API

```
GET https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest
  ?limit=100
  &convert=USD
  Headers: X-CMC_PRO_API_KEY: {CMC_KEY}

# Key endpoints:
# /v1/cryptocurrency/listings/latest — market cap rankings
# /v1/cryptocurrency/quotes/latest — price data
# /v1/global-metrics/quotes/latest — total market cap, BTC dominance
# /v1/cryptocurrency/category — sector performance
```

### Coinglass Open API v2

```
GET https://open-api.coinglass.com/public/v2/funding
  Headers: coinglassSecret: {COINGLASS_KEY}

# Key endpoints:
# /public/v2/funding — cross-exchange funding rates
# /public/v2/open_interest — open interest by exchange
# /public/v2/liquidation — liquidation data
# /public/v2/long_short — long/short ratio
# /public/v2/option — options data
```

---

## Derivatives & Funding Rates

| Source | Access Method | Details |
|--------|:------------:|---------|
| Coinglass | REST API | See Market Data section above |
| Laevitas | REST API | `https://api.laevitas.ch` — paid API |
| Deribit | REST API + WebSocket | `https://www.deribit.com/api/v2` — free |
| Binance Futures | REST API | `https://fapi.binance.com` — free |
| Binance Options | REST API | `https://eapi.binance.com` — free |
| Binance Arbitrage | Browser | See `binance-analytics` skill |

### Deribit API (Free, No Key for Public)

```
# BTC Options instruments
GET https://www.deribit.com/api/v2/public/get_instruments
  ?currency=BTC
  &kind=option
  &expired=false

# Order book
GET https://www.deribit.com/api/v2/public/get_order_book
  ?instrument_name=BTC-28MAR25-100000-C

# DVOL (Deribit Volatility Index)
GET https://www.deribit.com/api/v2/public/get_volatility_index_data
  ?currency=BTC
  &resolution=3600

# Trade history
GET https://www.deribit.com/api/v2/public/get_last_trades_by_currency
  ?currency=BTC
  &kind=option
  &count=100
```

### Binance Futures API

```
# Open Interest
GET https://fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT

# Funding Rate
GET https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&limit=100

# Premium Index (real-time funding + mark price)
GET https://fapi.binance.com/fapi/v1/premiumIndex

# Top Trader L/S Ratio
GET https://fapi.binance.com/futures/data/topLongShortAccountRatio
  ?symbol=BTCUSDT&period=1h&limit=30

# Taker Buy/Sell Volume
GET https://fapi.binance.com/futures/data/takerlongshortRatio
  ?symbol=BTCUSDT&period=1h&limit=30
```

### Binance Options API

```
# Options OI
GET https://eapi.binance.com/eapi/v1/openInterest?underlyingAsset=BTC

# Exercise History
GET https://eapi.binance.com/eapi/v1/exerciseHistory?underlyingAsset=BTC
```

---

## ETF & Institutional Flow

| Source | Access Method | Details |
|--------|:------------:|---------|
| Farside Investors | Browser | No API — `https://farside.co.uk/btc/` — table scraping |
| SoSoValue | Browser | No public API — browser automation |
| CoinShares | RSS/PDF | Weekly reports via blog RSS |
| BitMEX Research | RSS | Blog RSS feed |
| Bloomberg ETF | Browser | Paywalled — requires terminal/subscription |
| Grayscale | Browser | Holdings data on website |

### ETF Flow Data Access Strategy

ETF flow data has **no free API**. Recommended approaches:

1. **Primary**: Browser automation on Farside Investors (daily BTC/ETH ETF flows)
   - URL: `https://farside.co.uk/btc/` (BTC), `https://farside.co.uk/eth/` (ETH)
   - Simple HTML table — easy to parse with Playwright

2. **Secondary**: SoSoValue browser automation (cumulative flows, charts)
   - URL: `https://sosovalue.com/assets/etf/us-btc-spot`

3. **Supplementary**: CoinShares weekly report RSS
   - URL: `https://coinshares.com/research/feed`
   - Provides weekly institutional flow summary

---

## Research & Reports

| Source | Access Method | Details |
|--------|:------------:|---------|
| Binance Research | Browser | See `binance-analytics` skill |
| Messari | REST API | `https://data.messari.io/api` — free tier |
| Chainalysis | RSS | Blog RSS feed |
| a16z Crypto | RSS | Blog RSS feed |
| Galaxy Digital | RSS | Research blog RSS |
| Coinbase Institutional | Browser | No public API |
| K33 Research | Browser | Paywalled reports |

### Messari API

```
# Asset profile
GET https://data.messari.io/api/v1/assets/bitcoin/profile

# Asset metrics
GET https://data.messari.io/api/v1/assets/bitcoin/metrics

# Market data
GET https://data.messari.io/api/v1/assets/bitcoin/metrics/market-data

# News
GET https://data.messari.io/api/v1/news
  ?fields=title,url,published_at
```

---

## Calendars & Events

| Source | Access Method | Details |
|--------|:------------:|---------|
| CoinMarketCal | REST API | `https://developers.coinmarketcal.com/v1` — free tier |
| Token Unlocks | REST API | `https://token.unlocks.app/api` — paid plans |
| DefiLlama Unlocks | REST API | `https://api.llama.fi/unlocks` — free |
| Investing.com Calendar | Browser | No public API — browser automation |
| FOMC Calendar | RSS/CSV | Fed schedule page, parseable |
| Binance Announcements | RSS | `https://www.binance.com/en/support/announcement` — parseable |

### CoinMarketCal API

```
GET https://developers.coinmarketcal.com/v1/events
  ?max=50
  &dateRangeStart=2025-01-01
  &dateRangeEnd=2025-03-01
  &coins=bitcoin,ethereum
  &categories=1,2,3
  Headers: x-api-key: {CMC_CAL_KEY}

# Category IDs:
# 1=Exchange, 2=Conference, 3=Community, 4=Burn/Buyback
# 5=Partnership, 6=Release/Update, 7=Airdrop, 8=Brand
```

### DefiLlama Token Unlocks (Free)

```
GET https://api.llama.fi/unlocks

# Returns upcoming token unlocks with:
# - protocol name
# - unlock date
# - unlock amount (USD)
# - percentage of circulating supply
```

---

## Traditional Assets

| Source | Access Method | Details |
|--------|:------------:|---------|
| TradingView | Browser/Widget | No REST API — use charting library or browser |
| Yahoo Finance | REST API | `https://query1.finance.yahoo.com/v8/finance/chart/{TICKER}` — free |
| Alpha Vantage | REST API | `https://www.alphavantage.co/query` — free (25 req/day) |
| FRED | REST API | See Macro Economics section — yields, DXY, etc. |

### Yahoo Finance API (Unofficial, Free)

```
# Historical data
GET https://query1.finance.yahoo.com/v8/finance/chart/SPY
  ?range=1y
  &interval=1d

# Tickers for crypto correlation:
# ^GSPC (S&P 500), ^IXIC (NASDAQ), ^VIX (VIX)
# DX-Y.NYB (DXY), ^TNX (10Y Yield)
# GC=F (Gold Futures), CL=F (WTI Oil)
```

### Alpha Vantage API

```
GET https://www.alphavantage.co/query
  ?function=TIME_SERIES_DAILY
  &symbol=SPY
  &apikey={AV_KEY}

# Key functions:
# TIME_SERIES_DAILY — daily OHLCV
# TREASURY_YIELD — US treasury yields
# FEDERAL_FUNDS_RATE — fed funds rate
# CPI — consumer price index
# REAL_GDP — GDP data
```

---

## Quick Reference: Free APIs (No Key Required)

| API | Rate Limit | Best For |
|-----|-----------|----------|
| CoinGecko | 10-30 req/min | Token prices, market data |
| DefiLlama | Generous | DeFi TVL, yields, unlocks |
| Alternative.me F&G | Low | Fear & Greed Index |
| Deribit Public | Moderate | Options data, DVOL |
| Binance Futures | 2400 req/min | Funding, OI, L/S ratios |
| Reddit (.json) | Moderate | Subreddit sentiment |
| Blockchain.com | Moderate | BTC on-chain basics |

## Quick Reference: Free APIs (Key Required)

| API | Free Tier | Best For |
|-----|----------|----------|
| FRED | Unlimited (10 req/min) | Macro economic data |
| CoinMarketCap | 333 calls/day | Market cap, dominance |
| Etherscan | 5 req/sec | Ethereum on-chain |
| Dune Analytics | 2500 credits/mo | Custom on-chain queries |
| BLS | 500/day | Employment, CPI official |
| BEA | Unlimited | GDP, income |
| Congress.gov | 5000/hr | Legislative tracking |
| Messari | Limited | Research, asset profiles |
| CoinMarketCal | 500/mo | Event calendar |
