# Michael AI Assistant - Work Log

이 문서는 프로젝트의 작업 이력을 시간순으로 기록합니다.
이후 작업자는 이 문서를 참조하여 현재 상태를 파악하고 작업을 이어갈 수 있습니다.

---

## Phase 0: 프로젝트 시작 동기

> "기존 AI는 요청할 때만 반응한다. 나는 기억하고, 필요할 때 스스로 행동하고 조언해주는 AI를 원한다.
> Telegram이나 Slack 같은 채널을 통해 능동적으로 알려주고 대화하고 싶다.
> 쇼핑, 예약, 건강체크, 스케줄, 코딩, 투자 등 스스로 행동하는 24시간 깨어있는 동반자."

Moltbot(https://github.com/moltbot/moltbot) 프로젝트를 참고 대상으로 삼았고, "복잡한 것보다 뼈대를 튼튼히"를 원칙으로 시작. 친근한 이름으로 **마이클(Michael)**을 선택.

---

## Phase 1~6: 초기 구현 (commit: 0327561)

초기 커밋으로 MVP 전체 구조가 구현되었습니다.

### 구현된 컴포넌트

| 컴포넌트 | 파일 | 역할 |
|----------|------|------|
| Memory | `src/brain/memory.ts` | SQLite(better-sqlite3) 기반 영구 저장소 |
| Gateway | `src/core/gateway.ts` | WebSocket 기반 중앙 메시지 허브 (port 18789) |
| Claude Agent | `src/agent/claude-code.ts` | Claude CLI(`claude -p`) 서브프로세스로 AI 대화 |
| Telegram | `src/channels/telegram.ts` | Telegraf 봇, Gateway WebSocket 클라이언트 |
| Scheduler | `src/scheduler/cron.ts` | node-cron 기반 반복 알림 |
| Daemon | `scripts/install-daemon.sh` | macOS launchd 서비스 등록 |

### 테스트

- `memory.test.ts` (26 tests)
- `memory.integration.test.ts` (12 tests, 7 skipped)
- `gateway.test.ts` (8 tests)
- `cron.test.ts` (9 tests)

---

## Phase 7: Moltbot 벡터 검색 통합

Moltbot 프로젝트의 벡터 임베딩 검색 시스템을 Michael에 통합했습니다.

### 통합된 파일 (`src/memory-new/`)

| 파일 | 역할 |
|------|------|
| `manager.ts` | MemoryIndexManager — 벡터 인덱싱 핵심 |
| `config.ts` | 임베딩 설정 (provider, model, chunking 등) |
| `embeddings.ts` | 임베딩 프로바이더 팩토리 |
| `batch-openai.ts` | OpenAI Batch API 임베딩 |
| `batch-gemini.ts` | Gemini Batch API 임베딩 |

### Memory API 확장 (`src/brain/memory.ts`)

```typescript
await memory.initializeVectorSearch(config);      // 벡터 검색 엔진 초기화
await memory.syncMessagesToChunks(userId);         // 메시지 → 벡터 인덱싱
await memory.searchMessagesVector(userId, query);  // 시맨틱 검색
```

### DB 파일 분리

| DB | 경로 | 라이브러리 | 용도 |
|----|------|-----------|------|
| Main | `data/memory.db` | better-sqlite3 | users, messages, facts, schedules |
| Vector | `data/memory-index.db` | node:sqlite + sqlite-vec | embeddings, chunks, vec_chunks |

---

## 코드 리뷰 이슈 수정 (Task #19~#30)

벡터 검색 통합 후 코드 리뷰에서 발견된 12개 이슈를 모두 수정했습니다.

### 수정 목록

| # | 파일 | 내용 |
|---|------|------|
| 19 | `claude-code.ts` | `any[]` → `Message[]`, `VectorSearchResult` 타입 도입 |
| 20 | `memory.ts` | 벡터 검색 초기화 전 호출 시 에러 메시지 개선 |
| 21 | `config.ts` | `EMBEDDING_PROVIDER` 환경변수 유효성 검사 추가 |
| 22 | `memory.ts` | `syncMessagesToChunks` race condition 방지 (`isSyncing` 플래그) |
| 23 | `claude-code.ts` | `any[]` 잔여 타입 제거 |
| 24 | `manager.ts` | 하드코딩된 `agentId: "michael"` → 생성자 파라미터로 변경 |
| 25 | `manager.ts` | `INDEX_CACHE` 메모리 누수 방지 (`pruneIndexCache()`) |
| 26 | `memory.ts` | 에러 로그에 컨텍스트 추가 (userId, query, provider) |
| 27 | `claude-code.ts` | 벡터 검색 10초 타임아웃 (`Promise.race`) |
| 28 | `config.ts` | 모든 설정 기본값에 주석 추가 |
| 29 | `manager.ts` | 주석 처리된 session 코드 블록 제거 |
| 30 | `CLAUDE.md` | DB 파일 분리 문서화 |

---

## 벡터 검색 startup 통합 누락 수정

### 문제

`memory.initializeVectorSearch()`가 존재하지만 `src/index.ts`의 `start()`에서 호출되지 않았음.

### 수정 (`src/index.ts`)

```typescript
async start(): Promise<void> {
  // 벡터 검색 초기화 (선택적 - 실패해도 계속 진행)
  try {
    const config = loadMemoryConfig(dataDir);
    await this.memory.initializeVectorSearch(config);
    await this.memory.syncMessagesToChunks();
  } catch (error) {
    log('warn', `⚠️ Vector search initialization failed: ${error}`);
  }
  // ... Gateway, Scheduler, Telegram 시작
}
```

---

## 임베딩 모델 벤치마크

3개 임베딩 모델을 한국어 시맨틱 검색으로 비교 테스트했습니다.

| 모델 | Provider | 정확도 | 인덱싱 시간 | 비용 |
|------|----------|--------|-----------|------|
| **embeddinggemma-300M** (GGUF) | local | **4/4** (37~45%) | 4.3s | 무료 |
| granite-278m-multilingual (GGUF) | local | 2/4 | ~5s | 무료 |
| text-embedding-3-small | openai | 2/4 (15~29%) | 207s | 유료 |

**결론**: 기본 로컬 모델(embeddinggemma-300M)이 한국어에 가장 적합.

### 테스트 스크립트

`scripts/vector-test.ts` — 한국어 메시지 10개 저장 → 4개 시맨틱 쿼리 검색

### 참고 사항

- `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`: GGUF 포맷이 아니어서 node-llama-cpp 호환 불가
- OpenAI Batch API: 소량 데이터에 부적합 (비동기 polling 방식, 10개에 207초)
- 로컬 모델 병렬 다운로드 시 race condition 발생 (node-llama-cpp 이슈)

---

## 스케줄러 버그 수정 (2건)

Telegram에서 "3분 후에 알려줘" 테스트 중 발견.

### 버그 1: 새 스케줄이 Scheduler에 등록되지 않음

**원인**: `claude-code.ts:processResponse()`가 `memory.saveSchedule()`만 호출하고, 실행 중인 `Scheduler`에 cron job을 등록하지 않음. Agent가 Scheduler 참조를 가지고 있지 않았음.

**수정**:
- `claude-code.ts`: `setScheduler()` 메서드 추가, `processResponse()`에서 `scheduler.addSchedule()` 호출
- `index.ts`: `this.agent.setScheduler(this.scheduler)` 연결 추가

### 버그 2: Scheduler broadcast에 chatId 누락

**원인**: `cron.ts:executeJob()`이 metadata에 `chatId`를 포함하지 않아서 TelegramChannel이 메시지를 버림.

**수정**: `cron.ts:executeJob()`의 metadata에 `chatId: Number(schedule.userId)` 추가.

---

## 스케줄 관리 기능 추가

### 1회 vs 반복 스케줄 구분

| 기능 | 마커 | 동작 |
|------|------|------|
| 반복 스케줄 | `[SCHEDULE:cron_expr:message]` | node-cron 반복 실행 |
| 1회 알림 | `[SCHEDULE_ONCE:minutes:message]` | `setTimeout` 후 자동 정리 |
| 취소 | `[CANCEL_SCHEDULE:schedule_id]` | cron job 중지 + DB 비활성화 |

### 주요 변경

- **`claude-code.ts`**: `loadContext()`에 사용자 스케줄 목록 추가, 시스템 프롬프트에 Active Schedules 섹션 + 관리 지침 추가, `processResponse()`에 `SCHEDULE_ONCE`/`CANCEL_SCHEDULE` 마커 파싱 추가
- **`cron.ts`**: `addOneTimeSchedule()` 메서드 추가 (setTimeout 기반), `oneTimeJobs` Map 관리, `stop()`에서 타이머 정리

---

## 미해결 이슈 (GitHub Issues)

### [#1 — 1회 스케줄(setTimeout) 재시작 시 유실됨](https://github.com/ldmrepo/michael/issues/1)

`addOneTimeSchedule()`이 `setTimeout`만 사용하여 프로세스 메모리에만 존재.
앱 재시작 시 등록된 1회성 알림이 모두 사라짐.

**개선 방안**: schedules 테이블에 `type`(`cron`|`once`), `execute_at` 컬럼 추가.
DB에 저장 후 `setTimeout` 등록. 기동 시 미실행 스케줄 복원.

### [#2 — 스케줄 마커 구분자(:) 충돌로 메시지 파싱 오류](https://github.com/ldmrepo/michael/issues/2)

`[SCHEDULE:0 9 * * *:오전 9시: 회의]` — 메시지에 `:`가 포함되면 regex 파싱 오류.

**개선 방안**: 구분자를 `|`로 변경하거나, 이중 콜론(`::`) 사용.

---

## 현재 상태 요약

### 작동 중인 기능
- Gateway (WebSocket, port 18789)
- Memory (SQLite + 벡터 검색)
- Claude Agent (CLI `-p` 모드)
- Telegram 봇 (양방향 대화)
- Scheduler (반복 cron + 1회 setTimeout)
- 벡터 기반 시맨틱 메모리 검색

### 환경 설정 (`.env`)
```
TELEGRAM_BOT_TOKEN=<BotFather 토큰>
GATEWAY_PORT=18789
EMBEDDING_PROVIDER=local
```

### 테스트 현황
- 48 pass, 7 skipped (integration tests는 `INTEGRATION_TESTS=true` 필요)
- TypeScript strict mode 통과

### 다음 작업 우선순위
1. GitHub Issue #1 — 1회 스케줄 DB 영속화
2. GitHub Issue #2 — 마커 구분자 충돌 수정
3. Telegram 실사용 테스트 및 안정화
