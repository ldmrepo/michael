/**
 * AG-UI SSE (Server-Sent Events) Utilities
 *
 * Provides formatting and parsing utilities for AG-UI events over SSE.
 * Compatible with the a2ui-demo reference architecture.
 */

import { AGUIEvent } from './events.js';

/**
 * Format an AG-UI event as an SSE data line
 *
 * @example
 * ```ts
 * const event = createRunStarted('thread_1', 'run_1');
 * const sse = formatSSEEvent(event);
 * // => "data: {"type":"RUN_STARTED",...}\n\n"
 * ```
 */
export function formatSSEEvent(event: AGUIEvent): string {
  return `data: ${JSON.stringify(event)}\n\n`;
}

/**
 * Parse a single SSE line into an AG-UI event
 *
 * @param line - SSE line (e.g., "data: {...}")
 * @returns Parsed event or null if invalid
 *
 * @example
 * ```ts
 * const event = parseSSELine('data: {"type":"RUN_STARTED",...}');
 * // => { type: 'RUN_STARTED', ... }
 *
 * const invalid = parseSSELine('event: ping');
 * // => null
 * ```
 */
export function parseSSELine(line: string): AGUIEvent | null {
  const trimmed = line.trim();

  // Must start with "data: "
  if (!trimmed.startsWith('data: ')) {
    return null;
  }

  const data = trimmed.slice(6).trim();

  // Handle [DONE] marker
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
 * Parse multiple SSE lines and yield AG-UI events
 *
 * @param text - Multi-line SSE text
 * @returns Array of parsed events
 *
 * @example
 * ```ts
 * const text = `data: {"type":"RUN_STARTED",...}
 *
 * data: {"type":"RUN_FINISHED",...}
 *
 * `;
 * const events = parseSSEText(text);
 * // => [{ type: 'RUN_STARTED', ... }, { type: 'RUN_FINISHED', ... }]
 * ```
 */
export function parseSSEText(text: string): AGUIEvent[] {
  const events: AGUIEvent[] = [];
  const lines = text.split('\n');

  for (const line of lines) {
    const event = parseSSELine(line);
    if (event) {
      events.push(event);
    }
  }

  return events;
}

/**
 * Create an SSE stream from an array of AG-UI events
 *
 * @param events - Array of AG-UI events
 * @returns Formatted SSE string
 *
 * @example
 * ```ts
 * const events = [
 *   createRunStarted('t', 'r'),
 *   createRunFinished('t', 'r'),
 * ];
 * const stream = formatSSEStream(events);
 * // => "data: {...}\n\ndata: {...}\n\n"
 * ```
 */
export function formatSSEStream(events: AGUIEvent[]): string {
  return events.map(formatSSEEvent).join('');
}

/**
 * SSE Done marker
 */
export const SSE_DONE = 'data: [DONE]\n\n';

/**
 * Content-Type header for SSE
 */
export const SSE_CONTENT_TYPE = 'text/event-stream';

/**
 * Headers for SSE response
 */
export const SSE_HEADERS = {
  'Content-Type': SSE_CONTENT_TYPE,
  'Cache-Control': 'no-cache',
  Connection: 'keep-alive',
} as const;
