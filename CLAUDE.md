# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

Uses **better-sqlite3** (synchronous API) with these tables:
- `users`: User registry
- `messages`: Conversation history
- `facts`: Key-value facts about users
- `schedules`: Cron-based scheduled tasks
- `messages_fts`: FTS5 virtual table for full-text search

**Critical ordering bug fix**: When querying messages, ALWAYS use:
```typescript
ORDER BY timestamp DESC, id DESC  // id prevents same-timestamp collisions
```

All database operations are synchronous - no async/await needed for Memory methods.

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
```

**DO NOT SET `ANTHROPIC_API_KEY`** - this project uses Claude Code CLI, not the SDK.

## Testing Strategy

### Test Isolation
Each test file creates isolated instances:
- Random ports for Gateway tests (to avoid EADDRINUSE)
- In-memory SQLite databases (`:memory:`)
- Separate data directories

### Key Test Files
- `memory.test.ts`: 16 tests covering CRUD, FTS5 search, edge cases
- `gateway.test.ts`: 8 tests for WebSocket routing and error handling
- `cron.test.ts`: 9 tests for schedule management and cron validation

### Running Individual Tests
```bash
pnpm vitest run src/brain/memory.test.ts
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

## Code Style Notes

- TypeScript strict mode enabled
- ESNext modules (`"type": "module"` in package.json)
- File extensions required in imports: `import { X } from './x.js'`
- Prefer descriptive variable names over abbreviations
- Log important events with emoji prefixes for visual scanning
