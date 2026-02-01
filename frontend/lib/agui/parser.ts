/**
 * AG-UI Stream Parser
 *
 * Parses Server-Sent Events (SSE) containing AG-UI events and extracts A2UI messages
 * from TOOL_CALL_RESULT events for rendering.
 */

import {
  AGUIEvent,
  AGUIState,
  AGUIStatus,
  A2UI_MIME_TYPE,
  A2UI_TOOL_NAME,
  ToolCallResultEvent,
  ToolCallRequestEvent,
} from './types';
import {
  Surface,
  A2UIMessage,
  handleA2UIMessage,
  createEmptySurface,
} from '@/components/a2ui';

// --- Parse Result Types ---

/**
 * Result yielded by the AG-UI parser for each event
 */
export interface AGUIParseResult {
  /** Current surface state after processing the event */
  surface: Surface;
  /** Current run status */
  status: AGUIStatus;
  /** Thread ID from the run */
  threadId: string;
  /** Run ID */
  runId: string;
  /** The raw event that was processed */
  event: AGUIEvent;
  /** Accumulated text content (for TEXT_MESSAGE events) */
  textContent?: string;
  /** Pending frontend tool request (for TOOL_CALL_REQUEST events) */
  toolRequest?: ToolCallRequestEvent;
}

/**
 * Options for the AG-UI parser
 */
export interface AGUIParserOptions {
  /** Initial surface ID (default: 'main') */
  surfaceId?: string;
  /** Callback when A2UI message is received */
  onA2UIMessage?: (message: A2UIMessage) => void;
  /** Callback when text delta is received */
  onTextDelta?: (delta: string, messageId: string) => void;
  /** Callback when tool request is received */
  onToolRequest?: (request: ToolCallRequestEvent) => void;
}

// --- SSE Parser ---

/**
 * Parse a single SSE line into an AG-UI event
 */
export function parseSSELine(line: string): AGUIEvent | null {
  if (!line.startsWith('data: ')) {
    return null;
  }

  const data = line.slice(6).trim();
  if (!data || data === '[DONE]') {
    return null;
  }

  try {
    return JSON.parse(data) as AGUIEvent;
  } catch {
    return null;
  }
}

/**
 * Parse SSE stream and yield AG-UI events
 */
async function* parseSSEToEvents(
  reader: ReadableStreamDefaultReader<Uint8Array>
): AsyncGenerator<AGUIEvent> {
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;

      // Handle both "data: {...}" and "event: xxx\ndata: {...}" formats
      if (trimmed.startsWith('data: ')) {
        const event = parseSSELine(trimmed);
        if (event) {
          yield event;
        }
      }
    }
  }

  // Process any remaining content in buffer
  if (buffer.trim()) {
    const event = parseSSELine(buffer.trim());
    if (event) {
      yield event;
    }
  }
}

// --- Main Parser ---

/**
 * Parse AG-UI SSE stream and extract A2UI messages
 *
 * This is the main parsing function that:
 * 1. Reads SSE events from the stream
 * 2. Processes AG-UI events
 * 3. Extracts A2UI messages from TOOL_CALL_RESULT events
 * 4. Updates surface state
 *
 * @example
 * ```ts
 * const response = await fetch('/api/chat/stream', { method: 'POST', body: ... });
 * const reader = response.body?.getReader();
 *
 * for await (const result of parseAGUIStream(reader)) {
 *   if (result.status === 'running') {
 *     setCurrentSurface(result.surface);
 *   } else if (result.status === 'completed') {
 *     addMessage({ role: 'assistant', surface: result.surface });
 *   }
 * }
 * ```
 */
export async function* parseAGUIStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  options: AGUIParserOptions = {}
): AsyncGenerator<AGUIParseResult> {
  const surfaceId = options.surfaceId || 'main';
  let surface = createEmptySurface(surfaceId);
  let threadId = '';
  let runId = '';
  let status: AGUIStatus = 'idle';
  let textContent = '';
  let currentMessageId = '';

  for await (const event of parseSSEToEvents(reader)) {
    switch (event.type) {
      case 'RUN_STARTED':
        threadId = event.threadId;
        runId = event.runId;
        status = 'running';
        surface = createEmptySurface(surfaceId);
        textContent = '';
        break;

      case 'RUN_FINISHED':
        status = 'completed';
        break;

      case 'RUN_ERROR':
        status = 'error';
        break;

      case 'TEXT_MESSAGE_START':
        currentMessageId = event.messageId;
        textContent = '';
        break;

      case 'TEXT_MESSAGE_CONTENT':
        textContent += event.delta;
        options.onTextDelta?.(event.delta, event.messageId);
        break;

      case 'TEXT_MESSAGE_END':
        currentMessageId = '';
        break;

      case 'TOOL_CALL_START':
        // Track that we're receiving a tool call
        // Could add state tracking for multiple concurrent calls
        break;

      case 'TOOL_CALL_ARGS':
        // Streamed arguments - could accumulate if needed
        break;

      case 'TOOL_CALL_END':
        // Tool call arguments complete
        break;

      case 'TOOL_CALL_RESULT':
        // Check if this is an A2UI message
        const resultEvent = event as ToolCallResultEvent;
        if (resultEvent.content?.mimeType === A2UI_MIME_TYPE) {
          const a2uiMessage = resultEvent.content.data as A2UIMessage;
          surface = handleA2UIMessage(a2uiMessage, surface);
          options.onA2UIMessage?.(a2uiMessage);
        }
        break;

      case 'TOOL_CALL_REQUEST':
        // Frontend tool request (e.g., user confirmation)
        const requestEvent = event as ToolCallRequestEvent;
        options.onToolRequest?.(requestEvent);
        yield {
          surface,
          status,
          threadId,
          runId,
          event,
          textContent,
          toolRequest: requestEvent,
        };
        continue; // Skip the default yield below
    }

    yield {
      surface,
      status,
      threadId,
      runId,
      event,
      textContent,
    };
  }
}

// --- Utility Functions ---

/**
 * Check if an AG-UI event contains A2UI data
 */
export function hasA2UIData(event: AGUIEvent): boolean {
  return (
    event.type === 'TOOL_CALL_RESULT' &&
    (event as ToolCallResultEvent).content?.mimeType === A2UI_MIME_TYPE
  );
}

/**
 * Legacy A2UI message format (for backward compatibility)
 */
interface LegacyA2UIMessage {
  type: 'surfaceUpdate' | 'dataModelUpdate' | 'beginRendering';
  surfaceId?: string;
  components?: Array<{ id: string; component: Record<string, any> }>;
  root?: string;
  catalogId?: string;
  modelId?: string;
  data?: Record<string, any>;
}

/**
 * Check if data is in legacy format
 */
function isLegacyFormat(data: unknown): data is LegacyA2UIMessage {
  return (
    typeof data === 'object' &&
    data !== null &&
    'type' in data &&
    (data as LegacyA2UIMessage).type !== undefined
  );
}

/**
 * Convert legacy format to v0.8 standard format
 */
function convertLegacyToStandard(legacy: LegacyA2UIMessage): A2UIMessage | null {
  switch (legacy.type) {
    case 'surfaceUpdate':
      return {
        surfaceUpdate: {
          surfaceId: legacy.surfaceId || 'main',
          components: (legacy.components || []).map((c) => ({
            id: c.id,
            component: c.component,
          })),
        },
      };
    case 'beginRendering':
      return {
        beginRendering: {
          surfaceId: legacy.surfaceId || 'main',
          root: legacy.root || '',
          catalogId: legacy.catalogId,
        },
      };
    case 'dataModelUpdate':
      // Legacy format used modelId and data, convert to v0.8 surfaceId and contents
      const contents = Object.entries(legacy.data || {}).map(([key, value]) => {
        if (typeof value === 'string') return { key, valueString: value };
        if (typeof value === 'number') return { key, valueNumber: value };
        if (typeof value === 'boolean') return { key, valueBoolean: value };
        if (Array.isArray(value)) return { key, valueList: value };
        if (typeof value === 'object') return { key, valueMap: value };
        return { key, valueString: String(value) };
      });
      return {
        dataModelUpdate: {
          surfaceId: legacy.modelId || legacy.surfaceId || 'main',
          contents,
        },
      };
    default:
      return null;
  }
}

/**
 * Extract A2UI message from a TOOL_CALL_RESULT event
 * Supports both v0.8 standard format and legacy format for backward compatibility
 */
export function extractA2UIMessage(event: AGUIEvent): A2UIMessage | null {
  if (!hasA2UIData(event)) {
    return null;
  }

  const data = (event as ToolCallResultEvent).content.data;

  // v0.8 standard format: { surfaceUpdate: {...} }, { beginRendering: {...} }, etc.
  if (typeof data === 'object' && data !== null) {
    if ('surfaceUpdate' in data) return data as A2UIMessage;
    if ('beginRendering' in data) return data as A2UIMessage;
    if ('dataModelUpdate' in data) return data as A2UIMessage;
    if ('deleteSurface' in data) return data as A2UIMessage;

    // Legacy format: { type: 'surfaceUpdate', ... }
    if (isLegacyFormat(data)) {
      return convertLegacyToStandard(data);
    }
  }

  return null;
}

/**
 * Simplified parser that only extracts the final surface
 * Useful when you don't need streaming updates
 */
export async function parseAGUIStreamToSurface(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  surfaceId: string = 'main'
): Promise<{ surface: Surface; threadId: string; runId: string; error?: string }> {
  let finalResult: AGUIParseResult | null = null;

  for await (const result of parseAGUIStream(reader, { surfaceId })) {
    finalResult = result;
  }

  if (!finalResult) {
    return {
      surface: createEmptySurface(surfaceId),
      threadId: '',
      runId: '',
      error: 'No events received',
    };
  }

  return {
    surface: finalResult.surface,
    threadId: finalResult.threadId,
    runId: finalResult.runId,
    error: finalResult.status === 'error' ? 'Run failed' : undefined,
  };
}
