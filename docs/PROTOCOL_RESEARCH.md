# A2A / A2UI / AG-UI 프로토콜 기술 리서치

> **참고 자료** — 프로토콜 스펙 레퍼런스입니다. 실제 구현 아키텍처는 [ARCHITECTURE.md](ARCHITECTURE.md)를 참조하세요.

> **문서 버전**: 1.0
> **작성일**: 2026-02-01
> **목적**: 에이전트 통신 및 UI 프로토콜 기술 사양 정리

---

## 요약 비교표

| 구분 | A2A | A2UI | AG-UI |
|------|-----|------|-------|
| **제공자** | Google (Linux Foundation) | Google | CopilotKit + Microsoft |
| **최신 버전** | v0.3.0 (2025-07-30) | v0.8 (Public Preview) | 1.0 Stable |
| **용도** | 에이전트 ↔ 에이전트 | 에이전트 → UI 생성 | 에이전트 ↔ 사용자 |
| **전송** | JSON-RPC 2.0 / gRPC / REST | JSONL (Transport agnostic) | SSE over HTTP |
| **라이선스** | Apache 2.0 | Apache 2.0 | MIT |

---

## 1. A2A (Agent-to-Agent) Protocol

### 1.1 개요

> "An open protocol enabling communication and interoperability between opaque agentic applications."

- **발표**: 2025년 4월 9일 Google Cloud Next
- **거버넌스**: Linux Foundation 산하, 150+ 파트너 조직
- **GitHub**: https://github.com/a2aproject/A2A (21.7k stars)
- **공식 스펙**: https://a2a-protocol.org/latest/specification/

### 1.2 아키텍처 레이어

```
┌─────────────────────────────────────────────────────────┐
│  Layer 3: Protocol Bindings                             │
│  JSON-RPC 2.0 | gRPC | HTTP/REST                        │
├─────────────────────────────────────────────────────────┤
│  Layer 2: Abstract Operations                           │
│  SendMessage | GetTask | CancelTask | Subscribe...      │
├─────────────────────────────────────────────────────────┤
│  Layer 1: Data Model                                    │
│  Task | Message | Part | Artifact | AgentCard           │
└─────────────────────────────────────────────────────────┘
```

### 1.3 핵심 데이터 구조

#### AgentCard (자기 발견)

```json
{
  "name": "travel-agent",
  "url": "https://api.example.com/",
  "version": "1.0.0",
  "protocolVersion": "0.3.0",
  "capabilities": {
    "streaming": true,
    "pushNotifications": true
  },
  "skills": [
    {
      "id": "flight-booking",
      "name": "Flight Booking",
      "description": "Book flights worldwide"
    }
  ],
  "securitySchemes": {
    "oauth2": { "type": "oauth2", "flows": {} }
  }
}
```

**위치**: `/.well-known/agent.json`

#### Task 상태 머신

```
                    ┌─────────────┐
                    │  submitted  │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
              ┌─────│   working   │─────┐
              │     └──────┬──────┘     │
              │            │            │
    ┌─────────▼───┐  ┌─────▼─────┐  ┌───▼─────────┐
    │input-required│  │ completed │  │   failed    │
    └─────────────┘  └───────────┘  └─────────────┘
              │                            │
    ┌─────────▼───┐                 ┌──────▼──────┐
    │auth-required│                 │  canceled   │
    └─────────────┘                 └─────────────┘
                                    ┌─────────────┐
                                    │  rejected   │
                                    └─────────────┘
```

**TaskState 값**: 
- `submitted` - 제출됨
- `working` - 처리 중
- `input-required` - 입력 필요
- `auth-required` - 인증 필요
- `completed` - 완료
- `failed` - 실패
- `canceled` - 취소됨
- `rejected` - 거부됨
- `unknown` - 알 수 없음

#### Message 구조

```json
{
  "messageId": "msg_789",
  "role": "user",
  "parts": [
    {
      "type": "text",
      "text": "Book a flight to Tokyo"
    }
  ],
  "contextId": "context_456",
  "taskId": "task_123",
  "metadata": {}
}
```

#### Part 타입

| 타입 | 구조 | 설명 |
|------|------|------|
| **Text** | `{"type": "text", "text": "..."}` | 텍스트, 마크다운, HTML |
| **File** | `{"type": "file", "uri": "...", "mimeType": "..."}` | 파일 참조 |
| **Data** | `{"type": "data", "data": {...}}` | 구조화된 JSON |

### 1.4 JSON-RPC 메서드

| 카테고리 | 메서드 | 설명 |
|---------|--------|------|
| **Message** | `message/send` | 메시지 전송, Task 반환 |
| | `message/stream` | SSE 스트리밍 |
| **Task** | `tasks/get` | Task 상태 조회 |
| | `tasks/list` | Task 목록 (필터/페이징) |
| | `tasks/cancel` | Task 취소 |
| | `tasks/subscribe` | Task 업데이트 스트림 |
| **Push** | `tasks/pushNotificationConfig/create` | 웹훅 생성 |
| | `tasks/pushNotificationConfig/get` | 웹훅 조회 |
| | `tasks/pushNotificationConfig/list` | 웹훅 목록 |
| | `tasks/pushNotificationConfig/delete` | 웹훅 삭제 |
| **Agent** | `agent/getExtendedCard` | 인증된 AgentCard |

### 1.5 요청/응답 형식

#### 요청

```json
{
  "jsonrpc": "2.0",
  "id": "request_id",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "parts": [{"type": "text", "text": "Hello"}],
      "messageId": "msg_001"
    }
  }
}
```

#### 성공 응답

```json
{
  "jsonrpc": "2.0",
  "id": "request_id",
  "result": {
    "task": {
      "id": "task_123",
      "status": {"state": "working"}
    }
  }
}
```

#### 에러 응답

```json
{
  "jsonrpc": "2.0",
  "id": "request_id",
  "error": {
    "code": -32000,
    "message": "Task not found",
    "data": { "taskId": "invalid_id" }
  }
}
```

### 1.6 에러 코드

| 코드 | 이름 | 설명 |
|------|------|------|
| `-32700` | Parse Error | 잘못된 JSON |
| `-32600` | Invalid Request | 잘못된 JSON-RPC 구조 |
| `-32601` | Method Not Found | 알 수 없는 메서드 |
| `-32602` | Invalid Params | 잘못된 파라미터 |
| `-32603` | Internal Error | 서버 에러 |
| `-32000` | TaskNotFoundError | Task 없음 |
| `-32001` | PushNotificationNotSupportedError | 웹훅 미지원 |
| `-32002` | UnsupportedOperationError | 기능 미지원 |
| `-32003` | ContentTypeNotSupportedError | 미디어 타입 미지원 |
| `-32004` | VersionNotSupportedError | 프로토콜 버전 불일치 |

### 1.7 v0.3.0 신규 기능

| 기능 | 설명 |
|------|------|
| **gRPC 지원** | Protocol Buffers v3 기반 전송 |
| **서명된 보안 카드** | AgentCard 무결성 검증 |
| **Python SDK 확장** | `pip install a2a-sdk` |
| **에러 코드 표준화** | HTTP/gRPC/JSON-RPC 매핑 |

### 1.8 MCP vs A2A

| 구분 | MCP | A2A |
|------|-----|-----|
| **역할** | 도구/컨텍스트 제공 | 에이전트 간 협업 |
| **I/O** | 구조화됨 | 비구조화 (자율적) |
| **관계** | Tool 호출 | Peer-to-Peer |

### 1.9 SDK

```bash
# Python
pip install a2a-sdk

# JavaScript
npm install @a2a-protocol/sdk

# Go, Java, .NET도 지원
```

---

## 2. A2UI (Agent-to-UI) Protocol

### 2.1 개요

> "An open-source protocol for agent-driven, declarative user interfaces."

- **발표**: 2025년 12월 15일
- **상태**: v0.8 Public Preview
- **GitHub**: https://github.com/google/A2UI
- **공식 사이트**: https://a2ui.org/

### 2.2 설계 원칙

| 원칙 | 설명 |
|------|------|
| **Security-First** | 선언적 JSON, 코드 실행 없음. 사전 승인된 컴포넌트 카탈로그만 사용 |
| **LLM-Friendly** | Flat 구조로 점진적 생성 가능. 대화 진행에 따라 UI 점진적 변경 |
| **Framework-Agnostic** | React, Flutter, SwiftUI, Angular 등 모든 프레임워크 지원 |

### 2.3 메시지 플로우

```
Agent                          Client
  │                              │
  ├──── surfaceUpdate ──────────▶│  (컴포넌트 정의)
  │                              │
  ├──── dataModelUpdate ─────────▶│  (상태 업데이트)
  │                              │
  ├──── beginRendering ──────────▶│  (렌더링 시작)
  │                              │
  │◀──── userAction ─────────────┤  (사용자 입력)
  │                              │
```

### 2.4 메시지 타입

| 타입 | 설명 | 순서 |
|------|------|------|
| `surfaceUpdate` | 컴포넌트 정의 | 1 |
| `dataModelUpdate` | 상태 업데이트 | 2 |
| `beginRendering` | 렌더링 시작 | 3 |
| `deleteSurface` | Surface 삭제 | - |

#### surfaceUpdate 예시

```json
{
  "surfaceUpdate": {
    "surfaceId": "main",
    "components": [
      {
        "id": "booking-card",
        "component": {
          "Card": {
            "title": {"literalString": "Flight Booking"},
            "children": {"explicitList": ["date-input", "submit-btn"]}
          }
        }
      },
      {
        "id": "date-input",
        "component": {
          "DateTimeInput": {
            "label": {"literalString": "Departure"},
            "value": {"path": "/booking/date"}
          }
        }
      },
      {
        "id": "submit-btn",
        "component": {
          "Button": {
            "label": {"literalString": "Book Now"},
            "action": {
              "name": "submit_booking",
              "context": [
                {"key": "date", "value": {"path": "/booking/date"}}
              ]
            }
          }
        }
      }
    ]
  }
}
```

#### dataModelUpdate 예시

```json
{
  "dataModelUpdate": {
    "surfaceId": "main",
    "contents": [
      {"key": "booking", "valueMap": [
        {"key": "date", "valueString": "2026-03-15"},
        {"key": "destination", "valueString": "Tokyo"}
      ]},
      {"key": "user", "valueMap": [
        {"key": "name", "valueString": "John Doe"},
        {"key": "email", "valueString": "john@example.com"}
      ]}
    ]
  }
}
```

#### beginRendering 예시

```json
{
  "beginRendering": {
    "surfaceId": "main",
    "root": "booking-card",
    "catalogId": "https://a2ui.org/specification/v0_8/standard_catalog_definition.json"
  }
}
```

### 2.5 표준 컴포넌트 카탈로그

| 컴포넌트 | 용도 | 주요 속성 |
|---------|------|----------|
| `Text` | 텍스트 표시 | `text`, `usageHint` (h1, h2, h3, body, caption) |
| `Image` | 이미지 | `url`, `alt` |
| `Button` | 액션 버튼 | `label`, `action` |
| `TextField` | 텍스트 입력 | `label`, `value`, `placeholder` |
| `DateTimeInput` | 날짜/시간 | `label`, `value` |
| `Card` | 컨테이너 | `title`, `children` |
| `Row` | 가로 레이아웃 | `children`, `alignment` |
| `Column` | 세로 레이아웃 | `children`, `alignment` |
| `List` | 동적 목록 | `children` (template 사용) |
| `ListItem` | 목록 아이템 | `title`, `subtitle`, `trailing` |

### 2.6 BoundValue 시스템

```typescript
type BoundValue = {
  literalString?: string;      // 정적 문자열
  literalNumber?: number;      // 정적 숫자
  literalBoolean?: boolean;    // 정적 불린
  path?: string;               // JSON Pointer (/user/name)
}
```

**사용 예시**:

```json
// 리터럴만
{"literalString": "Hello"}

// 데이터 바인딩만
{"path": "/user/name"}

// 리터럴 + 바인딩 (초기값과 바인딩)
{
  "literalString": "Default Name",
  "path": "/user/name"
}
```

### 2.7 Data Model 구조

```json
{
  "dataModel": {
    "contents": [
      {"key": "user", "valueMap": [
        {"key": "name", "valueString": "John"},
        {"key": "age", "valueNumber": 30}
      ]},
      {"key": "items", "valueList": [
        {"valueString": "Item 1"},
        {"valueString": "Item 2"}
      ]}
    ]
  }
}
```

**Value 타입**:
- `valueString`: 문자열
- `valueNumber`: 숫자
- `valueBoolean`: 불린
- `valueMap`: 중첩 객체
- `valueList`: 배열

### 2.8 User Action (클라이언트 → 서버)

```json
{
  "userAction": {
    "name": "submit_booking",
    "surfaceId": "main",
    "sourceComponentId": "submit-btn",
    "timestamp": "2026-02-01T12:00:00Z",
    "context": {
      "date": "2026-03-15",
      "destination": "Tokyo"
    }
  }
}
```

### 2.9 렌더링 파이프라인

```
1. Agent가 선언적 JSON 전송
       ↓
2. 컴포넌트 카탈로그 검증
       ↓
3. 추상 컴포넌트 → 네이티브 위젯 매핑
       ↓
4. Data Model 경로에 바인딩
       ↓
5. 앱 스타일/접근성 적용 후 렌더링
```

---

## 3. AG-UI (Agent-User Interaction) Protocol

### 3.1 개요

> "The general-purpose, bi-directional connection between a user-facing application and any agentic backend."

- **개발**: CopilotKit (Microsoft 파트너)
- **통합**: LangGraph, CrewAI, Google ADK, AWS Strands, Oracle Agent Spec
- **GitHub**: https://github.com/ag-ui-protocol/ag-ui
- **공식 문서**: https://docs.ag-ui.com/

### 3.2 프로토콜 스택

```
┌─────────────────────────────────────────────────────────┐
│  Application Layer (CopilotKit, Custom UI)              │
├─────────────────────────────────────────────────────────┤
│  AG-UI Events (16 Standard Types)                       │
├─────────────────────────────────────────────────────────┤
│  Transport (SSE over HTTP, WebSocket optional)          │
├─────────────────────────────────────────────────────────┤
│  Agent Backend (LangGraph, CrewAI, ADK, etc.)           │
└─────────────────────────────────────────────────────────┘
```

### 3.3 이벤트 타입 (16개 + 확장)

#### Lifecycle Events (5개)

| 이벤트 | 필드 | 설명 |
|--------|------|------|
| `RunStarted` | `threadId`, `runId`, `parentRunId?`, `input?` | 실행 시작 |
| `RunFinished` | `threadId`, `runId`, `result?` | 실행 완료 |
| `RunError` | `message`, `code?` | 에러 발생 |
| `StepStarted` | `stepName` | 단계 시작 |
| `StepFinished` | `stepName` | 단계 완료 |

#### Text Message Events (4개)

| 이벤트 | 필드 | 설명 |
|--------|------|------|
| `TextMessageStart` | `messageId`, `role` | 메시지 시작 |
| `TextMessageContent` | `messageId`, `delta` | 텍스트 청크 |
| `TextMessageEnd` | `messageId` | 메시지 종료 |
| `TextMessageChunk` | `messageId`, `role?`, `delta?` | 편의 이벤트 (Start→Content→End 자동 확장) |

#### Tool Call Events (5개)

| 이벤트 | 필드 | 설명 |
|--------|------|------|
| `ToolCallStart` | `toolCallId`, `toolCallName`, `parentMessageId?` | 도구 호출 시작 |
| `ToolCallArgs` | `toolCallId`, `delta` | 인자 스트리밍 |
| `ToolCallEnd` | `toolCallId` | 호출 완료 |
| `ToolCallResult` | `messageId`, `toolCallId`, `content`, `role?` | 결과 반환 |
| `ToolCallChunk` | `toolCallId`, `toolCallName`, `delta?` | 편의 이벤트 |

#### State Management Events (3개)

| 이벤트 | 필드 | 설명 |
|--------|------|------|
| `StateSnapshot` | `snapshot` | 전체 상태 전송 |
| `StateDelta` | `delta` | RFC 6902 JSON Patch |
| `MessagesSnapshot` | `messages` | 대화 기록 동기화 |

#### Special Events (2개)

| 이벤트 | 필드 | 설명 |
|--------|------|------|
| `Raw` | `event`, `source?` | 외부 시스템 래핑 |
| `Custom` | `name`, `value` | 커스텀 확장 |

### 3.4 이벤트 스트림 예시

```
data: {"type":"RUN_STARTED","threadId":"t123","runId":"r456"}

data: {"type":"TEXT_MESSAGE_START","messageId":"m1","role":"assistant"}

data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"m1","delta":"I'll check "}

data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"m1","delta":"the weather..."}

data: {"type":"TOOL_CALL_START","toolCallId":"tc1","toolCallName":"get_weather"}

data: {"type":"TOOL_CALL_ARGS","toolCallId":"tc1","delta":"{\"city\":\"Seoul\"}"}

data: {"type":"TOOL_CALL_END","toolCallId":"tc1"}

data: {"type":"TOOL_CALL_RESULT","toolCallId":"tc1","content":"Sunny, 22°C"}

data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"m1","delta":"It's sunny!"}

data: {"type":"TEXT_MESSAGE_END","messageId":"m1"}

data: {"type":"RUN_FINISHED","threadId":"t123","runId":"r456"}
```

### 3.5 이벤트 패턴

#### Start-Content-End 패턴

```
TextMessageStart → TextMessageContent* → TextMessageEnd
ToolCallStart → ToolCallArgs* → ToolCallEnd → ToolCallResult
```

#### 상태 관리 패턴

```
StateSnapshot (전체 교체) vs StateDelta (부분 업데이트)
```

### 3.6 SDK 지원

| 언어 | 상태 | 패키지 |
|------|------|--------|
| Python | ✅ Stable | `ag-ui-sdk` |
| TypeScript | ✅ Stable | `@ag-ui/sdk` |
| Kotlin | ✅ Stable | Maven Central |
| Go | ✅ Stable | `github.com/ag-ui-protocol/ag-ui-go` |
| Rust | ✅ Stable | `crates.io/crates/ag-ui` |
| Java | ✅ Stable | Maven Central |
| Dart | ✅ Stable | pub.dev |
| .NET | 🚧 In Progress | - |

### 3.7 통합 프레임워크

**Backend 통합**:
- LangGraph
- CrewAI
- Microsoft Agent Framework
- Google ADK
- AWS Strands
- Mastra
- Pydantic AI
- Agno
- LlamaIndex
- AG2
- Oracle Agent Spec

**Frontend 통합**:
- CopilotKit (React)
- React Native (개발 중)
- Terminal clients

---

## 4. 프로토콜 상호 관계

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Interface                            │
│                     (Web, Mobile, Desktop)                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            │ AG-UI (사용자 ↔ 에이전트)
                            │ - 실시간 스트리밍
                            │ - 도구 실행 이벤트
                            ▼
┌───────────────────────────────────────────────────────────────────┐
│                      Agent Application                             │
│                                                                    │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐          │
│   │   Agent A   │◀──▶│   Agent B   │◀──▶│   Agent C   │          │
│   └─────────────┘    └─────────────┘    └─────────────┘          │
│          │                  │                  │                  │
│          └──────────────────┼──────────────────┘                  │
│                             │                                      │
│                     A2A Protocol                                   │
│                     (에이전트 ↔ 에이전트)                          │
│                                                                    │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │                     A2UI Renderer                        │    │
│   │                   (Rich UI 생성 시)                      │    │
│   └─────────────────────────────────────────────────────────┘    │
│                                                                    │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │                        MCP                               │    │
│   │              (도구 & 컨텍스트 제공)                       │    │
│   └─────────────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────────────┘
```

### 프로토콜 선택 가이드

| 시나리오 | 권장 프로토콜 |
|---------|--------------|
| 에이전트 간 협업 | A2A |
| 사용자 실시간 응답 | AG-UI |
| 리치 UI 생성 | A2UI |
| 도구/컨텍스트 | MCP |
| 단일 에이전트 + 실시간 | AG-UI |
| 멀티 에이전트 오케스트레이션 | A2A + AG-UI |

---

## 5. Michael 프로젝트 적용 권장

### 5.1 즉시 적용 가능: AG-UI

**이유**:
- Gateway WebSocket과 자연스러운 통합
- 실시간 응답 스트리밍
- 도구 실행 이벤트 발행

**구현 예시**:

```typescript
// Gateway 이벤트 확장
interface AGUIGatewayMessage extends GatewayMessage {
  streamId?: string;
  eventType?: 'RUN_STARTED' | 'RUN_FINISHED' | 'TEXT_MESSAGE_CONTENT' | 'TOOL_CALL_START' | 'TOOL_CALL_RESULT';
  toolCallId?: string;
  toolName?: string;
  toolArgs?: Record<string, any>;
  toolResult?: any;
}
```

### 5.2 장기 고려: A2A

**이유**:
- 멀티 에이전트 확장 시 필요
- 외부 에이전트 통합

### 5.3 선택적: A2UI

**이유**:
- Web UI 추가 시에만 필요
- Telegram은 마크업 제한적

---

## 참고 자료

### A2A Protocol
- **GitHub**: https://github.com/a2aproject/A2A
- **스펙**: https://a2a-protocol.org/latest/specification/
- **v0.3.0 스펙**: https://a2a-protocol.org/v0.3.0/specification/
- **Google Blog**: https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/
- **IBM 설명**: https://www.ibm.com/think/topics/agent2agent-protocol

### A2UI Protocol
- **GitHub**: https://github.com/google/A2UI
- **공식 사이트**: https://a2ui.org/
- **What is A2UI**: https://a2ui.org/introduction/what-is-a2ui/
- **Google Blog**: https://developers.googleblog.com/introducing-a2ui-an-open-project-for-agent-driven-interfaces/

### AG-UI Protocol
- **공식 문서**: https://docs.ag-ui.com/
- **이벤트 스펙**: https://docs.ag-ui.com/concepts/events
- **GitHub**: https://github.com/ag-ui-protocol/ag-ui
- **Microsoft Learn**: https://learn.microsoft.com/en-us/agent-framework/integrations/ag-ui/
- **CopilotKit**: https://www.copilotkit.ai/blog/introducing-ag-ui-the-protocol-where-agents-meet-users
