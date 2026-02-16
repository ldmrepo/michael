---
name: binance
description: "Binance 거래소 API 기본 정보. 마이클이 필요시 도구를 직접 생성하여 사용. 키워드: 바이낸스, binance, 포트폴리오, 잔고, 선물, 거래, spot, futures, balance"
allowed-tools: Bash(python3:*), Bash(curl:*), Read, Write
---

# Binance API Reference

## Authentication

환경변수: `BINANCE_API_KEY`, `BINANCE_API_SECRET` (`.env` 파일)

HMAC-SHA256 서명:
```python
import hmac, hashlib, time, requests

API_KEY = os.environ['BINANCE_API_KEY']
API_SECRET = os.environ['BINANCE_API_SECRET']
BASE = 'https://api.binance.com'

def signed_request(method, path, params=None):
    params = params or {}
    params['timestamp'] = int(time.time() * 1000)
    query = '&'.join(f'{k}={v}' for k, v in params.items())
    sig = hmac.new(API_SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()
    query += f'&signature={sig}'
    headers = {'X-MBX-APIKEY': API_KEY}
    url = f'{BASE}{path}?{query}'
    return requests.request(method, url, headers=headers).json()
```

## Core Endpoints

| Purpose | Method | Endpoint |
|---------|--------|----------|
| Spot 잔고 | GET | /api/v3/account |
| Futures 잔고 | GET | /fapi/v2/account |
| Futures 포지션 | GET | /fapi/v2/positionRisk |
| 현재가 | GET | /api/v3/ticker/price |
| Spot 주문 | POST | /api/v3/order |
| Futures 주문 | POST | /fapi/v1/order |
| 주문 취소 | DELETE | /api/v3/order |
| 거래 내역 | GET | /api/v3/myTrades |

## value_usd 계산법

```python
# Spot
for asset in account['balances']:
    free = float(asset['free'])
    locked = float(asset['locked'])
    total = free + locked
    if asset['asset'] in ('USDT', 'USDC', 'BUSD'):
        value_usd = total
    else:
        price = get_price(f"{asset['asset']}USDT")
        value_usd = total * price

# Futures — IMPORTANT: unrealizedProfit만 사용
for pos in positions:
    notional = abs(float(pos['notional']))  # 레버리지 포함 명목가
    equity = notional / float(pos['leverage'])  # 실제 투자 원금
    unrealized_pnl = float(pos['unrealizedProfit'])
    value_usd = equity + unrealized_pnl  # 이것이 실제 자산 가치
```

## 계정 정보

- Spot + Futures 통합 계정
- Futures: Cross/Isolated 마진
- 수수료: Maker 0.1%, Taker 0.1% (BNB 할인 시 0.075%)
- Rate limit: 1200 requests/min (weight 기반)

## 주의사항

- Futures notional은 레버리지 포함 → equity = notional / leverage
- timestamp 오차 1000ms 이내 필요 (서버 시간 동기화)
- IP whitelist 권장 (API key 보안)
