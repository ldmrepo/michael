/**
 * A2UI Integration Utilities
 *
 * Provides utilities for wrapping A2UI messages in AG-UI TOOL_CALL events.
 * This is the standard way to transmit A2UI messages over the AG-UI protocol.
 *
 * @see https://github.com/ag-ui-org/ag-ui
 */

import {
  AGUIEvent,
  generateId,
  createRunStarted,
  createRunFinished,
  createToolCallStart,
  createToolCallEnd,
  createToolCallResult,
} from './events.js';

// --- Constants ---

/**
 * MIME type for A2UI messages transmitted via AG-UI TOOL_CALL_RESULT
 */
export const A2UI_MIME_TYPE = 'application/json+a2ui';

/**
 * Tool name used for A2UI rendering in AG-UI protocol
 */
export const A2UI_TOOL_NAME = 'render_a2ui';

// --- A2UI Message Types ---

/**
 * A2UI message types
 */
export type A2UIMessageType = 'surfaceUpdate' | 'dataModelUpdate' | 'beginRendering';

/**
 * Base A2UI message structure
 */
export interface A2UIMessage {
  type: A2UIMessageType;
  [key: string]: unknown;
}

// --- Wrapping Functions ---

/**
 * Wrap A2UI messages in AG-UI TOOL_CALL events.
 *
 * This is the standard way to transmit A2UI messages over AG-UI:
 * 1. TOOL_CALL_START with tool name "render_a2ui"
 * 2. TOOL_CALL_RESULT for each A2UI message (with mimeType "application/json+a2ui")
 * 3. TOOL_CALL_END
 *
 * @param a2uiMessages - List of A2UI messages (surfaceUpdate, dataModelUpdate, beginRendering)
 * @param threadId - AG-UI thread ID
 * @param runId - AG-UI run ID
 * @returns List of AG-UI events
 *
 * @example
 * ```ts
 * const a2uiMessages = [
 *   { type: 'surfaceUpdate', surfaceId: 'main', components: [...] },
 *   { type: 'beginRendering', surfaceId: 'main' },
 * ];
 *
 * const events = wrapA2UIMessages(a2uiMessages, 'thread_1', 'run_1');
 * // => [TOOL_CALL_START, TOOL_CALL_RESULT, TOOL_CALL_RESULT, TOOL_CALL_END]
 * ```
 */
export function wrapA2UIMessages(
  a2uiMessages: A2UIMessage[],
  threadId: string,
  runId: string
): AGUIEvent[] {
  const toolCallId = generateId('a2ui');
  const events: AGUIEvent[] = [];

  // TOOL_CALL_START
  events.push(createToolCallStart(threadId, runId, toolCallId, A2UI_TOOL_NAME));

  // TOOL_CALL_RESULT for each A2UI message
  for (const msg of a2uiMessages) {
    events.push(createToolCallResult(threadId, runId, toolCallId, msg, A2UI_MIME_TYPE));
  }

  // TOOL_CALL_END
  events.push(createToolCallEnd(threadId, runId, toolCallId));

  return events;
}

/**
 * Create a complete AG-UI run with A2UI messages.
 *
 * Wraps the A2UI messages in a full AG-UI run sequence:
 * 1. RUN_STARTED
 * 2. TOOL_CALL sequence (via wrapA2UIMessages)
 * 3. RUN_FINISHED
 *
 * @param a2uiMessages - List of A2UI messages to transmit
 * @param threadId - Optional thread ID (generated if not provided)
 * @param runId - Optional run ID (generated if not provided)
 * @returns Complete list of AG-UI events for the run
 *
 * @example
 * ```ts
 * const a2uiMessages = [
 *   { type: 'surfaceUpdate', surfaceId: 'main', components: [...] },
 * ];
 *
 * const events = createCompleteA2UIRun(a2uiMessages);
 * // => [RUN_STARTED, TOOL_CALL_START, TOOL_CALL_RESULT, TOOL_CALL_END, RUN_FINISHED]
 * ```
 */
export function createCompleteA2UIRun(
  a2uiMessages: A2UIMessage[],
  threadId?: string,
  runId?: string
): AGUIEvent[] {
  const tid = threadId || generateId('thread');
  const rid = runId || generateId('run');

  const events: AGUIEvent[] = [];

  // RUN_STARTED
  events.push(createRunStarted(tid, rid));

  // A2UI TOOL_CALL sequence
  if (a2uiMessages.length > 0) {
    events.push(...wrapA2UIMessages(a2uiMessages, tid, rid));
  }

  // RUN_FINISHED
  events.push(createRunFinished(tid, rid));

  return events;
}

// --- Type Guards ---

/**
 * Check if a TOOL_CALL_RESULT contains A2UI data
 */
export function isA2UIResult(event: AGUIEvent): boolean {
  if (event.type !== 'TOOL_CALL_RESULT') {
    return false;
  }

  const resultEvent = event as { content?: { mimeType?: string } };
  return resultEvent.content?.mimeType === A2UI_MIME_TYPE;
}

/**
 * Extract A2UI message from a TOOL_CALL_RESULT event
 */
export function extractA2UIMessage(event: AGUIEvent): A2UIMessage | null {
  if (!isA2UIResult(event)) {
    return null;
  }

  const resultEvent = event as { content?: { data?: unknown } };
  return resultEvent.content?.data as A2UIMessage | null;
}
