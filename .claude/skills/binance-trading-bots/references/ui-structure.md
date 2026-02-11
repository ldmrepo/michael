# Binance Trading Bots — UI Structure Reference

## Table of Contents
- [Navigation](#navigation)
- [Bot Hub Page](#bot-hub-page)
- [Spot Grid Bot](#spot-grid-bot)
- [Futures Grid Bot](#futures-grid-bot)
- [Position Snowball Bot](#position-snowball-bot)
- [Futures DCA Bot](#futures-dca-bot)
- [Arbitrage Bot](#arbitrage-bot)
- [Rebalancing Bot](#rebalancing-bot)
- [Spot DCA Bot](#spot-dca-bot)
- [Futures TWAP & VP](#futures-twap--vp)
- [Common UI Patterns](#common-ui-patterns)

---

## Navigation

### URLs
```
Bot Hub:              https://www.binance.com/en/trading-bots
Spot Grid:            https://www.binance.com/en/trading-bots/spot/grid/{SYMBOL}
Futures Grid:         https://www.binance.com/en/trading-bots/futures/grid/{SYMBOL}
Position Snowball:    https://www.binance.com/en/trading-bots/futures/snowball/{SYMBOL}
Futures DCA:          https://www.binance.com/en/trading-bots/futures/dca-bot/{SYMBOL}
Arbitrage Bot:        https://www.binance.com/en/trading-bots/futures/arbitrage/{SYMBOL}
Rebalancing Bot:      https://www.binance.com/en/trading-bots/spot/rebalancing-bot/{SYMBOL}
Spot DCA:             https://www.binance.com/en/trading-bots/spot/dca-bot/{SYMBOL}
Futures TWAP:         https://www.binance.com/en/futures/{SYMBOL}?orderType=TWAP
Spot Algo Orders:     https://www.binance.com/en/vip-portal/OTC-trading-platform?ref=OTC-Algo
Futures VP:           (API-only, docs link)
```

### Initial Dialogs
On first visit to any bot page, a **Welcome modal** (`dialog "modal"`) may appear:
- Title: "Welcome to {Bot Type}"
- Multi-step guide (3-4 steps) with images
- **Close button**: `img` (X icon) at top-right of modal header
- **Next button**: `button "Next"` to advance steps
- **Guide link**: `link "Guide"` to FAQ/support article
- Must close this modal before interacting with the form behind it

---

## Bot Hub Page

### URL
```
https://www.binance.com/en/trading-bots
```

### Header
| Element | Description |
|---------|-------------|
| Total Balance | Account balance display with eye toggle |
| Today's PNL | Daily profit/loss |
| `button "Trade Now"` | Quick trade navigation |
| `button "Bots Wallet"` | Bot wallet details |

### Category Tabs
```
tablist:
  tab "All" [selected by default]
  tab "Algos"
  tab "Sideways"
  tab "Bullish"
  tab "Bearish"
```

### Bot Type Cards (visible by default)
6 cards shown initially:
1. **Spot Grid** → `/en/trading-bots/spot/grid/BTCUSDT`
2. **Futures Grid** → `/en/trading-bots/futures/grid/BTCUSDT`
3. **Position Snowball** → `/en/trading-bots/futures/snowball/BTCUSDT`
4. **Futures DCA** → `/en/trading-bots/futures/dca-bot/BTCUSDT`
5. **Arbitrage Bot** → `/en/trading-bots/futures/arbitrage/BTCUSDT`
6. **Rebalancing Bot** → `/en/trading-bots/spot/rebalancing-bot/BTCUSDT`

### "More Bots" / "Less Bots"
Click `"More Bots"` to reveal additional bots:
7. **Spot DCA** → `/en/trading-bots/spot/dca-bot/BTCUSDT`
8. **Spot Algo Orders** → `/en/vip-portal/OTC-trading-platform?ref=OTC-Algo` (VIP portal)
9. **Futures TWAP** → `/en/futures/BTCUSDT?orderType=TWAP` (redirects to futures page)
10. **Futures VP** → External API docs link

### Bot Marketplace
| Element | Description |
|---------|-------------|
| Marketplace tabs | `tab "Spot Grid"`, `tab "Futures Grid"` [selected], `tab "Futures DCA"`, `tab "Arbitrage"` |
| Filters | USDⓈ-M, Market, Direction, Runtime (1-7 Days), ROI, Leverage (5-10x), 7D MDD |
| Sort | `combobox` → "Top PNL" |
| Bot cards | Symbol, Direction+Leverage tag, Copier count, PNL, ROI, Runtime, Min. Investment, Matched Trades, 7D MDD |
| Copy button | `button "Copy"` per card |

### Hot Coin Leaderboard
- **Trending Market Top 10**: Spot Grid / Futures Grid tabs
- **Volatility Top 10**: Spot Grid / Futures Grid tabs
- Filter: `combobox` USDⓈ-M

---

## Spot Grid Bot

### Tab Selection
```
tablist:
  tab "AI"
  tab "Popular" [selected by default]
  tab "Manual"
```

### Manual Configuration Panel

| Field | Selector | Notes |
|-------|----------|-------|
| **1. Price Range** | | |
| Lower Price | `spinbutton` (first) | Lower bound |
| Upper Price | `spinbutton` (second) | Upper bound |
| Auto Fill | Button with `img` + "Auto Fill" text | Auto-calculate from historical data |
| **2. Number of Grids** | | |
| Grid Count | `spinbutton` | |
| Grid Mode | `combobox` → "Arithmetic" | Options: Arithmetic / Geometric |
| Profit/grid | Read-only text | "Profit/grid(fees deducted): --" |
| **3. Investment** | | |
| Investment Currency | `combobox` → "USDT" | |
| Amount | `spinbutton` + "USDT" suffix | |
| Slider | `slider "slider"` | 0-100% of available |
| Available | Text: "Available: X.XX USDT" | Clickable for details |
| Transfer | `img` (transfer icon) | Navigate to transfer |

### Advanced Section (Expandable)

| Element | Type | Notes |
|---------|------|-------|
| Trailing Up | `checkbox` | Auto-raise grid when price breaks above |
| Grid Trigger | `checkbox` | Start bot only when price reaches trigger |
| TP/SL | `checkbox` | Take Profit / Stop Loss configuration |
| Sell all BTC on stop | `checkbox` [checked by default] | Sell base asset when bot stops |

### Action
- `button "Sign Terms"` (first time) or `button "Create"` (after terms signed)

---

## Futures Grid Bot

### Tab Selection
```
tablist:
  tab "AI"
  tab "Popular"
  tab "Manual" [selected when navigated with Manual tab]
```

### Direction Tabs
```
tablist:
  tab "Neutral" [selected by default]
  tab "Long"
  tab "Short"
```

### Manual Configuration Panel

| Field | Selector | Notes |
|-------|----------|-------|
| **1. Price Range** | | |
| Lower Price | `spinbutton` (first) | |
| Upper Price | `spinbutton` (second) | |
| Auto Fill | Button: `img` + "Auto Fill" | |
| **2. Number of Grids** | | |
| Grid Count | `spinbutton` | |
| Grid Mode | `combobox` → "Arithmetic" | Arithmetic / Geometric |
| Profit/grid | Read-only: "--" | "Profit/grid(fees deducted)" |
| **3. Investment** | | |
| Amount | `spinbutton` | USDT amount |
| Leverage | Button showing current (e.g. `"1x"`) with dropdown `img` | Opens leverage modal |
| Slider | `slider "slider"` | 0-100% |
| Auto-Add Margin | `checkbox "Auto-Add Margin on Bracket Change"` | |
| Available | Text: "Available: X USDT" | |
| Transfer | `img` | |
| **Summary** | | |
| Qty/Order | Read-only: "X.XXX BTC" | Per-grid quantity |
| Total Investment | Read-only: "X.XX USDT" | |
| Est. Liq. Price (Long) | Read-only: "--" | |
| Est. Liq. Price (Short) | Read-only: "--" | |
| **Margin Mode** | | |
| Mode selector | Clickable: "Cross" with `img` | Cross / Isolated |

### Advanced Section

| Element | Type | Notes |
|---------|------|-------|
| Trailing Up | `checkbox` | |
| Trailing Down | `checkbox` | (Futures only, not available in Spot Grid) |
| Grid Trigger | `checkbox` | |
| TP/SL | `checkbox` | |
| Close all positions on stop | `checkbox` [checked] | |

### Action
- `button "Sign Terms"` or `button "Create"`

---

## Position Snowball Bot

### Direction Tabs
```
tablist:
  tab "Buy" [selected by default]
  tab "Sell"
```

### Configuration Panel

| Field | Selector | Notes |
|-------|----------|-------|
| Add Order on Price Increase | | |
| Percentage | `spinbutton` + "%" suffix | Price increase % to trigger additional order |
| **Investment** | | |
| Leverage | Button showing current (e.g. `"5x"`) with `img` dropdown | |
| Amount | `spinbutton` + "USDT" suffix | |
| Investment with Leverage | Read-only: "--" | Calculated: Amount * Leverage |
| Available | Text: "Available: X USDT" | |
| Transfer | `img` | |
| Auto-close | `checkbox` [checked]: "Auto-close when hit leverage bracket" | |

### Advanced Section

| Element | Type | Notes |
|---------|------|-------|
| Trigger Price | `checkbox` + input | Start bot at specific price (limit order entry) |
| Addition Order Slippage | `checkbox` + input | Slippage tolerance for add orders |
| TP/SL | `checkbox` | Take Profit / Stop Loss |

### Action
- `button "Create"` [disabled until form filled]

### Welcome Modal Guide Steps
1. Open a position with the bot (market order by default, limit via Trigger Price)
2. Set snowballing rules
3. Run your bot
4. Manage or stop the bot

---

## Futures DCA Bot

### Tab Selection
```
tablist:
  tab "Popular"
  tab "Manual" [selected]
```

### Direction Tabs
```
tablist:
  tab "Long" [selected]
  tab "Short"
```

### Configuration Panel

| Field | Selector | Notes |
|-------|----------|-------|
| **Price Settings** | | |
| Clear All | `button "Clear All"` with `img` | Reset all price settings |
| Price Deviation | `spinbutton` (default: "0.5") + "%" | Price drop to trigger DCA |
| Take Profit Per Round | `spinbutton` (default: "1") + "%" | TP target per round |
| **Investment** | | |
| Leverage | Button showing current (e.g. `"10x"`) with `img` | |
| Base Order Margin | `spinbutton` + "USDT" | Initial order size |
| DCA Order Margin | `spinbutton` + "USDT" | Each DCA order size |
| Max DCA Orders | `spinbutton` (default: "8") | Maximum DCA entries |
| **Summary** | | |
| Invested Margin | Read-only: "--" | |
| Available | Text: "Available: X USDT" | |
| Est. Liq. Price | Read-only: "--" | |
| Auto-add Margin | `checkbox` | |

### Advanced Section

| Element | Type | Notes |
|---------|------|-------|
| **DCA Order Details** | | |
| Price Deviation Multiplier | `spinbutton` (default: "1") | Multiplier for deviation between DCA orders |
| DCA Order Size Multiplier | `spinbutton` (default: "1.1") | Increase each subsequent DCA order |
| Start Condition | `checkbox` + input | Price/indicator-based trigger |
| Stop Condition | `checkbox` + input | Auto-stop conditions |
| Stop Loss | `checkbox` + input | Maximum loss |

### Action
- `button "Preview"` [disabled] — Preview order distribution
- `button "Create (Long)"` or `button "Create (Short)"` [disabled until filled]

---

## Arbitrage Bot

### Portfolio Header

| Element | Description |
|---------|-------------|
| Portfolio pair | "B BTCUSDT Perp" + "S BTC/USDT" (Buy futures + Sell spot) |
| Symbol selector | `img` (clickable to change pair) |
| Spread Rate | Current spread percentage |
| 3d Funding APR | 3-day rate / annualized |
| 7d Funding APR | 7-day rate / annualized |
| 30d Funding APR | 30-day rate / annualized |
| Next Funding | Next funding rate + countdown |

### Configuration Panel

| Field | Selector | Notes |
|-------|----------|-------|
| **1. Portfolio** | | |
| Futures leg | "B BTCUSDT Perp" with leverage (e.g. `"2x"` clickable) | |
| Spot leg | "S BTC/USDT" | |
| APR metrics | 3d/7d/30d APR display | |
| Next Funding | Rate + countdown | |
| Recommended min holding | Clickable: e.g. "75 days" with `img` | |
| **2. Investment** | | |
| Amount | `textbox` with placeholder "≥0.0037" + "BTC" suffix | Denominated in base asset |
| Slider | `slider "slider"` | 0-100% |
| Available | Text: "X.XXXX BTC" | |
| Est. Position Size | Read-only: "≈ --" | |
| Fee level | Text link | |
| **Entry spread** | | |
| Enable | `checkbox` [checked] | |
| Spread value | `spinbutton` (default: "-0.1") + "%" | Entry spread threshold |
| Current spread | Text: "Current Entry Spread: X.XX%" | |
| Alert | Warning if set spread < current spread | |

### Action
- `button "Sign Terms"` or `button "Create"`

### Welcome Modal Guide Steps
1. Choose Arbitrage Portfolio (Positive Carry / Reverse Carry)
2. Input Investment Amount
3. Create Arbitrage Portfolio
4. Close Arbitrage Portfolio

---

## Rebalancing Bot

### Tab Selection
```
tablist:
  tab "AI" [selected by default]
  tab "Manual"
```

### AI Tab — Category Portfolios
Pre-built portfolio categories with Copy buttons:
- Main Coins (BTC, ETH)
- BNB Chain (BNB, INJ, GALA, +2)
- Top Polkadot Tokens (DOT, ASTR, KSM, +2)
- Top Arbitrum Tokens (ARB, GMX, MAGIC, +1)
- Storage Tokens (FIL, STX, AR, +1)
- DeFi (UNI, LDO, AAVE, +1)
- Metaverse (SAND, MANA, AXS, +1)

Each card shows: 7D PNL, 30D PNL, 180D PNL, coin icons, `button "Copy"`, "Copy parameters to Manual settings" link.

### Manual Tab — Configuration Panel

| Field | Selector | Notes |
|-------|----------|-------|
| **Investment Currency** | | |
| Currency tabs | `tab "Invest USDT"` [selected] / `tab "Invest USDC"` | |
| **1. Allocation** | | |
| Add Coins | `"Add Coins"` button | Opens coin selector |
| Distribution | `radio "Equal"` [checked] / `radio "By Market Cap"` | |
| Coin rows | Numbered (1, 2, ...) | |
| Coin selector | `combobox` per row with coin icon + name | e.g. "BTC", "ETH" |
| Allocation % | `textbox` per row with +/- buttons (`img`) | e.g. "50%" |
| Remove coin | `img` (X icon) per row | |
| Remaining | Text: "Remaining allocation: X% / Target: 100%" | |
| **2. Invest Coin** | | |
| Total Investment | `spinbutton` + "USDT" suffix | |
| Slider | `slider "slider"` | 0-100% |
| Available | Text: "X.XX USDT" | |
| Transfer | `img` | |
| **Auto Rebalance** | | |
| Rebalance rule | Clickable: "By Coin Ratio: 10%" with `img` | Opens rebalance config |

### Advanced Section

| Element | Type | Notes |
|---------|------|-------|
| Trigger Price | `checkbox "Trigger Price"` | Start at specific price |
| Stop Trigger | `checkbox "Stop Trigger"` | Stop at specific price |
| Sell All Coins on Stop | `checkbox` [checked] | Sell all on bot stop |

### Action
- `button "Create"` [disabled until filled]

---

## Spot DCA Bot

### Direction Tabs
```
tablist:
  tab "Buy BTC" [selected]
  tab "Sell BTC"
```
Note: Tab labels include the base asset name (e.g., "Buy BTC", "Sell BTC").

### Configuration Panel

| Field | Selector | Notes |
|-------|----------|-------|
| **1. Price Settings** | | |
| Price Deviation | `spinbutton` (default: "1") + "%" | Price change to trigger DCA |
| Take Profit | `spinbutton` (default: "1.5") + "%" | TP target |
| TP Mode | Clickable: "Fix" with `img` | Fix / Trailing |
| **2. Investment** | | |
| Base Order Size | `spinbutton` + "USDT" | Initial order |
| DCA Order Size | `spinbutton` + "USDT" | Each DCA order |
| Max DCA Orders | `spinbutton` (default: "8") | |
| Available | Text: "X.XX USDT" | |
| Total Investment | Read-only: "-- USDT" | |

### Advanced Section (Expandable)

| Element | Selector | Notes |
|---------|----------|-------|
| Trigger Price | `spinbutton` + "USDT" | Start bot at specific price |
| Price deviation multiplier | `spinbutton` | Multiplier for subsequent deviations |
| DCA order size multiplier | `spinbutton` | Increase subsequent DCA sizes |
| Cooldown between rounds | `spinbutton` (default: "60") + "Sec" | Delay between rounds |
| **Price Range** | | |
| Lower | `spinbutton` | Lower price bound |
| Upper | `spinbutton` | Upper price bound |
| Stop Loss | `spinbutton` + "%" | |
| End bot on SL | `checkbox`: "End the bot once stop loss is triggered" | |

### Action
- `button "Create"` [disabled until filled]

### Welcome Modal Guide Steps
1. Set up Spot DCA (direction, price deviation, take profit, amounts)
2. Run Spot DCA
3. End Spot DCA

---

## Futures TWAP & VP

Futures TWAP and VP are accessed through the main Futures trading page, not the Trading Bots page.

### TWAP
- **URL**: `https://www.binance.com/en/futures/{SYMBOL}?orderType=TWAP`
- Redirects to Futures trading page with TWAP order type pre-selected
- See `binance-futures-advanced` skill for TWAP order form details

### Futures VP
- **API-only**: No dedicated UI page
- See `binance-futures-advanced` skill for VP API endpoint details

### Spot Algo Orders
- **URL**: `https://www.binance.com/en/vip-portal/OTC-trading-platform?ref=OTC-Algo`
- VIP portal feature — requires VIP status
- Not accessible via standard trading interface

---

## Common UI Patterns

### Tab Structure
All bot creation pages share a common tab structure:
```
tablist:
  tab "AI" or tab "Popular"    — AI/community recommended configs
  tab "Manual"                  — Manual parameter entry
```

### Leverage Modal
Triggered by clicking leverage button (e.g., "1x", "5x", "10x"):
- Slider for leverage selection
- Direct input field
- Max leverage depends on symbol and bracket
- `button "Confirm"` to apply

### Symbol Selector
- Located at top of page: `heading "{SYMBOL}"` (e.g., "BTCUSDT")
- Click `img` next to heading to open symbol search/filter
- Symbol change updates the URL

### Market Data Header (Spot Bots)
For Spot Grid, Rebalancing Bot, Spot DCA:
- 24h Change, 24h High, 24h Low, 24h Volume (base + quote)
- TradingView chart with timeframe selectors

### Market Data Header (Futures Bots)
For Futures Grid, Position Snowball, Futures DCA:
- Current price + 24h change %
- Perp tag with tooltip
- TradingView chart

### Running Bots Panel
Below the bot creation panel:
| Element | Description |
|---------|-------------|
| Bot type filter | `combobox` → current bot type name |
| Running tab | `tab "Running"` [selected] |
| History tab | `tab "History"` |
| PNL Analysis tab | `tab "PNL Analysis"` |
| Hide Other Pairs | `checkbox "Hide Other Pairs"` |
| Data refresh | "Data refreshes in Xs" countdown |
| Bot rows | Symbol, Direction, PnL, metrics, Stop button |

### Bottom Navigation Bar (Futures Bots)
```
Trading Bots | Trade | All Orders
```

### Ticker Bar
Scrolling ticker at bottom showing symbol prices with change % across all pairs.

### Welcome Modal Close Pattern
```javascript
// Close welcome modal that appears on first visit
const closeBtn = page.locator('dialog img[cursor=pointer]').first();
if (await closeBtn.isVisible()) {
  await closeBtn.click();
}
```
