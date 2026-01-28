# Moltbot 메모리 시스템 이식 전략

## 목표

Moltbot의 벡터 임베딩 메모리 시스템을 Michael에 이식하되, Michael의 아키텍처에 맞게 적응

## 파일 의존성 분석

### 1. 필수 핵심 파일 (반드시 이식)

```
manager.ts              (2,179 LOC) - 메인 MemoryIndexManager 클래스
├── embeddings.ts       - 임베딩 provider 추상화
│   ├── embeddings-openai.ts
│   ├── embeddings-gemini.ts
│   └── node-llama.ts   - 로컬 임베딩
├── batch-openai.ts     - OpenAI 배치 처리
├── batch-gemini.ts     - Gemini 배치 처리
├── internal.ts         - 유틸리티 함수들
├── hybrid.ts           - 하이브리드 검색 (벡터 + FTS5)
├── manager-search.ts   - 검색 로직
├── memory-schema.ts    - SQLite 스키마 정의
├── sqlite.ts           - node:sqlite 래퍼
└── sqlite-vec.ts       - sqlite-vec 확장 로딩
```

### 2. Moltbot 의존성 (제거/수정 필요)

manager.ts가 의존하는 Moltbot 특화 모듈들:

```typescript
// 제거할 import들
import { resolveAgentDir, resolveAgentWorkspaceDir } from "../agents/agent-scope.js";
import type { ResolvedMemorySearchConfig } from "../agents/memory-search.js";
import { resolveMemorySearchConfig } from "../agents/memory-search.js";
import type { MoltbotConfig } from "../config/config.js";
import { resolveSessionTranscriptsDirForAgent } from "../config/sessions/paths.js";
import { createSubsystemLogger } from "../logging/subsystem.js";
import { onSessionTranscriptUpdate } from "../sessions/transcript-events.js";
import { resolveUserPath } from "../utils.js";
```

## 이식 전략

### Phase 1: 단순 파일 복사 (의존성 무시)

모든 필수 핵심 파일을 Michael의 `src/memory/` 디렉토리로 복사:

```bash
cp -R moltbot/src/memory/*.ts michael/src/memory-new/
```

### Phase 2: Import 경로 수정

1. **내부 import 수정** (.js → .js 유지, ESM 유지)
2. **Moltbot 의존성 제거/대체**:

```typescript
// Before (Moltbot)
import { createSubsystemLogger } from "../logging/subsystem.js";
const log = createSubsystemLogger("memory");

// After (Michael)
import { log } from "../utils/logger.js";
```

### Phase 3: Michael 어댑터 작성

Moltbot의 기능을 Michael의 인터페이스로 연결:

**src/memory/adapter.ts** (새로 작성):
```typescript
import type { MemoryIndexManager } from './manager-new.js';
import type { Memory } from '../brain/memory.js';

/**
 * Michael의 기존 Memory 인터페이스를 MemoryIndexManager로 연결하는 어댑터
 */
export class MemoryAdapter implements Memory {
  private indexManager: MemoryIndexManager;

  constructor(dbPath: string, config: MemoryConfig) {
    this.indexManager = new MemoryIndexManager({
      agentId: 'michael-main',
      dataDir: path.dirname(dbPath),
      embeddingConfig: config.embedding
    });
  }

  async saveMessage(userId: string, role: string, content: string): Promise<void> {
    // MemoryIndexManager의 indexing API 호출
    await this.indexManager.indexMessage(userId, role, content);
  }

  async searchMessages(userId: string, query: string): Promise<Message[]> {
    // 벡터 + FTS5 하이브리드 검색
    const results = await this.indexManager.search(query, { userId });
    return results.map(r => this.resultToMessage(r));
  }

  // ... 기타 메서드 구현
}
```

### Phase 4: 설정 매핑

Moltbot의 설정을 Michael의 환경변수로 매핑:

**Michael .env:**
```bash
# 임베딩 Provider 선택
EMBEDDING_PROVIDER=local  # local | openai | gemini

# OpenAI (선택)
OPENAI_API_KEY=sk-...

# Gemini (선택)
GOOGLE_API_KEY=...

# Local 모델 (선택)
LOCAL_MODEL_PATH=~/.michael/models/embedding-model.gguf
```

**src/config/embedding.ts** (새로 작성):
```typescript
export interface EmbeddingConfig {
  provider: 'local' | 'openai' | 'gemini';
  model?: string;
  apiKey?: string;
  localModelPath?: string;
}

export function loadEmbeddingConfig(): EmbeddingConfig {
  const provider = process.env.EMBEDDING_PROVIDER || 'local';

  if (provider === 'local') {
    return {
      provider: 'local',
      localModelPath: process.env.LOCAL_MODEL_PATH || '~/.michael/models/embedding.gguf'
    };
  }

  if (provider === 'openai') {
    return {
      provider: 'openai',
      model: 'text-embedding-3-small',
      apiKey: process.env.OPENAI_API_KEY
    };
  }

  if (provider === 'gemini') {
    return {
      provider: 'gemini',
      model: 'text-embedding-004',
      apiKey: process.env.GOOGLE_API_KEY
    };
  }

  throw new Error(`Unknown embedding provider: ${provider}`);
}
```

## 파일 구조

### 최종 Michael 디렉토리 구조:

```
michael/
├── src/
│   ├── memory/              # 새 벡터 메모리 시스템
│   │   ├── adapter.ts       # Memory 인터페이스 어댑터
│   │   ├── manager.ts       # Moltbot MemoryIndexManager (이식)
│   │   ├── embeddings.ts    # (이식)
│   │   ├── embeddings-openai.ts
│   │   ├── embeddings-gemini.ts
│   │   ├── node-llama.ts
│   │   ├── batch-openai.ts
│   │   ├── batch-gemini.ts
│   │   ├── internal.ts
│   │   ├── hybrid.ts
│   │   ├── manager-search.ts
│   │   ├── memory-schema.ts
│   │   ├── sqlite.ts
│   │   └── sqlite-vec.ts
│   ├── brain/
│   │   └── memory.ts        # 기존 단순 Memory (Phase 4까지 유지)
│   └── config/
│       └── embedding.ts     # 임베딩 설정
```

## 수정 체크리스트

### manager.ts 수정사항:

- [ ] Import 경로 수정 (Moltbot → Michael)
- [ ] Logger 교체 (createSubsystemLogger → log)
- [ ] Config 타입 단순화 (MoltbotConfig → MemoryConfig)
- [ ] Agent scope 제거 (단일 사용자 가정)
- [ ] Session transcript 로직 단순화
- [ ] 파일 경로 리졸버 Michael 스타일로 변경

### embeddings.ts 수정사항:

- [ ] OpenAI/Gemini 클라이언트 임포트 확인
- [ ] node-llama-cpp optional 처리
- [ ] Provider 설정 Michael config로 매핑

### internal.ts 수정사항:

- [ ] 파일 시스템 유틸리티 확인
- [ ] 해시 함수 확인
- [ ] 청킹 로직 확인

### sqlite-vec.ts 수정사항:

- [ ] sqlite-vec 확장 로딩 확인
- [ ] 경로 문제 없는지 확인

## 검증 방법

### 1. 유닛 테스트

각 이식된 모듈별 테스트:

```typescript
// src/memory/manager.test.ts
test('MemoryIndexManager 초기화', async () => {
  const manager = new MemoryIndexManager({
    agentId: 'test',
    dataDir: './test-data',
    embeddingConfig: { provider: 'local' }
  });

  expect(manager).toBeDefined();
});

test('벡터 검색 작동', async () => {
  // 샘플 텍스트 인덱싱
  await manager.indexText('test.md', 'Hello world');

  // 검색
  const results = await manager.search('hello');
  expect(results.length).toBeGreaterThan(0);
});
```

### 2. 통합 테스트

Michael Agent와 통합:

```typescript
// src/agent/claude-code.test.ts
test('Agent가 벡터 메모리 사용', async () => {
  const memory = new MemoryAdapter('./test-data/memory.db', config);
  const agent = new ClaudeAgent(memory);

  // 대화 저장
  await agent.chat('test-user', '내 이름은 홍길동이야');

  // 나중에 검색
  await agent.chat('test-user', '내 이름이 뭐야?');

  // Agent가 벡터 검색으로 "홍길동" 찾아야 함
});
```

### 3. 성능 테스트

```typescript
test('1000개 메시지 인덱싱 성능', async () => {
  const start = Date.now();

  for (let i = 0; i < 1000; i++) {
    await manager.indexText(`msg-${i}.txt`, `Message ${i}`);
  }

  const elapsed = Date.now() - start;
  console.log(`1000 messages indexed in ${elapsed}ms`);

  // 로컬 모델: ~30-60초
  // OpenAI/Gemini: ~5-10초
});
```

## 주의사항

### 1. node:sqlite vs better-sqlite3

**Phase 2-3**: better-sqlite3 계속 사용 (호환성)
**Phase 4 이후**: node:sqlite로 전환 가능

manager.ts에서:
```typescript
// Moltbot (node:sqlite)
import { DatabaseSync } from "node:sqlite";

// Michael (better-sqlite3) - 임시
import Database from "better-sqlite3";
```

### 2. 로깅

Moltbot의 subsystem logger → Michael의 단순 logger:

```typescript
// Before
const log = createSubsystemLogger("memory");
log.info("indexed", { chunks: 10 });

// After
import { log } from "../utils/logger.js";
log("info", "✅ Indexed 10 chunks");
```

### 3. 파일 경로

Moltbot은 multi-agent를 지원하므로 복잡한 경로 구조:
```
~/.clawdbot/agents/<agentId>/memory/
```

Michael은 단일 사용자이므로 단순화:
```
./data/memory/
./data/embeddings/
```

### 4. Config 단순화

Moltbot: 복잡한 YAML 설정
Michael: 간단한 .env + TypeScript config

```typescript
// Moltbot
type MoltbotConfig = {
  agents: { [id: string]: AgentConfig };
  memory: { search: ResolvedMemorySearchConfig };
  // ... 수십 개 옵션
};

// Michael
type MemoryConfig = {
  provider: 'local' | 'openai' | 'gemini';
  model?: string;
  apiKey?: string;
  localModelPath?: string;
};
```

## 다음 단계

1. ✅ Task #1: 의존성 분석 완료
2. 🔄 Task #2: 파일 이식 (현재)
   - [ ] 파일 복사
   - [ ] Import 경로 수정
   - [ ] Moltbot 의존성 제거
   - [ ] Michael 어댑터 작성
3. ⏳ Task #3: 스키마 마이그레이션
4. ⏳ Task #4: Memory 클래스 교체
5. ⏳ Task #5: Agent 통합

## 참고 자료

- Moltbot 소스: `/Users/ldm/work/workspace/ai_agentic/opencode-demo/moltbot/src/memory/`
- Michael 현재 Memory: `src/brain/memory.ts`
- sqlite-vec 문서: https://github.com/asg017/sqlite-vec
- node-llama-cpp 문서: https://github.com/withcatai/node-llama-cpp
