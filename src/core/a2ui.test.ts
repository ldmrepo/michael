import { describe, it, expect } from 'vitest';
import {
  A2UI_MIME_TYPE,
  A2UI_TOOL_NAME,
  A2UIMessage,
  wrapA2UIMessages,
  createCompleteA2UIRun,
  isA2UIResult,
  extractA2UIMessage,
} from './a2ui.js';
import {
  createToolCallResult,
  createRunStarted,
  ToolCallResultEvent,
} from './events.js';

describe('A2UI Utilities', () => {
  describe('Constants', () => {
    it('should have correct MIME type', () => {
      expect(A2UI_MIME_TYPE).toBe('application/json+a2ui');
    });

    it('should have correct tool name', () => {
      expect(A2UI_TOOL_NAME).toBe('render_a2ui');
    });
  });

  describe('wrapA2UIMessages', () => {
    const threadId = 'thread_123';
    const runId = 'run_456';

    it('should wrap single A2UI message', () => {
      const a2uiMessage: A2UIMessage = {
        type: 'surfaceUpdate',
        surfaceId: 'main',
        components: [],
      };

      const events = wrapA2UIMessages([a2uiMessage], threadId, runId);

      expect(events.length).toBe(3);
      expect(events[0].type).toBe('TOOL_CALL_START');
      expect(events[1].type).toBe('TOOL_CALL_RESULT');
      expect(events[2].type).toBe('TOOL_CALL_END');
    });

    it('should wrap multiple A2UI messages', () => {
      const messages: A2UIMessage[] = [
        { type: 'surfaceUpdate', surfaceId: 'main', components: [] },
        { type: 'dataModelUpdate', modelId: 'data', data: {} },
        { type: 'beginRendering', surfaceId: 'main' },
      ];

      const events = wrapA2UIMessages(messages, threadId, runId);

      expect(events.length).toBe(5); // START + 3 RESULTS + END
      expect(events[0].type).toBe('TOOL_CALL_START');
      expect(events[1].type).toBe('TOOL_CALL_RESULT');
      expect(events[2].type).toBe('TOOL_CALL_RESULT');
      expect(events[3].type).toBe('TOOL_CALL_RESULT');
      expect(events[4].type).toBe('TOOL_CALL_END');
    });

    it('should use A2UI tool name', () => {
      const events = wrapA2UIMessages(
        [{ type: 'surfaceUpdate' }],
        threadId,
        runId
      );

      const startEvent = events[0] as any;
      expect(startEvent.toolCallName).toBe(A2UI_TOOL_NAME);
    });

    it('should use A2UI MIME type', () => {
      const events = wrapA2UIMessages(
        [{ type: 'surfaceUpdate' }],
        threadId,
        runId
      );

      const resultEvent = events[1] as ToolCallResultEvent;
      expect(resultEvent.content.mimeType).toBe(A2UI_MIME_TYPE);
    });

    it('should preserve A2UI message data', () => {
      const message: A2UIMessage = {
        type: 'surfaceUpdate',
        surfaceId: 'main',
        components: [{ type: 'Text', content: 'Hello' }],
      };

      const events = wrapA2UIMessages([message], threadId, runId);

      const resultEvent = events[1] as ToolCallResultEvent;
      expect(resultEvent.content.data).toEqual(message);
    });

    it('should use same toolCallId for all events', () => {
      const events = wrapA2UIMessages(
        [{ type: 'surfaceUpdate' }, { type: 'beginRendering' }],
        threadId,
        runId
      );

      const toolCallIds = events.map((e: any) => e.toolCallId);
      const uniqueIds = new Set(toolCallIds);
      expect(uniqueIds.size).toBe(1);
    });

    it('should handle empty message array', () => {
      const events = wrapA2UIMessages([], threadId, runId);

      expect(events.length).toBe(2); // START + END only
      expect(events[0].type).toBe('TOOL_CALL_START');
      expect(events[1].type).toBe('TOOL_CALL_END');
    });
  });

  describe('createCompleteA2UIRun', () => {
    it('should create complete run with A2UI messages', () => {
      const messages: A2UIMessage[] = [
        { type: 'surfaceUpdate', surfaceId: 'main' },
      ];

      const events = createCompleteA2UIRun(messages);

      expect(events[0].type).toBe('RUN_STARTED');
      expect(events[events.length - 1].type).toBe('RUN_FINISHED');
    });

    it('should include TOOL_CALL sequence', () => {
      const messages: A2UIMessage[] = [
        { type: 'surfaceUpdate' },
        { type: 'beginRendering' },
      ];

      const events = createCompleteA2UIRun(messages);

      // RUN_STARTED + TOOL_CALL_START + 2 RESULTS + TOOL_CALL_END + RUN_FINISHED
      expect(events.length).toBe(6);

      const types = events.map((e) => e.type);
      expect(types).toEqual([
        'RUN_STARTED',
        'TOOL_CALL_START',
        'TOOL_CALL_RESULT',
        'TOOL_CALL_RESULT',
        'TOOL_CALL_END',
        'RUN_FINISHED',
      ]);
    });

    it('should use provided threadId and runId', () => {
      const events = createCompleteA2UIRun(
        [{ type: 'surfaceUpdate' }],
        'custom_thread',
        'custom_run'
      );

      events.forEach((e) => {
        expect(e.threadId).toBe('custom_thread');
        expect(e.runId).toBe('custom_run');
      });
    });

    it('should generate threadId and runId if not provided', () => {
      const events = createCompleteA2UIRun([{ type: 'surfaceUpdate' }]);

      const threadId = events[0].threadId;
      const runId = events[0].runId;

      expect(threadId).toMatch(/^thread_\d+_[a-z0-9]+$/);
      expect(runId).toMatch(/^run_\d+_[a-z0-9]+$/);

      // All events should have same IDs
      events.forEach((e) => {
        expect(e.threadId).toBe(threadId);
        expect(e.runId).toBe(runId);
      });
    });

    it('should handle empty messages', () => {
      const events = createCompleteA2UIRun([]);

      expect(events.length).toBe(2); // RUN_STARTED + RUN_FINISHED only
      expect(events[0].type).toBe('RUN_STARTED');
      expect(events[1].type).toBe('RUN_FINISHED');
    });
  });

  describe('isA2UIResult', () => {
    const threadId = 'thread_1';
    const runId = 'run_1';

    it('should return true for A2UI TOOL_CALL_RESULT', () => {
      const event = createToolCallResult(
        threadId,
        runId,
        'tool_1',
        { type: 'surfaceUpdate' },
        A2UI_MIME_TYPE
      );

      expect(isA2UIResult(event)).toBe(true);
    });

    it('should return false for non-A2UI TOOL_CALL_RESULT', () => {
      const event = createToolCallResult(
        threadId,
        runId,
        'tool_1',
        { data: 'test' },
        'application/json'
      );

      expect(isA2UIResult(event)).toBe(false);
    });

    it('should return false for non-TOOL_CALL_RESULT events', () => {
      const event = createRunStarted(threadId, runId);
      expect(isA2UIResult(event)).toBe(false);
    });
  });

  describe('extractA2UIMessage', () => {
    const threadId = 'thread_1';
    const runId = 'run_1';

    it('should extract A2UI message from TOOL_CALL_RESULT', () => {
      const a2uiMessage: A2UIMessage = {
        type: 'surfaceUpdate',
        surfaceId: 'main',
        components: [{ type: 'Text', content: 'Hello' }],
      };

      const event = createToolCallResult(
        threadId,
        runId,
        'tool_1',
        a2uiMessage,
        A2UI_MIME_TYPE
      );

      const extracted = extractA2UIMessage(event);
      expect(extracted).toEqual(a2uiMessage);
    });

    it('should return null for non-A2UI events', () => {
      const event = createToolCallResult(
        threadId,
        runId,
        'tool_1',
        { data: 'test' },
        'application/json'
      );

      expect(extractA2UIMessage(event)).toBeNull();
    });

    it('should return null for non-TOOL_CALL_RESULT events', () => {
      const event = createRunStarted(threadId, runId);
      expect(extractA2UIMessage(event)).toBeNull();
    });
  });

  describe('Integration', () => {
    it('should roundtrip A2UI messages through wrap/extract', () => {
      const original: A2UIMessage = {
        type: 'surfaceUpdate',
        surfaceId: 'main',
        components: [
          { type: 'Text', content: 'Hello' },
          { type: 'Button', label: 'Click' },
        ],
      };

      const events = wrapA2UIMessages([original], 'thread_1', 'run_1');
      const resultEvent = events.find((e) => e.type === 'TOOL_CALL_RESULT');
      const extracted = extractA2UIMessage(resultEvent!);

      expect(extracted).toEqual(original);
    });

    it('should identify all A2UI results in a complete run', () => {
      const messages: A2UIMessage[] = [
        { type: 'surfaceUpdate' },
        { type: 'dataModelUpdate' },
        { type: 'beginRendering' },
      ];

      const events = createCompleteA2UIRun(messages, 'thread_1', 'run_1');
      const a2uiResults = events.filter(isA2UIResult);

      expect(a2uiResults.length).toBe(3);
    });
  });
});
