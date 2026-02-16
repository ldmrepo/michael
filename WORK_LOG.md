# WORK_LOG — 에이전트 4요소 체계 + 오케스트레이션 구현

> 최종 업데이트: 2026-02-15
> 이전 커밋: `4b9179e` (docs: 에이전트 4요소 체계 + NLM 지식 시스템 추가)
> 상태: **구현 완료, 커밋 전**

---

## 1. 작업 배경

감사 보고서에서 **심각도 높음** 2건 해결:

| # | 이슈 | 상태 |
|---|------|------|
| #2 | 에이전트 4요소 미구현 — 14개 전문가에 역할/지침/도구/지식 정의 없음 | ✅ 해결 |
| #3 | 에이전트 오케스트레이션 부재 — 마이클이 전문가를 호출하는 코드 없음 | ✅ 해결 |

설계 문서: `docs/ASSET-MANAGER-CONCEPT.md` §489-638

---

## 2. 완료된 작업 (Phase 1-9)

### Phase 1: AgentRegistry — 14개 에이전트 정의 ✅

**신규**: `src/decision/agent-registry.ts`

- `AgentDefinition` 인터페이스 (id, name, team, role, instructions, tools, knowledgeDir, outputFormat)
- `AgentTool` 인터페이스 (script, skillDir, args, timeout)
- `AGENT_REGISTRY` 상수: 14개 에이전트 전체 정의
  - 정보 수집팀(6): market_data, macro, news, social, onchain, pm_scanner
  - 분석팀(4): technical, risk, pm_probability, portfolio
  - 실행팀(4): binance_trader, pm_trader, dca, rebalancer
- 헬퍼: `getAgentsByTeam()`, `getExecutableAgents()`
- social 에이전트는 tools=[] (Playwright 인프라 별도 필요, 스코프 제외)

### Phase 2: RoutineAgents — 루틴별 소집 매핑 ✅

**신규**: `src/decision/routine-agents.ts`

- `GatherEntry` 인터페이스 (agentId, scriptIndex, args)
- `ROUTINE_AGENTS` 상수: 5개 루틴별 소집 목록
  - morning(7): 풀 소집
  - midday(3): 경량 (portfolio + binance_api + risk)
  - evening(4): 마감 (portfolio + market + news + risk)
  - weekly(10): 심층 (전체 + 온체인 3종)
  - monthly(6): 성과 (portfolio + NAV 스냅샷 + market + macro + risk + pm_scanner)

### Phase 3: AgentRunner — 스크립트 오케스트레이션 엔진 ✅

**신규**: `src/decision/agent-runner.ts`

- `GatherResult` 인터페이스 (agentId, script, status, message, data, durationMs)
- `AgentRunner` 클래스:
  - `runGatherPhase(routineType)`: ROUTINE_AGENTS 조회 → Promise.allSettled 병렬 실행
  - `runAgent(entry)`: AGENT_REGISTRY 조회 → spawnPython → StatePopulator 연동
  - `spawnPython(tool, extraArgs)`: scheduler-jobs.ts:124-206 패턴 추출 (spawn, 5분 timeout, JSON 파싱, safeResolve)
  - `static formatGatherSummary(results)`: 프롬프트용 텍스트 포맷
- skillDir 분기: `investment` vs `prediction-market` → `.claude/skills/{dir}/scripts/run.py`

### Phase 4: StatePopulator 확장 ✅

**수정**: `src/state-store/state-populator.ts`

추가된 case (9건):
```
collect_binance_api → populatePrices (기존 메서드 재사용)
collect_macro       → populateMacro (신규)
collect_news        → populateNews (신규)
collect_etf_flows   → populateOnchain (신규)
collect_smart_money  → populateOnchain
collect_options     → populateOnchain
collect_defi        → populateOnchain
scan_markets        → populateOpportunities (기존)
analyze             → populateAnalysis (신규)
```

신규 메서드 4건:
- `populateMacro()`: macro 객체 병합 + fed_rate/dxy 개별 필드
- `populateNews()`: headlines 갱신
- `populateOnchain()`: etf_flow, whale_moves, iv, max_pain, tvl_ranking, smart_money, options 필드를 macro에 병합
- `populateAnalysis()`: market_regime, overall_score, signals 갱신

### Phase 5: JudgmentCycle에 Gather Phase 통합 ✅

**수정**: `src/decision/judgment-cycle.ts`

변경된 `runCycle()` 흐름:
```
기존: mandate → state/inputs → NLM → prompt → Claude → Decision
변경: mandate → routineType 추출 → [Gather Phase] → state/inputs(최신값) → NLM → prompt → Claude → Decision
```

핵심 로직:
```typescript
// Gather Phase 조건: agentRunner 있고 + 루틴 트리거이고 + Sentinel 아닐 때
if (this.agentRunner && routineType && !trigger?.startsWith('SENTINEL:')) {
  const results = await this.agentRunner.runGatherPhase(routineType);
  gatherSummary = AgentRunner.formatGatherSummary(results);
}
```

### Phase 6: judgment-prompt.ts 확장 ✅

**수정**: `src/decision/judgment-prompt.ts`

- `buildJudgmentPrompt()` 파라미터 추가: `gatherSummary?: string`
- 섹션 7 신규: `[전문가 소집 결과]` — 루틴 가이드(섹션 8) 앞에 배치
- 기존 섹션 번호 시프트: 7→8 (루틴 가이드), 8→9 (판단 기준)

### Phase 7: 와이어링 ✅

**수정**: `src/index.ts`

```typescript
import { JudgmentCycle, AgentRunner } from './decision/index.js';
import { ..., initAgentKnowledge } from './knowledge/index.js';

// statePopulator 생성 후:
const agentRunner = new AgentRunner(statePopulator);
judgmentCycle.setAgentRunner(agentRunner);

// NLM 블록 내:
await initAgentKnowledge(km);
```

**수정**: `src/decision/index.ts` — 신규 export 추가 (AgentRunner, AGENT_REGISTRY, ROUTINE_AGENTS, 타입들)

### Phase 8: 테스트 ✅

**신규**: `src/decision/agent-registry.test.ts` (19 tests)
- AGENT_REGISTRY: 14개 완전성, 필드 유효성, 팀 분포, social 제외, skillDir 유효성
- 스크립트 파일 존재 확인 (investment + prediction-market)
- ROUTINE_AGENTS: 5개 루틴 정의, agentId 존재, scriptIndex 범위, 루틴별 특성 (morning 최대, midday 최소)
- AgentRunner.formatGatherSummary: 빈 결과, 성공, 혼합 결과

**수정**: `src/decision/judgment-cycle.test.ts` (+4 tests → 총 24 tests)
- gatherSummary 프롬프트 포함/미포함 테스트
- gatherSummary 위치 (루틴 가이드 앞) 검증

### Phase 9: Knowledge 노트북 부트스트랩 ✅

**신규**: `src/knowledge/init-agent-knowledge.ts`
- `initAgentKnowledge(km)`: 13개 실행 가능 에이전트(social 제외)에 대해 NLM 노트북 자동 생성/로드

**수정**: `src/knowledge/index.ts` — `initAgentKnowledge` export 추가

---

## 3. 파일 변경 요약

### 신규 파일 (5개)

| 파일 | 역할 |
|------|------|
| `src/decision/agent-registry.ts` | 14개 에이전트 4요소 정의 |
| `src/decision/routine-agents.ts` | 루틴별 소집 매핑 |
| `src/decision/agent-runner.ts` | 스크립트 오케스트레이션 엔진 |
| `src/knowledge/init-agent-knowledge.ts` | NLM 노트북 부트스트랩 |
| `src/decision/agent-registry.test.ts` | 레지스트리 + 루틴 + formatGatherSummary 테스트 |

### 수정 파일 (6개)

| 파일 | 변경 내용 |
|------|-----------|
| `src/state-store/state-populator.ts` | 9개 case 추가 + 4개 신규 populate 메서드 |
| `src/decision/judgment-cycle.ts` | agentRunner 필드 + Gather Phase 로직 |
| `src/decision/judgment-prompt.ts` | gatherSummary 파라미터 + [전문가 소집 결과] 섹션 |
| `src/decision/index.ts` | 신규 export 추가 |
| `src/knowledge/index.ts` | initAgentKnowledge export |
| `src/index.ts` | AgentRunner 와이어링 + initAgentKnowledge 호출 |
| `src/decision/judgment-cycle.test.ts` | gatherSummary 테스트 4건 추가 |

---

## 4. 검증 결과

```
tsc --noEmit        → 0 errors
vitest run src/decision/  → 43 tests pass (2 files)
vitest run (전체)         → 430 tests pass, 7 skipped (20 files)
```

---

## 5. 계획 대비 차이점 (2건)

| 항목 | 계획 | 구현 | 사유 |
|------|------|------|------|
| rebalancer 스크립트 | `cross_asset_rebalancer.py` | `execute_rebalance.py` | 실제 디스크에 파일 없음 → 실재 파일로 수정 |
| formatGatherSummary | JudgmentCycle private 메서드 | AgentRunner static 메서드 | GatherResult와의 결합도 → AgentRunner 소속이 적절 |

---

## 6. 아키텍처 다이어그램

```
JudgmentCycle.runCycle(trigger)
  │
  ├─ 1. mandate 읽기
  ├─ 2. routineType 추출 (morning/midday/evening/weekly/monthly)
  │
  ├─ 3. ★ Gather Phase (신규)
  │   ├─ ROUTINE_AGENTS[routineType] → GatherEntry[]
  │   ├─ AgentRunner.runGatherPhase()
  │   │   ├─ AGENT_REGISTRY[agentId] → AgentTool
  │   │   ├─ spawnPython(run.py, script.py)  ← 병렬 실행
  │   │   └─ StatePopulator.populateFromJobResult() → YAML 갱신
  │   └─ AgentRunner.formatGatherSummary() → 프롬프트 텍스트
  │
  ├─ 4. state/inputs 읽기 (Gather 후 최신값)
  ├─ 5. NLM 지식 조회
  ├─ 6. buildJudgmentPrompt(..., gatherSummary)
  │   ├─ [위임장] [현재상태] [판단재료] [최근결정]
  │   ├─ [긴급 트리거] [과거 패턴]
  │   ├─ ★ [전문가 소집 결과]  ← 신규 섹션
  │   ├─ [루틴 가이드]
  │   └─ [판단 기준] [출력 형식]
  │
  ├─ 7. Agent(Claude) 호출
  └─ 8. [DECISION:...] 파싱 → 승인 요청
```

---

## 7. 다음 작업자를 위한 참고사항

### 미구현 항목 (스코프 제외)

| 항목 | 사유 | 우선순위 |
|------|------|----------|
| social 에이전트 (X/Twitter) | Playwright 별도 인프라 필요 | 낮 |
| 에이전트 간 직접 통신 | 설계상 State Store 경유 원칙 | N/A |
| Knowledge 파일시스템 | NLM 노트북이 역할 수행 중 | N/A |
| Mandate 설정 UI | 별도 기능 | 중 |

### 주의사항

1. **rebalancer 스크립트**: CONCEPT.md에는 `cross_asset_rebalancer.py`로 명시되어 있으나, 실제 파일은 `execute_rebalance.py`. 향후 CONCEPT.md 업데이트 또는 스크립트 이름 변경 필요.

2. **Gather Phase 타임아웃**: 각 스크립트 기본 5분. morning 루틴(7개 병렬)은 최악의 경우 5분 소요. 전체 JudgmentCycle 실행 시간 고려 필요.

3. **Sentinel 트리거 스킵**: `trigger?.startsWith('SENTINEL:')` 시 Gather Phase 건너뜀. Sentinel이 이미 데이터를 갱신한 상태이므로 중복 수집 방지.

4. **StatePopulator 확장 시**: 새 스크립트 추가 시 `populateFromJobResult()` switch 문에 case 추가 + populate 메서드 작성 필요.

5. **테스트**: `agent-registry.test.ts`가 스크립트 파일 존재를 `existsSync`로 검증함. 스크립트 이름 변경 시 레지스트리 + 테스트 동시 수정 필요.

### 관련 파일 참조

- 설계 문서: `docs/ASSET-MANAGER-CONCEPT.md` §489-638 (14개 에이전트 정의)
- 기존 spawnPython 패턴: `src/investment/scheduler-jobs.ts:124-206`
- State Store 타입: `src/state-store/types.ts`
- 기존 cron 스케줄: `src/index.ts:180-195` (morning 08:00, midday 14:00, evening 21:00, weekly 월 09:00, monthly 1일 09:00)
