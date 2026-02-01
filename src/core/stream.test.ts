import { describe, it, expect } from 'vitest';
import {
  streamText,
  streamTextWhole,
  createTextRunStream,
  createA2UIRunStream,
  createCombinedRunStream,
  createErrorRunStream,
  collectStream,
  pipeStream,
  withErrorHandling,
  extractTextFromEvents,
  isStreamSuccessful,
  isStreamError,
  getStreamError,
  createStreamContext,
  TextStreamConfig,
  RunStreamConfig,
} from './stream.js';
import { AGUIEvent } from './events.js';
import { A2UIMessage, A2UI_TOOL_NAME } from './a2ui.js';

describe('AG-UI Stream Generator', () => {
  describe('createStreamContext', () => {
    it('should generate IDs when not provided', () => {
      const ctx = createStreamContext();

      expect(ctx.threadId).toMatch(/^thread_\d+_[a-z0-9]+$/);
      expect(ctx.runId).toMatch(/^run_\d+_[a-z0-9]+$/);
      expect(ctx.messageId).toMatch(/^msg_\d+_[a-z0-9]+$/);
      expect(ctx.isRunning).toBe(false);
      expect(ctx.hasError).toBe(false);
    });

    it('should use provided IDs', () => {
      const ctx = createStreamContext({
        threadId: 'custom_thread',
        runId: 'custom_run',
      });

      expect(ctx.threadId).toBe('custom_thread');
      expect(ctx.runId).toBe('custom_run');
    });
  });

  describe('streamText', () => {
    it('should stream text character by character', async () => {
      const events = await collectStream(
        streamText('Hi', 'thread_1', 'run_1')
      );

      expect(events.length).toBe(4); // START + 2 CONTENT + END
      expect(events[0].type).toBe('TEXT_MESSAGE_START');
      expect(events[1].type).toBe('TEXT_MESSAGE_CONTENT');
      expect(events[2].type).toBe('TEXT_MESSAGE_CONTENT');
      expect(events[3].type).toBe('TEXT_MESSAGE_END');

      // Check deltas
      expect((events[1] as any).delta).toBe('H');
      expect((events[2] as any).delta).toBe('i');
    });

    it('should use same messageId for all events', async () => {
      const events = await collectStream(
        streamText('ABC', 'thread_1', 'run_1')
      );

      const messageIds = events.map((e: any) => e.messageId);
      const uniqueIds = new Set(messageIds);
      expect(uniqueIds.size).toBe(1);
    });

    it('should respect chunkSize config', async () => {
      const config: TextStreamConfig = { chunkSize: 3 };
      const events = await collectStream(
        streamText('ABCDEF', 'thread_1', 'run_1', config)
      );

      // START + 2 CONTENT (ABC, DEF) + END
      expect(events.length).toBe(4);
      expect((events[1] as any).delta).toBe('ABC');
      expect((events[2] as any).delta).toBe('DEF');
    });

    it('should handle uneven chunks', async () => {
      const config: TextStreamConfig = { chunkSize: 3 };
      const events = await collectStream(
        streamText('ABCDE', 'thread_1', 'run_1', config)
      );

      // START + 2 CONTENT (ABC, DE) + END
      expect(events.length).toBe(4);
      expect((events[1] as any).delta).toBe('ABC');
      expect((events[2] as any).delta).toBe('DE');
    });

    it('should handle empty text', async () => {
      const events = await collectStream(
        streamText('', 'thread_1', 'run_1')
      );

      // START + END only (no CONTENT)
      expect(events.length).toBe(2);
      expect(events[0].type).toBe('TEXT_MESSAGE_START');
      expect(events[1].type).toBe('TEXT_MESSAGE_END');
    });

    it('should use specified role', async () => {
      const config: TextStreamConfig = { role: 'user' };
      const events = await collectStream(
        streamText('Hi', 'thread_1', 'run_1', config)
      );

      expect((events[0] as any).role).toBe('user');
    });
  });

  describe('streamTextWhole', () => {
    it('should stream text as single content event', async () => {
      const events = await collectStream(
        streamTextWhole('Hello World', 'thread_1', 'run_1')
      );

      expect(events.length).toBe(3); // START + 1 CONTENT + END
      expect(events[0].type).toBe('TEXT_MESSAGE_START');
      expect(events[1].type).toBe('TEXT_MESSAGE_CONTENT');
      expect(events[2].type).toBe('TEXT_MESSAGE_END');
      expect((events[1] as any).delta).toBe('Hello World');
    });

    it('should use specified role', async () => {
      const events = await collectStream(
        streamTextWhole('Hi', 'thread_1', 'run_1', 'system')
      );

      expect((events[0] as any).role).toBe('system');
    });
  });

  describe('createTextRunStream', () => {
    it('should wrap text in complete run', async () => {
      const events = await collectStream(createTextRunStream('Hi'));

      expect(events[0].type).toBe('RUN_STARTED');
      expect(events[events.length - 1].type).toBe('RUN_FINISHED');

      const types = events.map((e) => e.type);
      expect(types).toContain('TEXT_MESSAGE_START');
      expect(types).toContain('TEXT_MESSAGE_CONTENT');
      expect(types).toContain('TEXT_MESSAGE_END');
    });

    it('should use provided threadId and runId', async () => {
      const config: RunStreamConfig = {
        threadId: 'custom_thread',
        runId: 'custom_run',
      };
      const events = await collectStream(createTextRunStream('Hi', config));

      events.forEach((e) => {
        expect(e.threadId).toBe('custom_thread');
        expect(e.runId).toBe('custom_run');
      });
    });

    it('should generate consistent IDs across events', async () => {
      const events = await collectStream(createTextRunStream('Hi'));

      const threadIds = new Set(events.map((e) => e.threadId));
      const runIds = new Set(events.map((e) => e.runId));

      expect(threadIds.size).toBe(1);
      expect(runIds.size).toBe(1);
    });

    it('should respect text streaming config', async () => {
      const config: RunStreamConfig = {
        textConfig: { chunkSize: 5 },
      };
      const events = await collectStream(
        createTextRunStream('Hello World', config)
      );

      const contentEvents = events.filter(
        (e) => e.type === 'TEXT_MESSAGE_CONTENT'
      );
      expect(contentEvents.length).toBe(3); // "Hello", " Worl", "d"
    });
  });

  describe('createA2UIRunStream', () => {
    it('should wrap A2UI messages in complete run', async () => {
      const messages: A2UIMessage[] = [
        { type: 'surfaceUpdate', surfaceId: 'main', components: [] },
      ];

      const events = await collectStream(createA2UIRunStream(messages));

      expect(events[0].type).toBe('RUN_STARTED');
      expect(events[events.length - 1].type).toBe('RUN_FINISHED');

      const types = events.map((e) => e.type);
      expect(types).toContain('TOOL_CALL_START');
      expect(types).toContain('TOOL_CALL_RESULT');
      expect(types).toContain('TOOL_CALL_END');
    });

    it('should use A2UI tool name', async () => {
      const messages: A2UIMessage[] = [{ type: 'surfaceUpdate' }];
      const events = await collectStream(createA2UIRunStream(messages));

      const startEvent = events.find((e) => e.type === 'TOOL_CALL_START') as any;
      expect(startEvent.toolCallName).toBe(A2UI_TOOL_NAME);
    });

    it('should handle multiple A2UI messages', async () => {
      const messages: A2UIMessage[] = [
        { type: 'surfaceUpdate' },
        { type: 'dataModelUpdate' },
        { type: 'beginRendering' },
      ];

      const events = await collectStream(createA2UIRunStream(messages));

      const resultEvents = events.filter((e) => e.type === 'TOOL_CALL_RESULT');
      expect(resultEvents.length).toBe(3);
    });

    it('should handle empty messages', async () => {
      const events = await collectStream(createA2UIRunStream([]));

      // RUN_STARTED + RUN_FINISHED only
      expect(events.length).toBe(2);
      expect(events[0].type).toBe('RUN_STARTED');
      expect(events[1].type).toBe('RUN_FINISHED');
    });
  });

  describe('createCombinedRunStream', () => {
    it('should stream both text and A2UI messages', async () => {
      const a2uiMessages: A2UIMessage[] = [{ type: 'surfaceUpdate' }];

      const events = await collectStream(
        createCombinedRunStream('Hello', a2uiMessages)
      );

      const types = events.map((e) => e.type);

      // Should have both text and tool events
      expect(types).toContain('TEXT_MESSAGE_START');
      expect(types).toContain('TEXT_MESSAGE_CONTENT');
      expect(types).toContain('TEXT_MESSAGE_END');
      expect(types).toContain('TOOL_CALL_START');
      expect(types).toContain('TOOL_CALL_RESULT');
      expect(types).toContain('TOOL_CALL_END');

      // Wrapped in run events
      expect(types[0]).toBe('RUN_STARTED');
      expect(types[types.length - 1]).toBe('RUN_FINISHED');
    });

    it('should handle text only', async () => {
      const events = await collectStream(createCombinedRunStream('Hello'));

      const types = events.map((e) => e.type);
      expect(types).toContain('TEXT_MESSAGE_CONTENT');
      expect(types).not.toContain('TOOL_CALL_START');
    });

    it('should handle A2UI only', async () => {
      const a2uiMessages: A2UIMessage[] = [{ type: 'surfaceUpdate' }];
      const events = await collectStream(
        createCombinedRunStream(undefined, a2uiMessages)
      );

      const types = events.map((e) => e.type);
      expect(types).not.toContain('TEXT_MESSAGE_START');
      expect(types).toContain('TOOL_CALL_START');
    });

    it('should handle neither text nor A2UI', async () => {
      const events = await collectStream(createCombinedRunStream());

      expect(events.length).toBe(2);
      expect(events[0].type).toBe('RUN_STARTED');
      expect(events[1].type).toBe('RUN_FINISHED');
    });
  });

  describe('createErrorRunStream', () => {
    it('should create error stream from Error object', async () => {
      const error = new Error('Something went wrong');
      const events = await collectStream(createErrorRunStream(error, 'ERR_001'));

      expect(events.length).toBe(2);
      expect(events[0].type).toBe('RUN_STARTED');
      expect(events[1].type).toBe('RUN_ERROR');
      expect((events[1] as any).message).toBe('Something went wrong');
      expect((events[1] as any).code).toBe('ERR_001');
    });

    it('should create error stream from string', async () => {
      const events = await collectStream(createErrorRunStream('Error!'));

      expect(events[1].type).toBe('RUN_ERROR');
      expect((events[1] as any).message).toBe('Error!');
    });

    it('should use provided IDs', async () => {
      const config: RunStreamConfig = {
        threadId: 'thread_err',
        runId: 'run_err',
      };
      const events = await collectStream(
        createErrorRunStream('Error', 'ERR', config)
      );

      expect(events[0].threadId).toBe('thread_err');
      expect(events[0].runId).toBe('run_err');
    });
  });

  describe('collectStream', () => {
    it('should collect all events into array', async () => {
      const events = await collectStream(
        streamText('AB', 'thread_1', 'run_1')
      );

      expect(Array.isArray(events)).toBe(true);
      expect(events.length).toBe(4); // START + 2 CONTENT + END
    });
  });

  describe('pipeStream', () => {
    it('should call callback for each event', async () => {
      const collected: AGUIEvent[] = [];

      await pipeStream(
        streamText('AB', 'thread_1', 'run_1'),
        (event) => {
          collected.push(event);
        }
      );

      expect(collected.length).toBe(4);
    });

    it('should handle async callbacks', async () => {
      const collected: string[] = [];

      await pipeStream(createTextRunStream('Hi'), async (event) => {
        await new Promise((r) => setTimeout(r, 1));
        collected.push(event.type);
      });

      expect(collected.length).toBeGreaterThan(0);
      expect(collected[0]).toBe('RUN_STARTED');
    });
  });

  describe('withErrorHandling', () => {
    it('should pass through events normally', async () => {
      const source = streamText('Hi', 'thread_1', 'run_1');
      const wrapped = withErrorHandling(source, 'thread_1', 'run_1');

      const events = await collectStream(wrapped);
      expect(events.length).toBe(4);
      expect(events[0].type).toBe('TEXT_MESSAGE_START');
    });

    it('should catch errors and yield RUN_ERROR', async () => {
      async function* failingStream(): AsyncGenerator<AGUIEvent, void, undefined> {
        yield { type: 'RUN_STARTED', threadId: 't', runId: 'r', timestamp: '' } as AGUIEvent;
        throw new Error('Stream failed');
      }

      const wrapped = withErrorHandling(failingStream(), 'thread_1', 'run_1');
      const events = await collectStream(wrapped);

      expect(events.length).toBe(2);
      expect(events[0].type).toBe('RUN_STARTED');
      expect(events[1].type).toBe('RUN_ERROR');
      expect((events[1] as any).message).toBe('Stream failed');
    });
  });

  describe('extractTextFromEvents', () => {
    it('should extract text from TEXT_MESSAGE_CONTENT events', async () => {
      const events = await collectStream(
        streamText('Hello', 'thread_1', 'run_1')
      );

      const text = extractTextFromEvents(events);
      expect(text).toBe('Hello');
    });

    it('should handle events without text', () => {
      const events: AGUIEvent[] = [
        { type: 'RUN_STARTED', threadId: 't', runId: 'r', timestamp: '' },
        { type: 'RUN_FINISHED', threadId: 't', runId: 'r', timestamp: '' },
      ];

      expect(extractTextFromEvents(events)).toBe('');
    });
  });

  describe('isStreamSuccessful', () => {
    it('should return true for successful stream', async () => {
      const events = await collectStream(createTextRunStream('Hi'));
      expect(isStreamSuccessful(events)).toBe(true);
    });

    it('should return false for error stream', async () => {
      const events = await collectStream(createErrorRunStream('Error'));
      expect(isStreamSuccessful(events)).toBe(false);
    });

    it('should return false for incomplete stream', () => {
      const events: AGUIEvent[] = [
        { type: 'RUN_STARTED', threadId: 't', runId: 'r', timestamp: '' },
      ];
      expect(isStreamSuccessful(events)).toBe(false);
    });
  });

  describe('isStreamError', () => {
    it('should return true for error stream', async () => {
      const events = await collectStream(createErrorRunStream('Error'));
      expect(isStreamError(events)).toBe(true);
    });

    it('should return false for successful stream', async () => {
      const events = await collectStream(createTextRunStream('Hi'));
      expect(isStreamError(events)).toBe(false);
    });
  });

  describe('getStreamError', () => {
    it('should return error message', async () => {
      const events = await collectStream(createErrorRunStream('Test error'));
      expect(getStreamError(events)).toBe('Test error');
    });

    it('should return null for successful stream', async () => {
      const events = await collectStream(createTextRunStream('Hi'));
      expect(getStreamError(events)).toBeNull();
    });
  });

  describe('Event Sequence Validation', () => {
    it('should always start with RUN_STARTED', async () => {
      const textEvents = await collectStream(createTextRunStream('Hi'));
      const a2uiEvents = await collectStream(
        createA2UIRunStream([{ type: 'surfaceUpdate' }])
      );
      const errorEvents = await collectStream(createErrorRunStream('Err'));

      expect(textEvents[0].type).toBe('RUN_STARTED');
      expect(a2uiEvents[0].type).toBe('RUN_STARTED');
      expect(errorEvents[0].type).toBe('RUN_STARTED');
    });

    it('should end with RUN_FINISHED for successful streams', async () => {
      const textEvents = await collectStream(createTextRunStream('Hi'));
      const a2uiEvents = await collectStream(
        createA2UIRunStream([{ type: 'surfaceUpdate' }])
      );

      expect(textEvents[textEvents.length - 1].type).toBe('RUN_FINISHED');
      expect(a2uiEvents[a2uiEvents.length - 1].type).toBe('RUN_FINISHED');
    });

    it('should end with RUN_ERROR for error streams', async () => {
      const events = await collectStream(createErrorRunStream('Error'));
      expect(events[events.length - 1].type).toBe('RUN_ERROR');
    });

    it('TEXT_MESSAGE sequence should be START → CONTENT → END', async () => {
      const events = await collectStream(createTextRunStream('Hi'));

      const textEvents = events.filter(
        (e) =>
          e.type === 'TEXT_MESSAGE_START' ||
          e.type === 'TEXT_MESSAGE_CONTENT' ||
          e.type === 'TEXT_MESSAGE_END'
      );

      expect(textEvents[0].type).toBe('TEXT_MESSAGE_START');
      expect(textEvents[textEvents.length - 1].type).toBe('TEXT_MESSAGE_END');

      // All middle events should be CONTENT
      for (let i = 1; i < textEvents.length - 1; i++) {
        expect(textEvents[i].type).toBe('TEXT_MESSAGE_CONTENT');
      }
    });

    it('TOOL_CALL sequence should be START → RESULT* → END', async () => {
      const events = await collectStream(
        createA2UIRunStream([
          { type: 'surfaceUpdate' },
          { type: 'dataModelUpdate' },
        ])
      );

      const toolEvents = events.filter(
        (e) =>
          e.type === 'TOOL_CALL_START' ||
          e.type === 'TOOL_CALL_RESULT' ||
          e.type === 'TOOL_CALL_END'
      );

      expect(toolEvents[0].type).toBe('TOOL_CALL_START');
      expect(toolEvents[toolEvents.length - 1].type).toBe('TOOL_CALL_END');

      // All middle events should be RESULT
      for (let i = 1; i < toolEvents.length - 1; i++) {
        expect(toolEvents[i].type).toBe('TOOL_CALL_RESULT');
      }
    });
  });

  describe('Integration', () => {
    it('should support full roundtrip: generate → collect → extract', async () => {
      const originalText = 'Hello, World!';
      const events = await collectStream(createTextRunStream(originalText));
      const extractedText = extractTextFromEvents(events);

      expect(extractedText).toBe(originalText);
    });

    it('should work with delay config', async () => {
      const start = Date.now();
      const config: RunStreamConfig = {
        textConfig: { delayMs: 10 },
      };

      const events = await collectStream(createTextRunStream('ABC', config));
      const elapsed = Date.now() - start;

      // Should take at least 20ms (3 chars * 10ms delay, but first has no delay before)
      expect(elapsed).toBeGreaterThanOrEqual(20);
      expect(events.length).toBeGreaterThan(0);
    });
  });
});
