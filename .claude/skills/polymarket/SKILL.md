---
name: polymarket
description: "Polymarket 예측시장 API 기본 정보. 마이클이 필요시 도구를 직접 생성하여 사용. 키워드: 폴리마켓, polymarket, 예측시장, PM, 베팅, prediction market"
allowed-tools: Bash(python3:*), Bash(curl:*), Read, Write
---

# Polymarket API Reference

## Wallet Architecture

| Component | Address | Purpose |
|-----------|---------|---------|
| EOA (서명자) | `0xcd0935708e63634AbC0aff4f1a5FC5FC763d035d` | 트랜잭션 서명 |
| Proxy Wallet | `0x5C4A020D663B60cA608B48e00D174881c94b41f4` | 거래 실행 계정 |
| USDC.e (bridged) | `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174` | 결제 토큰 |

**CRITICAL**: Native USDC(`0x3c499c...`)는 사용 불가! 반드시 USDC.e(bridged) 사용.

## APIs

### CLOB API (거래)
- Base: `https://clob.polymarket.com`
- `/order` — 주문 생성
- `/cancel` — 주문 취소
- `/data/order/{id}` — 주문 조회
- `/data/orders` — 주문 목록

### Data API (마켓 정보)
- Base: `https://data-api.polymarket.com`
- 인증 불필요

### Gamma API (마켓 메타데이터)
- Base: `https://gamma-api.polymarket.com`
- `/markets?slug=xxx` — 마켓 조회 (slug 필수! id나 condition_id는 불안정)
- `/events` — 이벤트 목록

## py-clob-client 사용법

```python
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType

client = ClobClient(
    host="https://clob.polymarket.com",
    chain_id=137,
    key=os.environ['POLYMARKET_PRIVATE_KEY'],
    signature_type=1,  # POLY_PROXY (proxy wallet 사용 시 필수!)
    funder=os.environ['POLYMARKET_PROXY_WALLET'],
)

# 잔고 조회
balance = client.get_balance_allowance()

# 오더북 조회
book = client.get_order_book(token_id)

# 가격 조회
price = client.get_price(token_id, "BUY")  # returns {'price': '0.94'}
price_val = float(price['price'])

# 주문 생성
order = client.create_order(OrderArgs(
    token_id=token_id,
    price=0.95,
    size=10,
    side="BUY",
))
result = client.post_order(order, OrderType.GTC)
```

## 핵심 교훈 (실전)

1. `signature_type=1` (POLY_PROXY) + `funder=proxy_wallet` 필수
2. `get_price()` returns `{'price': '0.94'}` dict, not float
3. Gamma API: `?slug=` 파라미터만 신뢰 가능 (`?id=`, `?condition_id=` 불안정)
4. Best ask + $0.01로 주문해야 즉시 체결 (정확히 ask 가격이면 LIVE 유지)
5. 수수료 0% (2026 현재)
6. Paraswap: $400+ 스왑 시 revert → $50 청크 분할
7. Proxy Wallet은 Factory `proxy(calls)` 메서드로 배치 실행

## 환경변수

```
POLYMARKET_PRIVATE_KEY=0x...  # EOA private key
POLYMARKET_PROXY_WALLET=0x5C4A020D663B60cA608B48e00D174881c94b41f4
```
