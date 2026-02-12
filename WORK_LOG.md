# Michael AI Assistant - Work Log

프로젝트 작업 이력. 이후 작업자는 이 문서를 참조하여 현재 상태를 파악하고 작업을 이어간다.

---

## Phase 0: 프로젝트 시작 동기

> "기존 AI는 요청할 때만 반응한다. 기억하고, 필요할 때 스스로 행동하고 조언하며,
> Telegram 같은 채널을 통해 능동적으로 대화하는 24시간 깨어있는 동반자를 만든다."

Moltbot(https://github.com/moltbot/moltbot) 참고, **"복잡한 것보다 뼈대를 튼튼히"** 원칙.

---

## Phase 1~6: Core 시스템 (완료)

| 컴포넌트 | 파일 | 역할 |
|----------|------|------|
| Memory | `src/brain/memory.ts` | SQLite(better-sqlite3) 영구 저장소 + FTS5 |
| Gateway | `src/core/gateway.ts` | WebSocket 중앙 메시지 허브 (:18789) |
| Claude Agent | `src/agent/claude-code.ts` | Claude CLI(`claude -p`) AI 대화 |
| Telegram | `src/channels/telegram.ts` | Telegraf 봇 + 수동 폴링 |
| Scheduler | `src/scheduler/cron.ts` | node-cron 반복 + setTimeout 1회 알림 |
| Daemon | `scripts/install-daemon.sh` | macOS launchd 서비스 |

테스트: memory(26), gateway(8), cron(9), integration(12, 7 skipped)

---

## Phase 7: 벡터 검색 통합 (완료)

Moltbot 벡터 임베딩 검색을 통합. `src/memory-new/` 모듈.

- **DB 분리**: Main(`data/memory.db`, better-sqlite3) / Vector(`data/memory-index.db`, node:sqlite + sqlite-vec)
- **API**: `initializeVectorSearch()` → `syncMessagesToChunks()` → `searchMessagesVector()`
- **임베딩**: 로컬 embeddinggemma-300M (GGUF) 채택 — 한국어 정확도 최고 (4/4)

---

## Phase 8~12: 프로토콜 통합 (완료)

### Phase 8-10: HTTP Server + Telegram Mini App
- Express HTTP 서버 (:3000) — SSE 스트리밍, REST API, 정적 파일
- Telegram Mini App (React) — A2UI Surface 렌더링, Reply Keyboard 방식
- ngrok HTTPS 터널링

### Phase 11: 웹 프론트엔드
- Next.js 프론트엔드 (:3001) — AG-UI SSE 클라이언트, A2UI 렌더러

### Phase 12: A2A 멀티에이전트
- `src/a2a/` — A2AServer, A2AClient, A2AOrchestrator
- JSON-RPC 2.0 기반, AgentCard 표준

---

## Phase 13: Finance Agent (완료)

A2A 프로토콜 기반 재무 분석 에이전트 (:8001).

- **스킬**: 포트폴리오 분석, 시장 조사, 지출 추적
- **데이터**: yfinance(주식), CoinGecko(암호화폐), Frankfurter(환율), Alpha Vantage(fallback)
- **구조**: `src/agents/finance/` — agent.ts, executor.ts, server.ts, prompts.ts, tools.ts
- **실행**: Claude CLI spawn (`claude -p --allowedTools 'Bash(bash:*),Read'`)
- **Finance Skill**: `.claude/skills/finance/SKILL.md`

---

## Phase 14: Investment Service (진행중)

암호화폐 투자 서비스. Binance API + 브라우저 자동화, Semi-Auto 매매.

### 14.1 초기 구현 (2026-02-08)

**TypeScript 오케스트레이터** (`src/investment/`):
| 모듈 | 파일 | 역할 |
|------|------|------|
| PortfolioStore | `portfolio-store.ts` | DB CRUD (9개 테이블) |
| InvestmentScheduler | `scheduler-jobs.ts` | 14개 cron job 관리 |
| ResearchEngine | `research-engine.ts` | 데이터 수집 트리거 |
| AnalysisEngine | `analysis-engine.ts` | Claude AI 분석 통합 |
| RiskEngine | `risk-engine.ts` | 위험 모니터링 + 알림 |
| ExecutionEngine | `execution-engine.ts` | Semi-Auto 매매 워크플로우 |

**Python 스크립트** (`.claude/skills/investment/scripts/`, 25개):
- 인증: `auth_manager.py`, `browser_utils.py`
- 포트폴리오: `sync_balance.py`, `sync_transactions.py`, `snapshot_nav.py`
- 데이터 수집: `collect_market.py`, `collect_binance_api.py`, `collect_macro.py`, `collect_news.py`, `collect_defi.py`, `collect_etf_flows.py`, `collect_smart_money.py`, `collect_options.py`
- 분석: `analyze.py`
- 모니터링: `monitor_prices.py`, `monitor_risk.py`
- 실행: `execute_order.py`, `execute_dca.py`, `execute_rebalance.py`

### 14.2 코드 리뷰 & 수정 (2026-02-10~11)

5개 CRITICAL + 6개 WARNING 이슈 발견 후 수정.

**Phase 1 — Telegram 콜백 라우팅 (C1 + W6)**
- 문제: `inv_` 접두사 콜백이 InvestmentService에 도달하지 못함
- 수정:
  - `src/core/gateway.ts`: `registerHandler()` 메서드 추가 — 비-WebSocket 핸들러 등록
  - `src/channels/telegram.ts`: `inv_` 콜백 → `to: 'investment'`로 직접 라우팅
  - `src/investment/index.ts`: Gateway 핸들러 등록 + `handleGatewayMessage()` + `parseCallbackData()`

**Phase 2 — 주문 안전장치 (C3 + C4 + W3)**
- `execute_order.py`: MARKET 주문 시 Binance ticker API로 현재가 조회 후 est_value 검증
- `execute_dca.py`: `MAX_ORDER_USD` 한도 검증 추가
- `execute_rebalance.py`: 한도 초과 시 경고 메시지 포함 (silent skip 제거)

**Phase 3 — Claude AI 분석 통합 (C2)**
- `src/investment/analysis-engine.ts`: `analyzeWithClaude()` 추가 — `claude -p --model sonnet` spawn
- 분석 프롬프트: market_regime, overall_score(-100~+100), 매매 추천
- YAML frontmatter 파싱, 실패 시 raw JSON 요약으로 fallback

**Phase 4 — 기타 수정 (W1 + C5)**
- `db_utils.py`: `cleanup_old_research(days=30)` 추가 (분석 실행 시 자동 호출)
- `SKILL.md`: `collect_options.py` 설명을 "API-based (Deribit)"로 수정

### 14.3 userId 미스매치 버그 수정 (2026-02-11)

- 문제: Telegram 버튼 클릭 시 `userId`가 텔레그램 ID(`'123456789'`)로 전달되지만, 투자 데이터는 `'default'`로 저장됨 → 조회 결과 항상 비어있음
- 수정 (`src/investment/index.ts` `handleGatewayMessage()`):
  - `chatIdMap.set(this.userId, chatId)` — 내부 userId로 chatId 저장
  - `handleCallback(action, params, this.userId)` — 내부 userId로 데이터 조회

### 14.4 사용자 가이드 작성 (2026-02-11)

- `docs/INVESTMENT-USER-GUIDE.md` 작성
- 내용: 시작하기, Telegram 사용법, 브리핑, 포트폴리오, 분석, 위험 모니터링, Semi-Auto 매매, DCA, 리밸런싱, 데이터 소스, 스케줄, 안전장치, CLI 레퍼런스, 문제 해결

### 14.5 Finance Agent 자동 시작 통합 (2026-02-11)

- 문제: Finance Agent(`src/agents/finance/server.ts`)가 별도 프로세스로 수동 실행 필요 → A2A Orchestrator가 매분 health check 실패 경고
- 수정 (`src/index.ts`):
  - `FinanceAgentServer` import + 멤버 변수 추가
  - `start()`: HTTP Server 후 Finance Agent 자동 시작 (실패해도 계속 진행)
  - `stop()`: Finance Agent graceful shutdown 추가
- 결과: `pnpm start` 하나로 전체 서비스 시작, health check 경고 해소

### 14.6 분석 cron → Claude AI 라우팅 버그 수정 (2026-02-11)

- 문제: `daily_brief`/`weekly_deep` cron job이 `analyze.py`를 직접 실행 후 `handleJobResult()`에서 alerts만 처리 → `AnalysisEngine`의 Claude 분석 + DB 저장을 건너뜀 → `market_regime`, `overall_score` 항상 null
- 원인: 기존 3건의 분석 레코드는 Claude 통합 전에 생성 + cron 결과가 AnalysisEngine으로 라우팅되지 않음
- 수정:
  - `analysis-engine.ts`: `runAnalysis()`에서 보고서 처리를 `processReport()` 메서드로 분리
  - `index.ts`: `handleJobResult()`에서 `daily_brief`/`weekly_deep` → `this.analysis.processReport()` 라우팅 추가
- 검증: analyze.py → Claude CLI(`-p --model sonnet`) → YAML frontmatter 파싱 → DB 저장 (market_regime=risk_off, overall_score=-15) 정상 확인

---

## 미해결 이슈

### GitHub Issues (오래됨, 우선순위 낮음)
- [#1 — 1회 스케줄(setTimeout) 재시작 시 유실](https://github.com/ldmrepo/michael/issues/1)
- [#2 — 스케줄 마커 구분자(:) 충돌](https://github.com/ldmrepo/michael/issues/2)

### Investment Service 남은 작업
- **W2**: Telegram 텍스트 명령 미구현 ("포트폴리오 보여줘" 등 자연어)
- **W4**: FedWatch 브라우저 수집 미구현 (현재 FRED API만)
- **W5**: 브라우저 셀렉터 취약 (범용 CSS 클래스, 사이트 변경 시 깨짐)
- ~~**Finance Agent 자동 시작**~~: ✅ 14.5에서 해결
- ~~**분석 cron Claude AI 미연결**~~: ✅ 14.6에서 해결

---

## 2026-02-12 작업 내역

### 15.1 docs/ 정리 (완료, 커밋 `34f725c`)

- **삭제 9개**: 개발 과정 문서 (memory-porting-*, schema-migration-*, task2-*, vector-search-*, manager-modularization-*, 투자참조사이트 등)
- **이동 2개**: `docs/INVESTMENT-USER-GUIDE.md` → `docs/guides/`, `docs/PREDICTION-MARKET-USER-GUIDE.md` → `docs/guides/`
- **README.md**: 깨진 문서 링크 수정 (삭제/이동된 파일 → 새 경로)
- **ARCHITECTURE.md**: 날짜 업데이트
- **PROTOCOL_RESEARCH.md**: 상단에 "참고 자료" 노트 추가

최종 docs/ 구조:
```
docs/
├── API_vs_CLI.md
├── ARCHITECTURE.md
├── PROTOCOL_RESEARCH.md
└── guides/
    ├── INVESTMENT-USER-GUIDE.md
    └── PREDICTION-MARKET-USER-GUIDE.md
```

### 15.2 X (Twitter) 프로필 설정 + 첫 트윗 + 팔로우 (완료, 커밋 `bd17b5f`)

**프로필 설정** (Playwright 브라우저 자동화):
- 계정: `@idongmyeon67121` (이동명)
- Bio: "Software Developer | Building AI Agents & Web3 apps | TypeScript & Python | Sharing dev experiences and hard-won lessons"
- Location: Seoul, South Korea

**첫 트윗 게시** (KakaoTalk 봇 연결 경험 공유):
> Connected my AI to KakaoTalk via Open Builder today.
> Problem: 5s response limit, AI needs 10-60s.
> Solution: Callback API - return "thinking..." instantly, POST real answer async.
> Hidden gotcha: Callback toggle is buried in a kebab menu.
> #DevLog #AI #KakaoTalk

**개발자 10명 팔로우**:
@karpathy, @rauchg, @youyuxi, @dan_abramov, @addyosmani, @levelsio, @ThePrimeagen, @kentcdodds, @swyx, @t3dotgg

**X 스킬 전면 업데이트** (`.claude/skills/x/SKILL.md`):
- `/compose/post` 사용 금지 (파일 선택 모달 누적 버그)
- 홈 인라인 작성 + data-testid 셀렉터 + 오버레이 대응
- 팔로우 자동화 코드, 한국어 UI 매핑, 실전 교훈 6개

---

## 현재 상태 (2026-02-12)

### 서비스 구성

| 서비스 | 포트 | 프로토콜 | 상태 |
|--------|------|---------|------|
| Gateway | 18789 | WebSocket | 자동 (Michael 내장) |
| HTTP Server | 3000 | HTTP | 자동 (Michael 내장) |
| Telegram Bot | — | Polling | 자동 (Michael 내장) |
| KakaoTalk Bot | — | Callback API (ngrok) | 자동 (Michael 내장) |
| Investment Service | — | 내부 | 자동 (Michael 내장, 14 cron jobs) |
| Finance Agent | 8001 | HTTP (A2A) | 자동 (Michael 내장) |
| Web Frontend | 3001 | HTTP | 별도 실행 (`cd frontend && pnpm dev`) |

### Git 상태

- **브랜치**: main
- **최신 커밋**: `bd17b5f` - refactor: X 스킬 실전 검증 기반 전면 업데이트
- **원격**: 동기화 완료 (push 완료)
- **Working tree**: clean

### 시작 명령

```bash
# Michael 전체 서비스 (Gateway + HTTP + Telegram + Finance Agent + Investment)
pnpm build && pnpm start

# KakaoTalk 챗봇 (별도 터미널)
ngrok http 3000 --domain=roxy-exoskeletal-shayla.ngrok-free.dev

# Web Frontend (선택)
cd frontend && pnpm dev
```

### 환경 변수 (`.env`)

```bash
# 필수
TELEGRAM_BOT_TOKEN=xxx
BINANCE_API_KEY=xxx
BINANCE_API_SECRET=xxx

# 선택
GATEWAY_PORT=18789
HTTP_PORT=3000
EMBEDDING_PROVIDER=local
FRED_API_KEY=xxx
INVESTMENT_MAX_ORDER_USD=10000
INVESTMENT_PROPOSAL_EXPIRY_MIN=30
FINANCE_AGENT_URL=http://127.0.0.1:8001

# KakaoTalk
KAKAO_REST_API_KEY=xxx
KAKAO_BOT_ID=698dd7b4e9dbf31def3a1933
```

### 다음 작업 후보

- X 트윗 정기 게시 (개발 경험 공유 시리즈)
- Prediction Market 포트폴리오 모니터링/리밸런싱
- Investment Service 남은 이슈 (W2, W4, W5)

---

*마지막 업데이트: 2026-02-12*
