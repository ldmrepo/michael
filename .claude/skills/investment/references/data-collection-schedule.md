# Data Collection Schedule Reference

## Cron Schedule Overview

```
분 시 일 월 요일
*/30 * * * *     = 매 30분
0 0 * * *        = 자정
0 */6 * * *      = 6시간마다 (0, 6, 12, 18시)
0 */4 * * *      = 4시간마다
0 8,20 * * *     = 오전 8시, 오후 8시
0 22 * * 1-5     = 평일 오후 10시
0 */12 * * *     = 12시간마다
0 */2 * * *      = 2시간마다
*/5 * * * *      = 5분마다
*/15 * * * *     = 15분마다
0 8 * * *        = 매일 오전 8시
0 9 * * 1        = 월요일 오전 9시
```

## Data Sources

### API (Free, no auth)
- **CoinGecko**: Market cap, prices, volume (rate limit: 10-50 req/min)
- **Fear & Greed Index**: Sentiment indicator
- **FRED**: DXY, Fed rate, Treasury yields, M2, CPI
- **Binance Public API**: Funding rate, OI, L/S ratio, taker volume
- **DefiLlama**: Protocol TVL, chain TVL
- **RSS Feeds**: CoinDesk, CoinTelegraph, The Block

### API (Auth required)
- **Binance Private API**: Account balance, positions, orders (HMAC-SHA256)
- **Deribit Public API**: DVOL (volatility index), index prices

### Browser (Patchright)
- **Farside Investors**: BTC/ETH ETF flow tables
- **Binance Copy Trading**: Smart Money signals
- **Binance Trading Insight**: Fund flow, sentiment
- **CME FedWatch**: Rate probability (optional)

## Priority Data

### Critical (< 5min freshness)
- Position prices (for liquidation monitoring)
- Risk thresholds

### Important (< 4h freshness)
- Funding rates (changes every 8h)
- Open interest

### Regular (< 24h freshness)
- Macro indicators (change slowly)
- ETF flows (daily)
- News articles

### Background (< 1 week freshness)
- DeFi TVL trends
- Token unlock schedules
