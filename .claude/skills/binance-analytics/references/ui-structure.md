# Binance Analytics — UI Structure Reference

## Table of Contents
- [Smart Money Pages](#smart-money-pages)
- [Futures Trading Data](#futures-trading-data)
- [Arbitrage Data](#arbitrage-data)
- [Options Data](#options-data)
- [Heatmap](#heatmap)
- [Trading Insight](#trading-insight)
- [Futures Markets Overview](#futures-markets-overview)
- [Binance Research](#binance-research)
- [Other Data Pages](#other-data-pages)

---

## Smart Money Pages

### Top Traders Leaderboard

```
URL: https://www.binance.com/en/smart-money
```

| Element | Selector | Notes |
|---------|----------|-------|
| Trader cards | Card list in main content | Each card shows name, PnL, ROI, status |
| Period filter | Tabs or dropdown | 7D / 30D / 90D |
| Sort options | Clickable headers or dropdown | PnL / ROI / Assets |
| Subscribe button | `button` on trader card | Follow/unfollow trader |
| Position status | Badge text | "In Position" / "No Position" / "Private" |

### Smart Signal List

```
URL: https://www.binance.com/en/smart-money (Signals tab)
```

| Element | Selector | Notes |
|---------|----------|-------|
| Symbol list | Table rows | Each row = one symbol |
| Dominant Flow direction | "B" (green) / "S" (red) badge | Buy or Sell |
| Dominant Flow amount | Text next to direction | Dollar value |
| Period filter | Tab buttons | `30m` / `1h` / `24h` / `7D` / `All` |

### Smart Signal Detail

```
URL: https://www.binance.com/en/smart-money/signal/{SYMBOL}
Query params: ?timeRange=30m&side=BOTH&sortBy=TIME&sortOrder=DESC&page=1
```

| Element | Selector | Notes |
|---------|----------|-------|
| Traders tab | `tab "Traders"` | Default tab |
| Whales tab | `tab "Whales"` | Large position holders |
| Overview section | Container at top | Total Positions, L/S Ratio |
| Total Positions | Text | Combined long + short count |
| Notional L/S Ratio | Progress bar + text | Visual ratio display |
| Long section | Left panel | Current Positions, Avg Entry, PnL, Profitable % |
| Short section | Right panel | Same metrics as Long |
| Time range selector | Buttons | `30m` / `1h` / `24h` / `7D` / `All` |
| Side filter | Buttons or dropdown | `BOTH` / `LONG` / `SHORT` |
| Sort selector | Dropdown | `TIME` / `PNL` / `ENTRY_PRICE` |
| Sort order | Toggle button | ASC / DESC |
| Trader history table | Table below overview | Individual trader entries |
| Pagination | `button` elements | Page navigation |

### Trader History Row

| Field | Description |
|-------|-------------|
| Trader name | Anonymized or public name |
| Direction | Long / Short badge |
| Entry Price | Position entry price |
| Current Price | Current mark price |
| Unrealized PnL | Profit/loss amount |
| Time | Entry timestamp |

---

## Futures Trading Data

```
URL: https://www.binance.com/en/futures/funding-history/perpetual/trading-data
```

### Page Layout

| Element | Selector | Notes |
|---------|----------|-------|
| Symbol selector | Dropdown / search | Default: BTCUSDT |
| Contract type toggle | Tab or button group | USDⓈ-M / COIN-M |
| Chart type selector | Tab buttons | 8 chart types |
| Interval selector | `combobox` or button group | Per-chart interval selection |
| View mode toggle | Button | Single / Combined |
| Chart area | Canvas / SVG element | TradingView-style charts |

### Chart Type Selectors

| Chart | Tab Text |
|-------|----------|
| Open Interest | "Open Interest" |
| Top Trader L/S Ratio (Accounts) | "Top Trader Long/Short Ratio (Accounts)" |
| Top Trader L/S Ratio (Positions) | "Top Trader Long/Short Ratio (Positions)" |
| Long/Short Ratio | "Long/Short Ratio" |
| Taker Buy/Sell Volume | "Taker Buy/Sell Volume" |
| Basis | "Basis" |
| Funding Rate | "Funding Rate" |
| OI to Market Cap Ratio | "OI to Market Cap Ratio" |

### Interval Buttons

All charts share the same interval options:
```
5m | 15m | 30m | 1h | 2h | 4h | 6h | 12h | 1d
```

Each interval is a clickable button or combobox option. Default varies by chart.

---

## Arbitrage Data

```
URL: https://www.binance.com/en/futures/funding-history/perpetual/arbitrage-data
```

### Page Layout

| Element | Selector | Notes |
|---------|----------|-------|
| Tab: Funding Rate Arbitrage | Tab button | Default tab |
| Tab: Spread Arbitrage | Tab button | Alternative view |
| Position Size input | `textbox` | User-configurable simulation value |
| Data table | `table` | Sortable columns |
| Pagination | Page buttons | ~35 pages |
| Sort headers | Clickable column headers | Toggle ASC/DESC |

### Funding Rate Arbitrage Table Columns

| Column Header | Sortable | Description |
|---------------|:--------:|-------------|
| Symbol | Yes | Trading pair name |
| 3 Day Revenue | Yes | Simulated revenue based on Position Size |
| 3 Day Cum. Funding Rate | Yes | Cumulative funding rate |
| 3 Day APR | Yes | Annualized percentage return |
| Previous Funding Rate | Yes | Last settled rate |
| Next Funding Rate | Yes | Predicted next rate |
| Open Interest | Yes | Total OI in USDT |

### Spread Arbitrage Table Columns

| Column Header | Sortable | Description |
|---------------|:--------:|-------------|
| Symbol | Yes | Trading pair |
| Spread Rate | Yes | Futures-spot spread |
| Daily Interest | Yes | Daily return estimate |
| Yearly Interest | Yes | Annualized return |
| Open Interest | Yes | Total OI |

---

## Options Data

```
URL: https://www.binance.com/en/eoptions-data/{SYMBOL}
Example: https://www.binance.com/en/eoptions-data/BTC
```

### Tab Navigation

| Tab | Selector |
|-----|----------|
| Overview | Tab button (default) |
| Open Interest & Volume | Tab button |
| Term Structure | Tab button |
| Implied Volatility | Tab button |
| Max Pain | Tab button |
| Exercised History | Tab button |
| Volatility Index (BVOL) | Tab button |

### Overview Tab Elements

| Element | Selector | Notes |
|---------|----------|-------|
| Top 5 OI table | Table | Highest open interest contracts |
| Top 5 24hr Volume table | Table | Most active contracts |
| Call vs Put (OI) | Chart / progress bar | Visual ratio |
| Call vs Put (Volume) | Chart / progress bar | Visual ratio |
| OI & Volume History | Chart | Time series |
| Put/Call Ratio | Chart | Historical PCR |
| Group by Strike | Chart | Bar chart by strike price |
| Group by Expiration | Chart | Bar chart by expiry |
| 24hr Taker Flow | Table / chart | Recent aggressive flow |

### BVOL Tab Elements

| Element | Selector | Notes |
|---------|----------|-------|
| Current BVOL value | Large text | e.g., "57.84" |
| 24h Change | Colored text | Green/red percentage |
| Daily Range | Text | High - Low |
| Monthly Range | Text | High - Low |
| Timeframe selector | Button group | `Time` / `1m` / `5m` / `15m` / `1H` / `1D` |
| BVOL chart | Canvas / SVG | Historical volatility index chart |

### Max Pain Tab Elements

| Element | Selector | Notes |
|---------|----------|-------|
| Expiry selector | Dropdown | Select expiration date |
| Max Pain price | Highlighted value | Strike with maximum seller profit |
| Strike distribution | Bar chart | Call/Put OI by strike |
| Current price marker | Vertical line on chart | Current BTC price reference |

---

## Heatmap

```
URL: https://www.binance.com/en/futures/crypto-heatmap/
```

### Filter Controls

| Element | Selector | Notes |
|---------|----------|-------|
| Contract type | Toggle / tabs | USDⓈ-M / COIN-M |
| Metric selector | Dropdown or buttons | Trading Volume / Open Interest / Market Cap |
| Performance period | Dropdown or buttons | Default: 24h % |
| Coin count | Dropdown or buttons | Top 30 / Top 50 / Top 100 |

### Treemap Display

| Element | Description |
|---------|-------------|
| Cell size | Proportional to selected metric |
| Cell color | Green = positive performance, Red = negative |
| Cell label | Symbol name + performance % |
| Click action | Navigate to symbol detail or chart |

---

## Trading Insight

```
URL: https://www.binance.com/en/trading_insight/glass?id=22&token=BTC
```

### Page Layout

| Element | Selector | Notes |
|---------|----------|-------|
| Search box | `textbox "Search"` | Token search |
| Token selector | Clickable element with token name | e.g., "BTC/USDT" with price and change % |
| Chart timeframe | `tab "1d"` (in tablist) | Chart period selector |
| Description tab | `tab "Description"` | Chart description |
| More Data Insights tab | `tab "More Data Insights"` | Additional data |

### Left Sidebar — Category Navigation

| Category | Selector | Sub-items |
|----------|----------|-----------|
| Exchange - Trading Data | `generic` with cursor=pointer | Expandable, 16 sub-items |
| Exchange - Futures Data | `generic` with cursor=pointer | Expandable, 7 sub-items |
| Binance Square Data | `generic` with cursor=pointer | Expandable, 3 sub-items |
| Kline Pattern | `generic` with cursor=pointer | Expandable, 19 sub-items |
| ETF | `generic` with cursor=pointer | Expandable, 1 sub-item |

Each category has a chevron icon (img) indicating expand/collapse state.

### Exchange - Trading Data Sub-items

| Item | Selector |
|------|----------|
| Price Index - Asia/Europe/America | Clickable `generic` element |
| Trade Volume by Region | Clickable `generic` element |
| Price Fluctuation by Region | Clickable `generic` element |
| Fund flow | Clickable `generic` element |
| Fund flow - buy (large) | Clickable `generic` element |
| Fund flow - buy (medium) | Clickable `generic` element |
| Fund flow - buy (small) | Clickable `generic` element |
| Fund flow - sell (large) | Clickable `generic` element |
| Fund flow - sell (medium) | Clickable `generic` element |
| Fund flow - sell (small) | Clickable `generic` element |
| Fund flow - net inflow | Clickable `generic` element |
| Margin Debt Growth (C) | Clickable `generic` element |
| Margin Debt Growth (U) | Clickable `generic` element |
| Margin Long-Short Positions Ratio (C) | Clickable `generic` element |
| Margin Long-short Positions Ratio (U) | Clickable `generic` element |
| Isolated Margin Borrow Amount Ratio | Clickable `generic` element |

### Exchange - Futures Data Sub-items

| Item | Selector |
|------|----------|
| Open Interest | Clickable `generic` element |
| Top Trader Long/Short Ratio (Accounts) | Clickable `generic` element |
| Top Trader Long/Short Ratio (Positions) | Clickable `generic` element |
| Long/Short Ratio | Clickable `generic` element |
| Taker Buy/Sell Volume | Clickable `generic` element |
| Basis | Clickable `generic` element |
| Funding rate | Clickable `generic` element |

### Binance Square Data Sub-items

| Item | Selector |
|------|----------|
| Popularity Index (Posts) | Clickable `generic` element |
| Popularity Index (Clicks) | Clickable `generic` element |
| Fear and Greed Index | Clickable `generic` element |

### Kline Pattern Sub-items

19 candlestick patterns, each a clickable `generic` element:
Long Line Candle, Dragonfly Doji, Hikkake Pattern, Spinning Top, High-Wave Candle, Closing Marubozu, Rickshaw Man, Hanging Man, Gravestone Doji, Matching Low, Doji, Belt-hold, Long Legged Doji, Advance Block, Engulfing Pattern, Short Line Candle, Takuri, Separating Lines, Three Outside Up/Down.

### ETF Sub-items

| Item | Selector |
|------|----------|
| ETF net inflow | Clickable `generic` element |

### Right Sidebar Elements

| Element | Selector | Notes |
|---------|----------|-------|
| Fear & Greed Index section | Container with "Fear & Greed Index" text | Shows Yesterday and Last Week values |
| Yesterday value | Nested `generic` with label "Yesterday" | Value (0-100) + label (Extreme Fear/Fear/Neutral/Greed/Extreme Greed) |
| Last Week value | Nested `generic` with label "Last Week" | Same structure as Yesterday |
| Popular tab | `tab "Popular"` | Default selected |
| Smart Flow tab | `tab "Smart Flow"` | Alternative view |

### Popular Tab Row Structure

| Element | Description |
|---------|-------------|
| Rank number | Numeric position (1-30) |
| Token name | Symbol (e.g., "KAITO") |
| Mention change | e.g., "Mention +695" |
| Price change | Percentage, colored (e.g., "+3.25%") |
| Price | Current price value |

### Smart Flow Tab Row Structure

| Element | Description |
|---------|-------------|
| Rank number | Numeric position (1-30) |
| Token name | Symbol (e.g., "COW") |
| Signal text | Smart money signal description |
| Price change | Percentage, colored |
| Price | Current price value |

**Signal text patterns:**
- `+XX.XX% top holders are buying`
- `+XX.XX% top traders are buying`
- `N large buy orders`
- `New Rising Stars`
- `Volume surged +XX.XX% in the last Xh`
- `Price increased +XX.XX% in the last Xh`

---

## Futures Markets Overview

```
URL: https://www.binance.com/en/futures/markets/overview-um
```

### Top Navigation Tabs

| Tab | URL | Notes |
|-----|-----|-------|
| Market | `/en/futures/markets/overview-um` | Default, selected |
| USDⓈ-M | `/en/futures/funding-history/perpetual/trading-data` | Links to trading data |
| COIN-M | `/en/futures/funding-history/quarterly/trading-data` | Links to COIN-M data |
| Options | `/en/eoptions-data/ETHUSDT` | Links to options data |

### Top Widgets Row

| Widget | Selector | Notes |
|--------|----------|-------|
| Open Interest | Link "Open Interest" + `combobox` selectors | Symbol selector + USDT/currency toggle, shows OI value + 24h Change % |
| 1h Long/Short Ratio | Link "1h Long/Short Ratio" + `combobox` | Symbol selector, shows Short %, Long %, L/S Ratio with gauge image |
| Altcoin Week Index | Container with "Altcoin Week Index" text | Gauge image (0-100), "Bitcoin" and "Altcoin" labels, value text |
| News | Container with "News" text | Scrolling list of Binance Square news links with timestamps |

### Market Movers Widgets

| Widget | Selector | Notes |
|--------|----------|-------|
| Highest Searched (24h) | Container with icon + "Highest Searched" text | `combobox` for USDⓈ-M/COIN-M toggle, top 5 items with symbol + 24h change % |
| Highest Change (24h) | Container with icon + "Highest Change" text | Same structure as Highest Searched |

### Market Table Area

| Element | Selector | Notes |
|---------|----------|-------|
| Overview tab | `tab "Overview"` (selected by default) | Market overview table |
| Ranking tab | `tab "Ranking"` | Rankings view |
| Favorites sub-tab | `tab "Favorites"` | User's watchlist |
| USDⓈ-M Futures sub-tab | `tab "USDⓈ-M Futures"` (selected) | Default view |
| COIN-M Futures sub-tab | `tab "COIN-M Futures"` | Alternative contracts |
| Search box | `textbox "Search"` | Symbol search |
| Filter icon | `img` (cursor=pointer) | Additional filter toggle |

### Filter Dropdowns

| Filter | Selector | Notes |
|--------|----------|-------|
| Category | `combobox` with "Category" / "All" text | Sector category filter |
| 24h Volume | `combobox` with "24h Volume" / "All" text | Volume range filter |
| 24h Change | `combobox` with "24h Change" / "All" text | Change range filter |
| Range | `combobox` with "Range" / "All" text | Price range filter |
| Funding Rate | `combobox` with "Funding Rate" / "All" text | Funding rate filter |

### Binance Futures Index Section

| Element | Selector | Notes |
|---------|----------|-------|
| All Index tab | `tab "All Index"` (selected) | All USDⓈ-M index |
| BTCDOM Index tab | `tab "BTCDOM Index"` | BTC dominance index |
| Constituents | Text "400+" | Number of index components |
| Rebalancing Frequency | Text "Daily" | Rebalance schedule |
| Daily Range | Text with high/low values | Today's range |
| 1 Month Range | Text with high/low values | Monthly range |
| Index value | Large text (e.g., "0.4595310 USDT") | Current index value |
| Change % | Colored text (e.g., "-1.69%") | 24h change |
| Chart timeframes | Clickable elements: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1D, 1W, 1M | Chart period selectors |
| Learn more link | `link "Learn more"` | FAQ documentation |
| Trading Data link | `link "Trading Data"` | Links to index trading data page |

### Heatmap Link

| Element | Selector | Notes |
|---------|----------|-------|
| Heatmap | `link "Heatmap"` | Links to `/en/futures/crypto-heatmap/` |

### Alpha Section

| Element | Selector | Notes |
|---------|----------|-------|
| All tab | `tab "All"` (selected) | All chains |
| BSC tab | `tab "BSC"` | BNB Smart Chain |
| Ethereum tab | `tab "Ethereum"` | Ethereum chain |
| Solana tab | `tab "Solana"` | Solana chain |
| Base tab | `tab "Base"` | Base chain |
| Sonic tab | `tab "Sonic"` | Sonic chain |
| Sui tab | `tab "Sui"` | Sui chain |
| Search box | `textbox "input field"` | Token search |

---

## Binance Research

```
URL: https://www.binance.com/en/research
```

| Element | Description |
|---------|-------------|
| Insights & Analysis section | Research articles list |
| Project Reports section | Token evaluation reports |
| Category navigation | Filter by research type |
| Search | Content search |

---

## Other Data Pages

### Real-Time Funding Rate
```
URL: https://www.binance.com/en/futures/funding-history/perpetual/real-time-funding-rate
```
- Symbol list with current funding rate
- Countdown to next funding settlement
- Sortable by rate value

### Funding Rate History
```
URL: https://www.binance.com/en/futures/funding-history/perpetual/funding-fee-history
```
- Symbol selector
- Date range picker
- Historical funding rate table

### Insurance Fund History
```
URL: https://www.binance.com/en/futures/funding-history/perpetual/insurance-fund-history
```
- Chart showing fund balance over time
- Table with daily changes

### Index
```
URL: https://www.binance.com/en/futures/funding-history/perpetual/index
```
- Symbol selector
- Index composition table (exchange weights)
- Current index price

### Delivery Data
```
URL: https://www.binance.com/en/futures/funding-history/perpetual/delivery-data
```
- Quarterly contract delivery schedule
- Historical delivery prices
