---
name: binance-trailing-stop
description: >
  Binance Futures에서 Playwright 브라우저를 통해 Trailing Stop 주문을 UI로 직접 등록하는 자동화 스킬.
  활성화 가격(activationPrice), 콜백 비율(callbackRate%), 수량(size)을 파라미터로 받아
  Close 탭 → Trailing Stop 선택 → 값 입력 → Close long 순서로 주문을 제출한다.
  키워드: 트레일링 스탑, trailing stop, 바이낸스 선물, binance futures, 추적 매도, 자동 청산
---

# Binance Futures Trailing Stop 설정

## 파라미터

| 파라미터 | 예시 | 설명 |
|---------|------|------|
| `activationPrice` | `1.5` | 트레일링 스탑 활성화 기준가 |
| `callbackRate` | `5` | 최고가 대비 하락 % (0.1~5%) |
| `size` | `11960` 또는 `full` | 청산 수량 (full = Max 전체) |
| `symbol` | `XRPUSDT` | 선물 심볼 (기본값: XRPUSDT) |

## 단계별 실행 절차

### 1. 페이지 확인
현재 탭이 `https://www.binance.com/en/futures/{SYMBOL}` 인지 확인. 없으면 navigate.

### 2. Close 탭 클릭
```
getByRole('tab', { name: 'Close' })
```

### 3. Trailing Stop 선택
```
"Stop Limit" 탭 내부 combobox(드롭다운 화살표) 클릭
→ listbox에서 "Trailing Stop" 옵션 선택
→ getByTestId('trailingStop')
```

### 4. 값 입력
```
Callback Rate:    page.locator('#priceRate-NNN').fill(callbackRate)
Activation Price: page.locator('#activatePrice-NNN').fill(activationPrice)
Size:             page.locator('#unitAmount-NNN').fill(size)
  size="full" → Max 값(포지션 전체 수량) 직접 입력
```

### 5. Close long 제출
```
getByRole('button', { name: 'Close long' })
```

### 6. 주문 확인
```
Open Orders 탭 → Basic 탭:
- Type: "Trailing Stop / Close Long"
- Conditions: "Activation Price >= {activationPrice}"
- Amount: "{size} XRP"
```

## 중요 주의사항

- **Callback Rate 범위**: 0.1% ~ 5% (Binance 제한)
- **Activation Price**: LONG 포지션은 현재가보다 높게 설정
- **API 사용 불가**: `/fapi/v1/order`로 TRAILING_STOP_MARKET 주문 시 -4120 에러 발생 → **반드시 UI 방식으로만 등록**
- **기존 TP 충돌**: 동일 포지션에 TAKE_PROFIT 주문이 있으면 사전 취소 필요
- **SL 독립 유지**: Stop Market(SL)은 Trailing Stop과 독립적으로 공존함

## 동작 원리

```
가격 상승 → activationPrice 도달 → 활성화
→ 최고가 추적 → 최고가 대비 callbackRate% 하락 시 시장가 전량 청산

예시 (activationPrice=1.5, callbackRate=5%):
  1.36 → 1.5 도달 → 활성화
  1.5 → 1.6 상승 → 추적
  1.6 → 1.52 하락 시 청산  (= 1.6 × 0.95)
  1.6 → 1.7 → 1.615 하락 시 청산  (= 1.7 × 0.95)
```

## 실전 사례 (2026-03-07)

```
포지션: XRPUSDT LONG 12x, 11,960 XRP @ $1.358
SL: $1.3300 Stop Market (유지)
Trailing Stop: activationPrice=$1.5, callbackRate=5%, size=11960
결과: Open Orders에 "Trailing Stop / Close Long" 주문 등록 확인
```
