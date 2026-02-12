---
name: prediction-market
description: |
  Prediction market (예측 시장) 투자 전문 가이드. Polymarket, Kalshi 등 플랫폼 활용,
  확률 기반 베팅 전략, 차익거래, 유동성 공급, 정보 우위 전략.
  Use when: prediction market 분석, Polymarket 거래, 확률 베팅, 이벤트 헤지
  Keywords: "예측 시장", "prediction market", "polymarket", "kalshi", "베팅", "확률"
---

# Prediction Market 투자 가이드

## Overview

Prediction market(예측 시장)은 미래 이벤트의 결과에 대해 거래할 수 있는 시장이다. 참가자들은 특정 이벤트가 발생할 확률을 반영하는 **YES/NO 계약**을 매매하며, 계약 가격(0¢~100¢)이 시장이 평가하는 확률을 나타낸다.

**핵심 원리:**
- YES 계약 50¢ = 시장이 50% 확률로 평가
- 이벤트 발생 시 YES → $1.00 정산, NO → $0.00 정산
- YES + NO = 항상 $1.00 (상보적 관계)
- 가격이 실제 확률에서 벗어나면 → **수익 기회 발생**

**투자 수단으로서의 가치:**
- 전통 자산과 **낮은 상관관계** (이벤트 기반)
- 정보 우위가 **직접적으로 수익**으로 전환
- 단기 이벤트 (1일~6개월) 중심으로 **자본 회전율** 높음
- 포트폴리오 **헤지** 수단으로 활용 가능

---

## 주요 플랫폼 비교

| 플랫폼 | 유형 | 결제 | 수수료 | 2025 볼륨 | 접근성 | 강점 |
|--------|------|------|--------|-----------|--------|------|
| **Polymarket** | 탈중앙화 (Polygon) | USDC | 0% 거래, 2% 출금 | $9B+ | 글로벌 (미국 제외) | 최대 유동성, CLOB, 다양한 마켓 |
| **Kalshi** | 규제 거래소 (CFTC) | USD | 7% 순이익 | $3.2B+ | 미국 전용 | 규제 안정성, 선거/경제 마켓 |
| **Metaculus** | 예측 플랫폼 | 없음 (점수) | 없음 | N/A | 글로벌 | 과학/기술 예측, 커뮤니티 정확도 |
| **PredictIt** | CFTC 실험 | USD | 10% 이익, 5% 출금 | 축소 중 | 미국 | 정치 이벤트 (규모 제한 $850) |
| **Augur/Overtime** | 탈중앙화 (ETH) | ETH/USDC | ~2% | 소규모 | 글로벌 | 완전 탈중앙화, 검열 저항성 |

**권장 시작 플랫폼:** Polymarket (최대 유동성 + 낮은 수수료 + 한국 접근 가능)

---

## 핵심 개념

### CLOB (Central Limit Order Book)

Polymarket의 핵심 거래 엔진. 전통 거래소와 동일한 주문장 매칭 방식:

```
매수(Bid)          매도(Ask)
─────────          ─────────
48¢ × 5000        52¢ × 3000
47¢ × 8000        53¢ × 2000
46¢ × 12000       54¢ × 5000
```

- **Maker 주문**: 오더북에 유동성 추가 (수수료 0% 또는 리베이트)
- **Taker 주문**: 기존 주문과 매칭 (수수료 0~2%)
- **스프레드**: Bid-Ask 차이가 수익 기회 (2024: 평균 4.5% → 2025: 1.2%)

### MINT / MERGE 메커니즘

```
MINT: $1 USDC → 1 YES token + 1 NO token (새로운 쌍 생성)
MERGE: 1 YES token + 1 NO token → $1 USDC (쌍 소각)
```

이 메커니즘이 **가격 안정화**의 핵심:
- YES 55¢ + NO 55¢ = $1.10 → MINT 후 양쪽 매도로 차익 실현
- YES 45¢ + NO 45¢ = $0.90 → 양쪽 매수 후 MERGE로 차익 실현

### USDC 정산 & Polygon

- 모든 거래는 **Polygon 체인**의 USDC로 정산
- 입금: 크립토 지갑 → Polygon Bridge → Polymarket
- 출금: Polymarket → Polygon USDC → CEX/월렛 (2% 수수료)
- **가스비**: Polygon 특성상 거의 무시 가능 (<$0.01)

### UMA 분쟁 해결 (Optimistic Oracle)

1. **Proposer**가 결과 제출 + 보증금 예치
2. **2시간 이의 기간** — 누구든 반대 제안 가능
3. 이의 없으면 → 결과 확정, 정산
4. 이의 있으면 → **UMA 토큰 홀더 투표** (48시간)
5. 투표 결과로 최종 정산 + 패배측 보증금 슬래싱

### Longshot Bias / Favorites Bias

**통계적으로 검증된 시장 미스프라이싱 패턴:**

| 마켓 가격 | 실제 승률 | 미스프라이싱 | 방향 |
|-----------|-----------|-------------|------|
| 5¢ (5%) | 4.18% | **-16.4%** | 과대평가 (Longshot Bias) |
| 15¢ (15%) | 13.2% | **-12.0%** | 과대평가 |
| 50¢ (50%) | 50.1% | **+0.2%** | 정확 |
| 85¢ (85%) | 87.8% | **+3.3%** | 과소평가 (Favorites Bias) |
| 95¢ (95%) | 97.2% | **+2.3%** | 과소평가 |

**실전 의미:**
- 극단적 가격대(5¢ 이하, 95¢ 이상)에서 체계적 미스프라이싱 존재
- **고확률 채권형 전략**의 이론적 근거: 90¢+ 계약 매수 → 정산 시 5~10% 수익
- 저확률 이벤트는 **체계적으로 과대평가** → NO 매수 유리

---

## 6대 수익 전략

### 1. Information Arbitrage (정보 차익)

**원리:** 시장이 아직 반영하지 못한 정보를 먼저 확보하여 포지션 진입

**실행:**
- 1차 데이터 소스 모니터링 (정부 통계, 공식 발표, 규제 문서)
- 뉴스 발표 전 해당 이벤트 마켓에 포지션 설정
- 시장 반응 후 청산 또는 정산까지 보유

**엣지 확보 방법:**
- 특정 도메인 전문지식 (의학, 법률, 기술)
- 대안 데이터 (위성, 소셜미디어, 내부 설문)
- 분석 모델 (베이지안 업데이트, 앙상블 예측)

**예시:** FDA 승인 마켓에서 Phase 3 임상 데이터 공개 직전 포지션 → 400ms 내 반영

**기대 수익:** 이벤트당 15~40% (정보 품질에 따라)

### 2. Cross-Platform Arbitrage (플랫폼 간 차익)

**원리:** 동일 이벤트에 대해 플랫폼 간 가격 차이 활용

**실행:**
```
Polymarket: "BTC $150K by 2026 Q2" YES = 35¢
Kalshi:     "BTC $150K by 2026 Q2" YES = 42¢

→ Polymarket YES 매수 35¢ + Kalshi NO 매수 58¢ = 93¢
→ 어떤 결과든 $1.00 수령 → 7% 무위험 수익
```

**주의사항:**
- 정산 조건의 미묘한 차이 확인 필수 (날짜, 기준가, 소스)
- 자본 잠김 기간 고려 (연환산 수익률 계산)
- 출금 수수료/가스비 차감 후 순이익 확인

**역사적 사례:** 2024 미국 선거 — Polymarket vs Kalshi 간 $40M+ 차익 기회 발생

**기대 수익:** 연환산 8~25% (자본 잠김 기간 포함)

### 3. High-Probability Bond (고확률 채권형)

**원리:** 90%+ 확률 이벤트의 YES 계약 매수 → 정산 시 안정적 수익

**실행:**
- 95¢ 매수 → 정산 시 $1.00 수령 = **5.26% 수익**
- 90¢ 매수 → 정산 시 $1.00 수령 = **11.1% 수익**
- 정산까지 30일이면 → **연환산 64~135%**

**적합 마켓:**
- "Fed가 다음 회의에서 금리 동결" (컨센서스 확실)
- "빅테크 실적 흑자" (기본 시나리오)
- "UN 총회 개최 확정" (이미 확정된 이벤트)

**리스크:** 5~10% 확률로 전액 손실 가능 → **포트폴리오 분산 필수**

**기대 수익:** 연환산 20~60% (분산 포트폴리오 기준)

### 4. Liquidity Provision (유동성 공급)

**원리:** 오더북 양면에 주문을 배치하여 스프레드 수익 획득

**실행:**
```
YES Bid 48¢ (maker) ←→ YES Ask 52¢ (maker)
스프레드 4¢ per round trip
양면 보너스: 보상 3x
```

**Polymarket 유동성 프로그램:**
- 보상 풀: 마켓별 일일 배정
- Tight spread 보너스: 스프레드 좁을수록 더 많은 보상
- 양면 보너스: Bid+Ask 동시 제공 시 3배 보상

**리스크:** 방향성 리스크 (가격 급변 시 한쪽 포지션 잠김)

**기대 수익:** 연환산 15~40% (마켓 볼륨에 따라)

### 5. Domain Specialization (도메인 특화)

**원리:** 특정 분야 전문 지식으로 일반 시장 참가자 대비 우위 확보

**성공 사례:**
- **Evan Semet**: 날씨 예측 도메인 특화 → 시카고 기온/강수 마켓에서 지속 수익
- **프랑스 트레이더**: 이웃 효과(neighbor effect) 여론조사 분석 → 2024 미국 선거 $85M 수익

**추천 특화 도메인:**
- 크립토 규제 (SEC, CFTC 결정)
- 한국/아시아 정치 이벤트
- 기술 출시/채택 (AI, 반도체)
- 스포츠 통계 (MLB, NBA 고급 지표)
- 기후/날씨 (NOAA 데이터 기반)

**기대 수익:** 이벤트당 20~50% (전문성 깊이에 따라)

### 6. Algorithmic Trading (알고리즘 속도)

**원리:** API를 통한 자동화로 수동 트레이더 대비 속도 우위 확보

**실행:**
- Polymarket CLOB API로 실시간 오더북 모니터링
- 뉴스 피드 파싱 → 이벤트 감지 → 자동 주문 (목표: <1초)
- 차익거래 봇: 멀티 플랫폼 가격 비교 → 자동 실행

**인프라:**
- Python: `py-clob-client` + WebSocket
- 저지연 서버 (US East, Polygon RPC 근접)
- 뉴스 API: NewsAPI, GDELT, Twitter/X firehose

**기대 수익:** 연환산 30~100%+ (전략 품질에 따라)

---

## 리스크 관리

### 포지션 사이징 원칙

| 확신도 | 단일 포지션 비중 | Kelly 기준 |
|--------|------------------|-----------|
| 높음 (80%+ edge) | 최대 10% | Full Kelly |
| 중간 (60% edge) | 5% | Half Kelly |
| 낮음 (탐색) | 2% | Quarter Kelly |

**Kelly Criterion 공식:**
```
f* = (bp - q) / b
b = 순이익 배율, p = 승률, q = 1 - p

예: 60¢ YES 매수, 실제 확률 75%
b = (100-60)/60 = 0.667
f* = (0.667 × 0.75 - 0.25) / 0.667 = 37.5%
Half Kelly → 18.75% 배분
```

### 포트폴리오 헤지 원칙

1. **이벤트 상관관계 분석**: 동일 이벤트에 의존하는 포지션 합산 관리
2. **시간 분산**: 정산일 집중 방지 (주간 최대 5개 마켓)
3. **카테고리 분산**: 정치/경제/스포츠/크립토 균형 배분
4. **최대 손실 한도**: 전체 자본의 20% 이상 단일 카테고리 금지

### 자본 배분 원칙

```
총 Prediction Market 자본 배분 (전체 투자 포트폴리오의 5~15%)
├── 고확률 채권형 (40%): 안정 수익, 90%+ 마켓
├── 정보 차익 (25%): 도메인 전문성 활용
├── 유동성 공급 (20%): 스프레드 수익
└── 탐색/학습 (15%): 새 도메인, 소액 다수 베팅
```

---

## 크립토 투자 통합

Prediction market은 크립토 포지션의 **이벤트 헤지** 수단으로 활용 가능:

### 헤지 시나리오

| 기존 포지션 | 리스크 이벤트 | 헤지 방법 |
|------------|--------------|----------|
| BTC 롱 | SEC ETF 거부 가능성 | "SEC Approves BTC ETF" NO 매수 |
| ETH 롱 | 대규모 규제 발표 | "US Crypto Ban by 2026" YES 매수 |
| SOL 롱 | 네트워크 장애 리스크 | "Solana 99.9% Uptime Q1" NO 매수 |
| DeFi 포지션 | 해킹 리스크 | "Major DeFi Hack >$100M" YES 매수 |

### 시너지 효과

1. **정보 재활용**: 크립토 리서치 → prediction market 엣지
2. **이미 보유한 USDC**: 추가 자본 투입 없이 Polymarket 진입
3. **Polygon 생태계**: 이미 사용 중이면 진입 장벽 없음
4. **24/7 거래**: 크립토와 동일한 시간대 운영

---

## 시장 규모 & 트렌드 (2026)

### 성장 지표

| 지표 | 2023 | 2024 | 2025 | 2026 (추정) |
|------|------|------|------|------------|
| Polymarket 총 볼륨 | $300M | $9B | $20B+ | $44B+ |
| Kalshi 총 볼륨 | $100M | $3.2B | $8B+ | $15B+ |
| 일일 활성 트레이더 | 5K | 50K | 200K+ | 500K+ |
| 기관 참여도 | 낮음 | 시작 | 활발 | 주류 |

### 2026 주요 트렌드

1. **기관 자본 유입**: Jump Trading, Citadel 등 마켓 메이킹 참여
2. **스프레드 축소**: 전문 트레이더 유입으로 차익 기회 감소 (4.5%→1.2%→0.5%)
3. **도메인 전문화 필수**: 일반 전략으로는 수익 난이도 상승
4. **API/알고리즘 경쟁**: 수동 거래 → 자동화 필수 전환
5. **규제 명확화**: CFTC 가이드라인 확립, 더 많은 플랫폼 합법화
6. **크립토 네이티브 통합**: DeFi 프로토콜과 prediction market 합성
7. **InfoFi 내러티브**: 정보 = 금융 자산, prediction market이 핵심 인프라

### 경쟁 환경 변화

- **초기 (2023)**: 개인 트레이더 독주, 높은 미스프라이싱, 쉬운 수익
- **성장기 (2024-2025)**: 선거 이벤트 폭발, 기관 진입 시작
- **성숙기 (2026+)**: 전문화 필수, 알고리즘 경쟁, 자본 요건 상승

---

## 실전 체크리스트

### Phase 1: 계좌 개설 & 준비 (1~2일)

- [ ] Polymarket 계정 생성 (MetaMask 또는 이메일)
- [ ] Polygon 네트워크 USDC 준비 (최소 $100, 권장 $500+)
- [ ] Polymarket에 USDC 입금
- [ ] UI 탐색: 마켓 브라우징, 오더북 이해
- [ ] 소액 ($5~10) 첫 거래 실행 (학습용)

### Phase 2: 기본 전략 실행 (1~2주)

- [ ] 고확률 채권형 마켓 3개 이상 식별 및 진입
- [ ] 관심 도메인 2~3개 선정 (크립토, 기술, 정치 등)
- [ ] 일일 마켓 스캔 루틴 설정 (30분)
- [ ] 포지션 추적 스프레드시트 생성
- [ ] 승/패 기록 및 예측 정확도 자가 평가

### Phase 3: 고급 전략 진입 (1개월+)

- [ ] Polymarket API 키 발급 및 Python 환경 설정
- [ ] 크로스 플랫폼 가격 모니터링 도구 구축
- [ ] 정보 소스 파이프라인 구축 (뉴스 API, 데이터 피드)
- [ ] 자동 알림 시스템 구축 (가격 변동, 새 마켓)
- [ ] Kelly Criterion 기반 자동 사이징 도구 구축

### Phase 4: 스케일링 (3개월+)

- [ ] 포트폴리오 $1,000+ 규모 달성
- [ ] 월간 수익률 추적 및 벤치마크 비교
- [ ] 유동성 공급 프로그램 참여
- [ ] 알고리즘 트레이딩 봇 배포
- [ ] 주간/월간 전략 리뷰 및 조정

---

## Agentic Use Cases (Michael 연동)

Michael AI 시스템과 prediction market을 연동하여 자동화할 수 있는 10가지 시나리오:

1. **마켓 스캐너**: 새 마켓 등록 시 Telegram 알림 + 관련 도메인 자동 분류
2. **가격 알림**: 관심 마켓 가격이 임계값 돌파 시 즉시 알림
3. **차익거래 감지**: Polymarket vs Kalshi 가격 차이 실시간 모니터링 → 기회 알림
4. **뉴스 연동**: 관련 뉴스 발생 시 → 영향받는 마켓 식별 → 가격 변동 예측 알림
5. **포트폴리오 트래커**: 현재 포지션, 미실현 손익, 정산 일정 일일 요약
6. **Kelly 사이징 계산기**: 마켓 분석 결과 입력 → 최적 포지션 크기 자동 계산
7. **정산 알림**: 마켓 정산 24시간 전 알림 + 결과 예측 요약
8. **크립토 헤지 제안**: 크립토 포지션 분석 → 관련 prediction market 헤지 추천
9. **성과 분석**: 주간/월간 수익률, 예측 정확도, 도메인별 성과 자동 리포트
10. **전략 백테스트**: 과거 마켓 데이터로 전략 검증 및 최적화 제안

---

## Polymarket 입금/출금 실전 가이드

### 지갑 아키텍처 (중요!)

Polymarket은 **2개의 지갑**을 사용한다:

| 지갑 | 역할 | 설명 |
|------|------|------|
| **EOA (Externally Owned Account)** | 서명 지갑 | Magic.Link 또는 MetaMask로 생성. Private key 보유. 거래 서명에 사용 |
| **Proxy Wallet** | 거래 지갑 | Polymarket이 EOA 기반으로 생성한 스마트 컨트랙트. **실제 USDC 잔고가 여기에** |

```
[Binance/CEX] --USDC (Polygon)--> [EOA] --transfer--> [Proxy Wallet] = Polymarket 잔고
                                    ↑                       ↑
                                    Private Key 소유      Polymarket UI에 표시되는 잔고
```

**핵심 규칙:**
- Polymarket 거래 잔고 = **Proxy Wallet의 USDC 잔고**
- EOA에 USDC를 보내도 Polymarket에서 보이지 않음 → Proxy Wallet로 전송 필요
- CLOB API의 `get_balances()`는 Proxy Wallet 잔고를 반환

### Polygon 체인 요구사항

| 항목 | 값 |
|------|-----|
| **네트워크** | Polygon POS (Chain ID: 137) |
| **가스 토큰** | POL (구 MATIC) |
| **USDC.e (Collateral)** | `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174` (bridged, 6 decimals) — **Polymarket 거래에 사용** |
| **Native USDC** | `0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359` (Circle native) — **Polymarket에서 사용 불가** |
| **RPC** | `https://polygon-rpc.com` (fallback: `https://1rpc.io/matic`) |
| **가스비** | ERC20 transfer ~57K gas, approval batch ~154K gas ≈ 0.05~0.15 POL |
| **POA 체인 특성** | web3.py에서 `ExtraDataToPOAMiddleware` 필수 |

> **USDC vs USDC.e 주의!** Binance에서 Polygon USDC를 출금하면 **Native USDC**가 전송된다.
> 하지만 Polymarket CLOB은 **USDC.e (bridged)**만 인식한다.
> Native USDC를 보냈다면 DEX(Paraswap, QuickSwap 등)에서 1:1 스왑 필요.

### 컨트랙트 아키텍처

| 컨트랙트 | 주소 | 역할 |
|----------|------|------|
| **Proxy Factory** | `0xaB45c5A4B0c941a2F231C04C3f49182e1A254052` | EOA로 프록시 월렛 트랜잭션 실행 (`proxy()`) |
| **CTF Exchange** | `0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E` | 일반 마켓 거래소 |
| **Neg Risk CTF Exchange** | `0xC5d563A36AE78145C45a50134d48A1215220f80a` | Neg Risk 마켓 거래소 |
| **Neg Risk Adapter** | `0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296` | Neg Risk 어댑터 |
| **Conditional Tokens (CTF)** | `0x4D97DCd97eC945f40cF65F87097ACe5EA0476045` | ERC-1155 포지션 토큰 |

### 프록시 월렛 구조

- **EIP-1167 Minimal Proxy**: 45바이트 클론, implementation = `0x44e999d5c2f66ef0861317f9a4805ac2e90aeb4f`
- **실행 방법**: Proxy Factory의 `proxy(calls)` 메서드로 배치 실행
- **calls 구조**: `[(typeCode=1, to=address, value=0, data=calldata), ...]`
- **권한**: EOA가 Factory를 통해 호출해야 함 (직접 프록시 호출 X)

### 입금 방법

#### 방법 1: USDC.e 직접 입금 (권장)
1. Polymarket UI에서 Proxy Wallet 주소 확인 (Settings → Funding)
2. CEX에서 **USDC.e**를 Proxy Wallet에 직접 전송
3. 이미 USDC.e + approve가 설정되어 있다면 잔고에 자동 반영

#### 방법 2: Binance → 스왑 → 입금 (실전 검증됨)

**전체 플로우 (USDT → Polymarket):**
1. **Binance USDT → USDC 변환**: Binance는 보통 USDT를 보유. USDCUSDT 마켓에서 시장가 매도로 변환
2. **Binance USDC → EOA 출금**: Polygon 네트워크로 출금 — **Native USDC가 옴** (USDC.e 아님!)
3. **EOA에 POL(가스비) 필요** → Binance에서 POL 별도 출금 (수수료 0.13 POL)
4. **Native USDC → USDC.e 스왑** (Paraswap DEX, ~1:1 비율):
```python
# Paraswap 스왑 핵심 — approve는 반드시 TokenTransferProxy에!
# ✅ 맞음: approve(0x216b4b4ba9f3e719726886d34a177484278bfcae, amount)
# ❌ 틀림: approve(0xDEF171Fe48CF0115B1d80b88dc8eAB59176FEe57, amount)  # Router 아님!
```
5. **USDC.e → Proxy Wallet 전송**
6. **Proxy Factory approve** (최초 1회만):
```python
# USDC.e approve + CTF setApprovalForAll × 3 operators = 6 calls
factory.proxy([(1, USDC_E, 0, approve_calldata), ...])
```

> **Paraswap TokenTransferProxy 주의!** Paraswap API에서 받은 `priceRoute`의 TX를 실행하려면
> `approve()`를 Augustus Router(`0xDEF171Fe...`)가 아닌 **TokenTransferProxy**(`0x216b4b4b...`)에 해야 한다.
> Router는 TX의 `to` 필드일 뿐, 토큰을 실제로 pull하는 것은 TokenTransferProxy다.
> API 응답의 `priceRoute.tokenTransferProxy` 필드에서 주소를 확인할 수 있다.

### 출금 방법

#### 방법 1: Polymarket UI (간단)
1. Portfolio → Withdraw → USDC.e가 EOA로 이동
2. 출금 수수료: ~2%

#### 방법 2: 프로그래밍 (Proxy Factory 사용)
```python
# Proxy Wallet에서 직접 USDC.e를 EOA로 출금
factory.proxy([(1, USDC_E, 0, transfer_calldata)])
```

### Proxy Wallet 주소 확인법

- **Polymarket UI**: Settings → Funding → Deposit 주소
- **환경변수**: `.env`의 `POLYMARKET_PROXY_WALLET`
- **온체인 파생**: Proxy Factory + EOA → CREATE2로 결정적 주소 계산
- **py-clob-client**: `derive_api_key()` 과정에서 proxy 주소 파생

### Approval 설정 (Funds Activation)

입금 후 Polymarket에서 "Activate your funds" 단계가 필요하다. 이는 USDC.e와 CTF 토큰의 approve를 거래소 컨트랙트에 설정하는 것이다.

**UI 방법**: Portfolio → "Activate your funds" → Continue (Magic.Link 세션 필요)

**프로그래밍 방법** (Magic.Link 세션 만료 시):
```python
# Proxy Factory의 proxy() 메서드로 6개 approval 배치 실행
OPERATORS = [CTF_EXCHANGE, NEG_RISK_CTF_EXCHANGE, NEG_RISK_ADAPTER]
calls = []
for op in OPERATORS:
    calls.append((1, USDC_E, 0, encode_approve(op, MAX_UINT256)))
    calls.append((1, CTF, 0, encode_setApprovalForAll(op, True)))
factory.proxy(calls)  # EOA에서 서명, 가스비 ~154K gas
```

### 실전 교훈 (Common Pitfalls)

#### 입금/스왑 관련
| # | 교훈 | 상세 |
|---|------|------|
| 1 | **USDC.e 필수** | Polymarket은 USDC.e(`0x2791...`)만 인식. Binance 출금 = Native USDC → DEX 스왑 필요 |
| 2 | **Proxy Wallet에 입금** | EOA에 보내면 추가 전송 작업 필요. Proxy Wallet 주소로 직접 전송 |
| 3 | **Polygon POS 네트워크** | Ethereum이나 다른 체인으로 보내면 자금 손실 |
| 4 | **POL 가스비 필요** | EOA에 POL 없으면 transfer/approve/swap 모두 불가 |
| 5 | **Paraswap 대량 스왑 revert** | $100+ 단일 스왑 시 pool 유동성 부족으로 TX revert. **$50 청크로 분할** 필요 |
| 6 | **Paraswap approve 대상** | `TokenTransferProxy`(`0x216b4b...`)에 approve. Router(`0xDEF1...`)에 하면 revert |
| 7 | **Binance USDT→USDC 변환** | Binance 보유 USDT → USDCUSDT 시장가 주문 → USDC 확보 후 Polygon 출금 |

#### CLOB/거래 관련
| # | 교훈 | 상세 |
|---|------|------|
| 8 | **`get_price()` 반환값은 dict** | `{'price': '0.94'}` → `float(result['price'])` 파싱 필수 |
| 9 | **`get_balance_allowance()` params 필수** | `BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)` 전달. None이면 크래시 |
| 10 | **Approval 없이 거래 불가** | USDC.e approve + CTF setApprovalForAll × 3 operator 설정 필수 |
| 11 | **Magic.Link 세션 만료** | UI "Activate" 실패 시 → Proxy Factory `proxy()` 메서드로 직접 approve |
| 12 | **즉시 체결 전략** | Best ask + $0.01로 주문 → 즉시 MATCHED. 정확히 ask 가격이면 LIVE 유지됨 |

#### Gamma API 관련
| # | 교훈 | 상세 |
|---|------|------|
| 13 | **camelCase 필드명** | `endDateIso`, `conditionId`, `outcomePrices`, `liquidityNum`, `volume24hr` (snake_case 아님) |
| 14 | **`endDate` vs `endDateIso`** | `endDateIso` = date-only(`2026-12-31`), `endDate` = ISO+Z(`2026-12-31T00:00:00Z`). timezone 비교는 `endDate` 사용 |
| 15 | **`tokens` 배열 비어있음** | market list의 `tokens`는 empty. 가격은 `outcomePrices` (JSON `["0.055","0.945"]`) 사용 |
| 16 | **페이지네이션 100개 제한** | `limit=100` 최대. 전체 스캔 시 `offset` 파라미터로 페이지네이션 필요 |

#### 인프라/네트워크 관련
| # | 교훈 | 상세 |
|---|------|------|
| 17 | **RPC rate limit** | polygon-rpc.com 연속 호출 시 rate limit → fallback: `1rpc.io/matic` → `publicnode.com` |
| 18 | **EIP-1559 가스 설정** | `maxFeePerGas × 3`, `maxPriorityFeePerGas × 3`으로 빠른 포함 보장 |
| 19 | **web3.py POA 미들웨어** | `ExtraDataToPOAMiddleware` 필수 (Polygon은 POA 체인) |
| 20 | **Binance 화이트리스트** | USDC/Polygon과 POL/Polygon은 별도 등록 |

#### 데이터 동기화 관련
| # | 교훈 | 상세 |
|---|------|------|
| 21 | **DB ≠ 실제 보유** | 로컬 DB(`pm_positions`)는 주문 실행 시 기록된 스냅샷. 이후 매도/정산/만료로 실제와 불일치 가능 |
| 22 | **CLOB API가 진실의 소스** | `clob.get_positions()`가 반환하는 것이 현재 실제 보유 포지션. DB에 없는 포지션이 있거나, DB에는 있지만 실제로 매도/정산된 포지션 존재 가능 |
| 23 | **P&L 불일치 원인** | DB 기반 P&L 계산과 폴리마켓 UI P&L이 다르면 십중팔구 DB 미동기화. 매도된 포지션이 DB에 `open`으로 남아있거나, 정산된 마켓의 실현 손익이 반영 안 됨 |
| 24 | **모순 포지션 방지** | 같은 이벤트에 YES/NO 동시 베팅 금지. 리밸런싱 엔진에 모순 체크 로직 필수 (예: Fed 동결 YES + Fed 인하 YES = 모순) |
| 25 | **저확률 YES 주의** | 가격 $0.05~0.10 YES = 확률 5~10%. "싸니까 매수"가 아니라 "안 일어날 이벤트". 확률 10% 미만 YES에 큰 금액 투입 금지 |

---

## 거래 데이터 동기화 확인 가이드

### 왜 동기화가 필요한가?

로컬 DB(`pm_positions` 테이블)는 주문 실행 시점의 스냅샷일 뿐이다. 다음 상황에서 실제 폴리마켓 보유 포지션과 불일치가 발생한다:

1. **폴리마켓 UI에서 직접 매도** — DB에 반영 안 됨
2. **마켓 정산(resolved)** — DB status가 `open` 그대로 남음
3. **MERGE/REDEEM 실행** — YES+NO 쌍 소멸, DB 미반영
4. **부분 체결** — 주문의 일부만 체결되었는데 DB에는 전량 기록

### 동기화 절차 (수동)

```bash
# Step 1: 폴리마켓 API에서 실제 보유 포지션 조회
python -c "
from polymarket_client import create_client
client = create_client()
positions = client.get_positions()
import json
print(json.dumps(positions, indent=2))
"

# Step 2: DB의 열린 포지션 조회
python -c "
import db_utils
conn = db_utils.get_connection()
positions = db_utils.get_positions(conn, 'default', 'open')
for p in positions:
    print(f'{p[\"side\"]:>3} | size={p[\"size\"]:>6.1f} | entry={p[\"entry_price\"]:.4f} | {p[\"market_id\"][:20]}...')
conn.close()
"

# Step 3: 차이 확인 후 DB 업데이트
# - API에는 없는데 DB에 open인 포지션 → closed/settled로 변경
# - API에는 있는데 DB에 없는 포지션 → upsert
```

### 동기화 체크리스트

포트폴리오 체크(`check_portfolio.py`) 실행 전 반드시 확인:

1. *CLOB API 포지션 수 vs DB open 포지션 수* — 불일치 시 동기화 필요
2. *P&L 불일치* — 폴리마켓 UI의 Profit/Loss와 DB 계산 결과 비교
3. *정산된 마켓* — Gamma API에서 `closed: true`인 마켓의 DB 포지션 → `settled`로 업데이트
4. *거래 내역 대조* — `clob.get_trades()`로 매도 이력 확인, DB에 미반영된 매도 건 처리

### 자동 동기화 구현 가이드

`check_portfolio.py`에 `--sync` 플래그 추가 시 구현 순서:

```python
def sync_positions(client, conn, user_id="default"):
    """Sync DB positions with CLOB API actual holdings."""
    # 1. CLOB API에서 실제 포지션 가져오기
    api_positions = client.get_positions()
    api_token_ids = {p["asset"]: p for p in api_positions}  # token_id → position

    # 2. DB의 open 포지션 가져오기
    db_positions = db_utils.get_positions(conn, user_id, "open")

    # 3. DB에만 있고 API에 없는 것 → closed 처리
    for db_pos in db_positions:
        token_id = db_pos.get("token_id")
        if token_id and token_id not in api_token_ids:
            # 매도/정산된 포지션 → closed
            db_utils.close_position(conn, db_pos["id"], exit_price=0)
            print(f"  [SYNC] Closed: {db_pos['side']} {db_pos['market_id'][:30]}")

    # 4. API에만 있고 DB에 없는 것 → upsert
    for token_id, api_pos in api_token_ids.items():
        # market_id (condition_id) 매핑 후 upsert
        pass

    conn.commit()
```

### 주의사항

- CLOB `get_positions()` 반환 형식은 `[{"asset": "token_id", "size": "10.5", ...}]`
- `asset` 필드가 token_id (YES/NO 구분). market_id(condition_id)와 다름
- token_id → market_id 매핑은 `pm_markets` 테이블의 `yes_token_id`/`no_token_id` 참조
- 동기화 후 반드시 `check_portfolio.py`로 검증

---

## CLOB 거래 실행 가이드

### py-clob-client 인증 (Proxy Wallet 사용)

Polymarket은 Proxy Wallet을 통해 거래한다. `py-clob-client` 초기화 시 **반드시** `signature_type`과 `funder`를 설정해야 한다:

```python
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds
from py_order_utils.model.signatures import POLY_PROXY  # signature_type=1

creds = ApiCreds(
    api_key=POLYMARKET_API_KEY,
    api_secret=POLYMARKET_API_SECRET,
    api_passphrase=POLYMARKET_PASSPHRASE,
)

clob = ClobClient(
    host="https://clob.polymarket.com",
    key=POLYMARKET_PRIVATE_KEY,
    chain_id=137,
    creds=creds,
    signature_type=POLY_PROXY,       # CRITICAL: Proxy 지갑 사용 시 필수
    funder=POLYMARKET_PROXY_WALLET,  # CRITICAL: Proxy 지갑 주소
)
```

**Signature Types:**
| 값 | 상수 | 용도 |
|----|------|------|
| 0 | `EOA` | MetaMask 등 직접 지갑 (비표준) |
| 1 | `POLY_PROXY` | **Polymarket 표준** — Proxy Wallet 거래 |
| 2 | `POLY_GNOSIS_SAFE` | Gnosis Safe 멀티시그 |

> **주의**: `signature_type`과 `funder` 없이 주문하면 "not enough balance / allowance" 에러 발생.
> 온체인 잔고/allowance가 정상이어도 서버측에서 서명 타입 불일치로 거부함.

### L2 API 키 파생 (처음 1회)

L2 키가 없으면 L1 서명에서 파생:
```python
clob_l1 = ClobClient(
    host="https://clob.polymarket.com",
    key=POLYMARKET_PRIVATE_KEY,
    chain_id=137,
    signature_type=POLY_PROXY,
    funder=POLYMARKET_PROXY_WALLET,
)
creds = clob_l1.create_or_derive_api_creds()
# creds.api_key, creds.api_secret, creds.api_passphrase → .env에 저장
```

### 주문 실행 — OrderArgs 객체 사용

`create_order()`는 **dict가 아닌 OrderArgs 객체**를 요구한다:

```python
from py_clob_client.clob_types import OrderArgs, MarketOrderArgs
from py_clob_client.order_builder.constants import BUY, SELL

# Limit Order
order_args = OrderArgs(
    token_id="37951513621735...",  # YES 또는 NO token ID
    price=0.94,                     # 제한가 (0~1)
    size=10,                        # 계약 수
    side=BUY,                       # BUY 또는 SELL
)
signed_order = clob.create_order(order_args)
result = clob.post_order(signed_order)
# result: {"orderID": "...", "status": "MATCHED"}

# Market Order
market_args = MarketOrderArgs(
    token_id="37951513621735...",
    amount=10.0,    # BUY: USDC 금액, SELL: 계약 수
    side=BUY,
)
signed_order = clob.create_market_order(market_args)
result = clob.post_order(signed_order)
```

> **주의**: dict `{"token_id": ..., "price": ...}` 전달 시 `AttributeError: 'dict' object has no attribute 'token_id'` 에러 발생.

### 주문 상태

| status | 의미 |
|--------|------|
| `LIVE` | 오더북에 대기 중 (미체결) |
| `MATCHED` | 즉시 체결됨 |
| `DELAYED` | 지연 처리 중 |
| `CANCELED` | 취소됨 |

**Tip**: Limit order가 `LIVE`이면 현재 best ask보다 낮은 가격에 걸린 것. 즉시 체결을 원하면 best ask 이상의 가격으로 설정.

**즉시 체결 전략 (실전 검증):**
- Best ask 정확히 그 가격에 주문하면 `LIVE`로 남는 경우가 많음 (rounding, timing issue)
- **Best ask + $0.01로 주문하면 즉시 `MATCHED`** — 예: ask=$0.91이면 $0.92로 주문
- 1센트 추가 비용은 미미하지만 체결 확실성이 크게 향상됨
- 대량 주문 시에는 오더북 깊이를 확인하고 슬리피지 계산 후 진행

### 배치 주문 실행 패턴 (실전 검증)

여러 마켓에 연속 주문 시 검증된 패턴:

```python
import time
from py_clob_client.clob_types import OrderArgs, OrderType

orders = [
    {'name': 'ETH $2,800 NO', 'tid': '3663129...', 'size': 70},
    {'name': 'US Gold NO',     'tid': '5721884...', 'size': 60},
]

for o in orders:
    # 1) get_price() → dict 반환, float 파싱
    resp = clob.get_price(o['tid'], 'buy')
    ask = float(resp['price'])
    buy_price = round(min(ask + 0.01, 0.99), 2)  # 즉시 체결 보장

    # 2) OrderArgs 객체로 주문 생성 (dict X)
    order_args = OrderArgs(price=buy_price, size=o['size'],
                           side='BUY', token_id=o['tid'])
    signed = clob.create_order(order_args)
    result = clob.post_order(signed, OrderType.GTC)

    print(f"{o['name']}: {result.get('status')} @ ${buy_price}")
    time.sleep(1)  # rate limit 방지
```

> **잔고 확인**: `get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))` 사용. 파라미터 없이 호출하면 크래시.

### Neg Risk 마켓 특성

올림픽 금메달, 선거 승자 등 **다중 결과 마켓**은 Neg Risk 모드로 운영된다:

- 여러 outcome이 하나의 event에 속함 (예: "Norway", "Germany", "USA" 각각의 YES/NO)
- 오더북 정렬이 일반 마켓과 다를 수 있음
- **`get_price(token_id, "buy")`를 사용하는 것이 가장 안전** — raw order book 파싱보다 신뢰할 수 있음 (반환값은 dict, 실전 교훈 #8 참조)
- 거래소 주소: `NEG_RISK_CTF_EXCHANGE` (일반 마켓은 `CTF_EXCHANGE`)

### Gamma API 마켓 검색 팁

| 방법 | 설명 | 추천도 |
|------|------|--------|
| `search_markets(query)` | `_q` 파라미터로 텍스트 검색 | 낮음 — 오래된/비관련 마켓 다수 반환 |
| `get_markets(active=True, order="volume24hr")` | 볼륨 순 활성 마켓 | 중간 — 전체 마켓 리스트에서 필터 |
| `get_events(active=True)` | 이벤트(마켓 그룹) 조회 | **높음** — 다중 결과 마켓을 이벤트 단위로 탐색 |

**추천 플로우 (실전 검증):**
1. `get_markets(active=True, limit=100, offset=N)` → 페이지네이션으로 전체 마켓 수집
2. `outcomePrices` (JSON string) 파싱 → YES/NO 가격 확인 (`tokens` 배열은 비어있음!)
3. `endDate` (ISO+Z) 파싱 → 정산일 계산, `conditionId`로 마켓 식별
4. `clobTokenIds[0]`=YES, `clobTokenIds[1]`=NO → 거래할 토큰 ID 확보
5. `get_price(token_id, "buy")` → 현재 ask 확인 (dict 반환: `float(result['price'])`)
6. `create_limit_order(token_id, "BUY", ask+0.01, size)` → 즉시 체결

### 수수료 (2026년 현재)

| 항목 | 비율 |
|------|------|
| Maker 수수료 | **0%** |
| Taker 수수료 | **0%** |
| 출금 수수료 | ~2% |
| Polygon 가스비 | <$0.01 |

> `fee_rate_bps=0`으로 주문 시 수수료 없음. 향후 변경될 수 있으므로 API 응답의 `fee_rate_bps` 확인 권장.

### 첫 거래 체크리스트

1. `.env`에 `POLYMARKET_PRIVATE_KEY`, `POLYMARKET_API_KEY`, `POLYMARKET_API_SECRET`, `POLYMARKET_PASSPHRASE`, `POLYMARKET_PROXY_WALLET` 설정
2. Proxy Wallet에 USDC.e 잔고 + Approval 확인
3. `ClobClient` 초기화 시 `signature_type=POLY_PROXY`, `funder=proxy_wallet` 설정
4. `OrderArgs` 객체로 주문 생성 (dict X)
5. 소액 ($5~10) 테스트 후 본 거래 진행

### 포트폴리오 분산 프레임워크 (실전 검증)

고확률 채권형 전략 실행 시 다음 3가지 축으로 분산:

**1. 카테고리 분산** — 상관관계 낮은 이벤트 유형 혼합:
| 카테고리 | 목표 비중 | 예시 |
|----------|----------|------|
| 크립토/금융 | 30~40% | BTC 가격 범위, ETH ETF |
| 경제/통화 | 25~35% | Fed 금리 결정, 실업률 |
| 지정학 | 15~25% | 전쟁/평화, 정권 교체 |
| 스포츠/기타 | 5~15% | 올림픽, 선거 |

**2. 정산일 분산** — 자본 회전과 유동성 확보:
- 1주 이내: 20~30% (빠른 회전)
- 1~4주: 30~40% (핵심 수익)
- 1~6개월: 20~30% (높은 ROI but 자본 잠김)
- 기존 포지션과 겹치지 않는 마켓 우선 선택

**3. 포지션 크기 분산** — 단일 마켓 리스크 제한:
- 단일 포지션: 전체 자본의 10% 이하
- 같은 카테고리: 전체 자본의 40% 이하
- 현금(USDC.e) 유지: 전체의 10~20% (추가 기회 대응)

**마켓 선별 기준 (scan_markets.py --high-prob 필터):**
```
✅ YES 가격 90~97¢ (ROI 3~11%)
✅ 정산까지 5~120일
✅ 유동성 $50K+ (슬리피지 방지)
✅ 볼륨 $10K+/24h (활성 시장)
❌ 99¢+ (ROI 1% 미만 — 자본 효율성 부족)
❌ 정산 6개월+ (자본 잠김 과다)
❌ 기존 포지션과 동일 이벤트/카테고리 과다
```

---

## 고급 분석 & 리밸런싱 파이프라인

3개 스크립트가 순서대로 파이프라인을 구성:

```
portfolio_intelligence.py → cross_asset_rebalancer.py → execute_rebalance_pm.py
(신호 분석 + EV)           (통합 리밸런싱 플랜)          (CLOB 거래 실행)
```

### 1. portfolio_intelligence.py — 다중소스 확률 추정 엔진

투자 리서치 데이터(매크로, 센티먼트, 볼륨, 모멘텀, 유동성, 뉴스, 온체인)를 종합하여
각 PM 포지션의 Bayesian 확률과 Expected Value를 계산한다.

**사용법:**
```bash
# 전체 포트폴리오 분석
python scripts/portfolio_intelligence.py

# 특정 마켓만 분석
python scripts/portfolio_intelligence.py --market-id <condition_id>

# JSON 출력 + 시그널 상세
python scripts/portfolio_intelligence.py --json --verbose

# Kelly 파라미터 조정
python scripts/portfolio_intelligence.py --bankroll 500 --kelly-fraction 0.25
```

**시그널 가중치:**
| 시그널 | 가중치 | 소스 |
|--------|--------|------|
| momentum | 20% | 가격 변동률 1h/24h/7d |
| macro | 15% | FRED 금리/인플레이션 |
| sentiment | 15% | Fear & Greed Index |
| news | 15% | 뉴스 감성 분석 |
| onchain | 15% | DeFi TVL 추세 |
| volume | 10% | 24h 거래량 변화 |
| liquidity | 10% | 오더북 깊이 |

**출력:** `pm_intelligence` 테이블에 저장 (각 포지션별 true_prob, ev, kelly_size 등)

### 2. cross_asset_rebalancer.py — 크로스 애셋 리밸런서

PM 포지션 + Binance 보유 자산을 통합 포트폴리오로 분석하여 리밸런싱 플랜 생성.
기본적으로 **dry-run** (실행 없이 플랜만 출력).

**사용법:**
```bash
# PM + Binance 통합 리밸런싱 (기본: dry-run)
python scripts/cross_asset_rebalancer.py

# PM만 분석
python scripts/cross_asset_rebalancer.py --pm-only

# Binance만 분석
python scripts/cross_asset_rebalancer.py --binance-only

# 리스크 파라미터 조정
python scripts/cross_asset_rebalancer.py --max-crypto-pct 50 --max-single-pct 10 --max-leverage 2.0

# JSON 출력
python scripts/cross_asset_rebalancer.py --json
```

**리스크 분석 항목:**
- Herfindahl 집중도 지수 (HHI)
- 단일 포지션/카테고리 비중 제한
- 크립토 연관 PM 포지션 ↔ Binance 상관관계 분석
- 플랫폼 간 자본 이동 최적화 (PM ↔ Binance)

**출력:** `pm_cross_rebalances` 테이블에 각 포지션별 HOLD/ADD/REDUCE/EXIT 액션 저장

### 3. execute_rebalance_pm.py — 리밸런싱 실행기

`rebalance_engine.py`가 생성한 세션의 액션을 CLOB API로 실행.
우선순위: EXIT → REDUCE → ADD 순서.

**사용법:**
```bash
# 최근 세션 목록 확인
python scripts/execute_rebalance_pm.py --list-sessions

# 특정 세션 실행 (dry-run)
python scripts/execute_rebalance_pm.py --session-id <id> --dry-run

# 실제 실행 (확인 프롬프트 표시)
python scripts/execute_rebalance_pm.py --session-id <id>

# 강제 실행 (확인 생략)
python scripts/execute_rebalance_pm.py --session-id <id> --force

# EXIT 액션만 실행
python scripts/execute_rebalance_pm.py --session-id <id> --action EXIT
```

**안전장치:**
- 기본 dry-run (실행하려면 `--force` 필요)
- 가격 변동 5%+ 경고 (PRICE_DRIFT_WARN_PCT)
- 최대 3회 재시도 (MAX_RETRIES)
- 주문 간 1초 쿨다운 (rate limit 방지)
- 슬리피지 추적 및 실행 로그 감사 추적

**출력:** `pm_execution_log` 테이블에 체결 내역 (fill_price, slippage, status 등)

### 전체 파이프라인 실행 예시

```bash
# Step 1: 신호 분석 → EV 계산
python scripts/portfolio_intelligence.py --verbose

# Step 2: 통합 리밸런싱 플랜 생성
python scripts/cross_asset_rebalancer.py

# Step 3: 플랜 확인 후 실행
python scripts/execute_rebalance_pm.py --list-sessions
python scripts/execute_rebalance_pm.py --session-id <id> --dry-run
python scripts/execute_rebalance_pm.py --session-id <id> --force
```

---

## References

- **Polymarket API 기술 레퍼런스**: See [references/polymarket-api.md](references/polymarket-api.md) — API 아키텍처, 엔드포인트, 코드 예제
- **전략 심화 & Edge 분석**: See [references/strategies-and-edge.md](references/strategies-and-edge.md) — 미스프라이싱 패턴, 성공 사례, 데이터 소스

## Related Skills

- **크립토 투자 소스**: See [../crypto-investment-sources/SKILL.md](../crypto-investment-sources/SKILL.md) — 크립토 데이터 소스 및 분석 도구
- **바이낸스 분석**: See [../binance-analytics/SKILL.md](../binance-analytics/SKILL.md) — 거래소 분석 및 시장 데이터
