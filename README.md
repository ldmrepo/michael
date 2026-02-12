# 마이클 (Michael)

> 항상 깨어있고, 모든 것을 기억하는 개인 AI 어시스턴트

## 특징

- 🌙 **24시간 깨어있기**: pm2/launchd 데몬으로 항상 실행
- 🧠 **영구 메모리**: 모든 대화와 정보를 기억 (SQLite + 벡터 검색)
- 💬 **멀티 채널**: Telegram, 웹 채팅, REST API 지원
- 📱 **Mini App**: Telegram Mini App으로 복잡한 폼 입력 지원
- ⏰ **능동적 알림**: 스케줄에 따라 먼저 알림 전송
- 🤖 **Claude Code 기반**: Claude Code CLI 사용 (API 키 불필요)
- 🔍 **시맨틱 검색**: 벡터 임베딩으로 관련 대화 자동 검색
- 💰 **투자 서비스**: Binance 포트폴리오 자동 모니터링 (14개 cron job + Telegram 알림)
- 🎯 **예측 마켓**: Polymarket 자동 모니터링 (가격 추적, 고확률 스캔, 차익거래 감지)
- 📊 **실시간 금융 데이터**: 주식, 암호화폐, 환율 조회 (yfinance, CoinGecko)
- 🧘 **명상 생성기**: 맞춤형 명상 스크립트 생성 및 TTS 음성 변환 (OpenAI TTS)
- 🎬 **비디오 생성**: ComfyUI + Wan2.2 I2V 기반 YouTube Shorts 자동 생성

## 중요: Claude Max vs Anthropic API

마이클은 **Claude Code CLI**를 사용하므로 **API 키가 필요 없습니다**.

- ✅ Claude Max 구독만으로 사용 가능
- ✅ 추가 비용 없음
- ✅ 즉시 사용 가능

자세한 내용은 [docs/API_vs_CLI.md](docs/API_vs_CLI.md) 참조

## 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                       Frontend :3001                         │
│                    (Next.js + A2UI Renderer)                 │
└──────────────────────────┬──────────────────────────────────┘
                           │ /api/chat/stream (SSE)
┌──────────────────────────▼──────────────────────────────────┐
│                    HTTP Server :3000                         │
│  /webapp/* (Mini App)  /api/chat/*  /api/webapp/*  /health  │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                 Gateway (WebSocket) :18789                   │
└───┬─────────┬──────────┬──────────┬──────────┬──────────────┘
    │         │          │          │          │
┌───▼───┐ ┌──▼─────┐ ┌──▼────┐ ┌──▼─────┐ ┌──▼──────────────┐
│Telegram│ │ Claude │ │Memory │ │Schedule│ │  Services       │
│Channel │ │ Agent  │ │(SQLite│ │r(Cron) │ │  ├─Investment   │
└────────┘ └────────┘ │+Vec)  │ └────────┘ │  └─Prediction  │
                      └───────┘            │    Market      │
                                           └─────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                 Finance Agent :8001 (A2A)                    │
│  yfinance (주식)  │  CoinGecko (암호화폐)  │  환율 API       │
└─────────────────────────────────────────────────────────────┘

ngrok tunnel (HTTPS) ─────► localhost:3000 (Mini App, A2A)
```

## 설치

```bash
# 백엔드 의존성 설치
pnpm install

# 웹 프론트엔드 빌드
cd frontend && pnpm install && pnpm build && cd ..

# Telegram Mini App 빌드 (선택)
cd ui/telegram-mini-app && pnpm install && pnpm build && cd ../..

# Python 의존성 (금융 데이터용)
pip3 install yfinance

# 환경 변수 설정
cp .env.example .env
# .env 파일을 편집하여 필요한 설정 입력
```

## 환경 변수

```bash
# 필수
TELEGRAM_BOT_TOKEN=<BotFather에서 발급받은 토큰>

# Gateway 설정
GATEWAY_PORT=18789
GATEWAY_HOST=127.0.0.1

# HTTP 서버 설정
HTTP_PORT=3000
WEBAPP_URL=https://your-domain.ngrok-free.dev

# ngrok (Mini App HTTPS용)
NGROK_AUTHTOKEN=<ngrok 인증 토큰>

# 투자 서비스 (선택)
BINANCE_API_KEY=<Binance API 키>
BINANCE_API_SECRET=<Binance API 시크릿>

# 예측 마켓 (선택)
POLYMARKET_ENABLED=true
POLYMARKET_PRIVATE_KEY=<EOA 프라이빗 키>  # 거래 실행 시만 필요

# 임베딩 설정 (선택)
EMBEDDING_PROVIDER=local  # local, openai, gemini

# 금융 데이터 (선택, fallback용)
ALPHA_VANTAGE_API_KEY=<무료 API 키>
```

## 실행

### 개발 모드

```bash
# 터미널 1: 백엔드 실행
pnpm dev

# 터미널 2: 웹 프론트엔드 실행
cd frontend && pnpm dev

# 터미널 3: Finance Agent (선택)
pnpm dev:finance

# 터미널 4: ngrok (Mini App HTTPS용, 선택)
ngrok http --url=your-domain.ngrok-free.dev 3000
```

### 서비스 포트

| 서비스 | 포트 | 설명 |
|--------|------|------|
| Frontend | 3001 | 웹 채팅 UI (Next.js) |
| HTTP Server | 3000 | REST API, Mini App |
| Gateway | 18789 | WebSocket 허브 |
| Finance Agent | 8001 | A2A 금융 에이전트 |

### 프로덕션 빌드

```bash
# TypeScript 빌드 (백엔드)
pnpm build

# 프론트엔드 빌드
cd frontend && pnpm build && cd ..

# 빌드된 파일 실행
pnpm start
cd frontend && pnpm start  # 별도 터미널
```

### 데몬 모드 (24시간 실행)

#### pm2 (권장)

```bash
# pm2 설치
npm install -g pm2

# 서비스 시작
pm2 start ecosystem.config.cjs

# 상태 확인 / 로그 보기
pm2 status
pm2 logs michael

# 재시작 / 중지
pm2 restart michael
pm2 stop michael
```

#### launchd (macOS)

```bash
# 데몬 설치
bash scripts/install-daemon.sh

# 상태 확인
launchctl list | grep michael

# 로그 확인
bash scripts/logs.sh          # stdout 로그
bash scripts/logs.sh error    # stderr 로그

# 데몬 제거
bash scripts/uninstall-daemon.sh
```

## 프로젝트 구조

```
michael/
├── src/
│   ├── core/           # Gateway, HTTP Server, SSE, AG-UI Events
│   ├── brain/          # Memory (SQLite + 벡터 검색)
│   ├── channels/       # Telegram, Web Channel
│   ├── scheduler/      # Cron 스케줄러
│   ├── agent/          # Claude Code Agent
│   ├── investment/     # Binance 투자 모니터링 서비스
│   ├── prediction-market/ # Polymarket 예측 마켓 모니터링
│   ├── agents/         # 특화 에이전트
│   │   ├── base/       # BaseA2UIAgentExecutor
│   │   └── finance/    # Finance Agent (A2A 서버)
│   ├── memory-new/     # 벡터 임베딩 시스템
│   ├── a2ui/           # A2UI 타입 및 유틸리티
│   └── a2a/            # A2A 프로토콜
├── scripts/
│   ├── finance/        # 금융 API 스크립트 (yfinance, CoinGecko)
│   └── youtube-shorts/ # ComfyUI 비디오 생성
├── frontend/           # 웹 프론트엔드 (Next.js)
│   ├── app/            # Next.js App Router
│   ├── components/a2ui/# A2UI 컴포넌트 렌더러
│   └── lib/agui/       # AG-UI 클라이언트 라이브러리
├── ui/
│   └── telegram-mini-app/  # Telegram Mini App (React)
├── .claude/
│   └── skills/         # Claude Code 스킬 (25개)
│       ├── investment/           # Binance 투자 (hub)
│       ├── binance-*/            # Binance 세부 (analytics, futures, bots, copy-trading)
│       ├── prediction-market/    # Polymarket
│       ├── finance/              # 주식/코인/환율
│       ├── calendar/             # Google Calendar
│       ├── gmail-integration/    # Gmail
│       ├── kakaotalk-chatbot/    # KakaoTalk Open Builder
│       ├── meditation/           # 명상 생성
│       ├── youtube-shorts/       # YouTube Shorts
│       └── ...                   # weather, news, maps, x, notebooklm 등
├── data/
│   ├── memory.db       # 메인 DB (users, messages, facts, schedules)
│   └── memory-index.db # 벡터 인덱스 DB (embeddings, chunks)
└── docs/
```

## 테스트

```bash
# 모든 테스트 실행
pnpm test

# 특정 테스트만 실행
pnpm vitest run src/brain/memory.test.ts
pnpm vitest run src/core/gateway.test.ts

# 통합 테스트 (임베딩 프로바이더 필요)
INTEGRATION_TESTS=true pnpm vitest run src/brain/memory.integration.test.ts
```

## 사용법

### Telegram으로 사용하기

1. Telegram에서 BotFather로 봇 생성
2. `.env`에 `TELEGRAM_BOT_TOKEN` 설정
3. 마이클 실행
4. Telegram에서 봇과 대화

```
/start - 시작
/help - 도움말
/form - 예약 폼 열기 (Mini App 테스트)
"안녕 마이클" - 자연어 대화
"내 생일은 3월 15일이야" - 정보 기억
"매일 9시에 알려줘" - 스케줄 설정
```

### 명상 생성 예시

```
"5분 수면 명상 만들어줘"
"집중력 향상 3분 명상"
"스트레스 해소 명상 10분"
"아침 명상 5분"
```

**지원하는 명상 유형:**

| 유형 | 설명 |
|------|------|
| 수면 (sleep) | 깊은 수면을 위한 릴렉싱 가이드 |
| 집중 (focus) | 업무/학습 집중력 향상 |
| 스트레스 (stress) | 긴장 완화 및 마음 진정 |
| 아침 (morning) | 하루 시작을 위한 에너지 충전 |
| 마음챙김 (mindfulness) | 현재 순간에 집중 |

**시간 옵션:** 3분, 5분, 10분

**TTS 음성:** nova (기본, 차분한 여성), shimmer, onyx, alloy

### 투자 서비스 (Telegram 자동 알림)

Binance API 키와 Polymarket이 설정되면 자동으로 모니터링이 시작됩니다:

**Binance Investment (14개 cron job)**
- 포트폴리오 스냅샷 (4시간마다)
- 가격 변동 감시 (10분마다, 5%+ 알림)
- RSI/MA 기술 분석 (1시간마다)
- 일일 브리핑 (매일 9시)

**Prediction Market (5개 cron job)**
- 고확률 마켓 스캔 (6시간마다)
- 신규 마켓 감지 (4시간마다)
- 가격 변동 추적 (15분마다, 5%+ 알림)
- 차익거래 감지 (2시간마다)
- 일일 브리핑 (매일 9시)

**Telegram 콜백 버튼:**
- `inv_portfolio` / `pm_portfolio` - 포트폴리오 요약
- `inv_brief` / `pm_brief` - 수동 브리핑
- `pm_scan` - 고확률 마켓 스캔
- `pm_watchlist` - 워치리스트

### 금융 정보 질문 예시

```
"비트코인 현재가 알려줘"
"애플 주가"
"삼성전자 시세"
"이더리움 가격"
"달러 환율"
"NVDA 주식 정보"
```

**지원하는 금융 데이터:**

| 종류 | 예시 | 데이터 소스 |
|------|------|------------|
| 미국 주식 | AAPL, MSFT, NVDA, TSLA | yfinance |
| 한국 주식 | 005930.KS (삼성전자) | yfinance |
| 암호화폐 | bitcoin, ethereum, solana | CoinGecko |
| 환율 | USD/KRW, EUR/USD | Frankfurter |

### Mini App 폼 플로우

1. `/form` 명령어 전송
2. 키보드에 나타난 "📝 예약 폼 열기" 버튼 클릭
3. Mini App에서 폼 작성
4. "예약하기" 버튼 클릭
5. 봇이 제출된 데이터 수신

### 웹 프론트엔드로 사용하기

1. 백엔드 실행: `pnpm dev`
2. 프론트엔드 실행: `cd frontend && pnpm dev`
3. 브라우저에서 http://localhost:3001 접속
4. 채팅창에 메시지 입력

**AG-UI 프로토콜 지원:**
- 실시간 스트리밍 응답
- A2UI 동적 UI 렌더링 (카드, 버튼, 폼 등)

### WebSocket으로 직접 연결

```bash
# wscat 설치
npm install -g wscat

# Gateway 연결
wscat -c ws://127.0.0.1:18789

# 메시지 전송
> {"from": "cli", "to": "agent", "userId": "test", "content": "Hello Michael"}
```

### REST API로 직접 호출

```bash
# SSE 스트리밍 (AG-UI)
curl -X POST http://localhost:3000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "안녕 마이클", "userId": "test"}'

# JSON 응답 (비스트리밍)
curl -X POST http://localhost:3000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "비트코인 현재가", "userId": "test"}'
```

### Finance Agent A2A 호출

```bash
# Finance Agent 시작
pnpm dev:finance

# Agent Card 조회
curl http://localhost:8001/.well-known/agent.json

# A2A JSON-RPC 호출
curl -X POST http://localhost:8001/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"type": "text", "text": "삼성전자 주가"}]
      }
    }
  }'
```

## 로드맵

### 완료

- [x] Phase 1: Memory System (SQLite + FTS5)
- [x] Phase 2: Gateway Server (WebSocket)
- [x] Phase 3: Claude Code Agent (CLI)
- [x] Phase 4: Telegram 통합 (Telegraf)
- [x] Phase 5: Scheduler (node-cron)
- [x] Phase 6: 데몬화 (launchd)
- [x] Phase 7: 벡터 검색 통합
- [x] Phase 8-12: HTTP Server + Mini App
- [x] Phase 13: 웹 프론트엔드 통합 (Next.js + AG-UI + A2UI)
- [x] Phase 14: Finance Agent (실시간 금융 데이터)
- [x] Phase 15: Meditation Generator (명상 스크립트 + OpenAI TTS)
- [x] Phase 16: Investment Service (Binance 포트폴리오 자동 모니터링)
- [x] Phase 17: Prediction Market (Polymarket 자동 모니터링 + 알림)
- [x] Phase 18: Video Generation (ComfyUI + Wan2.2 I2V, Lightning LoRA)

### 진행 예정

- [ ] A2A Orchestrator 연동 (Finance Agent ↔ 메인 Agent)
- [ ] 프로덕션 배포 (실제 도메인 + SSL)
- [ ] 추가 채널 지원 (Slack, Discord)
- [ ] PM 자동 거래 (블록체인 거래 실행 자동화)

## 문서

- [API vs CLI 비교](docs/API_vs_CLI.md)
- [프로토콜 아키텍처](docs/PROTOCOL_INTEGRATION_ARCHITECTURE.md)
- [Prediction Market 사용 가이드](docs/PREDICTION-MARKET-USER-GUIDE.md)
- [작업 이력](WORK_LOG.md)

## License

MIT
