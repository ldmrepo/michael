---
name: investment
description: Personal cryptocurrency investment service with Binance API + browser automation
---

# Investment Skill

암호화폐 중심 개인 투자 서비스. Binance API(잔고/주문) + Patchright 브라우저(Smart Money 등) 이중 접근.
Semi-Auto 모드: 분석/추천 → Telegram 승인 → 자동 주문 실행.

## Prerequisites

```bash
# Required environment variables in .env
BINANCE_API_KEY=xxx
BINANCE_API_SECRET=xxx
FRED_API_KEY=xxx          # For macro data (optional)
```

## Architecture

```
InvestmentService (TypeScript orchestrator)
  ├── [cron] Python scripts (data collection + execution)
  ├── SQLite tables (portfolio, research, analysis, risk, proposals)
  ├── Claude Agent (analysis prompt with aggregated data)
  └── Gateway → Telegram (reports + inline approval buttons)
```

## Usage

**CRITICAL**: Always use `python scripts/run.py [script]` wrapper, never execute scripts directly.

### Authentication (One-time)

```bash
# Setup Binance browser authentication (for Smart Money, ETF data)
python scripts/run.py auth_manager.py setup
python scripts/run.py auth_manager.py status
python scripts/run.py auth_manager.py validate
```

### Portfolio

```bash
python scripts/run.py sync_balance.py --user-id default
python scripts/run.py sync_transactions.py --user-id default --symbols BTCUSDT,ETHUSDT
python scripts/run.py snapshot_nav.py --user-id default
```

### Research Collection

```bash
# API-based (no auth needed)
python scripts/run.py collect_market.py
python scripts/run.py collect_binance_api.py
python scripts/run.py collect_macro.py
python scripts/run.py collect_news.py
python scripts/run.py collect_defi.py

# Browser-based (needs Binance auth)
python scripts/run.py collect_etf_flows.py
python scripts/run.py collect_smart_money.py

# API-based (Deribit - no auth needed)
python scripts/run.py collect_options.py
```

### Analysis

```bash
python scripts/run.py analyze.py --daily --user-id default
python scripts/run.py analyze.py --weekly --user-id default
```

### Risk Monitoring

```bash
python scripts/run.py monitor_prices.py --user-id default
python scripts/run.py monitor_risk.py --user-id default
```

### Order Execution

```bash
# Execute approved proposal
python scripts/run.py execute_order.py --proposal-id 1
python scripts/run.py execute_order.py --proposal-id 1 --dry-run

# Rebalancing
python scripts/run.py execute_rebalance.py --user-id default \
  --targets '{"BTCUSDT": 50, "ETHUSDT": 30, "USDT": 20}'

# DCA
python scripts/run.py execute_dca.py --user-id default
python scripts/run.py execute_dca.py --user-id default --dry-run
```

## Scheduled Jobs (Automatic)

| Job | Schedule | Script |
|-----|----------|--------|
| Balance Sync | Every 30 min | sync_balance.py |
| NAV Snapshot | Midnight | snapshot_nav.py |
| Market Data | Every 6 hours | collect_market.py |
| Binance Derivatives | Every 4 hours | collect_binance_api.py |
| Macro Data | 8AM, 8PM | collect_macro.py |
| ETF Flows | 10PM weekdays | collect_etf_flows.py |
| Smart Money | Every 12 hours | collect_smart_money.py |
| News | Every 2 hours | collect_news.py |
| DeFi TVL | Every 6 hours | collect_defi.py |
| Price Monitor | Every 5 min | monitor_prices.py |
| Risk Monitor | Every 15 min | monitor_risk.py |
| Daily Brief | 8AM | analyze.py --daily |
| Weekly Analysis | Monday 9AM | analyze.py --weekly |

## Telegram Commands

- `포트폴리오 보여줘` → 잔고 + 비중
- `오늘 분석` → 일일 브리핑
- `매매 추천` → 분석 기반 제안 생성
- `알림 설정` → 가격/위험 임계값

## Data Storage

- Database: `data/memory.db` (shared with Michael core)
- Tables: `investment_holdings`, `investment_transactions`, `investment_snapshots`,
  `investment_research`, `investment_analysis`, `investment_risk_alerts`,
  `investment_risk_thresholds`, `investment_proposals`, `investment_dca_schedules`
- Browser state: `.claude/skills/investment/data/browser_state/`

## 거래 데이터 동기화

로컬 DB는 스냅샷일 뿐이므로 **분석/리밸런싱 전 반드시 동기화** 실행 (위 Portfolio 섹션 참조).

### 핵심 교훈

- **Binance API가 진실의 소스** — DB는 참고용. Spot(`account()`)과 Futures(`futures_position_information()`)를 별도 동기화
- **동기화 전 분석/리밸런싱 금지** — 오래된 DB 기준으로 잘못된 매매 제안이 생성됨
- **전체 자산 파악 시 PM도 동기화** — prediction-market 스킬 참조

## Related Skills

| Skill | Description |
|-------|-------------|
| [binance-futures-advanced](../binance-futures-advanced/SKILL.md) | 주문 유형 (Limit/Market/Stop/Trailing/TWAP/Scaled), 마진/레버리지/포지션 설정, TP/SL API |
| [binance-analytics](../binance-analytics/SKILL.md) | Smart Money, Futures Trading Data, 옵션, Arbitrage, Heatmap, Fear & Greed, Fund Flow |
| [binance-trading-bots](../binance-trading-bots/SKILL.md) | Grid/DCA/Snowball/Arbitrage/Rebalancing 봇 설정 및 브라우저 자동화 |
| [binance-copy-trading](../binance-copy-trading/SKILL.md) | Copy Trading 리더보드, 복사 설정, 포트폴리오 관리 |
| [prediction-market](../prediction-market/SKILL.md) | Polymarket 거래, 확률 베팅, 포트폴리오 동기화 |

---

## Safety Features

- `INVESTMENT_MAX_ORDER_USD` (default: $10,000) - single order limit
- `INVESTMENT_PROPOSAL_EXPIRY_MIN` (default: 30) - proposal timeout
- All orders require Telegram approval (Semi-Auto)
- `--dry-run` flag for testing
