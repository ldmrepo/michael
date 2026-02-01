/**
 * A2UI Integration Utilities (v0.8 Standard)
 *
 * Provides utilities for wrapping A2UI messages in AG-UI TOOL_CALL events.
 * This is the standard way to transmit A2UI messages over the AG-UI protocol.
 *
 * @see https://a2ui.org/specification/v0.8-a2ui/
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

// Re-export types from a2ui/types.ts
export type {
  BoundValue,
  ComponentDefinition,
  A2UIComponentType,
  SurfaceUpdate,
  BeginRendering,
  DataModelUpdate,
  DeleteSurface,
  DataModelContent,
  DataModelValue,
  A2UIMessage,
} from '../a2ui/types.js';

export {
  literal,
  pathRef,
  resolveBoundValue,
  isSurfaceUpdate,
  isBeginRendering,
  isDataModelUpdate,
  isDeleteSurface,
} from '../a2ui/types.js';

import type {
  ComponentDefinition,
  DataModelContent,
} from '../a2ui/types.js';

// --- Constants ---

/**
 * MIME type for A2UI messages transmitted via AG-UI TOOL_CALL_RESULT
 */
export const A2UI_MIME_TYPE = 'application/json+a2ui';

/**
 * Tool name used for A2UI rendering in AG-UI protocol
 */
export const A2UI_TOOL_NAME = 'render_a2ui';

// --- A2UI Message Types (v0.8 Standard) ---

/**
 * SurfaceUpdate message (v0.8 standard)
 */
export interface SurfaceUpdateMessage {
  surfaceUpdate: {
    surfaceId: string;
    components: ComponentDefinition[];
  };
}

/**
 * BeginRendering message (v0.8 standard)
 */
export interface BeginRenderingMessage {
  beginRendering: {
    surfaceId: string;
    root?: string;
    catalogId?: string;
  };
}

/**
 * DataModelUpdate message (v0.8 standard)
 */
export interface DataModelUpdateMessage {
  dataModelUpdate: {
    surfaceId: string;
    contents: DataModelContent[];
  };
}

/**
 * DeleteSurface message (v0.8 standard)
 */
export interface DeleteSurfaceMessage {
  deleteSurface: {
    surfaceId: string;
  };
}

/**
 * Union type for AG-UI transmission
 */
export type A2UIMessagePayload =
  | SurfaceUpdateMessage
  | BeginRenderingMessage
  | DataModelUpdateMessage
  | DeleteSurfaceMessage;

// --- Wrapping Functions ---

/**
 * Wrap A2UI messages in AG-UI TOOL_CALL events.
 *
 * This is the standard way to transmit A2UI messages over AG-UI:
 * 1. TOOL_CALL_START with tool name "render_a2ui"
 * 2. TOOL_CALL_RESULT for each A2UI message (with mimeType "application/json+a2ui")
 * 3. TOOL_CALL_END
 *
 * @param a2uiMessages - List of A2UI messages (surfaceUpdate, dataModelUpdate, beginRendering, deleteSurface)
 * @param threadId - AG-UI thread ID
 * @param runId - AG-UI run ID
 * @returns List of AG-UI events
 *
 * @example
 * ```ts
 * const a2uiMessages = [
 *   { surfaceUpdate: { surfaceId: 'main', components: [...] } },
 *   { beginRendering: { surfaceId: 'main', root: 'text_123' } },
 * ];
 *
 * const events = wrapA2UIMessages(a2uiMessages, 'thread_1', 'run_1');
 * // => [TOOL_CALL_START, TOOL_CALL_RESULT, TOOL_CALL_RESULT, TOOL_CALL_END]
 * ```
 */
export function wrapA2UIMessages(
  a2uiMessages: A2UIMessagePayload[],
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
 *   { surfaceUpdate: { surfaceId: 'main', components: [...] } },
 * ];
 *
 * const events = createCompleteA2UIRun(a2uiMessages);
 * // => [RUN_STARTED, TOOL_CALL_START, TOOL_CALL_RESULT, TOOL_CALL_END, RUN_FINISHED]
 * ```
 */
export function createCompleteA2UIRun(
  a2uiMessages: A2UIMessagePayload[],
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
export function extractA2UIMessage(event: AGUIEvent): A2UIMessagePayload | null {
  if (!isA2UIResult(event)) {
    return null;
  }

  const resultEvent = event as { content?: { data?: unknown } };
  return resultEvent.content?.data as A2UIMessagePayload | null;
}

// --- A2UI Message Creation Helpers (v0.8 Standard) ---

/**
 * Create A2UI Text component from plain text
 *
 * @param text - Text content to display
 * @param id - Component ID (default: generated)
 * @returns ComponentDefinition with Text component
 */
export function createTextComponent(text: string, id?: string): ComponentDefinition {
  return {
    id: id || generateId('text'),
    component: {
      Text: {
        text: { literalString: text },
      },
    },
  };
}

/**
 * Create A2UI SurfaceUpdate message from components (v0.8 standard)
 *
 * @param components - List of component definitions
 * @param surfaceId - Surface ID (default: 'main')
 * @returns SurfaceUpdateMessage
 */
export function createSurfaceUpdate(
  components: ComponentDefinition[],
  surfaceId: string = 'main'
): SurfaceUpdateMessage {
  return {
    surfaceUpdate: {
      surfaceId,
      components,
    },
  };
}

/**
 * Create A2UI BeginRendering message (v0.8 standard)
 *
 * @param surfaceId - Surface ID (default: 'main')
 * @param root - Root component ID (optional)
 * @param catalogId - Catalog ID (optional)
 * @returns BeginRenderingMessage
 */
export function createBeginRendering(
  surfaceId: string = 'main',
  root?: string,
  catalogId?: string
): BeginRenderingMessage {
  return {
    beginRendering: {
      surfaceId,
      ...(root && { root }),
      ...(catalogId && { catalogId }),
    },
  };
}

/**
 * Create A2UI DataModelUpdate message (v0.8 standard)
 *
 * @param surfaceId - Surface ID
 * @param data - Data to convert to contents
 * @returns DataModelUpdateMessage
 */
export function createDataModelUpdate(
  surfaceId: string,
  data: Record<string, unknown>
): DataModelUpdateMessage {
  return {
    dataModelUpdate: {
      surfaceId,
      contents: convertToDataModelContents(data),
    },
  };
}

/**
 * Convert a plain object to DataModelContent array
 */
function convertToDataModelContents(
  data: Record<string, unknown>
): DataModelContent[] {
  return Object.entries(data).map(([key, value]) => convertToDataModelContent(key, value));
}

/**
 * Convert a single key-value pair to DataModelContent
 */
function convertToDataModelContent(key: string, value: unknown): DataModelContent {
  if (typeof value === 'string') {
    return { key, valueString: value };
  }
  if (typeof value === 'number') {
    return { key, valueNumber: value };
  }
  if (typeof value === 'boolean') {
    return { key, valueBoolean: value };
  }
  if (Array.isArray(value)) {
    return {
      key,
      valueList: value.map((item) => convertToDataModelValue(item)),
    };
  }
  if (typeof value === 'object' && value !== null) {
    return {
      key,
      valueMap: convertToDataModelContents(value as Record<string, unknown>),
    };
  }
  // Fallback: convert to string
  return { key, valueString: String(value) };
}

/**
 * Convert a value to DataModelValue (for lists)
 */
function convertToDataModelValue(value: unknown): { valueString: string } | { valueNumber: number } | { valueBoolean: boolean } | { valueMap: DataModelContent[] } | { valueList: ReturnType<typeof convertToDataModelValue>[] } {
  if (typeof value === 'string') {
    return { valueString: value };
  }
  if (typeof value === 'number') {
    return { valueNumber: value };
  }
  if (typeof value === 'boolean') {
    return { valueBoolean: value };
  }
  if (Array.isArray(value)) {
    return { valueList: value.map(convertToDataModelValue) };
  }
  if (typeof value === 'object' && value !== null) {
    return { valueMap: convertToDataModelContents(value as Record<string, unknown>) };
  }
  return { valueString: String(value) };
}

/**
 * Create A2UI DeleteSurface message (v0.8 standard)
 *
 * @param surfaceId - Surface ID to delete
 * @returns DeleteSurfaceMessage
 */
export function createDeleteSurface(surfaceId: string): DeleteSurfaceMessage {
  return {
    deleteSurface: {
      surfaceId,
    },
  };
}

/**
 * Create A2UI messages from plain text
 *
 * This is the standard way to render plain text responses in A2UI:
 * 1. SurfaceUpdate with Text component
 * 2. BeginRendering to signal rendering start
 *
 * @param text - Plain text to convert
 * @param surfaceId - Surface ID (default: 'main')
 * @returns Array of A2UI messages (v0.8 standard format)
 *
 * @example
 * ```ts
 * const messages = createTextA2UIMessages('Hello, world!');
 * // => [
 * //   { surfaceUpdate: { surfaceId: 'main', components: [{ id: 'text_...', component: { Text: { text: { literalString: 'Hello, world!' } } } }] } },
 * //   { beginRendering: { surfaceId: 'main', root: 'text_...' } }
 * // ]
 * ```
 */
export function createTextA2UIMessages(
  text: string,
  surfaceId: string = 'main'
): A2UIMessagePayload[] {
  const textComponent = createTextComponent(text);

  return [
    createSurfaceUpdate([textComponent], surfaceId),
    createBeginRendering(surfaceId, textComponent.id),
  ];
}

// --- Legacy Format Support ---

/**
 * Legacy A2UI message format (for backward compatibility)
 * @deprecated Use v0.8 standard format instead
 */
export interface LegacyA2UIMessage {
  type: 'surfaceUpdate' | 'dataModelUpdate' | 'beginRendering';
  [key: string]: unknown;
}

/**
 * Convert legacy format to v0.8 standard format
 * @deprecated Use v0.8 standard format directly
 */
export function convertLegacyToStandard(legacy: LegacyA2UIMessage): A2UIMessagePayload | null {
  switch (legacy.type) {
    case 'surfaceUpdate':
      return {
        surfaceUpdate: {
          surfaceId: legacy.surfaceId as string,
          components: legacy.components as ComponentDefinition[],
        },
      };
    case 'beginRendering':
      return {
        beginRendering: {
          surfaceId: legacy.surfaceId as string,
          root: legacy.root as string | undefined,
          catalogId: legacy.catalogId as string | undefined,
        },
      };
    case 'dataModelUpdate':
      // Legacy format used modelId and data, convert to v0.8 surfaceId and contents
      return {
        dataModelUpdate: {
          surfaceId: (legacy.modelId || legacy.surfaceId) as string,
          contents: convertToDataModelContents((legacy.data || {}) as Record<string, unknown>),
        },
      };
    default:
      return null;
  }
}
