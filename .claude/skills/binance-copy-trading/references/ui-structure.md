# Binance Copy Trading — UI Structure Reference

## Table of Contents
- [Page Navigation & URLs](#page-navigation--urls)
- [Futures Leaderboard Page](#futures-leaderboard-page)
- [Spot Leaderboard Page](#spot-leaderboard-page)
- [Advanced Filters Modal](#advanced-filters-modal)
- [Trader Profile Page](#trader-profile-page)
- [Copy Settings Page (Futures)](#copy-settings-page-futures)
- [Copy Management Page](#copy-management-page)
- [Common Patterns](#common-patterns)

---

## Page Navigation & URLs

```
Futures Leaderboard:    https://www.binance.com/en/copy-trading
Spot Leaderboard:       https://www.binance.com/en/copy-trading/spot
Trader Profile:         https://www.binance.com/en/copy-trading/lead-details/{TRADER_ID}?timeRange=30D
Copy Settings:          https://www.binance.com/en/copy-trading/copy-setting?portfolioId={TRADER_ID}
Copy Management:        https://www.binance.com/en/copy-trading/copy-management
Compare Portfolios:     https://www.binance.com/en/copy-trading/compare/futures?portfolios={TRADER_ID}
```

---

## Futures Leaderboard Page

### Top-Level Tabs
| Element | Selector | Notes |
|---------|----------|-------|
| Futures tab | `tab "Futures"` [selected by default] | Links to `/copy-trading` |
| Spot tab | `tab "Spot"` | Links to `/copy-trading/spot` |
| Watch Tutorial | `generic "Watch Tutorial"` | Video tutorial link |

### Account Summary Section
| Element | Selector | Notes |
|---------|----------|-------|
| Total Margin Balance | `paragraph "Total Margin Balance"` | With eye icon to toggle visibility |
| Balance value | `generic "0.00"` + `generic "USDT"` | |
| Total Unrealized PnL | `generic "Total Unrealized PnL"` | Value or "--" |
| Copy Overview button | `link "Copy Overview"` | Links to `/en/copy-trading/copy-management` |

### Lead Trader Banner
| Element | Selector | Notes |
|---------|----------|-------|
| Banner text | "Be a Futures Lead Trader, enjoy up to 30% profit share + 10% commission rebate!" | |
| Apply Now button | `button "Apply Now"` | |

### Promotional Carousel
Scrollable `region` with slides:
- "How to Copy Trades?" (with image)
- "Join Futures Copy Trading, Share 70,000 USDT in Rewards!" (with image)
- "Copy Trading Lead Trader Growth Plan" (with image)
- "How to Lead Trades?" (with image)

### Announcement Bar
| Element | Selector | Notes |
|---------|----------|-------|
| Announcement icon | `img` (megaphone) | |
| Announcement links | `link` elements | News/announcements about copy trading |

### Portfolio Tabs & Filters
| Element | Selector | Notes |
|---------|----------|-------|
| All Portfolios tab | `tab "All Portfolios"` [selected by default] | |
| My Favorites tab | `tab "My Favorites"` | |
| Daily Picks button | `generic "Daily Picks"` | With icon |
| Time Period | `combobox "Select an option"` → "30 Days" | Options: 7 Days, 30 Days, 90 Days |
| Sort By | `combobox "Select an option"` → "PnL" | Options: PnL, ROI, Copiers, AUM |
| Smart Filter | `checkbox "Smart Filter"` [checked] | AI-curated selection |
| Trader Search | `textbox "Trader's Name"` | Free-text search |
| Advanced Filter icon | `img` (filter icon, clickable) | Opens Advanced Filters modal |
| Compare link | `link` → `/copy-trading/compare/futures` | Compare portfolios tool |

### Trader Card Structure
Each trader card is a `link` to `/en/copy-trading/lead-details/{TRADER_ID}?timeRange=30D&isSmartFilter=true`:

| Element | Selector/Description | Notes |
|---------|---------------------|-------|
| Avatar | `img` (first child) | Profile picture |
| Trader Name | `generic "{name}"` | e.g., "c1ultra" |
| Badge | `img "badge"` | Optional, for verified/top traders |
| Copier Count | `generic "{current} / {max}"` | e.g., "281 / 400" |
| API Tag | `generic "API"` | Present if trader uses API trading |
| Favorite Toggle | `img` (heart icon) | Star/unstar trader |
| Performance Chart | `img` (inline chart thumbnail) | Mini performance graph |
| PNL | `generic "30 Days PNL (USD)"` + value | e.g., "+243,291.96" |
| ROI | `generic "30 Days ROI"` + value | e.g., "+41.05%" |
| AUM | `generic "AUM"` + value | e.g., "1,221,068.87" |
| MDD | `generic "30 Days MDD"` + value | e.g., "3.35%" |
| Sharpe Ratio | `generic "Sharpe Ratio"` + value | e.g., "2.20" or "-" |
| Mock button | `button "Mock"` | Paper trade following |
| Copy button | `button "Copy"` | Start copying (opens new tab) |
| Full button | `button "Full"` [disabled] | Shown when copier slots full (replaces Copy) |

### Pagination
| Element | Selector | Notes |
|---------|----------|-------|
| Status text | `generic "Updated every 10 minutes"` | |
| Page numbers | `generic "1"`, `"2"`, etc. | Clickable |
| Ellipsis | `generic "..."` | |
| Next page | `img` (right arrow, clickable) | |
| Previous page | `img` (left arrow, clickable) | |

### FAQ Section
Expandable accordion items at page bottom:
1. What Is Copy Trading?
2. How does copy trading work?
3. What is the portfolio maximum drawdown?
4. What is Portfolio Sharpe Ratio?
5. What is portfolio AUM?
6. What's the benefit for lead traders?
7. What are the copy trading risk rules?

---

## Spot Leaderboard Page

### URL
```
https://www.binance.com/en/copy-trading/spot
```

### Key Differences from Futures
| Feature | Spot | Futures |
|---------|------|---------|
| URL | `/copy-trading/spot` | `/copy-trading` |
| Portfolio tabs | Recommended / All Portfolios / My Favorites | All Portfolios / My Favorites |
| Smart Copy button | `button "Smart Copy"` (present) | Not present |
| Sort options | `combobox` → "High PNL" | `combobox` → "PnL" |
| "More" filters | `generic "More"` (clickable) | Advanced filter icon |
| Metrics shown | PNL, ROI, AUM, 30 Days MDD, **Days Leading Trading** | PNL, ROI, AUM, 30 Days MDD, **Sharpe Ratio** |
| Lead Trader banner | "Be a Lead Trader" button | "Be a Futures Lead Trader" banner + "Apply Now" |
| Account Summary | Total Copying Balance (USDT), Unrealized PNL | Total Margin Balance, Total Unrealized PnL |

### Spot Trader Card Structure
Same as Futures card but with:
- "Days Leading Trading" metric (e.g., "437D") instead of "Sharpe Ratio"
- Optional badge icons next to avatar
- URL pattern: `/en/copy-trading/lead-details/{TRADER_ID}?timeRange=30D` (no `isSmartFilter` param)

### Spot-Specific Elements
| Element | Selector | Notes |
|---------|----------|-------|
| Recommended tab | `tab "Recommended"` [selected by default] | Default tab on Spot |
| Smart Copy button | `button "Smart Copy"` | AI-powered copy allocation |
| Join Now promo | `generic "Join Now"` | Elite Trader Program promo |

---

## Advanced Filters Modal

**Trigger:** Click the filter icon next to the search box on Futures leaderboard.

**Dialog:** `dialog "modal"` with title "Advanced Filters"

### Filter Controls

| Filter | Type | Options/Range | Selector |
|--------|------|--------------|----------|
| Time Range | Checkboxes | 7D, **30D** (default), 90D, 180D | `checkbox "7D"`, `checkbox "30D"` [checked], etc. |
| Tags | Checkboxes (multi-select) | Top Performer, Money Maker, Most Resilient, Whale Manager, Solid Growth, Low Leverage | `checkbox "Top Performer"`, etc. |
| 30D PNL | Range slider + inputs | 0 – 5,000,000 | `textbox "Minimum value"` + `textbox "Maximum value"` + dual `slider` |
| 30D ROI | Radio checkboxes | >= 0%, >= 25%, >= 50%, >= 100% | `checkbox "≥ 0%"`, etc. |
| 30D MDD | Radio checkboxes | <= 10%, <= 30%, <= 50%, <= 70% | `checkbox "≤ 10%"`, etc. |
| 30D Copy Trader PnL | Range slider + inputs | 0 – 5,000,000 | `textbox "Minimum value"` + `textbox "Maximum value"` + dual `slider` |
| Days Trading | Radio checkboxes | >= 30D, >= 60D, >= 90D, >= 180D | `checkbox "≥ 30D"`, etc. |
| AUM (USDT) | Radio checkboxes | >= 25,000, >= 100,000, >= 250,000, >= 500,000 | `checkbox "≥ 25,000"`, etc. |
| Minimum Copy Amount (USDT) | Radio checkboxes | <= 10, <= 50, <= 100, <= 1,000 | `checkbox "≤ 10"`, etc. |
| API | Toggle switch | on/off | `switch "switch"` |
| Copy-ready Portfolios | Toggle switch | on/off | `switch "switch"` |
| Hide Full Portfolios | Toggle switch | on/off | `switch "switch"` |
| Hide Lock-Up Period Portfolios | Toggle switch | on/off | `switch "switch"` |

### Action Buttons
| Element | Selector |
|---------|----------|
| Reset All | `button "Reset All"` |
| Confirm | `button "Confirm"` |
| Close (X) | `button "Close"` |

---

## Trader Profile Page

### URL
```
https://www.binance.com/en/copy-trading/lead-details/{TRADER_ID}?timeRange=30D
```

### Navigation
| Element | Selector | Notes |
|---------|----------|-------|
| Back link | `link "Portfolios List"` | Returns to leaderboard |
| Type badge | `generic "Futures Copy"` + `generic "Public"` | Portfolio type labels |

### Trader Header
| Element | Selector | Notes |
|---------|----------|-------|
| Follower count | `button "7,347"` | With share icon |
| Share button | `button` (share icon) | |
| Avatar | `img` | |
| Trader name | `generic "c1ultra"` | |
| Bio | `generic "Another account: c2cap..."` | Expandable with arrow icon |
| Tags | `generic "API Trading"`, `generic "Top Performer"` | Trading style tags |

### Trader Statistics
| Element | Selector | Notes |
|---------|----------|-------|
| Days Trading | `generic "Days Trading"` + value | e.g., "327" |
| Copiers | `generic "Copiers"` + value | e.g., "281/400" |
| Total Copiers | `generic "Total Copiers"` + value | All-time total, e.g., "2,438" |
| Mock Copiers | `generic "Mock Copiers"` + value | e.g., "17,846" |
| Closed Portfolios | `generic "Closed Portfolios"` + value | e.g., "2" |

### Action Buttons
| Element | Selector | Notes |
|---------|----------|-------|
| Copy | `button "Copy"` | Opens copy settings in new tab |
| Mock Copy | `button "Mock Copy"` | Paper trading |
| Compare | `link "Compare"` | Links to compare page |

### Performance Section
| Element | Selector | Notes |
|---------|----------|-------|
| "Performance" header | `generic "Performance"` | |
| Time period selector | `generic "30 Days"` (clickable dropdown) | |
| ROI | `generic "ROI"` + value | e.g., "+41.05%" |
| PnL | `generic "PnL"` + value | e.g., "+243,291.96" |
| Copier PnL | `generic "Copier PnL"` + value | e.g., "-21,091.13 USDT" |
| Sharpe Ratio | `generic "Sharpe Ratio"` + value | e.g., "2.20" |
| MDD | `generic "MDD"` + value | e.g., "3.36%" |
| Win Rate | `generic "Win Rate"` + value | e.g., "71.64%" |
| Win Positions | `generic "Win Positions"` + value | e.g., "48" |
| Total Positions | `generic "Total Positions"` + value | e.g., "67" |

### Performance Chart
| Element | Selector | Notes |
|---------|----------|-------|
| ROI tab | `tab "ROI"` [selected] | |
| PnL tab | `tab "PnL"` | |
| Time selector | `generic "30 Days"` (clickable) | |
| Chart | `img` (chart visualization) | Interactive chart with date axis |

### Lead Trader Overview
| Element | Selector | Notes |
|---------|----------|-------|
| AUM | `generic "AUM"` + value | e.g., "1,221,068.87 USDT" |
| Profit Sharing | `generic "Profit Sharing"` + value | e.g., "10.00%" |
| Leading Margin Balance | `generic "Leading Margin Balance"` + value | e.g., "635,865.52 USDT" |
| Lock-up period | `generic "Lock-up period"` + value | e.g., "30 Days" |
| Minimum Copy Amount | `generic "Minimum Copy Amount"` + value | e.g., "1000/1000 USDT" (min for Fixed Ratio / Fixed Amount) |

### Asset Preferences
| Element | Selector | Notes |
|---------|----------|-------|
| Header | `generic "Asset Preferences"` | With info icon |
| Time selector | `generic "30 Days"` (clickable) | |
| Pie chart | `img` (donut chart) | Token allocation visualization |
| Token items | Clickable items: "RIVER 40.48%", "DASH 7.3%", etc. | Shows allocation per asset |
| Refresh note | "Figures are refreshed every 1-2 hours." | |

### Bottom Tabs
| Tab | Selector | Notes |
|-----|----------|-------|
| Positions | `tab "Positions"` [selected] | Current open positions (may be private) |
| Position History | `tab "Position History"` | Past closed positions |
| Latest Records | `tab "Latest Records"` | Recent trading activity |
| Transfer History | `tab "Transfer History"` | Margin transfers |
| Copy Traders | `tab "Copy Traders"` | List of traders who copy this lead |

**Note:** Positions may be hidden: "This Lead Trader has set their current positions to 'private'."

---

## Copy Settings Page (Futures)

### URL
```
https://www.binance.com/en/copy-trading/copy-setting?portfolioId={TRADER_ID}
```

**Opens in a new tab** when clicking "Copy" on trader card or profile.

### Navigation
| Element | Selector | Notes |
|---------|----------|-------|
| Portfolios List | `generic "Portfolios List"` (clickable) | Back to leaderboard |
| Tutorial | `generic "Tutorial"` (clickable) | Help page |
| Page title | `banner "Futures Copy Settings"` | |

### Copy Mode Tabs
| Element | Selector | Notes |
|---------|----------|-------|
| Fixed Ratio | `tab "Fixed Ratio"` [selected by default] | Copy proportional to leader's position |
| Fixed Amount | `tab "Fixed Amount"` | Copy with fixed margin per order |

### Fixed Ratio Mode
| Field | Selector | Default | Notes |
|-------|----------|---------|-------|
| Description | Text: "The copy ratio is calculated based on the margin used..." | | Explanation text |
| Lock-up period | `generic "Lock-up period"` + `generic "30 Days"` | 30 Days | Not editable |
| Copy Amount | `textbox "1,000-300,000"` | Empty | USDT amount, with MAX button |
| Available balance | `generic "Available"` + `generic "0.00 USDT"` | | With transfer icon |
| Symbol Preferences | Clickable icon group + tooltip "Copiers can now set preferred symbols" | 99+ symbols | Opens symbol selector |
| Remove low-liquidity | `checkbox "Remove low-liquidity symbols"` | Unchecked | |
| Total Stop Loss | `spinbutton "input field"` + `combobox "USDT"` | Empty | Unit: USDT or % |

### Fixed Amount Mode (differences from Fixed Ratio)
| Field | Selector | Default | Notes |
|-------|----------|---------|-------|
| Description | "Each order will be opened at a fixed margin amount (cost per order)." | | |
| Cost Per Order | `textbox "10-50,000"` USDT | Empty | **Extra field** — fixed margin per trade |
| Copy Amount | `textbox "1,000-300,000"` USDT | Empty | Total capital allocation |

### Advanced Settings (both modes)
Expandable section: `generic "Advanced Settings (Optional)"` (clickable)

| Field | Selector | Default | Notes |
|-------|----------|---------|-------|
| Existing Position Copy Mode | `combobox "Select an option"` → "Copy Better Entries" | Copy Better Entries | |
| Auto-Invest | `switch "switch"` | Off | Auto-reinvest profits |
| Margin Mode | `combobox "Select an option"` → "Copy Leader Trader's Margin Mode" | Copy Leader's | Helper text below |
| Leverage | `combobox "Select an option"` → "Copy Leader Trader's Leverage" | Copy Leader's | Helper text below |
| Max Trade Slippage | `combobox "Select an option"` → "Default" | Default | |
| **Position Risk** section | | | |
| Take Profit | `spinbutton "0-2,000"` + `generic "%"` | Empty | 0-2000% per position |
| Stop Loss | `spinbutton "0-95"` + `generic "%"` | Empty | 0-95% per position |
| Max Cost per Order | `spinbutton "5-95"` + `generic "%"` | Empty | 5-95% of copy amount |

### Confirmation
| Element | Selector | Notes |
|---------|----------|-------|
| Terms checkbox | `checkbox "I have read and I agree to the User Service Agreement"` | Must check to enable Copy |
| Terms link | `link "User Service Agreement"` → `/about-legal/copy-trading-terms` | |
| Copy button | `button "Copy"` [disabled] | Enabled after amount + terms |

### Sidebar (Trader Info)
| Element | Selector | Notes |
|---------|----------|-------|
| Avatar | `img "User avatar"` | |
| Trader name | `generic "c1ultra"` | |
| Tags | `generic "API Trading"`, `generic "Top Performer"` | |
| Profit Sharing | `generic "Profit Sharing 10.00%"` | |
| Bio | Expandable text with "View Original" link | |
| 7 Days PNL | `generic "7 Days PNL (USDT)"` + value | |
| ROI | `generic "ROI"` + value | |
| Mini chart | `img` | Performance chart thumbnail |

---

## Copy Management Page

### URL
```
https://www.binance.com/en/copy-trading/copy-management
```

### Navigation
| Element | Selector | Notes |
|---------|----------|-------|
| Back link | `link "Portfolios List"` | Returns to leaderboard |
| Type selector | `combobox "Select an option"` → "Futures Copy" | Switch between Futures/Spot |

### Status Tabs
| Tab | Selector | Notes |
|-----|----------|-------|
| Ongoing | `tab "Ongoing (N)"` [selected] | Active copies (N = count) |
| Closed | `tab "Closed (N)"` | Stopped copies |
| Mock Copy Trading | `tab "Mock Copy Trading (N)"` | Paper trade copies |

### Account Overview
| Element | Selector | Notes |
|---------|----------|-------|
| Total Margin Balance | `generic "Total Margin Balance (USDT)"` | With eye toggle |
| Balance value | `generic "0.0000"` | |
| Total Wallet Balance | `generic "Total Wallet Balance (USDT)"` | |
| Total Realized PNL | `generic "Total Realized PNL (USDT)"` | |
| Net Profit | `generic "Net Profit (USDT)"` | |

### Empty State
| Element | Selector | Notes |
|---------|----------|-------|
| No records alert | `alert` with "No records" text | |
| View Portfolio List | `button "View Portfolio List"` | Navigate to leaderboard |

### Per-Trader Row (when active copies exist)
| Element | Description |
|---------|-------------|
| Trader avatar + name | Copied trader profile |
| Copy Amount | Allocated USDT |
| PnL | Profit/loss from this trader |
| ROI | Return percentage |
| Status | Active / Stopped |
| Settings icon | Modify copy parameters |
| Stop button | Stop copying this trader |

---

## Common Patterns

### Tab Navigation Opens New Tabs
Clicking trader cards, "Copy" buttons, and some navigation links opens new tabs. Use `browser_tabs` to manage:
```javascript
// After clicking Copy/trader card
await browser_tabs({ action: 'select', index: newTabIndex });
```

### Copier Slot Detection
When a trader's copier count equals max (e.g., "400 / 400"), the "Copy" button is replaced with `button "Full"` [disabled]. Check before attempting to copy.

### Smart Filter Default
The "Smart Filter" checkbox is **checked by default** on the Futures leaderboard, which pre-filters the trader list. Uncheck to see all traders.

### Combobox Interaction
Dropdowns use `combobox "Select an option"` pattern:
```javascript
// Click to open dropdown
await page.getByRole('combobox', { name: 'Select an option' }).first().click();
// Select option
await page.getByText('90 Days').click();
```

### Time Period URL Parameters
Trader profile URL includes `timeRange` param:
- `?timeRange=7D` — 7 days
- `?timeRange=30D` — 30 days (default)
- `?timeRange=90D` — 90 days
