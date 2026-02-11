---
name: binance-analytics
description: Binance professional analytics features guide for market analysis, Smart Money tracking, options data, arbitrage opportunities, heatmap visualization, Trading Insight (fund flow, margin data, Fear & Greed Index, Smart Flow signals, kline patterns), and Futures Markets Overview (Altcoin Week Index, market rankings, Binance Futures Index). Use when implementing market analysis dashboards, tracking smart money flows, analyzing options data (IV, Max Pain, BVOL), finding arbitrage opportunities, monitoring fund flows and margin data, detecting sentiment via Fear & Greed Index, or automating data collection from Binance analytics pages via browser automation.
---

# Binance Analytics

## Overview

Guide for Binance's professional analytics features — Smart Money tracking, futures trading data analysis, arbitrage opportunities, options analytics, market heatmaps, Trading Insight (fund flows, margin data, social sentiment, kline patterns, Fear & Greed Index), and Futures Markets Overview (Altcoin Week Index, market rankings, Binance Futures Index). Most features are **browser-only** with no public REST API, requiring Playwright automation for data extraction.

## Smart Money

### Top Traders Leaderboard

```
URL: https://www.binance.com/en/smart-money
```

Ranks traders by performance with subscription/following capability.

| Metric | Description |
|--------|-------------|
| 30D PnL | Profit/loss over 30 days (USDT) |
| ROI | Return on investment percentage |
| Assets | Total asset value |
| Copiers | Number of followers |

**Filters:**
- Period: 7D / 30D / 90D
- Sort: PnL / ROI / Assets
- Status: In Position / No Position / Private

### Smart Signal List

Shows per-symbol **Dominant Flow** — aggregated directional bias from smart money activity.

| Field | Description |
|-------|-------------|
| Symbol | Trading pair (e.g., BTCUSDT) |
| Dominant Flow Direction | Buy (B) or Sell (S) |
| Dominant Flow Amount | Aggregated directional volume |
| Period Filter | 30m / 1h / 24h / 7D / All |

### Smart Signal Detail

```
URL: https://www.binance.com/en/smart-money/signal/{SYMBOL}?timeRange=30m&side=BOTH&sortBy=TIME&sortOrder=DESC&page=1
```

Two main tabs: **Traders** and **Whales** (same structure, different data source).

**Overview Section:**

| Metric | Description |
|--------|-------------|
| Total Positions | Combined long + short count |
| Notional L/S Ratio | Long vs Short ratio by notional value |

**Long/Short Breakdown:**

| Field | Description |
|-------|-------------|
| Current Positions | Active position count |
| Avg Entry Price | Average entry price across positions |
| Unrealized PnL | Total unrealized profit/loss |
| Profitable % | Percentage of profitable positions |

**Individual Trader History:** Per-trader entry/exit records with timestamps and PnL.

### URL Parameters

| Param | Options | Description |
|-------|---------|-------------|
| `timeRange` | `30m`, `1h`, `24h`, `7D`, `ALL` | Data time window |
| `side` | `BOTH`, `LONG`, `SHORT` | Position direction filter |
| `sortBy` | `TIME`, `PNL`, `ENTRY_PRICE` | Sort field |
| `sortOrder` | `ASC`, `DESC` | Sort direction |
| `page` | Integer | Pagination |

## Futures Trading Data

```
URL: https://www.binance.com/en/futures/funding-history/perpetual/trading-data
```

8 analysis charts with configurable intervals. Supports USDⓈ-M and COIN-M switching.

### Charts

| Chart | Description | API Available |
|-------|-------------|:------------:|
| Open Interest | Total outstanding contracts | Yes |
| Top Trader L/S Ratio (Accounts) | Long vs short by account count | Yes |
| Top Trader L/S Ratio (Positions) | Long vs short by position size | Yes |
| Long/Short Ratio | Overall market L/S ratio | Yes |
| Taker Buy/Sell Volume | Aggressive buy vs sell volume | Yes |
| Basis | Futures-spot price difference | No |
| Funding Rate | Current/historical funding rates | Partial |
| OI to Market Cap Ratio | Open interest relative to market cap | No |

### Interval Options

All charts support: `5m` / `15m` / `30m` / `1h` / `2h` / `4h` / `6h` / `12h` / `1d`

### View Modes

- **Single**: One chart at a time (full detail)
- **Combined**: Open Interest chart overlaid with other metrics

## Arbitrage Data

```
URL: https://www.binance.com/en/futures/funding-history/perpetual/arbitrage-data
```

### Tabs

| Tab | Description |
|-----|-------------|
| Funding Rate Arbitrage | Earn from funding rate differentials |
| Spread Arbitrage | Earn from futures-spot spread |

### Funding Rate Arbitrage Table

| Column | Description |
|--------|-------------|
| Symbol | Trading pair |
| Position Size | User-configurable simulation input |
| 3 Day Revenue | Estimated revenue over 3 days |
| 3 Day Cum. Funding Rate | Cumulative funding rate (3D) |
| 3 Day APR | Annualized return based on 3D rate |
| Previous Funding Rate | Last settled funding rate |
| Next Funding Rate | Predicted next funding rate |
| Open Interest | Total open interest |

**Features:**
- All columns sortable (ascending/descending)
- Position Size input for revenue simulation
- ~35 pages of symbols available
- Best for finding high-APR opportunities programmatically

### Spread Arbitrage Table

| Column | Description |
|--------|-------------|
| Symbol | Trading pair |
| Spread Rate | Current futures-spot spread |
| Daily Interest | Annualized daily spread interest |
| Yearly Interest | Annualized yearly return |
| Open Interest | Total OI |

## Options Data

```
URL: https://www.binance.com/en/eoptions-data/{SYMBOL}
Example: https://www.binance.com/en/eoptions-data/BTC
```

### Analysis Tabs

| Tab | Description | API Available |
|-----|-------------|:------------:|
| Overview | Top 5 OI/Volume, Put/Call ratios, Taker Flow | Partial |
| Open Interest & Volume | Historical OI and volume charts | Yes |
| Term Structure | Volatility term structure across expirations | No |
| Implied Volatility | IV surface and skew analysis | No |
| Max Pain | Strike price with maximum option seller profit | No |
| Exercised History | Historical exercise data | Yes |
| Volatility Index (BVOL) | BTC Volatility Index | No |

### Overview Tab Details

| Section | Metrics |
|---------|---------|
| Top 5 OI | Highest open interest contracts |
| Top 5 24hr Volume | Most actively traded contracts |
| Call vs Put (OI) | Call/Put ratio by open interest |
| Call vs Put (Volume) | Call/Put ratio by volume |
| OI & Volume History | Time series chart |
| Put/Call Ratio | Historical PCR chart |
| Group by Strike | OI/Volume grouped by strike price |
| Group by Expiration | OI/Volume grouped by expiry date |
| 24hr Taker Flow | Recent aggressive order flow |

### Volatility Index (BVOL)

Real-time BTC implied volatility index.

| Metric | Description |
|--------|-------------|
| Current Value | e.g., 57.84 |
| 24h Change | Percentage change |
| Daily Range | High-low range for the day |
| Monthly Range | High-low range for the month |

**Chart timeframes:** Time / 1m / 5m / 15m / 1H / 1D

## Heatmap

```
URL: https://www.binance.com/en/futures/crypto-heatmap/
```

Visual treemap for market-wide analysis. **No API available.**

### Filters

| Filter | Options |
|--------|---------|
| Contract Type | USDⓈ-M / COIN-M |
| Metric | Trading Volume / Open Interest / Market Cap |
| Performance Period | 24h % change (default) |
| Coin Count | Top 30 / Top 50 / Top 100 |

Treemap cell size represents the selected metric; color represents performance (green = positive, red = negative).

## Other Data Pages

### Real-Time Funding Rate
```
URL: https://www.binance.com/en/futures/funding-history/perpetual/real-time-funding-rate
```
Live funding rates for all perpetual contracts. Useful for monitoring funding rate changes across all symbols.

### Funding Rate History
```
URL: https://www.binance.com/en/futures/funding-history/perpetual/funding-fee-history
```
Historical funding rate data with date range selection.

### Insurance Fund History
```
URL: https://www.binance.com/en/futures/funding-history/perpetual/insurance-fund-history
```
Insurance fund balance changes over time.

### Index
```
URL: https://www.binance.com/en/futures/funding-history/perpetual/index
```
Index price composition and weights for each perpetual contract.

### Delivery Data
```
URL: https://www.binance.com/en/futures/funding-history/perpetual/delivery-data
```
Delivery/settlement information for quarterly contracts.

## Trading Insight

```
URL: https://www.binance.com/en/trading_insight/glass?id=22&token=BTC
```

Comprehensive chart-based analysis platform with multiple data categories, sentiment indicators, and smart flow signals. Token-specific views available via `token` query parameter.

### Categories

#### Exchange - Trading Data (16 charts)

| Chart | Description |
|-------|-------------|
| Price Index - Asia/Europe/America | Price index comparison across regions |
| Trade Volume by Region | Volume distribution across Asia/Europe/America |
| Price Fluctuation by Region | Regional price volatility comparison |
| Fund flow | Overall fund flow analysis |
| Fund flow - buy (large) | Large buy order flow |
| Fund flow - buy (medium) | Medium buy order flow |
| Fund flow - buy (small) | Small buy order flow |
| Fund flow - sell (large) | Large sell order flow |
| Fund flow - sell (medium) | Medium sell order flow |
| Fund flow - sell (small) | Small sell order flow |
| Fund flow - net inflow | Net inflow (buy - sell) across sizes |
| Margin Debt Growth (C) | Cross margin debt growth trend |
| Margin Debt Growth (U) | USDT margin debt growth trend |
| Margin Long-Short Positions Ratio (C) | Cross margin L/S ratio |
| Margin Long-short Positions Ratio (U) | USDT margin L/S ratio |
| Isolated Margin Borrow Amount Ratio | Isolated margin borrowing ratio |

#### Exchange - Futures Data (7 charts)

Same as Futures Trading Data charts: Open Interest, Top Trader L/S Ratio (Accounts/Positions), Long/Short Ratio, Taker Buy/Sell Volume, Basis, Funding rate.

#### Binance Square Data (3 charts)

| Chart | Description |
|-------|-------------|
| Popularity Index (Posts) | Social post volume trend for token |
| Popularity Index (Clicks) | Click/engagement trend for token |
| Fear and Greed Index | Market fear/greed sentiment indicator |

#### Kline Pattern (19 patterns)

Candlestick pattern recognition: Long Line Candle, Dragonfly Doji, Hikkake Pattern, Spinning Top, High-Wave Candle, Closing Marubozu, Rickshaw Man, Hanging Man, Gravestone Doji, Matching Low, Doji, Belt-hold, Long Legged Doji, Advance Block, Engulfing Pattern, Short Line Candle, Takuri, Separating Lines, Three Outside Up/Down.

#### ETF

| Chart | Description |
|-------|-------------|
| ETF net inflow | Crypto ETF net inflow/outflow tracking |

### Sidebar Widgets

#### Fear & Greed Index

| Field | Description |
|-------|-------------|
| Yesterday | Previous day's index value (0-100) with label (Extreme Fear/Fear/Neutral/Greed/Extreme Greed) |
| Last Week | Weekly average index value with label |

#### Popular Tab

Top 30 trending tokens ranked by social mention volume.

| Field | Description |
|-------|-------------|
| Rank | 1-30 position |
| Token | Symbol name |
| Mentions | Mention count with change (e.g., "+695") |
| Price Change | 24h percentage change |
| Price | Current price |

#### Smart Flow Tab

Top 30 tokens with smart money signals. Signal types:

| Signal Type | Example | Description |
|-------------|---------|-------------|
| Top holders buying | "+100.00% top holders are buying" | Percentage of top holders accumulating |
| Top traders buying | "+100.00% top traders are buying" | Percentage of top traders accumulating |
| Large buy orders | "50 large buy orders" | Count of large buy orders detected |
| New Rising Stars | "New Rising Stars" | Newly trending tokens |
| Volume surge | "Volume surged +165.05% in the last 1h" | Unusual volume increase |
| Price increase | "Price increased +4.50% in the last 4h" | Notable price movement |

## Futures Markets Overview

```
URL: https://www.binance.com/en/futures/markets/overview-um
```

Central dashboard for futures market analysis with real-time widgets and market data.

### Top Widgets

| Widget | Description |
|--------|-------------|
| Open Interest | OI for selected symbol with 24h Change %, USDT/currency toggle |
| 1h Long/Short Ratio | Short Account %, Long Account %, L/S Ratio value with visual gauge |
| Altcoin Week Index | Bitcoin vs Altcoin gauge (0-100 scale), indicates "Bitcoin week" or "Altcoin week" |
| News | Real-time Binance Square news feed with timestamps and links |

### Market Movers

| Section | Description |
|---------|-------------|
| Highest Searched (24h) | Top 5 most searched symbols with 24h change %, USDⓈ-M/COIN-M toggle |
| Highest Change (24h) | Top 5 biggest movers with 24h change %, USDⓈ-M/COIN-M toggle |

### Market Table

Tabs: **Favorites** / **USDⓈ-M Futures** / **COIN-M Futures**

**Filters:**

| Filter | Options |
|--------|---------|
| Category | All / various sector categories |
| 24h Volume | Range presets |
| 24h Change | Range presets |
| Range | Price range filters |
| Funding Rate | Rate range filters |

### Ranking Tab

```
URL: https://www.binance.com/en/futures/markets/ranking-um
```

| Ranking | Description |
|---------|-------------|
| Gainer (Top 10) | Highest 24h price increase |
| Loser (Top 10) | Highest 24h price decrease |
| 24h Volume | Highest trading volume |
| Funding Rate | Highest/lowest funding rates |

Toggle: USDⓈ-M / COIN-M

### Binance Futures Index

Composite cryptocurrency price index tracking USDⓈ-M futures market performance.

| Metric | Value |
|--------|-------|
| Constituents | 400+ |
| Rebalancing Frequency | Daily |
| Index Tabs | All Index / BTCDOM Index |

**Chart timeframes:** 1m / 3m / 5m / 15m / 30m / 1h / 2h / 4h / 6h / 12h / 1D / 1W / 1M

### Alpha Section

Multi-chain token data with chain filters:

| Chain | Description |
|-------|-------------|
| All | All chains combined |
| BSC | BNB Smart Chain tokens |
| Ethereum | Ethereum tokens |
| Solana | Solana tokens |
| Base | Base chain tokens |
| Sonic | Sonic chain tokens |
| Sui | Sui chain tokens |

## Binance Research

```
URL: https://www.binance.com/en/research
```

Professional research reports and market analysis.

| Section | Description |
|---------|-------------|
| Insights & Analysis | In-depth research articles |
| Project Reports | Token/project evaluation reports |
| Weekly Market Commentary | Weekly market overview |
| Monthly Market Insights | Monthly comprehensive analysis |

## Chart Indicators (TradingView)

Binance futures uses an embedded TradingView chart with full indicator support.

### Built-in Defaults
- **MA(7)**, **MA(25)**, **MA(99)** — Moving averages
- **Volume** — Trade volume bars

### Timeframes
`Time` / `1s` / `15m` / `1H` / `4H` / `1D` / `1W` (plus additional custom intervals)

### Chart Types
Candles / Line / Bars / Area

### Chart Modes
- **Original** — Binance native chart
- **TradingView** — Full TradingView with all standard indicators

### Available TradingView Indicators (common)
RSI, MACD, Bollinger Bands, Stochastic, Ichimoku Cloud, EMA, SMA, VWAP, ATR, ADX, OBV, Fibonacci Retracement, Pivot Points, Volume Profile, and 100+ more standard TradingView indicators.

## Agentic Use Cases

1. **Smart Money signal following** — Track Dominant Flow direction and magnitude, trigger trades when smart money consensus exceeds threshold
2. **Whale position tracking** — Monitor Whales tab for large position changes, alert on significant entries/exits
3. **Arbitrage opportunity scanning** — Scrape arbitrage data, filter by APR > threshold, auto-execute highest-return opportunities
4. **Options IV/Max Pain analysis** — Track implied volatility changes and max pain levels for price direction prediction
5. **BVOL-based strategy switching** — Switch between mean-reversion (low BVOL) and trend-following (high BVOL) strategies
6. **Sentiment analysis from trading data** — Combine L/S Ratio, Taker Volume, and OI data for market sentiment scoring
7. **Heatmap sector rotation** — Detect capital flow between sectors using heatmap performance data
8. **Funding rate monitoring** — Track real-time funding rates across all symbols, alert on extreme values
9. **Open Interest divergence** — Detect OI-price divergences as potential reversal signals
10. **Put/Call ratio contrarian signals** — Track extreme PCR values for contrarian entry signals
11. **Fear & Greed Index-based timing** — Use extreme fear readings as accumulation signals, extreme greed as distribution signals
12. **Smart Flow signal aggregation** — Monitor "top holders/traders buying" signals across tokens for early trend detection
13. **Fund flow analysis** — Track large buy/sell order flows and net inflows to detect institutional activity
14. **Margin data monitoring** — Track margin debt growth and L/S position ratios for leverage-based sentiment
15. **Kline pattern detection** — Automate candlestick pattern scanning across symbols for technical entry/exit signals
16. **Altcoin rotation timing** — Use Altcoin Week Index to time rotation between BTC and altcoin positions
17. **Social sentiment tracking** — Monitor Popularity Index (posts/clicks) and trending token mentions for early momentum signals
18. **ETF flow tracking** — Monitor crypto ETF net inflows/outflows for institutional sentiment

## References

- **UI selectors & navigation**: See [references/ui-structure.md](references/ui-structure.md) for Playwright selectors
- **API availability**: See [references/api-mapping.md](references/api-mapping.md) for endpoint availability and alternatives
- **Related skills**:
  - [binance-futures-advanced](../binance-futures-advanced/SKILL.md) — Advanced order types and position management
  - [binance-trading-bots](../binance-trading-bots/SKILL.md) — Automated trading bots (Arbitrage Bot)
  - [binance-copy-trading](../binance-copy-trading/SKILL.md) — Copy trading and leaderboard
