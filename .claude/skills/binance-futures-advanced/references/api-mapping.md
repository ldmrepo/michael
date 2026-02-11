# Binance Futures Advanced — API Mapping Reference

## Table of Contents
- [Order Endpoints](#order-endpoints)
- [Order Type Parameters (Standard)](#order-type-parameters-standard)
- [Conditional/Algo Order Endpoint](#conditionalalgo-order-endpoint)
- [Conditional Order Type Parameters](#conditional-order-type-parameters)
- [Algo Execution Endpoints](#algo-execution-endpoints)
- [TP/SL Implementation](#tpsl-implementation)
- [Margin & Position Endpoints](#margin--position-endpoints)
- [Account Configuration Endpoints](#account-configuration-endpoints)
- [Market Data Endpoints](#market-data-endpoints)
- [WebSocket Market Data Streams](#websocket-market-data-streams)
- [WebSocket User Data Streams](#websocket-user-data-streams)
- [Rate Limits](#rate-limits)
- [Quick Reference Table](#quick-reference-table)
- [Important Notes](#important-notes)

---

## Order Endpoints

### New Order — `POST /fapi/v1/order`

Base URL: `https://fapi.binance.com`

**For LIMIT and MARKET orders only.** Since 2025-12-09, conditional orders (STOP, STOP_MARKET, TAKE_PROFIT, TAKE_PROFIT_MARKET, TRAILING_STOP_MARKET) must use `POST /fapi/v1/algoOrder` — sending them here returns error `-4120 STOP_ORDER_SWITCH_ALGO`.

**Common Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `symbol` | STRING | Yes | e.g. `BTCUSDT` |
| `side` | ENUM | Yes | `BUY` or `SELL` |
| `type` | ENUM | Yes | `LIMIT` or `MARKET` |
| `positionSide` | ENUM | No | `BOTH` (One-Way), `LONG`/`SHORT` (Hedge Mode) |
| `quantity` | DECIMAL | Varies | |
| `reduceOnly` | STRING | No | `true`/`false` |
| `newClientOrderId` | STRING | No | Unique ID, auto-generated if not sent |
| `selfTradePreventionMode` | ENUM | No | `NONE`, `EXPIRE_TAKER`, `EXPIRE_MAKER`, `EXPIRE_BOTH` |
| `recvWindow` | LONG | No | Max 60000 |
| `timestamp` | LONG | Yes | |

### Batch Orders — `POST /fapi/v1/batchOrders`

- Accepts up to 5 orders in a single request
- Param `batchOrders`: JSON array of order objects
- Used for Scaled Orders (no dedicated API — construct price ladder manually)
- Weight = number of orders in batch

### Cancel Order — `DELETE /fapi/v1/order`

| Param | Type | Required |
|-------|------|----------|
| `symbol` | STRING | Yes |
| `orderId` | LONG | Either this or `origClientOrderId` |
| `origClientOrderId` | STRING | Either this or `orderId` |

### Cancel Algo Order — `DELETE /fapi/v1/algoOrder`

| Param | Type | Required |
|-------|------|----------|
| `algoId` | LONG | Yes |

### Cancel All Orders — `DELETE /fapi/v1/allOpenOrders`

| Param | Type | Required |
|-------|------|----------|
| `symbol` | STRING | Yes |

---

## Order Type Parameters (Standard)

### LIMIT — via `POST /fapi/v1/order`

| Param | Required | Notes |
|-------|----------|-------|
| `timeInForce` | Yes | `GTC`, `IOC`, `FOK`, `GTD`, `GTX` (Post Only) |
| `quantity` | Yes | |
| `price` | Conditional | Not required if `priceMatch` is set |
| `priceMatch` | No | BBO mode (see below) |
| `goodTillDate` | Conditional | Required when `timeInForce=GTD`, epoch ms |

**Post Only** = LIMIT with `timeInForce=GTX`. Rejected if it would immediately match.

### MARKET — via `POST /fapi/v1/order`

| Param | Required |
|-------|----------|
| `quantity` | Yes |

### PriceMatch (BBO) Values

| Value | BUY Behavior | SELL Behavior |
|-------|-------------|--------------|
| `OPPONENT` | Best ask (1st level) | Best bid (1st level) |
| `OPPONENT_5` | 5th best ask | 5th best bid |
| `QUEUE` | Best bid (same side) | Best ask (same side) |
| `QUEUE_5` | 5th best bid | 5th best ask |
| `QUEUE_10` | 10th best bid | 10th best ask |
| `QUEUE_20` | 20th best bid | 20th best ask |

**Note (2025-10-23):** `OPPONENT_10` and `OPPONENT_20` are temporarily removed.

---

## Conditional/Algo Order Endpoint

### New Conditional Order — `POST /fapi/v1/algoOrder`

Base URL: `https://fapi.binance.com`

**Required since 2025-12-09** for all conditional order types.

**Common Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `symbol` | STRING | Yes | |
| `side` | ENUM | Yes | `BUY` / `SELL` |
| `algoType` | ENUM | Yes | `CONDITIONAL` |
| `type` | ENUM | Yes | See types below |
| `positionSide` | ENUM | No | `BOTH`/`LONG`/`SHORT` |
| `workingType` | ENUM | No | `MARK_PRICE` (default) or `CONTRACT_PRICE` |
| `priceProtect` | STRING | No | `TRUE`/`FALSE` |
| `reduceOnly` | BOOLEAN | No | |
| `closePosition` | BOOLEAN | No | Close entire position on trigger |
| `clientAlgoId` | STRING | No | Custom order ID |
| `selfTradePreventionMode` | ENUM | No | `EXPIRE_TAKER`, `EXPIRE_MAKER`, `EXPIRE_BOTH` |
| `goodTillDate` | LONG | No | For `GTD` timeInForce |
| `recvWindow` | LONG | No | |
| `timestamp` | LONG | Yes | |

### Conditional Order Trigger Logic

- **STOP/STOP_MARKET:** BUY triggers when price >= triggerPrice; SELL triggers when price <= triggerPrice
- **TAKE_PROFIT/TAKE_PROFIT_MARKET:** BUY triggers when price <= triggerPrice; SELL triggers when price >= triggerPrice

### Query/Cancel Algo Orders

| Operation | Endpoint | Weight |
|-----------|----------|--------|
| Query Single | `GET /fapi/v1/algoOrder` | 1 |
| Query Open | `GET /fapi/v1/openAlgoOrders` | 1 (symbol) / 40 (all) |
| Query All (7-day max) | `GET /fapi/v1/allAlgoOrders` | - |
| Cancel One | `DELETE /fapi/v1/algoOrder` | 1 |
| Cancel All by Symbol | `DELETE /fapi/v1/algoOpenOrders` | 1 |

---

## Conditional Order Type Parameters

### STOP (Stop Limit) — via `POST /fapi/v1/algoOrder`

| Param | Required | Notes |
|-------|----------|-------|
| `quantity` | Yes | |
| `price` | Conditional | Limit price, not required if `priceMatch` set |
| `triggerPrice` | Yes | Trigger price (was `stopPrice` in old API) |
| `timeInForce` | No | Default `GTC` |

### STOP_MARKET — via `POST /fapi/v1/algoOrder`

| Param | Required | Notes |
|-------|----------|-------|
| `triggerPrice` | Yes | Trigger price |
| `quantity` | No | Not needed if `closePosition=true` |

### TAKE_PROFIT — via `POST /fapi/v1/algoOrder`

| Param | Required | Notes |
|-------|----------|-------|
| `quantity` | Yes | |
| `price` | Conditional | Not required if `priceMatch` set |
| `triggerPrice` | Yes | |

### TAKE_PROFIT_MARKET — via `POST /fapi/v1/algoOrder`

| Param | Required | Notes |
|-------|----------|-------|
| `triggerPrice` | Yes | |
| `quantity` | No | Not needed if `closePosition=true` |

### TRAILING_STOP_MARKET — via `POST /fapi/v1/algoOrder`

| Param | Required | Notes |
|-------|----------|-------|
| `callbackRate` | Yes | 0.1–10 (percentage, e.g. `1.0` = 1%) |
| `activatePrice` | No | Price at which trailing starts (defaults to latest price) |

---

## Algo Execution Endpoints

### TWAP — `POST /sapi/v1/algo/futures/newOrderTwap`

Base URL: `https://api.binance.com` | Weight: 3000

| Param | Type | Required | Notes |
|-------|------|----------|-------|
| `symbol` | STRING | Yes | |
| `side` | ENUM | Yes | `BUY`/`SELL` |
| `quantity` | DECIMAL | Yes | Total quantity |
| `duration` | LONG | Yes | 300–86400 seconds |
| `positionSide` | ENUM | No | For Hedge Mode |
| `clientAlgoId` | STRING | No | 32-char custom order ID |
| `reduceOnly` | BOOLEAN | No | |
| `limitPrice` | DECIMAL | No | Worst acceptable price |

**Constraints:** Notional 1,000–1,000,000 USDT. Max 10 concurrent TWAP orders. `quantity * 60 / duration` must exceed symbol min quantity.

### VP (Volume Participation) — `POST /sapi/v1/algo/futures/newOrderVp`

Base URL: `https://api.binance.com` | Weight: 300

| Param | Type | Required | Notes |
|-------|------|----------|-------|
| `symbol` | STRING | Yes | |
| `side` | ENUM | Yes | |
| `quantity` | DECIMAL | Yes | Notional: 10,000–1,000,000 USDT |
| `urgency` | ENUM | Yes | `LOW`, `MEDIUM`, `HIGH` |
| `positionSide` | ENUM | No | |
| `clientAlgoId` | STRING | No | |
| `reduceOnly` | BOOLEAN | No | |
| `limitPrice` | DECIMAL | No | |

### Query/Cancel Algo Orders

| Operation | Endpoint |
|-----------|----------|
| Query Open | `GET /sapi/v1/algo/futures/openOrders` |
| Query Historical | `GET /sapi/v1/algo/futures/historicalOrders` |
| Query Sub Orders | `GET /sapi/v1/algo/futures/subOrders` |
| Cancel | `DELETE /sapi/v1/algo/futures/order` |

---

## TP/SL Implementation

Binance Futures API does **not** support OTOCO (One-Triggers-One-Cancels-Other). TP and SL must be placed as **separate conditional orders**.

### Steps:
1. Place entry order (LIMIT/MARKET) via `POST /fapi/v1/order`
2. Place Take Profit via `POST /fapi/v1/algoOrder`:
   - `algoType=CONDITIONAL`, `type=TAKE_PROFIT_MARKET`
   - `side=<opposite of entry>`, `triggerPrice=<TP price>`
   - `closePosition=true` or specify `quantity`
   - `workingType=MARK_PRICE` (recommended)
3. Place Stop Loss via `POST /fapi/v1/algoOrder`:
   - `algoType=CONDITIONAL`, `type=STOP_MARKET`
   - `side=<opposite of entry>`, `triggerPrice=<SL price>`
   - `closePosition=true` or specify `quantity`

**Critical:** TP and SL are independent. When one triggers, you must manually cancel the other.

---

## Margin & Position Endpoints

### Change Margin Type — `POST /fapi/v1/marginType`

| Param | Type | Values |
|-------|------|--------|
| `symbol` | STRING | e.g. `BTCUSDT` |
| `marginType` | ENUM | `CROSSED` or `ISOLATED` |

**Constraint:** Cannot change while positions are open for that symbol.

### Change Leverage — `POST /fapi/v1/leverage`

| Param | Type | Notes |
|-------|------|-------|
| `symbol` | STRING | |
| `leverage` | INT | 1–125 (symbol-dependent max) |

**Response:** `{"leverage": 21, "maxNotionalValue": "1000000", "symbol": "BTCUSDT"}`

### Change Position Mode — `POST /fapi/v1/positionSide/dual`

| Param | Type | Values |
|-------|------|--------|
| `dualSidePosition` | STRING | `true` (Hedge) / `false` (One-Way) |

**Constraint:** Cannot change while any position is open.

**Impact on orders:**
- One-Way: `positionSide` defaults to `BOTH`, `reduceOnly` available
- Hedge: `positionSide` must be `LONG`/`SHORT`, `reduceOnly` disabled

### Change Asset Mode — `POST /fapi/v1/multiAssetsMargin`

| Param | Type | Values |
|-------|------|--------|
| `multiAssetsMargin` | STRING | `true` (Multi-Assets) / `false` (Single-Asset) |

### Modify Isolated Position Margin — `POST /fapi/v1/positionMargin`

| Param | Type | Notes |
|-------|------|-------|
| `symbol` | STRING | |
| `amount` | DECIMAL | Margin amount |
| `type` | INT | `1` = Add, `2` = Reduce |
| `positionSide` | ENUM | Optional, for Hedge Mode |

### Auto-Add Margin

- **Readable** via `GET /fapi/v1/symbolConfig` (`isAutoAddMargin` field) and `GET /fapi/v2/positionRisk`
- **No public REST API to toggle** — UI-only setting
- **Workaround:** Use `POST /fapi/v1/positionMargin` with `type=1` to manually add margin

---

## Account Configuration Endpoints

| Operation | Endpoint | Weight |
|-----------|----------|--------|
| Get Position Mode | `GET /fapi/v1/positionSide/dual` | 30 |
| Get Multi-Assets Mode | `GET /fapi/v1/multiAssetsMargin` | - |
| Get Leverage Brackets | `GET /fapi/v1/leverageBracket` | 1 |
| Get Symbol Config | `GET /fapi/v1/symbolConfig` | 5 |
| Get Account Config | `GET /fapi/v1/accountConfig` | 5 |
| Full Account Info | `GET /fapi/v3/account` | 5 |
| Account Balance | `GET /fapi/v3/balance` | 5 |
| Position Risk | `GET /fapi/v3/positionRisk` | 5 |
| Commission Rate | `GET /fapi/v1/commissionRate` | 20 |
| API Trading Status | `GET /fapi/v1/apiTradingStatus` | 1 |
| Income History | `GET /fapi/v1/income` | 30 |
| ADL Quantile | `GET /fapi/v1/adlQuantile` | 5 |
| Order Rate Limit | `GET /fapi/v1/rateLimit/order` | 20 |
| Force Orders | `GET /fapi/v1/forceOrders` | 20/50 |
| Exchange Info | `GET /fapi/v1/exchangeInfo` | 1 |

### Commission Rate Response
```json
{
  "symbol": "BTCUSDT",
  "makerCommissionRate": "0.0002",
  "takerCommissionRate": "0.0004",
  "rpiCommissionRate": "0.00005"
}
```

---

## Market Data Endpoints

Base URL: `https://fapi.binance.com`

| Endpoint | Weight | Description |
|----------|--------|-------------|
| `GET /fapi/v1/exchangeInfo` | 1 | Exchange rules, symbol info, rate limits, filters |
| `GET /fapi/v1/premiumIndex` | 1/10 | Mark price, index price, funding rate, next funding time |
| `GET /fapi/v1/fundingRate` | 500/5min | Historical funding rates (max 1000 records) |
| `GET /fapi/v1/fundingInfo` | 500/5min | Funding rate info (intervals, caps) |
| `GET /fapi/v1/openInterest` | 1 | Current open interest for a symbol |
| `GET /fapi/v1/ticker/24hr` | 1/40 | 24hr price change statistics |
| `GET /fapi/v1/ticker/price` | 1/2 | Latest price |
| `GET /fapi/v1/ticker/bookTicker` | 1/2 | Best bid/ask |

### Market Sentiment Data (IP rate limit: 1000/5min)

| Endpoint | Description | Data Retention |
|----------|-------------|----------------|
| `/futures/data/openInterestHist` | Historical open interest | Latest 1 month |
| `/futures/data/topLongShortAccountRatio` | Top 20% traders L/S by account count | Latest 30 days |
| `/futures/data/topLongShortPositionRatio` | Top 20% traders L/S by position size | Latest 30 days |
| `/futures/data/globalLongShortAccountRatio` | Global L/S ratio all traders | Latest 30 days |
| `/futures/data/takerlongshortRatio` | Taker buy vs sell volume ratio | Latest 30 days |

**Common Parameters:** `symbol`, `period` (5m/15m/30m/1h/2h/4h/6h/12h/1d), `limit` (max 500), `startTime`, `endTime`

### Premium Index Response
```json
{
  "symbol": "BTCUSDT",
  "markPrice": "16520.50",
  "indexPrice": "16519.80",
  "estimatedSettlePrice": "16518.00",
  "lastFundingRate": "0.00010000",
  "interestRate": "0.00010000",
  "nextFundingTime": 1672531200000,
  "time": 1672515782136
}
```

---

## WebSocket Market Data Streams

Base URL: `wss://fstream.binance.com`
- Single stream: `wss://fstream.binance.com/ws/<streamName>`
- Combined: `wss://fstream.binance.com/stream?streams=<stream1>/<stream2>`

**Connection Rules:**
- Symbol names must be **lowercase**
- Connection valid for **24 hours**; server pings every **3 minutes**
- Max **10 incoming messages/second**, **1024 streams/connection**
- Combined stream events wrapped as: `{"stream":"<streamName>","data":<rawPayload>}`

### Available Streams

| Stream | Pattern | Frequency |
|--------|---------|-----------|
| Aggregate Trades | `<symbol>@aggTrade` | 100ms |
| Mark Price | `<symbol>@markPrice` or `@1s` | 3s or 1s |
| Mark Price (All) | `!markPrice@arr` or `@1s` | 3s or 1s |
| Kline | `<symbol>@kline_<interval>` | 250ms |
| Mini Ticker | `<symbol>@miniTicker` | 2000ms |
| Mini Ticker (All) | `!miniTicker@arr` | 2000ms |
| 24hr Ticker | `<symbol>@ticker` | 2000ms |
| 24hr Ticker (All) | `!ticker@arr` | 2000ms |
| Book Ticker | `<symbol>@bookTicker` | Real-time |
| Book Ticker (All) | `!bookTicker` | Real-time |
| Liquidation | `<symbol>@forceOrder` | 1000ms |
| Liquidation (All) | `!forceOrder@arr` | 1000ms |
| Partial Depth | `<symbol>@depth<5/10/20>` | 250ms |
| Partial Depth (fast) | `<symbol>@depth<5/10/20>@100ms` | 100ms |
| Diff Depth | `<symbol>@depth` | 250ms |
| Diff Depth (fast) | `<symbol>@depth@100ms` | 100ms |

**Kline intervals:** 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M

### Subscription Message Format
```json
{"method": "SUBSCRIBE", "params": ["btcusdt@aggTrade", "btcusdt@depth"], "id": 1}
{"method": "UNSUBSCRIBE", "params": ["btcusdt@aggTrade"], "id": 2}
{"method": "LIST_SUBSCRIPTIONS", "id": 3}
```

### Key Payload Examples

**Mark Price (`markPriceUpdate`):**
```json
{
  "e": "markPriceUpdate", "s": "BTCUSDT",
  "p": "16520.50",    // Mark price
  "i": "16519.80",    // Index price
  "r": "0.00010000",  // Funding rate
  "T": 1672531200000  // Next funding time
}
```

**Kline (`kline`):**
```json
{
  "e": "kline", "s": "BTCUSDT",
  "k": {
    "t": 1672515780000, "T": 1672515839999,
    "i": "1m", "o": "16500.00", "c": "16510.00",
    "h": "16520.00", "l": "16490.00", "v": "100.000",
    "n": 50, "x": false, "q": "1650000.00"
  }
}
```

**Book Ticker (`bookTicker`):**
```json
{
  "e": "bookTicker", "s": "BTCUSDT",
  "b": "16500.00", "B": "10.000",  // Best bid
  "a": "16500.50", "A": "5.000"    // Best ask
}
```

---

## WebSocket User Data Streams

Connection URL: `wss://fstream.binance.com/ws/<listenKey>`

### Listen Key Management

| Operation | Method | Endpoint | Weight |
|-----------|--------|----------|--------|
| Create | `POST` | `/fapi/v1/listenKey` | 1 |
| Keepalive | `PUT` | `/fapi/v1/listenKey` | 1 |
| Close | `DELETE` | `/fapi/v1/listenKey` | 1 |

- Valid for **60 minutes**; PUT extends by 60 minutes
- Recommended keepalive: **every 60 minutes**

### Event Types

#### MARGIN_CALL
Triggered when margin ratio approaches liquidation threshold.
```json
{
  "e": "MARGIN_CALL",
  "cw": "3.16812045",     // Cross wallet balance
  "p": [{
    "s": "BTCUSDT", "ps": "LONG", "pa": "0.100",
    "mt": "CROSSED", "mp": "16400.00", "up": "-100.00", "mm": "1.65"
  }]
}
```

#### ACCOUNT_UPDATE
Triggered on balance/position changes (not unfilled/cancelled orders).

**Reason types (`a.m`):** DEPOSIT, WITHDRAW, ORDER, FUNDING_FEE, WITHDRAW_REJECT, ADJUSTMENT, INSURANCE_CLEAR, ADMIN_DEPOSIT, ADMIN_WITHDRAW, MARGIN_TRANSFER, MARGIN_TYPE_CHANGE, ASSET_TRANSFER, AUTO_EXCHANGE, COIN_SWAP_DEPOSIT, COIN_SWAP_WITHDRAW

```json
{
  "e": "ACCOUNT_UPDATE",
  "a": {
    "m": "ORDER",
    "B": [{"a": "USDT", "wb": "122624.123", "cw": "100.123", "bc": "50.123"}],
    "P": [{"s": "BTCUSDT", "pa": "0.100", "ep": "16500.00", "bep": "16502.00",
           "up": "10.00", "mt": "isolated", "iw": "1650.00", "ps": "LONG"}]
  }
}
```

#### ORDER_TRADE_UPDATE
Triggered on order creation, status change, or trade execution.
```json
{
  "e": "ORDER_TRADE_UPDATE",
  "o": {
    "s": "BTCUSDT", "c": "myOrder1", "S": "BUY", "o": "LIMIT", "f": "GTC",
    "q": "0.100", "p": "16500.00", "ap": "16498.50",
    "x": "TRADE",              // Execution: NEW/CANCELED/CALCULATED/EXPIRED/TRADE/AMENDMENT
    "X": "PARTIALLY_FILLED",   // Status: NEW/PARTIALLY_FILLED/FILLED/CANCELED/EXPIRED
    "i": 8886774, "l": "0.050", "z": "0.050", "L": "16498.50",
    "N": "USDT", "n": "0.00330", "m": false, "R": false,
    "wt": "CONTRACT_PRICE", "ot": "LIMIT", "ps": "LONG",
    "cp": false, "AP": "0", "cr": "0", "pP": false, "rp": "0",
    "V": "NONE", "pm": "NONE", "gtd": 0
  }
}
```

Special client order ID prefixes: `"autoclose-"` = liquidation, `"adl_autoclose"` = ADL

#### ACCOUNT_CONFIG_UPDATE
Triggered when leverage or multi-asset mode changes.
```json
{
  "e": "ACCOUNT_CONFIG_UPDATE",
  "ac": {"s": "BTCUSDT", "l": 20},     // Leverage change
  "ai": {"j": true}                      // Multi-asset mode change
}
```

#### Other Events
| Event | Description |
|-------|-------------|
| `listenKeyExpired` | Stream expired; needs new listenKey |
| `STRATEGY_UPDATE` | Strategy (grid bot) lifecycle changes |
| `GRID_UPDATE` | Grid trading sub-order fills |
| `CONDITIONAL_ORDER_TRIGGER_REJECT` | Conditional order trigger rejected |

---

## Rate Limits

### REST API

| Limit Type | Interval | Default Limit |
|------------|----------|---------------|
| `REQUEST_WEIGHT` | 1 minute | **2400** per IP |
| `ORDERS` | 10 seconds | **300** per account |
| `ORDERS` | 1 minute | **1200** per account |

### Response Headers for Monitoring

| Header | Purpose |
|--------|---------|
| `X-MBX-USED-WEIGHT-1M` | Current weight usage for 1-minute window |
| `X-MBX-ORDER-COUNT-10S` | Order count in 10-second window |
| `X-MBX-ORDER-COUNT-1M` | Order count in 1-minute window |

### WebSocket Limits

| Limit | Value |
|-------|-------|
| Max streams per connection | **1024** |
| Max incoming messages | **10/second** |
| Connection validity | **24 hours** |
| Ping-pong timeout | **10 minutes** |
| Max connections per IP | **300** |
| Handshake weight | **5** per attempt |

### Violation Policy
- **HTTP 429**: Rate limit exceeded — must back off
- **HTTP 418**: Auto IP ban for repeated violations (escalates: 2min → 3 days)
- **Exception**: Reduce-only, close-position, risk-reduction orders exempt from -1008 protection

### Best Practices
1. Use WebSocket streams instead of polling REST
2. Monitor `X-MBX-USED-WEIGHT` headers on every response
3. Use combined streams to minimize WebSocket connections
4. Cache `exchangeInfo` (update only when filters change)
5. Implement exponential backoff on 429 responses

---

## Quick Reference Table

| UI Feature | Method | Endpoint | Base URL |
|-----------|--------|----------|----------|
| Limit / Market Order | POST | `/fapi/v1/order` | fapi.binance.com |
| Batch Orders (Scaled) | POST | `/fapi/v1/batchOrders` | fapi.binance.com |
| Conditional Orders (Stop/TP/SL/Trailing) | POST | `/fapi/v1/algoOrder` | fapi.binance.com |
| Cancel Conditional | DELETE | `/fapi/v1/algoOrder` | fapi.binance.com |
| Query Conditional Open | GET | `/fapi/v1/openAlgoOrders` | fapi.binance.com |
| TWAP Order | POST | `/sapi/v1/algo/futures/newOrderTwap` | api.binance.com |
| VP Order | POST | `/sapi/v1/algo/futures/newOrderVp` | api.binance.com |
| Change Leverage | POST | `/fapi/v1/leverage` | fapi.binance.com |
| Change Margin Type | POST | `/fapi/v1/marginType` | fapi.binance.com |
| Change Position Mode | POST | `/fapi/v1/positionSide/dual` | fapi.binance.com |
| Multi-Assets Mode | POST | `/fapi/v1/multiAssetsMargin` | fapi.binance.com |
| Modify Isolated Margin | POST | `/fapi/v1/positionMargin` | fapi.binance.com |
| Symbol Config | GET | `/fapi/v1/symbolConfig` | fapi.binance.com |
| Leverage Brackets | GET | `/fapi/v1/leverageBracket` | fapi.binance.com |
| Commission Rate | GET | `/fapi/v1/commissionRate` | fapi.binance.com |
| Premium Index | GET | `/fapi/v1/premiumIndex` | fapi.binance.com |
| Funding Rate | GET | `/fapi/v1/fundingRate` | fapi.binance.com |
| Exchange Info | GET | `/fapi/v1/exchangeInfo` | fapi.binance.com |

---

## Important Notes

1. **Conditional Order Migration (2025-12-09):** All conditional orders MUST use `POST /fapi/v1/algoOrder` with `algoType=CONDITIONAL`. The old `POST /fapi/v1/order` returns error `-4120`.
2. **Parameter Rename:** In `algoOrder`, use `triggerPrice` (not `stopPrice`) and `activatePrice` (not `activationPrice`).
3. **No OTOCO:** TP and SL are separate independent orders. Cancel the other manually when one triggers.
4. **Auto-Add Margin:** No public API to toggle — UI-only. Use `POST /fapi/v1/positionMargin` as workaround.
5. **Price Protection:** Set `priceProtect=TRUE` on conditional orders. Threshold queryable via `exchangeInfo` field `triggerProtect`.
6. **API Signature Change (2026-01-15):** REST API signature change requires percent-encoding payloads before computing signatures. Affects all HMAC, RSA, and Ed25519 signed requests.
7. **Recv Window:** Recommended 5000ms, max 60000ms.
8. **Testnet:** `https://demo-fapi.binance.com` for testing.
