# Prediction Market — Polymarket API 기술 레퍼런스

## Table of Contents

- [API 아키텍처](#api-아키텍처)
- [엔드포인트 목록](#엔드포인트-목록)
- [인증 & Rate Limits](#인증--rate-limits)
- [WebSocket 실시간 데이터](#websocket-실시간-데이터)
- [Python 라이브러리](#python-라이브러리)
- [주문 실행](#주문-실행)
- [Resolution & Settlement](#resolution--settlement)
- [코드 예제](#코드-예제)

---

## API 아키텍처

Polymarket은 3개의 분리된 API 레이어를 제공한다:

```
┌─────────────────────────────────────────────────┐
│              Polymarket API Stack                │
├─────────────────────────────────────────────────┤
│  Gamma Markets API (고수준)                      │
│  - 마켓 메타데이터, 카테고리, 설명               │
│  - 공개 접근, 인증 불필요                        │
│  - Base: https://gamma-api.polymarket.com        │
├─────────────────────────────────────────────────┤
│  CLOB API (거래 엔진)                            │
│  - 오더북, 주문 실행, 포지션 관리               │
│  - 인증 필요 (API Key + Secret)                 │
│  - Base: https://clob.polymarket.com             │
├─────────────────────────────────────────────────┤
│  Data API (분석용)                               │
│  - 히스토리컬 데이터, 볼륨, 가격 차트           │
│  - 공개 접근                                     │
│  - Base: https://data-api.polymarket.com         │
└─────────────────────────────────────────────────┘
```

| API | 용도 | 인증 | Rate Limit |
|-----|------|------|-----------|
| Gamma Markets | 마켓 탐색, 메타데이터 | 불필요 | 100 req/min |
| CLOB | 거래 실행, 오더북 | API Key + HMAC | 100 req/min |
| Data | 히스토리컬 분석 | 불필요 | 60 req/min |

---

## 엔드포인트 목록

### Gamma Markets API

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/markets` | GET | 모든 활성 마켓 목록 |
| `/markets/{id}` | GET | 특정 마켓 상세 정보 |
| `/markets?tag={tag}` | GET | 태그별 마켓 필터링 |
| `/events` | GET | 이벤트 목록 (마켓 그룹) |
| `/events/{id}` | GET | 특정 이벤트 상세 |

**마켓 응답 구조:**
```json
{
  "id": "0x...",
  "question": "Will BTC reach $150K by June 2026?",
  "description": "This market resolves...",
  "outcomes": ["Yes", "No"],
  "outcomePrices": ["0.35", "0.65"],
  "volume": "5234567.89",
  "liquidity": "1234567.89",
  "endDate": "2026-06-30T00:00:00Z",
  "active": true,
  "closed": false,
  "tags": ["crypto", "bitcoin"],
  "conditionId": "0x...",
  "questionId": "0x..."
}
```

### CLOB API

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/book` | GET | 오더북 스냅샷 |
| `/midpoint` | GET | 현재 중간가격 |
| `/price` | GET | 특정 사이드 최적 가격 |
| `/spread` | GET | Bid-Ask 스프레드 |
| `/order` | POST | 주문 제출 |
| `/cancel` | DELETE | 주문 취소 |
| `/orders` | GET | 내 주문 목록 |
| `/trades` | GET | 내 체결 내역 |
| `/positions` | GET | 현재 포지션 |
| `/balances` | GET | USDC 잔액 |

**오더북 응답 구조:**
```json
{
  "market": "0x...",
  "asset_id": "YES-token-id",
  "bids": [
    {"price": "0.48", "size": "5000"},
    {"price": "0.47", "size": "8000"}
  ],
  "asks": [
    {"price": "0.52", "size": "3000"},
    {"price": "0.53", "size": "2000"}
  ],
  "timestamp": "2026-01-15T12:00:00Z"
}
```

### Data API

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/prices` | GET | 가격 히스토리 |
| `/volume` | GET | 볼륨 히스토리 |
| `/trades` | GET | 공개 체결 내역 |
| `/timeseries` | GET | 시계열 데이터 |

---

## 인증 & Rate Limits

### 공개 엔드포인트 (인증 불필요)

Gamma Markets API와 Data API는 인증 없이 접근 가능:
```bash
curl "https://gamma-api.polymarket.com/markets?limit=10"
```

### 인증 엔드포인트 (CLOB API)

CLOB API는 **API Key + HMAC 서명** 필요:

```python
import hmac
import hashlib
import time

API_KEY = "your-api-key"
API_SECRET = "your-api-secret"
PASSPHRASE = "your-passphrase"

timestamp = str(int(time.time()))
message = timestamp + method + path + body
signature = hmac.new(
    API_SECRET.encode(),
    message.encode(),
    hashlib.sha256
).hexdigest()

headers = {
    "POLY_API_KEY": API_KEY,
    "POLY_SIGNATURE": signature,
    "POLY_TIMESTAMP": timestamp,
    "POLY_PASSPHRASE": PASSPHRASE,
}
```

### API Key 발급

1. Polymarket 계정 로그인
2. Settings → API Keys
3. API Key + Secret + Passphrase 발급
4. **보안**: Secret은 발급 시 1회만 표시, 안전하게 보관

### Rate Limits

| API | 제한 | 초과 시 |
|-----|------|---------|
| Gamma Markets | 100 req/min | 429 Too Many Requests |
| CLOB | 100 req/min (인증), 10 req/min (비인증) | 429 + 60초 쿨다운 |
| Data | 60 req/min | 429 |
| WebSocket | 5 connections/IP | 연결 거부 |

**Best Practice:**
- 요청 간 최소 600ms 간격 유지
- 429 응답 시 `Retry-After` 헤더 준수
- 배치 가능한 요청은 묶어서 전송

---

## WebSocket 실시간 데이터

### 연결

```python
import websockets
import json

async def connect_orderbook():
    uri = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    async with websockets.connect(uri) as ws:
        # 마켓 구독
        await ws.send(json.dumps({
            "type": "subscribe",
            "market": "0x...",
            "channel": "book"
        }))

        async for message in ws:
            data = json.loads(message)
            process_update(data)
```

### 채널 종류

| 채널 | 데이터 | 지연 |
|------|--------|------|
| `book` | 오더북 업데이트 | <50ms |
| `trades` | 실시간 체결 | <100ms |
| `price` | 가격 변동 | <50ms |
| `market` | 마켓 상태 변경 | <1s |

### 오더북 업데이트 메시지

```json
{
  "type": "book_update",
  "market": "0x...",
  "side": "buy",
  "price": "0.52",
  "size": "3500",
  "timestamp": 1705312800000
}
```

---

## Python 라이브러리

### py-clob-client (공식)

```bash
pip install py-clob-client
```

```python
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

# 클라이언트 초기화
client = ClobClient(
    host="https://clob.polymarket.com",
    key=API_KEY,
    chain_id=137,  # Polygon
    signature_type=2,  # POLY_GNOSIS_SAFE
    funder=WALLET_ADDRESS,
)

# 오더북 조회
book = client.get_order_book(token_id="YES-token-id")
print(f"Best bid: {book.bids[0].price}")
print(f"Best ask: {book.asks[0].price}")

# 주문 제출
order = client.create_and_post_order(OrderArgs(
    token_id="YES-token-id",
    price=0.50,
    size=100,
    side="BUY",
))
print(f"Order ID: {order.id}")
```

### polymarket-apis (커뮤니티)

```bash
pip install polymarket-apis
```

```python
from polymarket import Polymarket

pm = Polymarket()

# 마켓 검색
markets = pm.get_markets(tag="crypto", limit=10)
for m in markets:
    print(f"{m.question}: YES={m.yes_price:.0%}")

# 가격 히스토리
history = pm.get_price_history(market_id="0x...", interval="1h")
```

### 추가 유용 라이브러리

| 패키지 | 용도 |
|--------|------|
| `web3` | Polygon 온체인 상호작용 |
| `ccxt` | 크로스 플랫폼 거래소 통합 |
| `pandas` | 가격/볼륨 데이터 분석 |
| `websockets` | 실시간 오더북 수신 |
| `schedule` / `apscheduler` | 자동 스캔 스케줄링 |

---

## 주문 실행

### 주문 타입

| 타입 | 설명 | 수수료 |
|------|------|--------|
| **Limit** | 지정가 주문, 오더북에 등록 | Maker: 0% |
| **Market** | 즉시 체결, 최적 가격 매칭 | Taker: 0~2% |
| **FOK** (Fill or Kill) | 전량 즉시 체결 또는 취소 | Taker |
| **GTC** (Good Till Cancel) | 취소까지 유효 | Maker |

### 주문 실행 예제

```python
from py_clob_client.clob_types import OrderArgs, OrderType

# Limit 주문 (Maker)
limit_order = client.create_and_post_order(OrderArgs(
    token_id="YES-token-id",
    price=0.48,           # 48¢에 매수
    size=1000,            # 1000 contracts
    side="BUY",
    order_type=OrderType.GTC,
))

# Market 주문 (Taker)
market_order = client.create_and_post_order(OrderArgs(
    token_id="YES-token-id",
    price=0.55,           # 최대 55¢까지 수용
    size=500,
    side="BUY",
    order_type=OrderType.FOK,
))

# 주문 취소
client.cancel(order_id=limit_order.id)

# 전체 주문 취소
client.cancel_all()
```

### 슬리피지 관리

```python
def calculate_slippage(book, side, size):
    """오더북 기반 예상 슬리피지 계산"""
    orders = book.asks if side == "BUY" else book.bids
    filled = 0
    total_cost = 0

    for level in orders:
        fill_amount = min(size - filled, float(level.size))
        total_cost += fill_amount * float(level.price)
        filled += fill_amount
        if filled >= size:
            break

    avg_price = total_cost / filled if filled > 0 else 0
    best_price = float(orders[0].price) if orders else 0
    slippage = abs(avg_price - best_price) / best_price * 100

    return {
        "avg_price": avg_price,
        "best_price": best_price,
        "slippage_pct": slippage,
        "filled": filled,
    }
```

---

## Resolution & Settlement

### 정산 프로세스

```
마켓 종료
    │
    ▼
Proposer가 결과 제출 + UMA 보증금 예치
    │
    ▼
2시간 이의 기간 ─── 이의 없음 → 결과 확정 → 정산
    │
    이의 있음
    │
    ▼
UMA 토큰 홀더 투표 (48시간)
    │
    ▼
투표 결과 → 최종 정산
    │
    ├── YES 승: YES holders → $1.00/contract
    │              NO holders → $0.00/contract
    └── NO 승:  YES holders → $0.00/contract
                   NO holders → $1.00/contract
```

### 정산 확인 API

```python
# 마켓 상태 확인
market = client.get_market(condition_id="0x...")
if market.resolved:
    print(f"결과: {market.resolution}")
    print(f"정산일: {market.resolved_at}")

# 미정산 포지션 확인
positions = client.get_positions()
for pos in positions:
    if not pos.resolved:
        print(f"미정산: {pos.market} - {pos.outcome} x {pos.size}")
```

### 자동 정산 수령

정산 시 USDC가 자동으로 Polymarket 잔액에 입금:
- YES 승리 시: YES 보유량 × $1.00
- NO 승리 시: NO 보유량 × $1.00
- 패배 측: $0.00 (전액 손실)

---

## 코드 예제

### 1. 마켓 스캐너 — 고확률 채권형 기회 탐색

```python
import requests

def scan_high_prob_markets(min_price=0.90, min_volume=100000):
    """90%+ 확률 마켓 중 볼륨 충분한 기회 탐색"""
    resp = requests.get("https://gamma-api.polymarket.com/markets", params={
        "active": True,
        "closed": False,
        "limit": 100,
    })
    markets = resp.json()

    opportunities = []
    for m in markets:
        prices = m.get("outcomePrices", [])
        volume = float(m.get("volume", 0))

        if not prices or volume < min_volume:
            continue

        yes_price = float(prices[0])
        no_price = float(prices[1])

        # 고확률 YES 기회
        if yes_price >= min_price:
            roi = (1.0 - yes_price) / yes_price * 100
            opportunities.append({
                "question": m["question"],
                "side": "YES",
                "price": yes_price,
                "roi_pct": roi,
                "volume": volume,
                "end_date": m.get("endDate"),
            })

        # 고확률 NO 기회
        if no_price >= min_price:
            roi = (1.0 - no_price) / no_price * 100
            opportunities.append({
                "question": m["question"],
                "side": "NO",
                "price": no_price,
                "roi_pct": roi,
                "volume": volume,
                "end_date": m.get("endDate"),
            })

    return sorted(opportunities, key=lambda x: x["roi_pct"], reverse=True)
```

### 2. 크로스 플랫폼 차익거래 모니터

```python
import requests
from datetime import datetime

def check_arbitrage(polymarket_id, kalshi_ticker, threshold_pct=3.0):
    """Polymarket vs Kalshi 가격 비교"""
    # Polymarket 가격
    pm_resp = requests.get(
        f"https://gamma-api.polymarket.com/markets/{polymarket_id}"
    )
    pm_data = pm_resp.json()
    pm_yes = float(pm_data["outcomePrices"][0])

    # Kalshi 가격 (공개 API)
    kl_resp = requests.get(
        f"https://api.elections.kalshi.com/trade-api/v2/markets/{kalshi_ticker}"
    )
    kl_data = kl_resp.json()["market"]
    kl_yes = kl_data["last_price"] / 100  # Kalshi uses cents

    spread = abs(pm_yes - kl_yes)
    arb_pct = spread * 100

    if arb_pct >= threshold_pct:
        # 차익거래 기회!
        if pm_yes < kl_yes:
            action = f"BUY YES on Polymarket ({pm_yes:.2f}) + BUY NO on Kalshi ({1-kl_yes:.2f})"
        else:
            action = f"BUY NO on Polymarket ({1-pm_yes:.2f}) + BUY YES on Kalshi ({kl_yes:.2f})"

        return {
            "arbitrage": True,
            "spread_pct": arb_pct,
            "pm_yes": pm_yes,
            "kl_yes": kl_yes,
            "action": action,
            "guaranteed_profit_pct": arb_pct - 2.0,  # 수수료 차감
            "timestamp": datetime.now().isoformat(),
        }

    return {"arbitrage": False, "spread_pct": arb_pct}
```

### 3. 실시간 오더북 모니터

```python
import asyncio
import websockets
import json

class OrderBookMonitor:
    def __init__(self, market_id):
        self.market_id = market_id
        self.bids = {}
        self.asks = {}

    async def connect(self):
        uri = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps({
                "type": "subscribe",
                "market": self.market_id,
                "channel": "book",
            }))

            async for msg in ws:
                data = json.loads(msg)
                self.process_update(data)

    def process_update(self, data):
        if data.get("type") == "book_update":
            side = self.bids if data["side"] == "buy" else self.asks
            price = data["price"]
            size = float(data["size"])

            if size == 0:
                side.pop(price, None)
            else:
                side[price] = size

            self.print_book()

    def print_book(self):
        sorted_asks = sorted(self.asks.items(), key=lambda x: float(x[0]))[:5]
        sorted_bids = sorted(self.bids.items(), key=lambda x: float(x[0]), reverse=True)[:5]

        print("\n--- Order Book ---")
        for price, size in reversed(sorted_asks):
            print(f"  ASK {price}: {size:,.0f}")
        print("  ---")
        for price, size in sorted_bids:
            print(f"  BID {price}: {size:,.0f}")

        if sorted_bids and sorted_asks:
            spread = float(sorted_asks[0][0]) - float(sorted_bids[0][0])
            print(f"  Spread: {spread:.4f} ({spread*100:.2f}%)")

# 실행
# asyncio.run(OrderBookMonitor("0x...").connect())
```

### 4. Kelly Criterion 포지션 사이저

```python
def kelly_size(estimated_prob, market_price, bankroll, fraction=0.5):
    """
    Kelly Criterion 기반 최적 베팅 크기 계산

    Args:
        estimated_prob: 내가 추정하는 실제 확률 (0~1)
        market_price: 현재 시장 가격 (0~1)
        bankroll: 총 가용 자본 ($)
        fraction: Kelly 분율 (0.5 = Half Kelly, 권장)

    Returns:
        dict: 베팅 방향, 크기, 기대값
    """
    if estimated_prob > market_price:
        # YES 매수 유리
        b = (1 - market_price) / market_price  # 순이익 배율
        p = estimated_prob
        q = 1 - p
        kelly_f = (b * p - q) / b
    elif estimated_prob < market_price:
        # NO 매수 유리
        b = market_price / (1 - market_price)
        p = 1 - estimated_prob
        q = 1 - p
        kelly_f = (b * p - q) / b
    else:
        return {"side": "NONE", "size": 0, "edge": 0, "ev": 0}

    if kelly_f <= 0:
        return {"side": "NONE", "size": 0, "edge": 0, "ev": 0}

    adjusted_f = kelly_f * fraction
    bet_size = bankroll * adjusted_f
    side = "YES" if estimated_prob > market_price else "NO"
    edge = abs(estimated_prob - market_price)

    # 기대값 계산
    if side == "YES":
        ev = bet_size * ((1 - market_price) * estimated_prob - market_price * (1 - estimated_prob)) / market_price
    else:
        ev = bet_size * (market_price * (1 - estimated_prob) - (1 - market_price) * estimated_prob) / (1 - market_price)

    return {
        "side": side,
        "size": round(bet_size, 2),
        "kelly_fraction": round(kelly_f, 4),
        "adjusted_fraction": round(adjusted_f, 4),
        "edge": round(edge, 4),
        "ev": round(ev, 2),
        "contracts": int(bet_size / (market_price if side == "YES" else 1 - market_price)),
    }

# 사용 예시
# result = kelly_size(
#     estimated_prob=0.75,  # 내 추정: 75%
#     market_price=0.60,    # 시장: 60%
#     bankroll=1000,        # 자본: $1,000
#     fraction=0.5,         # Half Kelly
# )
# print(result)
# → {'side': 'YES', 'size': 187.50, 'edge': 0.15, 'ev': 46.88, ...}
```

---

## Quick Reference

### 자주 사용하는 API 호출

| 목적 | API | 엔드포인트 |
|------|-----|-----------|
| 마켓 목록 | Gamma | `GET /markets` |
| 마켓 상세 | Gamma | `GET /markets/{id}` |
| 현재 가격 | CLOB | `GET /midpoint?token_id=X` |
| 오더북 | CLOB | `GET /book?token_id=X` |
| 주문 실행 | CLOB | `POST /order` (인증) |
| 주문 취소 | CLOB | `DELETE /cancel` (인증) |
| 내 포지션 | CLOB | `GET /positions` (인증) |
| 가격 히스토리 | Data | `GET /prices?market=X` |
| 실시간 데이터 | WebSocket | `wss://ws-subscriptions-clob.polymarket.com/ws/market` |
