# Michael 프로토콜 통합 아키텍처 검토

> **문서 버전**: 1.0  
> **작성일**: 2026-02-01  
> **목적**: A2A/A2UI/AG-UI 프로토콜 통합 아키텍처 설계 및 구현 가능성 검토

---

## 1. 검토 요약

### 1.1 종합 판단

| 프로토콜 | 적용 대상 | 가능 여부 | 복잡도 | 권장 Phase |
|---------|----------|----------|--------|------------|
| **A2A** | 멀티에이전트 | ✅ 가능 | 높음 | Phase 5 |
| **A2UI** | 웹 채팅 | ✅ 가능 | 중간 | Phase 2 |
| **A2UI** | Telegram 네이티브 | ⚠️ 제한적 | 낮음 | Phase 3 |
| **A2UI** | Telegram Web App | ✅ 완전 가능 | 중간 | Phase 4 |
| **AG-UI** | 모든 채널 | ✅ 권장 | 낮음 | Phase 1 |

### 1.2 핵심 결론

1. **AG-UI를 공통 기반으로** - 모든 채널이 동일한 이벤트 스트림 사용
2. **A2UI는 렌더링 레이어** - 채널별 적응형 렌더링
3. **Telegram은 하이브리드** - 간단한 것은 네이티브, 복잡한 것은 Web App
4. **A2A는 백엔드 확장** - 멀티에이전트 협업 시 활성화

---

## 2. 현재 Michael 아키텍처

```
Gateway (WebSocket hub, port 18789)
  ├─> Telegram Channel (user interface)
  ├─> Claude Code Agent (AI brain via CLI)
  ├─> Memory (SQLite + Vector Search)
  └─> Scheduler (cron-based proactive notifications)
```

### 주요 컴포넌트

| 컴포넌트 | 파일 | 역할 |
|---------|------|------|
| Gateway | `src/core/gateway.ts` | WebSocket 허브, 메시지 라우팅 |
| ClaudeCodeAgent | `src/agent/claude-code.ts` | Claude CLI 기반 AI 에이전트 |
| TelegramChannel | `src/channels/telegram.ts` | Telegram 봇 인터페이스 |
| Memory | `src/brain/memory.ts` | SQLite + FTS5 + Vector Search |

### 현재 GatewayMessage 구조

```typescript
interface GatewayMessage {
  from: 'telegram' | 'scheduler' | 'cli';
  to: 'agent' | 'telegram';
  userId: string;
  content: string;
  metadata?: Record<string, any>;
}
```

---

## 3. 텔레그램 A2UI 적용 가능성 분석

### 3.1 Telegram 네이티브 UI 제약

| A2UI 컴포넌트 | Telegram 대응 | 매핑 가능 |
|--------------|--------------|----------|
| `Text` | 마크다운 텍스트 | ✅ 완전 |
| `Button` | InlineKeyboardButton | ✅ 완전 |
| `Image` | sendPhoto | ✅ 완전 |
| `Card` | 마크다운 블록 + 구분선 | ⚠️ 부분 |
| `Row` | InlineKeyboardMarkup (한 행) | ✅ 완전 |
| `Column` | 여러 메시지 순차 전송 | ⚠️ 부분 |
| `TextField` | ❌ 직접 불가 (입력 대기만) | ❌ 불가 |
| `DateTimeInput` | ❌ 불가 | ❌ 불가 |
| `List/ListItem` | 번호 목록 텍스트 | ⚠️ 부분 |

### 3.2 해결책: Telegram Web App (Mini App)

```
┌─────────────────────────────────────────────────────────┐
│                    Telegram Chat                         │
│                                                          │
│  User: 항공권 예약해줘                                   │
│                                                          │
│  Michael: 예약 정보를 입력해주세요                       │
│  ┌─────────────────────────────────────────────────┐    │
│  │  [📝 예약 폼 열기]  ← InlineKeyboardButton      │    │
│  └─────────────────────────────────────────────────┘    │
│                         │                                │
│                         ▼                                │
│  ┌─────────────────────────────────────────────────┐    │
│  │         Telegram Web App (Modal)                 │    │
│  │  ┌───────────────────────────────────────────┐  │    │
│  │  │     A2UI Full Renderer (React)            │  │    │
│  │  │                                           │  │    │
│  │  │  ┌─────────────────────────────────────┐  │  │    │
│  │  │  │ Card: Flight Booking               │  │  │    │
│  │  │  │  ├─ DateTimeInput: Departure       │  │  │    │
│  │  │  │  ├─ TextField: From                │  │  │    │
│  │  │  │  ├─ TextField: To                  │  │  │    │
│  │  │  │  └─ Button: [Book Now]             │  │  │    │
│  │  │  └─────────────────────────────────────┘  │  │    │
│  │  └───────────────────────────────────────────┘  │    │
│  └─────────────────────────────────────────────────┘    │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

**Telegram Web App 장점:**
- 완전한 A2UI 지원
- 네이티브 앱 경험
- Telegram과 양방향 통신 (sendData, close)
- 사용자 인증 자동 처리

---

## 4. 통합 아키텍처 설계

### 4.1 전체 아키텍처 다이어그램

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Michael Gateway                              │
│                    (WebSocket + HTTP + A2A JSON-RPC)                 │
│                           port 18789                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │                    AG-UI Event Bus                          │     │
│  │  RUN_STARTED | TEXT_MESSAGE_* | TOOL_CALL_* | STATE_*      │     │
│  │  A2UI_SURFACE_UPDATE | A2UI_DATA_UPDATE | A2UI_RENDER      │     │
│  └────────────────────────────────────────────────────────────┘     │
│                              │                                       │
│         ┌────────────────────┼────────────────────┐                 │
│         │                    │                    │                  │
│         ▼                    ▼                    ▼                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │   Telegram   │    │     Web      │    │    Slack     │          │
│  │   Channel    │    │   Channel    │    │   Channel    │          │
│  └──────┬───────┘    └──────┬───────┘    └──────────────┘          │
│         │                   │                                        │
│         ▼                   ▼                                        │
│  ┌──────────────┐    ┌──────────────┐                               │
│  │   Adaptive   │    │    A2UI      │                               │
│  │   Renderer   │    │   Renderer   │                               │
│  │              │    │   (React)    │                               │
│  │ A2UI → TG 매핑│    │              │                               │
│  └──────┬───────┘    └──────────────┘                               │
│         │                                                            │
│         ▼                                                            │
│  ┌──────────────┐                                                   │
│  │  Telegram    │  ← 복잡한 폼은 Web App으로 전환                   │
│  │  Web App     │                                                   │
│  │ (A2UI Full)  │                                                   │
│  └──────────────┘                                                   │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      A2A Server Layer                        │   │
│  │           /.well-known/agent.json (AgentCard)                │   │
│  │           / (JSON-RPC 2.0 Endpoint)                          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│         ┌────────────────────┼────────────────────┐                 │
│         │                    │                    │                  │
│         ▼                    ▼                    ▼                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │   Michael    │    │   Calendar   │    │   Shopping   │          │
│  │    Agent     │◀──▶│    Agent     │◀──▶│    Agent     │          │
│  │   (Claude)   │A2A │  (External)  │A2A │  (External)  │          │
│  └──────────────┘    └──────────────┘    └──────────────┘          │
│         │                                                            │
│         ▼                                                            │
│  ┌──────────────┐                                                   │
│  │    Memory    │                                                   │
│  │  (SQLite +   │                                                   │
│  │ Vector Search)│                                                   │
│  └──────────────┘                                                   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 레이어 설명

| 레이어 | 프로토콜 | 역할 |
|-------|---------|------|
| **Event Bus** | AG-UI | 실시간 이벤트 스트리밍, 모든 채널 공통 |
| **Channel** | - | 채널별 연결 관리 (Telegram, Web, Slack 등) |
| **Renderer** | A2UI | 채널별 UI 렌더링 (적응형 또는 풀) |
| **A2A Server** | A2A | 멀티에이전트 협업, 외부 에이전트 연동 |
| **Agent** | - | AI 처리, A2UI 생성, 도구 실행 |

---

## 5. 채널별 A2UI 렌더링 전략

### 5.1 Web Channel (완전 지원)

```typescript
// Agent가 A2UI JSON 생성
const a2uiResponse = {
  surfaceUpdate: {
    surfaceId: "main",
    components: [
      { 
        id: "booking-card", 
        component: { 
          Card: { 
            title: { literalString: "Flight Booking" },
            children: { explicitList: ["date-input", "dest-input", "submit-btn"] }
          } 
        } 
      },
      {
        id: "date-input",
        component: {
          DateTimeInput: {
            label: { literalString: "출발일" },
            value: { path: "/booking/date" }
          }
        }
      },
      {
        id: "dest-input",
        component: {
          TextField: {
            label: { literalString: "목적지" },
            value: { path: "/booking/destination" }
          }
        }
      },
      {
        id: "submit-btn",
        component: {
          Button: {
            label: { literalString: "예약하기" },
            action: {
              name: "submit_booking",
              context: [
                { key: "date", value: { path: "/booking/date" } },
                { key: "destination", value: { path: "/booking/destination" } }
              ]
            }
          }
        }
      }
    ]
  }
};

// React A2UI Renderer가 그대로 렌더링
<A2UIRenderer surface={a2uiResponse} onAction={handleAction} />
```

### 5.2 Telegram Channel (적응형)

```typescript
// TelegramAdaptiveRenderer
class TelegramAdaptiveRenderer {
  render(a2ui: A2UIMessage): TelegramMessage {
    const components = a2ui.surfaceUpdate.components;
    
    // 복잡도 판단: TextField, DateTimeInput 등 입력 요소 존재 여부
    const hasFormInputs = components.some(c => 
      c.component.TextField || 
      c.component.DateTimeInput ||
      c.component.NumberInput
    );
    
    if (hasFormInputs) {
      // Web App으로 전환
      return this.renderWithWebApp(a2ui);
    }
    
    // 네이티브 렌더링 가능한 경우
    return this.renderNative(components);
  }
  
  renderWithWebApp(a2ui: A2UIMessage): TelegramMessage {
    const sessionId = generateSessionId();
    // A2UI 상태를 임시 저장
    this.storeA2UIState(sessionId, a2ui);
    
    return {
      text: "입력이 필요합니다. 아래 버튼을 눌러주세요.",
      reply_markup: {
        inline_keyboard: [[{
          text: "📝 폼 열기",
          web_app: { url: `https://michael.app/a2ui/${sessionId}` }
        }]]
      }
    };
  }
  
  renderNative(components: A2UIComponent[]): TelegramMessage {
    let text = '';
    const buttons: InlineKeyboardButton[][] = [];
    
    for (const comp of components) {
      if (comp.component.Text) {
        // Text → Markdown
        const usage = comp.component.Text.usageHint;
        const content = this.resolveBoundValue(comp.component.Text.text);
        
        if (usage === 'h1') text += `*${content}*\n\n`;
        else if (usage === 'h2') text += `*${content}*\n`;
        else text += `${content}\n`;
      }
      
      if (comp.component.Button) {
        // Button → InlineKeyboardButton
        buttons.push([{
          text: this.resolveBoundValue(comp.component.Button.label),
          callback_data: JSON.stringify(comp.component.Button.action)
        }]);
      }
      
      if (comp.component.Card) {
        // Card → Bold title + 구분선
        const title = this.resolveBoundValue(comp.component.Card.title);
        text += `━━━━━━━━━━━━━━━\n*${title}*\n`;
      }
      
      if (comp.component.Image) {
        // Image는 별도 sendPhoto로 처리
        // 여기서는 placeholder
        text += `[이미지: ${comp.component.Image.alt?.literalString || ''}]\n`;
      }
    }
    
    return {
      text: text.trim(),
      parse_mode: 'Markdown',
      reply_markup: buttons.length > 0 ? { inline_keyboard: buttons } : undefined
    };
  }
}
```

### 5.3 Telegram Web App (완전 지원)

```typescript
// Telegram Mini App (React)
import { WebApp } from '@twa-dev/sdk';
import { A2UIRenderer } from '@michael/a2ui-react';

function TelegramMiniApp() {
  const [surface, setSurface] = useState<A2UISurface | null>(null);
  const sessionId = new URLSearchParams(window.location.search).get('session');
  
  useEffect(() => {
    // Gateway WebSocket 연결
    const ws = new WebSocket(`wss://michael.app/gateway?session=${sessionId}`);
    
    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      
      if (msg.type === 'A2UI_SURFACE_UPDATE') {
        setSurface(msg.payload);
      }
      
      if (msg.type === 'A2UI_DATA_UPDATE') {
        // 데이터 모델 업데이트
        updateDataModel(msg.payload);
      }
    };
    
    // 초기 A2UI 상태 로드
    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'GET_A2UI_STATE', sessionId }));
    };
    
    return () => ws.close();
  }, [sessionId]);
  
  const handleAction = (action: A2UIAction) => {
    // 액션 처리 후 Telegram으로 결과 전송
    const result = {
      action: action.name,
      context: action.context
    };
    
    WebApp.sendData(JSON.stringify(result));
    WebApp.close();
  };
  
  if (!surface) {
    return <div>Loading...</div>;
  }
  
  return (
    <div className="telegram-mini-app">
      <A2UIRenderer 
        surface={surface} 
        onAction={handleAction}
        theme={WebApp.colorScheme} // Telegram 테마 적용
      />
    </div>
  );
}
```

---

## 6. AG-UI 이벤트 통합

### 6.1 확장된 GatewayMessage

```typescript
// 기존 GatewayMessage 확장
interface AGUIGatewayMessage extends GatewayMessage {
  // AG-UI 이벤트 지원
  eventType?: AGUIEventType;
  streamId?: string;
  
  // 텍스트 메시지 이벤트
  messageId?: string;
  role?: 'user' | 'assistant';
  delta?: string;
  
  // 도구 호출 이벤트
  toolCallId?: string;
  toolCallName?: string;
  toolArgs?: Record<string, any>;
  toolResult?: any;
  
  // A2UI 이벤트 (AG-UI 확장)
  a2ui?: A2UIMessage;
}

type AGUIEventType = 
  // Lifecycle
  | 'RUN_STARTED'
  | 'RUN_FINISHED'
  | 'RUN_ERROR'
  | 'STEP_STARTED'
  | 'STEP_FINISHED'
  // Text Message
  | 'TEXT_MESSAGE_START'
  | 'TEXT_MESSAGE_CONTENT'
  | 'TEXT_MESSAGE_END'
  // Tool Call
  | 'TOOL_CALL_START'
  | 'TOOL_CALL_ARGS'
  | 'TOOL_CALL_END'
  | 'TOOL_CALL_RESULT'
  // State
  | 'STATE_SNAPSHOT'
  | 'STATE_DELTA'
  // A2UI Extension
  | 'A2UI_SURFACE_UPDATE'
  | 'A2UI_DATA_UPDATE'
  | 'A2UI_BEGIN_RENDERING';
```

### 6.2 이벤트 흐름 예시

```
User Message: "3월 15일 도쿄행 항공권 예약해줘"
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Gateway Event Stream                                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. RUN_STARTED                                                  │
│     {"threadId": "t1", "runId": "r1"}                           │
│                                                                  │
│  2. TEXT_MESSAGE_START                                           │
│     {"messageId": "m1", "role": "assistant"}                    │
│                                                                  │
│  3. TEXT_MESSAGE_CONTENT (스트리밍)                              │
│     {"messageId": "m1", "delta": "항공권을 "}                    │
│     {"messageId": "m1", "delta": "검색하겠습니다..."}            │
│                                                                  │
│  4. TOOL_CALL_START                                              │
│     {"toolCallId": "tc1", "toolCallName": "search_flights"}     │
│                                                                  │
│  5. TOOL_CALL_ARGS                                               │
│     {"toolCallId": "tc1", "delta": "{\"date\":\"2026-03-15\"}"}│
│                                                                  │
│  6. TOOL_CALL_END                                                │
│     {"toolCallId": "tc1"}                                       │
│                                                                  │
│  7. TOOL_CALL_RESULT                                             │
│     {"toolCallId": "tc1", "content": "[3 flights found]"}       │
│                                                                  │
│  8. A2UI_SURFACE_UPDATE  ← A2UI 통합                            │
│     {                                                            │
│       "surfaceId": "main",                                       │
│       "components": [                                            │
│         {"id": "flight1", "component": {"Card": {...}}},        │
│         {"id": "flight2", "component": {"Card": {...}}},        │
│         {"id": "flight3", "component": {"Card": {...}}}         │
│       ]                                                          │
│     }                                                            │
│                                                                  │
│  9. A2UI_BEGIN_RENDERING                                         │
│     {"surfaceId": "main", "root": "flight-list"}                │
│                                                                  │
│ 10. TEXT_MESSAGE_END                                             │
│     {"messageId": "m1"}                                         │
│                                                                  │
│ 11. RUN_FINISHED                                                 │
│     {"threadId": "t1", "runId": "r1"}                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
         │
         ├──────────────────┬──────────────────┐
         ▼                  ▼                  ▼
   ┌──────────┐      ┌──────────┐      ┌──────────┐
   │ Telegram │      │   Web    │      │  Slack   │
   │          │      │          │      │          │
   │ 적응형   │      │ A2UI     │      │ 적응형   │
   │ 렌더링   │      │ 풀 렌더링│      │ 렌더링   │
   └──────────┘      └──────────┘      └──────────┘
```

---

## 7. A2A 멀티에이전트 통합

### 7.1 Michael AgentCard

```json
{
  "name": "michael",
  "description": "24/7 개인 AI 어시스턴트. 일정 관리, 정보 검색, 예약 등 다양한 작업 수행",
  "url": "https://michael.app/",
  "version": "1.0.0",
  "protocolVersion": "0.3.0",
  "defaultInputModes": ["text"],
  "defaultOutputModes": ["text", "a2ui"],
  "capabilities": {
    "streaming": true,
    "pushNotifications": true,
    "a2ui": true
  },
  "skills": [
    {
      "id": "memory-search",
      "name": "Memory Search",
      "description": "과거 대화 및 저장된 정보 검색",
      "examples": ["지난주에 뭐 얘기했지?", "내 생일 언제야?"]
    },
    {
      "id": "schedule-management",
      "name": "Schedule Management",
      "description": "일정 등록, 조회, 알림 설정",
      "examples": ["내일 3시에 회의 알려줘", "이번 주 일정 보여줘"]
    },
    {
      "id": "proactive-notification",
      "name": "Proactive Notification",
      "description": "능동적 알림 및 리마인더",
      "examples": ["매일 아침 9시에 날씨 알려줘"]
    }
  ],
  "securitySchemes": {
    "telegramAuth": {
      "type": "custom",
      "description": "Telegram User ID 기반 인증"
    }
  }
}
```

### 7.2 A2A Server 엔드포인트

```typescript
// Gateway에 A2A 엔드포인트 추가
class Gateway {
  // ... 기존 코드 ...
  
  setupA2AEndpoints() {
    // AgentCard 엔드포인트
    this.httpServer.get('/.well-known/agent.json', (req, res) => {
      res.json(this.agentCard);
    });
    
    // JSON-RPC 2.0 엔드포인트
    this.httpServer.post('/', async (req, res) => {
      const { method, params, id } = req.body;
      
      try {
        let result;
        
        switch (method) {
          case 'message/send':
            result = await this.handleMessageSend(params);
            break;
          case 'message/stream':
            // SSE 스트리밍
            return this.handleMessageStream(params, res);
          case 'tasks/get':
            result = await this.handleTaskGet(params);
            break;
          case 'tasks/cancel':
            result = await this.handleTaskCancel(params);
            break;
          default:
            throw { code: -32601, message: 'Method not found' };
        }
        
        res.json({ jsonrpc: '2.0', id, result });
      } catch (error) {
        res.json({ jsonrpc: '2.0', id, error });
      }
    });
  }
  
  async handleMessageSend(params: MessageSendParams): Promise<Task> {
    const task = this.createTask(params.message);
    
    // Agent에게 메시지 전달
    this.agent.processMessage(task, params.message);
    
    return task;
  }
}
```

### 7.3 외부 에이전트 호출

```typescript
// A2A Client로 외부 에이전트 호출
class A2AClient {
  async callAgent(agentUrl: string, message: Message): Promise<Task> {
    // AgentCard 조회
    const card = await this.fetchAgentCard(agentUrl);
    
    // message/send 호출
    const response = await fetch(agentUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        jsonrpc: '2.0',
        id: generateId(),
        method: 'message/send',
        params: { message }
      })
    });
    
    return response.json().then(r => r.result.task);
  }
  
  async fetchAgentCard(agentUrl: string): Promise<AgentCard> {
    const url = new URL('/.well-known/agent.json', agentUrl);
    const response = await fetch(url);
    return response.json();
  }
}

// 사용 예시: Michael이 Calendar Agent 호출
const calendarAgent = new A2AClient();
const task = await calendarAgent.callAgent(
  'https://calendar-agent.example.com/',
  {
    role: 'user',
    parts: [{ type: 'text', text: '3월 15일 일정 확인해줘' }]
  }
);
```

---

## 8. 구현 로드맵

### Phase 1: AG-UI 기반 구축 (2-3주)

```
목표: 실시간 이벤트 스트리밍 기반 구축

작업:
├─ GatewayMessage 확장 (AG-UI 이벤트 타입)
├─ Agent 응답 스트리밍 구현
│   └─ Claude CLI stdout 청크 처리
├─ Telegram에 "입력 중..." 표시
│   └─ sendChatAction('typing')
├─ 도구 실행 이벤트 발행
│   └─ Memory 검색, Schedule 등록 시 이벤트
└─ 테스트 및 검증

산출물:
├─ src/core/gateway.ts (확장)
├─ src/core/events.ts (AG-UI 이벤트 정의)
├─ src/agent/claude-code.ts (스트리밍 지원)
└─ docs/AGUI_INTEGRATION.md
```

### Phase 2: Web Channel + A2UI (3-4주)

```
목표: 웹 채팅 인터페이스 + A2UI 풀 렌더링

작업:
├─ WebChannel 구현 (WebSocket 클라이언트)
│   └─ src/channels/web.ts
├─ React A2UI Renderer 개발
│   └─ packages/a2ui-react/
├─ Agent 프롬프트에 A2UI 생성 지시 추가
│   └─ "필요 시 A2UI JSON으로 응답"
├─ 기본 컴포넌트 지원
│   └─ Text, Button, Card, List, Image
└─ 웹 채팅 UI 개발
    └─ ui/web-chat/

산출물:
├─ src/channels/web.ts
├─ packages/a2ui-react/
├─ ui/web-chat/
└─ docs/A2UI_COMPONENT_GUIDE.md
```

### Phase 3: Telegram Adaptive Renderer (2주)

```
목표: Telegram에서 A2UI 적응형 렌더링

작업:
├─ TelegramAdaptiveRenderer 구현
│   └─ src/channels/telegram-renderer.ts
├─ A2UI → Telegram 네이티브 매핑 로직
│   ├─ Text → Markdown
│   ├─ Button → InlineKeyboardButton
│   ├─ Card → Bold title + 구분선
│   └─ List → 번호 목록
├─ 복잡도 판단 알고리즘
│   └─ hasFormInputs() → Web App 전환
└─ 콜백 쿼리 핸들러 업데이트

산출물:
├─ src/channels/telegram-renderer.ts
├─ src/channels/telegram.ts (업데이트)
└─ docs/TELEGRAM_A2UI_MAPPING.md
```

### Phase 4: Telegram Web App (2주)

```
목표: Telegram Mini App으로 완전한 A2UI 지원

작업:
├─ Telegram Mini App 개발 (React)
│   └─ ui/telegram-mini-app/
├─ A2UI 풀 렌더러 임베드
│   └─ @michael/a2ui-react 사용
├─ Bot ↔ Web App 양방향 통신
│   ├─ WebApp.sendData()
│   └─ answerWebAppQuery()
├─ 세션 상태 관리
│   └─ A2UI 상태 임시 저장/복원
└─ 결과 콜백 처리

산출물:
├─ ui/telegram-mini-app/
├─ src/channels/telegram-webapp.ts
└─ docs/TELEGRAM_MINI_APP_GUIDE.md
```

### Phase 5: A2A 멀티에이전트 (4주+)

```
목표: 외부 에이전트와 협업

작업:
├─ AgentCard 스키마 정의
│   └─ src/a2a/agent-card.ts
├─ A2A Server 엔드포인트 추가
│   ├─ /.well-known/agent.json
│   └─ / (JSON-RPC 2.0)
├─ JSON-RPC 2.0 핸들러
│   ├─ message/send
│   ├─ message/stream
│   ├─ tasks/get
│   └─ tasks/cancel
├─ A2A Client 구현
│   └─ src/a2a/client.ts
├─ Task 오케스트레이션 로직
│   └─ src/a2a/orchestrator.ts
└─ 외부 에이전트 연동 테스트
    ├─ Calendar Agent (예시)
    └─ Shopping Agent (예시)

산출물:
├─ src/a2a/
│   ├─ agent-card.ts
│   ├─ server.ts
│   ├─ client.ts
│   └─ orchestrator.ts
└─ docs/A2A_INTEGRATION.md
```

---

## 9. 파일 구조 변경 예상

```
michael/
├─ src/
│   ├─ core/
│   │   ├─ gateway.ts          # 확장: AG-UI + A2A
│   │   └─ events.ts           # 신규: AG-UI 이벤트 정의
│   ├─ channels/
│   │   ├─ telegram.ts         # 업데이트: Adaptive Renderer 연동
│   │   ├─ telegram-renderer.ts # 신규: A2UI → Telegram 매핑
│   │   ├─ telegram-webapp.ts  # 신규: Web App 통신
│   │   └─ web.ts              # 신규: Web Channel
│   ├─ a2a/                    # 신규: A2A 레이어
│   │   ├─ agent-card.ts
│   │   ├─ server.ts
│   │   ├─ client.ts
│   │   └─ orchestrator.ts
│   └─ agent/
│       └─ claude-code.ts      # 업데이트: 스트리밍, A2UI 생성
├─ packages/
│   └─ a2ui-react/             # 신규: React A2UI Renderer
│       ├─ src/
│       │   ├─ components/
│       │   ├─ renderer.tsx
│       │   └─ index.ts
│       └─ package.json
├─ ui/
│   ├─ web-chat/               # 신규: 웹 채팅 UI
│   └─ telegram-mini-app/      # 신규: Telegram Mini App
└─ docs/
    ├─ AGUI_INTEGRATION.md
    ├─ A2UI_COMPONENT_GUIDE.md
    ├─ TELEGRAM_A2UI_MAPPING.md
    ├─ TELEGRAM_MINI_APP_GUIDE.md
    └─ A2A_INTEGRATION.md
```

---

## 10. 결론

### 10.1 핵심 질문에 대한 답변

| 질문 | 답변 |
|------|------|
| A2A 멀티에이전트 가능? | ✅ Gateway에 A2A 엔드포인트 추가로 가능 |
| 웹 채팅 A2UI 동적 UI 가능? | ✅ WebChannel + React A2UI Renderer로 완전 지원 |
| AG-UI 상호작용 가능? | ✅ 모든 채널에 공통 적용 (권장, Phase 1) |
| Telegram A2UI 가능? | ⚠️ 네이티브는 제한적, **Web App으로 완전 지원** |

### 10.2 권장 구현 순서

```
AG-UI (Phase 1) → A2UI Web (Phase 2) → Telegram Adaptive (Phase 3) 
    → Telegram Web App (Phase 4) → A2A (Phase 5)
```

### 10.3 예상 총 개발 기간

| Phase | 기간 | 누적 |
|-------|------|------|
| Phase 1: AG-UI | 2-3주 | 2-3주 |
| Phase 2: Web + A2UI | 3-4주 | 5-7주 |
| Phase 3: TG Adaptive | 2주 | 7-9주 |
| Phase 4: TG Web App | 2주 | 9-11주 |
| Phase 5: A2A | 4주+ | 13-15주+ |

**총 예상: 약 3-4개월**

---

## 참고 자료

- [A2A Protocol Specification](https://a2a-protocol.org/latest/specification/)
- [A2UI Official Documentation](https://a2ui.org/)
- [AG-UI Protocol Documentation](https://docs.ag-ui.com/)
- [Telegram Bot API - Web Apps](https://core.telegram.org/bots/webapps)
- [Michael Architecture Analysis](./ARCHITECTURE_ANALYSIS.md)
- [Protocol Research](./PROTOCOL_RESEARCH.md)
