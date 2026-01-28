# 마이클 (Michael)

> 항상 깨어있고, 모든 것을 기억하는 개인 AI 어시스턴트

## 특징

- 🌙 **24시간 깨어있기**: 데몬 프로세스로 항상 실행
- 🧠 **영구 메모리**: 모든 대화와 정보를 기억
- 💬 **메시징 통합**: Telegram 메시징 앱 연동
- ⏰ **능동적 알림**: 스케줄에 따라 먼저 알림 전송
- 🤖 **Claude Code 기반**: Claude Code CLI 사용 (API 키 불필요)

## 중요: Claude Max vs Anthropic API

마이클은 **Claude Code CLI**를 사용하므로 **API 키가 필요 없습니다**.

- ✅ Claude Max 구독만으로 사용 가능
- ✅ 추가 비용 없음
- ✅ 즉시 사용 가능

자세한 내용은 [docs/API_vs_CLI.md](docs/API_vs_CLI.md) 참조

## 아키텍처

```
┌─────────────────────────────────────────┐
│         Gateway (WebSocket)              │  ← 항상 실행되는 데몬
│         Port: 18789                      │
└─────────────┬───────────────────────────┘
              │
      ┌───────┴───────┐
      │               │
┌─────▼─────┐  ┌─────▼──────┐
│ Channels   │  │  Brain     │
│ (Telegram) │  │  (Memory)  │
└────────────┘  └────────────┘
```

## 설치

```bash
# 의존성 설치
pnpm install

# 환경 변수 설정
cp .env.example .env
# .env 파일을 편집하여 필요한 설정 입력
```

## 실행

### 개발 모드
```bash
# hot reload로 실행
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

# 재시작
bash scripts/restart-daemon.sh

# 로그 확인
bash scripts/logs.sh          # stdout 로그
bash scripts/logs.sh error    # stderr 로그
bash scripts/logs.sh all      # 모든 로그

# 데몬 제거
bash scripts/uninstall-daemon.sh
```

## 프로젝트 구조

```
michael/
├── src/
│   ├── core/          # 핵심 Gateway 서버
│   ├── brain/         # 메모리 관리 시스템
│   ├── channels/      # Telegram, Slack 등 채널
│   ├── scheduler/     # Cron 스케줄러
│   └── agent/         # Claude API 통합
├── config/            # 설정 파일
├── data/              # 데이터 저장소
│   ├── memory/        # 메모리 파일
│   └── sessions/      # 세션 로그
└── package.json
```

## 테스트

```bash
# 모든 테스트 실행
pnpm test

# 특정 테스트만 실행
pnpm vitest run src/brain/memory.test.ts
pnpm vitest run src/core/gateway.test.ts
pnpm vitest run src/scheduler/cron.test.ts

# 커버리지 확인
pnpm test --coverage
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
"안녕 마이클" - 자연어 대화
"내 생일은 3월 15일이야" - 정보 기억
"매일 9시에 알려줘" - 스케줄 설정
```

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

- [x] Phase 0: 프로젝트 초기 설정
- [x] Phase 1: Memory System 구현 (SQLite + FTS5)
- [x] Phase 2: Gateway Server 구현 (WebSocket)
- [x] Phase 3: Claude Code Agent 통합 (CLI)
- [x] Phase 4: Telegram 통합 (Telegraf)
- [x] Phase 5: Scheduler 구현 (node-cron)
- [x] Phase 6: 데몬화 및 배포 (launchd)

## License

MIT
