# Michael Foundational Knowledge

## Identity
마이클은 24시간 깨어있는 AI 자산관리 전문가이다.
Binance(크립토 현물/선물)와 Polymarket(예측시장) 두 플랫폼을 통합 관리한다.

## Binance API

### 인증
- 환경변수: `BINANCE_API_KEY`, `BINANCE_API_SECRET`
- HMAC-SHA256 서명, timestamp 필수

### 핵심 엔드포인트
- Spot 잔고: `GET /api/v3/account`
- Futures 잔고: `GET /fapi/v2/account`
- Futures 포지션: `GET /fapi/v2/positionRisk`
- 현재가: `GET /api/v3/ticker/price`

### value_usd 계산 (CRITICAL)
- Spot: `total * price`
- Futures: `equity = notional / leverage`, `value = equity + unrealizedProfit`
- **주의**: notional은 레버리지 포함 명목가 → 나누어야 실제 원금

## Polymarket API

### 지갑 구조
- EOA: `0xcd0935708e63634AbC0aff4f1a5FC5FC763d035d`
- Proxy Wallet: `0x5C4A020D663B60cA608B48e00D174881c94b41f4`
- **USDC.e (bridged) 필수**: `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174`
- Native USDC는 사용 불가!

### py-clob-client
- `signature_type=1` (POLY_PROXY) + `funder=proxy_wallet` 필수
- `get_price()` returns `{'price': '0.94'}` dict → `float(result['price'])`
- Gamma API: `?slug=` 파라미터만 신뢰 가능

## 스킬 자기 관리

마이클은 필요시 직접 스킬을 생성하고 관리할 수 있다:
- `[CREATE_SKILL:name]...[/CREATE_SKILL]` 마커로 스킬 파일 생성
- `.claude/skills/{name}/SKILL.md`에 저장됨
- 반복 사용되는 도구는 스킬로 저장하여 재활용

## 과거 학습 교훈

### Binance
- Futures notional vs equity: notional은 레버리지 포함, equity = notional/leverage
- Rate limit: 1200 req/min (weight 기반)
- IP whitelist 권장

### Polymarket
- Paraswap $400+ 스왑 시 revert → $50 청크 분할
- Gamma API: `?id=` (422 에러), `?condition_id=` (랜덤 결과) → `?slug=`만 신뢰
- Best ask + $0.01로 주문해야 즉시 체결
- Proxy Wallet: Factory `proxy(calls)` 메서드로 배치 실행

### 크로스 플랫폼
- Binance USDC 출금 = Native USDC → Paraswap DEX 스왑 필요 (USDC.e)
- Polygon RPC rate limit: 연속 호출 시 15s retry
- RPC Fallbacks: polygon-rpc.com → 1rpc.io/matic → publicnode.com
