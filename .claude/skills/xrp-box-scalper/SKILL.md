---
name: xrp-box-scalper
description: >
  XRPUSDT 박스권 자동 스켈핑 전략 스킬. Binance Futures Hedge mode에서
  평균회귀형 범위장 스캘프를 설계, 검토, 백테스트, 운용할 때 사용한다.
  키워드: XRP, box range, 박스권, scalping, mean reversion, hedge mode,
  futures bot, funding, open interest, breakout filter
---

# XRP Box-Range Scalper

XRPUSDT가 추세장보다 박스장에 가까울 때 쓰는 자동 스캘핑 스킬이다. 핵심은 `박스 중앙에서 잦게 매매하지 않고`, `박스 가장자리에서만 평균회귀를 노리며`, `돌파일 때는 즉시 멈추는 것`이다.

이 스킬은 다음 상황에서 쓴다.
- 사용자가 XRP 박스권 자동매매 전략을 만들거나 수정하려고 할 때
- 현재 XRP가 범위장인지 평가하고 봇 가동 가능 여부를 판단할 때
- Binance Futures Hedge mode에서 LONG/SHORT 양방향 상태머신을 구현할 때
- 기존 `xrp_box_scalper.py` 또는 백테스트 스크립트를 조정할 때

## Core Model

전략 원칙은 세 가지다.
- `Linda Raschke`식: 박스 중앙이 아니라 가장자리에서만 짧게 먹는다.
- `Connors`식: RSI(2) 같은 짧은 평균회귀 필터를 진입 확인용으로 쓴다.
- `Avellaneda-Stoikov`식: 손실 중인 방향의 인벤토리가 커질수록 그 방향 추가 진입을 보수적으로 줄인다.

실전 결론:
- 단순 그리드보다 `edge fade + breakout stop + inventory skew`가 더 안전하다.
- 박스권이 무너지면 봇은 즉시 `STOPPED`로 전환한다.
- 중앙 구간에서는 신규 진입 금지다.

## Box Regime Checklist

봇을 켜기 전에 아래를 확인한다.
- 최근 `4h 20봉` 기준 상단/하단이 반복적으로 반응하는가
- `1h` 종가가 박스 밖으로 `2개 이상` 연속 안착하지 않았는가
- `ADX(14) < 23` 또는 추세 가속이 뚜렷하지 않은가
- 펀딩이 과열되지 않았는가
  - 기본 한도: `abs(fundingRate) <= 0.0003`
- OI가 급증하지 않았는가
  - 최근 `5m OI`가 직전 평균 대비 `+5%` 이상 급증하면 가동 중지 검토

하나라도 깨지면 박스장 봇을 끄고 추세장으로 재분류한다.

## Entry Logic

기본 운영 범위:
- `BOX_LOW`: 최근 4h 스윙 저점
- `BOX_HIGH`: 최근 4h 스윙 고점
- `BOX_MID`: `(BOX_LOW + BOX_HIGH) / 2`

진입 허용 구간:
- LONG: 박스 하단 `15~20%` 구간
- SHORT: 박스 상단 `15~20%` 구간

진입 필터:
- LONG
  - 가격이 하단 진입 구간 도달
  - `1m` 또는 `3m RSI(2) < 12`
  - 직전 캔들이 꼬리 후 회복하거나 현재 캔들 종가가 직전 고가를 회복
- SHORT
  - 가격이 상단 진입 구간 도달
  - `1m` 또는 `3m RSI(2) > 88`
  - 직전 캔들이 윗꼬리 후 밀리거나 현재 캔들 종가가 직전 저가를 하향

중앙부 규칙:
- `BOX_MID +/- 10% of box height` 구간에서는 신규 진입 금지

## Exit Logic

청산은 3단계로 나눈다.
- 1차 청산: `BOX_MID`
- 2차 청산: 반대편 `1/4` 구간
- 잔여 청산: 반대편 엣지 또는 짧은 ATR 트레일

예시:
- LONG이면 `BOX_LOW` 근처 진입
- 1차는 `BOX_MID`
- 2차는 `BOX_HIGH - 25% * box_height`
- 잔여는 `BOX_HIGH` 전후 또는 `5m ATR * 1.2` 추적

## Stop And Pause Rules

손절:
- LONG: `BOX_LOW - 0.5 ~ 0.8 x ATR(15m)`
- SHORT: `BOX_HIGH + 0.5 ~ 0.8 x ATR(15m)`

봇 중지 조건:
- `1h` 종가가 박스 밖으로 `2봉 연속` 안착
- 거래량 급증 + OI 급증 동반
- 일손실 한도 도달
- 연속 3손실
- 주요 뉴스 / CPI / FOMC / XRP 관련 이벤트 직전

기본 한도:
- `MAX_CONSECUTIVE_SL = 3`
- `DAILY_LOSS_LIMIT_PCT = 1.5 ~ 2.0`
- `COOLDOWN_AFTER_3SL = 2h`

## Sizing

자동봇 기준 권장:
- 레버리지: `2x ~ 5x`
- 1회 손실 허용: 총자산의 `0.25% ~ 0.5%`
- 한 방향 최대 노출: 사용 가능 증거금의 `20% ~ 30%`

주의:
- 박스 하단에서 LONG, 상단에서 SHORT를 동시에 들고 있어도 된다.
- 하지만 한쪽 손실이 누적되면 그 방향 진입 간격을 넓혀야 한다.
- 이것이 `inventory skew`다.

## Current XRP Defaults

이 값은 고정 상수가 아니라, 현재 구조를 보고 갱신해야 한다.

2026-03-07 기준 참고 범위:
- `BOX_LOW ~= 1.344`
- `BOX_HIGH ~= 1.472`
- 넓게 보면 `1.30 ~ 1.50` 박스로 해석 가능

운용 시:
- 이 값을 코드에 하드코딩하지 말고 최근 `4h` 스윙으로 재계산한다.
- 하드코딩이 필요하면 반드시 날짜를 함께 적는다.

## State Machine

양방향 독립 상태머신 권장:

```text
IDLE
-> ENTRY_ARMED
-> ENTRY_FILLED
-> SCALE_OUT_1
-> SCALE_OUT_2
-> TRAIL_REMAINDER
-> IDLE

ENTRY_ARMED
-> CANCELLED
-> COOLDOWN

ANY
-> STOPPED  # breakout / daily loss / regime invalidation
```

전역 상태:
- `regime = RANGE | TREND`
- `stopped = true | false`
- `daily_loss_lock = true | false`

## Scripts

기존 번들 스크립트:
- `scripts/xrp_box_scalper.py`
- `scripts/backtest_xrp_box.py`
- `scripts/backtest_bidirectional.py`
- `scripts/xrp_edge_fade_backtest.py`
- `scripts/xrp_edge_fade_sweep.py`
- `scripts/xrp_ultra_scalp_backtest.py`
- `scripts/xrp_micro_scalp_backtest.py`
- `scripts/multi_coin_scalper_backtest.py`
- `scripts/multi_coin_selector_backtest.py`

백테스트 예시:

```bash
python3 .claude/skills/xrp-box-scalper/scripts/xrp_edge_fade_backtest.py --profile aggressive --days 90
python3 .claude/skills/xrp-box-scalper/scripts/xrp_edge_fade_backtest.py --profile balanced --days 90
python3 .claude/skills/xrp-box-scalper/scripts/xrp_edge_fade_sweep.py --days 90 --top 10
python3 .claude/skills/xrp-box-scalper/scripts/xrp_ultra_scalp_backtest.py --profile daytrade --days 30
python3 .claude/skills/xrp-box-scalper/scripts/xrp_micro_scalp_backtest.py --profile aggressive --days 30
python3 .claude/skills/xrp-box-scalper/scripts/multi_coin_scalper_backtest.py --engine edge-best-return --days 30 --universe majors --max-symbols 8
python3 .claude/skills/xrp-box-scalper/scripts/multi_coin_selector_backtest.py --engine edge-best-return --days 30 --universe majors --max-symbols 8 --top-k 1,2
```

스크립트를 수정할 때 우선 반영할 것:
- 중앙부 신규 진입 금지
- RSI(2) 필터 옵션화
- 박스 돌파 후 자동 정지
- OI / funding 필터 추가
- inventory skew 로직 추가

## Binance Futures Notes

- Hedge mode 계정이면 `positionSide`를 반드시 명시한다.
- LONG 엔트리: `side=BUY`, `positionSide=LONG`
- LONG 종료: `side=SELL`, `positionSide=LONG`
- SHORT 엔트리: `side=SELL`, `positionSide=SHORT`
- SHORT 종료: `side=BUY`, `positionSide=SHORT`
- 손절은 `STOP_MARKET` 사용
- `TAKE_PROFIT_MARKET` 대신 `TAKE_PROFIT` 또는 분할 지정가 청산을 우선 검토
- `TRAILING_STOP_MARKET`은 추세 추종용 잔여 청산에만 제한적으로 사용

## Usage

```bash
export BINANCE_API_KEY="your_key"
export BINANCE_API_SECRET="your_secret"
python3 .claude/skills/xrp-box-scalper/scripts/xrp_box_scalper.py
```

## References

- Avellaneda & Stoikov, market making inventory control
- Linda Raschke, range trading / short-term mean reversion
- Larry Connors, RSI(2) mean reversion
- Binance Futures REST API docs for `openOrders`, `positionRisk`, `New Order`

## Risk Warning

이 스킬은 실거래 선물 자동화를 전제로 한다.
- 박스권은 언제든 추세장으로 바뀔 수 있다.
- 레버리지와 서버측 주문 오류는 작은 실수를 큰 손실로 확대한다.
- 봇은 `항상 자동 정지 조건`과 `일손실 제한`을 먼저 구현한 뒤 실행한다.
