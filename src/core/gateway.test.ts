import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { Gateway, GatewayMessage } from './gateway.js';
import WebSocket from 'ws';

describe('Gateway', () => {
  let gateway: Gateway;
  // Use a random port to avoid EADDRINUSE between test runs
  const testPort = 18790 + Math.floor(Math.random() * 1000);
  let testClients: WebSocket[] = [];

  function createTestClient(): WebSocket {
    const client = new WebSocket(`ws://127.0.0.1:${testPort}`);
    client.on('error', () => {}); // suppress uncaught ECONNREFUSED
    testClients.push(client);
    return client;
  }

  function closeClient(client: WebSocket): Promise<void> {
    return new Promise((resolve) => {
      if (client.readyState === WebSocket.CLOSED) { resolve(); return; }
      client.on('close', () => resolve());
      if (client.readyState === WebSocket.CONNECTING) {
        client.on('open', () => client.close());
        client.on('error', () => resolve());
        return;
      }
      if (client.readyState !== WebSocket.CLOSING) { client.close(); }
    });
  }

  function waitForOpen(client: WebSocket): Promise<void> {
    return new Promise((resolve, reject) => {
      client.on('open', () => resolve());
      client.on('error', (err) => reject(err));
    });
  }

  function waitForMessage(client: WebSocket): Promise<GatewayMessage> {
    return new Promise((resolve) => {
      client.once('message', (data) => {
        resolve(JSON.parse(data.toString()));
      });
    });
  }

  beforeEach(async () => {
    gateway = new Gateway(testPort);
    await gateway.start();
  });

  afterEach(async () => {
    await Promise.all(testClients.map(closeClient));
    testClients = [];
    await gateway.close();
  });

  describe('Connection', () => {
    it('should accept client connections', async () => {
      const client = createTestClient();
      await waitForOpen(client);
      expect(client.readyState).toBe(WebSocket.OPEN);
      client.close();
    });

    it('should send welcome message on connection', async () => {
      const client = createTestClient();
      const message = await waitForMessage(client);
      expect(message.content).toBe('Connected to Michael Gateway');
      expect(message.from).toBe('agent');
      expect(message.metadata).toHaveProperty('clientId');
      client.close();
    });

    it('should track connected clients', async () => {
      const client = createTestClient();
      await waitForOpen(client);
      await new Promise((r) => setTimeout(r, 100));
      const clients = gateway.getClients();
      expect(clients.length).toBeGreaterThan(0);
      client.close();
    });
  });

  describe('Messaging', () => {
    it('should handle invalid JSON messages', async () => {
      const client = createTestClient();

      // Wait for welcome
      await waitForMessage(client);

      // Send invalid JSON and wait for error response
      const errorPromise = waitForMessage(client);
      client.send('invalid json{');
      const message = await errorPromise;

      expect(message.content).toBe('Invalid message format');
      expect(message.metadata).toHaveProperty('error');
      client.close();
    });
  });

  describe('Client Management', () => {
    it('should remove disconnected clients', async () => {
      const client = createTestClient();
      await waitForOpen(client);
      await new Promise((r) => setTimeout(r, 100));

      const clientsBefore = gateway.getClients();
      expect(clientsBefore.length).toBeGreaterThan(0);

      client.close();
      await new Promise((r) => setTimeout(r, 100));

      const clientsAfter = gateway.getClients();
      expect(clientsAfter.length).toBeLessThan(clientsBefore.length);
    });

    it('should handle multiple simultaneous connections', async () => {
      const clients: WebSocket[] = [];

      for (let i = 0; i < 5; i++) {
        const client = createTestClient();
        clients.push(client);
      }

      await Promise.all(clients.map(waitForOpen));
      await new Promise((r) => setTimeout(r, 100));

      const gatewayClients = gateway.getClients();
      expect(gatewayClients.length).toBe(5);

      clients.forEach(c => c.close());
    });
  });

  describe('Broadcast', () => {
    it('should broadcast message to all clients', async () => {
      const clients: WebSocket[] = [];
      const numClients = 3;

      for (let i = 0; i < numClients; i++) {
        clients.push(createTestClient());
      }

      // Wait for all welcome messages
      await Promise.all(clients.map(waitForMessage));

      // Set up listeners for broadcast
      const broadcastPromises = clients.map((client) =>
        new Promise<GatewayMessage>((resolve) => {
          client.on('message', (data) => {
            const msg: GatewayMessage = JSON.parse(data.toString());
            if (msg.content === 'Broadcast test') resolve(msg);
          });
        })
      );

      await new Promise((r) => setTimeout(r, 100));
      gateway.broadcast({
        from: 'agent',
        to: 'telegram',
        userId: 'system',
        content: 'Broadcast test',
      });

      const results = await Promise.all(broadcastPromises);
      results.forEach((msg) => {
        expect(msg.content).toBe('Broadcast test');
      });

      clients.forEach(c => c.close());
    });
  });
});
