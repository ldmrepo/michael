# SQLite 스키마 마이그레이션 계획

## 현재 상황

### Michael 기존 스키마 (memory.ts)

```sql
-- 사용자 관리
CREATE TABLE users (
  id TEXT PRIMARY KEY,
  telegram_chat_id TEXT UNIQUE,
  created_at INTEGER NOT NULL
);

-- 메시지 저장
CREATE TABLE messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
  content TEXT NOT NULL,
  timestamp INTEGER NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 사용자 Fact (중요 정보)
CREATE TABLE facts (
  user_id TEXT NOT NULL,
  key TEXT NOT NULL,
  value TEXT NOT NULL,
  updated_at INTEGER NOT NULL,
  PRIMARY KEY (user_id, key),
  FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 스케줄 관리
CREATE TABLE schedules (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  cron_expression TEXT NOT NULL,
  message TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  created_at INTEGER NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

-- FTS5 전문 검색 (키워드 검색만)
CREATE VIRTUAL TABLE messages_fts USING fts5(
  content,
  content='messages',
  content_rowid='id'
);
```

**특징:**
- 메시지 단위 저장
- 단순한 FTS5 키워드 검색
- **벡터 임베딩 없음** ❌
- 사용자별 관리 (multi-user 지원)

### Moltbot 스키마 (MemoryIndexManager)

```sql
-- 시스템 메타데이터
CREATE TABLE meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

-- 파일 추적 (메모리 파일 or 세션 파일)
CREATE TABLE files (
  path TEXT PRIMARY KEY,
  source TEXT NOT NULL DEFAULT 'memory',  -- 'memory' or 'sessions'
  hash TEXT NOT NULL,
  mtime INTEGER NOT NULL,
  size INTEGER NOT NULL
);

-- 청킹된 텍스트 + 임베딩
CREATE TABLE chunks (
  id TEXT PRIMARY KEY,
  path TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'memory',
  start_line INTEGER NOT NULL,
  end_line INTEGER NOT NULL,
  hash TEXT NOT NULL,
  model TEXT NOT NULL,  -- 임베딩 모델명
  text TEXT NOT NULL,
  embedding TEXT NOT NULL,  -- JSON 배열 (벡터)
  updated_at INTEGER NOT NULL
);
CREATE INDEX idx_chunks_path ON chunks(path);
CREATE INDEX idx_chunks_source ON chunks(source);

-- 임베딩 캐시 (중복 계산 방지)
CREATE TABLE embedding_cache (
  provider TEXT NOT NULL,  -- 'openai', 'gemini', 'local'
  model TEXT NOT NULL,
  provider_key TEXT NOT NULL,
  hash TEXT NOT NULL,
  embedding TEXT NOT NULL,  -- JSON 배열
  dims INTEGER,
  updated_at INTEGER NOT NULL,
  PRIMARY KEY (provider, model, provider_key, hash)
);
CREATE INDEX idx_embedding_cache_updated_at ON embedding_cache(updated_at);

-- FTS5 키워드 검색 (하이브리드 검색용)
CREATE VIRTUAL TABLE memory_fts USING fts5(
  text,
  id UNINDEXED,
  path UNINDEXED,
  source UNINDEXED,
  model UNINDEXED,
  start_line UNINDEXED,
  end_line UNINDEXED
);

-- sqlite-vec 벡터 테이블 (동적 생성)
CREATE VIRTUAL TABLE vec_chunks USING vec0(
  id TEXT PRIMARY KEY,
  embedding FLOAT[768]  -- 차원은 모델에 따라 다름
);
```

**특징:**
- 파일 기반 chunking
- **벡터 임베딩 + 하이브리드 검색** ✅
- 임베딩 캐시로 성능 최적화
- 파일 단위 관리 (사용자 개념 없음)

---

## 두 시스템의 차이점

| 항목 | Michael (기존) | Moltbot (목표) |
|------|---------------|----------------|
| **저장 단위** | 메시지 (row) | 파일 → 청크 (chunks) |
| **검색 방식** | FTS5 키워드만 | 벡터 + FTS5 하이브리드 |
| **사용자 관리** | users, facts, schedules | 없음 (파일 기반) |
| **임베딩** | ❌ 없음 | ✅ 벡터 임베딩 저장 |
| **메모리 소스** | messages 테이블 | 파일 (MEMORY.md, memory/*.md) |
| **캐싱** | 없음 | embedding_cache 테이블 |

---

## 마이그레이션 전략: 하이브리드 접근 (Option A) ✅

### 기본 원칙

**"기존 Michael 기능 유지 + Moltbot 검색 엔진 추가"**

1. ✅ **유지**: `users`, `facts`, `schedules` - Michael 고유 기능
2. ✅ **유지**: `messages` - 대화 히스토리 (원본 데이터)
3. ✅ **추가**: `files`, `chunks`, `embedding_cache` - 벡터 검색용
4. ✅ **추가**: `memory_fts`, `vec_chunks` - 하이브리드 검색
5. ⚠️ **변경**: `messages_fts` → 제거하고 새로운 검색 사용

### 데이터베이스 통합

**단일 DB 파일: `data/memory.db`**

```
memory.db
├── [Michael 고유]
│   ├── users
│   ├── messages
│   ├── facts
│   └── schedules
│
└── [Moltbot 검색 엔진]
    ├── meta
    ├── files
    ├── chunks
    ├── embedding_cache
    ├── memory_fts (FTS5)
    └── vec_chunks (sqlite-vec)
```

---

## 마이그레이션 단계

### Phase 1: 스키마 확장 (비파괴적)

**목표**: 기존 테이블 유지하면서 새 테이블 추가

```sql
-- 1. Moltbot 테이블 추가
CREATE TABLE IF NOT EXISTS meta (...);
CREATE TABLE IF NOT EXISTS files (...);
CREATE TABLE IF NOT EXISTS chunks (...);
CREATE TABLE IF NOT EXISTS embedding_cache (...);
CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(...);

-- 2. sqlite-vec 로드 및 벡터 테이블 생성
-- (MemoryIndexManager.ensureVectorTable()에서 처리)
```

**검증:**
```bash
sqlite3 data/memory.db ".tables"
# 출력:
# users  messages  facts  schedules  messages_fts
# meta  files  chunks  embedding_cache  memory_fts  vec_chunks
```

### Phase 2: 메시지 인덱싱 어댑터 구현

**목표**: `messages` 테이블을 가상의 메모리 파일로 취급

**방법:**
1. `MemoryIndexManager.sync()` 호출 시
2. `messages` 테이블을 읽어서
3. 사용자별로 가상 파일 생성: `memory:user-{userId}.jsonl`
4. `chunks` 테이블에 임베딩과 함께 저장

**예시 변환:**

```typescript
// messages 테이블
{
  id: 1,
  user_id: "user123",
  role: "user",
  content: "내일 회의 준비해줘",
  timestamp: 1234567890
}

// ↓ 변환 ↓

// files 테이블
{
  path: "memory:user-user123.jsonl",
  source: "memory",
  hash: "abc123...",
  mtime: 1234567890,
  size: 1024
}

// chunks 테이블
{
  id: "user123:msg:1",
  path: "memory:user-user123.jsonl",
  source: "memory",
  start_line: 1,
  end_line: 1,
  text: "[user] 내일 회의 준비해줘",
  embedding: "[0.123, -0.456, ...]",  // 768차원 벡터
  model: "text-embedding-3-small",
  updated_at: 1234567890
}
```

### Phase 3: 검색 API 통합

**목표**: Memory 클래스에 벡터 검색 추가

```typescript
// src/brain/memory.ts
export class Memory {
  private indexManager: MemoryIndexManager | null = null;

  async initializeVectorSearch(config: MichaelMemoryConfig) {
    this.indexManager = await MemoryIndexManager.get({
      cfg: config,
      dataDir: path.dirname(this.dbPath)
    });
  }

  // 기존 FTS5 검색 (하위 호환)
  async searchMessages(userId: string, query: string): Promise<Message[]> {
    // 기존 코드 유지
  }

  // 새로운 벡터 + 하이브리드 검색
  async searchMessagesVector(
    userId: string,
    query: string,
    options?: {
      maxResults?: number;
      minScore?: number;
      hybrid?: boolean;
    }
  ): Promise<Array<Message & { score: number }>> {
    if (!this.indexManager) {
      throw new Error("Vector search not initialized. Call initializeVectorSearch() first.");
    }

    // MemoryIndexManager로 검색
    const results = await this.indexManager.search({
      query,
      vectorWeight: 0.7,
      textWeight: 0.3,
      ...options
    });

    // chunks → messages 변환
    const messageIds = results
      .map(r => r.id.match(/user123:msg:(\d+)/)?.[1])
      .filter(Boolean);

    // messages 테이블에서 원본 조회
    const stmt = this.db.prepare(`
      SELECT id, user_id as userId, role, content, timestamp
      FROM messages
      WHERE user_id = ? AND id IN (${messageIds.join(',')})
    `);

    return stmt.all(userId).map((msg, i) => ({
      ...msg,
      score: results[i].vectorScore
    }));
  }
}
```

### Phase 4: Claude Agent 통합

**목표**: Agent가 벡터 검색 사용

```typescript
// src/agent/claude-code.ts
class ClaudeCodeAgent {
  async chat(userId: string, message: string): Promise<string> {
    // 1. 벡터 검색으로 관련 컨텍스트 로드
    const relatedMessages = await this.memory.searchMessagesVector(
      userId,
      message,
      { maxResults: 5, hybrid: true }
    );

    // 2. 시스템 프롬프트 구성
    const systemPrompt = this.buildSystemPrompt({
      facts: await this.memory.getAllFacts(userId),
      relatedContext: relatedMessages  // 벡터 검색 결과
    });

    // 3. Claude 호출 (기존과 동일)
    // ...
  }
}
```

---

## 마이그레이션 스크립트

### 자동 마이그레이션

**파일**: `src/brain/migration.ts`

```typescript
import { Memory } from './memory.js';
import { MemoryIndexManager } from '../memory-new/manager.js';
import { loadMemoryConfig } from '../memory-new/config.js';

export async function migrateToVectorSearch(dataDir: string): Promise<void> {
  console.log('🔄 Starting vector search migration...');

  // 1. 기존 Memory 열기
  const memory = new Memory(`${dataDir}/memory.db`);

  // 2. MemoryIndexManager 초기화 (스키마 자동 생성)
  const config = loadMemoryConfig(dataDir);
  const indexManager = await MemoryIndexManager.get({
    cfg: config,
    dataDir
  });

  if (!indexManager) {
    throw new Error('Failed to initialize MemoryIndexManager');
  }

  console.log('✅ Schema extended with vector tables');

  // 3. 기존 messages를 chunks로 인덱싱
  // (MemoryIndexManager.sync()가 자동으로 처리)
  await indexManager.sync({ force: true });

  console.log('✅ Messages indexed with embeddings');

  // 4. 검증
  const status = await indexManager.status();
  console.log('📊 Migration complete:', {
    totalChunks: status.chunks.count,
    vectorEnabled: status.vector.enabled,
    ftsEnabled: status.fts.enabled
  });

  await indexManager.close();
  memory.close();
}
```

**실행:**
```bash
pnpm tsx src/brain/migration.ts
```

---

## 검증 체크리스트

### Schema 검증

```sql
-- 1. 모든 테이블 존재 확인
SELECT name FROM sqlite_master WHERE type='table';

-- 2. chunks 테이블 샘플 확인
SELECT id, path, substr(text, 1, 50), length(embedding)
FROM chunks LIMIT 5;

-- 3. 임베딩 캐시 확인
SELECT provider, model, COUNT(*) as cached_embeddings
FROM embedding_cache
GROUP BY provider, model;

-- 4. 벡터 테이블 확인 (sqlite-vec)
SELECT COUNT(*) FROM vec_chunks;
```

### 검색 성능 비교

```typescript
// 기존 FTS5 검색
const start1 = Date.now();
const ftsResults = await memory.searchMessages(userId, "회의 준비");
const time1 = Date.now() - start1;

// 새로운 벡터 검색
const start2 = Date.now();
const vectorResults = await memory.searchMessagesVector(userId, "회의 준비");
const time2 = Date.now() - start2;

console.log('FTS5:', ftsResults.length, 'results in', time1, 'ms');
console.log('Vector:', vectorResults.length, 'results in', time2, 'ms');
```

**예상 결과:**
- FTS5: 정확한 키워드 매칭 ("회의", "준비")
- Vector: 의미적 유사도 ("미팅 세팅", "회의실 예약" 등도 검색)

---

## 롤백 계획

### 문제 발생 시 롤백 방법

**Option 1: 테이블 삭제 (벡터 기능만 제거)**
```sql
DROP TABLE IF EXISTS meta;
DROP TABLE IF EXISTS files;
DROP TABLE IF EXISTS chunks;
DROP TABLE IF EXISTS embedding_cache;
DROP TABLE IF EXISTS memory_fts;
DROP TABLE IF EXISTS vec_chunks;
```

**Option 2: 백업에서 복구**
```bash
# 마이그레이션 전 백업
cp data/memory.db data/memory.db.backup

# 롤백
cp data/memory.db.backup data/memory.db
```

**중요:** `users`, `messages`, `facts`, `schedules` 테이블은 영향받지 않음!

---

## 타임라인

### Task #3: 스키마 마이그레이션 설계 (현재)
- [x] 스키마 분석
- [x] 마이그레이션 전략 수립
- [x] 계획 문서 작성

### Task #4: Memory 클래스 확장 (다음)
- [ ] `initializeVectorSearch()` 구현
- [ ] `searchMessagesVector()` 구현
- [ ] messages → chunks 어댑터 구현
- [ ] 마이그레이션 스크립트 작성

### Task #5: Claude Agent 통합
- [ ] 벡터 검색 API 통합
- [ ] 시스템 프롬프트 개선
- [ ] 컨텍스트 로딩 로직 변경

### Task #6: 테스트
- [ ] 스키마 마이그레이션 테스트
- [ ] 검색 정확도 테스트
- [ ] 성능 벤치마크

---

## 결론

**채택 전략: 하이브리드 접근 (Option A)**

### 장점
1. ✅ **비파괴적**: 기존 데이터 그대로 유지
2. ✅ **점진적**: 단계별 마이그레이션 가능
3. ✅ **안전**: 문제 시 쉽게 롤백
4. ✅ **하위 호환**: 기존 API 유지

### 단점
1. ⚠️ **복잡도 증가**: 두 시스템 관리
2. ⚠️ **중복 저장**: messages + chunks

### 향후 최적화 (Optional)
- messages → chunks 완전 전환 (Task #10 이후)
- 실시간 임베딩 생성 (메시지 저장 시)
- 임베딩 모델 업그레이드 지원

**다음 단계**: Task #4 - Memory 클래스 확장 시작
