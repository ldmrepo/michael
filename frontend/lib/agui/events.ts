/**
 * AG-UI Event Creation Helpers
 *
 * Utility functions for creating AG-UI events on the client side.
 * Primarily used for sending tool results back to the server.
 */

import {
  AGUIEvent,
  RunStartedEvent,
  RunFinishedEvent,
  RunErrorEvent,
  TextMessageStartEvent,
  TextMessageContentEvent,
  TextMessageEndEvent,
  ToolCallStartEvent,
  ToolCallArgsEvent,
  ToolCallEndEvent,
  ToolCallResultEvent,
  ToolCallRequestEvent,
  A2UI_MIME_TYPE,
  A2UI_TOOL_NAME,
} from './types';

/**
 * Generate a unique ID for events
 */
export function generateId(prefix: string = 'id'): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

/**
 * Get current timestamp in ISO format
 */
export function getTimestamp(): string {
  return new Date().toISOString();
}

// --- Run Events ---

export function createRunStarted(threadId: string, runId: string): RunStartedEvent {
  return {
    type: 'RUN_STARTED',
    threadId,
    runId,
    timestamp: getTimestamp(),
  };
}

export function createRunFinished(threadId: string, runId: string): RunFinishedEvent {
  return {
    type: 'RUN_FINISHED',
    threadId,
    runId,
    timestamp: getTimestamp(),
  };
}

export function createRunError(threadId: string, runId: string, message: string, code?: string): RunErrorEvent {
  return {
    type: 'RUN_ERROR',
    threadId,
    runId,
    message,
    code,
    timestamp: getTimestamp(),
  };
}

// --- Text Message Events ---

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
  };
}

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

// --- Tool Call Events ---

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
  };
}

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
    content: {
      mimeType,
      data,
    },
    timestamp: getTimestamp(),
  };
}

/**
 * Create a TOOL_CALL_RESULT event specifically for A2UI messages
 */
export function createA2UIResult(
  threadId: string,
  runId: string,
  toolCallId: string,
  a2uiMessage: unknown
): ToolCallResultEvent {
  return createToolCallResult(threadId, runId, toolCallId, a2uiMessage, A2UI_MIME_TYPE);
}

// --- Frontend Tool Request ---

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

// --- Tool Result (Client to Server) ---

/**
 * Tool result message sent from client to server
 */
export interface ToolResultMessage {
  threadId: string;
  toolCallId: string;
  result: unknown;
  error?: string;
}

/**
 * Create a tool result message to send back to server
 */
export function createToolResultMessage(
  threadId: string,
  toolCallId: string,
  result: unknown,
  error?: string
): ToolResultMessage {
  return {
    threadId,
    toolCallId,
    result,
    error,
  };
}

// --- Batch Event Creation for A2UI ---

/**
 * Create a complete sequence of AG-UI events for A2UI rendering
 * This wraps A2UI messages in the standard AG-UI TOOL_CALL pattern
 */
export function createA2UIEventSequence(
  threadId: string,
  runId: string,
  a2uiMessages: unknown[]
): AGUIEvent[] {
  const toolCallId = generateId('a2ui');
  const events: AGUIEvent[] = [];

  // Start the tool call
  events.push(createToolCallStart(threadId, runId, toolCallId, A2UI_TOOL_NAME));

  // Add each A2UI message as a result
  for (const msg of a2uiMessages) {
    events.push(createA2UIResult(threadId, runId, toolCallId, msg));
  }

  // End the tool call
  events.push(createToolCallEnd(threadId, runId, toolCallId));

  return events;
}

/**
 * Create a complete AG-UI run with A2UI messages
 */
export function createCompleteA2UIRun(
  a2uiMessages: unknown[],
  threadId?: string,
  runId?: string
): AGUIEvent[] {
  const tid = threadId || generateId('thread');
  const rid = runId || generateId('run');

  return [
    createRunStarted(tid, rid),
    ...createA2UIEventSequence(tid, rid, a2uiMessages),
    createRunFinished(tid, rid),
  ];
}
