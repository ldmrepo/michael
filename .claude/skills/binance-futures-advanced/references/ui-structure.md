# Binance Futures Advanced — UI Structure Reference

## Table of Contents
- [Page Navigation](#page-navigation)
- [Order Entry Panel](#order-entry-panel)
- [Order Type Forms (Detailed)](#order-type-forms-detailed)
- [TP/SL (Take Profit / Stop Loss)](#tpsl-take-profit--stop-loss)
- [Settings Drawer](#settings-drawer)
- [Margin & Leverage Controls](#margin--leverage-controls)
- [Position Panel](#position-panel)
- [Market Data Panel](#market-data-panel)

---

## Page Navigation

```
URL: https://www.binance.com/en/futures/{SYMBOL}
Example: https://www.binance.com/en/futures/BTCUSDT
```

### Top Navigation Links
| Element | URL |
|---------|-----|
| `link "Futures"` | `/en/futures/` |
| `link "Options"` | `/en/eoptions` |
| `link "Trading Bots"` | `/en/trading-bots/futures/grid/{SYMBOL}` |
| `link "Copy Trading"` | `/en/copy-trading` |
| `link "Smart Money"` | `/en/smart-money` |

---

## Order Entry Panel

### Open/Close Tabs
- `tab "Open"` [selected by default] — Open new position
- `tab "Close"` — Close existing position

### Order Type Selection

**Primary tabs (always visible):**
- `tab "Limit"` — Standard limit order
- `tab "Market"` — Market order
- **Third tab** — Dynamic, shows selected dropdown type (default: "Stop Limit")

**Dropdown** (click combobox arrow on third tab → `combobox "Select an option"`):

| Option | testId | Description |
|--------|--------|-------------|
| Stop Limit | `stopLimit` | Conditional limit order |
| Stop Market | `stopMarket` | Conditional market order |
| Conditional | `conditional` | Configurable limit/market conditional |
| Trailing Stop | `trailingStop` | Trailing stop with callback rate |
| Post Only | `postOnly` | Limit order with GTX (maker only) |
| TWAP | `twap` | Time-weighted average price |
| Scaled Order | `scaledOrder` | Multiple orders across price range |

### Common Elements

| UI Element | Selector | Notes |
|-----------|----------|-------|
| Available balance | Text: `Avbl {amount} USDT` | Shows available margin |
| Transfer button | `img "Transfer Asset"` | Navigate to transfer |
| Open Long button | `button "Open Long"` | Green button |
| Open Short button | `button "Open Short"` | Red button |
| Cost display | Text: `Cost {amount} USDT` | Shown per side |
| Max display | Text: `Max {amount} BTC` | Max position per side |
| Fee level | Text: `Fee level` | Clickable, shows fee info |
| Size slider | `slider "slider"` | 0-100% of available margin |

---

## Order Type Forms (Detailed)

### Limit Order

| Field | Selector | Notes |
|-------|----------|-------|
| Price | `textbox` (first) | Pre-filled with current price, suffix "USDT" |
| BBO checkbox | `checkbox "BBO"` | PriceMatch mode; disabled when TP/SL checked |
| Size | `textbox` (second) | Unit selector dropdown: BTC / USDT |
| Slider | `slider "slider"` | 0-100% |
| TP/SL | `checkbox "TP/SL"` | Expands TP/SL fields (see below) |
| TIF | Clickable area showing "GTC" | Opens GTC/IOC/FOK/GTD selector |

### Market Order

| Field | Selector | Notes |
|-------|----------|-------|
| Size | `textbox` | Unit selector: BTC / USDT |
| Slider | `slider "slider"` | 0-100% |
| TP/SL | `checkbox "TP/SL"` | Same as Limit |

### Stop Limit

| Field | Selector | Notes |
|-------|----------|-------|
| Stop Price | `textbox` | Trigger type selector: Last / Mark |
| Price | `textbox` (second) | Pre-filled, suffix "USDT"; BBO checkbox (disabled by default) |
| Size | `textbox` (third) | Unit selector: BTC / USDT |
| Slider | `slider "slider"` | 0-100% |
| TP/SL | `checkbox "TP/SL"` | Available |
| TIF | Clickable "GTC" | GTC/IOC/FOK/GTD |

### Stop Market

| Field | Selector | Notes |
|-------|----------|-------|
| Stop Price | `textbox` | Trigger type selector: Last / Mark |
| Size | `textbox` | Unit selector: BTC / USDT |
| Slider | `slider "slider"` | 0-100% |
| TP/SL | `checkbox "TP/SL"` | Available |

**Note:** No price field (market execution at trigger).

### Conditional

| Field | Selector | Notes |
|-------|----------|-------|
| Stop Price | `textbox` | Trigger type selector: Last / Mark |
| Price | `textbox` | Pre-filled, suffix "USDT" |
| Order Type | `combobox "Select"` → "Limit" | Can switch to "Market" (hides Price) |
| Size | `textbox` | Unit selector: BTC / USDT |
| Slider | `slider "slider"` | 0-100% |
| TIF | Clickable "GTC" | GTC/IOC/FOK/GTD (only for Limit type) |

**Key difference from Stop Limit:** Has a Limit/Market combobox to choose triggered order type.

### Trailing Stop

| Field | Selector | Notes |
|-------|----------|-------|
| Callback Rate | `textbox` | Quick buttons: `checkbox "1%"`, `checkbox "2%"` |
| Activation Price | `textbox` | Trigger type selector: Last / Mark |
| Size | `textbox` | Unit selector: BTC / USDT |
| Slider | `slider "slider"` | 0-100% |

**Note:** Callback Rate is 0.1-10% (the percentage by which price must retrace).

### Post Only

Same as Limit form but enforces `timeInForce=GTX`. The order is rejected if it would immediately match (ensures maker-only execution).

### TWAP

| Field | Selector | Notes |
|-------|----------|-------|
| Total Size | `textbox` | `button "MIN"` to auto-fill minimum |
| Total Time | `spinbutton` (hour) + `spinbutton` (min) | Quick buttons: `checkbox "1h"`, `checkbox "6h"`, `checkbox "12h"`, `checkbox "24h"` |
| TWAP Tutorial | `link` | Opens help page |

**Constraints:** Quick time buttons are disabled until size is entered. Duration: 5min - 24h. Notional: 1,000 - 1,000,000 USDT.

### Scaled Order

| Field | Selector | Notes |
|-------|----------|-------|
| Lower Price | `textbox` | Lower bound of price range |
| Upper Price | `textbox` | Upper bound of price range |
| Size (BTC) | `textbox` | Total size across all orders |
| Order Count | `textbox` | Range: 2-50 |
| Size Distribution | `radiogroup` | Options: Flat / Ascending / Descending / Random(±5%) |
| Action | `radiogroup` | Options: Buy / Sell |
| Preview | `button "Preview"` | Shows order distribution before placing |

---

## TP/SL (Take Profit / Stop Loss)

### Basic Mode (inline, on Limit/Market/Stop tabs)

When `checkbox "TP/SL"` is checked, the following fields appear:

| Field | Selector | Notes |
|-------|----------|-------|
| Take Profit label | Text: "Take Profit" | |
| TP Trigger Type | Clickable "Last" | Options: Last / Mark |
| TP Price | `textbox "Price"` | |
| TP Unit selector | Clickable "USDT" | Options: USDT / % |
| Stop Loss label | Text: "Stop Loss" | |
| SL Trigger Type | Clickable "Last" | Options: Last / Mark |
| SL Price | `textbox "Price"` | |
| SL Unit selector | Clickable "USDT" | Options: USDT / % |

**Note:** When TP/SL is enabled, the BBO checkbox becomes disabled.

### Advanced Mode (modal dialog)

Click `button "Advanced"` next to TP/SL checkbox to open modal:

**Dialog:** `dialog "modal"` with title "Take Profit/Stop Loss"

| Element | Selector | Notes |
|---------|----------|-------|
| Direction tabs | `tab "Open Long"` / `tab "Open Short"` | Select direction |
| **Take Profit section** | | |
| TP enable | `checkbox "Take Profit Last"` [checked] | Toggle + trigger type |
| TP Trigger Price | `textbox` (labeled "Trigger Price") | The price that triggers TP |
| TP Value | `textbox` + `combobox "Select"` → "PnL" | Options: PnL / ROI / Price |
| TP Order Type label | Text: "Market Price" | |
| TP Market toggle | `checkbox "Market"` [checked] | Uncheck for Limit order |
| **Stop Loss section** | | |
| SL enable | `checkbox "Stop Loss Last"` [checked] | Toggle + trigger type |
| SL Trigger Price | `textbox` (labeled "Trigger Price") | The price that triggers SL |
| SL Value | `textbox` + `combobox "Select"` → "PnL" | Options: PnL / ROI / Price |
| SL Order Type label | Text: "Market Price" | |
| SL Market toggle | `checkbox "Market"` [checked] | Uncheck for Limit order |
| Confirm | `button "Confirm"` [disabled] | Enabled when values entered |
| Close | `button "Close"` | Close modal |

**Tooltip:** "You can set the triggered order as a Limit order by entering the price here."

### Checkbox Interaction Note

The TP/SL checkbox is a custom `div[role="checkbox"]` (class: `bn-checkbox`). Standard Playwright click may trigger tooltip on first click. **Reliable toggle pattern:**
```javascript
// Dismiss any existing tooltip first
await page.locator('body').click({ position: { x: 10, y: 10 } });
await page.waitForTimeout(300);
// Force click the checkbox
await page.getByRole('checkbox', { name: 'TP/SL' }).click({ force: true });
```

---

## Settings Drawer

**Trigger:** `button "S"` (settings icon, top-right of order panel area)

Opens a slide-out drawer from the right side with sections:

### Trading Configuration
| Setting | UI Element | Notes |
|---------|-----------|-------|
| Account Mode | Link/button | Navigate to account settings |
| Order Confirmation | Toggle | Enable/disable order confirmation dialog |
| Position Mode | Button/link | Opens One-Way / Hedge Mode selector |
| Asset Mode | Button/link | Opens Single-Asset / Multi-Assets Mode selector |
| Default Trade Settings | Link | Default TIF, quantity type, trigger type |
| Price Protection | Toggle | Enable/disable for conditional orders |
| Order Adjustment | Toggle | |
| Notification | Link | Push notification settings |

### Position Mode Dialog
Triggered from Settings → Position Mode:
- Radio: One-Way Mode / Hedge Mode
- Confirm button
- **Cannot change while any position is open**

### Asset Mode Dialog
Triggered from Settings → Asset Mode:
- Radio: Single-Asset Mode / Multi-Assets Mode
- Description of each mode
- Confirm button
- **Multi-Assets only supports Cross Margin**

### Chart Synchronization
- Drawings Sync toggle
- Indicators Sync toggle

### Order Status Reminder
- Toggle for order fill notifications

### Advanced Tools
| Tool | Description |
|------|-------------|
| Cooling Period | Time delay between consecutive orders |
| Trading Parameters | Advanced order parameters |
| Position Limit Enlarge | Request higher position limits |
| Backtest | Strategy backtesting tool |
| Keyboard Shortcuts | Hotkey configuration |
| Market Monitor | Price alert configuration |
| Demo Trading | Paper trading mode toggle |

---

## Margin & Leverage Controls

### Margin Mode Button
- **Selector:** `button "Isolated"` or `button "Cross"` (shows current mode)
- **Location:** Above order entry panel, left side
- **Click action:** Opens modal dialog

**Margin Mode Dialog:**
- Radio buttons: Cross / Isolated
- Confirm button
- **Cannot change while positions are open for that symbol**

### Leverage Button
- **Selector:** `button "1x"` (shows current leverage, e.g. "20x", "50x")
- **Location:** Next to margin mode button
- **Click action:** Opens leverage adjustment modal

**Leverage Dialog:**
- Slider control (1x to max)
- Text input for direct value entry
- Max leverage depends on symbol and notional bracket
- Confirm button

### Asset Mode Button
- **Selector:** `button "Single-Asset Mode"` (in margin ratio section)
- **Location:** Below main trading area, in Margin Ratio panel

---

## Position Panel

Located below the chart/order panel area.

### Tabs
- `tab "Positions(N)"` — Current open positions (N = count)
- `tab "Open Orders(N)"` — Pending orders
- `tab "Order History"` — Completed/cancelled orders
- `tab "Trade History"` — Executed trades
- `tab "Transaction History"` — Margin transfers, funding
- `tab "Assets"` — Account balances

### Position Row Elements
| Element | Selector/Description |
|---------|---------------------|
| Direction badge | Text "B" (Buy/Long) or "S" (Sell/Short) |
| Symbol | e.g. "ETHUSDT" |
| Type tag | `tooltip "Perp"` — Perpetual contract |
| Mode tag | `tooltip "Cross 1x"` — Margin mode + leverage |
| Action icons | Share, TP/SL, Close, Chart icons |
| Unrealized PNL | Text with USDT value |
| ROI | Percentage return |
| Size | Position size in base asset |
| Margin | Allocated margin in USDT |
| Margin Ratio | Percentage (cross-account) |
| Entry Price | Average entry in USDT |
| Mark Price | Current mark price |
| Liq. Price | Liquidation price ("--" if cross with large margin) |
| TP/SL | Shows "-- / --" or set prices (clickable) |
| Action buttons | `button "TP/SL"`, `button "Close"`, `button "Reverse"` |

### Position Actions
| Action | How |
|--------|-----|
| Set TP/SL | Click `button "TP/SL"` on position row |
| Close position | Click `button "Close"` → opens close dialog |
| Reverse position | Click `button "Reverse"` → flips Long↔Short |
| Close all | `button "Close All Positions"` (top of panel) |
| Filter | `checkbox "Hide Other Symbols"` — Show only current symbol |

### Margin Adjustment (Isolated Mode)
Click the margin value on a position row to open:
- Add Margin / Remove Margin tabs
- Amount input
- Confirm button
- Maps to `POST /fapi/v1/positionMargin`

---

## Market Data Panel

### Header Bar
| Element | Description |
|---------|-------------|
| Symbol heading | `heading "BTCUSDT info tag"` — Symbol name + Perp tag |
| Last Price | Large text with current price |
| Price Change | USDT change + percentage |
| Mark Price | `generic "Mark"` + price |
| Index Price | `link "Index"` + price (clickable to funding history) |
| Funding Rate | `generic "Funding (8h) / Countdown"` + rate + timer |
| 24h High/Low | Price range |
| 24h Volume | BTC and USDT volumes |
| Open Interest | `link "Open Interest(USDT)"` (clickable to trading data) |

### Order Book
| Element | Description |
|---------|-------------|
| Tick size selector | Clickable "0.1" with dropdown |
| View mode icons | 3 icons for different order book layouts |
| Ask/Bid columns | Price (USDT) / Size (BTC) / Sum (BTC) |
| Spread display | Mid price + arrow + mark price |

### Recent Trades
| Column | Description |
|--------|-------------|
| Price (USDT) | Trade price (green = buy, red = sell) |
| Amount (BTC) | Trade size |
| Time | HH:MM:SS format |
