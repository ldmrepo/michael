---
name: binance-futures-advanced
description: Binance USDⓈ-M Futures advanced order types, margin settings, and position configuration guide. Use when implementing advanced futures trading features like TP/SL, Trailing Stop, Post-Only, TWAP, Scaled Orders, margin mode switching (Cross/Isolated), position mode (Hedge/One-Way), leverage changes, or Multi-Assets Mode via API or browser automation.
---

# Binance Futures Advanced

## Overview

Guide for Binance USDⓈ-M Futures advanced trading features — order types, margin/position settings, and their API mappings. Covers both REST API endpoints and Playwright browser automation paths.

## Order Types & API Mapping

### Standard Orders — `POST /fapi/v1/order`

| UI Tab | API `type` | Required Params |
|--------|-----------|-----------------|
| Limit | `LIMIT` | `timeInForce`, `quantity`, `price` or `priceMatch` |
| Market | `MARKET` | `quantity` |
| Post Only | `LIMIT` with `timeInForce=GTX` | `quantity`, `price` |

### Conditional Orders — `POST /fapi/v1/algoOrder` (since 2025-12-09)

**Critical:** Conditional orders MUST use `POST /fapi/v1/algoOrder` with `algoType=CONDITIONAL`. The old `/fapi/v1/order` returns error `-4120`. Use `triggerPrice` (not `stopPrice`).

| UI Tab | API `type` | Required Params |
|--------|-----------|-----------------|
| Stop Limit | `STOP` | `quantity`, `triggerPrice`, `price` or `priceMatch` |
| Stop Market | `STOP_MARKET` | `triggerPrice`, optional `closePosition` |
| Conditional | `STOP` or `STOP_MARKET` | UI-only: Limit/Market selector determines which API type to use |
| Trailing Stop | `TRAILING_STOP_MARKET` | `callbackRate` (0.1-10%), optional `activatePrice` |

### Algo Execution Orders

| UI Feature | API Endpoint | Key Params |
|-----------|-------------|------------|
| TWAP | `POST /sapi/v1/algo/futures/newOrderTwap` | `symbol`, `side`, `quantity`, `duration` (300-86400s) |
| VP | `POST /sapi/v1/algo/futures/newOrderVp` | `symbol`, `side`, `quantity`, `urgency` (LOW/MEDIUM/HIGH) |
| Scaled Order | No dedicated API — implement via `POST /fapi/v1/batchOrders` with calculated price ladder. UI supports Size Distribution: Flat/Ascending/Descending/Random(±5%), Order Count: 2-50 |

### TP/SL (Take Profit / Stop Loss)

TP and SL are **separate conditional orders** — no OTOCO support. When one triggers, cancel the other manually.

| Feature | API `type` (via algoOrder) | Params |
|---------|---------------------------|--------|
| Take Profit (limit) | `TAKE_PROFIT` | `triggerPrice`, `price`, `quantity` |
| Take Profit (market) | `TAKE_PROFIT_MARKET` | `triggerPrice`, optional `closePosition=true` |
| Stop Loss (limit) | `STOP` | `triggerPrice`, `price`, `quantity` |
| Stop Loss (market) | `STOP_MARKET` | `triggerPrice`, optional `closePosition=true` |

**TP/SL UI modes:**
- **Basic (inline)**: TP price + SL price with trigger type (Last/Mark) and unit (USDT/%)
- **Advanced (modal)**: Full dialog with Open Long/Short tabs, per-direction TP/SL config, PnL/ROI/Price target selector, Market/Limit toggle for triggered order type

### Time-in-Force (TIF)

| UI Value | API `timeInForce` | Description |
|----------|-------------------|-------------|
| GTC | `GTC` | Good Till Cancel |
| IOC | `IOC` | Immediate or Cancel |
| FOK | `FOK` | Fill or Kill |
| GTD | `GTD` | Good Till Date (requires `goodTillDate` param) |
| Post Only | `GTX` | Good Till Crossing (maker only) |

### PriceMatch (BBO)

The "BBO" checkbox in UI maps to the `priceMatch` parameter:
- `OPPONENT` — best opposing price
- `OPPONENT_5` — 5th level opponent (note: `OPPONENT_10`, `OPPONENT_20` temporarily removed since 2025-10-23)
- `QUEUE`, `QUEUE_5`, `QUEUE_10`, `QUEUE_20` — same-side queue levels

When `priceMatch` is set, `price` is not required for LIMIT orders.

## Margin & Position Settings

### Margin Mode (Cross / Isolated)

- **API**: `POST /fapi/v1/marginType`
- **Params**: `symbol`, `marginType` (`CROSSED` or `ISOLATED`)
- **UI**: Click "Isolated"/"Cross" button → modal with radio selection → Confirm
- **Note**: Applies per symbol. Cannot change while positions are open.

### Leverage

- **API**: `POST /fapi/v1/leverage`
- **Params**: `symbol`, `leverage` (1-125 depending on symbol)
- **UI**: Click "1x" button → slider/input → Confirm

### Position Mode (Hedge / One-Way)

- **API**: `POST /fapi/v1/positionSide/dual`
- **Params**: `dualSidePosition` (`true` = Hedge Mode, `false` = One-Way)
- **UI**: Settings (S button) → Position Mode
- **Note**: Cannot change while any position is open.

### Asset Mode (Single / Multi-Assets)

- **API**: `POST /fapi/v1/multiAssetsMargin`
- **Params**: `multiAssetsMargin` (`true` or `false`)
- **UI**: Settings (S button) → Asset Mode → Single-Asset / Multi-Assets
- **Note**: Multi-Assets only supports Cross Margin Mode. BFUSD only usable in Multi-Assets Mode.

### Isolated Position Margin Adjustment

- **API**: `POST /fapi/v1/positionMargin`
- **Params**: `symbol`, `amount`, `type` (1=add, 2=reduce), optional `positionSide`
- **UI**: Click margin amount on position row → Add/Remove margin

### Price Protection

- **API param**: `priceProtect` (`TRUE`/`FALSE`) on conditional orders
- **UI**: Settings → Price Protection toggle
- Protects against large price deviations on stop/TP orders

## Browser Automation (Playwright)

### Navigation
```
https://www.binance.com/en/futures/{SYMBOL}  (e.g., BTCUSDT)
```

### Key UI Selectors (Accessibility)
- Margin mode: `button "Isolated"` or `button "Cross"`
- Leverage: `button "1x"` (shows current leverage)
- Settings drawer: `button "S"`
- Order type tabs: `tab "Limit"`, `tab "Market"`, `tab "Stop Limit"`
- Stop Limit dropdown: `combobox` next to Stop Limit tab → options for Stop Market, Conditional, Trailing Stop, Post Only, TWAP, Scaled Order
- TIF selector: element with text "GTC" near TIF label
- TP/SL checkbox: `checkbox "TP/SL"`
- Open Long/Short: `button "Open Long"`, `button "Open Short"`

### Settings Drawer Items
- Trading Configuration: Account Mode, Order Confirmation, Position Mode, Asset Mode, Default Trade Settings, Price Protection, Order Adjustment, Notification
- Chart Synchronization: Drawings Sync, Indicators Sync
- Advanced Tools: Cooling Period, Trading Parameters, Position Limit Enlarge, Backtest, Keyboard Shortcuts, Market Monitor, Demo Trading

## Agentic Use Cases

1. **Smart order routing** — Use TWAP for large orders to minimize slippage
2. **Dynamic TP/SL** — Adjust TP/SL based on volatility using TAKE_PROFIT_MARKET with closePosition
3. **Margin optimization** — Switch between Cross/Isolated based on portfolio risk
4. **Hedge mode** — Open simultaneous Long and Short positions for hedging strategies
5. **Post-only orders** — Ensure maker fees with GTX time-in-force
6. **Trailing stops** — Auto-follow price with callbackRate for trend-following strategies

## References

- **API mapping details**: See [references/api-mapping.md](references/api-mapping.md) for complete endpoint reference
- **UI structure**: See [references/ui-structure.md](references/ui-structure.md) for Playwright selectors
- **Analytics & Trading Data**: See [binance-analytics](../binance-analytics/SKILL.md) for Futures Trading Data charts (Open Interest, L/S Ratio, Basis, Funding Rate, OI/Market Cap), Arbitrage Data analysis, and market sentiment indicators
