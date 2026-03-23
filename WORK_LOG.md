# Work Log

## 2026-03-07: XRP 박스권 자동 단타 봇 설계 및 백테스트

### 배경
- XRP LONG 포지션 보유 중: 11,960 XRP @ $1.358, 12x leverage
- XRP $1.33~$1.47 박스권 14일+ 횡보 확인
- 목표: 박스권 패턴 활용 자동 단타 봇, 일일 10% 수익 (마진 대비)

### 수행 작업

#### 1. 전문가 팀 설계 (Architect + Red Team + Quant)
- 3명 병렬 에이전트로 봇 설계
- **Architect**: 상태 머신 아키텍처 (IDLE → ENTRY_SIGNAL → IN_POSITION → EXIT_EVAL → COOLDOWN → STOPPED)
- **Red Team**: 31% 승률 + 12x 레버리지 = 음의 기대값 문제 식별, 파라미터 수정 요구
- **Quant**: 파라미터 최적화 수행 → 최적 Entry/TP/SL 도출

#### 2. 봇 구현
- 파일: `.claude/skills/xrp-box-scalper/scripts/xrp_box_scalper.py` (~950 lines)
- 양방향 LONG+SHORT 동시 운용 (Binance Hedge mode)
- 환경변수 API 키 관리, 리스크 관리 (3-SL/5-SL 쿨다운, 일일 손실 한도 -3%)
- 박스 범위 이탈 시 자동 대기

#### 3. 백테스트 버그 수정
- 컴파운딩 버그: 잔고 기반 포지션 사이징 → 고정 사이징으로 수정
- 박스 범위 필터 누락: 가격 $2~$3.6에서도 진입 → `BOX_LOW <= price <= BOX_HIGH` 조건 추가
- RSI 필터 제거: RSI<=35 발생 7.8%로 거래 기회 과도 제한

#### 4. 최종 백테스트 결과 (4H Aggressive 12x, 250일)

| 지표 | 값 |
|------|-----|
| Config | LONG $1.37/$1.42/$1.34, SHORT $1.43/$1.38/$1.46 |
| 총 거래 | 20회 (LONG 7 + SHORT 13) |
| 승률 | 55.0% (11W/9L) |
| 총 P/L | +$2,141 (+158%) |
| Profit Factor | 4.49 |
| Max Drawdown | 12.25% |
| 박스 활성 | 30/250일 (12%) |
| 거래일 평균 | +$119/day (8.8%) |

#### 5. 수익성 평가
- 조건부 수익성 있음 (박스권 유지 시)
- LONG 압도적 안정 (WR 71.4%, PF 8.26) vs SHORT 불안정 (WR 46.2%)
- 연환산 ~230%, 단 박스 활성 12%에 불과
- 12x 레버리지 리스크 감안 필요

### 현재 상태
- XRP 포지션: 11,960 LONG @ $1.358, PnL +$111
- 거래소 주문: SL $1.3413, SL $1.3580(BE), TP $1.5000 활성
- 모니터 v6: 중지 (사용자 요청)
- 봇: 구현 완료, 라이브 미실행

### 관련 파일
- `.claude/skills/xrp-box-scalper/scripts/xrp_box_scalper.py` — 메인 봇
- `.claude/skills/xrp-box-scalper/scripts/backtest_bidirectional.py` — 양방향 백테스트
- `.claude/skills/xrp-box-scalper/SKILL.md` — 스킬 문서
- `scripts/xrp_scalp_optimizer.py` — Quant 파라미터 최적화
