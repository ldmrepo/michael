# manager.ts 모듈화 계획

## 현재 상황

**파일 크기**: 71KB, 2,178줄
**복잡도**: ⚠️ 매우 높음
**주요 클래스**: `MemoryIndexManager`

## 문제점

1. **너무 큰 단일 파일** - 유지보수 어려움
2. **많은 Moltbot 의존성** - agent scope, session files, subsystem logger
3. **복잡한 기능들이 뒤섞임** - 검색, 인덱싱, 워칭, 벡터 관리 등

## MemoryIndexManager 기능 분석

### 1. 초기화 & 설정 (Initialization)
- `constructor()` - private constructor
- `static create()` - factory method
- `openDatabase()` - SQLite 연결
- `ensureSchema()` - 테이블 생성
- Settings 로딩

### 2. 검색 (Search) ⭐ 핵심
- `search()` - 하이브리드 검색 (벡터 + FTS5)
- `searchVector()` - 벡터 검색
- `searchKeyword()` - FTS5 검색
- `mergeHybridResults()` - 결과 병합

### 3. 인덱싱 (Indexing) ⭐ 핵심
- `sync()` - 파일 동기화 및 인덱싱
- `indexMemoryFiles()` - 메모리 파일 인덱싱
- `indexSessionFiles()` - 세션 파일 인덱싱 (Michael에 불필요)
- `chunkAndEmbed()` - 텍스트 청킹 + 임베딩

### 4. 임베딩 (Embedding)
- `embedQuery()` - 단일 텍스트 임베딩
- `embedBatch()` - 배치 임베딩
- Embedding cache 관리

### 5. 벡터 테이블 (Vector Table)
- `ensureVectorTable()` - vec0 테이블 생성
- `dropVectorTable()` - 테이블 삭제
- `ensureVectorReady()` - sqlite-vec 준비 확인
- `probeVectorAvailability()` - 벡터 검색 가능 여부

### 6. 파일 워칭 (File Watching) - Michael에 선택적
- `ensureWatcher()` - Chokidar 파일 워처
- `scheduleDirty()` - 변경 감지 및 재인덱싱
- `ensureSessionListener()` - 세션 파일 리스너 (불필요)

### 7. 상태 & 프로브 (Status)
- `status()` - 인덱스 상태 반환
- `probeEmbeddingAvailability()` - 임베딩 가능 여부
- `warmSession()` - 세션 워밍업 (불필요)

### 8. 라이프사이클 (Lifecycle)
- `close()` - 리소스 정리
- `readFile()` - 메모리 파일 읽기

## Michael용 단순화 전략

### 제거할 기능 (Moltbot 특화)

1. **Agent Scope** ❌
   - Multi-agent 지원 불필요
   - `agentId`, `agentDir`, `resolveAgentDir()` 제거

2. **Session File 워칭** ❌
   - Moltbot: 세션 파일 자동 인덱싱
   - Michael: 메시지만 DB에 저장
   - `ensureSessionListener()`, `indexSessionFiles()` 제거

3. **Session Warmup** ❌
   - `warmSession()` 제거

4. **Subsystem Logger** ❌
   - `createSubsystemLogger()` → 단순 `log()` 함수

### 유지할 핵심 기능 ⭐

1. **하이브리드 검색** (벡터 + FTS5)
2. **파일 인덱싱** (메모리 파일만)
3. **임베딩 생성 & 캐싱**
4. **벡터 테이블 관리**
5. **Status & Probe**

## 모듈 분해 계획

### 방안 A: 기능별 모듈 (추천) ✅

```
src/memory-new/
├── manager/
│   ├── index.ts              # MemoryIndexManager (메인 클래스)
│   ├── search.ts             # 검색 로직
│   ├── indexing.ts           # 파일 인덱싱 로직
│   ├── embedding.ts          # 임베딩 처리
│   ├── vector-table.ts       # 벡터 테이블 관리
│   ├── watch.ts              # 파일 워칭 (선택적)
│   └── types.ts              # 공통 타입
```

**장점**:
- 기능별로 명확히 분리
- 각 모듈 독립적 테스트 가능
- 유지보수 용이

**단점**:
- 파일 수 증가
- Import 관계 복잡해질 수 있음

### 방안 B: 레이어별 모듈

```
src/memory-new/
├── manager.ts                # MemoryIndexManager (단순화)
├── manager-search.ts         # 검색 (이미 존재)
├── manager-indexing.ts       # 인덱싱
├── manager-embedding.ts      # 임베딩
```

**장점**:
- 구조 단순
- Moltbot과 유사한 구조

**단점**:
- 여전히 파일이 클 수 있음

### 방안 C: 점진적 단순화 (현실적) ⭐

**Phase 1**: manager.ts 그대로 이식하되 Moltbot 의존성만 제거
**Phase 2**: 사용하면서 필요에 따라 모듈 분리
**Phase 3**: 안정화 후 리팩토링

**장점**:
- 빠르게 작동하는 버전 확보
- 실제 사용 패턴 파악 후 최적화

**단점**:
- 초기에는 여전히 큰 파일

## 권장 접근법: **방안 C (점진적)**

### Step 1: 최소 수정으로 작동 (Task #2 완료 목표)

1. **Import 경로 수정**
   ```typescript
   // Before
   import { resolveAgentDir } from "../agents/agent-scope.js";

   // After
   // 제거 또는 dataDir 직접 사용
   ```

2. **Logger 교체**
   ```typescript
   // Before
   const log = createSubsystemLogger("memory");
   log.info("indexed", { chunks: 10 });

   // After
   import { log } from "../../utils/logger.js";
   log("info", "✅ Indexed 10 chunks");
   ```

3. **Config 단순화**
   ```typescript
   // Before
   const config = resolveMemorySearchConfig(moltbotConfig, agentId);

   // After
   const config = options.config.memory.search;
   ```

4. **Agent Scope 제거**
   ```typescript
   // Before
   const workspaceDir = resolveAgentWorkspaceDir(agentId);
   const sessionDir = resolveSessionTranscriptsDirForAgent(agentId);

   // After
   const workspaceDir = this.dataDir;
   // sessionDir 제거 (불필요)
   ```

5. **Session File 로직 제거**
   ```typescript
   // ensureSessionListener() 전체 제거
   // indexSessionFiles() 제거
   // sessionsDirty, sessionPendingFiles 등 제거
   ```

### Step 2: 주석 처리로 복잡도 줄이기

불필요한 기능들을 완전히 삭제하지 말고 주석 처리:

```typescript
// // Michael: Session file watching not needed
// private ensureSessionListener() {
//   ...
// }
```

**이유**:
- 나중에 필요할 수 있음
- Moltbot 코드 참고 가능

### Step 3: 타입 단순화

```typescript
// Before
type MemorySource = "memory" | "sessions";

// After (Michael)
type MemorySource = "memory"; // sessions 제거
```

## 수정 체크리스트

### 필수 수정 (Step 1)

- [ ] Import 경로 수정 (Moltbot → Michael)
- [ ] Logger 교체
- [ ] Config 타입 변경 (MoltbotConfig → MichaelMemoryConfig)
- [ ] Agent scope 제거
- [ ] Session file 로직 제거/주석
- [ ] `resolveUserPath` import 수정

### 선택적 수정 (나중에)

- [ ] 파일 워칭 로직 단순화
- [ ] 메서드 분리 (manager/search.ts 등)
- [ ] 에러 메시지 Michael 스타일로
- [ ] Status 출력 형식 변경

## 예상 작업 시간

- **Import & Logger 수정**: 30분
- **Config 타입 변경**: 20분
- **Agent scope 제거**: 40분
- **Session file 로직 제거**: 30분
- **타입 체크 & 컴파일**: 20분
- **테스트 & 디버깅**: 40분

**총 예상 시간**: ~3시간

## 다음 단계

1. ✅ batch 파일 완료
2. ⏳ manager.ts 수정 시작
   - Import 경로부터 차근차근
3. ⏳ 컴파일 확인
4. ⏳ Task #2 완료

## 모듈화 타이밍

**지금 (Task #2)**: 모듈화 ❌ (시간 절약)
**Task #4 이후**: 모듈화 ✅ (안정화 후 리팩토링)

**이유**:
- 일단 작동하는 버전 확보가 우선
- 실제 사용해보고 bottleneck 파악
- 그 다음 최적화

---

## 결론

**방안 C (점진적 단순화)**를 채택합니다.

1. manager.ts를 최소한만 수정해서 작동시키기
2. Moltbot 의존성 제거
3. 불필요한 기능 주석 처리
4. 나중에 필요에 따라 모듈 분리

이렇게 하면 Task #2를 빠르게 완료하고, Task #3(스키마 마이그레이션)으로 진행할 수 있습니다.
