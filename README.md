# 마이클 (Michael)

> 항상 깨어있고, 모든 것을 기억하는 개인 AI 어시스턴트

## 특징

- 🌙 **24시간 깨어있기**: 데몬 프로세스로 항상 실행
- 🧠 **영구 메모리**: 모든 대화와 정보를 기억 (SQLite + 벡터 검색)
- 💬 **메시징 통합**: Telegram 메시징 앱 연동
- 📱 **Mini App**: Telegram Mini App으로 복잡한 폼 입력 지원
- ⏰ **능동적 알림**: 스케줄에 따라 먼저 알림 전송
- 🤖 **Claude Code 기반**: Claude Code CLI 사용 (API 키 불필요)
- 🔍 **시맨틱 검색**: 벡터 임베딩으로 관련 대화 자동 검색

## 중요: Claude Max vs Anthropic API

마이클은 **Claude Code CLI**를 사용하므로 **API 키가 필요 없습니다**.

- ✅ Claude Max 구독만으로 사용 가능
- ✅ 추가 비용 없음
- ✅ 즉시 사용 가능

자세한 내용은 [docs/API_vs_CLI.md](docs/API_vs_CLI.md) 참조

## 아키텍처

```
┌─────────────────────────────────────────────────────┐
│                HTTP Server :3000                     │
│  /webapp/* (Mini App)  /api/*  /health              │
└─────────────────────────┬───────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────┐
│              Gateway (WebSocket) :18789              │
└───┬─────────────┬─────────────┬─────────────┬───────┘
    │             │             │             │
┌───▼───┐   ┌─────▼─────┐  ┌────▼────┐  ┌────▼────┐
│Telegram│   │  Claude   │  │ Memory  │  │Scheduler│
│Channel │   │  Agent    │  │ (SQLite)│  │ (Cron)  │
└────────┘   └───────────┘  └─────────┘  └─────────┘

ngrok tunnel (HTTPS) ─────► localhost:3000
```

## 설치

```bash
# 의존성 설치
pnpm install

# Mini App 빌드
cd ui/telegram-mini-app && pnpm install && pnpm build && cd ../..

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

# 임베딩 설정 (선택)
EMBEDDING_PROVIDER=local  # local, openai, gemini
```

## 실행

### 개발 모드

```bash
# 1. ngrok 실행 (별도 터미널, Mini App용)
ngrok http --url=your-domain.ngrok-free.dev 3000

# 2. 서버 실행 (hot reload)
pnpm dev
```

### 프로덕션 빌드

```bash
# TypeScript 빌드
pnpm build

# 빌드된 파일 실행
pnpm start
```

### 데몬 모드 (24시간 실행)

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
│   ├── core/           # Gateway, HTTP Server
│   ├── brain/          # Memory (SQLite + 벡터 검색)
│   ├── channels/       # Telegram Channel
│   ├── scheduler/      # Cron 스케줄러
│   ├── agent/          # Claude Code Agent
│   ├── memory-new/     # 벡터 임베딩 시스템
│   ├── a2ui/           # A2UI 타입 및 유틸리티
│   └── a2a/            # A2A 프로토콜
├── ui/
│   └── telegram-mini-app/  # Telegram Mini App (React)
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

### Mini App 폼 플로우

1. `/form` 명령어 전송
2. 키보드에 나타난 "📝 예약 폼 열기" 버튼 클릭
3. Mini App에서 폼 작성
4. "예약하기" 버튼 클릭
5. 봇이 제출된 데이터 수신

### WebSocket으로 직접 연결

```bash
# wscat 설치
npm install -g wscat

# Gateway 연결
wscat -c ws://127.0.0.1:18789

# 메시지 전송
> {"from": "cli", "to": "agent", "userId": "test", "content": "Hello Michael"}
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

### 진행 예정

- [ ] A2A 프로토콜 완성 (외부 Agent 연동)
- [ ] 프로덕션 배포 (실제 도메인 + SSL)
- [ ] 추가 채널 지원 (Slack, Discord)

## 문서

- [API vs CLI 비교](docs/API_vs_CLI.md)
- [프로토콜 아키텍처](docs/PROTOCOL_INTEGRATION_ARCHITECTURE.md)
- [작업 이력](WORK_LOG.md)

## License

MIT
