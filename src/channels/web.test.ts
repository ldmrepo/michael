import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { WebChannel, createWebChannel, WebChannelConfig } from './web.js';

// Store the mock WebSocket instance for each test
let mockWsInstance: any = null;

// Mock WebSocket
vi.mock('ws', () => {
  return {
    WebSocket: vi.fn().mockImplementation(() => {
      const handlers: Record<string, Function[]> = {};
      mockWsInstance = {
        on: vi.fn((event: string, handler: Function) => {
          if (!handlers[event]) handlers[event] = [];
          handlers[event].push(handler);
        }),
        send: vi.fn(),
        close: vi.fn(),
        // Helper to trigger events in tests
        _trigger: (event: string, ...args: unknown[]) => {
          handlers[event]?.forEach((h) => h(...args));
        },
        _handlers: handlers,
      };
      return mockWsInstance;
    }),
  };
});

describe('WebChannel', () => {
  let channel: WebChannel;
  const config: WebChannelConfig = {
    gatewayUrl: 'ws://localhost:18789',
    channelId: 'test_channel',
    reconnect: {
      enabled: false,
      maxRetries: 3,
      baseDelayMs: 100,
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockWsInstance = null;
    channel = new WebChannel(config);
  });

  afterEach(() => {
    channel.disconnect();
  });

  describe('Configuration', () => {
    it('should use provided channelId', () => {
      expect(channel.getChannelId()).toBe('test_channel');
    });

    it('should generate channelId if not provided', () => {
      const ch = new WebChannel({ gatewayUrl: 'ws://localhost:18789' });
      expect(ch.getChannelId()).toMatch(/^web_\d+_[a-z0-9]+$/);
    });

    it('should start in disconnected state', () => {
      expect(channel.getState()).toBe('disconnected');
    });
  });

  describe('Connection', () => {
    it('should connect to gateway', async () => {
      const connectPromise = channel.connect();

      // Simulate successful connection
      mockWsInstance._trigger('open');

      await connectPromise;

      expect(channel.getState()).toBe('connected');
    });

    it('should call onConnect handler', async () => {
      const onConnect = vi.fn();
      channel.on('onConnect', onConnect);

      const connectPromise = channel.connect();
      mockWsInstance._trigger('open');

      await connectPromise;

      expect(onConnect).toHaveBeenCalled();
    });

    it('should handle connection error', async () => {
      const onError = vi.fn();
      channel.on('onError', onError);

      const connectPromise = channel.connect();
      mockWsInstance._trigger('error', new Error('Connection refused'));

      await expect(connectPromise).rejects.toThrow();
    });

    it('should handle disconnect', async () => {
      const onDisconnect = vi.fn();
      channel.on('onDisconnect', onDisconnect);

      const connectPromise = channel.connect();
      mockWsInstance._trigger('open');
      await connectPromise;

      mockWsInstance._trigger('close', 1000, Buffer.from('Normal closure'));

      expect(onDisconnect).toHaveBeenCalledWith(1000, 'Normal closure');
      expect(channel.getState()).toBe('disconnected');
    });
  });

  describe('Message Handling', () => {
    it('should send message to gateway', async () => {
      const connectPromise = channel.connect();
      mockWsInstance._trigger('open');
      await connectPromise;

      channel.sendMessage('user_123', 'Hello!');

      expect(mockWsInstance.send).toHaveBeenCalledWith(
        expect.stringContaining('"from":"web"')
      );
      expect(mockWsInstance.send).toHaveBeenCalledWith(
        expect.stringContaining('"to":"agent"')
      );
      expect(mockWsInstance.send).toHaveBeenCalledWith(
        expect.stringContaining('"content":"Hello!"')
      );
    });

    it('should not send if disconnected', () => {
      channel.sendMessage('user_123', 'Hello!');
      // Should not throw, just log error
      expect(channel.getState()).toBe('disconnected');
    });

    it('should call onMessage handler', async () => {
      const onMessage = vi.fn();
      channel.on('onMessage', onMessage);

      const connectPromise = channel.connect();
      mockWsInstance._trigger('open');
      await connectPromise;

      const message = {
        from: 'agent',
        to: 'web',
        userId: 'user_123',
        content: 'Hello!',
      };
      mockWsInstance._trigger('message', JSON.stringify(message));

      expect(onMessage).toHaveBeenCalledWith(expect.objectContaining(message));
    });
  });

  describe('AG-UI Event Handling', () => {
    it('should handle RUN_STARTED event', async () => {
      const onRunStarted = vi.fn();
      channel.on('onRunStarted', onRunStarted);

      const connectPromise = channel.connect();
      mockWsInstance._trigger('open');
      await connectPromise;

      const event = {
        from: 'agent',
        to: 'web',
        userId: 'user_123',
        content: '',
        eventType: 'RUN_STARTED',
        threadId: 'thread_1',
        runId: 'run_1',
      };
      mockWsInstance._trigger('message', JSON.stringify(event));

      expect(onRunStarted).toHaveBeenCalledWith('thread_1', 'run_1');
    });

    it('should handle TEXT_MESSAGE_CONTENT event', async () => {
      const onTextMessageContent = vi.fn();
      channel.on('onTextMessageContent', onTextMessageContent);

      const connectPromise = channel.connect();
      mockWsInstance._trigger('open');
      await connectPromise;

      const event = {
        from: 'agent',
        to: 'web',
        userId: 'user_123',
        content: '',
        eventType: 'TEXT_MESSAGE_CONTENT',
        messageId: 'msg_1',
        delta: 'Hello',
      };
      mockWsInstance._trigger('message', JSON.stringify(event));

      expect(onTextMessageContent).toHaveBeenCalledWith('msg_1', 'Hello');
    });

    it('should handle RUN_ERROR event', async () => {
      const onRunError = vi.fn();
      channel.on('onRunError', onRunError);

      const connectPromise = channel.connect();
      mockWsInstance._trigger('open');
      await connectPromise;

      const event = {
        from: 'agent',
        to: 'web',
        userId: 'user_123',
        content: '',
        eventType: 'RUN_ERROR',
        threadId: 'thread_1',
        runId: 'run_1',
        errorMessage: 'Something went wrong',
        errorCode: 'ERR_001',
      };
      mockWsInstance._trigger('message', JSON.stringify(event));

      expect(onRunError).toHaveBeenCalledWith('thread_1', 'run_1', 'Something went wrong', 'ERR_001');
    });

    it('should handle TOOL_CALL_START event', async () => {
      const onToolCallStart = vi.fn();
      channel.on('onToolCallStart', onToolCallStart);

      const connectPromise = channel.connect();
      mockWsInstance._trigger('open');
      await connectPromise;

      const event = {
        from: 'agent',
        to: 'web',
        userId: 'user_123',
        content: '',
        eventType: 'TOOL_CALL_START',
        toolCallId: 'tool_1',
        toolCallName: 'search_flights',
      };
      mockWsInstance._trigger('message', JSON.stringify(event));

      expect(onToolCallStart).toHaveBeenCalledWith('tool_1', 'search_flights');
    });
  });

  describe('A2UI Event Handling', () => {
    it('should handle surfaceUpdate A2UI event', async () => {
      const onA2UISurfaceUpdate = vi.fn();
      channel.on('onA2UISurfaceUpdate', onA2UISurfaceUpdate);

      const connectPromise = channel.connect();
      mockWsInstance._trigger('open');
      await connectPromise;

      const event = {
        from: 'agent',
        to: 'web',
        userId: 'user_123',
        content: '',
        a2ui: {
          type: 'surfaceUpdate',
          surfaceId: 'main',
          components: [
            { id: 'text1', component: { Text: { text: 'Hello' } } },
          ],
        },
      };
      mockWsInstance._trigger('message', JSON.stringify(event));

      expect(onA2UISurfaceUpdate).toHaveBeenCalledWith('main', expect.any(Array));
    });

    it('should handle dataModelUpdate A2UI event', async () => {
      const onA2UIDataUpdate = vi.fn();
      channel.on('onA2UIDataUpdate', onA2UIDataUpdate);

      const connectPromise = channel.connect();
      mockWsInstance._trigger('open');
      await connectPromise;

      const event = {
        from: 'agent',
        to: 'web',
        userId: 'user_123',
        content: '',
        a2ui: {
          type: 'dataModelUpdate',
          modelId: 'booking',
          data: { date: '2026-03-15', destination: 'Tokyo' },
        },
      };
      mockWsInstance._trigger('message', JSON.stringify(event));

      expect(onA2UIDataUpdate).toHaveBeenCalledWith('booking', { date: '2026-03-15', destination: 'Tokyo' });
    });
  });

  describe('Factory Function', () => {
    it('should create WebChannel instance', () => {
      const ch = createWebChannel({ gatewayUrl: 'ws://localhost:18789' });
      expect(ch).toBeInstanceOf(WebChannel);
    });
  });
});
