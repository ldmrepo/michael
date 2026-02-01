/**
 * AG-UI Protocol Type Definitions
 *
 * AG-UI (Agent-User Interface) is a standardized protocol for agent-to-user communication.
 * This implementation wraps A2UI messages in AG-UI TOOL_CALL events for standard compliance.
 *
 * @see https://github.com/ag-ui-org/ag-ui
 */

// --- Event Types ---

/**
 * All AG-UI event types
 */
export type AGUIEventType =
  | 'RUN_STARTED'
  | 'RUN_FINISHED'
  | 'RUN_ERROR'
  | 'TEXT_MESSAGE_START'
  | 'TEXT_MESSAGE_CONTENT'
  | 'TEXT_MESSAGE_END'
  | 'TOOL_CALL_START'
  | 'TOOL_CALL_ARGS'
  | 'TOOL_CALL_END'
  | 'TOOL_CALL_RESULT'
  | 'TOOL_CALL_REQUEST';

// --- Base Event ---

/**
 * Base interface for all AG-UI events
 * @see https://learn.microsoft.com/agent-framework/integrations/ag-ui/
 */
export interface AGUIBaseEvent {
  type: AGUIEventType;
  threadId: string;
  runId: string;
  /** ISO 8601 timestamp (required per AG-UI standard) */
  timestamp: string;
}

// --- Run Events ---

/**
 * RUN_STARTED: Signals the start of agent processing
 */
export interface RunStartedEvent extends AGUIBaseEvent {
  type: 'RUN_STARTED';
}

/**
 * RUN_FINISHED: Signals successful completion of agent processing
 */
export interface RunFinishedEvent extends AGUIBaseEvent {
  type: 'RUN_FINISHED';
}

/**
 * RUN_ERROR: Signals an error during agent processing
 */
export interface RunErrorEvent extends AGUIBaseEvent {
  type: 'RUN_ERROR';
  message: string;
  code?: string;
}

// --- Text Message Events ---

/**
 * TEXT_MESSAGE_START: Signals the start of a text message stream
 */
export interface TextMessageStartEvent extends AGUIBaseEvent {
  type: 'TEXT_MESSAGE_START';
  messageId: string;
  role: 'user' | 'assistant' | 'system';
}

/**
 * TEXT_MESSAGE_CONTENT: Contains a chunk of text content
 */
export interface TextMessageContentEvent extends AGUIBaseEvent {
  type: 'TEXT_MESSAGE_CONTENT';
  messageId: string;
  delta: string;
}

/**
 * TEXT_MESSAGE_END: Signals the end of a text message stream
 */
export interface TextMessageEndEvent extends AGUIBaseEvent {
  type: 'TEXT_MESSAGE_END';
  messageId: string;
}

// --- Tool Call Events (Backend Tools) ---

/**
 * TOOL_CALL_START: Signals the start of a backend tool call
 */
export interface ToolCallStartEvent extends AGUIBaseEvent {
  type: 'TOOL_CALL_START';
  toolCallId: string;
  toolCallName: string;
}

/**
 * TOOL_CALL_ARGS: Contains streamed arguments for a tool call
 */
export interface ToolCallArgsEvent extends AGUIBaseEvent {
  type: 'TOOL_CALL_ARGS';
  toolCallId: string;
  delta: string;
}

/**
 * TOOL_CALL_END: Signals the end of tool call arguments
 */
export interface ToolCallEndEvent extends AGUIBaseEvent {
  type: 'TOOL_CALL_END';
  toolCallId: string;
}

/**
 * Tool call result content structure
 */
export interface ToolCallResultContent {
  mimeType: string;
  data: unknown;
}

/**
 * TOOL_CALL_RESULT: Contains the result of a tool call
 * A2UI messages are transmitted as TOOL_CALL_RESULT with mimeType "application/json+a2ui"
 */
export interface ToolCallResultEvent extends AGUIBaseEvent {
  type: 'TOOL_CALL_RESULT';
  toolCallId: string;
  content: ToolCallResultContent;
}

// --- Frontend Tool Events ---

/**
 * TOOL_CALL_REQUEST: Request for frontend to execute a tool (e.g., user confirmation)
 * This replaces the A2UI userAction pattern with a standard AG-UI approach
 */
export interface ToolCallRequestEvent extends AGUIBaseEvent {
  type: 'TOOL_CALL_REQUEST';
  toolCallId: string;
  toolName: string;
  arguments: Record<string, unknown>;
}

// --- Union Type ---

/**
 * Union of all AG-UI event types
 */
export type AGUIEvent =
  | RunStartedEvent
  | RunFinishedEvent
  | RunErrorEvent
  | TextMessageStartEvent
  | TextMessageContentEvent
  | TextMessageEndEvent
  | ToolCallStartEvent
  | ToolCallArgsEvent
  | ToolCallEndEvent
  | ToolCallResultEvent
  | ToolCallRequestEvent;

// --- State Types ---

/**
 * AG-UI connection/run state
 */
export type AGUIStatus = 'idle' | 'running' | 'completed' | 'error';

/**
 * AG-UI state for tracking current run
 */
export interface AGUIState {
  threadId: string | null;
  runId: string | null;
  status: AGUIStatus;
  error?: string;
}

// --- Constants ---

/**
 * MIME type for A2UI messages transmitted via AG-UI TOOL_CALL_RESULT
 */
export const A2UI_MIME_TYPE = 'application/json+a2ui';

/**
 * Tool name used for A2UI rendering in AG-UI protocol
 */
export const A2UI_TOOL_NAME = 'render_a2ui';

// --- Type Guards ---

/**
 * Check if an event is a run event
 */
export function isRunEvent(event: AGUIEvent): event is RunStartedEvent | RunFinishedEvent | RunErrorEvent {
  return event.type === 'RUN_STARTED' || event.type === 'RUN_FINISHED' || event.type === 'RUN_ERROR';
}

/**
 * Check if an event is a text message event
 */
export function isTextMessageEvent(event: AGUIEvent): event is TextMessageStartEvent | TextMessageContentEvent | TextMessageEndEvent {
  return event.type.startsWith('TEXT_MESSAGE_');
}

/**
 * Check if an event is a tool call event
 */
export function isToolCallEvent(event: AGUIEvent): event is ToolCallStartEvent | ToolCallArgsEvent | ToolCallEndEvent | ToolCallResultEvent {
  return event.type.startsWith('TOOL_CALL_') && event.type !== 'TOOL_CALL_REQUEST';
}

/**
 * Check if an event is a frontend tool request
 */
export function isToolCallRequestEvent(event: AGUIEvent): event is ToolCallRequestEvent {
  return event.type === 'TOOL_CALL_REQUEST';
}

/**
 * Check if a TOOL_CALL_RESULT contains A2UI data
 */
export function isA2UIResult(event: AGUIEvent): event is ToolCallResultEvent {
  return (
    event.type === 'TOOL_CALL_RESULT' &&
    (event as ToolCallResultEvent).content?.mimeType === A2UI_MIME_TYPE
  );
}
