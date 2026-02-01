/**
 * A2A Protocol Type Definitions
 *
 * Agent-to-Agent (A2A) protocol types for inter-agent communication.
 * Based on the A2A Protocol Specification.
 *
 * @see https://a2a-protocol.org/
 */

// --- JSON-RPC 2.0 Base Types ---

/**
 * JSON-RPC 2.0 request
 */
export interface JSONRPCRequest {
  jsonrpc: '2.0';
  id: string | number;
  method: string;
  params?: Record<string, unknown>;
}

/**
 * JSON-RPC 2.0 response
 */
export interface JSONRPCResponse {
  jsonrpc: '2.0';
  id: string | number;
  result?: unknown;
  error?: JSONRPCError;
}

/**
 * JSON-RPC 2.0 error
 */
export interface JSONRPCError {
  code: number;
  message: string;
  data?: unknown;
}

// --- Standard JSON-RPC Error Codes ---

export const JSON_RPC_ERRORS = {
  // Standard JSON-RPC errors
  PARSE_ERROR: -32700,
  INVALID_REQUEST: -32600,
  METHOD_NOT_FOUND: -32601,
  INVALID_PARAMS: -32602,
  INTERNAL_ERROR: -32603,
  // Custom A2A error codes (-32000 to -32099)
  TASK_NOT_FOUND: -32000,
  PUSH_NOTIFICATION_NOT_SUPPORTED: -32001,
  UNSUPPORTED_OPERATION: -32002,
  CONTENT_TYPE_NOT_SUPPORTED: -32003,
  VERSION_NOT_SUPPORTED: -32004,
  // Additional custom errors
  TASK_CANCELLED: -32010,
  AGENT_UNAVAILABLE: -32011,
  AUTHENTICATION_REQUIRED: -32012,
  RATE_LIMITED: -32013,
  CONFIG_NOT_FOUND: -32014,
} as const;

// --- Agent Card Types ---

/**
 * Skill definition
 */
export interface AgentSkill {
  /** Unique skill identifier */
  id: string;
  /** Human-readable name */
  name: string;
  /** Description of what the skill does */
  description: string;
  /** Example prompts */
  examples?: string[];
  /** Input schema (JSON Schema) */
  inputSchema?: Record<string, unknown>;
  /** Output schema (JSON Schema) */
  outputSchema?: Record<string, unknown>;
}

/**
 * Agent capabilities
 */
export interface AgentCapabilities {
  /** Supports streaming responses */
  streaming?: boolean;
  /** Supports push notifications */
  pushNotifications?: boolean;
  /** Supports A2UI rendering */
  a2ui?: boolean;
  /** Supports multi-turn conversations */
  multiTurn?: boolean;
  /** Supports state persistence */
  stateful?: boolean;
}

/**
 * Security scheme
 */
export interface SecurityScheme {
  type: 'apiKey' | 'oauth2' | 'bearer' | 'custom';
  description?: string;
  /** For apiKey: header, query, or cookie */
  in?: 'header' | 'query' | 'cookie';
  /** For apiKey: name of the header/query/cookie */
  name?: string;
}

/**
 * Agent Card - describes an agent's capabilities
 */
export interface AgentCard {
  /** Agent name */
  name: string;
  /** Agent description */
  description: string;
  /** Base URL of the agent */
  url: string;
  /** Agent version */
  version: string;
  /** A2A protocol version */
  protocolVersion: string;
  /** Supported input modes */
  defaultInputModes: ('text' | 'audio' | 'image' | 'file')[];
  /** Supported output modes */
  defaultOutputModes: ('text' | 'audio' | 'image' | 'file' | 'a2ui')[];
  /** Agent capabilities */
  capabilities: AgentCapabilities;
  /** Available skills */
  skills?: AgentSkill[];
  /** Security schemes */
  securitySchemes?: Record<string, SecurityScheme>;
  /** Provider information */
  provider?: {
    name: string;
    url?: string;
    contact?: string;
  };
}

// --- Message Types ---

/**
 * Message role
 */
export type MessageRole = 'user' | 'assistant' | 'system';

/**
 * Message part - text
 */
export interface TextPart {
  type: 'text';
  text: string;
}

/**
 * Message part - file/image
 */
export interface FilePart {
  type: 'file';
  mimeType: string;
  data?: string; // base64 encoded
  url?: string;
}

/**
 * Message part - A2UI
 */
export interface A2UIPart {
  type: 'a2ui';
  a2ui: unknown; // A2UI message
}

/**
 * Message part union
 */
export type MessagePart = TextPart | FilePart | A2UIPart;

/**
 * A2A Message
 */
export interface A2AMessage {
  role: MessageRole;
  parts: MessagePart[];
  /** Optional metadata */
  metadata?: Record<string, unknown>;
}

// --- Task Types ---

/**
 * Task status
 */
export type TaskStatus =
  | 'pending'
  | 'working'
  | 'completed'
  | 'failed'
  | 'cancelled';

/**
 * Task artifact
 */
export interface TaskArtifact {
  /** Artifact type */
  type: string;
  /** MIME type */
  mimeType: string;
  /** Artifact data */
  data: unknown;
}

/**
 * Task status info (v0.3.0 standard)
 */
export interface TaskStatusInfo {
  /** Current state */
  state: TaskStatus;
  /** Status timestamp */
  timestamp: string;
  /** Optional status message */
  message?: string;
}

/**
 * Task definition (v0.3.0 standard)
 * @see https://a2a-protocol.org/latest/definitions/#task
 */
export interface Task {
  /** Unique task ID */
  id: string;
  /** Context ID for conversation continuity */
  contextId?: string;
  /** Task status info */
  status: TaskStatusInfo;
  /** Task artifacts */
  artifacts?: TaskArtifact[];
  /** Message history */
  history?: A2AMessage[];
  /** Creation timestamp */
  createdAt: string;
  /** Last updated timestamp */
  updatedAt: string;
  /** Error message (if failed) */
  error?: string;
  /** Metadata */
  metadata?: Record<string, unknown>;
}

// --- A2A Method Parameters ---

/**
 * message/send parameters
 */
export interface MessageSendParams {
  message: A2AMessage;
  /** Optional task metadata */
  metadata?: Record<string, unknown>;
}

/**
 * message/send result
 */
export interface MessageSendResult {
  task: Task;
}

/**
 * message/stream parameters
 */
export interface MessageStreamParams {
  message: A2AMessage;
  /** Optional task metadata */
  metadata?: Record<string, unknown>;
}

/**
 * tasks/get parameters
 */
export interface TasksGetParams {
  taskId: string;
}

/**
 * tasks/get result
 */
export interface TasksGetResult {
  task: Task;
}

/**
 * tasks/cancel parameters
 */
export interface TasksCancelParams {
  taskId: string;
}

/**
 * tasks/cancel result
 */
export interface TasksCancelResult {
  task: Task;
}

/**
 * tasks/list parameters
 */
export interface TasksListParams {
  /** Filter by status */
  status?: TaskStatus;
  /** Limit results */
  limit?: number;
  /** Offset for pagination */
  offset?: number;
}

/**
 * tasks/list result
 */
export interface TasksListResult {
  tasks: Task[];
  total: number;
}

/**
 * tasks/subscribe parameters (v0.3.0 standard)
 * Subscribe to task updates via SSE stream
 */
export interface TasksSubscribeParams {
  /** Task ID to subscribe to */
  taskId: string;
}

// --- Push Notification Config Types (v0.3.0 standard) ---

/**
 * Push notification authentication
 */
export interface PushNotificationAuth {
  /** Authentication type */
  type: 'bearer' | 'apiKey' | 'none';
  /** Token or API key */
  token?: string;
  /** Header name for apiKey type */
  headerName?: string;
}

/**
 * Push notification configuration
 */
export interface PushNotificationConfig {
  /** Unique config ID */
  id: string;
  /** Task ID this config is for */
  taskId: string;
  /** Webhook URL to receive notifications */
  url: string;
  /** Authentication settings */
  authentication?: PushNotificationAuth;
  /** Events to receive notifications for */
  events?: ('statusUpdate' | 'artifactUpdate' | 'message')[];
  /** Creation timestamp */
  createdAt: string;
}

/**
 * tasks/pushNotificationConfig/create parameters
 */
export interface PushNotificationConfigCreateParams {
  taskId: string;
  url: string;
  authentication?: PushNotificationAuth;
  events?: ('statusUpdate' | 'artifactUpdate' | 'message')[];
}

/**
 * tasks/pushNotificationConfig/create result
 */
export interface PushNotificationConfigCreateResult {
  config: PushNotificationConfig;
}

/**
 * tasks/pushNotificationConfig/get parameters
 */
export interface PushNotificationConfigGetParams {
  taskId: string;
  configId: string;
}

/**
 * tasks/pushNotificationConfig/get result
 */
export interface PushNotificationConfigGetResult {
  config: PushNotificationConfig;
}

/**
 * tasks/pushNotificationConfig/list parameters
 */
export interface PushNotificationConfigListParams {
  taskId: string;
}

/**
 * tasks/pushNotificationConfig/list result
 */
export interface PushNotificationConfigListResult {
  configs: PushNotificationConfig[];
}

/**
 * tasks/pushNotificationConfig/delete parameters
 */
export interface PushNotificationConfigDeleteParams {
  taskId: string;
  configId: string;
}

/**
 * tasks/pushNotificationConfig/delete result
 */
export interface PushNotificationConfigDeleteResult {
  success: boolean;
}

// --- SSE Event Types for tasks/subscribe ---

/**
 * Task status update event (SSE)
 */
export interface TaskStatusUpdateEvent {
  type: 'statusUpdate';
  taskId: string;
  status: TaskStatusInfo;
}

/**
 * Task artifact update event (SSE)
 */
export interface TaskArtifactUpdateEvent {
  type: 'artifactUpdate';
  taskId: string;
  artifact: TaskArtifact;
}

/**
 * Task message event (SSE)
 */
export interface TaskMessageEvent {
  type: 'message';
  taskId: string;
  message: A2AMessage;
}

/**
 * Union of all task SSE event types
 */
export type TaskSubscribeEvent =
  | TaskStatusUpdateEvent
  | TaskArtifactUpdateEvent
  | TaskMessageEvent;

// --- Type Guards ---

export function isTextPart(part: MessagePart): part is TextPart {
  return part.type === 'text';
}

export function isFilePart(part: MessagePart): part is FilePart {
  return part.type === 'file';
}

export function isA2UIPart(part: MessagePart): part is A2UIPart {
  return part.type === 'a2ui';
}

// --- Utility Functions ---

/**
 * Create a JSON-RPC response
 */
export function createJSONRPCResponse(
  id: string | number,
  result: unknown
): JSONRPCResponse {
  return { jsonrpc: '2.0', id, result };
}

/**
 * Create a JSON-RPC error response
 */
export function createJSONRPCError(
  id: string | number,
  code: number,
  message: string,
  data?: unknown
): JSONRPCResponse {
  return { jsonrpc: '2.0', id, error: { code, message, data } };
}

/**
 * Create a text message
 */
export function createTextMessage(role: MessageRole, text: string): A2AMessage {
  return { role, parts: [{ type: 'text', text }] };
}

/**
 * Extract text from message
 */
export function extractTextFromMessage(message: A2AMessage): string {
  return message.parts
    .filter(isTextPart)
    .map((p) => p.text)
    .join('\n');
}

// --- Task Helper Functions ---

/**
 * Generate a unique ID
 */
export function generateId(prefix: string = 'id'): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
}

/**
 * Create a new task (v0.3.0 standard)
 */
export function createTask(
  input: A2AMessage,
  contextId?: string,
  metadata?: Record<string, unknown>
): Task {
  const now = new Date().toISOString();
  return {
    id: generateId('task'),
    contextId,
    status: {
      state: 'pending',
      timestamp: now,
    },
    history: [input],
    createdAt: now,
    updatedAt: now,
    metadata,
  };
}

/**
 * Update task status
 */
export function updateTaskStatus(
  task: Task,
  state: TaskStatus,
  message?: string
): Task {
  const now = new Date().toISOString();
  return {
    ...task,
    status: {
      state,
      timestamp: now,
      message,
    },
    updatedAt: now,
  };
}

/**
 * Add message to task history
 */
export function addTaskMessage(task: Task, message: A2AMessage): Task {
  return {
    ...task,
    history: [...(task.history || []), message],
    updatedAt: new Date().toISOString(),
  };
}

/**
 * Add artifact to task
 */
export function addTaskArtifact(task: Task, artifact: TaskArtifact): Task {
  return {
    ...task,
    artifacts: [...(task.artifacts || []), artifact],
    updatedAt: new Date().toISOString(),
  };
}

/**
 * Complete task with output
 */
export function completeTask(
  task: Task,
  output: A2AMessage,
  artifacts?: TaskArtifact[]
): Task {
  const now = new Date().toISOString();
  return {
    ...task,
    status: {
      state: 'completed',
      timestamp: now,
    },
    history: [...(task.history || []), output],
    artifacts: artifacts ? [...(task.artifacts || []), ...artifacts] : task.artifacts,
    updatedAt: now,
  };
}

/**
 * Fail task with error
 */
export function failTask(task: Task, error: string): Task {
  const now = new Date().toISOString();
  return {
    ...task,
    status: {
      state: 'failed',
      timestamp: now,
      message: error,
    },
    error,
    updatedAt: now,
  };
}
