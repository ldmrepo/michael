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
  PARSE_ERROR: -32700,
  INVALID_REQUEST: -32600,
  METHOD_NOT_FOUND: -32601,
  INVALID_PARAMS: -32602,
  INTERNAL_ERROR: -32603,
  // Custom A2A error codes (-32000 to -32099)
  TASK_NOT_FOUND: -32001,
  TASK_CANCELLED: -32002,
  AGENT_UNAVAILABLE: -32003,
  AUTHENTICATION_REQUIRED: -32004,
  RATE_LIMITED: -32005,
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
 * Task definition
 */
export interface Task {
  /** Unique task ID */
  id: string;
  /** Task status */
  status: TaskStatus;
  /** Input message */
  input: A2AMessage;
  /** Output message (when completed) */
  output?: A2AMessage;
  /** Task artifacts */
  artifacts?: TaskArtifact[];
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
