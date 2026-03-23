# AGENTS.md

## Project Overview

**마이클(Michael)** — 24/7 AI 자산관리 전문가. Telegram으로 실시간 브리핑 및 거래 실행.

### Architecture

```
Gateway (WebSocket :18789)
  ├─> Telegram Channel
  ├─> Claude/Codex Agent
  ├─> Memory (SQLite)
  └─> Scheduler (node-cron)
```

모든 컴포넌트는 Gateway를 통해 통신한다. Memory만 직접 동기 접근한다.

## Critical Rules

1. `claude -p` 기반 CLI 사용. `--task`, `@anthropic-ai/sdk` 사용 금지.
2. `ANTHROPIC_API_KEY`를 설정하지 않는다. Claude Max 구독 기반으로 동작한다.
3. Memory는 `better-sqlite3` 기반 동기 접근만 사용한다.
4. DB 조회 시 정렬은 항상 `ORDER BY timestamp DESC, id DESC`를 기본으로 한다.
5. Telegram과 Agent는 직접 연결하지 않고 반드시 Gateway를 경유한다.
6. cron 등록 전 `cron.validate()`를 반드시 수행한다.

## Code Rules

- 민감 정보는 코드에 하드코딩하지 않는다. API 키, 비밀번호, 지갑 주소는 반드시 환경변수로 관리한다.
- TypeScript는 strict mode를 유지하고 ESNext modules 기준을 따른다.
- import 시 `.js` 확장자를 명시한다.
- 스킬 스크립트는 `.claude/skills/{skill_name}/scripts/`에 둔다.
- 공통 스크립트는 `scripts/`에 둔다.

## Strategy Migration Rule

- 전략을 개선하거나 새 전략으로 전환할 때 과거 전략과의 호환성을 위해 코드를 남기지 않는다.
- 기존 전략 관련 소스, 설정, CLI, 테스트, 문서, dead import를 함께 제거한다.
- fallback, bridge, compatibility layer를 남겨 기술부채를 만들지 않는다.
- 최종 상태는 단일 활성 전략 경로만 유지하는 것을 원칙으로 한다.

## Strategy Baseline Rule

- 현재 채택한 전략 기준선은 마지막으로 유효한 out-of-sample 결과를 낸 버전으로 고정한다.
- 기준선은 `기준 자체가 잘못되었다`는 근거가 확인될 때만 변경한다.
- 기준선 변경 전에는 반드시 현재 기준선 대비 실제 백테스트/워크포워드 수치로 열화 또는 오류를 입증해야 한다.
- 기준선 위 실험은 한 번에 한 변수만 바꾸고, OOS 결과가 기준선보다 나빠지면 채택하지 않는다.
- 현재 `binance-scalper` 전략 기준선 run id는 `20260308T071943Z-strategy-walkforward`로 본다.

## Key Files

- Agent: `src/agent/claude-code.ts`
- Gateway: `src/core/gateway.ts`
- Memory: `src/brain/memory.ts`
- Scheduler: `src/scheduler/cron.ts`
- Telegram: `src/channels/telegram.ts`
- Vector Search: `src/memory-new/manager.ts`

## Reference

- 추가 프로젝트 맥락과 운영 설명은 `CLAUDE.md`를 함께 참고한다.
