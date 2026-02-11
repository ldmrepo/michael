---
name: binance-copy-trading
description: Binance Copy Trading and Leaderboard guide for browsing top traders, configuring copy settings, and managing copy portfolios. Use when implementing copy trading features, analyzing trader performance from leaderboard, configuring copy parameters (ratio, amount, risk controls), or automating copy trading flows via browser automation.
---

# Binance Copy Trading

## Overview

Guide for Binance Copy Trading features — leaderboard browsing, copy configuration, and portfolio management. Covers both Futures and Spot copy trading. Primarily browser-automation driven as no public API exists for copy trading operations.

## Leaderboard

### Futures Leaderboard
```
https://www.binance.com/en/copy-trading
```

### Spot Leaderboard
```
https://www.binance.com/en/copy-trading/spot
```

### Trader Performance Metrics

| Metric | Futures | Spot | Description |
|--------|:-------:|:----:|-------------|
| PNL | Yes | Yes | Total profit/loss in USDT |
| ROI | Yes | Yes | Return on investment percentage |
| AUM | Yes | Yes | Assets under management |
| MDD | Yes | Yes | Maximum drawdown (30 days) |
| Sharpe Ratio | Yes | No | Risk-adjusted return measure |
| Days Leading Trading | No | Yes | How long trader has been leading |
| Copiers | Yes | Yes | Current/max copier count (e.g., "281/400") |

### Filters & Sorting (Futures)

| Filter | Options |
|--------|---------|
| Time Period | 7 Days / 30 Days / 90 Days |
| Sort By | PnL / ROI / Copiers / AUM |
| Smart Filter | AI-curated selection (checked by default) |
| Trader Search | Free-text name search |

### Advanced Filters (Futures)

| Filter | Type | Options |
|--------|------|---------|
| Time Range | Checkboxes | 7D, 30D (default), 90D, 180D |
| Tags | Multi-select | Top Performer, Money Maker, Most Resilient, Whale Manager, Solid Growth, Low Leverage |
| 30D PNL | Range slider | 0 – 5,000,000 |
| 30D ROI | Presets | >= 0%, >= 25%, >= 50%, >= 100% |
| 30D MDD | Presets | <= 10%, <= 30%, <= 50%, <= 70% |
| 30D Copy Trader PnL | Range slider | 0 – 5,000,000 |
| Days Trading | Presets | >= 30D, >= 60D, >= 90D, >= 180D |
| AUM (USDT) | Presets | >= 25,000, >= 100,000, >= 250,000, >= 500,000 |
| Min Copy Amount (USDT) | Presets | <= 10, <= 50, <= 100, <= 1,000 |
| API | Toggle | Show only API traders |
| Copy-ready Portfolios | Toggle | Show only with available slots |
| Hide Full Portfolios | Toggle | Hide maxed-out copier slots |
| Hide Lock-Up Period Portfolios | Toggle | Hide lock-up portfolios |

### Trader Card Elements

Each trader card displays:
- Profile name, avatar, and optional badge
- Copier count: "current / max" (e.g., "281 / 400")
- API tag (if applicable)
- Performance chart thumbnail
- Performance metrics (PNL, ROI, AUM, MDD, Sharpe Ratio)
- Action buttons: Mock / Copy (or Full if maxed)

**Copy button availability:** When copier slots are full (e.g., 400/400), the Copy button is replaced with a disabled "Full" button.

## Trader Profile Page

### URL
```
https://www.binance.com/en/copy-trading/lead-details/{TRADER_ID}?timeRange=30D
```

### Profile Information

| Section | Fields |
|---------|--------|
| Header | Name, bio, tags (API Trading, Top Performer, etc.) |
| Statistics | Days Trading, Copiers (current/max), Total Copiers, Mock Copiers, Closed Portfolios |
| Performance | ROI, PnL, Copier PnL, Sharpe Ratio, MDD, Win Rate, Win Positions, Total Positions |
| Lead Trader Overview | AUM, Profit Sharing %, Leading Margin Balance, Lock-up period, Minimum Copy Amount |
| Asset Preferences | Pie chart of token allocation (refreshed every 1-2 hours) |

### Profile Tabs

| Tab | Description |
|-----|-------------|
| Positions | Current open positions (may be set to private) |
| Position History | Past closed positions |
| Latest Records | Recent trading activity |
| Transfer History | Margin transfers |
| Copy Traders | List of copiers |

### Profile Actions
- **Copy** — Opens copy settings in new tab
- **Mock Copy** — Paper trade following
- **Compare** — Compare portfolio with others

## Copy Settings

### URL
```
https://www.binance.com/en/copy-trading/copy-setting?portfolioId={TRADER_ID}
```

### Copy Mode

| Mode | Description |
|------|-------------|
| Fixed Ratio | Copy proportional to leader's position size based on margin ratio |
| Fixed Amount | Copy with fixed USDT margin per order |

### Fixed Ratio Configuration

| Parameter | Range/Options | Description |
|-----------|--------------|-------------|
| Copy Amount | 1,000–300,000 USDT | Total capital allocated |
| Lock-up Period | 30 Days | Minimum commitment (not editable) |
| Symbol Preferences | Multi-select (99+ symbols) | Choose which symbols to copy |
| Remove Low-Liquidity Symbols | Toggle | Auto-exclude illiquid pairs |
| Total Stop Loss | USDT amount or % | Maximum total loss before stopping |

### Fixed Amount Configuration (extra field)

| Parameter | Range/Options | Description |
|-----------|--------------|-------------|
| Cost Per Order | 10–50,000 USDT | Fixed margin amount per trade |
| Copy Amount | 1,000–300,000 USDT | Total capital allocated |
| (Other settings same as Fixed Ratio) | | |

### Advanced Settings

| Parameter | Default | Options | Description |
|-----------|---------|---------|-------------|
| Existing Position Copy Mode | Copy Better Entries | Dropdown | How to handle leader's existing positions |
| Auto-Invest | Off | Toggle switch | Auto-reinvest profits |
| Margin Mode | Copy Leader's | Copy Leader's / Custom | Follow leader or set own margin mode |
| Leverage | Copy Leader's | Copy Leader's / Custom | Follow leader or set own leverage |
| Max Trade Slippage | Default | Default / Custom | Maximum acceptable slippage |
| Take Profit | — | 0–2,000% | Per-position TP percentage |
| Stop Loss | — | 0–95% | Per-position SL percentage |
| Max Cost per Order | — | 5–95% | Maximum % of copy amount per single trade |

### Confirmation Requirements
1. Enter copy amount (and cost per order for Fixed Amount mode)
2. Check "I have read and I agree to the User Service Agreement"
3. Click "Copy" button (disabled until requirements met)

## Copy Management

### URL
```
https://www.binance.com/en/copy-trading/copy-management
```

### Status Tabs

| Tab | Description |
|-----|-------------|
| Ongoing (N) | Active copy relationships |
| Closed (N) | Stopped copies |
| Mock Copy Trading (N) | Paper trade copies |

### Account Overview

| Metric | Description |
|--------|-------------|
| Total Margin Balance | Total margin in USDT |
| Total Wallet Balance | Total wallet in USDT |
| Total Realized PNL | Cumulative realized profit/loss |
| Net Profit | Overall net profit |

### Type Selector
Dropdown to switch between "Futures Copy" and "Spot Copy" views.

## API Availability

**No public REST API** exists for Binance Copy Trading. All operations require browser automation:

| Operation | API Available | Alternative |
|-----------|:------------:|-------------|
| Browse leaderboard | No | Browser automation |
| View trader profile | No | Browser automation |
| Start copying | No | Browser automation |
| Configure copy settings | No | Browser automation |
| Stop copying | No | Browser automation |
| View own copy positions | **Yes** | `GET /fapi/v2/positionRisk` |
| View own copy orders | **Yes** | `GET /fapi/v1/openOrders` |
| View account balance | **Yes** | `GET /fapi/v2/balance` |

## Browser Automation (Playwright)

### Key URLs
```
Futures Leaderboard:    https://www.binance.com/en/copy-trading
Spot Leaderboard:       https://www.binance.com/en/copy-trading/spot
Trader Profile:         https://www.binance.com/en/copy-trading/lead-details/{TRADER_ID}
Copy Settings:          https://www.binance.com/en/copy-trading/copy-setting?portfolioId={TRADER_ID}
Copy Management:        https://www.binance.com/en/copy-trading/copy-management
Compare Portfolios:     https://www.binance.com/en/copy-trading/compare/futures
```

### Copy Flow
1. Navigate to leaderboard
2. Browse/filter traders (Smart Filter is on by default)
3. Click "Copy" on a trader card → **opens new tab**
4. Switch to new tab with `browser_tabs`
5. Select mode: Fixed Ratio (default) or Fixed Amount
6. Enter copy amount (and cost per order for Fixed Amount)
7. Optionally configure symbol preferences and stop loss
8. Expand "Advanced Settings" for additional controls
9. Check terms agreement checkbox
10. Click "Copy" to confirm

### Important Patterns
- **New tab navigation:** Clicking trader cards and Copy buttons opens new tabs
- **Copier slot check:** Full portfolios show disabled "Full" button instead of "Copy"
- **Smart Filter default:** The leaderboard has Smart Filter checked by default
- **Combobox pattern:** Dropdowns use `combobox "Select an option"` role

For detailed UI selectors, see [references/ui-structure.md](references/ui-structure.md).
For API details, see [references/api-mapping.md](references/api-mapping.md).

## Agentic Use Cases

1. **Top trader screening** — Scrape leaderboard data, filter by Sharpe > 1.5 and MDD < 20%
2. **Auto-copy allocation** — Distribute capital across multiple traders based on performance
3. **Risk monitoring** — Monitor copy portfolio PnL, auto-stop if drawdown exceeds threshold
4. **Rebalancing** — Periodically re-evaluate traders and switch underperformers
5. **Performance tracking** — Log daily PnL/ROI for each copied trader
6. **Copier slot monitoring** — Watch for Full portfolios that open new slots
7. **Advanced filter automation** — Use advanced filters to find traders matching specific criteria (tags, AUM, MDD thresholds)
8. **Spot vs Futures comparison** — Compare Spot and Futures leader performance metrics

## References

- **API mapping details**: See [references/api-mapping.md](references/api-mapping.md) for complete endpoint reference
- **UI structure**: See [references/ui-structure.md](references/ui-structure.md) for Playwright selectors
- **Analytics & Smart Money**: See [binance-analytics](../binance-analytics/SKILL.md) for Smart Money trader analysis, Dominant Flow signals, Whale position tracking, and market sentiment data for evaluating copy trading candidates
