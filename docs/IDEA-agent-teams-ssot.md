# 마이클 진화 설계서: Agent Teams + SSoT 기반 전문가 시스템

> **목표**: 마이클을 "범용 AI 어시스턴트"에서 "전문가 팀을 지휘하는 AI 오케스트레이터"로 진화시킨다.
> **핵심 원칙**: 에이전트에게 원시 데이터를 밀어넣는(Push) 방식에서, 통제된 지식 엔진으로부터 정제된 정보를 끌어오는(Pull) 구조로 전환한다.

---

## 1. 현재 마이클의 한계

### 1.1 단일 두뇌 구조의 병목

```
사용자 요청 → 마이클 (단일 Claude 세션) → 응답
```

현재 마이클은 하나의 Claude Code 세션이 모든 역할을 수행한다:
- 시장 분석, 리스크 평가, 주문 실행, 뉴스 수집을 한 세션에서 순차 처리
- 컨텍스트 윈도우에 모든 정보가 뒤섞여 "맥락적 노이즈" 발생
- 스킬(SKILL.md)은 실행 도구만 제공할 뿐, 정제된 지식을 제공하지 않음

### 1.2 구체적 문제점

| 문제 | 원인 | 결과 |
|------|------|------|
| 정보 노이즈 | 웹 검색 + API 결과가 컨텍스트에 무분별 축적 | 토큰 낭비, 응답 품질 저하 |
| 전문성 부재 | 하나의 프롬프트가 모든 도메인을 커버 | 깊이 없는 범용적 답변 |
| 지식 휘발 | 세션 종료 시 분석 맥락 소멸 | 매번 처음부터 분석 반복 |
| 순차 처리 | 시장 분석 → 리스크 평가 → 실행이 직렬 | 응답 지연 (복잡 작업 시 1분+) |

---

## 2. 제안: 3중 아키텍처 (Agent Teams + Skills + NotebookLM)

### 2.1 비전

```
사용자 "리밸런싱 해줘"
    ↓
마이클 (Team Lead / Orchestrator)
    ↓ 복잡도 판단 → Agent Team 가동
    │
    ├─→ 시장분석 에이전트 ←── Skills (실행 도구) + NotebookLM (정제된 지식)
    ├─→ 리스크관리 에이전트 ←── Skills (실행 도구) + NotebookLM (정제된 지식)
    └─→ 주문실행 에이전트 ←── Skills (실행 도구) + NotebookLM (정제된 지식)
    │
    ├── 에이전트 간 메시지 교환 (상호 견제)
    ├── 공유 태스크 리스트 (작업 조율)
    └── Persistent Memory (경험 축적)
    ↓
전문가급 종합 솔루션
```

### 2.2 3중 레이어 정의

| 레이어 | 역할 | 기술 | 비유 |
|--------|------|------|------|
| **Skills** | 실행 능력 (손과 발) | `.claude/skills/` 스크립트 | 도구를 사용하는 능력 |
| **NotebookLM** | 지식 능력 (제2의 두뇌) | NotebookLM SSoT 쿼리 | 교과서와 참고서 |
| **Agent Teams** | 협업 능력 (팀워크) | Claude Code Agent Teams | 전문가 회의실 |

**추가 레이어:**
| 레이어 | 역할 | 기술 |
|--------|------|------|
| **Persistent Memory** | 학습 능력 | `.claude/agent-memory/` |

---

## 3. Claude Code 기능 매핑

### 3.1 Custom Subagents (`.claude/agents/`)

각 전문가를 마크다운 파일로 정의한다. 핵심은 `skills` 필드로 SSOT 지식을 프리로드하고, `memory`로 경험을 축적하는 것이다.

```yaml
# .claude/agents/market-analyst.md
---
name: market-analyst
description: |
  암호화폐 시장 분석 전문가. 시장 데이터 수집, 가격 트렌드 분석,
  펀딩비/롱숏비율/OI 분석, 매크로 지표 해석 시 사용.
tools: Bash, Read, Grep, Glob
model: sonnet
skills:
  - investment              # 바이낸스 API SSOT
  - binance-analytics       # 시장 분석 데이터 SSOT
  - crypto-investment-sources  # 정보원 SSOT
memory: project             # 분석 패턴 축적
---

당신은 암호화폐 시장 분석 전문가입니다.

## 분석 프로토콜
1. 바이낸스 API로 실시간 데이터 수집 (가격, 펀딩비, OI, 롱숏비율)
2. NotebookLM "투자분석" 노트북에서 과거 패턴 및 매크로 분석 쿼리
3. 기술적/펀더멘탈 종합 판단 제공
4. memory에서 과거 분석 결과를 참고하여 정확도 향상

## 출력 형식
- 시장 상태 (강세/약세/횡보)
- 핵심 지표 요약
- 단기/중기 전망
- 신뢰도 (높음/중간/낮음) + 근거
```

### 3.2 전문가 에이전트 설계

#### 에이전트 1: market-analyst (시장 분석가)

| 항목 | 설정 |
|------|------|
| 프리로드 스킬 | investment, binance-analytics, crypto-investment-sources |
| 도구 | Bash, Read, Grep, Glob |
| 모델 | sonnet (비용 효율) |
| 메모리 | project (분석 패턴 축적) |
| NotebookLM 노트북 | "투자분석" — 매크로 데이터, 시장 사이클, 과거 패턴 |

#### 에이전트 2: risk-manager (리스크 관리자)

| 항목 | 설정 |
|------|------|
| 프리로드 스킬 | investment, binance-futures-advanced |
| 도구 | Bash, Read, Grep, Glob |
| 모델 | sonnet |
| 메모리 | project (리스크 이벤트 기록) |
| NotebookLM 노트북 | "리스크관리" — SL/TP 전략, 포지션 사이징, 과거 손실 교훈 |

#### 에이전트 3: trade-executor (거래 실행자)

| 항목 | 설정 |
|------|------|
| 프리로드 스킬 | investment, binance-futures-advanced, prediction-market |
| 도구 | Bash, Read, Grep, Glob, Write |
| 모델 | sonnet |
| 메모리 | project (거래 이력) |
| hooks | PreToolUse: 주문 전 리스크 체크 스크립트 실행 |

#### 에이전트 4: news-researcher (뉴스 리서처)

| 항목 | 설정 |
|------|------|
| 프리로드 스킬 | crypto-investment-sources, news, x |
| 도구 | Bash, Read, WebSearch, WebFetch |
| 모델 | haiku (빠른 수집, 비용 절감) |
| 메모리 | project |
| NotebookLM 노트북 | "시장뉴스" — 검증된 뉴스 소스, 과거 이벤트 영향 분석 |

### 3.3 Skills = SSOT (통제된 진실의 원천)

현재 보유한 스킬이 각 에이전트의 SSOT 역할을 한다:

```
.claude/skills/
  ├── investment/SKILL.md              → 바이낸스 API 사용법, 스크립트 실행법
  ├── binance-futures-advanced/        → 선물 주문 유형, 마진/레버리지 설정
  ├── binance-analytics/               → Smart Money, 옵션, 펀드 플로우
  ├── prediction-market/               → Polymarket CLOB API, 포지션 관리
  ├── crypto-investment-sources/       → 정보원 레퍼런스 (뉴스, 온체인, 매크로)
  ├── finance/                         → 실시간 시세 조회
  └── news/                            → 뉴스 브리핑 생성
```

**에이전트의 `skills` 필드로 프리로드하면:**
- 에이전트 시작 시 해당 스킬 *전체 내용*이 컨텍스트에 주입됨
- 에이전트는 "자기 분야의 진실"을 확실히 알고 시작
- 웹 검색 없이도 정확한 API 호출, 스크립트 실행 가능

### 3.4 NotebookLM = 제2의 두뇌 (정제된 지식)

Skills가 "실행 방법"을 알려준다면, NotebookLM은 "판단 근거"를 제공한다.

#### 노트북 설계

| 노트북 | 용도 | 소스 예시 |
|--------|------|-----------|
| 투자분석 | 매크로, 시장 사이클, 기술적 분석 패턴 | Fed 정책 분석, BTC 사이클 연구, 온체인 지표 해석 |
| 리스크관리 | 포지션 사이징, SL/TP 전략, 과거 교훈 | 청산 사례 분석, 켈리 공식, 리스크/리워드 가이드 |
| 시장뉴스 | 검증된 뉴스 소스, 이벤트 임팩트 | CPI/FOMC 영향 분석, 규제 이벤트 히스토리 |
| 보안핸드북 | API 키 관리, 거래소 보안, 스마트컨트랙트 | OWASP, CVE, 거래소 해킹 사례 |
| 코드베이스 | 마이클 아키텍처, 스킬 구조 | Repomix 패키징된 소스코드, ADR(아키텍처 결정 기록) |

#### 이단계 검색 프로세스

```
에이전트가 판단 필요 시:
  1단계: 관련 리소스 식별 → NotebookLM에 업로드 (필요 시)
  맥락 초기화: 리서치 잔재 제거
  2단계: NotebookLM에 정제된 쿼리 → Gemini가 종합한 핵심 결과만 수신
```

#### CLI vs MCP 선택

| 항목 | CLI (`nlm`) | MCP (`notebooklm-mcp`) |
|------|-------------|------------------------|
| 토큰 효율 | 높음 (필요한 결과만 반환) | 낮음 (29개 도구 컨텍스트 점유) |
| 장기 작업 안정성 | 높음 | 세션 의존적 |
| 설정 복잡도 | 낮음 (`nlm setup`) | 중간 |
| 실시간 상호작용 | 보통 | 높음 |

**권장: CLI 우선, 필요 시 MCP 보조** — nlm.md의 제안과 동일

---

## 4. 작동 시나리오

### 시나리오 1: "전체 리밸런싱 해줘" (복잡 — Agent Team)

```
동명님: "전체 리밸런싱 해줘"
    ↓
마이클 (Lead, delegate mode):
  "복잡한 작업 → Agent Team 가동"
    │
    ├─ Task 1 → market-analyst
    │   ├── 바이낸스 API: BTC/ETH/SOL 실시간 데이터 수집
    │   ├── NotebookLM "투자분석": 현재 시장 사이클 판단 쿼리
    │   ├── 펀딩비, 롱숏비율, OI 분석
    │   └── 결론: "BTC 단기 강세, SOL 과매수, ETH 중립"
    │
    ├─ Task 2 → risk-manager
    │   ├── 현재 포지션 조회 (3개 롱 포지션)
    │   ├── NotebookLM "리스크관리": 적정 포지션 사이징 쿼리
    │   ├── 각 포지션 리스크/리워드 계산
    │   └── 결론: "SOL SL 타이트닝 필요, BTC 추가 가능, 총 리스크 15% 이하 유지"
    │
    ├─ Task 3 → news-researcher
    │   ├── 최근 24시간 주요 뉴스 수집
    │   ├── NotebookLM "시장뉴스": 이벤트 임팩트 분석
    │   └── 결론: "FOMC 의사록 발표 예정 — 단기 변동성 주의"
    │
    ├─ 에이전트 간 메시지 교환:
    │   market-analyst → risk-manager: "SOL 과매수, 비중 축소 추천"
    │   risk-manager → market-analyst: "동의, SL $86으로 타이트닝"
    │   news-researcher → all: "FOMC 전 신규 포지션 자제 추천"
    │
    └─ 마이클 (Lead) 종합:
        "시장분석 + 리스크평가 + 뉴스를 종합한 리밸런싱 안"
        → 동명님에게 전문가급 제안 전달
```

### 시나리오 2: "잔고 조회해줘" (단순 — 직접 처리)

```
동명님: "잔고 조회해줘"
    ↓
마이클: "단순 작업 → 직접 처리"
    → investment 스킬의 binance_client.py 실행
    → 결과 포맷팅 후 응답
    (Agent Team 가동하지 않음 — 과잉)
```

### 시나리오 3: "BTC 전망 분석해줘" (중간 — Subagent 위임)

```
동명님: "BTC 전망 분석해줘"
    ↓
마이클: "중간 복잡도 → market-analyst 서브에이전트 위임"
    → market-analyst가 독립 컨텍스트에서 분석
    → 결과만 마이클에게 반환
    → 포맷팅 후 동명님에게 전달
```

---

## 5. 복잡도 기반 자동 분기 (Smart Routing)

모든 요청에 팀을 가동하면 비용 과잉이므로, 복잡도에 따라 자동 분기한다:

```
사용자 요청
    ↓
마이클 (복잡도 판단)
    │
    ├─ Level 1 (단순): 직접 처리
    │   예: "잔고 조회", "날씨", "일정 확인"
    │   방식: 스킬 직접 호출
    │   비용: 1x (기본)
    │
    ├─ Level 2 (중간): 서브에이전트 1~2개 위임
    │   예: "BTC 분석해줘", "포지션 리스크 체크"
    │   방식: 전문가 서브에이전트에 위임, 결과만 반환
    │   비용: 2~3x
    │
    └─ Level 3 (복잡): Agent Team 가동
        예: "전체 리밸런싱", "투자 전략 수립", "포트폴리오 최적화"
        방식: 3~4개 에이전트 팀 + NotebookLM 쿼리 + 상호 토론
        비용: 5~7x
        품질: 전문가급
```

### 판단 기준

| 기준 | Level 1 | Level 2 | Level 3 |
|------|---------|---------|---------|
| 도메인 수 | 1개 | 1~2개 | 3개+ |
| 판단 필요 | 없음 (데이터 조회) | 단일 관점 | 다중 관점 종합 |
| 상호 의존성 | 없음 | 낮음 | 높음 (견제 필요) |
| 리스크 | 낮음 | 중간 | 높음 (자금 이동) |
| 예상 시간 | 10~30초 | 30~60초 | 1~3분 |

---

## 6. NotebookLM 통합 설계

### 6.1 지식 동기화 워크플로우

```
구현 계획 수립
    ↓
구현 및 빌드 검증
    ↓
결정 사항의 NotebookLM 업데이트  ← 선순환
    ↓
다음 작업에서 업데이트된 지식 참조
```

### 6.2 Repomix를 활용한 코드베이스 패키징

마이클의 소스코드를 AI 친화적 형태로 변환하여 NotebookLM에 업로드:

```bash
# Repomix로 코드베이스를 단일 파일로 패키징
repomix --output michael-codebase.txt

# NotebookLM에 업로드
nlm source add <notebook-id> --file michael-codebase.txt
```

에이전트는 파일 시스템을 직접 탐색하는 대신, NotebookLM에서 구조화된 코드 이해를 얻음.

### 6.3 멀티 에이전트 SSoT 공유

```
market-analyst ──┐
risk-manager ────┤── 동일한 NotebookLM Notebook ID 참조
trade-executor ──┤
news-researcher ─┘

→ 한 에이전트가 업데이트한 "결정 로그"를
  다른 에이전트가 즉시 참조 가능
```

---

## 7. Persistent Memory (경험 축적)

각 에이전트는 `memory: project` 설정으로 대화가 끝나도 학습 내용을 유지한다:

```
.claude/agent-memory/
  ├── market-analyst/
  │   └── MEMORY.md    ← "SOL 롱숏비율 70% 초과 시 과매수 신호"
  ├── risk-manager/
  │   └── MEMORY.md    ← "XRP -$186 청산: SL 미설정이 원인"
  └── trade-executor/
      └── MEMORY.md    ← "Algo 주문은 별도 API 조회 필요"
```

시간이 지날수록 각 에이전트는:
- 과거 분석 패턴을 기억하고
- 실수를 반복하지 않으며
- 점점 더 정확한 판단을 내림

---

## 8. 품질 보증: Hooks

### 8.1 거래 실행 전 리스크 체크

```yaml
# trade-executor의 hooks 설정
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/validate-trade.sh"
```

`validate-trade.sh`:
- 포지션 사이즈가 계좌의 30% 초과 시 차단
- SL 미설정 주문 차단
- 동일 방향 3개 이상 포지션 시 경고

### 8.2 팀 작업 완료 시 검증

```yaml
# settings.json
hooks:
  TaskCompleted:
    - hooks:
        - type: command
          command: "./scripts/verify-analysis.sh"
```

분석 결과에 필수 항목(시장 판단, 리스크 평가, 근거) 누락 시 반려.

---

## 9. 구현 로드맵

### Phase 1: Custom Subagents + Skills SSOT (즉시 가능)

- `.claude/agents/`에 4개 전문가 에이전트 정의
- 기존 스킬을 SSOT로 프리로드 (`skills` 필드)
- `memory: project`로 영속적 학습 활성화
- 단일 세션에서 서브에이전트 위임 테스트

**예상 효과**: 전문성 분리, 컨텍스트 오염 방지
**비용 영향**: 기존 대비 2~3x (서브에이전트 호출 시)

### Phase 2: NotebookLM 통합 (1~2주)

- `notebooklm-mcp-cli` 설치 및 인증
- 5개 전문 노트북 생성 (투자분석, 리스크관리, 시장뉴스, 보안핸드북, 코드베이스)
- 각 에이전트의 프롬프트에 NotebookLM 쿼리 프로토콜 추가
- Repomix로 코드베이스 패키징 → 코드베이스 노트북 업로드

**예상 효과**: 할루시네이션 감소, 판단 근거 강화
**비용 영향**: NotebookLM 무료, nlm CLI 토큰 비용 미미

### Phase 3: Agent Teams 활성화 (2~3주)

- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` 활성화 (이미 설정됨)
- 복잡도 기반 Smart Routing 로직 구현
- Agent Team 시나리오 테스트 (리밸런싱, 전략 수립)
- Hooks로 품질 게이트 적용
- delegate mode 테스트

**예상 효과**: 복잡 작업에서 전문가급 품질
**비용 영향**: 복잡 작업 시 5~7x (단순 작업은 변화 없음)

### Phase 4: 텔레그램 통합 (3~4주)

- 마이클의 `claude -p` CLI 호출에서 Agent Teams 자동 트리거
- 텔레그램에서 "리밸런싱 해줘" → 자동으로 팀 가동
- 진행 상황을 텔레그램으로 스트리밍 (AG-UI 이벤트)
- 최종 결과를 텔레그램 포맷으로 전달

**예상 효과**: 엔드투엔드 자동화
**기술 과제**: CLI 모드에서 Agent Teams 프로그래밍적 트리거

---

## 10. 기술적 제약 및 대응

| 제약 | 영향 | 대응 |
|------|------|------|
| Agent Teams = Experimental | 안정성 이슈 가능 | Phase 1의 Subagent로 대부분 커버, Teams는 복잡 작업만 |
| 세션 복원 불가 | 팀 상태 유실 | 태스크 리스트 + Memory로 상태 보존 |
| 중첩 팀 불가 | 에이전트가 하위 팀 생성 불가 | Lead가 모든 팀원 직접 관리 |
| 토큰 비용 증가 | 팀원 수 × 별도 세션 | Smart Routing으로 복잡 작업만 팀 가동 |
| NotebookLM 비공식 API | API 변경 위험 | CLI 래퍼로 추상화, 변경 시 래퍼만 수정 |
| 같은 파일 동시 편집 | 충돌 위험 | 에이전트별 담당 파일 분리 |

---

## 11. 기대 효과

### Before (현재)
```
마이클 (범용 AI)
  → 모든 걸 혼자 하는 "만능 인턴"
  → 넓지만 얕은 지식
  → 세션마다 리셋
```

### After (목표)
```
마이클 (AI 오케스트레이터)
  → 전문가 팀을 지휘하는 "시니어 매니저"
  → 각 분야 깊은 전문성 (SSOT)
  → 경험이 축적되는 학습 시스템
  → 통제된 지식에 기반한 신뢰할 수 있는 판단
```

### 정량적 기대

| 지표 | 현재 | 목표 |
|------|------|------|
| 복잡 분석 정확도 | ~70% (추정) | 90%+ (SSOT + 다중 관점) |
| 할루시네이션 비율 | 보통 | 최소화 (NotebookLM 근거 기반) |
| 복잡 작업 응답 시간 | 1~3분 (순차) | 1~2분 (병렬, 품질은 대폭 향상) |
| 지식 재사용률 | 0% (세션 리셋) | 80%+ (Memory + NotebookLM) |
| 리스크 사고 빈도 | 간헐적 (SL 누락 등) | 최소화 (Hooks 자동 검증) |

---

## 12. 결론

이 설계는 마이클을 세 가지 차원에서 진화시킨다:

1. **실행 → 전문성**: Skills SSOT로 각 에이전트가 자기 분야의 전문가로 시작
2. **추측 → 근거**: NotebookLM으로 통제된 지식에 기반한 판단
3. **개인 → 팀**: Agent Teams로 다중 관점 종합 + 상호 견제

핵심은 "모든 요청에 팀 가동"이 아닌, **복잡도 기반 Smart Routing**으로 비용과 품질의 최적점을 찾는 것이다. 단순 작업은 빠르게, 복잡 작업은 전문가급으로.

> *"단순히 도구를 사용하는 AI"에서 "지식을 갖춘 전문가 팀을 지휘하는 AI"로의 전환*

---

*작성일: 2026-02-15*
*버전: 1.0*
*작성: 마이클 (Claude Code Agent)*
