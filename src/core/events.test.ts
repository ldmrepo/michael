import { describe, it, expect } from 'vitest';
import {
  AGUIEventType,
  AGUIEvent,
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
  ToolCallRequestEvent,
  generateId,
  generateRunId,
  generateMessageId,
  generateThreadId,
  generateToolCallId,
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
  createToolCallRequest,
  // Type guards
  isRunEvent,
  isTextMessageEvent,
  isToolCallEvent,
  isToolCallRequestEvent,
} from './events.js';

describe('AG-UI Events', () => {
  describe('AGUIEventType', () => {
    it('should have all lifecycle event types', () => {
      const types: AGUIEventType[] = ['RUN_STARTED', 'RUN_FINISHED', 'RUN_ERROR'];
      types.forEach((t) => expect(t).toBeDefined());
    });

    it('should have all text streaming event types', () => {
      const types: AGUIEventType[] = [
        'TEXT_MESSAGE_START',
        'TEXT_MESSAGE_CONTENT',
        'TEXT_MESSAGE_END',
      ];
      types.forEach((t) => expect(t).toBeDefined());
    });

    it('should have all tool call event types', () => {
      const types: AGUIEventType[] = [
        'TOOL_CALL_START',
        'TOOL_CALL_ARGS',
        'TOOL_CALL_END',
        'TOOL_CALL_RESULT',
        'TOOL_CALL_REQUEST',
      ];
      types.forEach((t) => expect(t).toBeDefined());
    });
  });

  describe('ID Generators', () => {
    describe('generateId', () => {
      it('should generate unique IDs', () => {
        const id1 = generateId('test');
        const id2 = generateId('test');
        expect(id1).not.toBe(id2);
      });

      it('should generate ID with correct prefix', () => {
        const id = generateId('custom');
        expect(id).toMatch(/^custom_\d+_[a-z0-9]+$/);
      });
    });

    describe('generateRunId', () => {
      it('should generate unique run IDs', () => {
        const id1 = generateRunId();
        const id2 = generateRunId();
        expect(id1).not.toBe(id2);
      });

      it('should generate run ID with correct prefix', () => {
        const id = generateRunId();
        expect(id).toMatch(/^run_\d+_[a-z0-9]+$/);
      });

      it('should generate many unique IDs', () => {
        const ids = new Set<string>();
        for (let i = 0; i < 100; i++) {
          ids.add(generateRunId());
        }
        expect(ids.size).toBe(100);
      });
    });

    describe('generateMessageId', () => {
      it('should generate unique message IDs', () => {
        const id1 = generateMessageId();
        const id2 = generateMessageId();
        expect(id1).not.toBe(id2);
      });

      it('should generate message ID with correct prefix', () => {
        const id = generateMessageId();
        expect(id).toMatch(/^msg_\d+_[a-z0-9]+$/);
      });
    });

    describe('generateThreadId', () => {
      it('should generate unique thread IDs', () => {
        const id1 = generateThreadId();
        const id2 = generateThreadId();
        expect(id1).not.toBe(id2);
      });

      it('should generate thread ID with correct prefix', () => {
        const id = generateThreadId();
        expect(id).toMatch(/^thread_\d+_[a-z0-9]+$/);
      });
    });

    describe('generateToolCallId', () => {
      it('should generate unique tool call IDs', () => {
        const id1 = generateToolCallId();
        const id2 = generateToolCallId();
        expect(id1).not.toBe(id2);
      });

      it('should generate tool call ID with correct prefix', () => {
        const id = generateToolCallId();
        expect(id).toMatch(/^tool_\d+_[a-z0-9]+$/);
      });
    });
  });

  describe('getTimestamp', () => {
    it('should return ISO format timestamp', () => {
      const timestamp = getTimestamp();
      expect(timestamp).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/);
    });

    it('should return current time', () => {
      const before = new Date().toISOString();
      const timestamp = getTimestamp();
      const after = new Date().toISOString();
      expect(timestamp >= before).toBe(true);
      expect(timestamp <= after).toBe(true);
    });
  });

  describe('Run Event Helpers', () => {
    const threadId = 'thread_123';
    const runId = 'run_456';

    it('should create RUN_STARTED event with required fields', () => {
      const event = createRunStarted(threadId, runId);

      expect(event.type).toBe('RUN_STARTED');
      expect(event.threadId).toBe(threadId);
      expect(event.runId).toBe(runId);
      expect(event.timestamp).toBeDefined();
    });

    it('should create RUN_FINISHED event with required fields', () => {
      const event = createRunFinished(threadId, runId);

      expect(event.type).toBe('RUN_FINISHED');
      expect(event.threadId).toBe(threadId);
      expect(event.runId).toBe(runId);
      expect(event.timestamp).toBeDefined();
    });

    it('should create RUN_ERROR event with message', () => {
      const event = createRunError(threadId, runId, 'Something went wrong');

      expect(event.type).toBe('RUN_ERROR');
      expect(event.threadId).toBe(threadId);
      expect(event.runId).toBe(runId);
      expect(event.message).toBe('Something went wrong');
      expect(event.code).toBeUndefined();
    });

    it('should create RUN_ERROR event with message and code', () => {
      const event = createRunError(threadId, runId, 'Something went wrong', 'ERR_001');

      expect(event.type).toBe('RUN_ERROR');
      expect(event.message).toBe('Something went wrong');
      expect(event.code).toBe('ERR_001');
    });
  });

  describe('Text Message Event Helpers', () => {
    const threadId = 'thread_123';
    const runId = 'run_456';
    const messageId = 'msg_789';

    it('should create TEXT_MESSAGE_START event', () => {
      const event = createTextMessageStart(threadId, runId, messageId);

      expect(event.type).toBe('TEXT_MESSAGE_START');
      expect(event.threadId).toBe(threadId);
      expect(event.runId).toBe(runId);
      expect(event.messageId).toBe(messageId);
      expect(event.role).toBe('assistant');
    });

    it('should create TEXT_MESSAGE_START event with custom role', () => {
      const event = createTextMessageStart(threadId, runId, messageId, 'user');

      expect(event.role).toBe('user');
    });

    it('should create TEXT_MESSAGE_CONTENT event', () => {
      const event = createTextMessageContent(threadId, runId, messageId, 'Hello ');

      expect(event.type).toBe('TEXT_MESSAGE_CONTENT');
      expect(event.threadId).toBe(threadId);
      expect(event.runId).toBe(runId);
      expect(event.messageId).toBe(messageId);
      expect(event.delta).toBe('Hello ');
    });

    it('should create TEXT_MESSAGE_END event', () => {
      const event = createTextMessageEnd(threadId, runId, messageId);

      expect(event.type).toBe('TEXT_MESSAGE_END');
      expect(event.threadId).toBe(threadId);
      expect(event.runId).toBe(runId);
      expect(event.messageId).toBe(messageId);
    });
  });

  describe('Tool Call Event Helpers', () => {
    const threadId = 'thread_123';
    const runId = 'run_456';
    const toolCallId = 'tool_789';

    it('should create TOOL_CALL_START event', () => {
      const event = createToolCallStart(threadId, runId, toolCallId, 'search');

      expect(event.type).toBe('TOOL_CALL_START');
      expect(event.threadId).toBe(threadId);
      expect(event.runId).toBe(runId);
      expect(event.toolCallId).toBe(toolCallId);
      expect(event.toolCallName).toBe('search');
    });

    it('should create TOOL_CALL_ARGS event', () => {
      const event = createToolCallArgs(threadId, runId, toolCallId, '{"query":');

      expect(event.type).toBe('TOOL_CALL_ARGS');
      expect(event.toolCallId).toBe(toolCallId);
      expect(event.delta).toBe('{"query":');
    });

    it('should create TOOL_CALL_END event', () => {
      const event = createToolCallEnd(threadId, runId, toolCallId);

      expect(event.type).toBe('TOOL_CALL_END');
      expect(event.toolCallId).toBe(toolCallId);
    });

    it('should create TOOL_CALL_RESULT event with default mimeType', () => {
      const event = createToolCallResult(threadId, runId, toolCallId, { result: 'success' });

      expect(event.type).toBe('TOOL_CALL_RESULT');
      expect(event.toolCallId).toBe(toolCallId);
      expect(event.content.mimeType).toBe('application/json');
      expect(event.content.data).toEqual({ result: 'success' });
    });

    it('should create TOOL_CALL_RESULT event with custom mimeType', () => {
      const event = createToolCallResult(
        threadId,
        runId,
        toolCallId,
        '<ui />',
        'application/json+a2ui'
      );

      expect(event.content.mimeType).toBe('application/json+a2ui');
      expect(event.content.data).toBe('<ui />');
    });

    it('should create TOOL_CALL_REQUEST event', () => {
      const event = createToolCallRequest(threadId, runId, toolCallId, 'confirm', {
        message: 'Are you sure?',
      });

      expect(event.type).toBe('TOOL_CALL_REQUEST');
      expect(event.toolCallId).toBe(toolCallId);
      expect(event.toolName).toBe('confirm');
      expect(event.arguments).toEqual({ message: 'Are you sure?' });
    });
  });

  describe('AGUIEvent Union Type', () => {
    it('should accept RunStartedEvent', () => {
      const event: AGUIEvent = createRunStarted('thread_1', 'run_1');
      expect(event.type).toBe('RUN_STARTED');
    });

    it('should accept RunFinishedEvent', () => {
      const event: AGUIEvent = createRunFinished('thread_1', 'run_1');
      expect(event.type).toBe('RUN_FINISHED');
    });

    it('should accept all event types in the union', () => {
      const events: AGUIEvent[] = [
        createRunStarted('t', 'r'),
        createRunFinished('t', 'r'),
        createRunError('t', 'r', 'error'),
        createTextMessageStart('t', 'r', 'm'),
        createTextMessageContent('t', 'r', 'm', 'delta'),
        createTextMessageEnd('t', 'r', 'm'),
        createToolCallStart('t', 'r', 'tc', 'name'),
        createToolCallArgs('t', 'r', 'tc', 'delta'),
        createToolCallEnd('t', 'r', 'tc'),
        createToolCallResult('t', 'r', 'tc', {}),
        createToolCallRequest('t', 'r', 'tc', 'name', {}),
      ];

      expect(events.length).toBe(11);
      events.forEach((e) => {
        expect(e.threadId).toBe('t');
        expect(e.runId).toBe('r');
        expect(e.timestamp).toBeDefined();
      });
    });
  });

  describe('AGUIBaseEvent structure', () => {
    it('should have all required base fields', () => {
      const event = createRunStarted('thread_1', 'run_1');

      // Type assertion to check base interface
      const baseEvent: AGUIBaseEvent = event;
      expect(baseEvent.type).toBeDefined();
      expect(baseEvent.threadId).toBeDefined();
      expect(baseEvent.runId).toBeDefined();
      expect(baseEvent.timestamp).toBeDefined();
    });
  });

  describe('Type Guards', () => {
    const threadId = 'thread_1';
    const runId = 'run_1';
    const messageId = 'msg_1';
    const toolCallId = 'tool_1';

    describe('isRunEvent', () => {
      it('should return true for RUN_STARTED', () => {
        const event = createRunStarted(threadId, runId);
        expect(isRunEvent(event)).toBe(true);
      });

      it('should return true for RUN_FINISHED', () => {
        const event = createRunFinished(threadId, runId);
        expect(isRunEvent(event)).toBe(true);
      });

      it('should return true for RUN_ERROR', () => {
        const event = createRunError(threadId, runId, 'error');
        expect(isRunEvent(event)).toBe(true);
      });

      it('should return false for non-run events', () => {
        const textEvent = createTextMessageStart(threadId, runId, messageId);
        const toolEvent = createToolCallStart(threadId, runId, toolCallId, 'test');
        expect(isRunEvent(textEvent)).toBe(false);
        expect(isRunEvent(toolEvent)).toBe(false);
      });

      it('should narrow type correctly', () => {
        const event: AGUIEvent = createRunError(threadId, runId, 'test error', 'ERR_001');
        if (isRunEvent(event)) {
          // TypeScript should recognize this as a run event
          expect(event.threadId).toBe(threadId);
          if (event.type === 'RUN_ERROR') {
            expect(event.message).toBe('test error');
          }
        }
      });
    });

    describe('isTextMessageEvent', () => {
      it('should return true for TEXT_MESSAGE_START', () => {
        const event = createTextMessageStart(threadId, runId, messageId);
        expect(isTextMessageEvent(event)).toBe(true);
      });

      it('should return true for TEXT_MESSAGE_CONTENT', () => {
        const event = createTextMessageContent(threadId, runId, messageId, 'delta');
        expect(isTextMessageEvent(event)).toBe(true);
      });

      it('should return true for TEXT_MESSAGE_END', () => {
        const event = createTextMessageEnd(threadId, runId, messageId);
        expect(isTextMessageEvent(event)).toBe(true);
      });

      it('should return false for non-text-message events', () => {
        const runEvent = createRunStarted(threadId, runId);
        const toolEvent = createToolCallStart(threadId, runId, toolCallId, 'test');
        expect(isTextMessageEvent(runEvent)).toBe(false);
        expect(isTextMessageEvent(toolEvent)).toBe(false);
      });

      it('should narrow type correctly', () => {
        const event: AGUIEvent = createTextMessageContent(threadId, runId, messageId, 'hello');
        if (isTextMessageEvent(event)) {
          expect(event.messageId).toBe(messageId);
          if (event.type === 'TEXT_MESSAGE_CONTENT') {
            expect(event.delta).toBe('hello');
          }
        }
      });
    });

    describe('isToolCallEvent', () => {
      it('should return true for TOOL_CALL_START', () => {
        const event = createToolCallStart(threadId, runId, toolCallId, 'test');
        expect(isToolCallEvent(event)).toBe(true);
      });

      it('should return true for TOOL_CALL_ARGS', () => {
        const event = createToolCallArgs(threadId, runId, toolCallId, 'args');
        expect(isToolCallEvent(event)).toBe(true);
      });

      it('should return true for TOOL_CALL_END', () => {
        const event = createToolCallEnd(threadId, runId, toolCallId);
        expect(isToolCallEvent(event)).toBe(true);
      });

      it('should return true for TOOL_CALL_RESULT', () => {
        const event = createToolCallResult(threadId, runId, toolCallId, {});
        expect(isToolCallEvent(event)).toBe(true);
      });

      it('should return false for TOOL_CALL_REQUEST (frontend tool)', () => {
        const event = createToolCallRequest(threadId, runId, toolCallId, 'confirm', {});
        expect(isToolCallEvent(event)).toBe(false);
      });

      it('should return false for non-tool-call events', () => {
        const runEvent = createRunStarted(threadId, runId);
        const textEvent = createTextMessageStart(threadId, runId, messageId);
        expect(isToolCallEvent(runEvent)).toBe(false);
        expect(isToolCallEvent(textEvent)).toBe(false);
      });

      it('should narrow type correctly', () => {
        const event: AGUIEvent = createToolCallResult(threadId, runId, toolCallId, { data: 'test' });
        if (isToolCallEvent(event)) {
          expect(event.toolCallId).toBe(toolCallId);
          if (event.type === 'TOOL_CALL_RESULT') {
            expect(event.content.data).toEqual({ data: 'test' });
          }
        }
      });
    });

    describe('isToolCallRequestEvent', () => {
      it('should return true for TOOL_CALL_REQUEST', () => {
        const event = createToolCallRequest(threadId, runId, toolCallId, 'confirm', { message: 'ok?' });
        expect(isToolCallRequestEvent(event)).toBe(true);
      });

      it('should return false for other tool call events', () => {
        const startEvent = createToolCallStart(threadId, runId, toolCallId, 'test');
        const resultEvent = createToolCallResult(threadId, runId, toolCallId, {});
        expect(isToolCallRequestEvent(startEvent)).toBe(false);
        expect(isToolCallRequestEvent(resultEvent)).toBe(false);
      });

      it('should return false for non-tool events', () => {
        const runEvent = createRunStarted(threadId, runId);
        const textEvent = createTextMessageStart(threadId, runId, messageId);
        expect(isToolCallRequestEvent(runEvent)).toBe(false);
        expect(isToolCallRequestEvent(textEvent)).toBe(false);
      });

      it('should narrow type correctly', () => {
        const event: AGUIEvent = createToolCallRequest(threadId, runId, toolCallId, 'confirm', { message: 'sure?' });
        if (isToolCallRequestEvent(event)) {
          expect(event.toolName).toBe('confirm');
          expect(event.arguments).toEqual({ message: 'sure?' });
        }
      });
    });

    describe('Type guard combinations', () => {
      it('should categorize all events correctly', () => {
        const allEvents: AGUIEvent[] = [
          createRunStarted('t', 'r'),
          createRunFinished('t', 'r'),
          createRunError('t', 'r', 'err'),
          createTextMessageStart('t', 'r', 'm'),
          createTextMessageContent('t', 'r', 'm', 'd'),
          createTextMessageEnd('t', 'r', 'm'),
          createToolCallStart('t', 'r', 'tc', 'n'),
          createToolCallArgs('t', 'r', 'tc', 'd'),
          createToolCallEnd('t', 'r', 'tc'),
          createToolCallResult('t', 'r', 'tc', {}),
          createToolCallRequest('t', 'r', 'tc', 'n', {}),
        ];

        const runEvents = allEvents.filter(isRunEvent);
        const textEvents = allEvents.filter(isTextMessageEvent);
        const toolCallEvents = allEvents.filter(isToolCallEvent);
        const toolRequestEvents = allEvents.filter(isToolCallRequestEvent);

        expect(runEvents.length).toBe(3);
        expect(textEvents.length).toBe(3);
        expect(toolCallEvents.length).toBe(4);
        expect(toolRequestEvents.length).toBe(1);

        // No overlaps
        expect(runEvents.length + textEvents.length + toolCallEvents.length + toolRequestEvents.length).toBe(11);
      });
    });
  });
});
