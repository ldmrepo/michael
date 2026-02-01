/**
 * AG-UI Protocol Type Definitions
 *
 * AG-UI (Agent-User Interface) is a standardized protocol for agent-to-user communication.
 * This implementation follows the a2ui-demo reference architecture.
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
 */
export interface AGUIBaseEvent {
  type: AGUIEventType;
  threadId: string;
  runId: string;
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
 */
export interface ToolCallResultEvent extends AGUIBaseEvent {
  type: 'TOOL_CALL_RESULT';
  toolCallId: string;
  content: ToolCallResultContent;
}

// --- Frontend Tool Events ---

/**
 * TOOL_CALL_REQUEST: Request for frontend to execute a tool
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

// --- ID Generators ---

/**
 * Generate a unique ID with prefix
 */
export function generateId(prefix: string = 'id'): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
}

/**
 * Run ID 생성
 */
export function generateRunId(): string {
  return generateId('run');
}

/**
 * Message ID 생성
 */
export function generateMessageId(): string {
  return generateId('msg');
}

/**
 * Thread ID 생성
 */
export function generateThreadId(): string {
  return generateId('thread');
}

/**
 * Tool Call ID 생성
 */
export function generateToolCallId(): string {
  return generateId('tool');
}

/**
 * Get current timestamp in ISO format
 */
export function getTimestamp(): string {
  return new Date().toISOString();
}

// --- Run Event Helpers ---

/**
 * RUN_STARTED 이벤트 생성
 */
export function createRunStarted(threadId: string, runId: string): RunStartedEvent {
  return {
    type: 'RUN_STARTED',
    threadId,
    runId,
    timestamp: getTimestamp(),
  };
}

/**
 * RUN_FINISHED 이벤트 생성
 */
export function createRunFinished(threadId: string, runId: string): RunFinishedEvent {
  return {
    type: 'RUN_FINISHED',
    threadId,
    runId,
    timestamp: getTimestamp(),
  };
}

/**
 * RUN_ERROR 이벤트 생성
 */
export function createRunError(
  threadId: string,
  runId: string,
  message: string,
  code?: string
): RunErrorEvent {
  const event: RunErrorEvent = {
    type: 'RUN_ERROR',
    threadId,
    runId,
    message,
    timestamp: getTimestamp(),
  };
  if (code) {
    event.code = code;
  }
  return event;
}

// --- Text Message Event Helpers ---

/**
 * TEXT_MESSAGE_START 이벤트 생성
 */
export function createTextMessageStart(
  threadId: string,
  runId: string,
  messageId: string,
  role: 'user' | 'assistant' | 'system' = 'assistant'
): TextMessageStartEvent {
  return {
    type: 'TEXT_MESSAGE_START',
    threadId,
    runId,
    messageId,
    role,
    timestamp: getTimestamp(),
  };
}

/**
 * TEXT_MESSAGE_CONTENT 이벤트 생성
 */
export function createTextMessageContent(
  threadId: string,
  runId: string,
  messageId: string,
  delta: string
): TextMessageContentEvent {
  return {
    type: 'TEXT_MESSAGE_CONTENT',
    threadId,
    runId,
    messageId,
    delta,
    timestamp: getTimestamp(),
  };
}

/**
 * TEXT_MESSAGE_END 이벤트 생성
 */
export function createTextMessageEnd(
  threadId: string,
  runId: string,
  messageId: string
): TextMessageEndEvent {
  return {
    type: 'TEXT_MESSAGE_END',
    threadId,
    runId,
    messageId,
    timestamp: getTimestamp(),
  };
}

// --- Tool Call Event Helpers ---

/**
 * TOOL_CALL_START 이벤트 생성
 */
export function createToolCallStart(
  threadId: string,
  runId: string,
  toolCallId: string,
  toolCallName: string
): ToolCallStartEvent {
  return {
    type: 'TOOL_CALL_START',
    threadId,
    runId,
    toolCallId,
    toolCallName,
    timestamp: getTimestamp(),
  };
}

/**
 * TOOL_CALL_ARGS 이벤트 생성
 */
export function createToolCallArgs(
  threadId: string,
  runId: string,
  toolCallId: string,
  delta: string
): ToolCallArgsEvent {
  return {
    type: 'TOOL_CALL_ARGS',
    threadId,
    runId,
    toolCallId,
    delta,
    timestamp: getTimestamp(),
  };
}

/**
 * TOOL_CALL_END 이벤트 생성
 */
export function createToolCallEnd(
  threadId: string,
  runId: string,
  toolCallId: string
): ToolCallEndEvent {
  return {
    type: 'TOOL_CALL_END',
    threadId,
    runId,
    toolCallId,
    timestamp: getTimestamp(),
  };
}

/**
 * TOOL_CALL_RESULT 이벤트 생성
 */
export function createToolCallResult(
  threadId: string,
  runId: string,
  toolCallId: string,
  data: unknown,
  mimeType: string = 'application/json'
): ToolCallResultEvent {
  return {
    type: 'TOOL_CALL_RESULT',
    threadId,
    runId,
    toolCallId,
    content: { mimeType, data },
    timestamp: getTimestamp(),
  };
}

/**
 * TOOL_CALL_REQUEST 이벤트 생성
 */
export function createToolCallRequest(
  threadId: string,
  runId: string,
  toolCallId: string,
  toolName: string,
  args: Record<string, unknown>
): ToolCallRequestEvent {
  return {
    type: 'TOOL_CALL_REQUEST',
    threadId,
    runId,
    toolCallId,
    toolName,
    arguments: args,
    timestamp: getTimestamp(),
  };
}

// --- Type Guards ---

/**
 * Check if an event is a run event (RUN_STARTED | RUN_FINISHED | RUN_ERROR)
 */
export function isRunEvent(
  event: AGUIEvent
): event is RunStartedEvent | RunFinishedEvent | RunErrorEvent {
  return (
    event.type === 'RUN_STARTED' ||
    event.type === 'RUN_FINISHED' ||
    event.type === 'RUN_ERROR'
  );
}

/**
 * Check if an event is a text message event
 */
export function isTextMessageEvent(
  event: AGUIEvent
): event is TextMessageStartEvent | TextMessageContentEvent | TextMessageEndEvent {
  return (
    event.type === 'TEXT_MESSAGE_START' ||
    event.type === 'TEXT_MESSAGE_CONTENT' ||
    event.type === 'TEXT_MESSAGE_END'
  );
}

/**
 * Check if an event is a tool call event (excluding TOOL_CALL_REQUEST)
 */
export function isToolCallEvent(
  event: AGUIEvent
): event is ToolCallStartEvent | ToolCallArgsEvent | ToolCallEndEvent | ToolCallResultEvent {
  return (
    event.type === 'TOOL_CALL_START' ||
    event.type === 'TOOL_CALL_ARGS' ||
    event.type === 'TOOL_CALL_END' ||
    event.type === 'TOOL_CALL_RESULT'
  );
}

/**
 * Check if an event is a frontend tool request
 */
export function isToolCallRequestEvent(
  event: AGUIEvent
): event is ToolCallRequestEvent {
  return event.type === 'TOOL_CALL_REQUEST';
}
