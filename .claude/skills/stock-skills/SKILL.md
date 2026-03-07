---
name: stock-skills
description: >
  주식 트레이딩 대가(드러켄밀러, 리버모어, CANSLIM, 튜더 존스, 피터 린치)의 전략을
  암호화폐 시장에 적용하는 가이드. 트레이딩 전략, 진입/청산 조건, 리스크 관리, 모멘텀,
  추세추종, 평균회귀, 돌파매수, BTC 사이클, 알트코인 로테이션, 텐배거 발굴에 대한
  질문이나 코인 투자 전략이 필요할 때 사용.
allowed-tools: WebSearch, WebFetch, Read, Write
---

# Stock Skills — 트레이딩 전략 라이브러리

## 개요

주식 시장의 전설적 투자자들의 검증된 전략과 기법을 정리한 스킬 라이브러리.
주식뿐 아니라 암호화폐 시장에 적용하는 방법까지 포함한다.

## 트리거 키워드

- 트레이딩 전략, 매매 기법, 진입 조건, 청산 조건
- 드러켄밀러, 리버모어, CANSLIM, 튜더 존스, 피터 린치
- 모멘텀, 추세추종, 평균회귀, 돌파매수
- BTC 사이클, 알트코인 로테이션, 내러티브 투자

## 지원 파일 — 상세 전략 참조

### 대가 전략 (masters/)
- [masters/druckenmiller.md](masters/druckenmiller.md) — 매크로 트렌드 + 대규모 포지션 집중
- [masters/livermore.md](masters/livermore.md) — 모멘텀 피라미딩 + 피봇 포인트
- [masters/canslim.md](masters/canslim.md) — O'Neil 성장주 선별 7가지 기준
- [masters/tudor-jones.md](masters/tudor-jones.md) — 리스크 관리 + 손실 제한 철학
- [masters/lynch.md](masters/lynch.md) — 텐배거 발굴 + 생활 속 투자

### 핵심 기법 (techniques/)
- [techniques/trend-following.md](techniques/trend-following.md) — 추세 추종 시스템
- [techniques/momentum.md](techniques/momentum.md) — 상대 모멘텀 전략
- [techniques/mean-reversion.md](techniques/mean-reversion.md) — 평균 회귀 전략
- [techniques/breakout.md](techniques/breakout.md) — 돌파 매수 전략

### 코인 시장 적용 (crypto-application/)
- [crypto-application/btc-cycle.md](crypto-application/btc-cycle.md) — BTC 반감기 사이클 트레이딩
- [crypto-application/altcoin-rotation.md](crypto-application/altcoin-rotation.md) — 알트코인 섹터 로테이션
- [crypto-application/narrative-investing.md](crypto-application/narrative-investing.md) — 내러티브 기반 투자
- [crypto-application/success-cases.md](crypto-application/success-cases.md) — 5대 성공 사례 요약
- [crypto-application/success-cases-v2.md](crypto-application/success-cases-v2.md) — 12개 10배+ 성공 사례 심층 분석 (진입 매트릭스, VC 추적법, Exit 프레임워크)
- [crypto-application/followalong-strategy.md](crypto-application/followalong-strategy.md) — 대가 전략 통합 실전 따라하기 가이드

사용 가이드: [USAGE-GUIDE.md](USAGE-GUIDE.md)

## 빠른 참조 — 시장 상황별 전략 선택

| 시장 상황 | 추천 전략 | 참조 파일 |
|-----------|-----------|-----------|
| 강한 상승 추세 | 모멘텀 + 피라미딩 | livermore.md, momentum.md |
| 횡보/박스권 | 평균 회귀 | mean-reversion.md |
| 박스 돌파 | 돌파 매수 | breakout.md |
| 매크로 전환점 | 드러켄밀러식 방향 전환 | druckenmiller.md |
| 성장주 발굴 | CANSLIM 스크리닝 | canslim.md |
| BTC 강세장 | 반감기 사이클 | btc-cycle.md |
| 알트 시즌 | 섹터 로테이션 | altcoin-rotation.md |
| 실전 통합 | 대가 전략 따라하기 | followalong-strategy.md |

## 공통 리스크 관리 원칙

1. **포지션 크기**: 단일 포지션 최대 계좌의 10% (초보자 5%)
2. **손절 원칙**: 진입가 대비 -7~-8% 도달 시 무조건 손절
3. **분산**: 동일 섹터 최대 3개 포지션
4. **수익 보호**: +20% 이상 수익 시 트레일링 스탑 적용
5. **현금 비중**: 약세장/불확실성 구간에서 현금 20~50% 유지

---

## 현재 추천 전략 (2026 Q1)

### 시장 환경 진단

- **BTC 반감기 (2024-04) 후 약 10개월**: 역사적 강세 구간 (반감기 후 6~18개월)
- **매크로**: 연준 금리 동결/인하 관망, DXY 횡보
- **BTC 도미넌스**: 55~60% (Phase 2 → 대형 알트 기회 구간)
- **온체인**: NUPL 0.4~0.6 (낙관 구간, 아직 과열 아님)

### 전략 1: BTC 반감기 사이클 추세 추종

```
근거: 4차 반감기 후 10개월, 역사적으로 12~18개월이 최대 상승 구간
참조: btc-cycle.md, trend-following.md
진입: BTC 200일선 위 + 20>50>200 정렬 유지 중 → 보유 유지
포지션: 포트폴리오 40~50%
손절: 주봉 200일선 하향 이탈 시
목표: 사이클 정점 신호(NUPL > 0.75) 출현까지 보유
```

### 전략 2: XRP 박스권 평균 회귀

```
근거: XRP $1.33~$1.47 박스권 형성 (2026년 Q1 기준, 4주+ 횡보)
참조: mean-reversion.md
진입: 하단 $1.33~$1.35 (RSI < 35 + 볼린저 하단 접촉)
청산: 중심선 $1.40 (50% 익절), 상단 $1.47 (전량 익절)
손절: $1.28 (박스 하단 -4% 이탈)
포지션: 계좌의 5~8% (튜더 존스 1% 리스크 룰 적용)
  → 손절까지 약 5% → 포지션 = 계좌의 20% × 5% = 1% 리스크
```

### 전략 3: DePIN 섹터 내러티브 초기 진입

```
근거: DePIN = "DeFi 2020년" 위치 (출발점), AI 수요 + 실물 인프라 연결
참조: narrative-investing.md, altcoin-rotation.md
대표 코인: RNDR, HNT, IO (섹터 리더 1~3위)
진입: BTC.D 하락 전환 + 해당 코인 52주 신고가 돌파 시
포지션: 개별 코인 3~5% (총 DePIN 10% 이하)
익절: +100% 시 원금 회수, 내러티브 과열 시 전량 청산
손절: -20% (알트 변동성 감안)
```

### 공통 리스크 규칙 (튜더 존스 1% 룰)

```
모든 포지션 공통:
- 단일 거래 최대 리스크 = 계좌의 1%
- 포지션 크기 = (계좌 × 1%) / 손절 %
- 월간 최대 드로우다운 -10% 시 신규 진입 중단
- 3연속 손절 시 하루 거래 중단 + 시장 재평가
```
