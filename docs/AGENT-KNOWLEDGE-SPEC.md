# Agent Knowledge System Specification

> NotebookLM 기반 "Second Brain" — 14개 전문가 에이전트의 지식 관리 체계

## 1. 개요

마이클의 14개 전문가 에이전트는 각각 독립된 Google NotebookLM 노트북을 가진다.
이 노트북이 에이전트의 **"Second Brain"** 역할을 하며, 세 가지 핵심 기능을 제공한다:

| 기능 | 설명 | 구현 |
|------|------|------|
| **읽기 (Query)** | 맥락 기반 동적 질문 → Gemini가 종합한 답변 | `NlmClient.query()` |
| **쓰기 (Source/Note)** | 외부 문서(Source) + 자기 주석(Note) 저장 | `addSource()`, `noteCreate()` |
| **이해 (Outline)** | 노트북의 요약/주제 파악 → 동적 질문 생성 | `describeNotebook()` |

### 비전 vs 구현

```
┌─ 비전 ──────────────────────────────────────────┐
│  에이전트가 스스로:                               │
│  1. 노트북 구조를 파악하고 (마인드맵/아웃라인)     │
│  2. 맥락에 맞는 질문을 생성하고 (동적 Query)       │
│  3. 실패/성공 교훈을 기록/수정/삭제 (자율 지식 관리)│
└─────────────────────────────────────────────────┘
```

## 2. 아키텍처

```
                    ┌──────────────────────────────────────┐
                    │         Google NotebookLM             │
                    │  (Gemini 기반 지식 엔진)               │
                    │                                      │
                    │  ┌──────────┐  ┌──────────┐          │
                    │  │ Notebook │  │ Notebook │  × 14    │
                    │  │ market_  │  │ macro    │          │
                    │  │ data     │  │          │  ...     │
                    │  │          │  │          │          │
                    │  │ Sources: │  │ Sources: │          │
                    │  │  [Found] │  │  [Found] │          │
                    │  │  Snap..  │  │  Snap..  │          │
                    │  │ Notes:   │  │ Notes:   │          │
                    │  │  [OK]..  │  │  [FAIL]..│          │
                    │  └──────────┘  └──────────┘          │
                    └──────────┬───────────────────────────┘
                               │ nlm CLI
                    ┌──────────┴───────────────────────────┐
                    │         NlmClient (래퍼)               │
                    │  src/knowledge/nlm-client.ts          │
                    └──────────┬───────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
     ┌────────┴────────┐ ┌────┴──────┐ ┌───────┴───────┐
     │ KnowledgeManager│ │ Knowledge │ │ initAgent     │
     │ (노트북 레지스트리)│ │ Sync      │ │ Knowledge     │
     │ + 아웃라인 캐시   │ │ (동기화)   │ │ (시딩)         │
     └────────┬────────┘ └────┬──────┘ └───────────────┘
              │               │
              │     ┌─────────┼─────────┐
              │     │         │         │
     ┌────────┴─────┴──┐ ┌───┴──────┐ ┌┴──────────────┐
     │ JudgmentCycle    │ │ Decision │ │ StateStore     │
     │ (동적 Query)     │ │ Executor │ │ (onDecision    │
     │                  │ │(Write-   │ │  Recorded)     │
     │                  │ │ back)    │ │                │
     └──────────────────┘ └──────────┘ └────────────────┘
```

### 파일 구조

```
src/knowledge/
├── nlm-client.ts           # NLM CLI 래퍼 (핵심)
├── knowledge-manager.ts    # 에이전트별 노트북 관리 + 아웃라인 캐시
├── knowledge-sync.ts       # 자동 동기화 (Decision → Source/Note)
├── init-agent-knowledge.ts # 부트스트랩 + Foundational Knowledge 시딩
├── index.ts                # Re-exports
└── knowledge.test.ts       # 테스트 (43개)

knowledge/                  # Foundational Knowledge 원본
├── market-data/foundational.md
├── macro/foundational.md
├── news/foundational.md
├── social/foundational.md
├── onchain/foundational.md
├── pm-scanner/foundational.md
├── technical/foundational.md
├── risk/foundational.md
├── pm-analysis/foundational.md
├── portfolio/foundational.md
├── binance-exec/foundational.md
├── pm-exec/foundational.md
├── dca/foundational.md
└── rebalancer/foundational.md

data/
├── nlm-notebooks.json      # 에이전트 → 노트북 ID 매핑 (영속)
└── state/
    ├── mandate.yaml         # 운용 규정
    ├── state.yaml           # 포트폴리오 상태
    └── inputs.yaml          # 시장 데이터 입력
```

## 3. 핵심 컴포넌트

### 3.1 NlmClient — CLI 래퍼

`nlm` CLI를 `child_process.execFile`로 호출하는 TypeScript 래퍼.

**Source**: `src/knowledge/nlm-client.ts`

#### CLI 커맨드 매핑

| 메서드 | CLI 커맨드 | 용도 |
|--------|-----------|------|
| `query(question)` | `nlm notebook query <id> "question"` | 노트북에 질문 |
| `addSource(title, content)` | `nlm source add <id> --text "..." --title "..." --wait` | Source 추가 |
| `addSourceFile(path)` | `nlm source add <id> --file <path> --wait` | 파일 Source 추가 |
| `listSources()` | `nlm source list <id> --json` | Source 목록 |
| `deleteSource(sourceId)` | `nlm source delete <id> --confirm` | Source 삭제 |
| `describeNotebook()` | `nlm describe notebook <id>` | 노트북 아웃라인 |
| `noteCreate(title, content)` | `nlm note create <id> --title "..." --content "..."` | Note 생성 |
| `noteList()` | `nlm note list <id> --json` | Note 목록 |
| `noteUpdate(noteId, content)` | `nlm note update <id> <noteId> --content "..."` | Note 수정 |
| `noteDelete(noteId)` | `nlm note delete <id> <noteId> --confirm` | Note 삭제 |
| `createNotebook(title)` | `nlm notebook create "title"` | 노트북 생성 (static) |

#### CLI 응답 형식

```jsonc
// nlm notebook query → answer 추출
{"value":{"answer":"...", "conversation_id":"...", "sources_used":[]}}

// nlm describe notebook → summary + topics 추출
{"value":{"summary":["요약 텍스트..."], "suggested_topics":["주제1","주제2"]}}

// nlm note list --json
{"notebook_id":"...", "notes":[{"id":"uuid","title":"..."}], "count":0}

// nlm notebook create → UUID 파싱
"✓ Created notebook: ...\n  ID: <uuid>"
```

#### 설정

| 환경변수 | 기본값 | 설명 |
|---------|--------|------|
| `NLM_BIN` | `nlm` | nlm CLI 경로 |
| — | 60초 | 실행 타임아웃 (`EXEC_TIMEOUT`) |

### 3.2 KnowledgeManager — 노트북 레지스트리

에이전트별 독립 노트북을 관리하는 중앙 레지스트리.

**Source**: `src/knowledge/knowledge-manager.ts`

#### 핵심 동작

1. **자동 생성**: `getClient(agentName)` 호출 시 노트북이 없으면 자동 생성
2. **영속 매핑**: `data/nlm-notebooks.json`에 `{agentName → notebookId}` 저장
3. **클라이언트 캐시**: 한번 생성된 `NlmClient`는 메모리 캐시
4. **아웃라인 캐시**: `getOutline(agentName)` — 1시간 TTL, stale-on-error

#### 아웃라인 캐시 전략

```typescript
// 1시간 TTL
private readonly OUTLINE_TTL = 60 * 60 * 1000;

// 캐시 히트: 즉시 반환
// 캐시 미스: nlm describe notebook 호출 → 캐시 갱신
// 에러 시: stale 데이터 반환 (stale > nothing)
// Note 변경 시: invalidateOutline() 호출로 강제 갱신
```

#### 노트북 레지스트리 형식

```json
{
  "market_data": {
    "notebookId": "abc12345-...",
    "title": "Michael: market_data",
    "createdAt": "2026-02-15T..."
  },
  "macro": { ... },
  ...
}
```

### 3.3 KnowledgeSync — 자동 동기화

NotebookLM과의 양방향 동기화를 담당.

**Source**: `src/knowledge/knowledge-sync.ts`

#### 동기화 흐름

| 흐름 | 메서드 | 트리거 | 노트북 |
|------|--------|--------|--------|
| Decision 기록 | `syncDecision()` | StateStore.onDecisionRecorded | judgment |
| 일일 스냅샷 | `syncDailySnapshot()` | cron `0 22 * * *` | snapshot |
| 코드베이스 동기화 | `syncCodebase()` | 수동 | judgment |
| 실행 결과 Write-back | `syncDecisionOutcome()` | DecisionExecutor 성공/실패 | agent별 |
| Note 자동 정리 | `pruneOldNotes()` | cron `0 3 * * 0` (일요일) | agent별 |

#### Source vs Note 구분

```
Source (외부 문서)                    Note (자기 주석)
─────────────────                    ───────────────
• Foundational Knowledge             • 거래 실행 결과
• Daily Snapshot                     • 실패 교훈
• Codebase (Repomix)                 • 패턴 발견
• Decision 기록                      • 개선 사항

nlm source add/list/delete           nlm note create/list/update/delete
장기 보존                             30일 후 자동 정리
```

#### Write-back: Decision → Agent Note

```
DecisionExecutor.execute()
  ├─ 성공: decision.status = 'executed'
  │    └─ writeBackDecision() → syncDecisionOutcome()
  │         → noteCreate("[SUCCESS] 2026-02-15: BUY BTC", ...)
  │         → km.invalidateOutline('binance_trader')
  │
  └─ 실패: decision.status = 'rejected'
       └─ writeBackDecision() → syncDecisionOutcome()
            → noteCreate("[FAIL] 2026-02-15: BUY BTC", ...)
            → km.invalidateOutline('binance_trader')
```

에이전트 매핑 (`resolveAgentForDecision`):
- `platform.startsWith('binance')` → `binance_trader`
- `platform === 'polymarket'` → `pm_trader`

#### Note 자동 정리

매주 일요일 03:00, 30일 초과 Note 삭제:

```
Note 제목 형식: "[SUCCESS] 2026-02-15: BUY BTC"
                         └── 날짜 파싱 → cutoff 비교
```

대상 에이전트: `binance_trader`, `pm_trader` (실행팀만)

### 3.4 initAgentKnowledge — Foundational Knowledge 시딩

**Source**: `src/knowledge/init-agent-knowledge.ts`

부팅 시 14개 에이전트의 기반 지식을 자동 시딩.

#### 시딩 프로세스

```
1. getExecutableAgents() → 14개 에이전트
2. 각 에이전트:
   a. km.getClient(agent.id) → 노트북 생성/로드
   b. seedFoundationalKnowledge(client, agent):
      i.  listSources() → "[Foundational]" 접두사 확인
      ii. 이미 있으면 skip (idempotent)
      iii. knowledge/{knowledgeDir}/foundational.md 읽기
      iv. addSource("[Foundational] {agent.name}", content)
```

#### Foundational Knowledge 규모

| 에이전트 | 파일 | 라인 수 |
|---------|------|--------|
| market_data | `knowledge/market-data/foundational.md` | ~300 |
| macro | `knowledge/macro/foundational.md` | ~280 |
| news | `knowledge/news/foundational.md` | ~260 |
| social | `knowledge/social/foundational.md` | ~290 |
| onchain | `knowledge/onchain/foundational.md` | ~310 |
| pm_scanner | `knowledge/pm-scanner/foundational.md` | ~280 |
| technical | `knowledge/technical/foundational.md` | ~290 |
| risk | `knowledge/risk/foundational.md` | ~280 |
| pm_probability | `knowledge/pm-analysis/foundational.md` | ~270 |
| portfolio | `knowledge/portfolio/foundational.md` | ~260 |
| binance_trader | `knowledge/binance-exec/foundational.md` | ~280 |
| pm_trader | `knowledge/pm-exec/foundational.md` | ~270 |
| dca | `knowledge/dca/foundational.md` | ~280 |
| rebalancer | `knowledge/rebalancer/foundational.md` | ~290 |
| **합계** | **14 파일** | **~3,940 라인** |

각 파일은 해당 에이전트의 도메인 전문 지식을 포함:
- 역할 및 책임
- 핵심 지표/용어 정의
- 판단 프레임워크
- 실전 교훈 및 주의사항

## 4. 동적 Query 시스템

### 기존 방식 (deprecated)

```typescript
// 고정 문자열 — 맥락 무시
knowledgeQuery: '현재 BTC/ETH 기술적 분석 신호와 과거 유사 패턴은?'
```

### 새 방식: 아웃라인 + 맥락 기반

```typescript
private async queryAgentNotebooks(
  agentIds: string[],
  context: {
    gatherSummary?: string;   // Gather Phase에서 수집한 시장 데이터
    trigger?: string;          // Sentinel 트리거 (예: "PRICE_CRASH")
    routineType?: string;      // 루틴 유형 (morning/midday/evening/weekly/monthly)
  },
): Promise<string>
```

#### Query 생성 로직

```
1. outline = km.getOutline(agentId)     → 노트북 주제 목록
2. queryParts 조합:
   - "노트북 주제: [BTC, ETH, RSI, ...]"       ← outline.topics
   - "트리거: PRICE_CRASH"                     ← context.trigger
   - "최신 데이터: BTC $96K -2.3% ..."         ← context.gatherSummary
   - "이 맥락에서 {agent.name}의 과거 패턴과 교훈은?"
3. client.query(queryParts.join('\n'))   → Gemini 종합 답변
```

이 방식의 장점:
- **맥락 반영**: 아침 루틴 vs 급락 트리거에서 다른 질문 생성
- **노트북 인지**: 주제 목록으로 관련 없는 질문 방지
- **데이터 연계**: 최신 수집 데이터가 질문에 반영

## 5. 14개 에이전트 노트북 구조

### 팀 구성

```
정보 수집팀 (Intelligence)    분석팀 (Analysis)      실행팀 (Execution)
├── market_data              ├── technical          ├── binance_trader
├── macro                    ├── risk               ├── pm_trader
├── news                     ├── pm_probability     ├── dca
├── social                   └── portfolio          └── rebalancer
├── onchain
└── pm_scanner
```

### 노트북 컨텐츠 구성

각 에이전트 노트북은 다음 계층으로 구성:

```
Notebook: "Michael: {agent_id}"
│
├── Sources (외부 문서)
│   ├── [Foundational] {agent_name}     ← 기반 지식 (시딩)
│   ├── Daily Snapshot 2026-02-15       ← 일일 스냅샷 (자동)
│   ├── D-20260215-001: BUY BTC $50     ← 의사결정 기록 (자동)
│   └── Michael Codebase                ← 코드베이스 (수동)
│
└── Notes (자기 주석)
    ├── [SUCCESS] 2026-02-15: BUY BTC   ← 실행 성공 교훈
    └── [FAIL] 2026-02-10: SELL ETH     ← 실행 실패 교훈
```

## 6. 생명주기

### 부팅 시 (`src/index.ts`)

```
1. NlmClient.isAvailable() 확인
2. KnowledgeManager 생성 (data/ 디렉토리)
3. judgment/snapshot 노트북 클라이언트 생성
4. KnowledgeSync 인스턴스 생성
5. JudgmentCycle에 Knowledge 연결 (km + judgmentNlm + knowledgeSync)
6. StateStore에 Decision 콜백 등록
7. 일일 스냅샷 cron 등록 (22:00)
8. initAgentKnowledge(km) → 14개 노트북 생성/로드 + Foundational 시딩
9. Note 자동 정리 cron 등록 (일요일 03:00)
```

### 판단 주기 (`JudgmentCycle.runCycle`)

```
1. Gather Phase: AgentRunner로 정보 수집 스크립트 병렬 실행
2. 결과 → StatePopulator → state.yaml/inputs.yaml
3. queryAgentNotebooks(agentIds, context) → 동적 NLM Query
4. 프롬프트 구성: mandate + state + inputs + NLM 컨텍스트
5. Claude 판단 → Decision 생성
6. DecisionExecutor.execute() → 실행
7. Write-back: syncDecisionOutcome() → Agent Note
8. syncDecision() → judgment 노트북 Source
```

### 정기 스케줄

| 시간 | 작업 | 메서드 |
|------|------|--------|
| 08:00 | Morning 판단 | `judgmentCycle.runCycle('morning')` |
| 14:00 | Midday 판단 | `judgmentCycle.runCycle('midday')` |
| 21:00 | Evening 판단 | `judgmentCycle.runCycle('evening')` |
| 22:00 | Daily Snapshot | `knowledgeSync.syncDailySnapshot()` |
| 월 09:00 | Weekly 심층 분석 | `judgmentCycle.runCycle('weekly')` |
| 1일 09:00 | Monthly 심층 분석 | `judgmentCycle.runCycle('monthly')` |
| 일 03:00 | Note 자동 정리 | `knowledgeSync.pruneOldNotes()` |

## 7. 의존성 및 전제 조건

### 필수

- **nlm CLI**: `notebooklm-mcp-cli` 설치 + `nlm auth` 완료
- **Google 계정**: NotebookLM 접근 권한
- **mandate.yaml**: State Store 활성화 조건

### Graceful Degradation

NLM 미설치/미인증 시:
1. `NlmClient.isAvailable()` → `false`
2. Knowledge 관련 모든 기능 skip
3. JudgmentCycle은 NLM 없이 동작 (context가 비어있을 뿐)
4. 로그: `⚠️ Knowledge sync (NLM) failed to initialize`

## 8. 테스트

**Source**: `src/knowledge/knowledge.test.ts` (43개 테스트)

### 테스트 커버리지

| 카테고리 | 테스트 수 | 검증 대상 |
|---------|----------|----------|
| NlmClient 기본 | 6 | `isAvailable`, `query`, `addSource`, `listSources`, `deleteSource`, `createNotebook` |
| NlmClient JSON 파싱 | 5 | `query` answer 추출, `describeNotebook` summary/topics, 비-JSON fallback |
| Note CRUD | 5 | `noteCreate` UUID 파싱, `noteList` JSON 파싱, `noteUpdate`, `noteDelete` |
| KnowledgeManager | 8 | `getClient` 자동생성/캐시, 레지스트리 영속, `getOutline` TTL/stale/invalidate |
| KnowledgeSync | 4 | `syncDecision`, `syncDailySnapshot` |
| Write-back | 4 | `syncDecisionOutcome` 성공/실패/platform 매핑/null 처리 |
| Note Pruning | 3 | `pruneOldNotes` 삭제/유지/날짜 파싱 |
| Foundational Seeding | 5 | idempotent, 파일 존재/미존재, prefix 매칭 |
| initAgentKnowledge | 3 | 전체 초기화, 실패 허용, 카운트 |

### 실행

```bash
# 전체 테스트
pnpm vitest run src/knowledge/knowledge.test.ts

# 특정 카테고리
pnpm vitest run src/knowledge/knowledge.test.ts -t "NlmClient"
pnpm vitest run src/knowledge/knowledge.test.ts -t "Note CRUD"
```

## 9. 참고 문서

- `docs/nlm.md` — NotebookLM "Second Brain" 개념 가이드
- `docs/ASSET-MANAGER-CONCEPT.md` — 14개 에이전트 4요소 정의
- `docs/ARCHITECTURE-LAYERS.md` — 전체 아키텍처 계층
- `src/decision/agent-registry.ts` — 에이전트 레지스트리 (역할/도구/지식디렉토리)
