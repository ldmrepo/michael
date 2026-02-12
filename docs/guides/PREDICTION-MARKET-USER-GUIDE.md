# Prediction Market 사용자 가이드

Michael AI의 예측 시장(Prediction Market) 투자 서비스. Polymarket 연동으로 마켓 스캔, 포지션 관리, 차익거래 감지, 리스크 관리를 지원한다.

---

## 목차

1. [시작하기](#1-시작하기)
2. [핵심 개념](#2-핵심-개념)
3. [입금 가이드](#3-입금-가이드)
4. [마켓 스캔](#4-마켓-스캔)
5. [거래 실행](#5-거래-실행)
6. [포트폴리오 관리](#6-포트폴리오-관리)
7. [가격 모니터링](#7-가격-모니터링)
8. [차익거래 감지](#8-차익거래-감지)
9. [Kelly Criterion 포지션 사이징](#9-kelly-criterion-포지션-사이징)
10. [리스크 관리](#10-리스크-관리)
11. [CLI 레퍼런스](#11-cli-레퍼런스)
12. [문제 해결](#12-문제-해결)

---

## 1. 시작하기

### 1.1 필수 환경 변수

`.env` 파일에 다음을 설정한다:

```bash
# 필수 — Polymarket 거래용
POLYMARKET_PRIVATE_KEY=         # Polygon 지갑 private key (EOA)
POLYMARKET_PROXY_WALLET=        # Polymarket Proxy Wallet 주소

# 필수 — CLOB API 인증 (L2, 처음 1회 자동 파생 가능)
POLYMARKET_API_KEY=             # L2 API key
POLYMARKET_API_SECRET=          # L2 API secret
POLYMARKET_PASSPHRASE=          # L2 passphrase

# 선택 — 안전 한도
POLYMARKET_MAX_POSITION_USD=1000  # 단일 포지션 상한 (USD)

# 선택 — Polygon RPC (기본값 있음)
POLYGON_RPC_URL=https://polygon-rpc.com
```

### 1.2 지갑 준비

Polymarket은 **2개의 지갑**을 사용한다:

| 지갑 | 역할 | 설명 |
|------|------|------|
| **EOA** | 서명 지갑 | Private key를 보유. 거래 서명에 사용 |
| **Proxy Wallet** | 거래 지갑 | Polymarket이 EOA 기반으로 생성한 스마트 컨트랙트. **실제 USDC 잔고** |

```
[CEX] → USDC (Polygon) → [EOA] → transfer → [Proxy Wallet] = Polymarket 잔고
```

> **핵심**: Polymarket 거래 잔고 = **Proxy Wallet의 USDC.e 잔고**. EOA에 USDC를 보내도 Polymarket에서 보이지 않는다.

### 1.3 L2 API 키 파생 (처음 1회)

L2 키가 없으면 L1 서명에서 자동으로 파생할 수 있다:

```bash
# Python 환경에서 실행
cd .claude/skills/prediction-market
python scripts/run.py polymarket_client.py derive-keys
```

파생된 `api_key`, `api_secret`, `api_passphrase`를 `.env`에 저장한다.

### 1.4 환경 설정

첫 실행 시 자동으로 Python 가상환경이 생성된다:

```bash
# 수동 설정 (필요 시)
cd .claude/skills/prediction-market
python scripts/run.py setup_environment.py
```

### 1.5 연결 테스트

```bash
# 잔고 확인 (거래 없이 읽기만)
python scripts/run.py wallet_utils.py balance

# 결과 예시:
# ==================================================
#   Polygon Wallet Balances
# ==================================================
#   Address:      0xcd0935708e63634AbC0aff4f1a5FC5FC763d035d
#   USDC.e:       $116.560000  (Polymarket)
#   Native USDC:  $0.000000  (needs swap)
#   POL:          9.452000
#   Gas Price:    30.00 gwei
#   Transfer Cost: ~0.001950 POL
#   Can Transfer: YES
# ==================================================
```

---

## 2. 핵심 개념

### 2.1 YES/NO 계약

| 개념 | 설명 |
|------|------|
| **YES 계약** | 이벤트 발생 시 $1.00 수령, 미발생 시 $0.00 |
| **NO 계약** | 이벤트 미발생 시 $1.00 수령, 발생 시 $0.00 |
| **가격 = 확률** | YES 70¢ = 시장이 70% 확률로 평가 |
| **YES + NO = $1.00** | 항상 상보적 관계 |

### 2.2 Polymarket 구조

| 구성 요소 | 역할 |
|-----------|------|
| **Gamma API** | 마켓 탐색 (공개, 인증 불필요) |
| **CLOB API** | 거래 실행 (py-clob-client, 인증 필요) |
| **Data API** | 히스토리컬 분석 (공개/인증) |
| **Polygon POS** | 결제 체인 (USDC.e, Chain ID 137) |

### 2.3 주요 용어

| 용어 | 설명 |
|------|------|
| **CLOB** | Central Limit Order Book — 오더북 기반 매칭 |
| **Neg Risk** | 다중 결과 마켓 (올림픽, 선거 등) |
| **USDC.e** | Bridged USDC — Polymarket의 결제 토큰 |
| **Conditional Token (CTF)** | ERC-1155 기반 포지션 토큰 |
| **Maker/Taker** | 유동성 공급자/소비자 |
| **Kelly Criterion** | 최적 포지션 크기 계산 공식 |

---

## 3. 입금 가이드

### 3.1 방법 1: USDC.e 직접 입금 (권장)

1. Polymarket UI → Settings → Funding → Proxy Wallet 주소 확인
2. CEX에서 **USDC.e**를 Proxy Wallet에 직접 전송
3. Approval이 설정되어 있다면 잔고에 자동 반영

### 3.2 방법 2: Binance → 스왑 → 입금 (실전 검증됨)

**전체 플로우 (USDT → Polymarket):**

```
① Binance: USDT → USDC 변환 (USDCUSDT 시장가)
② Binance: USDC Polygon 출금 → EOA (Native USDC 도착)
③ EOA에 POL 필요 (가스비) → Binance에서 POL 별도 출금
④ Paraswap DEX: Native USDC → USDC.e 스왑 ($50 청크!)
⑤ USDC.e → Proxy Wallet 전송
⑥ Proxy Factory approve (최초 1회)
```

### 3.3 주의사항

| 항목 | 내용 |
|------|------|
| **USDC vs USDC.e** | Binance 출금 = **Native USDC**. Polymarket은 **USDC.e만** 인식. DEX 스왑 필수 |
| **Paraswap 대량 스왑** | $100+ 단일 스왑 시 revert. **$50 청크로 분할** 필요 |
| **Paraswap approve 대상** | `TokenTransferProxy`(`0x216b4b...`)에 approve. Router(`0xDEF1...`)가 아님! |
| **POL 가스비** | EOA에 POL 없으면 모든 온체인 작업 불가. 최소 1 POL 확보 |
| **네트워크** | 반드시 **Polygon POS**로 출금. 다른 체인으로 보내면 자금 손실 |

### 3.4 Approval 설정 (첫 거래 전 필수)

입금 후 Polymarket에서 "Activate your funds" 단계가 필요하다:

**UI 방법**: Portfolio → "Activate your funds" → Continue

**프로그래밍 방법** (Magic.Link 세션 만료 시):
```bash
# USDC.e approve + CTF setApprovalForAll × 3 operators = 6 calls
# Proxy Factory의 proxy() 메서드로 배치 실행
```

### 3.5 잔고 확인

```bash
# EOA의 모든 잔고 (USDC.e + Native USDC + POL)
python scripts/run.py wallet_utils.py balance

# 특정 주소 잔고
python scripts/run.py wallet_utils.py balance --address 0x5C4A...

# JSON 출력
python scripts/run.py wallet_utils.py balance --json
```

### 3.6 USDC 전송

```bash
# Proxy Wallet로 전송 (전체 잔고)
python scripts/run.py wallet_utils.py transfer-usdc --to-proxy

# 특정 금액 전송
python scripts/run.py wallet_utils.py transfer-usdc --to 0x5C4A... --amount 100

# 시뮬레이션 (전송 없이 확인만)
python scripts/run.py wallet_utils.py transfer-usdc --to-proxy --dry-run
```

---

## 4. 마켓 스캔

`scan_markets.py`로 수익 기회를 탐색한다. 인증 없이도 사용 가능 (Gamma API 기반).

### 4.1 고확률 채권형 스캔

90%+ 확률 마켓에서 채권형 수익 기회를 찾는다:

```bash
# 기본 (90%+ 확률)
python scripts/run.py scan_markets.py --high-prob

# 95%+ 확률만
python scripts/run.py scan_markets.py --high-prob --threshold 0.95

# 300개 마켓 스캔 (페이지네이션)
python scripts/run.py scan_markets.py --high-prob --pages 3

# 결과 예시:
# ┌──────────────────────────────┬──────┬───────┬──────┬────────┬────┬─────────┬────────┐
# │ Question                     │ Side │ Price │ ROI% │Ann.ROI%│Days│ Vol24h  │ Liq    │
# ├──────────────────────────────┼──────┼───────┼──────┼────────┼────┼─────────┼────────┤
# │ Will Fed hold rates in Mar?  │ YES  │ $0.95 │ 5.3% │  193%  │ 10 │$125,000 │$89,000 │
# │ BTC above $50K end of Feb?   │ YES  │ $0.97 │ 3.1% │   85%  │ 13 │ $89,000 │$67,000 │
# └──────────────────────────────┴──────┴───────┴──────┴────────┴────┴─────────┴────────┘
```

**결과 필드 설명:**

| 필드 | 설명 |
|------|------|
| **Side** | 고확률 방향 (YES 또는 NO) |
| **Price** | 현재 가격 (= 시장이 평가하는 확률) |
| **ROI%** | 정산 시 예상 수익률 |
| **Ann.ROI%** | 연환산 수익률 (자본 효율성 평가) |
| **Days** | 정산까지 남은 일수 |
| **Vol24h** | 24시간 거래량 (유동성 지표) |
| **Liq** | 오더북 유동성 |

### 4.2 신규 마켓 스캔

최근 등록된 마켓을 찾는다:

```bash
# 최근 24시간
python scripts/run.py scan_markets.py --new

# 최근 48시간
python scripts/run.py scan_markets.py --new --hours 48
```

### 4.3 볼륨 상위 마켓

거래가 활발한 인기 마켓:

```bash
python scripts/run.py scan_markets.py --high-volume --limit 20
```

### 4.4 태그별 필터링

```bash
# 크립토 마켓
python scripts/run.py scan_markets.py --tag crypto

# 정치 마켓
python scripts/run.py scan_markets.py --tag politics

# 스포츠 마켓
python scripts/run.py scan_markets.py --tag sports
```

### 4.5 텍스트 검색

```bash
python scripts/run.py scan_markets.py --search "bitcoin"
python scripts/run.py scan_markets.py --search "Fed rate"
```

### 4.6 워치리스트 저장

발견한 마켓을 DB에 저장하여 모니터링할 수 있다:

```bash
# 스캔 결과를 DB에 저장
python scripts/run.py scan_markets.py --high-prob --save

# JSON 출력 (프로그래밍용)
python scripts/run.py scan_markets.py --high-prob --json
```

---

## 5. 거래 실행

### 5.1 거래 전 체크리스트

1. `.env`에 5개 환경변수 설정 완료 (`PRIVATE_KEY`, `API_KEY`, `API_SECRET`, `PASSPHRASE`, `PROXY_WALLET`)
2. Proxy Wallet에 USDC.e 잔고 확인
3. Approval 설정 완료 (최초 1회)
4. 소액 테스트 후 본 거래

### 5.2 주문 유형

| 유형 | 설명 | 사용 시점 |
|------|------|----------|
| **Limit Order** | 지정가 주문 | 정확한 가격에 진입하고 싶을 때 |
| **Market Order** | 시장가 주문 | 즉시 체결이 필요할 때 |
| **GTC** | Good Till Cancel | 취소 전까지 유효 (기본값) |

### 5.3 즉시 체결 전략 (실전 검증)

```
Best ask 정확히 그 가격에 주문 → LIVE로 남는 경우 있음
Best ask + $0.01로 주문       → 즉시 MATCHED (권장)
```

1센트 추가 비용은 미미하지만 체결 확실성이 크게 향상된다.

### 5.4 프로그래밍 거래 예시

```python
from py_clob_client.clob_types import OrderArgs, OrderType

# 1) 현재가 조회 (dict 반환 주의!)
resp = clob.get_price(token_id, 'buy')
ask = float(resp['price'])  # {'price': '0.94'} → 0.94

# 2) 주문 생성 (OrderArgs 객체 필수, dict X)
order_args = OrderArgs(
    token_id=token_id,
    price=round(min(ask + 0.01, 0.99), 2),
    size=10,
    side='BUY',
)

# 3) 서명 + 제출
signed = clob.create_order(order_args)
result = clob.post_order(signed, OrderType.GTC)
# result: {"orderID": "...", "status": "MATCHED"}
```

### 5.5 배치 주문 (여러 마켓 동시 진입)

```python
import time
orders = [
    {'name': 'Fed Hold YES', 'tid': '3663129...', 'size': 70},
    {'name': 'BTC $50K NO',  'tid': '5721884...', 'size': 60},
]
for o in orders:
    resp = clob.get_price(o['tid'], 'buy')
    ask = float(resp['price'])
    buy_price = round(min(ask + 0.01, 0.99), 2)

    order_args = OrderArgs(price=buy_price, size=o['size'],
                           side='BUY', token_id=o['tid'])
    signed = clob.create_order(order_args)
    result = clob.post_order(signed, OrderType.GTC)
    print(f"{o['name']}: {result.get('status')} @ ${buy_price}")
    time.sleep(1)  # rate limit 방지
```

### 5.6 주문 상태

| Status | 의미 |
|--------|------|
| `MATCHED` | 즉시 체결됨 |
| `LIVE` | 오더북에 대기 중 (미체결) |
| `DELAYED` | 지연 처리 중 |
| `CANCELED` | 취소됨 |

### 5.7 수수료 (2026년 현재)

| 항목 | 비율 |
|------|------|
| Maker 수수료 | **0%** |
| Taker 수수료 | **0%** |
| 출금 수수료 | ~2% |
| Polygon 가스비 | <$0.01 |

---

## 6. 포트폴리오 관리

### 6.1 포지션 조회

```python
# Python에서 현재 포지션 조회
from polymarket_client import create_client
client = create_client()
positions = client.get_positions()
```

### 6.2 잔고 확인

```python
balance = client.get_balance_usdc()
print(f"Available: ${balance:.2f}")
```

### 6.3 포트폴리오 분산 원칙

**카테고리 분산** — 상관관계 낮은 이벤트 유형 혼합:

| 카테고리 | 목표 비중 | 예시 |
|----------|----------|------|
| 크립토/금융 | 30~40% | BTC 가격 범위, ETH ETF |
| 경제/통화 | 25~35% | Fed 금리 결정, 실업률 |
| 지정학 | 15~25% | 전쟁/평화, 정권 교체 |
| 스포츠/기타 | 5~15% | 올림픽, 선거 |

**정산일 분산** — 자본 회전과 유동성 확보:

| 기간 | 비중 | 특성 |
|------|------|------|
| 1주 이내 | 20~30% | 빠른 회전 |
| 1~4주 | 30~40% | 핵심 수익 |
| 1~6개월 | 20~30% | 높은 ROI, 자본 잠김 |

**포지션 크기** — 단일 마켓 리스크 제한:
- 단일 포지션: 전체 자본의 10% 이하
- 같은 카테고리: 전체 자본의 40% 이하
- 현금(USDC.e) 유지: 전체의 10~20%

### 6.4 마켓 선별 기준

```
✅ YES 가격 90~97¢ (ROI 3~11%)
✅ 정산까지 5~120일
✅ 유동성 $50K+ (슬리피지 방지)
✅ 볼륨 $10K+/24h (활성 시장)
❌ 99¢+ (ROI 1% 미만)
❌ 정산 6개월+ (자본 잠김 과다)
❌ 기존 포지션과 동일 카테고리 과다
```

---

## 7. 가격 모니터링

`monitor_prices.py`로 관심 마켓의 가격 변동을 추적한다.

### 7.1 특정 마켓 모니터링

```bash
# 1회 체크
python scripts/run.py monitor_prices.py --market-id <condition_id> --once

# 연속 모니터링 (60초 간격)
python scripts/run.py monitor_prices.py --market-id <condition_id> --interval 60

# 5% 이상 변동 시 알림
python scripts/run.py monitor_prices.py --market-id <condition_id> --threshold 5
```

### 7.2 워치리스트 전체 모니터링

```bash
# DB에 저장된 워치리스트 전체
python scripts/run.py monitor_prices.py --watchlist --once

# JSON 출력
python scripts/run.py monitor_prices.py --watchlist --once --json
```

---

## 8. 차익거래 감지

`monitor_arbitrage.py`로 Polymarket vs Kalshi 간 가격 차이를 감지한다.

### 8.1 1회 스캔

```bash
# 3%+ 순이익 기회만 표시
python scripts/run.py monitor_arbitrage.py --once --threshold 3.0

# 50개 마켓 스캔
python scripts/run.py monitor_arbitrage.py --once --limit 50
```

### 8.2 연속 모니터링

```bash
# 5분 간격 연속 스캔
python scripts/run.py monitor_arbitrage.py --continuous --interval 300
```

### 8.3 결과 해석

| 필드 | 설명 |
|------|------|
| **PM Price** | Polymarket 가격 |
| **Kalshi Price** | Kalshi 가격 |
| **Spread%** | 가격 차이 비율 |
| **Net Profit%** | 수수료 차감 후 순이익률 |

> **주의**: 정산 조건의 미묘한 차이를 반드시 확인해야 한다 (날짜, 기준가, 소스가 다를 수 있음).

---

## 9. Kelly Criterion 포지션 사이징

`calculate_kelly.py`로 최적 포지션 크기를 계산한다.

### 9.1 기본 사용

```bash
# 내 추정 확률 75%, 현재 시장가 60¢, 자본 $1,000
python scripts/run.py calculate_kelly.py \
  --estimated-prob 0.75 \
  --market-price 0.60 \
  --bankroll 1000

# 결과 예시:
# Kelly Criterion Analysis
# ─────────────────────────
# Estimated Probability: 75.0%
# Market Price: $0.60
# Edge: +15.0%
# Direction: BUY YES
# Full Kelly: 37.5% ($375.00, 625 contracts)
# Half Kelly: 18.8% ($187.50, 312 contracts)
# Expected Value: $56.25 per $100
```

### 9.2 마켓 ID로 자동 현재가 조회

```bash
# 마켓 ID 지정 시 현재가를 자동으로 조회
python scripts/run.py calculate_kelly.py \
  --estimated-prob 0.80 \
  --market-id <condition_id> \
  --bankroll 500
```

### 9.3 Kelly 분율 조절

| 분율 | 용도 | 설명 |
|------|------|------|
| 1.0 (Full Kelly) | 이론적 최적 | 변동성 매우 높음, 비권장 |
| **0.5 (Half Kelly)** | **실전 권장** | 좋은 수익률 + 관리 가능한 변동성 |
| 0.25 (Quarter Kelly) | 보수적 | 확신도 낮을 때 |

```bash
# Quarter Kelly
python scripts/run.py calculate_kelly.py \
  --estimated-prob 0.65 \
  --market-price 0.55 \
  --bankroll 1000 \
  --fraction 0.25
```

### 9.4 Kelly 공식

```
f* = (bp - q) / b
b = 순이익 배율 = (1 - price) / price
p = 내 추정 승률
q = 1 - p

예: 60¢ YES 매수, 실제 확률 75%
b = (1 - 0.60) / 0.60 = 0.667
f* = (0.667 × 0.75 - 0.25) / 0.667 = 37.5%
Half Kelly → 18.75% 배분
```

---

## 10. 리스크 관리

### 10.1 핵심 리스크

| 리스크 | 설명 | 대응 |
|--------|------|------|
| **이벤트 리스크** | 고확률 마켓도 5~10% 확률로 전액 손실 | 포트폴리오 분산 (10개+ 포지션) |
| **유동성 리스크** | 볼륨 적은 마켓에서 청산 어려움 | Vol $10K+, Liq $50K+ 마켓만 |
| **정산 리스크** | UMA 분쟁으로 정산 지연/변경 | 논쟁적 마켓 회피 |
| **플랫폼 리스크** | Polymarket 서비스 장애/규제 | 자본의 일부만 배치 |
| **스마트 컨트랙트 리스크** | 컨트랙트 취약점 | 검증된 마켓만 거래 |
| **자본 잠김 리스크** | 정산까지 장기간 대기 | 정산일 분산 |

### 10.2 안전장치

| 항목 | 설정 |
|------|------|
| 단일 포지션 상한 | `POLYMARKET_MAX_POSITION_USD` (기본 $1,000) |
| 카테고리 집중도 | 전체 자본의 40% 이하 |
| 현금 유지비율 | 10~20% |
| 최소 유동성 | $50K+ |

### 10.3 크립토 투자 헤지

Prediction market은 크립토 포지션의 이벤트 헤지 수단으로 활용 가능하다:

| 기존 포지션 | 리스크 이벤트 | 헤지 방법 |
|------------|--------------|----------|
| BTC 롱 | Fed 금리 인상 | "Fed Holds Rates" NO 매수 |
| ETH 롱 | 규제 발표 | "US Crypto Ban" YES 매수 |
| 전체 포트폴리오 | 블랙스완 | 저확률 고수익 이벤트 YES 매수 |

---

## 11. CLI 레퍼런스

모든 스크립트는 `scripts/run.py`를 통해 실행한다 (가상환경 자동 관리).

### 11.1 wallet_utils.py — 지갑 관리

```bash
# 잔고 확인
python scripts/run.py wallet_utils.py balance [--address ADDR] [--json]

# USDC 전송
python scripts/run.py wallet_utils.py transfer-usdc \
  --to ADDR | --to-proxy \
  [--amount USDC_AMOUNT] \
  [--dry-run] [--json]
```

| 옵션 | 설명 |
|------|------|
| `balance` | USDC.e, Native USDC, POL 잔고 확인 |
| `--address` | 특정 주소 조회 (기본: EOA) |
| `transfer-usdc` | USDC 전송 |
| `--to` | 목적지 주소 |
| `--to-proxy` | Proxy Wallet으로 전송 |
| `--amount` | 금액 (기본: 전체 잔고) |
| `--dry-run` | 시뮬레이션 (전송 없음) |

### 11.2 scan_markets.py — 마켓 스캔

```bash
python scripts/run.py scan_markets.py \
  --high-prob | --new | --high-volume | --tag TAG | --search TEXT \
  [--threshold 0.90] [--hours 24] [--limit 50] [--pages 1] \
  [--save] [--json]
```

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--high-prob` | 고확률 채권형 마켓 | - |
| `--new` | 신규 마켓 | - |
| `--high-volume` | 볼륨 상위 마켓 | - |
| `--tag` | 태그별 필터 (crypto, politics, sports) | - |
| `--search` | 텍스트 검색 | - |
| `--threshold` | 확률 임계값 (--high-prob) | 0.90 |
| `--hours` | 시간 범위 (--new) | 24 |
| `--limit` | 최대 결과 수 | 50 |
| `--pages` | 페이지 수 (--high-prob, 각 100개) | 1 |
| `--save` | 결과를 DB 워치리스트에 저장 | false |
| `--json` | JSON 출력 | false |

### 11.3 monitor_prices.py — 가격 모니터링

```bash
python scripts/run.py monitor_prices.py \
  --market-id ID | --watchlist \
  [--threshold 5.0] [--interval 60] [--once] [--json]
```

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--market-id` | 특정 마켓 모니터링 | - |
| `--watchlist` | DB 워치리스트 전체 | - |
| `--threshold` | 알림 임계값 (%) | 5.0 |
| `--interval` | 체크 간격 (초) | 60 |
| `--once` | 1회만 실행 | false |

### 11.4 monitor_arbitrage.py — 차익거래 감지

```bash
python scripts/run.py monitor_arbitrage.py \
  [--threshold 3.0] [--limit 50] \
  [--once] [--continuous] [--interval 300] [--json]
```

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--threshold` | 최소 순이익 (%) | 3.0 |
| `--limit` | 플랫폼당 스캔 마켓 수 | 50 |
| `--once` | 1회 스캔 | false |
| `--continuous` | 연속 모니터링 | false |
| `--interval` | 스캔 간격 (초) | 300 |

### 11.5 calculate_kelly.py — 포지션 사이징

```bash
python scripts/run.py calculate_kelly.py \
  --estimated-prob PROB \
  [--market-price PRICE | --market-id ID] \
  [--bankroll 1000] [--fraction 0.5] [--json]
```

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--estimated-prob` | 내 추정 확률 (0~1) | **필수** |
| `--market-price` | 현재 시장가 (0~1) | 0 |
| `--market-id` | 마켓 ID (자동 현재가 조회) | - |
| `--bankroll` | 가용 자본 ($) | 1000 |
| `--fraction` | Kelly 분율 (0.25~1.0) | 0.5 |

---

## 12. 문제 해결

### 12.1 연결/인증 오류

| 에러 | 원인 | 해결 |
|------|------|------|
| `Cannot connect to any Polygon RPC` | RPC rate limit | 다른 RPC 자동 시도됨. 반복 시 잠시 대기 |
| `not enough balance / allowance` | signature_type 불일치 | `POLY_PROXY` + `funder=proxy_wallet` 확인 |
| `Missing API credentials` | .env 미설정 | 5개 환경변수 모두 설정 확인 |
| `web3 not installed` | 의존성 누락 | `python scripts/run.py setup_environment.py` |

### 12.2 거래 오류

| 에러 | 원인 | 해결 |
|------|------|------|
| `LIVE` 상태 유지 | 가격이 best ask보다 낮음 | ask + $0.01로 재주문 |
| `'dict' object has no attribute 'token_id'` | dict 대신 OrderArgs 필요 | `OrderArgs(...)` 객체 사용 |
| `float() argument... not 'dict'` | `get_price()` dict 반환 | `float(result['price'])` 파싱 |
| `AttributeError: 'NoneType'...` | `get_balance_allowance()` params 누락 | `BalanceAllowanceParams(...)` 전달 |

### 12.3 입금/스왑 오류

| 에러 | 원인 | 해결 |
|------|------|------|
| Polymarket 잔고 0 | Native USDC 입금 | USDC.e로 DEX 스왑 후 Proxy에 전송 |
| Paraswap TX revert | 대량 스왑 | $50 청크로 분할 |
| "Activate your funds" 실패 | Magic.Link 세션 만료 | Proxy Factory `proxy()` 직접 실행 |
| `insufficient funds for gas` | POL 부족 | EOA에 POL 추가 출금 |

### 12.4 Gamma API 관련

| 문제 | 원인 | 해결 |
|------|------|------|
| `tokens` 배열이 비어있음 | Gamma API 특성 | `outcomePrices` JSON 파싱으로 가격 확인 |
| 100개 이상 마켓 조회 불가 | 페이지 제한 | `offset` 파라미터로 페이지네이션 |
| 날짜 비교 오류 | `endDateIso` timezone 없음 | `endDate` (ISO+Z suffix) 사용 |
| `liquidity` 타입 오류 | 문자열 반환 | `liquidityNum` (숫자) 필드 사용 |

### 12.5 DB 관련

```bash
# DB 테이블 확인
sqlite3 data/memory.db ".tables" | grep pm_

# 워치리스트 조회
sqlite3 data/memory.db "SELECT id, question, volume FROM pm_markets LIMIT 10"

# 가격 스냅샷 조회
sqlite3 data/memory.db "SELECT * FROM pm_prices ORDER BY recorded_at DESC LIMIT 5"
```

---

## 부록: 아키텍처 요약

```
.claude/skills/prediction-market/
├── SKILL.md                     # 스킬 정의 + 전략 가이드 + 실전 교훈
├── references/                  # API 레퍼런스, 전략 문서
├── requirements.txt             # Python 의존성
├── data/                        # 로컬 데이터
└── scripts/
    ├── config.py                # 환경변수, 상수, 컨트랙트 주소
    ├── polymarket_client.py     # 코어 API 클라이언트 (Gamma + CLOB + Data)
    ├── db_utils.py              # SQLite (마켓, 가격, 포지션, 거래내역)
    ├── wallet_utils.py          # 온체인 지갑 (잔고, 전송)
    ├── scan_markets.py          # 마켓 스캐너 (고확률, 신규, 볼륨, 태그)
    ├── monitor_prices.py        # 가격 모니터링
    ├── monitor_arbitrage.py     # 크로스 플랫폼 차익거래 감지
    ├── calculate_kelly.py       # Kelly Criterion 포지션 사이징
    ├── output_format.py         # 출력 포맷팅 유틸
    ├── run.py                   # 유니버설 러너 (venv 자동 관리)
    └── setup_environment.py     # venv 생성 + 의존성 설치
```

**API 계층:**

| 계층 | 인증 | 용도 | 스크립트 |
|------|------|------|---------|
| **Gamma API** | 불필요 | 마켓 탐색, 검색 | scan_markets, monitor_prices |
| **CLOB API** | Private Key + L2 | 거래 실행, 잔고 | polymarket_client |
| **Data API** | 선택적 | 히스토리컬 분석 | polymarket_client |
| **Polygon RPC** | 불필요 | 온체인 잔고, 전송 | wallet_utils |
