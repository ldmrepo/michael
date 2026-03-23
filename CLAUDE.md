# CLAUDE.md

## Project Overview

**마이클(Michael)** — 24/7 AI 자산관리 전문가. Telegram으로 실시간 브리핑 및 거래 실행.

### Architecture

```
Gateway (WebSocket :18789)
  ├─> Telegram Channel
  ├─> Claude Code Agent  ← AI brain (CLI, NOT SDK)
  ├─> Memory (SQLite)
  └─> Scheduler (node-cron)
```

모든 컴포넌트는 Gateway를 통해 통신. Memory만 직접 동기 접근.

## Build Commands

```bash
pnpm dev          # 개발 (hot reload)
pnpm build        # TypeScript 빌드
pnpm start        # 빌드 실행
pnpm test         # 전체 테스트
pnpm tsc --noEmit # 타입 체크

bash scripts/install-daemon.sh   # macOS launchd 등록
bash scripts/logs.sh             # stdout 로그
bash scripts/logs.sh error       # stderr 로그
```

## Critical Rules

1. **Claude CLI 사용** — `claude -p` (stdin), NOT `--task`, NOT `@anthropic-ai/sdk`
2. **DO NOT SET `ANTHROPIC_API_KEY`** — Claude Max 구독으로 동작
3. **Memory는 동기** — `better-sqlite3`, async/await 불필요
4. **ORDER BY** — 항상 `ORDER BY timestamp DESC, id DESC` (타임스탬프 충돌 방지)
5. **Gateway 경유 필수** — Telegram ↔ Agent 직접 연결 금지
6. **cron.validate()** — 스케줄 등록 전 반드시 검증

## Environment Variables

```bash
TELEGRAM_BOT_TOKEN=...          # 필수
GATEWAY_PORT=18789              # 선택 (기본값)
DATA_DIR=./data                 # 선택
CLAUDE_MODEL=claude-sonnet-4-6  # 선택 (기본값)
EMBEDDING_PROVIDER=local        # local | openai | gemini
```

## Code Rules

- **민감 정보 금지**: API 키/비밀번호/지갑 주소 → 반드시 환경변수
- **스킬 스크립트**: `.claude/skills/{스킬명}/scripts/`
- **공통 스크립트**: `scripts/`
- TypeScript strict mode, ESNext modules, import 시 `.js` 확장자 필수
- **전략 전환 원칙**: 전략을 개선하거나 새 전략으로 전환할 때는 과거 전략과의 호환성을 위해 코드를 남기지 않는다. 기존 전략 관련 소스, 설정, CLI, 테스트, 문서, dead import를 함께 제거하고 단일 활성 전략 경로만 유지한다.
- **전략 기준선 원칙**: 현재 채택한 전략 기준선은 마지막 유효 OOS(out-of-sample) 버전으로 고정한다. 기준선은 잘못되었다는 근거가 확인될 때만 변경하고, 변경 전에는 반드시 현재 기준선 대비 실측 백테스트/워크포워드 열화를 입증해야 한다.
- **현재 기준선 식별자**: `binance-scalper`의 현재 기준선 run id는 `20260308T071943Z-strategy-walkforward`다.

## Agent Response Markers

마이클이 응답에 포함하면 자동 처리:

| 마커 | 동작 |
|------|------|
| `[FACT:key:value]` | 메모리 facts 저장 |
| `[SCHEDULE:cron:msg]` | 반복 스케줄 등록 |
| `[SCHEDULE_ONCE:min:msg]` | 1회 알림 |
| `[CANCEL_SCHEDULE:id]` | 스케줄 취소 |
| `[LESSON:title:content]` | NLM + Vault 저장 |
| `[CREATE_SKILL:name]...[/CREATE_SKILL]` | 스킬 파일 생성 |

## NLM 세컨드 브레인 — Query → Act → Record

작업 전 반드시 관련 노트북 query, 완료 후 즉시 기록.

```bash
# 노트북별 query
nlm notebook query 766109ef-... "질문"  # binance_trader
nlm notebook query c4c42932-... "질문"  # pm_trader
nlm notebook query 36e85c3c-... "질문"  # portfolio
nlm notebook query c3cebd51-... "질문"  # michael (범용)

# 기록
nlm note create <notebook_id> --title "[SUCCESS|FAILURE] YYYY-MM-DD: 설명" --content "내용"
```

## Key Files

| 역할 | 파일 |
|------|------|
| AI Agent | `src/agent/claude-code.ts` |
| Gateway | `src/core/gateway.ts` |
| Memory | `src/brain/memory.ts` |
| Scheduler | `src/scheduler/cron.ts` |
| Telegram | `src/channels/telegram.ts` |
| Vector Search | `src/memory-new/manager.ts` |
