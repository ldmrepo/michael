/**
 * AG-UI Protocol Module
 *
 * This module provides AG-UI (Agent-User Interface) protocol support for the frontend.
 * AG-UI is used to standardize agent-to-user communication, with A2UI messages transmitted
 * as TOOL_CALL_RESULT events.
 *
 * @example
 * ```ts
 * import { AGUIClient, parseAGUIStream, AGUIEvent, A2UI_MIME_TYPE } from '@/lib/agui';
 *
 * // Using the high-level client
 * const client = new AGUIClient({
 *   baseUrl: '/api',
 *   onSurfaceUpdate: (surface) => setSurface(surface),
 * });
 * await client.sendMessage('서울에서 부산 KTX');
 *
 * // Or using the low-level parser
 * for await (const result of parseAGUIStream(reader)) {
 *   console.log(result.surface, result.status);
 * }
 * ```
 */

// Types
export type {
  // Event types
  AGUIEventType,
  AGUIBaseEvent,
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
  ToolCallResultContent,
  ToolCallRequestEvent,
  AGUIEvent,

  // State types
  AGUIStatus,
  AGUIState,
} from './types';

// Constants
export { A2UI_MIME_TYPE, A2UI_TOOL_NAME } from './types';

// Type guards
export {
  isRunEvent,
  isTextMessageEvent,
  isToolCallEvent,
  isToolCallRequestEvent,
  isA2UIResult,
} from './types';

// Event creation helpers
export {
  generateId,
  getTimestamp,
  createRunStarted,
  createRunFinished,
  createRunError,
  createTextMessageStart,
  createTextMessageContent,
  createTextMessageEnd,
  createToolCallStart,
  createToolCallArgs,
  createToolCallEnd,
  createToolCallResult,
  createA2UIResult,
  createToolCallRequest,
  createToolResultMessage,
  createA2UIEventSequence,
  createCompleteA2UIRun,
} from './events';

export type { ToolResultMessage } from './events';

// Parser
export {
  parseSSELine,
  parseAGUIStream,
  parseAGUIStreamToSurface,
  hasA2UIData,
  extractA2UIMessage,
} from './parser';

export type { AGUIParseResult, AGUIParserOptions } from './parser';

// Client
export { AGUIClient, createClientConfig } from './client';

export type { AGUIClientOptions } from './client';
