---
name: crypto-investment-sources
description: Comprehensive crypto investment reference sources covering news, social media, macro economics (Fed/FOMC/interest rates), regulation/policy, on-chain analytics, market data, derivatives/funding rates, ETF flows, research reports, event calendars, and correlated traditional assets (DXY, bonds, gold, equities). Use when researching market conditions, building data pipelines, monitoring sentiment, tracking institutional flows, or implementing multi-source investment analysis systems.
---

# Crypto Investment Sources

## Overview

Comprehensive directory of crypto investment reference sources organized by category. Covers data access methods (API, RSS, browser automation) for each source to enable automated monitoring and analysis pipelines.

## News & Media

| Source | URL | Focus |
|--------|-----|-------|
| CoinDesk | https://www.coindesk.com | Crypto industry standard news |
| CoinTelegraph | https://cointelegraph.com | Crypto/blockchain news & analysis |
| The Block | https://www.theblock.co | Crypto research & investigative reporting |
| Decrypt | https://decrypt.co | Web3/crypto accessible news |
| DL News | https://www.dlnews.com | DeFi/crypto deep reporting |
| Bloomberg Crypto | https://www.bloomberg.com/crypto | Traditional finance + crypto crossover |
| Reuters Crypto | https://www.reuters.com/technology/cryptocurrency/ | Global wire service crypto coverage |
| Binance Square | https://www.binance.com/en/square | Binance integrated news feed |

**Key monitoring signals:**
- Breaking regulatory news (SEC filings, enforcement actions)
- Exchange listings/delistings
- Protocol upgrades and incidents
- Institutional adoption announcements
- Macro-crypto correlation events

## Social Media & Community

| Source | URL | Focus |
|--------|-----|-------|
| X (Twitter) | https://x.com | Real-time market reaction, KOL opinions |
| Reddit r/cryptocurrency | https://reddit.com/r/cryptocurrency | Retail sentiment gauge |
| Reddit r/bitcoin | https://reddit.com/r/bitcoin | BTC-specific community |
| Telegram | https://telegram.org | Project channels, alpha groups |
| Discord | https://discord.com | DeFi/NFT project communities |
| LunarCrush | https://lunarcrush.com | Social media analytics (mentions, sentiment scoring) |

**Key monitoring signals:**
- Trending topics and mention spikes
- KOL position changes and calls
- Community sentiment shifts (fear/euphoria)
- New narrative formation (AI, RWA, DePIN, etc.)

### Key Crypto KOL Categories (X/Twitter)

| Category | Examples | Value |
|----------|---------|-------|
| On-chain analysts | @lookonchain, @EmberCN, @ai_9684xtpa | Whale tracking, smart money moves |
| Macro/crypto | @MacroScope17, @tedtalksmacro | Macro-crypto correlation |
| Trading | @CryptoQuant_en, @52kskew | Technical & quantitative analysis |
| VC/Institutional | @a16z, @paradigm | Investment trends, new narratives |
| Protocol founders | Project-specific | Insider development updates |

## Macro Economics & Interest Rates

### Central Banks

| Source | URL | Focus |
|--------|-----|-------|
| Federal Reserve | https://www.federalreserve.gov | US monetary policy, FOMC statements, dot plot |
| CME FedWatch Tool | https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html | Real-time rate hike/cut probability |
| FRED (St. Louis Fed) | https://fred.stlouisfed.org | Economic data (CPI, employment, GDP, M2, yield curve) |
| ECB | https://www.ecb.europa.eu | Eurozone monetary policy |
| BOJ | https://www.boj.or.jp/en/ | Japan monetary policy (yen carry trade impact) |
| PBOC | http://www.pbc.gov.cn/en/ | China monetary policy (liquidity impact) |

### Economic Data

| Source | URL | Focus |
|--------|-----|-------|
| Trading Economics | https://tradingeconomics.com | Global macro indicators dashboard |
| Investing.com Calendar | https://www.investing.com/economic-calendar/ | Economic event calendar (CPI, NFP, FOMC, etc.) |
| US Treasury | https://home.treasury.gov | Treasury policy, bond auctions, yield data |
| BLS (Bureau of Labor Statistics) | https://www.bls.gov | Employment, CPI, PPI official data |
| BEA | https://www.bea.gov | GDP, personal income, trade balance |

### Key Macro Events for Crypto

| Event | Frequency | Impact | Source |
|-------|-----------|--------|--------|
| FOMC Decision | 8x/year | High - rate path determines risk appetite | Fed |
| CPI Release | Monthly | High - inflation -> rate expectations | BLS |
| Non-Farm Payrolls | Monthly | High - employment -> rate expectations | BLS |
| PCE Price Index | Monthly | High - Fed's preferred inflation gauge | BEA |
| GDP | Quarterly | Medium - economic growth signal | BEA |
| PPI | Monthly | Medium - leading inflation indicator | BLS |
| Initial Jobless Claims | Weekly | Medium - labor market health | DOL |
| ISM Manufacturing/Services | Monthly | Medium - economic activity | ISM |
| Retail Sales | Monthly | Medium - consumer spending | Census |
| FOMC Minutes | 3 weeks post-meeting | Medium - policy nuance | Fed |
| Jackson Hole Symposium | Annual (Aug) | High - policy direction signals | Fed |
| US Treasury Refunding | Quarterly | Medium - bond supply impact | Treasury |

### FRED Key Series for Crypto

| Series ID | Name | Crypto Relevance |
|-----------|------|-----------------|
| `CPIAUCSL` | CPI (All Urban) | Inflation -> rate expectations |
| `FEDFUNDS` | Federal Funds Rate | Direct cost of capital |
| `M2SL` | M2 Money Supply | Liquidity conditions |
| `DGS10` | 10-Year Treasury Yield | Risk-free rate comparison |
| `DGS2` | 2-Year Treasury Yield | Short-term rate expectations |
| `T10Y2Y` | 10Y-2Y Spread | Yield curve inversion signal |
| `UNRATE` | Unemployment Rate | Labor market health |
| `DTWEXBGS` | Trade Weighted Dollar Index | Dollar strength |
| `WALCL` | Fed Balance Sheet | Quantitative tightening/easing |
| `RRPONTSYD` | Reverse Repo (ON RRP) | Liquidity drain gauge |

## Regulation & Policy

| Source | URL | Focus |
|--------|-----|-------|
| SEC | https://www.sec.gov | US securities regulation (ETF approvals, enforcement) |
| CFTC | https://www.cftc.gov | US commodities/futures regulation |
| FinCEN | https://www.fincen.gov | US anti-money laundering rules |
| ESMA (MiCA) | https://www.esma.europa.eu | EU crypto regulatory framework |
| FSC (Korea) | https://www.fsc.go.kr | Korean virtual asset regulation |
| FSS (Korea) | https://www.fss.or.kr | Korean financial supervision |
| Congress.gov | https://www.congress.gov | US crypto-related bills tracking |
| FATF | https://www.fatf-gafi.org | Global AML/CFT standards |

### Key Regulatory Watch Items

| Item | Impact | Status Tracker |
|------|--------|----------------|
| Bitcoin Spot ETF flows | High - institutional on/off ramp | Farside, SoSoValue |
| Ethereum Spot ETF | High - ETH institutional access | SEC filings |
| Stablecoin legislation | High - USDT/USDC regulatory risk | Congress.gov |
| Crypto market structure bill | High - exchange/token classification | Congress.gov |
| SEC enforcement actions | High - project-specific impact | SEC EDGAR |
| Tax reporting rules | Medium - investor behavior change | IRS, Congress |

## On-Chain Data & Analytics

| Source | URL | Focus |
|--------|-----|-------|
| Glassnode | https://glassnode.com | On-chain metrics (NUPL, SOPR, exchange balance, STH/LTH) |
| CryptoQuant | https://cryptoquant.com | On-chain + exchange data analysis |
| Dune Analytics | https://dune.com | Custom on-chain SQL queries & dashboards |
| Nansen | https://nansen.ai | Smart money tracking, wallet labeling |
| Arkham Intelligence | https://www.arkhamintel.com | Wallet tracking & entity analysis |
| DefiLlama | https://defillama.com | DeFi TVL, yields, protocol comparison |
| Etherscan | https://etherscan.io | Ethereum on-chain explorer |
| Blockchain.com | https://www.blockchain.com/explorer | Bitcoin on-chain explorer |
| Santiment | https://santiment.net | On-chain + social + development metrics |
| IntoTheBlock | https://www.intotheblock.com | On-chain financial analytics |

### Key On-Chain Metrics

| Metric | Source | Signal |
|--------|--------|--------|
| Exchange Net Flow | CryptoQuant, Glassnode | Outflow = accumulation, Inflow = sell pressure |
| NUPL (Net Unrealized Profit/Loss) | Glassnode | >0.75 = euphoria (top), <0 = capitulation (bottom) |
| SOPR (Spent Output Profit Ratio) | Glassnode | <1 = selling at loss (bottom signal) |
| MVRV Z-Score | Glassnode | >7 = overvalued, <0 = undervalued |
| Realized Cap | Glassnode | Cost basis of all coins |
| STH/LTH Supply | Glassnode | Short-term vs long-term holder behavior |
| Whale Transaction Count | Santiment | Large transaction spikes = volatility incoming |
| Active Addresses | Glassnode | Network usage/adoption trend |
| DeFi TVL | DefiLlama | Capital locked in DeFi protocols |
| Stablecoin Market Cap | DefiLlama | Dry powder available for buying |

## Market Data & Indicators

| Source | URL | Focus |
|--------|-----|-------|
| CoinMarketCap | https://coinmarketcap.com | Market cap, volume, rankings |
| CoinGecko | https://www.coingecko.com | Token data, DeFi, NFT metrics |
| TradingView | https://www.tradingview.com | Chart analysis, technical indicators |
| Alternative.me | https://alternative.me/crypto/fear-and-greed-index/ | Crypto Fear & Greed Index |
| Coinglass | https://www.coinglass.com | Liquidation data, OI, funding rates |
| Kaiko | https://www.kaiko.com | Institutional-grade market data |
| CryptoCompare | https://www.cryptocompare.com | Multi-exchange aggregated data |
| Binance Trading Insight | https://www.binance.com/en/trading_insight/glass | Fear & Greed, Smart Flow, fund flow |
| Binance Trading Data | https://www.binance.com/en/futures/funding-history/perpetual/trading-data | OI, L/S Ratio, funding rate charts |

### Key Market Indicators

| Indicator | Source | Signal |
|-----------|--------|--------|
| Fear & Greed Index | Alternative.me, Binance | Extreme Fear (<20) = buy signal, Extreme Greed (>80) = caution |
| BTC Dominance | CoinMarketCap | Rising = risk-off, Falling = altcoin season |
| Total Market Cap | CoinMarketCap | Macro trend direction |
| Stablecoin Dominance | CoinGecko | High = fear/cash heavy, Low = risk-on |
| Altcoin Season Index | Blockchaincenter.net | >75 = altseason, <25 = BTC season |
| CMC 100 Index | CoinMarketCap | Broad market performance |

## Derivatives & Funding Rates

| Source | URL | Focus |
|--------|-----|-------|
| Coinglass Funding | https://www.coinglass.com/FundingRate | Cross-exchange funding rate comparison |
| Coinglass Liquidation | https://www.coinglass.com/LiquidationData | Liquidation heatmap/data |
| Coinglass OI | https://www.coinglass.com/OpenInterest | Open interest across exchanges |
| Laevitas | https://app.laevitas.ch | Options/futures analysis (IV, skew, expiry) |
| Deribit Metrics | https://metrics.deribit.com | Options OI, implied volatility, Max Pain |
| Binance Arbitrage | https://www.binance.com/en/futures/funding-history/perpetual/arbitrage-data | Funding/spread arbitrage data |
| Binance Options | https://www.binance.com/en/eoptions-data/BTC | Options OI, BVOL, term structure |

### Key Derivatives Signals

| Signal | Source | Interpretation |
|--------|--------|---------------|
| Funding Rate >0.1% | Coinglass | Overheated longs, potential pullback |
| Funding Rate <-0.05% | Coinglass | Excessive shorts, potential squeeze |
| OI spike + price drop | Coinglass | Short buildup, potential squeeze |
| OI drop + price drop | Coinglass | Long liquidation cascade |
| Put/Call Ratio >1.5 | Deribit, Binance | Extreme fear (contrarian bullish) |
| IV Spike | Laevitas, Binance BVOL | Large move expected |
| Max Pain divergence | Deribit | Price gravitates toward max pain at expiry |
| Options Expiry (large OI) | Deribit | Increased volatility around monthly/quarterly expiry |

## ETF & Institutional Flow

| Source | URL | Focus |
|--------|-----|-------|
| Farside Investors | https://farside.co.uk/btc/ | BTC ETF daily net inflow/outflow |
| SoSoValue | https://sosovalue.com | Crypto ETF data aggregator |
| BitMEX Research | https://blog.bitmex.com/research/ | Institutional research |
| Grayscale | https://www.grayscale.com | GBTC/ETHE fund data |
| CoinShares | https://coinshares.com/research | Weekly institutional flow report |
| 21Shares | https://21shares.com | ETP data and research |
| Bloomberg ETF | https://www.bloomberg.com/markets/etfs | ETF flow analytics |

### Key ETF Metrics

| Metric | Source | Signal |
|--------|--------|--------|
| BTC ETF Daily Net Flow | Farside, SoSoValue | Positive = institutional buying, Negative = redemption |
| ETH ETF Daily Net Flow | Farside, SoSoValue | ETH institutional demand |
| GBTC Outflow | Farside | Selling pressure from Grayscale conversion |
| Cumulative Net Flow | SoSoValue | Long-term institutional trend |
| AUM (Assets Under Management) | Each issuer | Total institutional exposure |

## Research & Reports

| Source | URL | Focus |
|--------|-----|-------|
| Binance Research | https://www.binance.com/en/research | Project/market reports |
| Messari | https://messari.io | Crypto research & data |
| Delphi Digital | https://delphidigital.io | Deep research reports |
| a16z Crypto | https://a16zcrypto.com | VC perspective research |
| Galaxy Digital | https://www.galaxy.com/research/ | Institutional research |
| Grayscale Research | https://www.grayscale.com/research | Market insights |
| Coinbase Institutional | https://www.coinbase.com/institutional | Institutional market analysis |
| K33 Research | https://k33.com/research | Nordic crypto research |
| Chainalysis | https://www.chainalysis.com/blog/ | Compliance/adoption research |

## Calendars & Events

| Source | URL | Focus |
|--------|-----|-------|
| CoinMarketCal | https://coinmarketcal.com | Crypto event calendar (airdrops, upgrades, listings) |
| Token Unlocks | https://token.unlocks.app | Token unlock schedule (sell pressure prediction) |
| Investing.com Calendar | https://www.investing.com/economic-calendar/ | Macro economic events |
| FOMC Calendar | https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm | FOMC meeting schedule |
| DeFi Llama Unlocks | https://defillama.com/unlocks | Token unlock tracker |
| Binance Announcements | https://www.binance.com/en/support/announcement | Listing, delisting, maintenance |

### Key Event Types

| Event Type | Impact | Sources |
|------------|--------|---------|
| Token Unlock (large %) | High - sell pressure | Token Unlocks, DefiLlama |
| Exchange Listing | High - liquidity/access increase | Binance, exchange announcements |
| Protocol Upgrade | Medium-High - fundamental change | Project GitHub, announcements |
| Airdrop | Medium - farming activity, sell pressure | CoinMarketCal |
| FOMC Meeting | High - macro risk appetite | Fed Calendar |
| Options/Futures Expiry | High - volatility spike | Deribit, Coinglass |
| Bitcoin Halving | Very High - supply shock narrative | ~every 4 years |
| Macro Data Release | Medium-High - rate expectations | Investing.com Calendar |

## Traditional Assets (Correlation)

| Asset | TradingView Symbol | Crypto Correlation | Signal |
|-------|-------------------|-------------------|--------|
| DXY (Dollar Index) | `DXY` | Inverse | Dollar strength -> crypto weakness |
| US 10Y Treasury | `US10Y` | Inverse | Rising yields -> risk-off |
| US 2Y Treasury | `US02Y` | Inverse | Short-term rate expectations |
| 10Y-2Y Spread | `US10Y-US02Y` | Context | Inversion = recession signal |
| Gold | `XAUUSD` | Variable | Safe haven comparison |
| S&P 500 | `SPX` | Positive (high) | Risk asset correlation |
| NASDAQ 100 | `QQQ` | Positive (highest) | Tech/growth correlation |
| VIX | `VIX` | Inverse | Fear index -> crypto volatility |
| Russell 2000 | `RUT` | Positive | Risk appetite breadth |
| Oil (WTI) | `CL1!` | Context | Inflation input |
| Copper | `HG1!` | Context | Economic health indicator |
| Japan Nikkei | `NI225` | Context | Yen carry trade unwind risk |

### Correlation Regimes

| Regime | BTC-SPX Corr | BTC-DXY Corr | Description |
|--------|:------------:|:------------:|-------------|
| Risk-On | High (+) | High (-) | BTC moves with stocks, inverse to dollar |
| Liquidity-Driven | High (+) | High (-) | M2/Fed balance sheet drives all risk assets |
| Crypto-Native | Low | Low | BTC driven by halving, adoption, regulation |
| Crisis | Very High (+) | Variable | All assets correlated in panic selling |

## Agentic Use Cases

1. **Multi-source sentiment dashboard** — Aggregate Fear & Greed, social mentions, funding rates, and ETF flows into a single sentiment score
2. **Macro event alert system** — Monitor economic calendar + CME FedWatch for rate-sensitive trade triggers
3. **Smart money flow tracker** — Combine on-chain whale tracking (Arkham/Nansen) with Binance Smart Flow signals
4. **ETF flow momentum** — Track daily BTC/ETH ETF flows, alert on consecutive inflow/outflow streaks
5. **Token unlock sell pressure** — Monitor upcoming unlocks via Token Unlocks API, pre-position short hedges
6. **Cross-market correlation monitor** — Track BTC-SPX/DXY/VIX correlations, alert on regime changes
7. **Regulatory news scanner** — Monitor SEC/CFTC RSS + Congress.gov for crypto-related actions
8. **On-chain accumulation detector** — Track exchange outflows + STH/LTH supply shifts for accumulation signals
9. **Funding rate arbitrage scanner** — Cross-exchange funding rate comparison for delta-neutral yield
10. **Social narrative tracker** — Monitor trending topics on X/Reddit/LunarCrush for emerging narratives

## References

- **Data access methods**: See [references/data-access.md](references/data-access.md) for API, RSS, and automation details per source
- **Related skills**:
  - [binance-analytics](../binance-analytics/SKILL.md) — Binance-specific analytics (Smart Money, Trading Data, Options, Heatmap, Trading Insight)
  - [binance-futures-advanced](../binance-futures-advanced/SKILL.md) — Futures order types and margin settings
  - [binance-copy-trading](../binance-copy-trading/SKILL.md) — Copy trading and leaderboard
  - [binance-trading-bots](../binance-trading-bots/SKILL.md) — Automated trading bots
