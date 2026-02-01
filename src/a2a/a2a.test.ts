/**
 * A2A Protocol Tests
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  A2AServer,
  A2AClient,
  A2AOrchestrator,
  createTextMessage,
  extractTextFromMessage,
  getMichaelAgentCard,
  JSON_RPC_ERRORS,
  type A2AMessage,
  type JSONRPCRequest,
} from './index.js';

describe('A2A Types', () => {
  describe('createTextMessage', () => {
    it('should create a text message', () => {
      const message = createTextMessage('user', 'Hello!');
      expect(message.role).toBe('user');
      expect(message.parts).toHaveLength(1);
      expect(message.parts[0]).toEqual({ type: 'text', text: 'Hello!' });
    });
  });

  describe('extractTextFromMessage', () => {
    it('should extract text from message parts', () => {
      const message: A2AMessage = {
        role: 'assistant',
        parts: [
          { type: 'text', text: 'Hello' },
          { type: 'text', text: 'World' },
        ],
      };
      expect(extractTextFromMessage(message)).toBe('Hello\nWorld');
    });

    it('should handle non-text parts', () => {
      const message: A2AMessage = {
        role: 'assistant',
        parts: [
          { type: 'text', text: 'Hello' },
          { type: 'file', mimeType: 'image/png', url: 'http://example.com/img.png' },
        ],
      };
      expect(extractTextFromMessage(message)).toBe('Hello');
    });
  });
});

describe('Agent Card', () => {
  it('should return Michael agent card', () => {
    const card = getMichaelAgentCard();
    expect(card.name).toBe('michael');
    expect(card.version).toBe('1.0.0');
    expect(card.capabilities.streaming).toBe(true);
    expect(card.capabilities.a2ui).toBe(true);
    expect(card.skills).toBeDefined();
    expect(card.skills!.length).toBeGreaterThan(0);
  });

  it('should allow custom URL', () => {
    const card = getMichaelAgentCard('https://custom.example.com');
    expect(card.url).toBe('https://custom.example.com');
  });
});

describe('A2A Server', () => {
  let server: A2AServer;

  beforeEach(() => {
    server = new A2AServer();
  });

  afterEach(() => {
    server.destroy();
  });

  it('should return method not found for unknown methods', async () => {
    const request: JSONRPCRequest = {
      jsonrpc: '2.0',
      id: '1',
      method: 'unknown/method',
    };

    const response = await server.handleRequest(request);
    expect(response.error).toBeDefined();
    expect(response.error!.code).toBe(JSON_RPC_ERRORS.METHOD_NOT_FOUND);
  });

  it('should handle message/send without handler', async () => {
    const request: JSONRPCRequest = {
      jsonrpc: '2.0',
      id: '1',
      method: 'message/send',
      params: {
        message: { role: 'user', parts: [{ type: 'text', text: 'Hello' }] },
      },
    };

    const response = await server.handleRequest(request);
    expect(response.error).toBeDefined();
    expect(response.error!.code).toBe(JSON_RPC_ERRORS.AGENT_UNAVAILABLE);
  });

  it('should handle message/send with handler', async () => {
    server.setHandler({
      processMessage: async (message) => {
        return createTextMessage('assistant', 'Response: ' + extractTextFromMessage(message));
      },
    });

    const request: JSONRPCRequest = {
      jsonrpc: '2.0',
      id: '1',
      method: 'message/send',
      params: {
        message: { role: 'user', parts: [{ type: 'text', text: 'Hello' }] },
      },
    };

    const response = await server.handleRequest(request);
    expect(response.error).toBeUndefined();
    expect(response.result).toBeDefined();
    const result = response.result as { task: { id: string; status: string } };
    expect(result.task.id).toBeDefined();
    // Task may be pending, working, or completed depending on timing
    expect(['pending', 'working', 'completed']).toContain(result.task.status);
  });

  it('should handle tasks/get for non-existent task', async () => {
    const request: JSONRPCRequest = {
      jsonrpc: '2.0',
      id: '1',
      method: 'tasks/get',
      params: { taskId: 'non_existent' },
    };

    const response = await server.handleRequest(request);
    expect(response.error).toBeDefined();
    expect(response.error!.code).toBe(JSON_RPC_ERRORS.TASK_NOT_FOUND);
  });

  it('should handle tasks/list', async () => {
    const request: JSONRPCRequest = {
      jsonrpc: '2.0',
      id: '1',
      method: 'tasks/list',
      params: {},
    };

    const response = await server.handleRequest(request);
    expect(response.error).toBeUndefined();
    expect(response.result).toBeDefined();
    const result = response.result as { tasks: unknown[]; total: number };
    expect(result.tasks).toBeDefined();
    expect(result.total).toBeDefined();
  });

  it('should return agent card JSON', () => {
    const cardJson = server.getAgentCard();
    const card = JSON.parse(cardJson);
    expect(card.name).toBe('michael');
  });
});

describe('A2A Client', () => {
  let client: A2AClient;

  beforeEach(() => {
    client = new A2AClient({
      timeoutMs: 5000,
      retry: { maxRetries: 1, baseDelayMs: 100 },
    });
  });

  it('should handle fetch errors gracefully', async () => {
    // Mock fetch to fail
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));

    await expect(
      client.getAgentCard('http://non-existent.example.com')
    ).rejects.toThrow();
  });

  it('should clear cache', () => {
    client.clearCache();
    // No error means success
  });
});

describe('A2A Orchestrator', () => {
  let orchestrator: A2AOrchestrator;

  beforeEach(() => {
    orchestrator = new A2AOrchestrator();
  });

  afterEach(() => {
    orchestrator.destroy();
  });

  it('should register and unregister agents', () => {
    orchestrator.registerAgent('test', 'http://test.example.com');
    expect(orchestrator.getAgent('test')).toBeDefined();
    expect(orchestrator.getAgent('test')!.url).toBe('http://test.example.com');

    orchestrator.unregisterAgent('test');
    expect(orchestrator.getAgent('test')).toBeUndefined();
  });

  it('should get all registered agents', () => {
    orchestrator.registerAgent('agent1', 'http://agent1.example.com');
    orchestrator.registerAgent('agent2', 'http://agent2.example.com');

    const agents = orchestrator.getAllAgents();
    expect(agents).toHaveLength(2);
  });

  it('should get healthy agents only', () => {
    orchestrator.registerAgent('healthy', 'http://healthy.example.com');
    orchestrator.registerAgent('unhealthy', 'http://unhealthy.example.com');

    // Mark one as unhealthy
    const unhealthy = orchestrator.getAgent('unhealthy');
    if (unhealthy) unhealthy.healthy = false;

    const healthyAgents = orchestrator.getHealthyAgents();
    expect(healthyAgents).toHaveLength(1);
    expect(healthyAgents[0].name).toBe('healthy');
  });

  it('should throw for unknown agent', async () => {
    await expect(
      orchestrator.sendToAgent('unknown', 'Hello')
    ).rejects.toThrow('Agent not found');
  });

  it('should throw for unhealthy agent', async () => {
    orchestrator.registerAgent('unhealthy', 'http://unhealthy.example.com');
    const agent = orchestrator.getAgent('unhealthy');
    if (agent) agent.healthy = false;

    await expect(
      orchestrator.sendToAgent('unhealthy', 'Hello')
    ).rejects.toThrow('Agent unhealthy');
  });
});
