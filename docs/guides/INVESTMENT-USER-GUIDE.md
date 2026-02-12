# Investment Service 사용자 가이드

Michael AI의 암호화폐 투자 서비스. Binance 계정 연동으로 포트폴리오 관리, 시장 분석, 위험 모니터링, Semi-Auto 매매를 지원한다.

---

## 목차

1. [시작하기](#1-시작하기)
2. [Telegram 사용법](#2-telegram-사용법)
3. [일일 브리핑](#3-일일-브리핑)
4. [포트폴리오 관리](#4-포트폴리오-관리)
5. [시장 분석](#5-시장-분석)
6. [위험 모니터링 & 알림](#6-위험-모니터링--알림)
7. [Semi-Auto 매매](#7-semi-auto-매매)
8. [DCA (적립식 투자)](#8-dca-적립식-투자)
9. [리밸런싱](#9-리밸런싱)
10. [데이터 소스](#10-데이터-소스)
11. [자동 스케줄](#11-자동-스케줄)
12. [안전장치](#12-안전장치)
13. [CLI 레퍼런스](#13-cli-레퍼런스)
14. [문제 해결](#14-문제-해결)

---

## 1. 시작하기

### 1.1 필수 환경 변수

`.env` 파일에 다음을 설정한다:

```bash
# 필수 - Binance API
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret

# 필수 - Telegram
TELEGRAM_BOT_TOKEN=your_bot_token

# 선택 - 매크로 경제 데이터 (FRED)
FRED_API_KEY=your_fred_key

# 선택 - 안전 한도 (기본값 표시)
INVESTMENT_MAX_ORDER_USD=10000      # 1회 주문 상한 (USD)
INVESTMENT_PROPOSAL_EXPIRY_MIN=30   # 매매 제안 만료 시간 (분)
```

### 1.2 Binance API 키 발급

1. [Binance API Management](https://www.binance.com/en/my/settings/api-management) 접속
2. API 키 생성 → **읽기 권한 + Spot 주문 + Futures 주문** 활성화
3. IP 제한 설정 권장 (보안)

### 1.3 브라우저 인증 (선택)

Smart Money, ETF 흐름 등 브라우저 기반 데이터 수집에 필요하다:

```bash
# 최초 1회 - Binance 로그인 (브라우저 창이 열림, 수동 로그인)
python scripts/run.py auth_manager.py setup

# 인증 상태 확인
python scripts/run.py auth_manager.py status
```

### 1.4 서비스 시작

Michael 전체 서비스 시작 시 Investment Service도 자동으로 함께 시작된다:

```bash
pnpm build && pnpm start
```

로그에서 다음을 확인:
```
📌 Handler registered for: investment
💰 InvestmentService initialized
✅ Investment scheduler started: 14 jobs
```

---

## 2. Telegram 사용법

Michael 봇에게 메시지를 보내면 AI가 응답한다. 투자 관련 기능은 **인라인 버튼**으로 조작한다.

### 2.1 주요 버튼

일일 브리핑 수신 시 하단에 3개 버튼이 표시된다:

| 버튼 | 기능 | 설명 |
|------|------|------|
| 📋 **상세** | 분석 상세 보기 | 최근 분석의 전체 요약 텍스트 |
| 💰 **포트폴리오** | 자산 현황 | Spot/Futures 잔고, 종목별 비중, 미실현 손익 |
| 🔔 **알림설정** | 알림 임계값 조회 | 설정된 가격/위험 알림 목록 |

### 2.2 매매 제안 버튼

AI 분석에 의해 매매 제안이 생성되면:

| 버튼 | 기능 |
|------|------|
| ✅ **실행** | 제안 승인 → Binance 주문 실행 |
| ❌ **거부** | 제안 거부 (주문 안 함) |
| ✏️ **수정** | 수량/가격 수정 (향후 지원) |

### 2.3 위험 알림 버튼

위험 알림 수신 시 상황에 따라:

| 버튼 | 조건 |
|------|------|
| **포지션축소** | 청산 임박, 급락 알림 시 |
| **손절설정** | 청산 임박, 급락 알림 시 |
| **확인** | 모든 알림 (확인 처리) |

---

## 3. 일일 브리핑

매일 오전 8시(UTC)에 자동으로 Telegram 브리핑이 전송된다.

### 3.1 브리핑 내용

```
📊 일일 투자 브리핑 (2026-02-11)

💰 포트폴리오: $12,345 (Spot $8,000 | Futures $4,345)
😱 Fear & Greed: 45 (Fear) — 7일 추이: 52→48→45

📈 주요 코인 (24h)
BTC $97,200 (+1.2%)  |  ETH $2,650 (-0.5%)
SOL $195 (+3.1%)     |  BNB $680 (+0.8%)

📉 파생상품
펀딩레이트: BTC 0.01% | ETH 0.005%
미결제약정: BTC $18.5B (+2%) | ETH $8.2B (-1%)

🏦 매크로
DXY 104.2 | 10Y 4.35% | Fed Rate 4.50%

📰 뉴스 (최근 24h)
• SEC approves new crypto ETF...
• Bitcoin mining difficulty reaches...
```

### 3.2 수동 브리핑 전송

스케줄 외에 수동으로 브리핑을 생성/전송할 수 있다:

```bash
# Michael 실행 중일 때
node scripts/send-briefing.mjs
```

### 3.3 Claude AI 분석

브리핑에는 Claude AI가 수집 데이터를 종합 분석한 내용이 포함된다:

- **Market Regime**: `risk_on` / `risk_off` / `neutral` / `crisis`
- **Overall Score**: -100 (극도 약세) ~ +100 (극도 강세)
- **매매 추천**: 조건 충족 시 자동으로 Trade Proposal 생성

---

## 4. 포트폴리오 관리

### 4.1 자동 동기화

- **잔고 동기화**: 30분마다 Binance Spot + Futures 잔고를 자동 갱신
- **일일 스냅샷**: 매일 자정(UTC) 총자산, Spot/Futures 비율, BTC 가격 기록

### 4.2 수동 동기화

```bash
# Spot + Futures 잔고 즉시 동기화
python scripts/run.py sync_balance.py --user-id default

# 거래 내역 동기화 (특정 종목)
python scripts/run.py sync_transactions.py --user-id default --symbols BTCUSDT,ETHUSDT

# 일일 NAV 스냅샷 수동 생성
python scripts/run.py snapshot_nav.py --user-id default
```

### 4.3 포트폴리오 조회

Telegram에서 **💰 포트폴리오** 버튼을 탭하면:

```
💰 포트폴리오

총 자산: $12,345
Spot: $8,000 | Futures: $4,345

BTCUSDT │ $5,200 │ 42% │ +$320
ETHUSDT │ $3,100 │ 25% │ -$85
SOLUSDT │ $2,500 │ 20% │ +$150
BNBUSDT │ $1,000 │ 8%
USDT    │ $545   │ 4%

📅 마지막 스냅샷: 2026-02-11
```

---

## 5. 시장 분석

### 5.1 데이터 수집 (자동)

시스템이 자동으로 다양한 소스에서 데이터를 수집한다:

| 카테고리 | 수집 주기 | 데이터 |
|----------|----------|--------|
| 시장 데이터 | 6시간 | Top 20 코인 시세, Fear & Greed 지수 |
| 파생상품 | 4시간 | 펀딩레이트, 미결제약정, 롱숏비율, 테이커 거래량 |
| 매크로 | 12시간 | DXY, Fed 금리, 국채 수익률, M2, CPI |
| 뉴스 | 2시간 | CoinDesk, CoinTelegraph, The Block RSS |
| DeFi | 6시간 | 프로토콜별 TVL Top 20, 체인별 TVL Top 15 |
| ETF 흐름 | 평일 22시 | BTC/ETH ETF 유입/유출 |
| Smart Money | 12시간 | Binance 카피트레이딩 상위 트레이더 |
| 옵션 | 12시간 | BTC/ETH DVOL(변동성), Max Pain |

### 5.2 수동 분석 실행

```bash
# 일일 분석 (수집된 최근 24시간 데이터 종합)
python scripts/run.py analyze.py --daily --user-id default

# 주간 분석 (수집된 최근 7일 데이터 종합)
python scripts/run.py analyze.py --weekly --user-id default
```

### 5.3 분석 결과 구조

| 항목 | 설명 |
|------|------|
| **Market Regime** | `risk_on` (위험자산 선호) / `risk_off` (안전자산 선호) / `neutral` / `crisis` |
| **Overall Score** | -100 ~ +100. 가중치: 심리(20%), 파생(20%), 온체인(15%), 매크로(15%), 가격(15%), 뉴스(15%) |
| **Recommendations** | 매매 추천 목록 (종목, 방향, 사유, 신뢰도) |

---

## 6. 위험 모니터링 & 알림

### 6.1 자동 모니터링

| 모니터 | 주기 | 감시 항목 |
|--------|------|----------|
| 가격 모니터 | 5분 | 사용자 설정 가격 임계값 상회/하회 |
| 위험 모니터 | 15분 | 포지션 집중도, 청산가 근접도, 최대 낙폭(MDD) |

### 6.2 알림 유형

| 알림 | 심각도 | 조건 | Telegram 표시 |
|------|--------|------|--------------|
| **가격 상회** | ⚠️ warning | 현재가 > 설정 가격 | `⚠️ WARNING: BTC $98,000 초과` |
| **가격 하회** | ⚠️ warning | 현재가 < 설정 가격 | `⚠️ WARNING: ETH $2,500 미만` |
| **급락** | ⚠️/🚨 | 24시간 하락률 > 임계값 | `🚨 CRITICAL: SOL -15% 급락` |
| **집중도** | ⚠️ warning | 단일 포지션 > 50% | `⚠️ WARNING: BTC 비중 65% 과집중` |
| **청산 임박** | ⚠️/🚨 | 청산가까지 10% 이내 (5%=critical) | `🚨 CRITICAL: ETHUSDT 청산가 $2,100 근접` |
| **MDD 초과** | ⚠️/🚨 | 최대 낙폭 > 20% (30%=critical) | `⚠️ WARNING: MDD -22% 도달` |

### 6.3 알림 확인

Telegram에서 **확인** 버튼을 탭하면 해당 알림이 확인 처리된다. `🚨 CRITICAL` 알림에는 **포지션축소**, **손절설정** 액션 버튼이 함께 표시된다.

---

## 7. Semi-Auto 매매

**"분석 → 제안 → 승인 → 실행"** 워크플로우로 모든 매매가 이루어진다. 사용자 승인 없이는 주문이 실행되지 않는다.

### 7.1 매매 흐름

```
① AI 분석이 매매 기회 감지
   ↓
② Trade Proposal 생성 → Telegram 전송
   ┌──────────────────────────────────────┐
   │ 📋 매매 추천 #42                      │
   │ BUY BTCUSDT (spot) 0.05개 (~$4,860) │
   │ SL $94,000 | TP $102,000            │
   │ 사유: Fear & Greed 35, 과매도 반등 예상 │
   │ ⏰ 30분 후 만료                       │
   │                                      │
   │ [✅ 실행] [❌ 거부] [✏️ 수정]          │
   └──────────────────────────────────────┘
   ↓
③ 사용자가 ✅ 실행 탭
   ↓
④ Binance API로 주문 실행
   ↓
⑤ 결과 알림
   ✅ 체결: BUY 0.05 BTCUSDT @ $97,200
```

### 7.2 제안 만료

- 기본 30분 후 자동 만료 (`INVESTMENT_PROPOSAL_EXPIRY_MIN`)
- 만료된 제안에 ✅ 실행을 눌러도 `⏰ 제안 만료됨` 메시지가 표시됨

### 7.3 주문 유형

| 유형 | 설명 |
|------|------|
| `MARKET` | 시장가 즉시 체결 (가격 미지정) |
| `LIMIT` | 지정가 대기 주문 |
| Spot | 현물 매매 |
| Futures | 선물 매매 (레버리지 설정 가능) |

### 7.4 Dry Run (테스트)

실제 주문 없이 테스트:

```bash
python scripts/run.py execute_order.py --proposal-id 1 --dry-run
```

---

## 8. DCA (적립식 투자)

Dollar Cost Averaging — 정해진 금액을 정기적으로 매수하는 전략.

### 8.1 DCA 스케줄 설정

DB에 직접 등록하거나 Claude에게 요청:

| 설정 항목 | 예시 |
|-----------|------|
| 종목 | `BTCUSDT` |
| 금액 | `$100` (1회 매수 금액) |
| 주기 | `0 9 * * 1` (매주 월요일 오전 9시) |
| 계좌 | `spot` (현물) |

### 8.2 DCA 실행

```bash
# 활성 DCA 스케줄 전체 실행
python scripts/run.py execute_dca.py --user-id default

# 특정 스케줄만 실행
python scripts/run.py execute_dca.py --user-id default --dca-id 5

# 테스트 (주문 없이 시뮬레이션)
python scripts/run.py execute_dca.py --user-id default --dry-run
```

### 8.3 DCA 실행 기록

실행될 때마다 자동으로 기록:
- `total_invested`: 누적 투자 금액
- `total_quantity`: 누적 매수 수량
- `last_executed_at`: 마지막 실행 시간

---

## 9. 리밸런싱

목표 비중에 맞춰 포트폴리오를 재조정한다.

### 9.1 사용법

```bash
# 목표 비중 설정: BTC 50%, ETH 30%, USDT 20%
python scripts/run.py execute_rebalance.py --user-id default \
  --targets '{"BTCUSDT": 50, "ETHUSDT": 30, "USDT": 20}'

# --execute 플래그로 실제 실행 (없으면 시뮬레이션만)
python scripts/run.py execute_rebalance.py --user-id default \
  --targets '{"BTCUSDT": 50, "ETHUSDT": 30, "USDT": 20}' \
  --execute
```

### 9.2 동작 방식

1. 현재 보유량과 목표 비중을 비교
2. 각 종목별 매수/매도 필요량 계산
3. 1회 주문 한도(`MAX_ORDER_USD`) 초과 시 해당 종목 스킵 + 경고 메시지
4. `--execute` 시 Trade Proposal 생성 → 승인 워크플로우로 진행

---

## 10. 데이터 소스

### 10.1 API 기반 (무료, 인증 불필요)

| 소스 | 데이터 | 스크립트 |
|------|--------|----------|
| **CoinGecko** | Top 20 코인 시세, 시가총액 | `collect_market.py` |
| **Alternative.me** | Fear & Greed 지수 | `collect_market.py` |
| **Binance Futures API** | 펀딩레이트, OI, 롱숏비율 | `collect_binance_api.py` |
| **FRED** | DXY, Fed 금리, 국채, M2, CPI | `collect_macro.py` |
| **DefiLlama** | 프로토콜/체인 TVL | `collect_defi.py` |
| **Deribit** | BTC/ETH DVOL, Max Pain | `collect_options.py` |
| **RSS** | CoinDesk, CoinTelegraph, The Block | `collect_news.py` |

### 10.2 브라우저 기반 (Binance 인증 필요)

| 소스 | 데이터 | 스크립트 |
|------|--------|----------|
| **Farside Investors** | BTC/ETH ETF 유입/유출 | `collect_etf_flows.py` |
| **Binance Copy Trading** | 상위 트레이더 포지션 | `collect_smart_money.py` |

---

## 11. 자동 스케줄

Michael 시작 시 14개 cron job이 자동 실행된다:

### 포트폴리오

| Job | 주기 | 설명 |
|-----|------|------|
| 잔고 동기화 | 30분마다 | Spot + Futures 잔고 갱신 |
| NAV 스냅샷 | 매일 자정 | 일일 자산 가치 기록 |

### 데이터 수집

| Job | 주기 | 설명 |
|-----|------|------|
| 시장 데이터 | 6시간 | CoinGecko + Fear & Greed |
| 파생상품 | 4시간 | 펀딩레이트, OI, L/S비율 |
| 매크로 | 8AM/8PM | DXY, 금리, M2 |
| 뉴스 | 2시간 | RSS 피드 수집 |
| DeFi | 6시간 | TVL 데이터 |
| ETF 흐름 | 평일 22시 | BTC/ETH ETF |
| Smart Money | 12시간 | 카피트레이딩 |
| 옵션 | 12시간 | DVOL, Max Pain |

### 모니터링 & 분석

| Job | 주기 | 설명 |
|-----|------|------|
| 가격 모니터 | 5분 | 가격 임계값 감시 |
| 위험 모니터 | 15분 | 집중도, 청산, MDD |
| 일일 브리핑 | 매일 8AM | Claude AI 종합 분석 |
| 주간 분석 | 월요일 9AM | 주간 딥다이브 |

> 모든 시간은 UTC 기준

---

## 12. 안전장치

### 12.1 주문 한도

| 항목 | 기본값 | 환경변수 |
|------|--------|----------|
| 1회 주문 상한 | $10,000 | `INVESTMENT_MAX_ORDER_USD` |
| 제안 만료 시간 | 30분 | `INVESTMENT_PROPOSAL_EXPIRY_MIN` |

- **MARKET 주문**: 가격 미지정이므로 현재 시세를 자동 조회하여 주문 금액 검증
- **DCA**: 1회 금액이 주문 한도를 초과하면 실행 거부
- **리밸런싱**: 개별 주문이 한도 초과 시 해당 종목 스킵 + 경고

### 12.2 Semi-Auto 승인

- 모든 매매는 Telegram에서 사용자가 **✅ 실행** 버튼을 탭해야 실행
- 시스템이 자체적으로 주문을 실행하는 경우는 **없음**
- 제안 만료 시 자동 폐기 (실행 안 됨)

### 12.3 Dry Run

모든 실행 스크립트는 `--dry-run` 플래그를 지원한다. 실제 주문 없이 시뮬레이션:

```bash
python scripts/run.py execute_order.py --proposal-id 1 --dry-run
python scripts/run.py execute_dca.py --user-id default --dry-run
```

### 12.4 데이터 정리

- Research 테이블: 30일 이상 된 데이터 자동 삭제 (분석 실행 시)
- 거래 내역, 스냅샷: 영구 보관

---

## 13. CLI 레퍼런스

모든 Python 스크립트는 반드시 `scripts/run.py` 래퍼를 통해 실행한다:

```bash
python scripts/run.py <script_name> [options]
```

### 인증

| 명령 | 설명 |
|------|------|
| `auth_manager.py setup` | Binance 브라우저 로그인 |
| `auth_manager.py status` | 인증 상태 확인 |
| `auth_manager.py validate` | 브라우저 세션 유효성 검사 |

### 포트폴리오

| 명령 | 설명 |
|------|------|
| `sync_balance.py --user-id default` | 잔고 동기화 |
| `sync_transactions.py --user-id default --symbols BTCUSDT,ETHUSDT` | 거래내역 동기화 |
| `snapshot_nav.py --user-id default` | NAV 스냅샷 생성 |

### 데이터 수집

| 명령 | 설명 | 인증 |
|------|------|------|
| `collect_market.py` | 시세 + Fear & Greed | 불필요 |
| `collect_binance_api.py` | 펀딩레이트, OI | 불필요 |
| `collect_macro.py` | DXY, 금리, M2 | FRED_API_KEY |
| `collect_news.py` | RSS 뉴스 | 불필요 |
| `collect_defi.py` | DeFi TVL | 불필요 |
| `collect_options.py` | 옵션 변동성 | 불필요 |
| `collect_etf_flows.py` | ETF 흐름 | 브라우저 인증 |
| `collect_smart_money.py` | Smart Money | 브라우저 인증 |

### 분석

| 명령 | 설명 |
|------|------|
| `analyze.py --daily --user-id default` | 일일 종합 분석 |
| `analyze.py --weekly --user-id default` | 주간 딥다이브 분석 |

### 모니터링

| 명령 | 설명 |
|------|------|
| `monitor_prices.py --user-id default` | 가격 임계값 점검 |
| `monitor_risk.py --user-id default` | 위험 지표 점검 |

### 매매 실행

| 명령 | 설명 |
|------|------|
| `execute_order.py --proposal-id <ID>` | 승인된 제안 실행 |
| `execute_order.py --proposal-id <ID> --dry-run` | 테스트 (주문 안 함) |
| `execute_dca.py --user-id default` | DCA 스케줄 실행 |
| `execute_dca.py --user-id default --dry-run` | DCA 테스트 |
| `execute_rebalance.py --user-id default --targets '{...}'` | 리밸런싱 시뮬레이션 |
| `execute_rebalance.py --user-id default --targets '{...}' --execute` | 리밸런싱 실행 |

---

## 14. 문제 해결

### 서비스가 시작되지 않을 때

```bash
# 포트 충돌 확인
lsof -i :18789

# 기존 프로세스 종료 후 재시작
kill $(lsof -i :18789 -t)
pnpm build && pnpm start
```

### Telegram 버튼이 동작하지 않을 때

1. 로그에서 `📌 Handler registered for: investment` 확인
2. `✅ Investment service started` 확인
3. 로그에 `💰 Investment callback:` 메시지가 나오는지 확인
4. 서비스 재시작: `kill $(lsof -i :18789 -t) && pnpm build && pnpm start`

### 포트폴리오가 비어있을 때

```bash
# 수동 잔고 동기화
python scripts/run.py sync_balance.py --user-id default

# DB 직접 확인
sqlite3 data/memory.db "SELECT symbol, quantity FROM investment_holdings WHERE user_id='default'"
```

### 브리핑이 전송되지 않을 때

```bash
# 수동 브리핑 전송
node scripts/send-briefing.mjs

# 데이터 수집 상태 확인
sqlite3 data/memory.db "SELECT source, COUNT(*), MAX(collected_at) FROM investment_research GROUP BY source"
```

### API 키 관련 오류

```bash
# Binance API 연결 테스트
python scripts/run.py sync_balance.py --user-id default

# .env 파일 확인
grep BINANCE .env
```
