# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Origin

기존 AI는 **요청할 때만 반응**한다. 사용자가 원하는 것은 그 한계를 넘는 것이다:
- 모든 대화와 정보를 **기억**하고
- 필요한 시점에 **스스로 행동**하고 조언하며
- Telegram/Slack 같은 채널을 통해 **능동적으로 알려주고 대화**하는 동반자

쇼핑, 예약, 건강체크, 스케줄, 코딩, 투자 등 다양한 영역에서 스스로 판단하고 행동할 수 있는 **24시간 깨어있는 개인 AI 어시스턴트**를 목표로 한다.

Moltbot(https://github.com/moltbot/moltbot) 프로젝트를 참고하여 뼈대를 구축했고, 친근한 이름으로 **마이클(Michael)**을 선택했다.

원칙: **"복잡한 것보다 뼈대를 튼튼히"**

## Project Overview

**마이클 (Michael)** is a 24/7 personal AI assistant that remembers everything and proactively helps users through Telegram messaging.

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

## Project Phases (All Complete)

- [x] Phase 1: Memory System (SQLite + FTS5)
- [x] Phase 2: Gateway Server (WebSocket)
- [x] Phase 3: Claude Code Agent (CLI integration)
- [x] Phase 4: Telegram Channel (Telegraf)
- [x] Phase 5: Scheduler (node-cron)
- [x] Phase 6: Daemon deployment (launchd for macOS)
- [x] Phase 7: Vector Search (Moltbot integration) - Semantic memory retrieval

## Code Style Notes

- TypeScript strict mode enabled
- ESNext modules (`"type": "module"` in package.json)
- File extensions required in imports: `import { X } from './x.js'`
- Prefer descriptive variable names over abbreviations
- Log important events with emoji prefixes for visual scanning
