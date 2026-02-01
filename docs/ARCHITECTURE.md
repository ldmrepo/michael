# Michael 시스템 아키텍처

## 개요

Michael은 24시간 깨어있는 개인 AI 어시스턴트입니다. Hub-and-Spoke 아키텍처를 채택하여 Gateway가 중앙 메시지 허브 역할을 하고, 각 컴포넌트가 WebSocket으로 연결됩니다.

---

## 전체 시스템 구조

```mermaid
graph TB
    subgraph External["외부 서비스"]
        TG[Telegram API]
        NGROK[ngrok Tunnel]
        CLAUDE[Claude CLI]
    end

    subgraph HTTP["HTTP Layer :3000"]
        HS[HTTP Server]
        STATIC["/webapp/* Static Files"]
        API["/api/* REST API"]
        HEALTH["/health"]
    end

    subgraph Core["Core Layer :18789"]
        GW[Gateway<br/>WebSocket Hub]
    end

    subgraph Channels["Channels"]
        TC[Telegram Channel]
        WC[Web Channel]
    end

    subgraph Brain["Brain"]
        MEM[(Memory<br/>SQLite)]
        VEC[(Vector Index<br/>sqlite-vec)]
    end

    subgraph Services["Services"]
        AGENT[Claude Agent]
        SCHED[Scheduler]
        WEBAPP[WebApp Manager]
    end

    subgraph UI["UI Layer"]
        MINIAPP[Telegram Mini App<br/>React]
    end

    %% External connections
    TG <-->|Polling| TC
    NGROK -->|HTTPS| HS
    CLAUDE <-->|Subprocess| AGENT

    %% HTTP connections
    HS --> STATIC
    HS --> API
    HS --> HEALTH
    MINIAPP -->|fetch| API

    %% Gateway connections
    TC <-->|WebSocket| GW
    WC <-->|WebSocket| GW
    AGENT <-->|Direct| GW
    SCHED -->|Broadcast| GW

    %% Brain connections
    AGENT --> MEM
    AGENT --> VEC
    TC --> WEBAPP
    WEBAPP --> MEM

    %% Scheduler
    SCHED --> MEM
```

---

## 컴포넌트 상세

### 1. Gateway (WebSocket Hub)

중앙 메시지 라우터로서 모든 컴포넌트 간 통신을 중재합니다.

```mermaid
graph LR
    subgraph Gateway["Gateway :18789"]
        WS[WebSocket Server]
        ROUTER[Message Router]
        CLIENTS[Client Registry]
    end

    TC[Telegram] -->|connect| WS
    WC[Web] -->|connect| WS
    WS --> ROUTER
    ROUTER -->|route| CLIENTS
    CLIENTS -->|to: agent| AGENT[Agent]
    CLIENTS -->|to: telegram| TC
    CLIENTS -->|broadcast| ALL[All Clients]
```

**메시지 프로토콜:**
```typescript
interface GatewayMessage {
  from: 'telegram' | 'web' | 'scheduler' | 'agent';
  to: 'agent' | 'telegram' | 'web' | 'broadcast';
  userId: string;
  content: string;
  metadata?: {
    chatId?: number;
    eventType?: string;  // AG-UI event
    runId?: string;
    // ...
  };
}
```

### 2. HTTP Server

Mini App 서빙과 REST API를 담당합니다.

```mermaid
graph TB
    subgraph HTTPServer["HTTP Server :3000"]
        EXPRESS[Express App]

        subgraph Routes["Routes"]
            R1["GET /health"]
            R2["GET /.well-known/agent.json"]
            R3["GET /api/webapp/session/:id"]
            R4["POST /api/webapp/session/:id"]
            R5["GET /webapp/*"]
        end
    end

    EXPRESS --> R1
    EXPRESS --> R2
    EXPRESS --> R3
    EXPRESS --> R4
    EXPRESS --> R5

    R3 --> WAM[WebApp Manager]
    R4 --> WAM
    R5 --> DIST[dist/webapp/]
```

### 3. Telegram Channel

Telegram Bot API와 통신하고 Mini App을 관리합니다.

```mermaid
graph TB
    subgraph TelegramChannel["Telegram Channel"]
        BOT[Telegraf Bot]
        POLL[Manual Polling]
        HANDLERS[Message Handlers]
        RENDERER[A2UI Renderer]
        WAM[WebApp Manager]
    end

    TGAPI[Telegram API] <-->|getUpdates| POLL
    POLL --> BOT
    BOT --> HANDLERS

    subgraph HandlersDetail["Handlers"]
        H1["/start, /help"]
        H2["/form Command"]
        H3["Text Messages"]
        H4["Callback Query"]
        H5["web_app_data"]
    end

    HANDLERS --> H1
    HANDLERS --> H2
    HANDLERS --> H3
    HANDLERS --> H4
    HANDLERS --> H5

    H2 --> WAM
    H5 --> WAM
    RENDERER --> BOT
```

### 4. Claude Agent

Claude CLI를 subprocess로 실행하여 AI 응답을 생성합니다.

```mermaid
graph TB
    subgraph ClaudeAgent["Claude Agent"]
        PROC[Process Manager]
        CTX[Context Builder]
        PARSE[Response Parser]
    end

    subgraph Context["Context Sources"]
        USER[User Info]
        MSG[Recent Messages]
        VEC[Vector Search Results]
        SCHED[Active Schedules]
    end

    subgraph Markers["Special Markers"]
        M1["[FACT:key:value]"]
        M2["[SCHEDULE:cron:msg]"]
        M3["[SCHEDULE_ONCE:min:msg]"]
        M4["[CANCEL_SCHEDULE:id]"]
    end

    GW[Gateway] -->|message| CTX
    CTX --> USER
    CTX --> MSG
    CTX --> VEC
    CTX --> SCHED
    CTX -->|prompt| PROC
    PROC -->|spawn| CLI[claude -p]
    CLI -->|stdout| PARSE
    PARSE --> Markers
    PARSE -->|response| GW
```

### 5. Memory System

두 개의 SQLite 데이터베이스로 구성됩니다.

```mermaid
graph TB
    subgraph Memory["Memory System"]
        subgraph MainDB["memory.db (better-sqlite3)"]
            USERS[(users)]
            MESSAGES[(messages)]
            FACTS[(facts)]
            SCHEDULES[(schedules)]
            FTS[(messages_fts)]
        end

        subgraph VectorDB["memory-index.db (node:sqlite)"]
            META[(meta)]
            FILES[(files)]
            CHUNKS[(chunks)]
            CACHE[(embedding_cache)]
            VEC_CHUNKS[(vec_chunks)]
        end
    end

    AGENT[Agent] --> MainDB
    AGENT --> VectorDB
    SCHED[Scheduler] --> SCHEDULES

    MESSAGES <-->|FTS5| FTS
    CHUNKS <-->|sqlite-vec| VEC_CHUNKS
```

---

## 데이터 흐름

### 1. 일반 대화 흐름

```mermaid
sequenceDiagram
    participant U as User
    participant T as Telegram
    participant TC as Telegram Channel
    participant GW as Gateway
    participant A as Claude Agent
    participant M as Memory
    participant C as Claude CLI

    U->>T: 메시지 전송
    T->>TC: getUpdates (polling)
    TC->>GW: {from: telegram, to: agent}
    GW->>A: route message

    A->>M: 사용자 정보 조회
    A->>M: 최근 메시지 조회
    A->>M: 벡터 검색 (관련 대화)
    A->>C: claude -p (stdin: prompt)
    C-->>A: stdout: response

    A->>M: 메시지 저장
    A->>GW: {from: agent, to: telegram}
    GW->>TC: route response
    TC->>T: sendMessage
    T->>U: 응답 표시
```

### 2. Mini App 폼 제출 흐름

```mermaid
sequenceDiagram
    participant U as User
    participant T as Telegram
    participant TC as Telegram Channel
    participant WM as WebApp Manager
    participant HS as HTTP Server
    participant MA as Mini App

    U->>T: /form 명령어
    T->>TC: message update
    TC->>WM: createSession(surface)
    WM-->>TC: sessionId
    TC->>T: Reply Keyboard (web_app button)
    T->>U: 키보드 표시

    U->>T: 버튼 클릭
    T->>MA: Open Mini App (sessionUrl)
    MA->>HS: GET /api/webapp/session/:id
    HS->>WM: getSession(id)
    WM-->>HS: session data
    HS-->>MA: {surface, dataModel}
    MA->>MA: Render A2UI

    U->>MA: 폼 작성 + 제출
    MA->>T: tg.sendData(result)
    T->>TC: web_app_data update
    TC->>TC: Parse & process data
    TC-->>U: 확인 메시지
```

### 3. 스케줄 알림 흐름

```mermaid
sequenceDiagram
    participant CRON as node-cron
    participant S as Scheduler
    participant GW as Gateway
    participant TC as Telegram Channel
    participant T as Telegram API
    participant U as User

    CRON->>S: trigger job
    S->>S: Load schedule from DB
    S->>GW: broadcast {to: telegram}
    GW->>TC: route message
    TC->>T: sendMessage(chatId)
    T->>U: 알림 표시
```

---

## 프로토콜 통합

### AG-UI (Agent-User Interface)

실시간 이벤트 스트리밍 프로토콜입니다.

```mermaid
stateDiagram-v2
    [*] --> RUN_STARTED
    RUN_STARTED --> TEXT_MESSAGE_START
    TEXT_MESSAGE_START --> TEXT_MESSAGE_CONTENT
    TEXT_MESSAGE_CONTENT --> TEXT_MESSAGE_CONTENT
    TEXT_MESSAGE_CONTENT --> TEXT_MESSAGE_END
    TEXT_MESSAGE_END --> TOOL_CALL_START
    TOOL_CALL_START --> TOOL_CALL_END
    TOOL_CALL_END --> TEXT_MESSAGE_START
    TEXT_MESSAGE_END --> RUN_FINISHED
    RUN_FINISHED --> [*]

    RUN_STARTED --> RUN_ERROR
    RUN_ERROR --> [*]
```

### A2UI (Agent-Driven UI)

선언적 UI 명세 프로토콜입니다.

```mermaid
graph TB
    subgraph A2UI["A2UI Surface"]
        SURFACE[SurfaceUpdate]
        SURFACE --> COMP1[Component: Text]
        SURFACE --> COMP2[Component: TextField]
        SURFACE --> COMP3[Component: Button]
        SURFACE --> COMP4[Component: DateTimeInput]
    end

    subgraph DataModel["Data Model"]
        DM["/form/name"]
        DM2["/form/phone"]
        DM3["/form/date"]
    end

    COMP2 -->|value.path| DM
    COMP4 -->|value.path| DM3
    COMP3 -->|action| ACTION[submit_reservation]
```

### A2A (Agent-to-Agent) v0.3.0

JSON-RPC 2.0 기반 에이전트 간 통신 프로토콜입니다.

**핵심 타입 (v0.3.0 표준):**

```typescript
// Task 구조
interface Task {
  id: string;
  contextId?: string;              // 대화 연속성을 위한 컨텍스트 ID
  status: TaskStatusInfo;          // 상태 정보 객체
  artifacts?: TaskArtifact[];      // 출력 아티팩트
  history?: A2AMessage[];          // 메시지 히스토리
  createdAt: string;
  updatedAt: string;
  error?: string;
  metadata?: Record<string, unknown>;
}

// 상태 정보 (v0.3.0)
interface TaskStatusInfo {
  state: 'pending' | 'working' | 'completed' | 'failed' | 'cancelled';
  timestamp: string;
  message?: string;
}
```

**지원 메서드:**

| 메서드 | 설명 |
|--------|------|
| `message/send` | 메시지 전송, Task 반환 |
| `message/stream` | SSE 스트리밍 응답 |
| `tasks/get` | Task 상태 조회 |
| `tasks/list` | Task 목록 조회 |
| `tasks/cancel` | Task 취소 |
| `tasks/subscribe` | Task 업데이트 SSE 구독 |
| `tasks/pushNotificationConfig/*` | 웹훅 설정 CRUD |

**에러 코드:**

| 코드 | 이름 | 설명 |
|------|------|------|
| `-32000` | TASK_NOT_FOUND | 태스크 없음 |
| `-32001` | PUSH_NOTIFICATION_NOT_SUPPORTED | 푸시 미지원 |
| `-32010` | TASK_CANCELLED | 태스크 취소됨 |
| `-32011` | AGENT_UNAVAILABLE | 에이전트 불가 |
| `-32014` | CONFIG_NOT_FOUND | 설정 없음 |

```mermaid
sequenceDiagram
    participant C as Client Agent
    participant S as Server Agent
    participant WH as Webhook

    C->>S: GET /.well-known/agent.json
    S-->>C: AgentCard (capabilities)

    C->>S: POST / (message/send)
    Note right of C: {"method": "message/send",<br/>"params": {"message": {...}}}
    S-->>C: {"result": {"task": {...}}}

    C->>S: POST / (tasks/subscribe)
    Note right of C: SSE 스트림 구독
    S-->>C: event: statusUpdate
    S-->>C: event: artifactUpdate
    S-->>C: event: message

    opt Push Notifications
        C->>S: POST / (pushNotificationConfig/create)
        S-->>C: {"result": {"config": {...}}}
        S->>WH: POST (statusUpdate)
    end
```

**Orchestrator (멀티 에이전트):**

```mermaid
graph TB
    subgraph Orchestrator["A2A Orchestrator"]
        REG[Agent Registry]
        HEALTH[Health Check]
        WORKFLOW[Workflow Engine]
    end

    subgraph Agents["Registered Agents"]
        A1[Calendar Agent]
        A2[Weather Agent]
        A3[Search Agent]
    end

    WORKFLOW -->|step 1| A1
    WORKFLOW -->|step 2| A2
    WORKFLOW -->|parallel| A3
    HEALTH -->|60s interval| A1
    HEALTH -->|60s interval| A2
    HEALTH -->|60s interval| A3
```

---

## 데이터베이스 스키마

### Main DB (memory.db)

```mermaid
erDiagram
    users {
        string id PK
        string name
        string created_at
        string updated_at
    }

    messages {
        int id PK
        string user_id FK
        string role
        string content
        string timestamp
    }

    facts {
        int id PK
        string user_id FK
        string key
        string value
        string created_at
    }

    schedules {
        int id PK
        string user_id FK
        string cron_expression
        string message
        int active
        string created_at
    }

    users ||--o{ messages : has
    users ||--o{ facts : has
    users ||--o{ schedules : has
```

### Vector DB (memory-index.db)

```mermaid
erDiagram
    meta {
        string key PK
        string value
    }

    files {
        int id PK
        string path
        string hash
        string indexed_at
    }

    chunks {
        int id PK
        int file_id FK
        string content
        blob embedding
        string metadata
    }

    embedding_cache {
        string text_hash PK
        blob embedding
        string created_at
    }

    files ||--o{ chunks : contains
```

---

## 배포 아키텍처

### 개발 환경

```mermaid
graph TB
    subgraph Local["Local Machine"]
        DEV[pnpm dev<br/>tsx watch]
        NGROK[ngrok tunnel]
    end

    subgraph External["External"]
        TG[Telegram API]
        NGROK_CLOUD[ngrok Cloud]
    end

    DEV -->|:3000| NGROK
    NGROK -->|HTTPS| NGROK_CLOUD
    NGROK_CLOUD -->|webhook URL| TG
    TG <-->|polling| DEV
```

### 프로덕션 환경 (예정)

```mermaid
graph TB
    subgraph Server["Production Server"]
        NGINX[nginx<br/>Reverse Proxy]
        APP[Michael App<br/>launchd daemon]
        CERT[Let's Encrypt<br/>SSL]
    end

    subgraph External["External"]
        TG[Telegram API]
        DNS[DNS]
    end

    DNS --> NGINX
    CERT --> NGINX
    NGINX -->|:3000| APP
    TG <-->|polling| APP
```

---

## 보안 고려사항

1. **환경 변수**: 민감 정보는 `.env` 파일에 저장, git에서 제외
2. **HTTPS**: Mini App은 ngrok/SSL로 HTTPS 필수
3. **입력 검증**: 모든 사용자 입력은 sanitize
4. **세션 관리**: WebApp 세션은 메모리에만 저장, 만료 처리

---

## 확장 포인트

| 영역 | 확장 방법 |
|------|----------|
| 채널 추가 | `src/channels/`에 새 채널 구현, Gateway 연결 |
| AI 모델 변경 | `src/agent/`에서 Claude CLI 대신 다른 모델 사용 |
| 저장소 변경 | `src/brain/memory.ts`의 DB 레이어 교체 |
| UI 컴포넌트 | `src/a2ui/types.ts`에 새 컴포넌트 타입 추가 |

---

*마지막 업데이트: 2026-02-02*
