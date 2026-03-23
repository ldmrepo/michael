# CLAUDE.md

## Snowball Rider — BTC 추세 추종 전략

### 합의 전략 (3팀 검증 완료)
| 항목 | 값 |
|------|-----|
| 종목 | BTCUSDT |
| EMA | 10/26 |
| RSI | 21 (LONG>45, SHORT<55) |
| SL | -70% leveraged PnL (BB 체제전환 시 -40%로 축소) |
| TP | +20% latch 활성화 → EMA(7) vs EMA(14) 크로스 2일 연속 (종가 기준) |
| BB 체제전환 | BB(20) 폭 > 평균의 1.8배 → SL -40% (위기 감지) |
| 레버리지 | 2x (시작 시 자동 설정) |
| 할당 | 100% (BB 체제전환이 자본 보호) |
| 타임프레임 | 일봉 (확정 캔들만 사용, 진행 중 캔들 제외) |
| detect 주기 | 1시간 (3600초) |

### 백테스트 결과 (6.5년, Crash+Funding 포함)
- $818 → $1,924,496 (CAGR +232%, MaxDD 71.9%, 승률 86%)
- Walk-forward 5/5 OOS 양수, Monte Carlo P(수익>0) = 100%
- 강한 후보 우위 (확정 우위 아님 — 라이브 포워드 축적 필요)

### 배포 환경
- **AWS Lightsail** Seoul (ap-northeast-2a), Ubuntu 24.04 LTS
- IP: 3.34.40.162 (Binance API whitelist 등록)
- systemd 서비스: `snowball-rider.service` (자동 재시작, 부팅 시 시작)
- 비용: $5/월 (90일 무료 ~2026-06)

### Commands
```bash
# 클라우드 (SSH)
ssh -i ~/.ssh/lightsail-snowball.pem ubuntu@3.34.40.162
sudo systemctl status snowball-rider   # 상태 확인
sudo systemctl restart snowball-rider  # 재시작
sudo journalctl -u snowball-rider -f   # 실시간 로그

# 로컬 (개발/테스트)
python -m snowball_rider              # 시작 (DRY_RUN=true 기본)
DRY_RUN=false python -m snowball_rider  # 라이브
python scripts/monitor_cli.py         # 터미널 모니터
```

### Rules
- 민감 정보: 반드시 환경변수 (.env)
- 단일 종목: BTCUSDT only
- 단일 전략: EMA 10/26 + RSI 21 + BB 체제전환 (합의 파라미터 고정)
- DRY_RUN=true 기본값
- 파라미터 변경 금지: 3팀 검증 + walk-forward 완료된 합의 값

### 시작 시 자동 검증
- Hedge mode 확인 (one-way면 종료)
- BTCUSDT 레버리지 2x 설정

### 검증 이력
- Alpha팀 (Robust Optimization): 대부분 이웃 > B&H (ema_slow±2에서 일부 미달)
- Beta팀 (Monte Carlo 5,000회): P(수익>0) > 99% (v2 정확 파라미터 미포함)
- Gamma팀 (Walk-Forward 5윈도우): **4/5 OOS 양수** (W2 하락장 -36.55%)
- 독립 재구현: 100% 결과 일치
- 엔진 수학 감사: 12/12 PASS
- 편향 검증: 셔플 시 전멸 (타이밍 엣지 확인)
- 교차 자산: BTC에서만 작동 (ETH/SOL/BNB/DOGE/XRP 실패)

### 알려진 리스크
- 기간 의존성: 전반기(2019-2022) +365% vs 후반기(2022-2026) +3.6%
- MaxDD 71.9%: 최고점 대비 72% 하락 구간 존재
- 펀딩비: 수익의 ~50% 잠식 (이미 백테스트에 포함)

### 알려진 제한 (백테스트-라이브 차이)
- SL: 백테스트는 일봉 high/low 즉시 체결, 라이브는 1시간 mark price 샘플링
- TP latch: SQLite config 테이블에 persist (프로세스 재시작 시 자동 복원)
- TP 활성화: 라이브는 종가 기준 (백테스트와 동일)
- BTC 전용: 다른 자산 일반화 불가

### 운영 정책
- 진입: fail-close (API 실패 시 진입 차단, 거래소 untracked 포지션 존재 시 차단)
- 청산: fail-open (API 실패 시 DB 수량으로 fallback, 최선 실행)
- 청산 수량: 거래소 positionAmt 우선, 실패 시 DB qty fallback
- 데이터 신선도: 72h 이상 stale 시 신규 진입 차단, 기존 포지션 SL만 실행
- 캔들 부족 (<30개): mark price 비상 SL만 실행
- 강제 정리: FORCE_CLOSED status로 감사 구분
- 알림 쿨다운: QTY DRIFT/UNTRACKED 10분, STALE 1시간

### 포워드 검증 기준 (6개월 후 판정)
| 기준 | 값 |
|------|-----|
| 최소 거래수 | ≥ 3건 |
| MDD 상한 | ≤ 80% |
| 수익률 하한 | > 0% |
| 승률 하한 | ≥ 50% |
