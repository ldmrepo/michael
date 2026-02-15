# Polymarket Trade Executor (폴리마켓 거래 실행가) — Foundational Knowledge

## 역할 정의

폴리마켓 거래 실행가는 **예측 마켓에서 포지션 진입과 청산을 최적 조건으로 수행**하는 전문 에이전트다. Polymarket의 CLOB(Central Limit Order Book)을 해석하고, thin book 환경에서 슬리피지를 최소화하며, Polygon 네트워크 가스 비용까지 고려한 총 실행 비용 최적화가 핵심 임무다.

일반 거래소와 달리 예측 마켓은 **유동성이 극도로 얇고, 스프레드가 넓으며, 결과 확정 시점이 존재**한다는 특수성이 있다. 이 특수성을 깊이 이해하고 활용하는 것이 이 에이전트의 차별점이다.

---

## 핵심 개념

### 1. CLOB (Central Limit Order Book) 구조

Polymarket은 전통적인 AMM(Automated Market Maker)이 아닌 **CLOB 방식**을 사용한다. 중앙화 오더북에서 매수/매도 주문이 매칭된다.

**오더북 데이터 구조**:
```json
{
  "market": "condition_id",
  "asset_id": "token_id_for_YES_or_NO",
  "bids": [{"price": "0.55", "size": "100"}, ...],
  "asks": [{"price": "0.57", "size": "50"}, ...],
  "min_tick_size": "0.01",
  "neg_risk": true
}
```

**핵심 필드 해석**:
- `bids`: 매수 대기 주문 (높은 가격순 정렬)
- `asks`: 매도 대기 주문 (낮은 가격순 정렬)
- `min_tick_size`: 최소 가격 단위. 대부분 $0.01
- `neg_risk`: Negative Risk 구조 여부 (다중 결과 마켓)

**스프레드 분석**:
```
스프레드 = best ask - best bid
스프레드(%) = (best ask - best bid) / mid price × 100
mid price = (best ask + best bid) / 2
```

- 유동성 좋은 마켓: 스프레드 1-2센트 ($0.01-$0.02)
- 평균 마켓: 스프레드 3-5센트
- 유동성 얇은 마켓: 스프레드 10센트+ (진입 주의)

### 2. Negative Risk (Neg Risk) 구조

**Binary Market (일반)**:
- YES + NO = $1.00 항상 성립
- YES 가격이 $0.60이면 NO는 $0.40
- Neg Risk = false

**Multi-Outcome Market (Neg Risk)**:
- 여러 결과 중 하나만 실현 (예: "어느 나라가 금메달 최다?")
- NegRiskAdapter 스마트 컨트랙트가 CTF(Conditional Token Framework)를 감싸서 관리
- 각 결과의 YES 가격 합 <= $1.00 (보통 약간 초과: 마켓 마진)
- **중요**: Neg risk 마켓의 오더북 정렬이 일반과 다를 수 있음. `get_price()` 사용이 안전

**CTF 토큰 동작**:
```
$1 USDC.e → split → 1 YES token + 1 NO token (binary)
1 YES + 1 NO → merge → $1 USDC.e (아무 때나 가능)
마켓 종료 시: 승리 토큰 = $1, 패배 토큰 = $0
```

**Neg Risk 마켓에서의 차익**:
- 모든 결과의 NO를 합산 매수하면 확정 이익 가능 (합 < $1 × (N-1)일 때)
- 실전에서는 유동성과 체결 비용 때문에 이론적 차익 < 실행 비용인 경우가 많음

### 3. 주문 유형 (Order Types)

**GTC (Good Till Cancelled)** — 기본 주문
- 체결되거나 수동 취소할 때까지 유효
- **사용**: 대부분의 일반 거래. 원하는 가격에 대기
- **정밀도**: 비교적 유연한 소수점 처리

**FOK (Fill or Kill)** — 즉시 전량 체결 또는 취소
- 전량 즉시 체결 불가능하면 전체 주문 취소
- **사용**: 현재 오더북에서 즉시 체결하고 싶을 때 (시장가 대용)
- **정밀도 제약 (CRITICAL)**:
  - Sell order: maker amount 소수점 2자리, taker amount 4자리
  - size × price 결과가 소수점 2자리 이내여야 함
  - 예: 100 shares × $0.55 = $55.00 (OK), 100 shares × $0.551 = $55.10 (OK), 33 shares × $0.57 = $18.81 (OK)

**GTD (Good Till Date)** — 기한부 주문
- 지정 시점까지 유효
- **사용**: 마켓 종료일 전에 자동 취소되게 설정

**FAK (Fill and Kill)** — 가능한 만큼 즉시 체결, 잔량 취소
- FOK과 유사하나 부분 체결 허용
- **사용**: "가능한 만큼 즉시 사고, 나머지는 포기"

### 4. Polymarket API 아키텍처

**계층 구조**:
```
CLOB API (주문 제출/관리)
  ├─ REST API (주문, 오더북, 포지션 조회)
  ├─ WebSocket (실시간 오더북 업데이트)
  └─ Gamma API (마켓 메타데이터, 가격 이력)
```

**인증 (CRITICAL)**:
- API Key + Secret으로 L1 인증 (읽기 전용)
- L2 인증 (주문 제출): API Key + Secret + 주문 서명
- **Proxy Wallet 사용 시**: `signature_type = POLY_PROXY (1)`, `funder = proxy_wallet_address`
- EOA 직접 사용 시: `signature_type = EOA (0)`

**Gamma API 주의사항**:
- `?id=` 파라미터: 숫자 ID만 지원, conditionId (0x... hex) 전달 시 422 에러
- `?condition_id=` 파라미터: 필터링 안 됨, 무관한 마켓 20개 리턴
- `?slug=` 파라미터: **유일하게 신뢰할 수 있는 조회 방법**
- 필드명: camelCase 사용 (`endDateIso`, `conditionId`, `outcomePrices`)

### 5. USDC.e 유동성 관리

**핵심 규칙: Polymarket은 USDC.e(bridged)만 사용**

- Contract: `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174` (USDC.e, bridged)
- Native USDC (`0x3c499c...`)는 **인식 불가**

**잔고 관리 흐름**:
```
외부 입금 (Binance 등)
  → Native USDC로 Polygon 도착
  → Paraswap DEX에서 USDC.e로 스왑 (1:1)
  → Proxy Wallet로 전송
  → Approval 설정 (USDC.e approve × 3, CTF setApprovalForAll × 3)
  → 거래 가능
```

**Paraswap 스왑 주의사항**:
- 대량 스왑 ($100+) revert 가능 → **$50 청크로 분할**
- Approve 대상: TokenTransferProxy (`0x216b4b4b...`), Router (`0xDEF1...`)가 아님!
- QuickSwapV3 경유 시 1:1 비율 (수수료 무시 가능)

### 6. Gas 비용 최적화 (Polygon)

**Polygon 가스 비용 구조**:
- 일반 거래: 0.001~0.01 POL ($0.001~$0.01)
- 복잡한 컨트랙트 호출: 0.01~0.1 POL
- 배치 트랜잭션 (factory.proxy): 0.05~0.2 POL

**최적화 전략**:
1. **배치 처리**: factory.proxy()로 여러 approval을 한 번에 실행 (가스 1회)
2. **가스 가격 모니터링**: Polygon은 보통 30-50 gwei. 100+ gwei일 때 비긴급 트랜잭션 지연
3. **EIP-1559 가스 설정**: maxFeePerGas와 maxPriorityFeePerGas에 3배 여유 (Polygon 특성)
4. **RPC 폴백**: polygon-rpc.com → 1rpc.io/matic → publicnode.com (rate limit 대비)

---

## 베스트 프랙티스

### Pre-Execution Checklist

1. **오더북 깊이 확인**: CLOB API로 bids/asks 조회
   - Best bid/ask 사이 스프레드 확인 (>5센트면 유동성 경고)
   - 주문 크기 대비 상위 3단계 호가 잔량 비율 확인

2. **Proxy Wallet USDC.e 잔고 확인**: 주문 금액 + 가스비 여유 (최소 0.5 POL)

3. **마켓 상태 확인**:
   - 마켓이 아직 활성인지 (종료/정산 시작 여부)
   - endDate까지 남은 시간 (24시간 이내면 유동성 급감 예상)

4. **Neg Risk 여부 확인**: 오더북 응답의 `neg_risk` 플래그. Neg risk 마켓은 오더북 해석 방법이 다름

### 대량 주문 분할 (Thin Book 전략)

Polymarket의 유동성은 Binance 대비 극도로 얇다. $500 주문도 대량으로 간주해야 한다.

**분할 기준**:

| 주문 크기 (USD) | 분할 수 | 간격 | 방식 |
|---|---|---|---|
| < $100 | 1 (분할 불필요) | - | GTC Limit |
| $100 - $500 | 2-3 | 30초-2분 | 가격 단계별 GTC |
| $500 - $2,000 | 5-10 | 1-5분 | 수동 분할 + 호가 모니터링 |
| $2,000+ | 10+ | 5-30분 | 장시간 분할 + 스프레드 추적 |

**가격 단계별 분할 예시** ($500 YES 매수, best ask $0.65):
```
주문 1: 200 shares @ $0.65 (best ask)
주문 2: 150 shares @ $0.66 (1센트 위)
주문 3: 150 shares @ $0.64 (bid에 대기)
```

### 최적 진입 시점

1. **스프레드가 좁을 때**: bid-ask 1-2센트 → 즉시 진입 유리
2. **뉴스/이벤트 직후**: 유동성이 일시적으로 증가, 스프레드 축소
3. **정산일 임박 시 주의**: 24시간 전부터 유동성 급감, 스프레드 확대
4. **심야(KST 03:00-09:00) 회피**: 마켓 메이커 비활성, 호가 간격 확대

### Execution Flow

```
명령 수신 → 마켓 상태 확인 → 오더북 분석 → 스프레드/유동성 판단
  → 주문 유형 결정 (GTC/FOK/FAK) → 분할 여부 판단
  → 주문 서명 → API 제출 → 체결 모니터링 → 결과 보고
```

---

## 주의사항 / 안티패턴

### 절대 하지 말 것

1. **FOK으로 대량 주문**: thin book에서 FOK $500은 전량 취소될 확률 높음. GTC 또는 FAK 사용
2. **best ask 정확 가격으로 즉시 체결 기대**: 정확히 ask 가격이면 LIVE 상태로 대기됨. **best ask + $0.01**로 주문해야 즉시 MATCHED
3. **Native USDC로 거래 시도**: Polymarket은 USDC.e(bridged)만 인식. Native USDC 전송 시 자금 손실 위험
4. **signature_type EOA(0) + Proxy Wallet**: Proxy 지갑 사용 시 반드시 POLY_PROXY(1) + funder 설정
5. **Gamma API `?id=conditionId`**: 422 에러. `?slug=` 사용 필수
6. **정산 시작된 마켓에 주문**: 체결 불가능하며 가스만 낭비

### 흔한 실수

- **`get_price()` 반환값 오해**: dict `{'price': '0.94'}` 반환. `float(result['price'])`로 파싱 필요
- **OrderArgs dict 전달**: `create_order()`에 dict가 아닌 OrderArgs 객체 전달 필수
- **Neg risk 마켓 가격 해석 오류**: 일반 마켓과 bid/ask 정렬이 다를 수 있음
- **Paraswap 대량 스왑 실패**: $50 이상 단위로 청크 분할 필요
- **RPC rate limit**: polygon-rpc.com 연속 호출 시 429. 15초 대기 후 재시도 또는 폴백 RPC 사용
- **endDateIso vs endDate 혼동**: timezone-aware 비교 시 `endDate` 사용 (Z suffix 포함)

---

## 판단 기준

### 주문 유형 결정 플로우

```
즉시 체결 필요?
  → YES: 전량 체결 필수?
    → YES: FOK (정밀도 제약 확인!)
    → NO: FAK (가능한 만큼 체결)
  → NO: 만기일 지정 필요?
    → YES: GTD
    → NO: GTC (기본)
```

### 스프레드 기반 의사결정

| 스프레드 | 판단 | 행동 |
|---|---|---|
| 1-2센트 | 매우 좋음 | 즉시 진입 가능 (GTC at best ask) |
| 3-5센트 | 정상 | Mid price 근처 GTC 대기 |
| 6-10센트 | 주의 | 분할 진입, 인내심 필요 |
| 10센트+ | 위험 | 진입 재고. 유동성 회복 대기 권장 |

### 유동성 판단 기준

| 지표 | 좋음 | 보통 | 나쁨 |
|---|---|---|---|
| Best bid/ask 잔량 | > $500 | $100-500 | < $100 |
| 상위 5호가 합산 | > $2,000 | $500-2,000 | < $500 |
| 24h 거래량 | > $50,000 | $10,000-50,000 | < $10,000 |
| 스프레드 | < 3센트 | 3-8센트 | > 8센트 |

### 가스 비용 대비 수익성 판단

```
최소 수익 = 주문금액 × 기대 수익률
가스 비용 = 예상 가스(POL) × POL 가격(USD)

순수익 = 최소 수익 - 가스 비용
→ 순수익 < 0이면 거래 거부

예시: $50 주문, 기대 수익 5% ($2.50)
  가스 비용: 0.05 POL × $0.50 = $0.025
  순수익: $2.475 → 실행 가치 있음

예시: $5 주문, 기대 수익 3% ($0.15)
  가스 비용: 0.05 POL × $0.50 = $0.025
  순수익: $0.125 → 실행 가능하나 마진 얇음
```

### 컨트랙트 주소 레퍼런스

| 컨트랙트 | 주소 | 용도 |
|---|---|---|
| USDC.e (Bridged) | `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174` | 거래 토큰 |
| CTF (Conditional Tokens) | `0x4D97DCd97eC945f40cF65F87097ACe5EA0476045` | 조건부 토큰 |
| CTF Exchange | Polymarket docs 참조 | 일반 마켓 거래 |
| Neg Risk CTF Exchange | Polymarket docs 참조 | Neg risk 마켓 거래 |
| Neg Risk Adapter | Polymarket docs 참조 | 다중 결과 마켓 |
| Proxy Factory | `0xaB45c5A4B0c941a2F231C04C3f49182e1A254052` | Proxy 지갑 생성/호출 |
| Paraswap TokenTransferProxy | `0x216b4b4ba9F3e719726886d34a177484278Bfcae` | DEX 스왑 approve |

### 포지션 모니터링 기준

| 상황 | 행동 |
|---|---|
| 가격 10센트+ 불리하게 이동 | 손절 검토 (리밸런서에 보고) |
| 정산일 24시간 이내 | 유동성 모니터링 강화, 청산 준비 |
| 가격 $0.95+ (YES 보유) | 이익 실현 검토 (잔여 5% 수익 vs 리스크) |
| 가격 $0.05- (NO 보유) | 이익 실현 검토 |
| 마켓 resolved | 즉시 정산 실행 (redeem) |
