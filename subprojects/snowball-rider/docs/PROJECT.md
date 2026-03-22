---
title: "Snowball Rider 프로젝트"
aliases: [Project, 프로젝트 정의]
date: 2026-03-22
created: 2026-03-22
updated: 2026-03-22
type: playbook
domain: binance
tags: [project, snowball-rider, btc, trend-following]
source: manual
status: active
---

# Snowball Rider

> [!info] 눈뭉치 굴리기 — 작은 자본을 추세에 올라타서 복리로 키우는 전략

## 핵심 철학

1. **단일 종목 집중** — BTCUSDT only
2. **큰 추세만 따라감** — 일봉 EMA 크로스 기반, 월 0.5~1회 거래
3. **부분 할당** — 60% 투자, 40% 예비금 (블랙스완 방어)
4. **복리 성장** — 수익 재투자, 눈뭉치처럼 굴리기

## 전략 히스토리

| 버전 | 이름 | 결과 | 상태 |
|------|------|------|------|
| v1 | [[strategies/v1-xrp-trend/v1 XRP 추세 추종\|XRP 추세 추종]] | 모든 조건에서 청산 | **RETIRED** |
| **v2** | [[strategies/v2-btc-consensus/v2 BTC 합의 전략\|BTC 합의 전략]] | **$818→$84,797 (6.5년, CAGR+105%)** | **ACTIVE** |

## 게이트 기준

| # | 게이트 | 기준 | v2 결과 |
|---|--------|------|---------|
| 1 | 백테스트 수익률 | > 0% (1년) | +105%/yr PASS |
| 2 | 최대 드로우다운 | < 70% | 60.5% PASS |
| 3 | 청산 횟수 | 0 | 0 PASS |
| 4 | 월평균 거래 수 | ≥ 0.3 | 0.42/mo PASS |
| 5 | 양의 기대값 | W×AvgWin > L×AvgLoss | 85%×50% > 15%×32% PASS |
| 6 | OOS 검증 | 5/5 윈도우 양수 | 5/5 PASS |
| 7 | Robust 검증 | 모든 ±1 이웃 > B&H | PASS |
| 8 | 독립 재구현 | 결과 일치 | 100% PASS |

## 기술 스택

- Python 3.12+, WebSocket (실시간 캔들), SQLite (상태 저장)
- Binance USD-M Futures, Hedge mode
- Telegram Bot (원격 제어)

## 관련 문서

- [[문서작성규칙]]
- [[strategies/v2-btc-consensus/v2 BTC 합의 전략]]
- [[strategies/v1-xrp-trend/v1 XRP 추세 추종]] (archived)
