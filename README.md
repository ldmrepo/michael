# 마이클 (Michael)

> 24시간 깨어있는 AI 자산관리 전문가 — "눈덩이 굴리기(Snowball)"

## 특징

- 💰 **투자 서비스**: Binance 포트폴리오 자동 모니터링 (14개 cron job + Telegram 알림)
- 🎯 **예측 마켓**: Polymarket 자동 모니터링 (가격 추적, 고확률 스캔, 차익거래 감지)
- 🧠 **전문가 팀**: 14개 AI 전문가 에이전트가 역할/지침/도구/지식을 갖추고 협업
- 📊 **판단 사이클**: Gather Phase → State 갱신 → Claude 판단 → 승인 → 실행
- 📰 **투자 뉴스**: 시장 뉴스 자동 브리핑
- 🌙 **24시간 모니터링**: pm2/launchd 데몬으로 항상 실행
- 🧠 **영구 메모리**: 모든 대화와 투자 정보를 기억 (SQLite + 벡터 검색)
- 💬 **멀티 채널**: Telegram, 웹 채팅, REST API 지원
- ⏰ **능동적 알림**: 가격 변동, 기회 포착 시 즉시 알림
- 🤖 **Claude Code 기반**: Claude Code CLI 사용 (API 키 불필요)

## 중요: Claude Max vs Anthropic API

마이클은 **Claude Code CLI**를 사용하므로 **API 키가 필요 없습니다**.

- ✅ Claude Max 구독만으로 사용 가능
- ✅ 추가 비용 없음
- ✅ 즉시 사용 가능

자세한 내용은 [docs/API_vs_CLI.md](docs/API_vs_CLI.md) 참조

## 아키텍처

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Gateway (WebSocket) :18789                       │
└──┬──────────┬──────────┬──────────┬──────────┬─────────────────────┘
   │          │          │          │          │
┌──▼───┐ ┌───▼─────┐ ┌──▼─────┐ ┌─▼───────┐ ┌▼──────────────────────┐
│Tele- │ │ Claude  │ │Memory  │ │Scheduler│ │ Decision System       │
│gram  │ │ Agent   │ │(SQLite │ │ (Cron)  │ │ ├─JudgmentCycle       │
│      │ │         │ │+Vec)   │ │         │ │ ├─AgentRunner          │
└──────┘ └─────────┘ └────────┘ └─────────┘ │ │  └─14 전문가 에이전트│
                                             │ ├─StateStore (YAML)   │
                                             │ ├─Sentinel (감시)     │
                                             │ └─Knowledge (NLM)     │
                                             └────────────────────────┘
```

### 판단 사이클 흐름

```
cron trigger (morning/midday/evening/weekly/monthly)
  │
  ▼
JudgmentCycle.runCycle()
  ├─ 1. Mandate(위임장) 읽기
  ├─ 2. ★ Gather Phase — 전문가 팀 소집
  │     ├─ ROUTINE_AGENTS[routineType] → 소집 목록
  │     ├─ AgentRunner: Python 스크립트 병렬 실행
  │     └─ StatePopulator: 결과 → state.yaml / inputs.yaml 갱신
  ├─ 3. State/Inputs 최신값 읽기
  ├─ 4. Claude에게 판단 요청 (프롬프트)
  ├─ 5. [DECISION:...] 마커 파싱
  └─ 6. Telegram 승인 요청 → 사용자 승인 → 자동 실행
```

### 14개 전문가 에이전트

| 팀 | 에이전트 | 역할 | 도구 |
|----|----------|------|------|
| **정보 수집** | 시장 데이터 수집가 | 크립토/전통 시장 가격·거래량 수집 | `collect_market.py`, `collect_binance_api.py` |
| | 매크로 분석가 | 거시경제 지표 수집 (FRED) | `collect_macro.py` |
| | 뉴스 수집가 | 투자 뉴스 수집·sentiment 분류 | `collect_news.py` |
| | 온체인 분석가 | ETF 플로우, 고래 이동, 옵션 | `collect_etf_flows.py`, `collect_smart_money.py`, `collect_options.py`, `collect_defi.py` |
| | PM 스캐너 | Polymarket 마켓 탐색·기회 발견 | `scan_markets.py`, `monitor_prices.py` |
| **분석** | 기술 분석가 | 차트 패턴·기술 지표 분석 | `analyze.py` |
| | 리스크 관리자 | 포트폴리오 위험 평가·경고 | `monitor_risk.py`, `monitor_prices.py` |
| | PM 확률 분석가 | 예측시장 확률 추정·Kelly 계산 | `estimate_true_probability.py` |
| | 포트폴리오 분석가 | 통합 NAV·배분 상태 평가 | `sync_balance.py`, `snapshot_nav.py` |
| **실행** | Binance 트레이더 | Spot/Futures 주문 실행 | `execute_order.py` |
| | PM 트레이더 | Polymarket CLOB 매수/매도 | `polymarket_client.py` |
| | DCA 봇 | 정기 자동 매수 | `execute_dca.py` |
| | 리밸런서 | 목표 자산배분 복원 | `execute_rebalance.py` |

> 소셜 감시자 (X/Twitter)는 Playwright 인프라 별도 구축 필요 — 도구 미연결 상태

## 설치

```bash
# 백엔드 의존성 설치
pnpm install

# Python 의존성 (금융 데이터용)
pip3 install yfinance

# 환경 변수 설정
cp .env.example .env
# .env 파일을 편집하여 필요한 설정 입력
```

## 환경 변수

```bash
# 필수
TELEGRAM_BOT_TOKEN=<BotFather에서 발급받은 토큰>

# Gateway 설정
GATEWAY_PORT=18789
GATEWAY_HOST=127.0.0.1

# HTTP 서버 설정
HTTP_PORT=3000
WEBAPP_URL=https://your-domain.ngrok-free.dev

# ngrok (Mini App HTTPS용)
NGROK_AUTHTOKEN=<ngrok 인증 토큰>

# 투자 서비스 (선택)
BINANCE_API_KEY=<Binance API 키>
BINANCE_API_SECRET=<Binance API 시크릿>

# 예측 마켓 (선택)
POLYMARKET_ENABLED=true
POLYMARKET_PRIVATE_KEY=<EOA 프라이빗 키>  # 거래 실행 시만 필요

# 임베딩 설정 (선택)
EMBEDDING_PROVIDER=local  # local, openai, gemini

# 금융 데이터 (선택, fallback용)
ALPHA_VANTAGE_API_KEY=<무료 API 키>
```

## 실행

### 개발 모드

```bash
# 터미널 1: 백엔드 실행
pnpm dev

# 터미널 2: Finance Agent (선택)
pnpm dev:finance
```

### 서비스 포트

| 서비스 | 포트 | 설명 |
|--------|------|------|
| HTTP Server | 3000 | REST API |
| Gateway | 18789 | WebSocket 허브 |
| Finance Agent | 8001 | A2A 금융 에이전트 |

### 프로덕션 빌드

```bash
# TypeScript 빌드
pnpm build

# 빌드된 파일 실행
pnpm start
```

### 데몬 모드 (24시간 실행)

#### pm2 (권장)

```bash
# pm2 설치
npm install -g pm2

# 서비스 시작
pm2 start ecosystem.config.cjs

# 상태 확인 / 로그 보기
pm2 status
pm2 logs michael

# 재시작 / 중지
pm2 restart michael
pm2 stop michael
```

#### launchd (macOS)

```bash
# 데몬 설치
bash scripts/install-daemon.sh

# 상태 확인
launchctl list | grep michael

# 로그 확인
bash scripts/logs.sh          # stdout 로그
bash scripts/logs.sh error    # stderr 로그

# 데몬 제거
bash scripts/uninstall-daemon.sh
```

## 프로젝트 구조

```
michael/
├── src/
│   ├── core/              # Gateway, HTTP Server, SSE, AG-UI Events
│   ├── brain/             # Memory (SQLite + 벡터 검색)
│   ├── channels/          # Telegram, Web Channel
│   ├── scheduler/         # Cron 스케줄러
│   ├── agent/             # Claude Code Agent
│   ├── decision/          # 판단 시스템
│   │   ├── agent-registry.ts    # 14개 전문가 에이전트 4요소 정의
│   │   ├── routine-agents.ts    # 루틴별 소집 매핑
│   │   ├── agent-runner.ts      # 스크립트 오케스트레이션 엔진
│   │   ├── judgment-cycle.ts    # 5단계 판단 루프
│   │   ├── judgment-prompt.ts   # 판단 프롬프트 빌더
│   │   └── decision-executor.ts # 승인된 결정 실행기
│   ├── state-store/       # YAML 기반 상태 관리
│   │   ├── state-populator.ts   # Python 결과 → YAML 변환
│   │   └── types.ts             # Mandate, State, Inputs, Decision 타입
│   ├── sentinel/          # 실시간 감시 (가격 급변 등)
│   ├── knowledge/         # NLM 노트북 지식 관리
│   │   ├── knowledge-manager.ts # 에이전트별 노트북 관리
│   │   ├── init-agent-knowledge.ts # 노트북 자동 부트스트랩
│   │   └── nlm-client.ts       # NLM CLI 래퍼
│   ├── investment/        # Binance 투자 모니터링 서비스
│   ├── prediction-market/ # Polymarket 예측 마켓 모니터링
│   ├── agents/            # 특화 에이전트
│   │   ├── base/          # BaseA2UIAgentExecutor
│   │   └── finance/       # Finance Agent (A2A 서버)
│   ├── memory-new/        # 벡터 임베딩 시스템
│   ├── a2ui/              # A2UI 타입 및 유틸리티
│   └── a2a/               # A2A 프로토콜
├── .claude/
│   └── skills/            # Claude Code 스킬 (자산관리 특화)
│       ├── investment/              # Binance 투자 스크립트
│       ├── prediction-market/       # Polymarket 스크립트
│       ├── finance/                 # 주식/코인/환율
│       ├── news/                    # 투자 뉴스 브리핑
│       ├── x/                       # 시장 심리 분석 (Twitter)
│       └── ...                      # a2a, a2ui, agui 등
├── data/
│   ├── memory.db          # 메인 DB (users, messages, facts, schedules)
│   ├── memory-index.db    # 벡터 인덱스 DB (embeddings, chunks)
│   └── state/             # YAML 상태 파일
│       ├── mandate.yaml   # 위임장 (투자 규칙)
│       ├── state.yaml     # 포트폴리오 현재 상태
│       ├── inputs.yaml    # 시장 분석 입력
│       └── decisions/     # 결정 기록
└── docs/
```

## 테스트

```bash
# 모든 테스트 실행
pnpm test

# 특정 모듈 테스트
pnpm vitest run src/decision/        # 판단 시스템 (43 tests)
pnpm vitest run src/brain/memory.test.ts
pnpm vitest run src/core/gateway.test.ts

# 통합 테스트 (임베딩 프로바이더 필요)
INTEGRATION_TESTS=true pnpm vitest run src/brain/memory.integration.test.ts
```

## 사용법

### Telegram으로 사용하기

1. Telegram에서 BotFather로 봇 생성
2. `.env`에 `TELEGRAM_BOT_TOKEN` 설정
3. 마이클 실행
4. Telegram에서 봇과 대화

```
/start - 시작
/help - 도움말
"비트코인 현재가" - 시세 조회
"포트폴리오 현황" - Binance 포트폴리오
"PM 브리핑" - Polymarket 포지션 요약
"매일 9시에 브리핑 보내줘" - 스케줄 설정
```

### 자동 판단 루틴

`mandate.yaml` 설정 시 자동 활성화:

| 루틴 | 시간 | 소집 에이전트 | 목적 |
|------|------|---------------|------|
| 아침 | 08:00 | 7개 (풀 소집) | 밤새 변화 파악 + 기회 포착 |
| 낮 | 14:00 | 3개 (경량) | 포트폴리오·가격·리스크 점검 |
| 저녁 | 21:00 | 4개 | 하루 마감 + 리스크 정리 |
| 주간 | 월 09:00 | 10개 (심층) | 주간 성과 리뷰 + 온체인 |
| 월간 | 1일 09:00 | 6개 | 월간 KPI 분석 + NAV 스냅샷 |

### 투자 서비스 (Telegram 자동 알림)

Binance API 키와 Polymarket이 설정되면 자동으로 모니터링이 시작됩니다:

**Binance Investment (14개 cron job)**
- 포트폴리오 스냅샷 (4시간마다)
- 가격 변동 감시 (10분마다, 5%+ 알림)
- RSI/MA 기술 분석 (1시간마다)
- 일일 브리핑 (매일 9시)

**Prediction Market (5개 cron job)**
- 고확률 마켓 스캔 (6시간마다)
- 신규 마켓 감지 (4시간마다)
- 가격 변동 추적 (15분마다, 5%+ 알림)
- 차익거래 감지 (2시간마다)
- 일일 브리핑 (매일 9시)

**Telegram 콜백 버튼:**
- `inv_portfolio` / `pm_portfolio` - 포트폴리오 요약
- `inv_brief` / `pm_brief` - 수동 브리핑
- `pm_scan` - 고확률 마켓 스캔
- `pm_watchlist` - 워치리스트

### 금융 정보 질문 예시

```
"비트코인 현재가 알려줘"
"애플 주가"
"삼성전자 시세"
"이더리움 가격"
"달러 환율"
"NVDA 주식 정보"
```

**지원하는 금융 데이터:**

| 종류 | 예시 | 데이터 소스 |
|------|------|------------|
| 미국 주식 | AAPL, MSFT, NVDA, TSLA | yfinance |
| 한국 주식 | 005930.KS (삼성전자) | yfinance |
| 암호화폐 | bitcoin, ethereum, solana | CoinGecko |
| 환율 | USD/KRW, EUR/USD | Frankfurter |

### WebSocket으로 직접 연결

```bash
# wscat 설치
npm install -g wscat

# Gateway 연결
wscat -c ws://127.0.0.1:18789

# 메시지 전송
> {"from": "cli", "to": "agent", "userId": "test", "content": "Hello Michael"}
```

### REST API로 직접 호출

```bash
# SSE 스트리밍 (AG-UI)
curl -X POST http://localhost:3000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "안녕 마이클", "userId": "test"}'

# JSON 응답 (비스트리밍)
curl -X POST http://localhost:3000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "비트코인 현재가", "userId": "test"}'
```

### Finance Agent A2A 호출

```bash
# Finance Agent 시작
pnpm dev:finance

# Agent Card 조회
curl http://localhost:8001/.well-known/agent.json

# A2A JSON-RPC 호출
curl -X POST http://localhost:8001/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"type": "text", "text": "삼성전자 주가"}]
      }
    }
  }'
```

## 로드맵

### 인프라 (완료)

- [x] Memory System (SQLite + FTS5 + 벡터 검색)
- [x] Gateway Server (WebSocket) + HTTP Server
- [x] Claude Code Agent (CLI) + Scheduler (node-cron)
- [x] Telegram 통합 + 웹 프론트엔드 (Next.js + AG-UI + A2UI)
- [x] 데몬화 (launchd/pm2)
- [x] A2A 프로토콜 (멀티 에이전트)

### 자산관리 (완료)

- [x] Finance Agent (실시간 금융 데이터 - yfinance, CoinGecko)
- [x] Investment Service (Binance 포트폴리오 자동 모니터링)
- [x] Prediction Market (Polymarket 자동 모니터링 + 알림)
- [x] 범용 비서 → 자산관리 전문가 전환

### 판단 시스템 (완료)

- [x] State Store (YAML 기반 포트폴리오 상태 관리)
- [x] Judgment Cycle (5단계 판단 루프)
- [x] Sentinel (실시간 감시 + 긴급 트리거)
- [x] Knowledge (NLM 노트북 지식 관리)
- [x] 에이전트 4요소 체계 (14개 전문가 역할/지침/도구/지식)
- [x] 에이전트 오케스트레이션 (Gather Phase + AgentRunner)

### 진행 예정

- [ ] PM 자동 거래 실행 자동화
- [ ] Binance Futures 자동 전략 실행
- [ ] 포트폴리오 리밸런싱 엔진
- [ ] 크로스 플랫폼 차익거래 (PM ↔ Binance)
- [ ] 소셜 감시자 (X/Twitter Playwright 연동)
- [ ] 프로덕션 배포 (실제 도메인 + SSL)

## 문서

- [API vs CLI 비교](docs/API_vs_CLI.md)
- [시스템 아키텍처](docs/ARCHITECTURE.md)
- [아키텍처 레이어](docs/ARCHITECTURE-LAYERS.md)
- [자산관리 컨셉](docs/ASSET-MANAGER-CONCEPT.md)
- [프로토콜 리서치](docs/PROTOCOL_RESEARCH.md)
- [투자 서비스 가이드](docs/guides/INVESTMENT-USER-GUIDE.md)
- [예측 마켓 가이드](docs/guides/PREDICTION-MARKET-USER-GUIDE.md)

## License

MIT
