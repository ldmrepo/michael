# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Origin

**"눈덩이 굴리기(Snowball)"** — 소액 자본을 체계적으로 불려나가는 자산관리 시스템.

기존 AI는 요청할 때만 반응하지만, 마이클은:
- 시장 데이터를 **24시간 모니터링**하고
- 투자 기회를 **능동적으로 포착**하여 알리며
- Telegram을 통해 **실시간 브리핑과 거래 실행**을 지원하는 투자 동반자

자산관리 및 투자 전략 실행에 특화된 **24시간 깨어있는 AI 자산관리 전문가**를 목표로 한다.

Moltbot(https://github.com/moltbot/moltbot) 프로젝트를 참고하여 뼈대를 구축했고, 친근한 이름으로 **마이클(Michael)**을 선택했다.

원칙: **"복잡한 것보다 뼈대를 튼튼히"**

## Project Overview

**마이클 (Michael)** is a 24/7 asset management specialist that monitors markets, executes investment strategies, and proactively alerts users through Telegram messaging.

### Core Architecture

The system uses a **hub-and-spoke architecture** with Gateway as the central WebSocket server (port 18789):

```
Gateway (WebSocket hub)
  ├─> Telegram Channel (user interface)
  ├─> Claude Code Agent (AI brain via CLI)
  ├─> Memory (SQLite persistence)
  └─> Scheduler (cron-based proactive notifications)
```

**Critical Design Principle**: All components communicate through Gateway's WebSocket layer - no direct component-to-component calls except Memory (which is accessed synchronously by all components).

## Build and Test Commands

```bash
# Development (hot reload)
pnpm dev

# Build TypeScript
pnpm build

# Run built app
pnpm start

# Run all tests
pnpm test

# Run specific test file
pnpm vitest run src/brain/memory.test.ts
pnpm vitest run src/core/gateway.test.ts
pnpm vitest run src/scheduler/cron.test.ts

# Type checking
pnpm tsc --noEmit

# Daemon management (macOS only)
bash scripts/install-daemon.sh    # Install as launchd service
bash scripts/logs.sh               # View stdout logs
bash scripts/logs.sh error         # View stderr logs
bash scripts/uninstall-daemon.sh   # Remove daemon
```

## Critical Implementation Details

### 1. Claude Code CLI Integration (NOT SDK)

**IMPORTANT**: This project uses `claude` CLI, NOT `@anthropic-ai/sdk`. See `docs/API_vs_CLI.md` for detailed rationale.

**Why CLI over SDK:**
- Works with Claude Max subscription (no API key needed)
- No additional costs
- User already has claude.ai account

**Implementation in `src/agent/claude-code.ts`:**
```typescript
// CORRECT: Use -p (print) mode with stdin
const process = spawn('claude', ['-p']);
process.stdin.write(prompt);
process.stdin.end();

// WRONG: --task flag doesn't exist
const process = spawn('claude', ['--task', prompt]); // ❌
```

The agent parses special markers from Claude's responses:
- `[FACT:key:value]` → saves to memory.facts table
- `[SCHEDULE:cron:message]` → saves to memory.schedules table

### 2. Memory System Architecture

**File**: `src/brain/memory.ts`

Uses **better-sqlite3** (synchronous API). The system uses **two separate SQLite database files**:

#### Database File Separation

| Database | Path | Purpose | Library |
|----------|------|---------|---------|
| **Main Memory DB** | `data/memory.db` | Core app data (users, messages, facts, schedules) | better-sqlite3 |
| **Vector Index DB** | `data/memory-index.db` | Embeddings and vector search | node:sqlite + sqlite-vec |

**Why separate files?**
- Main DB uses `better-sqlite3` (synchronous, stable, production-ready)
- Vector DB uses `node:sqlite` (Node.js 22+ built-in) for sqlite-vec extension compatibility
- Isolates vector search failures from core functionality
- Allows independent backup/migration of each database

#### Michael Core Tables (memory.db)
- `users`: User registry
- `messages`: Conversation history
- `facts`: Key-value facts about users
- `schedules`: Cron-based scheduled tasks
- `messages_fts`: FTS5 virtual table for full-text search

#### Vector Search Tables (memory-index.db)
Managed by `MemoryIndexManager` from `src/memory-new/`:
- `meta`: System metadata (model, provider, chunk settings)
- `files`: Indexed file tracking with hash for change detection
- `chunks`: Chunked text with embeddings
- `embedding_cache`: Embedding cache for performance
- `memory_fts`: FTS5 for hybrid search (BM25 keyword matching)
- `vec_chunks`: sqlite-vec virtual table for vector similarity search

**Critical ordering bug fix**: When querying messages, ALWAYS use:
```typescript
ORDER BY timestamp DESC, id DESC  // id prevents same-timestamp collisions
```

All database operations are synchronous - no async/await needed for Memory methods.

### 2.1 Vector Search Integration (Moltbot)

Michael integrates Moltbot's vector embedding search for semantic memory retrieval.

**Key APIs:**
```typescript
// Initialize vector search engine
await memory.initializeVectorSearch(config);

// Index messages as embeddings
await memory.syncMessagesToChunks(userId);

// Semantic search (vector + FTS5 hybrid)
const results = await memory.searchMessagesVector(userId, query, {
  maxResults: 5,
  minScore: 0.7,
});
```

**Agent Integration:**
Claude Agent automatically uses vector search when initialized:
- Loads recent messages (last 5)
- Finds semantically related past conversations (top 3)
- Includes both in system prompt for context-aware responses

**Files:**
- `src/memory-new/manager.ts`: MemoryIndexManager (core)
- `src/memory-new/config.ts`: Configuration types
- `src/memory-new/embeddings.ts`: Embedding provider factory

### 3. Gateway Message Protocol

**File**: `src/core/gateway.ts`

WebSocket messages follow this structure:
```typescript
{
  from: 'telegram' | 'scheduler' | 'cli',
  to: 'agent' | 'telegram',
  userId: string,
  content: string,
  metadata?: Record<string, any>
}
```

**Message Flow Example:**
```
User types in Telegram
  → TelegramChannel sends {from: 'telegram', to: 'agent', ...}
  → Gateway routes to Agent
  → Agent responds via Gateway.send()
  → Gateway routes {from: 'agent', to: 'telegram', ...}
  → TelegramChannel receives and sends to user
```

### 4. Scheduler Design

**File**: `src/scheduler/cron.ts`

- Loads all active schedules from DB on startup
- Uses `node-cron` for task execution
- Sends scheduled messages via Gateway (not directly to Telegram)
- ALWAYS validates cron expressions with `cron.validate()` before scheduling

### 5. Telegram Integration

**File**: `src/channels/telegram.ts`

- Uses Telegraf bot framework
- Connects to Gateway as WebSocket client
- Implements reconnection logic (max 5 retries with exponential backoff)
- Maps Telegram chat IDs to internal user IDs in metadata

## Environment Variables

Required in `.env`:
```bash
# Optional: Gateway configuration
GATEWAY_PORT=18789
GATEWAY_HOST=127.0.0.1

# Required: Telegram bot
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather

# Optional: Data directory
DATA_DIR=./data

# Vector Search Configuration
EMBEDDING_PROVIDER=local  # Options: local, openai, gemini

# For OpenAI embeddings
# OPENAI_API_KEY=sk-...

# For Gemini embeddings
# GOOGLE_API_KEY=...

# Debug options
DEBUG_MEMORY_EMBEDDINGS=false
```

**DO NOT SET `ANTHROPIC_API_KEY`** - this project uses Claude Code CLI, not the SDK.

**Embedding Provider Options:**
- `local`: Free, offline, uses node-llama-cpp (recommended for development)
- `openai`: Better accuracy, requires API key
- `gemini`: Free tier available, requires API key

## Testing Strategy

### Test Isolation
Each test file creates isolated instances:
- Random ports for Gateway tests (to avoid EADDRINUSE)
- In-memory SQLite databases (`:memory:`)
- Separate data directories

### Key Test Files
- `memory.test.ts`: 26 tests covering CRUD, FTS5 search, vector search API, edge cases
- `memory.integration.test.ts`: 12 tests for full vector search integration (7 skipped without `INTEGRATION_TESTS=true`)
- `gateway.test.ts`: 8 tests for WebSocket routing and error handling
- `cron.test.ts`: 9 tests for schedule management and cron validation

### Running Individual Tests
```bash
# Unit tests
pnpm vitest run src/brain/memory.test.ts

# Integration tests (requires embedding provider)
INTEGRATION_TESTS=true pnpm vitest run src/brain/memory.integration.test.ts
```

## Common Pitfalls

1. **Don't use `--task` flag with claude CLI** - use `-p` mode with stdin
2. **Don't forget `id` in ORDER BY** - prevents timestamp collision bugs
3. **Don't call Agent directly from Telegram** - always route through Gateway
4. **Don't use async with Memory** - better-sqlite3 is synchronous
5. **Don't skip cron.validate()** - invalid expressions crash node-cron
6. **Don't assume Telegram is always available** - check `TELEGRAM_BOT_TOKEN` before starting

## Project Phases

### Infrastructure (Complete)
- [x] Phase 1: Memory System (SQLite + FTS5)
- [x] Phase 2: Gateway Server (WebSocket)
- [x] Phase 3: Claude Code Agent (CLI integration)
- [x] Phase 4: Telegram Channel (Telegraf)
- [x] Phase 5: Scheduler (node-cron)
- [x] Phase 6: Daemon deployment (launchd for macOS)
- [x] Phase 7: Vector Search (Moltbot integration) - Semantic memory retrieval

### Protocol Integration (Complete)
- [x] Phase 8-12: AG-UI, A2UI, A2A protocols

### Asset Management — 자율 도구 관리 (Current)
- [x] Binance/Polymarket API 기본 정보 스킬 제공
- [x] 마이클 세컨드 브레인 (NLM) 통합 — 경험 축적 + [LESSON:] 마커
- [x] 사전 스케줄/스크립트 제거 → 마이클이 필요시 직접 도구 생성·실행
- [x] Finance Agent (주식/코인/환율 A2A 서비스)

**도구 관리 방식**: 마이클은 `binance`, `polymarket` 스킬의 API 정보를 참조하여
필요시 직접 스크립트를 작성·실행한다. 반복 사용 도구는 `[CREATE_SKILL:]` 마커로
스킬로 저장. 학습 사항은 `[LESSON:]` 마커로 NLM에 기록하여 축적한다.

### 코드 작성 규칙
- **민감 정보 금지**: API 키, 비밀번호, 지갑 주소 등을 코드에 하드코딩하지 않는다. 반드시 환경변수(`os.environ`) 사용
- **스킬 스크립트**: 특정 스킬 전용 스크립트는 `.claude/skills/{스킬명}/scripts/`에 작성
- **공통 스크립트**: 여러 스킬에서 공유하는 유틸리티는 `scripts/` 디렉토리에 작성

### 세컨드 브레인 (NLM) 활용 — 필수 실행 지침

NLM은 마이클의 장기 기억 시스템이다. **매 작업 시 반드시 활용**할 것.

#### 필수 워크플로우: Query → Act → Record

**1단계: 작업 전 Query (Pull before Act)**
관련 작업을 시작하기 전에 반드시 해당 노트북에 query하여 과거 경험/교훈을 확인한다.
```bash
# Binance 거래 관련 작업 전
nlm notebook query 766109ef-af97-4ed3-a1a8-9ce9e14a9c14 "관련 질문"

# Polymarket 거래 관련 작업 전
nlm notebook query c4c42932-5266-421c-9657-deb50b38515d "관련 질문"

# 포트폴리오/리스크 관련 작업 전
nlm notebook query 36e85c3c-f11d-4206-bc75-cd975849f749 "관련 질문"

# 범용/기타
nlm notebook query c3cebd51-e260-4de4-9a57-a9cc9913dd4c "관련 질문"
```

**2단계: 작업 실행 (Act)**

**3단계: 경험 즉시 기록 (Write after Learn)**
성공/실패 경험은 즉시 Note로 기록한다.
```bash
nlm note create <notebook_id> --title "[SUCCESS|FAILURE] YYYY-MM-DD: 간략 설명" --content "원인, 과정, 결과, 교훈"
```

#### 노트북 선택 기준
- **Binance 거래 실행** → `binance_trader` (766109ef...)
- **Polymarket 거래 실행** → `pm_trader` (c4c42932...)
- **포트폴리오 점검** → `portfolio` (36e85c3c...)
- **리스크 관리** → `risk` (195aa81f...)
- **범용/기타** → `michael` (c3cebd51...)

#### 자동 기록 마커
- `[LESSON:제목:내용]` → michael 노트북에 Note 자동 생성
- `[CREATE_SKILL:]` → 반복 사용 도구를 스킬로 저장

## Protocol Integration

### AG-UI (Agent-User Interface)
Real-time event streaming protocol for agent-to-user communication.

**Files:**
- `src/core/events.ts` - AG-UI event types and helpers
- `src/core/a2ui.ts` - A2UI message wrapping utilities

### A2UI (Agent-driven UI)
Declarative UI specification for dynamic interface generation.

**Files:**
- `src/a2ui/types.ts` - A2UI component types
- `src/a2ui/state.ts` - Data model state management
- `src/channels/telegram-renderer.ts` - A2UI → Telegram native mapping
- `ui/telegram-mini-app/` - Telegram Mini App for complex forms

### A2A (Agent-to-Agent)
Protocol for inter-agent communication and multi-agent workflows.

**Files:**
- `src/a2a/types.ts` - A2A protocol types (JSON-RPC 2.0)
- `src/a2a/agent-card.ts` - Michael's AgentCard definition
- `src/a2a/server.ts` - A2A server for incoming requests
- `src/a2a/client.ts` - A2A client for calling other agents
- `src/a2a/orchestrator.ts` - Multi-agent workflow orchestration

**Usage:**
```typescript
// A2A Server
const server = new A2AServer({ baseUrl: 'http://localhost:18789' });
server.setHandler({
  processMessage: async (message) => agent.chat(message),
});

// A2A Client
const client = new A2AClient();
const response = await client.chat('https://other-agent.example.com', 'Hello!');

// Orchestrator (multi-agent workflow)
const orchestrator = new A2AOrchestrator();
orchestrator.registerAgent('finance', 'http://localhost:8001');
orchestrator.registerAgent('market-scanner', 'https://scanner-agent.example.com');
const result = await orchestrator.runWorkflow([
  { agent: 'finance', message: 'BTC 현재가 및 기술 분석' },
  { agent: 'market-scanner', message: '고확률 예측 마켓 스캔', dependsOn: ['step_0'] },
]);
```

## Code Style Notes

- TypeScript strict mode enabled
- ESNext modules (`"type": "module"` in package.json)
- File extensions required in imports: `import { X } from './x.js'`
- Prefer descriptive variable names over abbreviations
- Log important events with emoji prefixes for visual scanning
