/**
 * AG-UI Stream Generator
 *
 * AsyncGenerator-based stream utilities for AG-UI events.
 * Ensures proper event sequencing: RUN_STARTED → (TEXT_MESSAGE | TOOL_CALL) → RUN_FINISHED
 *
 * @see https://github.com/ag-ui-org/ag-ui
 */

import {
  AGUIEvent,
  generateId,
  generateMessageId,
  createRunStarted,
  createRunFinished,
  createRunError,
  createTextMessageStart,
  createTextMessageContent,
  createTextMessageEnd,
} from './events.js';
import { wrapA2UIMessages, A2UIMessage } from './a2ui.js';

// --- Stream Configuration ---

/**
 * Configuration for text streaming
 */
export interface TextStreamConfig {
  /** Chunk size for streaming (default: 1 for character-by-character) */
  chunkSize?: number;
  /** Delay between chunks in ms (default: 0) */
  delayMs?: number;
  /** Message role (default: 'assistant') */
  role?: 'user' | 'assistant' | 'system';
}

/**
 * Configuration for AG-UI run stream
 */
export interface RunStreamConfig {
  /** Thread ID (generated if not provided) */
  threadId?: string;
  /** Run ID (generated if not provided) */
  runId?: string;
  /** Text streaming config */
  textConfig?: TextStreamConfig;
}

// --- Stream Context ---

/**
 * Context object for managing stream state
 */
export interface StreamContext {
  threadId: string;
  runId: string;
  messageId: string;
  isRunning: boolean;
  hasError: boolean;
}

/**
 * Create a new stream context
 */
export function createStreamContext(config?: RunStreamConfig): StreamContext {
  return {
    threadId: config?.threadId || generateId('thread'),
    runId: config?.runId || generateId('run'),
    messageId: generateMessageId(),
    isRunning: false,
    hasError: false,
  };
}

// --- Text Streaming ---

/**
 * Stream text as TEXT_MESSAGE events
 *
 * Yields: TEXT_MESSAGE_START → TEXT_MESSAGE_CONTENT* → TEXT_MESSAGE_END
 *
 * @param text - Full text to stream
 * @param threadId - Thread ID
 * @param runId - Run ID
 * @param config - Streaming configuration
 *
 * @example
 * ```ts
 * const events = streamText('Hello World', 'thread_1', 'run_1');
 * for await (const event of events) {
 *   console.log(event.type, event);
 * }
 * // TEXT_MESSAGE_START
 * // TEXT_MESSAGE_CONTENT (delta: 'H')
 * // TEXT_MESSAGE_CONTENT (delta: 'e')
 * // ... etc
 * // TEXT_MESSAGE_END
 * ```
 */
export async function* streamText(
  text: string,
  threadId: string,
  runId: string,
  config?: TextStreamConfig
): AsyncGenerator<AGUIEvent, void, undefined> {
  const chunkSize = config?.chunkSize ?? 1;
  const delayMs = config?.delayMs ?? 0;
  const role = config?.role ?? 'assistant';
  const messageId = generateMessageId();

  // TEXT_MESSAGE_START
  yield createTextMessageStart(threadId, runId, messageId, role);

  // TEXT_MESSAGE_CONTENT for each chunk
  for (let i = 0; i < text.length; i += chunkSize) {
    const delta = text.slice(i, i + chunkSize);
    yield createTextMessageContent(threadId, runId, messageId, delta);

    if (delayMs > 0) {
      await delay(delayMs);
    }
  }

  // TEXT_MESSAGE_END
  yield createTextMessageEnd(threadId, runId, messageId);
}

/**
 * Stream text as a single content event (no chunking)
 *
 * Yields: TEXT_MESSAGE_START → TEXT_MESSAGE_CONTENT → TEXT_MESSAGE_END
 */
export async function* streamTextWhole(
  text: string,
  threadId: string,
  runId: string,
  role: 'user' | 'assistant' | 'system' = 'assistant'
): AsyncGenerator<AGUIEvent, void, undefined> {
  const messageId = generateMessageId();

  yield createTextMessageStart(threadId, runId, messageId, role);
  yield createTextMessageContent(threadId, runId, messageId, text);
  yield createTextMessageEnd(threadId, runId, messageId);
}

// --- Complete Run Streams ---

/**
 * Create a complete AG-UI run stream for text response
 *
 * Yields: RUN_STARTED → TEXT_MESSAGE_START → TEXT_MESSAGE_CONTENT* → TEXT_MESSAGE_END → RUN_FINISHED
 *
 * @param text - Text to stream
 * @param config - Run configuration
 *
 * @example
 * ```ts
 * const events = createTextRunStream('Hello!', { chunkSize: 5 });
 * for await (const event of events) {
 *   console.log(event.type);
 * }
 * ```
 */
export async function* createTextRunStream(
  text: string,
  config?: RunStreamConfig
): AsyncGenerator<AGUIEvent, void, undefined> {
  const ctx = createStreamContext(config);

  try {
    // RUN_STARTED
    yield createRunStarted(ctx.threadId, ctx.runId);
    ctx.isRunning = true;

    // Stream text
    yield* streamText(text, ctx.threadId, ctx.runId, config?.textConfig);

    // RUN_FINISHED
    yield createRunFinished(ctx.threadId, ctx.runId);
    ctx.isRunning = false;
  } catch (error) {
    ctx.hasError = true;
    const message = error instanceof Error ? error.message : String(error);
    yield createRunError(ctx.threadId, ctx.runId, message, 'STREAM_ERROR');
  }
}

/**
 * Create a complete AG-UI run stream for A2UI messages
 *
 * Yields: RUN_STARTED → TOOL_CALL_START → TOOL_CALL_RESULT* → TOOL_CALL_END → RUN_FINISHED
 *
 * @param a2uiMessages - A2UI messages to wrap
 * @param config - Run configuration
 *
 * @example
 * ```ts
 * const events = createA2UIRunStream([
 *   { type: 'surfaceUpdate', surfaceId: 'main', components: [] }
 * ]);
 * for await (const event of events) {
 *   console.log(event.type);
 * }
 * ```
 */
export async function* createA2UIRunStream(
  a2uiMessages: A2UIMessage[],
  config?: RunStreamConfig
): AsyncGenerator<AGUIEvent, void, undefined> {
  const ctx = createStreamContext(config);

  try {
    // RUN_STARTED
    yield createRunStarted(ctx.threadId, ctx.runId);
    ctx.isRunning = true;

    // Wrap A2UI messages in TOOL_CALL events
    if (a2uiMessages.length > 0) {
      const toolEvents = wrapA2UIMessages(a2uiMessages, ctx.threadId, ctx.runId);
      for (const event of toolEvents) {
        yield event;
      }
    }

    // RUN_FINISHED
    yield createRunFinished(ctx.threadId, ctx.runId);
    ctx.isRunning = false;
  } catch (error) {
    ctx.hasError = true;
    const message = error instanceof Error ? error.message : String(error);
    yield createRunError(ctx.threadId, ctx.runId, message, 'STREAM_ERROR');
  }
}

/**
 * Create a combined run stream with both text and A2UI messages
 *
 * Yields: RUN_STARTED → TEXT_MESSAGE* → TOOL_CALL* → RUN_FINISHED
 *
 * @param text - Optional text to stream first
 * @param a2uiMessages - Optional A2UI messages to send after text
 * @param config - Run configuration
 */
export async function* createCombinedRunStream(
  text?: string,
  a2uiMessages?: A2UIMessage[],
  config?: RunStreamConfig
): AsyncGenerator<AGUIEvent, void, undefined> {
  const ctx = createStreamContext(config);

  try {
    // RUN_STARTED
    yield createRunStarted(ctx.threadId, ctx.runId);
    ctx.isRunning = true;

    // Stream text if provided
    if (text) {
      yield* streamText(text, ctx.threadId, ctx.runId, config?.textConfig);
    }

    // Send A2UI messages if provided
    if (a2uiMessages && a2uiMessages.length > 0) {
      const toolEvents = wrapA2UIMessages(a2uiMessages, ctx.threadId, ctx.runId);
      for (const event of toolEvents) {
        yield event;
      }
    }

    // RUN_FINISHED
    yield createRunFinished(ctx.threadId, ctx.runId);
    ctx.isRunning = false;
  } catch (error) {
    ctx.hasError = true;
    const message = error instanceof Error ? error.message : String(error);
    yield createRunError(ctx.threadId, ctx.runId, message, 'STREAM_ERROR');
  }
}

// --- Error Handling ---

/**
 * Create an error run stream
 *
 * Yields: RUN_STARTED → RUN_ERROR
 *
 * @param error - Error to report
 * @param code - Error code
 * @param config - Run configuration
 */
export async function* createErrorRunStream(
  error: Error | string,
  code: string = 'ERROR',
  config?: RunStreamConfig
): AsyncGenerator<AGUIEvent, void, undefined> {
  const ctx = createStreamContext(config);
  const message = error instanceof Error ? error.message : error;

  yield createRunStarted(ctx.threadId, ctx.runId);
  yield createRunError(ctx.threadId, ctx.runId, message, code);
}

// --- Stream Utilities ---

/**
 * Collect all events from a stream into an array
 *
 * @param stream - AsyncGenerator stream
 * @returns Array of all events
 *
 * @example
 * ```ts
 * const events = await collectStream(createTextRunStream('Hello'));
 * console.log(events.length); // 5 (START, MSG_START, MSG_CONTENT, MSG_END, FINISH)
 * ```
 */
export async function collectStream(
  stream: AsyncGenerator<AGUIEvent, void, undefined>
): Promise<AGUIEvent[]> {
  const events: AGUIEvent[] = [];
  for await (const event of stream) {
    events.push(event);
  }
  return events;
}

/**
 * Pipe a stream to a callback function
 *
 * @param stream - AsyncGenerator stream
 * @param callback - Function to call for each event
 *
 * @example
 * ```ts
 * await pipeStream(
 *   createTextRunStream('Hello'),
 *   (event) => console.log(event.type)
 * );
 * ```
 */
export async function pipeStream(
  stream: AsyncGenerator<AGUIEvent, void, undefined>,
  callback: (event: AGUIEvent) => void | Promise<void>
): Promise<void> {
  for await (const event of stream) {
    await callback(event);
  }
}

/**
 * Create a stream that wraps another stream with error handling
 *
 * @param stream - Source stream
 * @param threadId - Thread ID for error events
 * @param runId - Run ID for error events
 */
export async function* withErrorHandling(
  stream: AsyncGenerator<AGUIEvent, void, undefined>,
  threadId: string,
  runId: string
): AsyncGenerator<AGUIEvent, void, undefined> {
  try {
    for await (const event of stream) {
      yield event;
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    yield createRunError(threadId, runId, message, 'STREAM_ERROR');
  }
}

// --- Helper Functions ---

/**
 * Delay utility for throttled streaming
 */
function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Extract full text from a stream of events
 *
 * @param events - Array of AG-UI events
 * @returns Concatenated text from TEXT_MESSAGE_CONTENT events
 */
export function extractTextFromEvents(events: AGUIEvent[]): string {
  return events
    .filter((e) => e.type === 'TEXT_MESSAGE_CONTENT')
    .map((e) => (e as { delta: string }).delta)
    .join('');
}

/**
 * Check if a stream completed successfully (has RUN_FINISHED, no RUN_ERROR)
 */
export function isStreamSuccessful(events: AGUIEvent[]): boolean {
  const hasFinished = events.some((e) => e.type === 'RUN_FINISHED');
  const hasError = events.some((e) => e.type === 'RUN_ERROR');
  return hasFinished && !hasError;
}

/**
 * Check if a stream has an error
 */
export function isStreamError(events: AGUIEvent[]): boolean {
  return events.some((e) => e.type === 'RUN_ERROR');
}

/**
 * Get error message from stream events
 */
export function getStreamError(events: AGUIEvent[]): string | null {
  const errorEvent = events.find((e) => e.type === 'RUN_ERROR');
  if (errorEvent && 'message' in errorEvent) {
    return (errorEvent as { message: string }).message;
  }
  return null;
}
