---
name: binance-trading-bots
description: Binance built-in trading bots configuration and automation guide. Covers Futures Grid, Spot Grid, Futures DCA, Position Snowball, Arbitrage Bot, Rebalancing Bot, Spot DCA, Futures TWAP, and Spot Algo Orders. Use when implementing automated trading strategies via browser automation, understanding bot parameters, or exploring bot-related API endpoints.
---

# Binance Trading Bots

## Overview

Guide for Binance's built-in trading bot features — configuration parameters, creation flows, and automation paths. Covers both browser automation (Playwright) and API availability for each bot type.

## Available Bot Types

| Bot Type | Asset | URL Path | Description |
|----------|-------|----------|-------------|
| Spot Grid | Spot | `/spot/grid/{SYMBOL}` | Buy low and sell high, 24/7 |
| Futures Grid | Futures | `/futures/grid/{SYMBOL}` | Automate longs and shorts |
| Position Snowball | Futures | `/futures/snowball/{SYMBOL}` | Compounding growth with floating profits |
| Futures DCA | Futures | `/futures/dca-bot/{SYMBOL}` | Auto-scale positions, turn losses to gains |
| Arbitrage Bot | Futures+Spot | `/futures/arbitrage/{SYMBOL}` | Delta neutral funding fee arbitrage |
| Rebalancing Bot | Spot | `/spot/rebalancing-bot/{SYMBOL}` | Smart multi-coin portfolio rebalancing |
| Spot DCA | Spot | `/spot/dca-bot/{SYMBOL}` | Lower average entry cost, profit from reversals |
| Futures TWAP | Futures | (Futures page) | Time-weighted average price execution |
| Futures VP | Futures | (API only) | Volume participation execution |
| Spot Algo Orders | Spot | (VIP portal) | Large order execution in smaller blocks |

## Spot Grid Bot

### Configuration Parameters

| Parameter | Options/Range | Description |
|-----------|--------------|-------------|
| Lower Price | Number | Lower bound of price range |
| Upper Price | Number | Upper bound of price range |
| Grid Mode | Arithmetic / Geometric | Price distribution between grids |
| Number of Grids | 2–170 | Number of grid levels |
| Investment | USDT/USDC amount | Total investment (currency selectable) |

### Advanced Settings

| Setting | Description |
|---------|-------------|
| Trailing Up | Auto-raise grid range when price breaks above upper bound |
| Grid Trigger | Start bot only when price reaches trigger |
| TP/SL | Take Profit / Stop Loss |
| Sell all BTC on stop | Sell base asset when bot stops (checked by default) |

## Futures Grid Bot

### Configuration Parameters

| Parameter | Options/Range | Description |
|-----------|--------------|-------------|
| Direction | Neutral / Long / Short | Grid trading direction |
| Lower Price | Number | Lower bound of price range |
| Upper Price | Number | Upper bound of price range |
| Grid Mode | Arithmetic / Geometric | Price distribution between grids |
| Number of Grids | 2–170 | Number of grid levels |
| Investment | USDT amount | Total margin allocated |
| Leverage | 1x–125x | Leverage multiplier |
| Margin Mode | Cross / Isolated | Margin isolation setting |

### Advanced Settings

| Setting | Description |
|---------|-------------|
| Trailing Up | Auto-raise grid range when price breaks above upper bound |
| Trailing Down | Auto-lower grid range when price breaks below lower bound |
| Grid Trigger Price | Only start the bot when price reaches trigger |
| TP/SL | Take Profit / Stop Loss |
| Close all positions on stop | Close all positions when bot stops |
| Auto-Add Margin on Bracket Change | Automatically add margin if leverage bracket changes |

## Position Snowball Bot

### Configuration Parameters

| Parameter | Options/Range | Description |
|-----------|--------------|-------------|
| Direction | Buy / Sell | Position direction |
| Add Order on Price Increase (%) | Percentage | Price increase % to trigger additional order |
| Leverage | 1x–125x | Leverage multiplier |
| Investment Amount | USDT | Initial margin amount |
| Auto-close on bracket | Checkbox (default: on) | Auto-close when hitting leverage bracket |

### Advanced Settings

| Setting | Description |
|---------|-------------|
| Trigger Price | Start bot at specific price (limit order entry instead of market) |
| Addition Order Slippage | Slippage tolerance for additional orders |
| TP/SL | Take Profit / Stop Loss |

### How It Works
1. Opens initial position (market order by default, limit via Trigger Price)
2. When price increases by set %, adds to position (snowball effect)
3. Compounds floating profits into larger position size
4. Auto-closes when leverage bracket is hit or TP/SL triggers

## Futures DCA Bot

### Configuration Parameters

| Parameter | Options/Range | Description |
|-----------|--------------|-------------|
| Direction | Long / Short | DCA direction |
| Price Deviation (%) | Percentage (default: 0.5%) | Price change to trigger DCA order |
| Take Profit Per Round (%) | Percentage (default: 1%) | Profit target per DCA round |
| Leverage | 1x–125x | Leverage multiplier |
| Base Order Margin | USDT | Initial order margin |
| DCA Order Margin | USDT | Each DCA order margin |
| Max DCA Orders | Number (default: 8) | Maximum DCA entries per round |

### Advanced Settings

| Setting | Default | Description |
|---------|---------|-------------|
| Price Deviation Multiplier | 1 | Multiplier for deviation between successive DCA orders |
| DCA Order Size Multiplier | 1.1 | Increase each subsequent DCA order size |
| Start Condition | — | Price or indicator-based trigger to start |
| Stop Condition | — | Conditions to stop the bot |
| Stop Loss | — | Maximum loss before stopping |
| Auto-Add Margin | off | Auto margin addition |

## Arbitrage Bot

### Configuration Parameters

| Parameter | Options/Range | Description |
|-----------|--------------|-------------|
| Portfolio | Futures+Spot pair | e.g., Buy BTCUSDT Perp + Sell BTC/USDT |
| Leverage | 2x (default) | Futures leg leverage |
| Investment | Base asset amount | e.g., ≥0.0037 BTC |
| Entry Spread | Percentage (default: -0.1%) | Spread threshold to enter position |

### Key Metrics Displayed

| Metric | Description |
|--------|-------------|
| Spread Rate | Current spread between futures and spot |
| 3d/7d/30d Funding APR | Funding rate annualized over different periods |
| Next Funding | Next funding rate + countdown timer |
| Recommended min holding | Minimum holding period for profitability |

### How It Works
- **Positive Carry**: When funding rate > 0, short futures + buy spot to earn funding fees
- **Reverse Carry**: When funding rate < 0, long futures + sell spot to earn funding fees
- Delta-neutral strategy — hedges price risk, earns from funding rate differential

## Rebalancing Bot

### Configuration Parameters

| Parameter | Options/Range | Description |
|-----------|--------------|-------------|
| Investment Currency | USDT / USDC | Currency for investment |
| Coin Allocation | Multiple coins with % allocation | Portfolio composition |
| Distribution | Equal / By Market Cap | How to distribute allocation |
| Total Investment | USDT/USDC amount | Total investment |
| Auto Rebalance | By Coin Ratio: X% | Rebalance trigger threshold |

### Advanced Settings

| Setting | Description |
|---------|-------------|
| Trigger Price | Start bot at specific price |
| Stop Trigger | Stop bot at specific price |
| Sell All Coins on Stop | Sell all coins when bot stops (checked by default) |

### AI Category Portfolios
Pre-built portfolios available: Main Coins, BNB Chain, Top Polkadot Tokens, Top Arbitrum Tokens, Storage Tokens, DeFi, Metaverse. Each can be copied to Manual settings.

## Spot DCA Bot

### Configuration Parameters

| Parameter | Options/Range | Description |
|-----------|--------------|-------------|
| Direction | Buy / Sell | DCA direction (tabs: "Buy BTC" / "Sell BTC") |
| Price Deviation (%) | Percentage (default: 1%) | Price change to trigger DCA |
| Take Profit (%) | Percentage (default: 1.5%) | TP target per round |
| TP Mode | Fix / Trailing | Fixed or trailing take profit |
| Base Order Size | USDT | Initial order size |
| DCA Order Size | USDT | Each DCA order size |
| Max DCA Orders | Number (default: 8) | Maximum DCA entries per round |

### Advanced Settings

| Setting | Default | Description |
|---------|---------|-------------|
| Trigger Price | — | Start bot at specific price |
| Price deviation multiplier | — | Multiplier for subsequent deviations |
| DCA order size multiplier | — | Increase subsequent DCA order sizes |
| Cooldown between rounds | 60 sec | Delay between rounds |
| Price Range (Lower/Upper) | — | Operating price bounds |
| Stop Loss (%) | — | Stop loss percentage |
| End bot on SL | off | End bot when stop loss triggers |

## API Availability

Most bot types are **UI-only** — no public REST API exists for creating/managing trading bots.

| Bot Type | Public API | Alternative |
|----------|-----------|-------------|
| Spot Grid | No | Browser automation |
| Futures Grid | No | Browser automation |
| Position Snowball | No | Browser automation |
| Futures DCA | No | Browser automation |
| Arbitrage Bot | No | Browser automation |
| Rebalancing Bot | No | Browser automation |
| Spot DCA | No | Browser automation |
| Futures TWAP | **Yes** | `POST /sapi/v1/algo/futures/newOrderTwap` |
| Futures VP | **Yes** | `POST /sapi/v1/algo/futures/newOrderVp` |
| Spot Algo Orders | Partial | Standard algo endpoints (VIP access) |

For detailed API mapping and Playwright selectors, see:
- **API details**: [references/api-mapping.md](references/api-mapping.md)
- **UI selectors**: [references/ui-structure.md](references/ui-structure.md)

## Browser Automation (Playwright)

### Navigation
```
Bot Hub:              https://www.binance.com/en/trading-bots
Spot Grid:            https://www.binance.com/en/trading-bots/spot/grid/{SYMBOL}
Futures Grid:         https://www.binance.com/en/trading-bots/futures/grid/{SYMBOL}
Position Snowball:    https://www.binance.com/en/trading-bots/futures/snowball/{SYMBOL}
Futures DCA:          https://www.binance.com/en/trading-bots/futures/dca-bot/{SYMBOL}
Arbitrage Bot:        https://www.binance.com/en/trading-bots/futures/arbitrage/{SYMBOL}
Rebalancing Bot:      https://www.binance.com/en/trading-bots/spot/rebalancing-bot/{SYMBOL}
Spot DCA:             https://www.binance.com/en/trading-bots/spot/dca-bot/{SYMBOL}
```

### Bot Creation Flow
1. Navigate to bot type URL
2. **Close welcome modal** if present (X button in dialog header)
3. Select "Manual" tab (vs "AI" or "Popular")
4. Select direction if applicable (Neutral/Long/Short or Buy/Sell)
5. Fill configuration parameters
6. Expand "Advanced" section for additional settings
7. Click "Create" button (or "Sign Terms" first time)
8. Confirm in the confirmation dialog

### Welcome Modal Handling
First visit to any bot page shows a welcome dialog that blocks interaction:
```javascript
// Close welcome modal
const closeBtn = page.locator('dialog img[cursor=pointer]').first();
if (await closeBtn.isVisible()) {
  await closeBtn.click();
}
```

## Agentic Use Cases

1. **Volatility-based Grid** — Auto-calculate grid range using ATR/Bollinger Bands, create via Playwright
2. **Multi-symbol DCA** — Run DCA bots across multiple symbols with different parameters
3. **Dynamic bot management** — Monitor running bots, stop losers, restart with adjusted parameters
4. **Funding rate arbitrage** — Use Arbitrage Bot when funding rate exceeds threshold
5. **TWAP execution** — Use API endpoint for large order execution to minimize slippage
6. **Portfolio rebalancing** — Use Rebalancing Bot with custom coin allocations and rebalance triggers
7. **Snowball accumulation** — Use Position Snowball during strong trends to compound profits
8. **DCA with trailing TP** — Use Spot DCA with trailing take profit mode for trend capture

## References

- **API mapping details**: See [references/api-mapping.md](references/api-mapping.md) for complete endpoint reference
- **UI structure**: See [references/ui-structure.md](references/ui-structure.md) for Playwright selectors
- **Analytics & Arbitrage**: See [binance-analytics](../binance-analytics/SKILL.md) for Arbitrage Data analysis (Funding Rate APR, Spread Arbitrage), funding rate monitoring, and market data for bot parameter optimization
