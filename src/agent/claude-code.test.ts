import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ClaudeCodeAgent, StreamingCallbacks, A2UIAgentMessage } from './claude-code.js';
import { Memory } from '../brain/memory.js';

// Mock child_process
vi.mock('child_process', () => ({
  spawn: vi.fn(() => ({
    stdin: {
      write: vi.fn(),
      end: vi.fn(),
    },
    stdout: {
      on: vi.fn(),
    },
    stderr: {
      on: vi.fn(),
    },
    on: vi.fn(),
  })),
}));

describe('ClaudeCodeAgent', () => {
  let agent: ClaudeCodeAgent;
  let mockMemory: Memory;

  beforeEach(() => {
    // Create mock memory
    mockMemory = {
      saveMessage: vi.fn().mockResolvedValue(undefined),
      saveFact: vi.fn().mockResolvedValue(undefined),
      saveSchedule: vi.fn().mockResolvedValue(undefined),
      deactivateSchedule: vi.fn().mockResolvedValue(undefined),
      getRecentMessages: vi.fn().mockReturnValue([]),
      getAllFacts: vi.fn().mockReturnValue([]),
      searchMessages: vi.fn().mockReturnValue([]),
      searchMessagesVector: vi.fn().mockResolvedValue([]),
    } as unknown as Memory;

    agent = new ClaudeCodeAgent(mockMemory);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('A2UI Marker Parsing', () => {
    // Access private method through any type for testing
    const processResponse = async (
      agent: ClaudeCodeAgent,
      userId: string,
      userMessage: string,
      response: string,
      callbacks?: StreamingCallbacks
    ) => {
      return (agent as any).processResponse(userId, userMessage, response, callbacks);
    };

    it('should parse A2UI_SURFACE markers', async () => {
      const onA2UI = vi.fn();
      const callbacks: StreamingCallbacks = { onA2UI };

      const response = `Here's a card for you:
[A2UI_SURFACE:main][{"id":"card1","component":{"Card":{"title":{"literalString":"Welcome"}}}}][/A2UI_SURFACE]
Enjoy!`;

      await processResponse(agent, 'user1', 'show card', response, callbacks);

      expect(onA2UI).toHaveBeenCalledTimes(1);
      const messages = onA2UI.mock.calls[0][0] as A2UIAgentMessage[];
      expect(messages.length).toBe(1);
      expect(messages[0].type).toBe('surfaceUpdate');
      expect(messages[0].surfaceId).toBe('main');
      expect(messages[0].components).toEqual([
        { id: 'card1', component: { Card: { title: { literalString: 'Welcome' } } } },
      ]);
    });

    it('should parse A2UI_DATA markers', async () => {
      const onA2UI = vi.fn();
      const callbacks: StreamingCallbacks = { onA2UI };

      const response = `Updating data:
[A2UI_DATA:booking]{"date":"2026-03-15","destination":"Tokyo"}[/A2UI_DATA]
Done!`;

      await processResponse(agent, 'user1', 'book trip', response, callbacks);

      expect(onA2UI).toHaveBeenCalledTimes(1);
      const messages = onA2UI.mock.calls[0][0] as A2UIAgentMessage[];
      expect(messages.length).toBe(1);
      expect(messages[0].type).toBe('dataModelUpdate');
      expect(messages[0].modelId).toBe('booking');
      expect(messages[0].data).toEqual({
        date: '2026-03-15',
        destination: 'Tokyo',
      });
    });

    it('should parse multiple A2UI markers', async () => {
      const onA2UI = vi.fn();
      const callbacks: StreamingCallbacks = { onA2UI };

      const response = `
[A2UI_SURFACE:main][{"id":"text1","component":{"Text":{"text":{"literalString":"Hello"}}}}][/A2UI_SURFACE]
[A2UI_DATA:form]{"name":"John"}[/A2UI_DATA]
[A2UI_SURFACE:sidebar][{"id":"menu","component":{"List":{"children":{"explicitList":[]}}}}][/A2UI_SURFACE]
`;

      await processResponse(agent, 'user1', 'show ui', response, callbacks);

      expect(onA2UI).toHaveBeenCalledTimes(1);
      const messages = onA2UI.mock.calls[0][0] as A2UIAgentMessage[];
      expect(messages.length).toBe(3);
      expect(messages[0].type).toBe('surfaceUpdate');
      expect(messages[0].surfaceId).toBe('main');
      expect(messages[1].type).toBe('dataModelUpdate');
      expect(messages[1].modelId).toBe('form');
      expect(messages[2].type).toBe('surfaceUpdate');
      expect(messages[2].surfaceId).toBe('sidebar');
    });

    it('should not call onA2UI when no markers present', async () => {
      const onA2UI = vi.fn();
      const callbacks: StreamingCallbacks = { onA2UI };

      const response = 'Hello! How can I help you today?';

      await processResponse(agent, 'user1', 'hello', response, callbacks);

      expect(onA2UI).not.toHaveBeenCalled();
    });

    it('should not call onA2UI when callback not provided', async () => {
      const response = '[A2UI_SURFACE:main][{"id":"text1"}][/A2UI_SURFACE]';

      // Should not throw
      await processResponse(agent, 'user1', 'show', response, undefined);
      await processResponse(agent, 'user1', 'show', response, {});
    });

    it('should handle invalid JSON in A2UI markers gracefully', async () => {
      const onA2UI = vi.fn();
      const callbacks: StreamingCallbacks = { onA2UI };

      const response = `
[A2UI_SURFACE:main]invalid-json[/A2UI_SURFACE]
[A2UI_DATA:form]{"valid":"data"}[/A2UI_DATA]
`;

      await processResponse(agent, 'user1', 'test', response, callbacks);

      // Only valid marker should be in the result
      expect(onA2UI).toHaveBeenCalledTimes(1);
      const messages = onA2UI.mock.calls[0][0] as A2UIAgentMessage[];
      expect(messages.length).toBe(1);
      expect(messages[0].type).toBe('dataModelUpdate');
    });

    it('should clean A2UI markers from saved response', async () => {
      const response = `Hello!
[A2UI_SURFACE:main][{"id":"text1"}][/A2UI_SURFACE]
How can I help?
[A2UI_DATA:form]{"name":"John"}[/A2UI_DATA]
Bye!`;

      await processResponse(agent, 'user1', 'test', response);

      // Check that memory.saveMessage was called with clean content
      expect(mockMemory.saveMessage).toHaveBeenCalledWith(
        'user1',
        'assistant',
        expect.not.stringContaining('[A2UI_')
      );
      expect(mockMemory.saveMessage).toHaveBeenCalledWith(
        'user1',
        'assistant',
        'Hello!\n\nHow can I help?\n\nBye!'
      );
    });

    it('should handle multiline JSON in A2UI markers', async () => {
      const onA2UI = vi.fn();
      const callbacks: StreamingCallbacks = { onA2UI };

      const response = `Here's your data:
[A2UI_DATA:booking]{
  "date": "2026-03-15",
  "destination": "Tokyo",
  "passengers": 2
}[/A2UI_DATA]
Done!`;

      await processResponse(agent, 'user1', 'book', response, callbacks);

      expect(onA2UI).toHaveBeenCalledTimes(1);
      const messages = onA2UI.mock.calls[0][0] as A2UIAgentMessage[];
      expect(messages.length).toBe(1);
      expect(messages[0].data).toEqual({
        date: '2026-03-15',
        destination: 'Tokyo',
        passengers: 2,
      });
    });
  });

  describe('Fact Marker Parsing', () => {
    const processResponse = async (
      agent: ClaudeCodeAgent,
      userId: string,
      userMessage: string,
      response: string
    ) => {
      return (agent as any).processResponse(userId, userMessage, response);
    };

    it('should parse and save facts', async () => {
      const response = 'Got it! [FACT:name:John Doe] I will remember that.';

      await processResponse(agent, 'user1', 'my name is John Doe', response);

      expect(mockMemory.saveFact).toHaveBeenCalledWith('user1', 'name', 'John Doe');
    });

    it('should parse multiple facts', async () => {
      const response = '[FACT:name:John][FACT:age:30][FACT:city:Tokyo]';

      await processResponse(agent, 'user1', 'info', response);

      expect(mockMemory.saveFact).toHaveBeenCalledTimes(3);
      expect(mockMemory.saveFact).toHaveBeenCalledWith('user1', 'name', 'John');
      expect(mockMemory.saveFact).toHaveBeenCalledWith('user1', 'age', '30');
      expect(mockMemory.saveFact).toHaveBeenCalledWith('user1', 'city', 'Tokyo');
    });
  });

  describe('Schedule Marker Parsing', () => {
    const processResponse = async (
      agent: ClaudeCodeAgent,
      userId: string,
      userMessage: string,
      response: string
    ) => {
      return (agent as any).processResponse(userId, userMessage, response);
    };

    it('should save schedule to DB when no scheduler', async () => {
      const response = '[SCHEDULE:0 9 * * *:Good morning!]';

      await processResponse(agent, 'user1', 'remind me', response);

      expect(mockMemory.saveSchedule).toHaveBeenCalledWith(
        expect.stringContaining('schedule_'),
        'user1',
        '0 9 * * *',
        'Good morning!'
      );
    });
  });

  describe('StreamingCallbacks Interface', () => {
    it('should have all required callback types', () => {
      const callbacks: StreamingCallbacks = {
        onStart: vi.fn(),
        onTextContent: vi.fn(),
        onTextEnd: vi.fn(),
        onToolStart: vi.fn(),
        onToolEnd: vi.fn(),
        onA2UI: vi.fn(),
        onFinish: vi.fn(),
        onError: vi.fn(),
      };

      // All callbacks should be defined
      expect(callbacks.onStart).toBeDefined();
      expect(callbacks.onTextContent).toBeDefined();
      expect(callbacks.onTextEnd).toBeDefined();
      expect(callbacks.onToolStart).toBeDefined();
      expect(callbacks.onToolEnd).toBeDefined();
      expect(callbacks.onA2UI).toBeDefined();
      expect(callbacks.onFinish).toBeDefined();
      expect(callbacks.onError).toBeDefined();
    });
  });

  describe('A2UIAgentMessage Interface', () => {
    it('should support surfaceUpdate type', () => {
      const msg: A2UIAgentMessage = {
        type: 'surfaceUpdate',
        surfaceId: 'main',
        components: [{ id: 'text1' }],
      };
      expect(msg.type).toBe('surfaceUpdate');
    });

    it('should support dataModelUpdate type', () => {
      const msg: A2UIAgentMessage = {
        type: 'dataModelUpdate',
        modelId: 'form',
        data: { name: 'John' },
      };
      expect(msg.type).toBe('dataModelUpdate');
    });

    it('should support beginRendering type', () => {
      const msg: A2UIAgentMessage = {
        type: 'beginRendering',
        surfaceId: 'main',
        root: 'root-component',
      };
      expect(msg.type).toBe('beginRendering');
    });
  });
});
