import { describe, it, expect } from 'vitest';
import {
  formatSSEEvent,
  parseSSELine,
  parseSSEText,
  formatSSEStream,
  SSE_DONE,
  SSE_CONTENT_TYPE,
  SSE_HEADERS,
} from './sse.js';
import {
  createRunStarted,
  createRunFinished,
  createRunError,
  createTextMessageContent,
  AGUIEvent,
} from './events.js';

describe('SSE Utilities', () => {
  const threadId = 'thread_123';
  const runId = 'run_456';

  describe('formatSSEEvent', () => {
    it('should format event as SSE data line', () => {
      const event = createRunStarted(threadId, runId);
      const sse = formatSSEEvent(event);

      expect(sse).toMatch(/^data: \{.*\}\n\n$/);
      expect(sse).toContain('"type":"RUN_STARTED"');
      expect(sse).toContain(`"threadId":"${threadId}"`);
      expect(sse).toContain(`"runId":"${runId}"`);
    });

    it('should end with double newline', () => {
      const event = createRunFinished(threadId, runId);
      const sse = formatSSEEvent(event);

      expect(sse.endsWith('\n\n')).toBe(true);
    });

    it('should produce valid JSON in data field', () => {
      const event = createTextMessageContent(threadId, runId, 'msg_1', 'Hello');
      const sse = formatSSEEvent(event);

      const dataContent = sse.replace('data: ', '').trim();
      expect(() => JSON.parse(dataContent)).not.toThrow();
    });
  });

  describe('parseSSELine', () => {
    it('should parse valid SSE data line', () => {
      const event = createRunStarted(threadId, runId);
      const sse = `data: ${JSON.stringify(event)}`;

      const parsed = parseSSELine(sse);
      expect(parsed).not.toBeNull();
      expect(parsed?.type).toBe('RUN_STARTED');
      expect(parsed?.threadId).toBe(threadId);
      expect(parsed?.runId).toBe(runId);
    });

    it('should handle whitespace', () => {
      const event = createRunFinished(threadId, runId);
      const sse = `  data: ${JSON.stringify(event)}  `;

      const parsed = parseSSELine(sse);
      expect(parsed).not.toBeNull();
      expect(parsed?.type).toBe('RUN_FINISHED');
    });

    it('should return null for non-data lines', () => {
      expect(parseSSELine('event: message')).toBeNull();
      expect(parseSSELine('id: 123')).toBeNull();
      expect(parseSSELine('retry: 3000')).toBeNull();
      expect(parseSSELine('')).toBeNull();
      expect(parseSSELine('   ')).toBeNull();
    });

    it('should return null for [DONE] marker', () => {
      expect(parseSSELine('data: [DONE]')).toBeNull();
    });

    it('should return null for empty data', () => {
      expect(parseSSELine('data: ')).toBeNull();
      expect(parseSSELine('data:    ')).toBeNull();
    });

    it('should return null for invalid JSON', () => {
      expect(parseSSELine('data: not json')).toBeNull();
      expect(parseSSELine('data: {invalid}')).toBeNull();
    });
  });

  describe('parseSSEText', () => {
    it('should parse multiple events', () => {
      const event1 = createRunStarted(threadId, runId);
      const event2 = createRunFinished(threadId, runId);

      const text = [
        `data: ${JSON.stringify(event1)}`,
        '',
        `data: ${JSON.stringify(event2)}`,
        '',
      ].join('\n');

      const events = parseSSEText(text);
      expect(events.length).toBe(2);
      expect(events[0].type).toBe('RUN_STARTED');
      expect(events[1].type).toBe('RUN_FINISHED');
    });

    it('should skip invalid lines', () => {
      const event = createRunStarted(threadId, runId);

      const text = [
        'event: start',
        `data: ${JSON.stringify(event)}`,
        'id: 123',
        'data: invalid json',
        '',
      ].join('\n');

      const events = parseSSEText(text);
      expect(events.length).toBe(1);
      expect(events[0].type).toBe('RUN_STARTED');
    });

    it('should handle empty text', () => {
      expect(parseSSEText('')).toEqual([]);
      expect(parseSSEText('\n\n\n')).toEqual([]);
    });
  });

  describe('formatSSEStream', () => {
    it('should format multiple events', () => {
      const events: AGUIEvent[] = [
        createRunStarted(threadId, runId),
        createRunFinished(threadId, runId),
      ];

      const stream = formatSSEStream(events);

      expect(stream).toContain('RUN_STARTED');
      expect(stream).toContain('RUN_FINISHED');
      expect(stream.split('data: ').length - 1).toBe(2);
    });

    it('should handle empty array', () => {
      expect(formatSSEStream([])).toBe('');
    });
  });

  describe('roundtrip (format -> parse)', () => {
    it('should preserve event data through format/parse cycle', () => {
      const original = createRunError(threadId, runId, 'Test error', 'ERR_001');
      const formatted = formatSSEEvent(original);
      const parsed = parseSSELine(formatted.trim());

      expect(parsed).not.toBeNull();
      expect(parsed?.type).toBe(original.type);
      expect(parsed?.threadId).toBe(original.threadId);
      expect(parsed?.runId).toBe(original.runId);
      expect((parsed as any)?.message).toBe('Test error');
      expect((parsed as any)?.code).toBe('ERR_001');
    });

    it('should preserve all events through stream roundtrip', () => {
      const originals: AGUIEvent[] = [
        createRunStarted(threadId, runId),
        createTextMessageContent(threadId, runId, 'msg_1', 'Hello World'),
        createRunFinished(threadId, runId),
      ];

      const stream = formatSSEStream(originals);
      const parsed = parseSSEText(stream);

      expect(parsed.length).toBe(originals.length);

      for (let i = 0; i < originals.length; i++) {
        expect(parsed[i].type).toBe(originals[i].type);
        expect(parsed[i].threadId).toBe(originals[i].threadId);
        expect(parsed[i].runId).toBe(originals[i].runId);
      }
    });
  });

  describe('SSE Constants', () => {
    it('should have correct DONE marker', () => {
      expect(SSE_DONE).toBe('data: [DONE]\n\n');
    });

    it('should have correct Content-Type', () => {
      expect(SSE_CONTENT_TYPE).toBe('text/event-stream');
    });

    it('should have correct headers', () => {
      expect(SSE_HEADERS['Content-Type']).toBe('text/event-stream');
      expect(SSE_HEADERS['Cache-Control']).toBe('no-cache');
      expect(SSE_HEADERS.Connection).toBe('keep-alive');
    });
  });
});
