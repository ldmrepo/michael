# Binance Trading Bots — API Mapping Reference

## Table of Contents
- [API Availability Summary](#api-availability-summary)
- [Futures TWAP API](#futures-twap-api)
- [Futures VP API](#futures-vp-api)
- [Spot TWAP API](#spot-twap-api)
- [Futures Conditional/Algo Order API](#futures-conditionalalgo-order-api)
- [Auto-Invest API](#auto-invest-api)
- [WebSocket Bot Events](#websocket-bot-events)
- [Grid Bot — No Public API](#grid-bot--no-public-api)
- [DCA Bot — No Public API](#dca-bot--no-public-api)
- [Workarounds via Standard API](#workarounds-via-standard-api)
- [Internal BAPI Endpoints (Undocumented)](#internal-bapi-endpoints-undocumented)
- [Rate Limits](#rate-limits)

---

## API Availability Summary

| Bot Type | Public API | Workaround |
|----------|-----------|------------|
| Futures Grid | **No** | Browser automation or DIY limit orders |
| Spot Grid | **No** | Browser automation or DIY limit orders |
| Position Snowball | **No** | Browser automation or DIY trailing + DCA |
| Futures DCA | **No** | Browser automation or Auto-Invest API |
| Arbitrage Bot | **No** | Spot + Futures API combo |
| Rebalancing Bot | **No** | Index-Linked Plan or manual rebalance |
| Spot DCA | **No** | Browser automation or Auto-Invest API |
| Futures TWAP | **Yes** | `POST /sapi/v1/algo/futures/newOrderTwap` |
| Futures VP | **Yes** | `POST /sapi/v1/algo/futures/newOrderVp` |
| Spot TWAP | **Yes** | `POST /sapi/v1/algo/spot/newOrderTwap` |
| Spot Algo Orders | Partial | Standard algo endpoints (VIP access) |

---

## Futures TWAP API

### Create — `POST /sapi/v1/algo/futures/newOrderTwap`

Base URL: `https://api.binance.com` | Weight: 3000

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `symbol` | STRING | Yes | e.g. `BTCUSDT` |
| `side` | ENUM | Yes | `BUY` / `SELL` |
| `quantity` | DECIMAL | Yes | Notional: 1,000–1,000,000 USDT |
| `duration` | LONG | Yes | 300–86400 seconds |
| `positionSide` | ENUM | No | `BOTH`/`LONG`/`SHORT` (hedge mode) |
| `clientAlgoId` | STRING | No | 32-char unique ID |
| `reduceOnly` | BOOLEAN | No | default false |
| `limitPrice` | DECIMAL | No | Worst acceptable price |
| `timestamp` | LONG | Yes | |

**Constraints:** Max 10 simultaneous TWAP orders. `quantity * 60 / duration` must exceed symbol min quantity.

**Response:** `{"clientAlgoId": "str", "success": bool, "code": int, "msg": "str"}`

### Management

| Operation | Endpoint | Weight |
|-----------|----------|--------|
| Query Open | `GET /sapi/v1/algo/futures/openOrders` | - |
| Query Historical | `GET /sapi/v1/algo/futures/historicalOrders` | - |
| Query Sub Orders | `GET /sapi/v1/algo/futures/subOrders` | - |
| Cancel | `DELETE /sapi/v1/algo/futures/order` | - |

---

## Futures VP API

### Create — `POST /sapi/v1/algo/futures/newOrderVp`

Base URL: `https://api.binance.com` | Weight: 300

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `symbol` | STRING | Yes | e.g. `BTCUSDT` |
| `side` | ENUM | Yes | `BUY` / `SELL` |
| `quantity` | DECIMAL | Yes | Notional: 10,000–1,000,000 USDT |
| `urgency` | ENUM | Yes | `LOW`, `MEDIUM`, `HIGH` |
| `positionSide` | ENUM | No | `BOTH`/`LONG`/`SHORT` |
| `clientAlgoId` | STRING | No | 32-char unique ID |
| `reduceOnly` | BOOLEAN | No | default false |
| `limitPrice` | DECIMAL | No | Worst acceptable price |
| `timestamp` | LONG | Yes | |

**Response:** Same as TWAP.

---

## Spot TWAP API

### Create — `POST /sapi/v1/algo/spot/newOrderTwap`

Base URL: `https://api.binance.com` | Weight: 3000

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `symbol` | STRING | Yes | e.g. `BTCUSDT` |
| `side` | ENUM | Yes | `BUY` / `SELL` |
| `quantity` | DECIMAL | Yes | Notional: 1,000–100,000 USDT |
| `duration` | LONG | Yes | 300–86400 seconds |
| `clientAlgoId` | STRING | No | 32-char unique ID |
| `limitPrice` | DECIMAL | No | Worst acceptable price |
| `timestamp` | LONG | Yes | |

**Constraints:** Max 20 simultaneous Algo orders. No VP equivalent for Spot.

### Management

| Operation | Endpoint |
|-----------|----------|
| Query Open | `GET /sapi/v1/algo/spot/openOrders` |
| Query Historical | `GET /sapi/v1/algo/spot/historicalOrders` |
| Query Sub Orders | `GET /sapi/v1/algo/spot/subOrders` |
| Cancel | `DELETE /sapi/v1/algo/spot/order` |

---

## Futures Conditional/Algo Order API

**Critical (since 2025-12-09):** Conditional orders MUST use `POST /fapi/v1/algoOrder` with `algoType=CONDITIONAL`. The old `/fapi/v1/order` returns `-4120`.

### Create — `POST /fapi/v1/algoOrder`

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `algoType` | ENUM | Yes | `CONDITIONAL` |
| `symbol` | STRING | Yes | |
| `side` | ENUM | Yes | `BUY` / `SELL` |
| `type` | ENUM | Yes | `STOP_MARKET`, `TAKE_PROFIT_MARKET`, `STOP`, `TAKE_PROFIT`, `TRAILING_STOP_MARKET` |
| `triggerPrice` | DECIMAL | Yes | Trigger condition price |
| `price` | DECIMAL | No | Limit price |
| `quantity` | DECIMAL | Cond. | Not needed with `closePosition=true` |
| `closePosition` | BOOL | No | Close all positions on trigger |
| `callbackRate` | DECIMAL | No | For trailing stops (0.1-10%) |
| `activatePrice` | DECIMAL | No | Trailing stop activation price |
| `workingType` | ENUM | No | `MARK_PRICE` / `CONTRACT_PRICE` |
| `timeInForce` | ENUM | No | `IOC`/`GTC`/`FOK`/`GTX` |

### Management

| Operation | Endpoint | Weight |
|-----------|----------|--------|
| Query Single | `GET /fapi/v1/algoOrder` | 1 |
| Query Open | `GET /fapi/v1/openAlgoOrders` | 1/40 |
| Query All (7-day max) | `GET /fapi/v1/allAlgoOrders` | - |
| Cancel One | `DELETE /fapi/v1/algoOrder` | 1 |
| Cancel All by Symbol | `DELETE /fapi/v1/algoOpenOrders` | 1 |

---

## Auto-Invest API

Base URL: `https://api.binance.com`

### Plan Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/sapi/v1/lending/auto-invest/plan/add` | POST | Create investment plan |
| `/sapi/v1/lending/auto-invest/plan/edit` | POST | Edit plan details |
| `/sapi/v1/lending/auto-invest/plan/edit-status` | POST | Activate/pause plan |

### Query Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/sapi/v1/lending/auto-invest/target-asset/list` | GET | Target asset list |
| `/sapi/v1/lending/auto-invest/target-asset/roi/list` | GET | ROI return list |
| `/sapi/v1/lending/auto-invest/all/asset` | GET | All source + target assets |
| `/sapi/v1/lending/auto-invest/source-asset/list` | GET | Source assets for investment |
| `/sapi/v1/lending/auto-invest/plan/list` | GET | List of plans |
| `/sapi/v1/lending/auto-invest/plan/id` | GET | Plan holding details |
| `/sapi/v1/lending/auto-invest/history/list` | GET | Subscription transaction history |

### One-Time Transaction

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/sapi/v1/lending/auto-invest/one-time/transaction` | POST | Execute one-time purchase (TRADE) |
| `/sapi/v1/lending/auto-invest/one-time/status` | GET | Query transaction status |

### Index-Linked Plan

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/sapi/v1/lending/auto-invest/index/redemption` | POST | Redeem index plan |
| `/sapi/v1/lending/auto-invest/index/redemption` | GET | Query redemption status |
| `/sapi/v1/lending/auto-invest/index/info` | GET | Query index details |
| `/sapi/v1/lending/auto-invest/index/position` | GET | Index plan position details |
| `/sapi/v1/lending/auto-invest/rebalance/history` | GET | Rebalance history |

---

## WebSocket Bot Events

Connection: `wss://fstream.binance.com/ws/<listenKey>` (see Futures Advanced skill for listenKey management)

### STRATEGY_UPDATE

Fires when a strategy (grid bot, etc.) is created/cancelled/expired.

```json
{
  "e": "STRATEGY_UPDATE",
  "su": {
    "si": 176054594,      // Strategy ID
    "st": "GRID",         // Strategy Type
    "ss": "NEW",          // Status: NEW, WORKING, CANCELLED, EXPIRED
    "s": "BTCUSDT",       // Symbol
    "ut": 1669261797627,  // Update Time
    "c": 8007             // Operation Code
  }
}
```

**Operation Codes:**

| Code | Description |
|------|-------------|
| 8001 | Strategy parameters updated |
| 8002 | User cancelled strategy |
| 8003 | User manually placed/cancelled order |
| 8004 | Stop limit reached |
| 8005 | Position liquidated |
| 8006 | Max open order limit reached |
| 8007 | New grid order |
| 8008 | Insufficient margin |
| 8009 | Price out of bounds |
| 8010 | Market closed/paused |
| 8011 | Close position failed |
| 8012 | Exceeded maximum notional value |
| 8013 | Grid expired (KYC/jurisdiction) |
| 8014 | Quantitative trading rules violation |
| 8015 | Position empty or liquidated |

### GRID_UPDATE

Fires when a grid sub-order is filled/partially filled.

```json
{
  "e": "GRID_UPDATE",
  "gu": {
    "si": 176057039,       // Strategy ID
    "st": "GRID",          // Strategy Type
    "ss": "WORKING",       // Status
    "s": "BTCUSDT",        // Symbol
    "r": "-0.00300716",    // Realized PnL
    "up": "16720",         // Unmatched Avg Price
    "uq": "-0.001",        // Unmatched Quantity
    "uf": "-0.00300716",   // Unmatched Fee
    "mp": "0.0",           // Matched PnL
    "ut": 1669262908197    // Update Time
  }
}
```

**Note:** Grid bot P&L is ONLY available via `GRID_UPDATE` WebSocket events. No REST API exists to query grid bot P&L.

---

## Grid Bot — No Public API

Binance does **not** expose public REST API endpoints for Grid Bot creation or management. Grid bot activities don't appear in standard order history endpoints.

**What IS available via API:**
- Query account balance and positions (`GET /fapi/v3/balance`, `GET /fapi/v3/positionRisk`)
- View open orders placed by grid bot (`GET /fapi/v1/openOrders`)
- Grid bot orders appear as regular limit orders with auto-generated client order IDs
- Monitor via WebSocket: `STRATEGY_UPDATE` (lifecycle), `GRID_UPDATE` (fills/PnL)

**What is NOT available via API:**
- Create, stop, or modify grid bot
- Query grid bot status/PnL (except via WebSocket)

---

## DCA Bot — No Public API

Same as Grid Bot — no public API for DCA bot management.

**Alternative for simple DCA:** Use Auto-Invest API (`/sapi/v1/lending/auto-invest/plan/add`) for recurring purchases. For Futures DCA, browser automation is required.

---

## Workarounds via Standard API

### DIY Grid Trading

Replicate grid trading using standard order API:

1. Calculate grid levels: `lower_price + i * (upper_price - lower_price) / num_grids`
2. Place limit buy orders at each level below current price
3. Place limit sell orders at each level above current price
4. Use `POST /fapi/v1/batchOrders` (up to 5 per request)
5. Monitor fills via WebSocket `ORDER_TRADE_UPDATE`
6. Replace filled orders with opposite side at next grid level

**Limitations vs native Grid Bot:**
- No trailing up/down
- No auto-restart
- Manual fill monitoring required
- No built-in PnL tracking

### DIY DCA

1. Place initial market order (base order)
2. Set conditional orders at deviation levels via `POST /fapi/v1/algoOrder`
3. Monitor fills via WebSocket `ORDER_TRADE_UPDATE`
4. Place take profit order after each fill
5. Reset round after TP hit

### DIY Arbitrage (Funding Rate)

1. Spot: Buy via `POST /api/v3/order`
2. Futures: Short via `POST /fapi/v1/order`
3. Monitor funding rate: `GET /fapi/v1/premiumIndex` or WebSocket `markPriceUpdate` (includes `r` field)
4. Close both legs when funding rate reverses

### DIY Rebalancing

1. Get current portfolio: `GET /api/v3/account`
2. Calculate target vs actual allocation
3. Execute trades to rebalance via `POST /api/v3/order`
4. Or use Auto-Invest Index-Linked Plans with monthly auto-rebalancing

### DIY Position Snowball

1. Enter initial position
2. Monitor price via WebSocket
3. Add to position at defined price increase intervals
4. Set trailing stop for entire position via `POST /fapi/v1/algoOrder` with `TRAILING_STOP_MARKET`

---

## Internal BAPI Endpoints (Undocumented)

**WARNING:** NOT officially supported. May break at any time. Requires cookie-based session auth (not API key HMAC). Binance states: "not recommended to use."

| Endpoint | Description |
|----------|-------------|
| `POST bapi/futures/v1/private/future/strategy/place-order` | Strategy order placement (supports OTOCO) |
| `GET bapi/futures/v1/private/future/strategy/query` | Query strategy info |
| `GET bapi/futures/v1/private/future/strategy/query-open-strategy` | Query active strategies |
| `GET bapi/futures/v1/private/future/order/open-orders` | Orders with strategyId field |

---

## Rate Limits

- TWAP/VP endpoints: Weight 3000/300 respectively (against SAPI rate limit)
- Standard order endpoints: 1 weight per request
- Batch orders: weight = number of orders in batch
- All endpoints require HMAC SHA256 signature
- **API Signature Change (2026-01-15):** Percent-encoding required before computing signatures
