# Plan: OpenClaw 최신 코드 대비 Michael 적용 가능 기능 검토

## Context

Michael은 OpenClaw(구 Moltbot) 프로젝트를 참고하여 메모리 시스템을 이식했다. OpenClaw가 최신 코드로 업데이트되었으므로, Michael에 적용 가능한 신규 기능을 검토한다.

**이 문서는 코드 변경 계획이 아닌 기능 검토 보고서이다.**

---

## 현재 Michael vs OpenClaw 비교

| 영역 | Michael | OpenClaw |
|------|---------|----------|
| Embedding 프로바이더 | OpenAI, Gemini, Local | OpenAI, Gemini, **Voyage**, Local |
| 배치 처리 | 없음 (실시간만) | OpenAI/Gemini/Voyage Batch API |
| 토큰 제한 관리 | 하드코딩 | 프로바이더별 중앙 설정 |
| 검색 | Hybrid (vector 0.7 + FTS5 0.3) | 동일 |
| 인덱싱 소스 | messages → markdown → chunks | messages + **session transcripts** |
| UTF-8 입력 검증 | 없음 | 바이트 단위 분할 |
| QMD 외부 백엔드 | 없음 | 외부 메모리 시스템 연동 |
| Auth 프로필 체이닝 | 없음 | 다중 API 키 자동 폴백 |

---

## 적용 가능 기능 (우선순위순)

### 1. Embedding 토큰 제한 중앙 설정 — ⭐ HIGH / Small

**문제**: Michael은 chunking 시 토큰 제한을 하드코딩. 프로바이더별 max input tokens가 다름 (OpenAI: 8192, Gemini: 2048, Voyage: 32000)
**해결**: 프로바이더/모델별 토큰 제한 테이블 + 초과 시 자동 분할

- **참조**: `reference/openclaw/src/memory/embedding-model-limits.ts`, `embedding-input-limits.ts`
- **수정 대상**: `src/memory-new/config.ts`, `src/memory-new/manager.ts`
- **작업량**: ~50-80 라인

### 2. Voyage AI Embedding 프로바이더 — ⭐ HIGH / Small

**이점**: 다국어(한국어) 지원 우수, 코드 특화 모델(voyage-code-3) 제공, 가격 경쟁력
**구현**: REST API 클라이언트 + 프로바이더 팩토리 등록

- **참조**: `reference/openclaw/src/memory/embeddings-voyage.ts`, `batch-voyage.ts`
- **수정 대상**: 신규 `src/memory-new/embeddings-voyage.ts`, `src/memory-new/embeddings.ts` (팩토리), `src/memory-new/config.ts`
- **작업량**: ~100-150 라인

### 3. Batch Embedding API — ⭐ HIGH / Medium

**이점**: OpenAI Batch API 사용 시 50% 비용 절감. 대량 재인덱싱에 적합 (24시간 이내 완료)
**구현**: 배치 스케줄러 + 폴링 + 완료 콜백

- **참조**: `reference/openclaw/src/memory/batch-openai.ts`, `batch-gemini.ts`
- **수정 대상**: 신규 `src/memory-new/batch-scheduler.ts`, `src/memory-new/manager.ts`
- **작업량**: ~300-500 라인

### 4. UTF-8 바이트 입력 검증 — MEDIUM / Small

**문제**: 한국어/이모지 포함 텍스트에서 바이트 기준 제한 초과 시 인코딩 에러 가능
**해결**: 임베딩 전 UTF-8 바이트 수 검증 + 자동 분할

- **참조**: `reference/openclaw/src/memory/embedding-input-limits.ts`
- **수정 대상**: `src/memory-new/internal.ts`, `src/memory-new/manager.ts`
- **작업량**: ~80-120 라인

### 5. Session Transcript 인덱싱 — MEDIUM / Medium

**이점**: 현재 messages만 인덱싱. Gateway 대화 세션 전체를 JSONL로 저장/인덱싱하면 더 풍부한 컨텍스트 제공
**구현**: JSONL 파서 + 세션 소스 필터링

- **참조**: `reference/openclaw/src/memory/session-files.ts`, `sync-session-files.ts`
- **수정 대상**: 신규 `src/memory-new/session-files.ts`, `src/memory-new/manager.ts`
- **작업량**: ~200-300 라인

### 6. QMD 외부 메모리 백엔드 — LOW

외부 메모리 시스템(Obsidian, Logseq 등) 연동. 파워 유저용. 현재 Michael에는 불필요.

### 7. Auth 프로필 체이닝 — LOW

다중 API 키 자동 폴백. 싱글 유저 Michael에는 과잉.

---

## 추천 실행 순서

즉시 적용 가치가 있는 것은 **#1 토큰 제한 설정**과 **#2 Voyage 프로바이더**. 비용 절감이 필요하면 **#3 Batch API** 추가.

나머지(#4~#7)는 필요 시점에 검토.
