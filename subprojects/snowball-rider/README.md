# Snowball Rider

BTC 추세 추종 자동매매 — 눈뭉치 굴리기처럼 복리로 자산을 키우는 전략.

## 전략

BTCUSDT 일봉 기반 추세 추종. 2x 레버리지, 100% 할당, BB 체제전환 SL.

**진입 LONG:** EMA(10) > EMA(26) + RSI(21) > 45

**진입 SHORT:** EMA(10) < EMA(26) + RSI(21) < 55

**청산 SL:** leveraged PnL ≤ -70% (BB 체제전환 시 -40%)

**청산 TP:** 수익 +20% latch 후 EMA(7) vs EMA(14) 역크로스 2일 연속

**BB 체제전환:** BB(20) 폭 > 평균 1.8배 → SL -40%로 축소 (위기 감지)

**백테스트:** $818 → $1,924,496 (6.5년, CAGR +232%, MaxDD 71.9%)

## 배포

AWS Lightsail Seoul (3.34.40.162) — systemd 서비스로 24/7 운용.

```bash
# 클라우드 접속
ssh -i ~/.ssh/lightsail-snowball.pem ubuntu@3.34.40.162

# 서비스 관리
sudo systemctl status snowball-rider    # 상태
sudo systemctl restart snowball-rider   # 재시작
sudo journalctl -u snowball-rider -f    # 실시간 로그

# 배포 업데이트
scp -i ~/.ssh/lightsail-snowball.pem /tmp/snowball-rider.tar.gz ubuntu@3.34.40.162:~
ssh -i ~/.ssh/lightsail-snowball.pem ubuntu@3.34.40.162 "cd snowball-rider && tar xzf ~/snowball-rider.tar.gz && sudo systemctl restart snowball-rider"
```

## 로컬 개발

```bash
# 설치
python3 -m venv .venv
.venv/bin/pip install -e .

# .env 설정
BINANCE_API_KEY=...
BINANCE_API_SECRET=...
SCALPER_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
DRY_RUN=true

# 실행
python -m snowball_rider              # foreground (DRY_RUN=true 기본)
DRY_RUN=false python -m snowball_rider  # 라이브
```

## Telegram 명령어

| 명령 | 기능 |
|------|------|
| `/status` | 포지션, 잔고, 전략 상태 |
| `/kill` | 거래 중단 |
| `/unkill` | 거래 재개 |
| `/close` | 전량 청산 |
| `/report` | 오늘 P&L |
| `/help` | 도움말 |

## 구조

```
src/snowball_rider/
├── strategy.py      — 전략 엔진 (detect + execute)
├── feeds.py         — WebSocket 일봉 수집 + SQLite 저장
├── executor.py      — Binance Futures REST API
├── state.py         — SQLite (positions, candles, config)
├── indicators.py    — EMA, RSI
├── telegram_bot.py  — Telegram 명령어
├── notify.py        — Telegram 알림
├── monitor.py       — 포지션 감시
└── __main__.py      — CLI 진입점
```
