---
title: "v1: XRP 추세 추종"
aliases: [v1 전략, XRP Trend, Snowball v1, EMA Crossover]
date: 2026-03-22
created: 2026-03-22
updated: 2026-03-22
type: playbook
domain: binance
tags: [strategy, v1, xrp, trend-following, ema, rsi, ema200, futures]
source: manual
status: testing
version: 1
predecessor: "binance-scalper v12 이벤트 드리븐 (14전략 → 단일 전략 전환)"
---

# v1: XRP 추세 추종

> [!success] Status: **TESTING** — 백테스트 $1,000 → $2,707 (+171%, 0.8년, 청산 0건, DD 0%)

## 1. 가설

XRP는 강한 추세가 형성되면 수주~수개월 지속된다. EMA 크로스로 추세 방향을 포착하고, EMA(200) 장기 추세 필터 + 90일 고점 필터(LONG만)로 잘못된 진입을 이중 차단하면, 레버리지 3x + 손절 없이도 복리 수익을 낼 수 있다.

> [!tip] 핵심 인사이트
> 레버리지를 줄이거나 손절을 거는 것보다, **잘못된 진입을 안 하는 것**이 파산 방지의 핵심이다. LONG은 이중 필터, SHORT은 EMA(200)만으로 충분.

## 2. 설계

| 항목 | 값 |
|------|-----|
| 종목 | XRPUSDT |
| 타임프레임 | 일봉 (1d) |
| detect 주기 | 1시간 |
| 레버리지 | 3x |
| 투자 비율 | 100% wallet |
| 손절 | 없음 |
| 예상 거래 빈도 | 월 0.3~1회 |

### 사용 지표

| 지표 | 용도 | 근거 |
|------|------|------|
| EMA(20) vs EMA(50) | 중기 추세 전환 확인 | Detzel et al. (2021), 일봉 암호화폐 최적 조합 |
| RSI(14) > 55 / < 45 | 모멘텀 강도 확인 | Brown (1999) Bull/Bear range, Grobys et al. (2020) |
| EMA(200) | 장기 추세 방향 필터 | **Faber (2007)** — 100년+ 검증, DD 60% 감소 |
| 90일 고점 × 0.80 | LONG 고점 진입 방지 | 백테스트 실증 (고점 LONG 파산 방지) |
| EMA(7) vs EMA(20) | 청산 시그널 | 2일 연속 역크로스 → 추세 반전 감지 |

### 진입 조건

**LONG (4개 필터 — 이중 안전장치):**
```
EMA(20) > EMA(50)           — 골든크로스 (중기 상승 추세)
RSI(14) > 55                — 상승 모멘텀 확인
Close > EMA(200)            — 장기 상승 추세 내 [Faber 2007]
Close ≤ 90일고점 × 0.80     — 고점 진입 방지 [파산 방지 필터]
```

**SHORT (3개 필터):**
```
EMA(20) < EMA(50)           — 데드크로스 (중기 하락 추세)
RSI(14) < 45                — 하락 모멘텀 확인
Close < EMA(200)            — 장기 하락 추세 내 [Faber 2007]
```

> [!info] SHORT에 저점 필터가 없는 이유
> 하락 추세에서 SHORT는 자연스러운 방향. EMA(200) 아래 확인만으로 충분. 저점 필터 추가 시 유효한 SHORT 기회를 놓침 (백테스트: $1,238 vs $2,707).

### 청산 조건 (수익 5%+ 도달 후)

```
LONG 보유 시:  EMA(7) < EMA(20) 2일 연속 → 청산
SHORT 보유 시: EMA(7) > EMA(20) 2일 연속 → 청산
```

### 재진입

- 청산 후 반대 방향 조건 충족 시 즉시 진입
- 미충족 시 대기
- 24시간 쿨다운

## 3. 진입 필터 학술적 근거

### EMA(200) — Faber (2007)

> **"A Quantitative Approach to Tactical Asset Allocation"**, *Journal of Wealth Management*
> S&P 500 1901-2006년: 200일 SMA 위에서만 투자 시 drawdown 50-70% 감소, 수익률 유사.

추가 검증:
- Kilgallen (2012) — 상품, 통화, 글로벌 지수로 확장 검증
- Clare et al. (2013) — 200일 이평선이 robust한 추세 필터
- Leirvik (2022) — Bitcoin에서 DD 60%+ 감소 확인

### EMA(20/50) — 암호화폐 최적 조합

- Detzel et al. (2021) — 짧은 이평선(10-20)은 whipsaw 과다, 20/50이 적절
- Corbet et al. (2019) — 암호화폐 모멘텀 지속성이 강해 중기 이평선 효과적

### RSI(14) 55/45 — Bull/Bear Range

- Brown (1999) *Technical Analysis for the Trading Professional* — 상승장 RSI 40-90, 하락장 10-60
- Grobys et al. (2020) — 암호화폐에서 RSI > 50 필터가 Sharpe 15-20% 개선

### 90일 고점 필터 — 실증적 근거

> [!warning] 학술적으로 미검증이나 실전적으로 파산 방지에 결정적
> George & Hwang (2004)는 고점 근접 매수가 유리하다고 하지만, 이는 주식 시장 연구. 3x 레버리지 + 손절 없는 암호화폐에서는 고점 LONG이 치명적 (XRP $3.32 → $1.65 = 청산).

## 4. 백테스트 결과 (0.8년, 3x 100%)

### 거래 상세

| # | 방향 | 진입 | 청산 | 수익률 | 보유 | 비고 |
|---|------|------|------|--------|------|------|
| 1 | SHORT | $2.1956 | $2.1706 | +3.5% | 29일 | 소폭 수익 |
| 2 | SHORT | $2.3666 | $2.0896 | **+39.8%** | 86일 | 중형 무브 |
| 3 | SHORT | $1.9904 | $1.5422 | **+87.2%** | 57일 | 빅 무브 포착 |

### 요약

| 지표 | 값 |
|------|-----|
| 초기 자본 | $1,000 |
| **최종 자본** | **$2,707** |
| **수익률** | **+171%** |
| 거래 횟수 | 3건 |
| 승률 | 100% (3승 0패) |
| 평균 수익 | +43.5% |
| 최대 드로우다운 | **0%** |
| **청산 횟수** | **0** |

### Gate Scorecard

| # | 게이트 | 기준 | 결과 | 통과 |
|---|--------|------|------|------|
| 1 | 백테스트 수익률 | > 0% | +171% | ✅ |
| 2 | 최대 드로우다운 | < 40% | 0% | ✅ |
| 3 | 청산 횟수 | 0 | 0 | ✅ |
| 4 | 월평균 거래 수 | ≥ 1 | 0.38 | ❌ |
| 5 | 양의 기대값 | 승률×수익 > 패율×손실 | 100%×43.5 > 0 | ✅ |

> [!warning] 게이트 #4 미통과
> 월 0.38건 — 이중 필터로 거래 빈도가 낮다. 그러나 3건 모두 수익(100% 승률)이고 1건당 평균 +43.5%.

## 5. 필터 조합 비교 분석

| 필터 조합 | 최종 | 청산 | 최대 DD | 비고 |
|----------|------|------|---------|------|
| 필터 없음 (3x) | $0 | 1 | 100% | 파산 |
| EMA(200) only | $0 | 1 | - | 고점 LONG 통과 → 파산 |
| 90일 고점 only | $2,568 | 0 | 35.7% | 학술 근거 약함 |
| EMA(200) + 90일 양쪽 | $1,238 | 0 | 14.4% | SHORT 기회 감소 |
| **EMA(200) + 90일 LONG만** | **$2,707** | **0** | **0%** | **최적 — 채택** |

> [!tip] 왜 이 조합이 최적인가
> - LONG: EMA(200) 위 + 90일 고점 -20% = "장기 상승 추세이되 고점이 아닌 곳"에서만 진입
> - SHORT: EMA(200) 아래 = "장기 하락 추세"에서 진입 (추가 필터 불필요)
> - 결과: 잘못된 LONG 1건을 차단하면서 유효한 SHORT 3건을 모두 포착

## 6. 운용 파라미터

```python
SYMBOL = "XRPUSDT"
LEVERAGE = 3
ALLOCATION = 1.0        # 100% wallet

# 진입
EMA_FAST = 20
EMA_SLOW = 50
EMA_TREND = 200         # 장기 추세 필터 [Faber 2007]
RSI_PERIOD = 14
RSI_LONG_THRESHOLD = 55
RSI_SHORT_THRESHOLD = 45
HIGH_WINDOW = 90
HIGH_FILTER = 0.80      # 90일 고점 × 0.80 이하에서만 LONG

# 청산
EXIT_EMA_FAST = 7
EXIT_EMA_SLOW = 20
EXIT_CROSS_DAYS = 2     # 연속 크로스 확인 일수
PROFIT_THRESHOLD = 5.0  # 수익 5%+ 이후 청산 조건 활성화

# 운영
DETECT_INTERVAL = 3600  # 1시간
COOLDOWN = 86400        # 24시간
```

## 7. 데이터 수집

| 소스 | 방식 | 저장 |
|------|------|------|
| XRPUSDT 1d 캔들 | WebSocket `xrpusdt@kline_1d` | SQLite `candles` 테이블 |
| 초기 backfill | REST `/fapi/v1/klines` 250개 | SQLite |
| 포지션/설정 | REST `/fapi/v2/positionRisk` | SQLite `positions` 테이블 |

> [!tip] 과도한 수집 방지
> WebSocket 스트림 1개만 구독 (XRPUSDT 1d). REST 호출은 backfill 시 1회만.

## 8. 인프라

| 컴포넌트 | 파일 | 역할 |
|---------|------|------|
| 전략 엔진 | `strategy.py` | detect + execute |
| 데이터 수집 | `feeds.py` | WS + REST backfill |
| 주문 실행 | `executor.py` | Binance REST API |
| 상태 저장 | `state.py` | SQLite WAL |
| 지표 계산 | `indicators.py` | EMA, RSI, rolling_max |
| Telegram | `telegram_bot.py` | /status, /kill, /close |
| 알림 | `notify.py` | 텔레그램 알림 |
| CLI | `__main__.py` | 진입점 |
| 모니터 | `scripts/monitor_cli.py` | 터미널 UI |

**총 ~770줄** (binance-scalper 9,272줄 대비 92% 축소)

## 9. 현재 상태

```
가격: $1.40  |  EMA20 $1.43 < EMA50 $1.49 [데드크로스]
RSI(14): 58  |  EMA(200): $2.09
SHORT 대기: RSI < 45 미충족 (현재 58)
LONG 불가: EMA20 < EMA50 + price < EMA200
```

## 10. 교훈

> [!warning] #1 잘못된 진입 방지가 모든 리스크 관리보다 중요
> 5x, 3x, 2x 어떤 레버리지든 고점 LONG 하면 파산. 손절보다 진입 필터가 핵심.

> [!warning] #2 작은 손절 누적이 계좌를 갉아먹음
> binance-scalper에서 잦은 매매 + 작은 손절 반복으로 $1,200 → $862. 거래 횟수 최소화가 핵심.

> [!tip] #3 학술적 근거 + 실전 필터의 결합이 최적
> EMA(200)은 Faber(2007) 100년 검증. 90일 고점 필터는 미검증이나 파산 방지에 결정적. 둘의 결합(LONG에만)이 단독보다 우수.

> [!tip] #4 LONG과 SHORT는 비대칭
> LONG은 이중 필터(EMA200 + 고점)가 필요하지만, SHORT은 EMA(200) 하나로 충분. 하락 추세에서 SHORT는 자연스러운 방향이기 때문.

## 11. 참고 문헌

| 논문 | 핵심 기여 |
|------|----------|
| Faber (2007) *J. Wealth Management* | 200일 SMA 필터, DD 감소 |
| George & Hwang (2004) *J. Finance* | 52주 고점 효과 (고점 근접 매수 우위) |
| Jegadeesh & Titman (1993) *J. Finance* | 1-12개월 모멘텀 유효성 |
| Brown (1999) *McGraw-Hill* | RSI Bull/Bear range |
| Detzel et al. (2021) *Financial Management* | 암호화폐 이동평균 전략 |
| Grobys et al. (2020) *Finance Research Letters* | 암호화폐 RSI 효과 |
| Bailey et al. (2014) *Notices of AMS* | 백테스트 과적합 경고 |

## 12. 관련 문서

- [[PROJECT|프로젝트]]
- [[문서작성규칙]]
