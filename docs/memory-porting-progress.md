# Moltbot 메모리 시스템 이식 진행 상황

## Task #2: Moltbot 메모리 핵심 파일 이식 - IN PROGRESS

**시작 시간**: 2026-01-29 00:24
**현재 상태**: 기본 유틸리티 파일 완료, 임베딩 파일 진행 중

---

## 복사된 파일 (13개)

```
src/memory-new/
├── batch-gemini.ts          (13KB)  ⏳ 검토 필요
├── batch-openai.ts          (12KB)  ⏳ 검토 필요
├── embeddings.ts            (7.3KB) ✅ Import 수정 완료
├── embeddings-gemini.ts     (5.1KB) ⏳ 검토 필요
├── embeddings-openai.ts     (2.7KB) ⏳ 검토 필요
├── hybrid.ts                (2.5KB) ✅ 완료 (의존성 없음)
├── internal.ts              (5.4KB) ✅ 완료 (의존성 없음)
├── manager.ts               (71KB)  ⏳ 가장 큰 파일, 많은 의존성
├── manager-search.ts        (5.0KB) ✅ Import 수정 완료
├── memory-schema.ts         (2.8KB) ✅ 완료 (의존성 없음)
├── node-llama.ts            (82B)   ⏳ 검토 필요
├── sqlite.ts                (332B)  ✅ Import 수정 완료
└── sqlite-vec.ts            (789B)  ✅ 완료 (의존성 없음)
```

---

## 새로 작성된 Michael 파일 (2개)

### 1. `src/memory-new/utils.ts`
**목적**: UTF-16 safe 문자열 처리 (emoji, surrogate pair 지원)
**내용**:
- `isHighSurrogate()`
- `isLowSurrogate()`
- `sliceUtf16Safe()`
- `truncateUtf16Safe()`

**사용처**: manager-search.ts (snippet 자르기)

### 2. `src/memory-new/config.ts`
**목적**: Michael의 간소화된 메모리 설정
**내용**:
- `MichaelMemoryConfig` 타입 (Moltbot의 MoltbotConfig 대체)
- `MemoryEmbeddingConfig` 타입
- `MemorySearchConfig` 타입
- `resolveUserPath()` 함수
- `loadMemoryConfig()` 함수 (환경변수에서 설정 로드)

**사용처**: embeddings.ts, manager.ts

---

## 파일별 수정 내역

### ✅ sqlite.ts
**변경사항**:
```diff
- import { installProcessWarningFilter } from "../infra/warnings.js";
- installProcessWarningFilter();
```
**이유**: Moltbot의 infra 모듈 의존성 제거 (필수 아님)

### ✅ manager-search.ts
**변경사항**:
```diff
- import { truncateUtf16Safe } from "../utils.js";
+ import { truncateUtf16Safe } from "./utils.js";
```
**이유**: Moltbot utils 대신 로컬 utils 사용

### ✅ embeddings.ts (부분 완료)
**변경사항**:
```diff
- import type { MoltbotConfig } from "../config/config.js";
- import { resolveUserPath } from "../utils.js";
+ import type { MichaelMemoryConfig } from "./config.js";
+ import { resolveUserPath } from "./config.js";

- config: MoltbotConfig;
+ config: MichaelMemoryConfig;
```
**이유**: Michael의 간소화된 설정 사용

---

## 남은 작업

### 우선순위 1: 임베딩 Provider 파일들

1. **embeddings-openai.ts** (2.7KB)
   - OpenAI API 호출
   - 확인 필요: OpenAI SDK import, Moltbot 의존성

2. **embeddings-gemini.ts** (5.1KB)
   - Gemini API 호출
   - 확인 필요: Gemini SDK import, Moltbot 의존성

3. **node-llama.ts** (82B)
   - node-llama-cpp lazy import
   - 간단한 파일, 빠르게 확인 가능

### 우선순위 2: 배치 처리 파일들

4. **batch-openai.ts** (12KB)
   - OpenAI 배치 임베딩 최적화
   - 확인 필요: API calls, Moltbot logger

5. **batch-gemini.ts** (13KB)
   - Gemini 배치 임베딩 최적화
   - 확인 필요: API calls, Moltbot logger

### 우선순위 3: 메인 Manager 파일

6. **manager.ts** (71KB) ⚠️ 가장 복잡
   - MemoryIndexManager 클래스 (2,179 LOC)
   - 많은 Moltbot 의존성:
     ```typescript
     import { resolveAgentDir } from "../agents/agent-scope.js";
     import { resolveMemorySearchConfig } from "../agents/memory-search.js";
     import { resolveSessionTranscriptsDirForAgent } from "../config/sessions/paths.js";
     import { createSubsystemLogger } from "../logging/subsystem.js";
     import { onSessionTranscriptUpdate } from "../sessions/transcript-events.js";
     import { resolveUserPath } from "../utils.js";
     ```
   - 제거/대체 필요한 기능:
     - Agent scope (multi-agent 지원) → 단일 사용자로 단순화
     - Session transcript 감시 → Michael은 메시지만 저장
     - Subsystem logger → Michael의 단순 logger

---

## 설계 결정 사항

### 1. node:sqlite vs better-sqlite3

**현재**: Moltbot은 node:sqlite (Node 22+ 내장) 사용
**Michael**: Phase 2-3는 better-sqlite3 유지, Phase 4 이후 node:sqlite 전환

**이유**:
- better-sqlite3는 이미 설치되어 있고 동작함
- 점진적 마이그레이션을 위해 먼저 better-sqlite3로 테스트
- 안정화 후 node:sqlite로 전환

**TODO**: manager.ts에서 DatabaseSync 타입 처리 방법 결정 필요

### 2. 로거 통합

**Moltbot**: subsystem logger (structured logging)
```typescript
const log = createSubsystemLogger("memory");
log.info("indexed", { chunks: 10, path: "file.md" });
```

**Michael**: 단순 logger (string logging)
```typescript
import { log } from "../utils/logger.js";
log("info", "✅ Indexed 10 chunks in file.md");
```

**변경 전략**:
- manager.ts의 모든 `log.*` 호출을 Michael 스타일로 변환
- 구조화된 데이터는 문자열로 직렬화

### 3. 설정 단순화

**Moltbot**: 복잡한 YAML 설정 + 런타임 리졸버
```yaml
agents:
  agent-1:
    memory:
      search:
        embedding:
          provider: openai
          model: text-embedding-3-small
```

**Michael**: 환경변수 + 간단한 TypeScript 설정
```bash
EMBEDDING_PROVIDER=local
LOCAL_MODEL_PATH=~/.michael/models/embedding.gguf
```

### 4. Agent Scope 제거

**Moltbot**: 멀티 에이전트 지원, 각 agent마다 별도 memory
```
~/.clawdbot/agents/agent-1/memory/
~/.clawdbot/agents/agent-2/memory/
```

**Michael**: 단일 사용자, 하나의 memory
```
./data/memory/
```

**변경 사항**:
- `resolveAgentDir()` 제거 → `dataDir` 직접 사용
- `agentId` 파라미터 제거 → 고정값 "michael-main" 사용

---

## 다음 단계

### 즉시 수행 (Task #2 완료)

1. embeddings-openai.ts 확인 및 수정
2. embeddings-gemini.ts 확인 및 수정
3. node-llama.ts 확인 (아마 수정 불필요)
4. batch-openai.ts 확인 및 수정
5. batch-gemini.ts 확인 및 수정
6. **manager.ts 대대적 수정**:
   - Import 경로 수정
   - Moltbot 의존성 제거
   - Logger 호출 변환
   - Agent scope 로직 단순화
   - Session transcript 로직 제거/단순화

### Task #3 이후

- SQLite 스키마 마이그레이션 (기존 memory.db → 새 벡터 스키마)
- Memory 인터페이스 어댑터 작성
- Agent 통합
- 테스트 작성

---

## 주요 도전 과제

### 1. manager.ts 복잡도
- **2,179 LOC** (가장 큰 파일)
- 많은 Moltbot 특화 기능
- 파일 워칭, 세션 동기화, 배치 임베딩 등

**해결 방안**:
- 단계별로 섹션 나눠서 수정
- 불필요한 기능은 주석 처리 후 나중에 구현
- 핵심 기능(인덱싱, 검색)만 우선 작동시키기

### 2. better-sqlite3 vs node:sqlite 타입 차이
- Moltbot: `DatabaseSync` from "node:sqlite"
- Michael (현재): `Database` from "better-sqlite3"

**해결 방안**:
- 타입 어댑터 작성 또는
- 공통 인터페이스 정의

### 3. 임베딩 Provider 테스트
- OpenAI/Gemini: API 키 필요
- Local: 모델 다운로드 필요 (~500MB-2GB)

**해결 방안**:
- Mock provider로 먼저 테스트
- 실제 API는 수동 테스트

---

## 진행률

- [x] 의존성 분석 (Task #1)
- [x] 파일 복사 (13개 파일)
- [x] 단순 유틸리티 파일 수정 (5개)
- [x] Michael config 파일 작성
- [ ] 임베딩 provider 파일 수정 (3개)
- [ ] 배치 처리 파일 수정 (2개)
- [ ] manager.ts 대대적 수정 (71KB)
- [ ] 컴파일 확인
- [ ] Task #2 완료

**예상 남은 시간**: 2-3시간 (manager.ts가 대부분)
