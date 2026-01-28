# Task #2: Moltbot 메모리 핵심 파일 이식 - 진행 상황

## 완료된 작업 (12/15 파일)

### ✅ 1. 유틸리티 & 스키마 파일 (100% 완료)

| 파일 | 상태 | 변경사항 |
|------|------|----------|
| `sqlite.ts` | ✅ | Moltbot warning filter 제거 |
| `sqlite-vec.ts` | ✅ | 의존성 없음 (그대로 사용) |
| `memory-schema.ts` | ✅ | 의존성 없음 (그대로 사용) |
| `hybrid.ts` | ✅ | 의존성 없음 (그대로 사용) |
| `internal.ts` | ✅ | 의존성 없음 (그대로 사용) |
| `manager-search.ts` | ✅ | `truncateUtf16Safe` import 수정 |

### ✅ 2. 새로 작성된 Michael 파일

| 파일 | 목적 | 내용 |
|------|------|------|
| `utils.ts` | UTF-16 safe 문자열 처리 | `truncateUtf16Safe()`, `sliceUtf16Safe()` |
| `config.ts` | Michael 설정 타입 | `MichaelMemoryConfig`, `loadMemoryConfig()`, `resolveUserPath()` |

### ✅ 3. 임베딩 Provider 파일 (100% 완료)

| 파일 | 상태 | 변경사항 |
|------|------|----------|
| `embeddings.ts` | ✅ | MoltbotConfig → MichaelMemoryConfig |
| `embeddings-openai.ts` | ✅ | API key resolver 단순화 |
| `embeddings-gemini.ts` | ✅ | API key resolver + logger 단순화 |
| `node-llama.ts` | ✅ | 의존성 없음 (lazy import wrapper) |

## 남은 작업 (3/15 파일)

### ⏳ 4. 배치 처리 파일 (예상: 30분)

| 파일 | 크기 | 예상 이슈 |
|------|------|-----------|
| `batch-openai.ts` | 12KB | Logger, OpenAI SDK 호출 |
| `batch-gemini.ts` | 13KB | Logger, Gemini API 호출 |

**예상 변경사항**:
- Logger 호출 제거/단순화
- Moltbot 설정 참조 제거
- API key 처리 단순화 (이미 embeddings-*.ts에서 해결됨)

### ⚠️ 5. Manager 파일 (예상: 2-3시간)

| 파일 | 크기 | 복잡도 |
|------|------|--------|
| `manager.ts` | 71KB (2,179 LOC) | ⚠️ 매우 높음 |

**확인된 Moltbot 의존성**:
```typescript
import { resolveAgentDir, resolveAgentWorkspaceDir } from "../agents/agent-scope.js";
import type { ResolvedMemorySearchConfig } from "../agents/memory-search.js";
import { resolveMemorySearchConfig } from "../agents/memory-search.js";
import type { MoltbotConfig } from "../config/config.js";
import { resolveSessionTranscriptsDirForAgent } from "../config/sessions/paths.js";
import { createSubsystemLogger } from "../logging/subsystem.js";
import { onSessionTranscriptUpdate } from "../sessions/transcript-events.js";
import { resolveUserPath } from "../utils.js";
```

**필요한 수정 (8개 영역)**:

1. **Import 경로 수정** (30분)
   - 내부 import (.js 확장자 유지)
   - Moltbot 의존성 제거

2. **Logger 교체** (20분)
   ```typescript
   // Before
   const log = createSubsystemLogger("memory");
   log.info("indexed", { chunks: 10 });

   // After
   import { log } from "../utils/logger.js";
   log("info", "✅ Indexed 10 chunks");
   ```

3. **Agent Scope 제거** (30분)
   ```typescript
   // Before: Multi-agent support
   const agentDir = resolveAgentDir(agentId);
   const workspaceDir = resolveAgentWorkspaceDir(agentId);

   // After: Single user
   const agentDir = dataDir;
   const workspaceDir = dataDir;
   ```

4. **Config 단순화** (20분)
   ```typescript
   // Before
   const config = resolveMemorySearchConfig(moltbotConfig, agentId);

   // After
   const config = options.config.memory.search;
   ```

5. **Session Transcript 로직 제거/단순화** (40분)
   - Moltbot: 세션 파일 워칭 + 자동 인덱싱
   - Michael: 메시지만 저장 (파일 워칭 불필요)

6. **파일 경로 리졸버 수정** (20분)
   ```typescript
   // Before
   const sessionDir = resolveSessionTranscriptsDirForAgent(agentId);

   // After
   // 제거 또는 단순화
   ```

7. **타입 정의 조정** (10분)
   - `MoltbotConfig` → `MichaelMemoryConfig`
   - `ResolvedMemorySearchConfig` → `MemorySearchConfig`

8. **기타 Moltbot 특화 기능** (20분)
   - Event emitter 제거/단순화
   - Agent workspace 개념 제거

**총 예상 시간**: ~3시간 (manager.ts 복잡도에 따라 변동 가능)

---

## 주요 설계 결정

### 1. API Key 관리 단순화

**Moltbot**: 복잡한 credential 시스템
- `~/.clawdbot/credentials/` 파일
- Agent별 API key 저장
- Keyring 통합

**Michael**: 환경변수 우선
- `OPENAI_API_KEY`
- `GOOGLE_API_KEY` / `GEMINI_API_KEY`
- 없으면 에러 throw

### 2. Logger 단순화

**Moltbot**: 구조화된 로깅
```typescript
log.info("indexed", {
  path: "file.md",
  chunks: 10,
  elapsed: 1234
});
```

**Michael**: 문자열 로깅
```typescript
log("info", "✅ Indexed file.md: 10 chunks (1234ms)");
```

### 3. Config 단순화

**Moltbot**:
- YAML 파일 (`~/.clawdbot/config.yaml`)
- Agent별 설정
- 수십 개 옵션

**Michael**:
- 환경변수 (`.env`)
- 단일 사용자
- 최소 옵션 (provider, model, keys)

### 4. Agent Scope 제거

**Moltbot**: Multi-agent
```
~/.clawdbot/agents/
  ├── agent-1/
  │   ├── memory/
  │   └── workspace/
  └── agent-2/
      ├── memory/
      └── workspace/
```

**Michael**: Single user
```
./data/
  ├── memory/
  ├── embeddings/
  └── models/
```

---

## 다음 단계

### 즉시 수행 (Task #2 완료)

1. **batch-openai.ts 수정** (15분)
   - Logger 제거/단순화
   - API 호출은 그대로 유지

2. **batch-gemini.ts 수정** (15분)
   - Logger 제거/단순화
   - API 호출은 그대로 유지

3. **manager.ts 대대적 수정** (2-3시간)
   - 위에 나열된 8개 영역 수정
   - 섹션별로 진행하며 테스트

4. **컴파일 확인** (10분)
   ```bash
   cd /Users/ldm/work/workspace/ai_agentic/opencode-demo/michael
   pnpm tsc --noEmit src/memory-new/*.ts
   ```

5. **Task #2 완료 체크**

### Task #3 이후

- SQLite 스키마 마이그레이션
- Memory 어댑터 작성
- Agent 통합
- 테스트 작성

---

## 진행률

```
Task #2: Moltbot 메모리 핵심 파일 이식
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
완료: ████████████████████████████████████████████████████░░░░░░░░░  12/15 (80%)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ 유틸리티 & 스키마: 6/6 (100%)
✅ 새 Michael 파일: 2/2 (100%)
✅ 임베딩 Provider: 4/4 (100%)
⏳ 배치 처리: 0/2 (0%)
⏳ Manager: 0/1 (0%)
```

---

## 예상 완료 시간

- **배치 파일**: 30분
- **manager.ts**: 2-3시간
- **컴파일 확인**: 10분
- **총**: ~3-4시간

**현재 시각**: 2026-01-29 00:24
**예상 완료**: 2026-01-29 03:00-04:00

---

## 기술적 도전 과제

### 1. Manager.ts 복잡도
- 2,179 LOC
- 많은 Moltbot 특화 로직
- 파일 워칭, 세션 동기화, 배치 임베딩

**해결 방안**:
- 단계별 섹션 분할 수정
- 불필요한 기능 주석 처리
- 핵심 기능(인덱싱, 검색)만 우선 작동

### 2. node:sqlite vs better-sqlite3
- Moltbot: `DatabaseSync` (node:sqlite)
- Michael: `Database` (better-sqlite3)

**해결 방안**:
- Phase 2-3: better-sqlite3 계속 사용
- Phase 4: node:sqlite로 전환 고려
- 타입 어댑터 필요할 수 있음

### 3. 파일 워칭 (Chokidar)
- Moltbot: 세션 파일 자동 인덱싱
- Michael: 메모리 파일만 인덱싱?

**해결 방안**:
- 일단 파일 워칭 비활성화
- 나중에 필요시 추가

---

## 성공 지표

Task #2가 완료되면:

✅ 모든 15개 파일이 Michael 구조에 맞게 수정됨
✅ Moltbot 의존성 완전히 제거됨
✅ TypeScript 컴파일 에러 없음
✅ 각 파일이 독립적으로 import 가능
✅ 문서화 완료 (이 파일!)
