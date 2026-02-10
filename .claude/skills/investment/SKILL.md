---
name: investment
description: Personal cryptocurrency investment service with Binance API + browser automation
version: 1.0.0
tags: [crypto, binance, investment, trading, portfolio]
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

## Safety Features

- `INVESTMENT_MAX_ORDER_USD` (default: $10,000) - single order limit
- `INVESTMENT_PROPOSAL_EXPIRY_MIN` (default: 30) - proposal timeout
- All orders require Telegram approval (Semi-Auto)
- `--dry-run` flag for testing
