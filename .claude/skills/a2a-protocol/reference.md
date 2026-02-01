# A2A Protocol Reference

Detailed reference for A2A Protocol v0.3.0 data types and structures.

---

## Complete Type Definitions

### AgentCard (Full Schema)

```typescript
interface AgentCard {
  // Required fields
  name: string;                          // Unique agent identifier
  description: string;                   // Human-readable description
  url: string;                           // Base URL for agent endpoint
  version: string;                       // Agent version (semver)

  // Protocol info
  protocolVersion: string;               // "0.3.0"
  preferredTransport?: "JSONRPC" | "GRPC";

  // Content modes
  defaultInputModes: ContentType[];      // ["text", "file", "data"]
  defaultOutputModes: ContentType[];

  // Capabilities
  capabilities: AgentCapabilities;

  // Skills
  skills: AgentSkill[];

  // Security
  securitySchemes?: Record<string, SecurityScheme>;
  security?: SecurityRequirement[];

  // Optional metadata
  provider?: ProviderInfo;
  documentationUrl?: string;
  supportsAuthenticatedExtendedCard?: boolean;
}

interface AgentCapabilities {
  streaming?: boolean;                   // SSE support
  pushNotifications?: boolean;           // Webhook support
  extendedAgentCard?: boolean;           // Auth-only card info
  stateTransitionHistory?: boolean;      // Full state history
}

interface AgentSkill {
  id: string;                            // Unique skill ID
  name: string;                          // Display name
  description: string;                   // What this skill does
  examples?: string[];                   // Example queries
  tags?: string[];                       // Categorization
  inputModes?: ContentType[];            // Override defaults
  outputModes?: ContentType[];
}

interface ProviderInfo {
  organization: string;
  url?: string;
}
```

### Task (Full Schema)

```typescript
interface Task {
  id: string;                            // Unique task ID
  contextId?: string;                    // Conversation context
  status: TaskStatus;                    // Current state
  artifacts?: Artifact[];                // Output artifacts
  history?: Message[];                   // Message history
  metadata?: Record<string, any>;        // Custom metadata
}

interface TaskStatus {
  state: TaskState;
  timestamp: string;                     // ISO 8601
  message?: StatusMessage;               // Optional status message
  error?: TaskError;                     // Error details (if failed)
}

type TaskState =
  | "submitted"
  | "working"
  | "input-required"
  | "auth-required"
  | "completed"
  | "failed"
  | "cancelled"
  | "rejected";

interface TaskError {
  code: string;
  message: string;
  data?: any;
}
```

### Message (Full Schema)

```typescript
interface Message {
  messageId?: string;                    // Unique message ID
  role: "user" | "agent";                // Sender role
  parts: Part[];                         // Content parts
  contextId?: string;                    // Conversation context
  taskId?: string;                       // Associated task
  referenceTaskIds?: string[];           // Related tasks
  metadata?: Record<string, any>;        // Custom metadata
  extensions?: string[];                 // Extension URIs
}
```

### Part Types

```typescript
// Union type for all part types
type Part = TextPart | FilePart | DataPart;

interface TextPart {
  type: "text";
  text: string;
  mimeType?: string;                     // "text/plain", "text/markdown", etc.
}

interface FilePart {
  type: "file";
  uri: string;                           // File URI
  name?: string;                         // Display name
  mimeType?: string;                     // MIME type
  size?: number;                         // File size in bytes
}

interface DataPart {
  type: "data";
  data: any;                             // JSON-serializable data
  schema?: string;                       // JSON Schema URI
  mimeType?: string;                     // Default: application/json
}
```

### Artifact (Full Schema)

```typescript
interface Artifact {
  id: string;                            // Unique artifact ID
  name?: string;                         // Display name
  description?: string;                  // Human-readable description
  parts: Part[];                         // Content parts
  index?: number;                        // Order in sequence
  append?: boolean;                      // Append to existing
  lastChunk?: boolean;                   // Final chunk indicator
  metadata?: Record<string, any>;        // Custom metadata
}
```

---

## JSON-RPC Request/Response Types

### SendMessageRequest

```typescript
interface SendMessageRequest {
  jsonrpc: "2.0";
  id: string | number;
  method: "message/send";
  params: {
    message: Message;
    configuration?: SendConfiguration;
  };
}

interface SendConfiguration {
  acceptedOutputModes?: ContentType[];
  blocking?: boolean;                    // Wait for completion
  historyLength?: number;                // Include N history messages
}
```

### SendMessageResponse

```typescript
// Success - Task created
interface SendMessageTaskResponse {
  jsonrpc: "2.0";
  id: string | number;
  result: {
    task: Task;
  };
}

// Success - Immediate response
interface SendMessageMessageResponse {
  jsonrpc: "2.0";
  id: string | number;
  result: {
    message: Message;
  };
}
```

### GetTaskRequest

```typescript
interface GetTaskRequest {
  jsonrpc: "2.0";
  id: string | number;
  method: "tasks/get";
  params: {
    id: string;                          // Task ID
    historyLength?: number;              // Include N history messages
  };
}
```

### ListTasksRequest

```typescript
interface ListTasksRequest {
  jsonrpc: "2.0";
  id: string | number;
  method: "tasks/list";
  params: {
    contextId?: string;                  // Filter by context
    status?: TaskState[];                // Filter by states
    pageSize?: number;                   // 1-100, default 50
    pageToken?: string;                  // Pagination cursor
    historyLength?: number;
    createdAfter?: string;               // ISO 8601
    createdBefore?: string;
    includeArtifacts?: boolean;
  };
}

interface ListTasksResponse {
  jsonrpc: "2.0";
  id: string | number;
  result: {
    tasks: Task[];
    nextPageToken?: string;
    totalSize?: number;
  };
}
```

### CancelTaskRequest

```typescript
interface CancelTaskRequest {
  jsonrpc: "2.0";
  id: string | number;
  method: "tasks/cancel";
  params: {
    id: string;                          // Task ID
  };
}
```

---

## Streaming Event Types

```typescript
// Wrapper for all streaming events
interface StreamResponse {
  task?: Task;                           // Initial task state
  message?: Message;                     // Direct response
  statusUpdate?: TaskStatusUpdateEvent;  // State change
  artifactUpdate?: TaskArtifactUpdateEvent;  // Artifact update
}

interface TaskStatusUpdateEvent {
  taskId: string;
  contextId?: string;
  status: TaskStatus;
  final: boolean;                        // Is terminal state
}

interface TaskArtifactUpdateEvent {
  taskId: string;
  contextId?: string;
  artifact: Artifact;
}
```

---

## Security Scheme Types

```typescript
interface ApiKeySecurityScheme {
  type: "apiKey";
  in: "header" | "query" | "cookie";
  name: string;
}

interface HttpSecurityScheme {
  type: "http";
  scheme: "bearer" | "basic" | "digest";
  bearerFormat?: string;
}

interface OAuth2SecurityScheme {
  type: "oauth2";
  flows: {
    authorizationCode?: OAuth2AuthorizationCodeFlow;
    clientCredentials?: OAuth2ClientCredentialsFlow;
    deviceCode?: OAuth2DeviceCodeFlow;
  };
}

interface OAuth2ClientCredentialsFlow {
  tokenUrl: string;
  refreshUrl?: string;
  scopes: Record<string, string>;
}

interface OpenIdConnectSecurityScheme {
  type: "openIdConnect";
  openIdConnectUrl: string;
}

interface MutualTLSSecurityScheme {
  type: "mutualTLS";
}
```

---

## Push Notification Types

```typescript
interface PushNotificationConfig {
  id?: string;
  url: string;                           // Webhook URL
  token?: string;                        // Verification token
  authentication?: PushNotificationAuth;
}

interface PushNotificationAuth {
  type: "bearer" | "basic" | "apiKey";
  token?: string;                        // For bearer
  username?: string;                     // For basic
  password?: string;                     // For basic
  headerName?: string;                   // For apiKey
  headerValue?: string;                  // For apiKey
}

// Webhook payload
interface PushNotificationPayload {
  taskId: string;
  event: StreamResponse;
  timestamp: string;
}
```

---

## Error Types

```typescript
interface A2AError {
  code: number;
  message: string;
  data?: any;
}

// Standard JSON-RPC errors
const PARSE_ERROR = -32700;
const INVALID_REQUEST = -32600;
const METHOD_NOT_FOUND = -32601;
const INVALID_PARAMS = -32602;
const INTERNAL_ERROR = -32603;

// A2A-specific errors
const TASK_NOT_FOUND = -32000;
const PUSH_NOTIFICATION_NOT_SUPPORTED = -32001;
const UNSUPPORTED_OPERATION = -32002;
const CONTENT_TYPE_NOT_SUPPORTED = -32003;
const VERSION_NOT_SUPPORTED = -32004;
```

---

## Content Types

```typescript
type ContentType = "text" | "file" | "data";

// Common MIME types
const MIME_TYPES = {
  TEXT_PLAIN: "text/plain",
  TEXT_MARKDOWN: "text/markdown",
  TEXT_HTML: "text/html",
  APPLICATION_JSON: "application/json",
  IMAGE_PNG: "image/png",
  IMAGE_JPEG: "image/jpeg",
  APPLICATION_PDF: "application/pdf",
};
```

---

## Python SDK Type Mapping

| TypeScript | Python SDK |
|------------|------------|
| `AgentCard` | `a2a.types.AgentCard` |
| `AgentCapabilities` | `a2a.types.AgentCapabilities` |
| `AgentSkill` | `a2a.types.AgentSkill` |
| `Task` | `a2a.types.Task` |
| `TaskStatus` | `a2a.types.TaskStatus` |
| `TaskState` | `a2a.types.TaskState` |
| `Message` | `a2a.types.Message` |
| `Part` | `a2a.types.Part` |
| `TextPart` | `a2a.types.TextPart` |
| `FilePart` | `a2a.types.FilePart` |
| `DataPart` | `a2a.types.DataPart` |
| `Artifact` | `a2a.types.Artifact` |
| `ContentType` | `a2a.types.ContentTypes` |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.3.0 | 2024 | Current stable, streaming, push notifications |
| 0.2.x | 2024 | Extended agent cards, pagination |
| 0.1.x | 2024 | Initial specification |
