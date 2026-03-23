---
title: "마이클 요청 처리 흐름"
date: "2026-02-16"
type: documentation
domain: architecture
tags: [architecture, flow, memory, nlm, vault, knowledge]
source: manual
status: active
---

# 마이클 요청 처리 흐름

마이클이 사용자의 요청을 받아 처리하고 응답하는 전체 과정을 설명합니다.

## 1. 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                     사용자 (Telegram)                        │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ↓
┌─────────────────────────────────────────────────────────────┐
│                  Telegram Channel                            │
│              (WebSocket Client)                              │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ↓
┌─────────────────────────────────────────────────────────────┐
│                    Gateway                                   │
│              (WebSocket Hub: 18789)                          │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ↓
┌─────────────────────────────────────────────────────────────┐
│               ClaudeCodeAgent                                │
│          (AI Brain via Claude CLI)                           │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │           지식 검색 시스템                              │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐ │ │
│  │  │  Memory  │  │   NLM    │  │  Obsidian Vault      │ │ │
│  │  │  SQLite  │  │NotebookLM│  │  (Markdown Files)    │ │ │
│  │  └────┬─────┘  └────┬─────┘  └──────────┬───────────┘ │ │
│  │       │             │                    │              │ │
│  │       ↓             ↓                    ↓              │ │
│  │  Recent Msgs   AI Query           Curated Playbooks    │ │
│  │  Vector Search Learned Lessons    Archived Knowledge   │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │           프롬프트 생성 → Claude CLI 호출               │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │         응답 처리 및 학습 기록                          │ │
│  │  - [LESSON:] → NLM + Vault 듀얼 라이트                 │ │
│  │  - [FACT:] → Memory facts 테이블                       │ │
│  │  - [SCHEDULE:] → Memory schedules 테이블               │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ↓
                   Gateway
                      │
                      ↓
               Telegram Channel
                      │
                      ↓
                  사용자에게 응답
```

## 2. 요청 처리 단계별 흐름

### 2.1 메시지 수신 (Telegram → Gateway)

1. 사용자가 Telegram에 메시지 전송
2. **TelegramChannel** WebSocket 클라이언트가 메시지 수신
3. Gateway로 메시지 전송:
   ```typescript
   {
     from: 'telegram',
     to: 'agent',
     userId: '7976872618',  // Telegram chat_id
     content: '스캘핑',
     metadata: { chatId: 7976872618 }
   }
   ```

### 2.2 메시지 저장 (Memory)

Gateway가 Agent로 메시지를 라우팅하기 전에 **Memory**에 저장:

```typescript
// data/memory.db - messages 테이블
{
  user_id: '7976872618',
  role: 'user',
  content: '스캘핑',
  timestamp: 1771229432150
}
```

**Memory 역할:**
- 대화 이력 영구 저장 (SQLite)
- FTS5 전문 검색 지원
- 벡터 임베딩 저장 (memory-index.db)
- Facts, Schedules 관리

### 2.3 지식 검색 단계 (Knowledge Retrieval)

Agent가 메시지를 받으면 **세 가지 지식 시스템**을 병렬로 조회:

#### A. Memory 검색 (Recent + Vector)

**최근 대화 조회:**
```sql
SELECT * FROM messages
WHERE user_id = '7976872618'
ORDER BY timestamp DESC, id DESC
LIMIT 5
```

**벡터 유사도 검색:**
```typescript
memory.searchMessagesVector(userId, message, {
  maxResults: 3,
  minScore: 0.7
})
```

- 사용자의 메시지를 임베딩으로 변환
- memory-index.db의 vec_chunks 테이블에서 유사 벡터 검색
- FTS5 키워드 매칭과 하이브리드 검색
- 과거 유사한 대화 컨텍스트 제공

**로그 예시:**
```
memory embeddings: query start { provider: 'local', timeoutMs: 300000 }
```

#### B. NLM (NotebookLM) 조회

**AI 기반 의미 검색:**
```bash
nlm notebook query c3cebd51-e260-4de4-9a57-a9cc9913dd4c "스캘핑"
```

**NLM의 특징:**
- 17개 도메인별 노트북 관리
- AI 기반 의미론적 질의 응답
- 학습된 교훈 자동 통합
- **30일 TTL** (자동 삭제)

**도메인별 노트북:**
- `binance_trader` (766109ef-...) - Binance 거래 교훈
- `pm_trader` (c4c42932-...) - Polymarket 거래 교훈
- `portfolio` (36e85c3c-...) - 포트폴리오 관리
- `risk` (195aa81f-...) - 리스크 관리
- `michael` (c3cebd51-...) - 범용 교훈

**로그 예시:**
```
📓 Agent knowledge initialized: 1 notebooks
🧠 NLM connected to Agent
```

#### C. Obsidian Vault 검색

**큐레이션된 지식 검색:**
```typescript
vault.searchByContent('스캘핑', {
  status: 'active',
  limit: 3
})
```

**검색 대상:**
- 제목 (frontmatter.title)
- 본문 (content)
- 태그 (frontmatter.tags) ← **2026-02-16 개선**

**Vault의 특징:**
- **영구 보존** (Git 버전 관리 가능)
- 구조화된 디렉토리 (playbooks/, lessons/, daily/, weekly/)
- YAML 프론트매터로 메타데이터 관리
- 사람이 직접 편집 가능

**로그 예시:**
```
📓 Vault query: "스캘핑..."
📓 Vault results: 1 notes found
```

**검색 결과:**
```markdown
### BTC Scalping Test Strategy (binance)
# BTC Scalping Test Strategy

## Entry Criteria
- 5분봉 RSI < 30
- 볼린저 밴드 하단 터치

## Position Sizing
- 포트폴리오의 3%
- 레버리지 5x
...
```

### 2.4 프롬프트 생성 (Prompt Building)

Agent가 수집한 모든 컨텍스트를 통합하여 프롬프트 생성:

```typescript
buildPrompt(message, context, nlmContext, vaultContext) {
  return `
당신은 마이클(Michael), 24시간 자산관리 AI 전문가입니다.

## 최근 대화 (Memory)
${context}  // 최근 5개 메시지

## 벡터 검색 결과 (Semantic Memory)
${vectorContext}  // 유사한 과거 대화 3개

## 세컨드 브레인 (NLM - AI Knowledge)
${nlmContext}  // NLM 쿼리 결과

## 지식 저장소 (Curated Knowledge)
${vaultContext}  // Vault 플레이북/교훈

## 사용자 메시지
${message}
`;
}
```

### 2.5 Claude CLI 호출

```typescript
const process = spawn('claude', ['-p']);  // print mode
process.stdin.write(prompt);
process.stdin.end();

// 스트리밍 응답 수신
process.stdout.on('data', (data) => {
  // 응답을 Gateway로 전송
  gateway.send({
    from: 'agent',
    to: 'telegram',
    userId,
    content: data.toString()
  });
});
```

**CLI 사용 이유:**
- Claude Max 구독 활용 (API 키 불필요)
- 추가 비용 없음
- 간단한 통합

### 2.6 응답 처리 및 학습 기록

Claude의 응답을 파싱하여 특수 마커 처리:

#### A. [LESSON:] 마커 - 듀얼 라이트

```
[LESSON:Hedge Mode 필수:Binance Futures Hedge mode에서는 positionSide 필수]
```

**NLM 기록:**
```bash
nlm note create c3cebd51-e260-4de4-9a57-a9cc9913dd4c \
  --title "Hedge Mode 필수" \
  --content "Binance Futures Hedge mode에서는 positionSide 필수"
```

**Vault 기록:**
```typescript
vault.createNote({
  frontmatter: {
    title: 'Hedge Mode 필수',
    date: '2026-02-16',
    type: 'lesson',
    domain: 'general',
    tags: [],
    source: 'nlm',
    status: 'active'
  },
  content: 'Binance Futures Hedge mode에서는 positionSide 필수'
}, 'lessons/general')
```

**저장 위치:**
- NLM: `michael` 노트북 (30일 TTL)
- Vault: `lessons/general/hedge-mode-필수.md` (영구)

#### B. [FACT:] 마커 - Memory 저장

```
[FACT:preferred_leverage:5x]
```

```sql
INSERT INTO facts (user_id, key, value, updated_at)
VALUES ('7976872618', 'preferred_leverage', '5x', 1771229432150)
ON CONFLICT (user_id, key) DO UPDATE SET value = '5x';
```

#### C. [SCHEDULE:] 마커 - Cron 등록

```
[SCHEDULE:0 9 * * *:매일 아침 9시 포트폴리오 리포트]
```

```sql
INSERT INTO schedules (user_id, cron, message, active)
VALUES ('7976872618', '0 9 * * *', '매일 아침 9시 포트폴리오 리포트', 1);
```

```typescript
cron.schedule('0 9 * * *', () => {
  gateway.send({
    from: 'scheduler',
    to: 'agent',
    userId: '7976872618',
    content: '매일 아침 9시 포트폴리오 리포트'
  });
});
```

### 2.7 응답 전송

```
Agent → Gateway → TelegramChannel → 사용자
```

**최종 응답 예시:**
```
동명님! 스캘핑 기회 분석하겠습니다!

━━━━━━━━━━━━━━━━━━━━
🔥 BTC 스캘핑 전략 실행
━━━━━━━━━━━━━━━━━━━━

세컨드 브레인의 "BTC Scalping Test Strategy"를 참고하여
현재 시장 상황을 분석하겠습니다!

진입 조건 체크:
✓ 5분봉 RSI < 30 여부
✓ 볼린저 밴드 하단 터치 여부
✓ 포지션 사이즈: 포트폴리오 3% (레버리지 5x)

목표 수익/손절:
• TP: +2% (레버리지 5x → 10% 수익)
• SL: -0.5% (레버리지 5x → 2.5% 손실)

지금 바로 시장 분석하겠습니다! 💪
```

## 3. 자동화된 백그라운드 작업

### 3.1 Cron 스케줄 (index.ts)

```typescript
// 일일 저널 (매일 21:00 UTC = KST 06:00)
cron.schedule('0 21 * * *', () =>
  obsidianSync.generateDailyJournal()
);

// 주간 리뷰 (일요일 02:00 UTC)
cron.schedule('0 2 * * 0', () =>
  obsidianSync.generateWeeklyReview()
);

// NLM → Vault 아카이빙 (일요일 02:30 UTC)
cron.schedule('30 2 * * 0', () =>
  obsidianSync.archiveNlmLessons([...])
);

// Vault → NLM 플레이북 동기화 (매일 03:30 UTC)
cron.schedule('30 3 * * *', () =>
  obsidianSync.syncPlaybooksToNlm()
);
```

### 3.2 NLM ↔ Vault 양방향 동기화

#### NLM → Vault (아카이빙)

**목적:** NLM의 30일 TTL 교훈을 영구 보존

```typescript
archiveNlmLessons(agentIds, domainMap) {
  for (const [agentId, domain] of agentIds) {
    // NLM에서 노트 목록 조회
    const notes = nlmClient.noteList(agentId);

    for (const note of notes) {
      // 중복 확인 (nlm_note_id)
      if (state.nlmArchived[note.id]) continue;

      // Vault에 저장
      const path = vault.createNote({
        frontmatter: {
          title: note.title,
          type: 'lesson',
          domain,
          source: 'nlm',
          nlm_note_id: note.id,
          status: 'active'
        },
        content: note.content
      }, `lessons/${domain}`);

      // 상태 저장
      state.nlmArchived[note.id] = path;
    }
  }
}
```

**저장 경로:**
```
lessons/
├── binance/
│   └── hedge-mode-lesson.md
├── polymarket/
│   └── usdc-e-required.md
└── general/
    └── api-rate-limit.md
```

#### Vault → NLM (플레이북 업로드)

**목적:** 큐레이션된 플레이북을 NLM Source로 등록하여 AI 지식 품질 향상

```typescript
syncPlaybooksToNlm() {
  const playbooks = vault.listNotes('playbooks/');

  for (const playbook of playbooks) {
    // 해시로 변경 감지
    const hash = crypto.hash(playbook.content);
    const cached = state.vaultUploaded[playbook.path];

    if (cached?.hash === hash) continue;  // 미변경 스킵

    // NLM에 Source로 업로드
    const sourceId = nlmClient.addSource(
      notebookId,
      playbook.content,
      playbook.frontmatter.title
    );

    // 상태 저장
    state.vaultUploaded[playbook.path] = { hash, sourceId };
  }
}
```

## 4. 데이터베이스 구조

### 4.1 Memory DB (data/memory.db)

**better-sqlite3** - 동기 API

```sql
-- 사용자
CREATE TABLE users (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  created_at INTEGER NOT NULL
);

-- 메시지
CREATE TABLE messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  role TEXT NOT NULL,  -- 'user' | 'assistant'
  content TEXT NOT NULL,
  timestamp INTEGER NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

-- FTS5 전문 검색
CREATE VIRTUAL TABLE messages_fts USING fts5(
  content,
  content=messages,
  content_rowid=id
);

-- Facts (사용자 속성)
CREATE TABLE facts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  key TEXT NOT NULL,
  value TEXT NOT NULL,
  updated_at INTEGER NOT NULL,
  UNIQUE(user_id, key)
);

-- Schedules (Cron 작업)
CREATE TABLE schedules (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  cron TEXT NOT NULL,
  message TEXT NOT NULL,
  active INTEGER DEFAULT 1,
  created_at INTEGER NOT NULL
);
```

### 4.2 Vector Index DB (data/memory-index.db)

**node:sqlite** - sqlite-vec 확장 지원

```sql
-- 임베딩 청크
CREATE TABLE chunks (
  id TEXT PRIMARY KEY,
  file_id TEXT NOT NULL,
  content TEXT NOT NULL,
  embedding BLOB,  -- 벡터 임베딩
  start_char INTEGER,
  end_char INTEGER,
  FOREIGN KEY (file_id) REFERENCES files(id)
);

-- 벡터 검색 (sqlite-vec)
CREATE VIRTUAL TABLE vec_chunks USING vec0(
  chunk_id TEXT PRIMARY KEY,
  embedding FLOAT[768]  -- 임베딩 차원
);

-- FTS5 하이브리드 검색
CREATE VIRTUAL TABLE memory_fts USING fts5(
  chunk_id UNINDEXED,
  content
);
```

### 4.3 Obsidian Sync State (data/obsidian-sync-state.json)

```json
{
  "nlmArchived": {
    "note_abc123": "lessons/binance/hedge-mode.md"
  },
  "vaultUploaded": {
    "playbooks/test-strategy.md": {
      "hash": "sha256:abc...",
      "nlmSourceId": "source_xyz789"
    }
  }
}
```

## 5. 주요 설계 결정 사항

### 5.1 왜 세 가지 지식 시스템을 사용하나?

| 시스템 | 역할 | 장점 | 단점 |
|--------|------|------|------|
| **Memory** | 대화 이력 저장 | - 빠른 조회<br>- FTS5 전문 검색<br>- 벡터 유사도 검색 | - 구조화 어려움<br>- AI 쿼리 불가 |
| **NLM** | AI 기반 지식 검색 | - 의미론적 이해<br>- 자동 통합<br>- 자연어 질의 | - 30일 TTL<br>- 편집 불가<br>- 오프라인 불가 |
| **Vault** | 큐레이션된 지식 저장 | - 영구 보존<br>- 구조화<br>- 직접 편집 가능<br>- Git 버전 관리 | - AI 쿼리 불가<br>- 수동 관리 |

**시너지 효과:**
- Memory: 최근 문맥 + 유사 대화 검색
- NLM: AI가 학습한 교훈 자동 통합
- Vault: 큐레이션된 플레이북 영구 보존

### 5.2 듀얼 라이트 (NLM + Vault)

[LESSON:] 마커를 **두 곳에 동시 저장**:

1. **NLM**: 즉시 AI 쿼리 가능, 30일 후 자동 삭제
2. **Vault**: 영구 보존, 사람이 편집 가능

**장점:**
- NLM의 즉시성과 Vault의 영구성을 동시에 확보
- NLM이 삭제되어도 Vault에 백업 존재
- Vault에서 큐레이션 후 NLM에 재업로드 가능

### 5.3 동기 vs 비동기

| 컴포넌트 | API 스타일 | 이유 |
|----------|-----------|------|
| Memory (better-sqlite3) | **동기** | - 단순성<br>- 안정성<br>- 빠른 로컬 I/O |
| Vector Index (node:sqlite) | **비동기** | - sqlite-vec 호환<br>- 임베딩 계산 시간 |
| NLM CLI | **비동기** | - 외부 프로세스<br>- 네트워크 I/O |
| Vault (파일 I/O) | **동기** | - Memory 패턴 일관성<br>- 단순 파일 읽기 |

## 6. 성능 최적화

### 6.1 캐싱 전략

```typescript
// 임베딩 캐시
CREATE TABLE embedding_cache (
  text_hash TEXT PRIMARY KEY,
  embedding BLOB NOT NULL,
  created_at INTEGER NOT NULL
);
```

동일한 텍스트는 임베딩을 재계산하지 않고 캐시 사용.

### 6.2 하이브리드 검색

**BM25 (FTS5) + 벡터 유사도**

```typescript
// 1. FTS5로 키워드 매칭
const ftsResults = db.prepare(`
  SELECT chunk_id FROM memory_fts
  WHERE content MATCH ?
  ORDER BY rank LIMIT 100
`).all(query);

// 2. 벡터 유사도 계산
const vecResults = db.prepare(`
  SELECT chunk_id, vec_distance_cosine(embedding, ?) as score
  FROM vec_chunks
  WHERE chunk_id IN (${ftsResults.map(r => r.chunk_id)})
  ORDER BY score DESC LIMIT 10
`).all(queryEmbedding);
```

**장점:**
- FTS5로 후보군 빠르게 필터링 (100개)
- 벡터 유사도로 정확도 향상 (상위 10개)

### 6.3 Vault 검색 최적화

**단어 토큰화 + 부분 일치**

```typescript
const queryWords = query.toLowerCase().split(/\s+/).filter(w => w.length > 1);
const results = allNotes.filter(note => {
  const tags = note.frontmatter.tags?.join(' ') || '';
  const searchable = `${note.frontmatter.title} ${note.content} ${tags}`.toLowerCase();
  return queryWords.some(word => searchable.includes(word));
});
```

**개선 사항 (2026-02-16):**
- 태그 검색 추가
- 한글/영문 동시 검색 지원

## 7. 로깅 및 디버깅

### 7.1 주요 로그 포인트

```typescript
// 초기화
log('info', '📓 Vault structure ensured: ./data/obsidian-vault');
log('info', '📓 Obsidian vault connected to Agent');
log('info', '🧠 NLM connected to Agent');

// 지식 검색
log('info', '📓 Vault query: "스캘핑..."');
log('info', '📓 Vault results: 1 notes found');

// 학습 기록
log('info', '📝 Lesson recorded to NLM: Hedge Mode 필수');
log('info', '📝 Lesson archived to Vault: lessons/general/hedge-mode.md');

// 에러
log('warn', '⚠️  Vault query error: ...');
log('error', '❌ NLM query failed: ...');
```

### 7.2 PM2 로그 확인

```bash
# 전체 로그
pm2 logs michael

# Vault 관련 로그만
pm2 logs michael --lines 100 --nostream | grep "📓\|Vault"

# 에러 로그
pm2 logs michael --err
```

### 7.3 데이터베이스 디버깅

```bash
# Memory DB 확인
sqlite3 data/memory.db "SELECT * FROM messages ORDER BY timestamp DESC LIMIT 5;"

# Vector Index DB 확인
sqlite3 data/memory-index.db "SELECT COUNT(*) FROM chunks;"

# Vault 파일 확인
ls -la data/obsidian-vault/playbooks/
cat data/obsidian-vault/playbooks/test-strategy.md
```

## 8. 트러블슈팅

### 8.1 Vault 검색 결과 없음

**증상:**
```
📓 Vault query: "스캘핑..."
📓 Vault results: 0 notes found
```

**해결 방법:**
1. 파일 존재 확인: `ls data/obsidian-vault/playbooks/`
2. frontmatter status 확인: `status: active`인지
3. 태그 확인: 한글/영문 태그 모두 포함되었는지
4. 검색 로직 확인: `searchByContent()` 메서드

### 8.2 NLM 쿼리 실패

**증상:**
```
⚠️  NLM query failed: Command failed: nlm notebook query ...
```

**해결 방법:**
1. NLM CLI 설치 확인: `which nlm`
2. 노트북 ID 확인: `nlm notebook list`
3. 인증 상태 확인: `nlm whoami`

### 8.3 벡터 검색 느림

**증상:**
```
memory embeddings: query start { timeoutMs: 300000 }
(3분 이상 소요)
```

**해결 방법:**
1. 로컬 모델 캐시 확인: `~/.cache/node-llama-cpp`
2. 임베딩 캐시 확인: `SELECT COUNT(*) FROM embedding_cache;`
3. OpenAI/Gemini 등 외부 API 사용 고려

## 9. 향후 개선 사항

### 9.1 Vault 벡터 검색 통합

현재 Vault는 키워드 검색만 지원. MemoryIndexManager에 Vault 파일 소스 추가하여 벡터 검색 지원 예정.

### 9.2 실시간 파일 감시

`chokidar`로 Vault 디렉토리 감시하여 파일 변경 시 자동 NLM 동기화.

### 9.3 다국어 검색

한국어 ↔ 영어 용어 매핑 테이블 구축하여 양방향 검색 지원.

### 9.4 지식 그래프

Obsidian의 링크 구조를 파싱하여 지식 간 관계 시각화.

## 10. 결론

마이클의 요청 처리는 **세 가지 지식 시스템의 조화**로 이루어집니다:

- **Memory**: 빠른 대화 이력 + 벡터 유사도 검색
- **NLM**: AI 기반 의미론적 지식 검색 (30일 TTL)
- **Vault**: 큐레이션된 영구 지식 저장소

이를 통해 마이클은:
1. 최근 문맥을 기억하고
2. 과거 유사한 대화를 찾아내며
3. 학습한 교훈을 자동으로 통합하고
4. 큐레이션된 플레이북을 참조하여

**일관되고 맥락있는 응답**을 제공합니다.

모든 학습은 **듀얼 라이트**로 NLM과 Vault에 동시 기록되어, NLM의 즉시성과 Vault의 영구성을 모두 확보합니다.
